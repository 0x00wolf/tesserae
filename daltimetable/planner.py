"""
daltimetable.planner -- find every conflict-free way to fit a set of courses into
a set of terms.

    from daltimetable import DalTimetable, SchedulePlanner, Elective, Commitment

    timetable = DalTimetable()
    planner = SchedulePlanner(
        timetable,
        courses=["CSCI 2134", "CSCI 3130", "MATH 2060"],
        terms=["202710", "202720"],
        min_per_term=1,
        max_per_term=2,
    )
    for schedule in planner.schedules(limit=10):
        print(schedule.describe())

See docs/MODULES.md for the full API.
"""

from dataclasses import dataclass

from .timetable import (
    DAY_NAMES,
    Meeting,
    Section,
    SectionSet,
    normalize_course,
    split_course,
    _read_clock,
    _read_days,
)

# Banner writes a link code as the component it points at plus a group digit:
# a lecture carrying "B0" wants a lab carrying "L0", and "B0, T0" wants one of
# each. Verified on COMM 1010, where lecture 01 (B0) pairs with labs B01-B05
# (L0) and lecture 02 (B1) pairs with labs B06-B10 (L1).
LINK_COMPONENT = {"L": "Lecture", "B": "Lab", "T": "Tutorial"}


class PlannerError(Exception):
    """A request the planner cannot make sense of."""


# ---------------------------------------------------------------------------
# What you hand the planner
# ---------------------------------------------------------------------------

class Elective:
    """
    A slot to be filled from a pool of candidate courses.

    Three ways to say what the pool is:

        Elective(["PHYC 2451", "PHYC 2452"], pick=1)   # one of these two
        Elective(subject="PHYC", level=1000, pick=1)   # any 1000-level physics
        Elective(some_section_set, pick=1)             # anything in this set

    pick is how many courses to take from the pool.
    """

    def __init__(self, pool=None, pick=1, subject=None, level=None):
        if pick < 1:
            raise PlannerError("an elective must pick at least one course")
        self.pick = pick
        self.subject = subject.strip().upper() if subject else None
        self.level = level
        self.courses = None
        self.section_set = None

        if isinstance(pool, SectionSet):
            self.section_set = pool
        elif pool is not None:
            self.courses = []
            for entry in pool:
                self.courses.append(normalize_course(entry))
        elif self.subject is None:
            raise PlannerError(
                "an elective needs either a list of courses, a SectionSet, "
                "or a subject= to draw from")

    def candidates(self, timetable, terms):
        """The course names this slot may be filled with."""
        if self.courses is not None:
            return list(self.courses)
        if self.section_set is not None:
            sections = self.section_set
        else:
            sections = timetable.sections(terms, [self.subject])
            if self.level is not None:
                sections = sections.level(self.level)
        names = []
        for course, _title in sections.courses():
            names.append(course)
        return names

    def __repr__(self):
        if self.courses is not None:
            return "Elective(%r, pick=%d)" % (self.courses, self.pick)
        if self.subject is not None:
            return "Elective(subject=%r, level=%r, pick=%d)" % (
                self.subject, self.level, self.pick)
        return "Elective(<%d sections>, pick=%d)" % (len(self.section_set), self.pick)


class Commitment:
    """
    Hours that must stay free, for something that is not a Dal course.

        Commitment("Work", "MW", "17:00", "21:00")
        Commitment("Commute", ["Friday"], "08:00", "09:00", term="202710")

    Anything that IS a Dal section -- a lab you TA -- should come from
    DalTimetable.section() instead, so its times are Banner's rather than
    typed by hand.
    """

    def __init__(self, label, days, start, end, room="", term=None, title=""):
        self.label = label
        self.title = title or label
        self.days = tuple(sorted(_read_days(days), key=DAY_NAMES.index))
        self.start_minutes = _read_clock(start)
        self.end_minutes = _read_clock(end)
        if self.end_minutes <= self.start_minutes:
            raise PlannerError("%s ends before it starts" % label)
        self.room = room
        self.term = term

    def meetings(self):
        return (Meeting(
            days=self.days,
            start=_clock(self.start_minutes),
            end=_clock(self.end_minutes),
            start_minutes=self.start_minutes,
            end_minutes=self.end_minutes,
            room=self.room,
            delivery="In Person" if self.room else "Unknown",
        ),)

    def __repr__(self):
        return "Commitment(%r, %r, %s-%s)" % (
            self.label, "".join(day[:2] for day in self.days),
            _clock(self.start_minutes), _clock(self.end_minutes))


@dataclass(frozen=True)
class Busy:
    """One commitment as the planner sees it: a label, a term, and meetings."""

    label: str
    title: str
    term: str            # None means every term
    meetings: tuple
    section: Section = None


# ---------------------------------------------------------------------------
# What the planner gives back
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CourseChoice:
    """One course and the sections you would register in together."""

    course: str
    title: str
    sections: tuple

    def __str__(self):
        return "%s  %s" % (self.course, self.title)


@dataclass(frozen=True)
class Schedule:
    """One complete arrangement: which courses in which term, and which sections."""

    terms: dict
    commitments: tuple = ()
    variation: int = 1

    def choices(self, term):
        return self.terms.get(term, ())

    def course_names(self, term=None):
        names = []
        if term is None:
            keys = sorted(self.terms)
        else:
            keys = [term]
        for key in keys:
            for choice in self.terms.get(key, ()):
                names.append(choice.course)
        return names

    def rows(self):
        """
        Flat tuples, one per meeting:

            ("202720", "CSCI 1315", "Lecture",
             ["Monday", "Wednesday", "Friday"], "12:35-13:25", "Rowe 1009")

        A section that meets on two patterns produces two rows.
        """
        out = []
        for term in sorted(self.terms):
            for choice in self.terms[term]:
                for section in choice.sections:
                    for meeting in section.meetings:
                        out.append((
                            term,
                            choice.course,
                            section.component,
                            list(meeting.days),
                            meeting.clock(),
                            meeting.room,
                        ))
        return out

    def describe(self, term_names=None):
        """A plain text summary of the whole schedule."""
        if term_names is None:
            term_names = {}
        lines = []
        for term in sorted(self.terms):
            heading = term_names.get(term, "Term %s" % term)
            choices = self.terms[term]
            lines.append("%s -- %d course%s"
                         % (heading, len(choices), "" if len(choices) == 1 else "s"))
            for choice in sorted(choices, key=lambda item: item.course):
                lines.append("  %-11s %s" % (choice.course, choice.title))
                for section in choice.sections:
                    lines.append("    %-9s %-4s %s" % (
                        section.component, section.section,
                        _meeting_text(section)))
            for busy in self.commitments:
                if busy.term is None or busy.term == term:
                    for meeting in busy.meetings:
                        lines.append("  %-11s %s  (%s)" % (
                            busy.label, _one_meeting_text(meeting), "kept free"))
        return "\n".join(lines)


def _meeting_text(section):
    parts = []
    for meeting in section.meetings:
        parts.append(_one_meeting_text(meeting))
    return "; ".join(parts)


def _one_meeting_text(meeting):
    if not meeting.scheduled:
        return "%s  %s" % (meeting.delivery, meeting.room)
    return "%-6s %s  %s" % (meeting.letters(), meeting.clock(), meeting.room)


def _clock(minutes):
    return "%02d:%02d" % (minutes // 60, minutes % 60)


# ---------------------------------------------------------------------------
# Conflicts
# ---------------------------------------------------------------------------

def meetings_overlap(first, second):
    """True if two meetings share a weekday and overlap in time."""
    if not first.scheduled or not second.scheduled:
        return False
    shares_a_day = False
    for day in first.days:
        if day in second.days:
            shares_a_day = True
            break
    if not shares_a_day:
        return False
    return (first.start_minutes < second.end_minutes
            and second.start_minutes < first.end_minutes)


def _clash(meetings_a, meetings_b):
    for first in meetings_a:
        for second in meetings_b:
            if meetings_overlap(first, second):
                return True
    return False


# ---------------------------------------------------------------------------
# The planner
# ---------------------------------------------------------------------------

class SchedulePlanner:
    """
    Every conflict-free way to place `courses` across `terms`.

    Each term ends up holding between min_per_term and max_per_term courses.
    Electives add courses chosen from a pool; commitments are hours that stay
    free without counting toward the per-term totals.
    """

    def __init__(self, timetable, courses, terms, min_per_term, max_per_term,
                 electives=None, commitments=None,
                 earliest=None, latest=None, require_seats=False):
        self.timetable = timetable
        self.terms = []
        for term in terms:
            self.terms.append(str(term).strip())
        if not self.terms:
            raise PlannerError("at least one term is required")

        self.courses = []
        for entry in courses:
            name = normalize_course(entry)
            if name not in self.courses:
                self.courses.append(name)

        if min_per_term > max_per_term:
            raise PlannerError("min_per_term is larger than max_per_term")
        self.min_per_term = min_per_term
        self.max_per_term = max_per_term

        self.electives = list(electives) if electives else []
        self.earliest = _read_clock(earliest) if earliest else None
        self.latest = _read_clock(latest) if latest else None
        self.require_seats = require_seats

        self.commitments = []
        for entry in commitments or []:
            self.commitments.append(_as_busy(entry))

        self._bundle_cache = {}

    # -- public -------------------------------------------------------------

    def schedules(self, limit=100):
        """Up to `limit` complete schedules, in a stable order."""
        self._check_subjects()
        found = []
        for extra in self._elective_sets():
            course_list = self.courses + list(extra)
            self._search(course_list, found, limit)
            if len(found) >= limit:
                break

        numbered = []
        for index in range(len(found)):
            numbered.append(Schedule(terms=found[index],
                                     commitments=tuple(self.commitments),
                                     variation=index + 1))
        return numbered

    def _check_subjects(self):
        """
        Catch a typo'd subject before anything else.

        Without this, an unreachable course would just make the search come
        back empty, which reads as "no schedule fits" rather than "CSC is not
        a subject".
        """
        subjects = []
        for course in self.courses:
            subject, _ = split_course(course)
            if subject not in subjects:
                subjects.append(subject)
        for elective in self.electives:
            if elective.subject is not None and elective.subject not in subjects:
                subjects.append(elective.subject)
            for name in elective.courses or []:
                subject, _ = split_course(name)
                if subject not in subjects:
                    subjects.append(subject)
        if subjects:
            self.timetable.check_subjects(subjects, self.terms)

    def offerings(self, course):
        """{term: [bundle, ...]} for one course -- useful when nothing fits."""
        found = {}
        for term in self.terms:
            found[term] = self._bundles(term, course)
        return found

    # -- electives ----------------------------------------------------------

    def _elective_sets(self):
        """Every combination of elective courses, as tuples of course names."""
        combinations = [()]
        for elective in self.electives:
            pool = []
            for name in elective.candidates(self.timetable, self.terms):
                if name not in self.courses:
                    pool.append(name)
            if len(pool) < elective.pick:
                return []
            picks = _combinations(pool, elective.pick)
            extended = []
            for partial in combinations:
                for pick in picks:
                    merged = partial + pick
                    if len(set(merged)) == len(merged):
                        extended.append(merged)
            combinations = extended
        return combinations

    # -- bundles ------------------------------------------------------------

    def _bundles(self, term, course):
        """
        The ways to register in one course in one term.

        A bundle is a lecture plus whatever lab or tutorial its link code
        demands. Bundles that clash with themselves, that fall outside the
        time window, or that have no seats are dropped here.
        """
        key = (term, course)
        if key in self._bundle_cache:
            return self._bundle_cache[key]

        subject, _ = split_course(course)
        sections = self.timetable.sections([term], [subject], course=course)
        sections = self._narrow(sections)

        lectures = []
        by_component = {}
        for section in sections:
            by_component.setdefault(section.component, []).append(section)
            if section.component == "Lecture":
                lectures.append(section)

        bundles = []
        if not lectures:
            # A thesis, workshop or ensemble stands alone.
            for section in sections:
                bundles.append((section,))
        else:
            for lecture in lectures:
                groups = []
                for component, digit in _partners(lecture):
                    matches = _matching(by_component.get(component, []), digit)
                    if matches:
                        groups.append(matches)
                for combination in _product(groups):
                    bundle = (lecture,) + combination
                    if not _self_clash(bundle):
                        bundles.append(bundle)

        self._bundle_cache[key] = bundles
        return bundles

    def _narrow(self, sections):
        if self.earliest is not None or self.latest is not None:
            floor = self.earliest if self.earliest is not None else 0
            ceiling = self.latest if self.latest is not None else 24 * 60
            sections = sections.between(_clock(floor), _clock(ceiling))
        if self.require_seats:
            sections = sections.with_seats()
        return sections

    # -- search -------------------------------------------------------------

    def _search(self, course_list, found, limit):
        if len(course_list) > len(self.terms) * self.max_per_term:
            return
        if len(course_list) < len(self.terms) * self.min_per_term:
            return

        ordered = sorted(course_list, key=lambda name: self._option_count(name))
        for course in ordered:
            if self._option_count(course) == 0:
                return

        placed = {}
        for term in self.terms:
            placed[term] = []
        self._place(ordered, 0, placed, found, limit)

    def _option_count(self, course):
        total = 0
        for term in self.terms:
            total += len(self._bundles(term, course))
        return total

    def _place(self, courses, index, placed, found, limit):
        if len(found) >= limit:
            return

        if index == len(courses):
            for term in self.terms:
                if len(placed[term]) < self.min_per_term:
                    return
            found.append(_snapshot(placed))
            return

        remaining = len(courses) - index
        needed = 0
        for term in self.terms:
            shortfall = self.min_per_term - len(placed[term])
            if shortfall > 0:
                needed += shortfall
        if remaining < needed:
            return

        course = courses[index]
        for term in self.terms:
            if len(placed[term]) >= self.max_per_term:
                continue
            for bundle in self._bundles(term, course):
                if not self._fits(bundle, term, placed[term]):
                    continue
                placed[term].append(CourseChoice(
                    course=course, title=bundle[0].title, sections=bundle))
                self._place(courses, index + 1, placed, found, limit)
                placed[term].pop()
                if len(found) >= limit:
                    return

    def _fits(self, bundle, term, already):
        for section in bundle:
            for busy in self.commitments:
                if busy.term is not None and busy.term != term:
                    continue
                if _clash(section.meetings, busy.meetings):
                    return False
            for choice in already:
                for other in choice.sections:
                    if _clash(section.meetings, other.meetings):
                        return False
        return True


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _as_busy(entry):
    if isinstance(entry, Busy):
        return entry
    if isinstance(entry, Commitment):
        return Busy(label=entry.label, title=entry.title, term=entry.term,
                    meetings=entry.meetings())
    if isinstance(entry, Section):
        return Busy(label=entry.course, title=entry.title, term=entry.term,
                    meetings=entry.meetings, section=entry)
    raise PlannerError(
        "a commitment must be a Section from DalTimetable.section() or a "
        "Commitment, got %r" % (entry,))


def _partners(lecture):
    """'B0, T0' -> [('Lab', '0'), ('Tutorial', '0')]."""
    found = []
    link = lecture.link
    if not link:
        return found
    for piece in link.split(","):
        piece = piece.strip()
        if len(piece) < 2:
            continue
        component = LINK_COMPONENT.get(piece[0])
        if component is not None and component != "Lecture":
            found.append((component, piece[1:]))
    return found


def _matching(candidates, digit):
    """
    Sections in the same link group.

    A few courses in the calendar point at a group that has no members --
    BUSI 5551 has a lecture linked to a lab group that does not exist -- so
    fall back to every section of that component rather than losing the course.
    """
    matched = []
    for section in candidates:
        link = section.link or ""
        for piece in link.split(","):
            piece = piece.strip()
            if len(piece) >= 2 and piece[1:] == digit:
                matched.append(section)
                break
    if matched:
        return matched
    return candidates


def _product(groups):
    combinations = [()]
    for group in groups:
        extended = []
        for partial in combinations:
            for section in group:
                extended.append(partial + (section,))
        combinations = extended
    return combinations


def _combinations(pool, size):
    """Every way to choose `size` items from pool, order ignored."""
    if size == 0:
        return [()]
    results = []
    for index in range(len(pool)):
        for rest in _combinations(pool[index + 1:], size - 1):
            results.append((pool[index],) + rest)
    return results


def _self_clash(bundle):
    for index in range(len(bundle)):
        for other in range(index + 1, len(bundle)):
            if _clash(bundle[index].meetings, bundle[other].meetings):
                return True
    return False


def _snapshot(placed):
    copy = {}
    for term in placed:
        copy[term] = tuple(placed[term])
    return copy
