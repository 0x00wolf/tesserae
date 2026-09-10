"""
daltimetable.timetable -- read Dalhousie's academic timetable.

The timetable page is an Ellucian Banner Extensibility page, and every filter on
it is backed by a JSON endpoint that needs no login. This module calls those
endpoints directly: no HTML parsing, no browser, no dependencies outside the
standard library.

    from daltimetable import DalTimetable

    timetable = DalTimetable()
    timetable.available_terms()
    timetable.sections(terms=["202720"], subjects=["CSCI"]).level(4000).courses()

See docs/MODULES.md for the full API.
"""

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date

BASE_URL = "https://self-service.dal.ca/BannerExtensibility/internalPb/virtualDomains."
USER_AGENT = "dal-timetable-planner/1.0 (student course-planning tool)"

# Campus groupings, as the timetable's "Locations:" checkboxes label them.
CAMPUSES = {"100": "Halifax", "200": "Truro", "300": "Online", "400": "Others"}
ALL_CAMPUSES = ["100", "200", "300", "400"]

# Banner packs a section's several meeting patterns into parallel <br>-joined
# lists across these columns plus TIMES and LOCATIONS. Index i across all of
# them describes one meeting.
DAY_COLUMNS = [
    ("SUNDAYS", "Sunday"),
    ("MONDAYS", "Monday"),
    ("TUESDAYS", "Tuesday"),
    ("WEDNESDAYS", "Wednesday"),
    ("THURSDAYS", "Thursday"),
    ("FRIDAYS", "Friday"),
    ("SATURDAYS", "Saturday"),
]

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday",
             "Thursday", "Friday", "Saturday"]

# Single letters, the way a timetable prints them. R is Thursday, U is Sunday.
DAY_LETTERS = {"U": "Sunday", "M": "Monday", "T": "Tuesday", "W": "Wednesday",
               "R": "Thursday", "F": "Friday", "S": "Saturday"}

# Banner's placeholder for "no scheduled meeting time -- consult the department".
NO_FIXED_TIME = "C/D"

# Banner's abbreviations for what kind of thing a section is.
COMPONENTS = {
    "Lec": "Lecture",
    "Lab": "Lab",
    "Tut": "Tutorial",
    "Ths": "Thesis",
    "Int": "Internship",
    "WkT": "Workshop",
    "WkS": "Workshop",
    "Ens": "Ensemble",
}

# Sections whose room changes partway through the term carry
# "*** 08-SEP-2026 - 09-DEC-2026 ***" header slots inside LOCATIONS.
DATE_RANGE_HEADER = re.compile(r"\*\*\*\s*(\S+)\s*-\s*(\S+)\s*\*\*\*")
HTML_TAG = re.compile(r"<[^>]+>")

MONTHS = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
          "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}

# Campus words Banner puts in front of every room string.
CAMPUS_WORDS = ["Studley", "Carleton", "Sexton", "Agricultural"]

# Long building names, shortened to something that fits on a timetable.
BUILDING_SHORT = [
    ("GOLDBERG COMPUTER SCIENCE BLDG", "Goldberg"),
    ("SIR JAMES DUNN BUILDING", "Dunn"),
    ("KENNETH C ROWE MANAGEMENT", "Rowe"),
    ("HENRY HICKS ACADEMIC ADMIN", "Hicks"),
    ("MONA CAMPBELL BUILDING", "Mona Campbell"),
    ("INDUSTRIAL ENG & CONT ED ADDIT", "Industrial Eng"),
    ("LSC-COMMON AREA", "LSC"),
    ("LSC-BIOL&EARTH", "LSC Biol"),
    ("LSC-PSYCHOLOGY", "LSC Psych"),
    ("MCCAIN ARTS&SS", "McCain"),
    ("KILLAM LIBRARY", "Killam"),
    ("WELDON LAW BLDG", "Weldon"),
    ("CHEMISTRY", "Chemistry"),
    ("CHASE BLDG", "Chase"),
    ("TUPPER BLDG", "Tupper"),
    ("DENTISTRY", "Dentistry"),
]


class TimetableError(Exception):
    """Anything this module refuses to do."""


class UnknownSubject(TimetableError):
    """A subject code Dalhousie does not offer."""


class NotFound(TimetableError):
    """A course or section that is not in the timetable."""


# ---------------------------------------------------------------------------
# Course names
# ---------------------------------------------------------------------------

def split_course(text):
    """
    Accept any of these and return ('CSCI', '2134'):

        csci2134   CSCI 2134   csci 2134   CSCI2134   CSCI-2134   csci  2134

    Dalhousie subject codes are all exactly four letters -- verified against
    the full list of 156 -- so the unseparated form splits at four safely.
    """
    if not isinstance(text, str):
        raise TimetableError("course must be a string, got %r" % (text,))
    cleaned = text.strip().upper().replace("-", " ").replace("_", " ")
    if " " in cleaned:
        subject, _, number = cleaned.partition(" ")
    else:
        subject, number = cleaned[:4], cleaned[4:]
    subject = subject.strip()
    number = number.strip()
    if not subject or not number:
        raise TimetableError(
            "could not read a subject and course number from %r "
            "-- try something like 'CSCI 2134'" % (text,))
    return (subject, number)


def normalize_course(text):
    """Any accepted spelling of a course name -> 'CSCI 2134'."""
    subject, number = split_course(text)
    return "%s %s" % (subject, number)


# ---------------------------------------------------------------------------
# What a section looks like
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Meeting:
    """One meeting pattern: a set of weekdays, a time, and a room."""

    days: tuple = ()
    start: str = None            # "08:35", or None when there is no fixed time
    end: str = None
    start_minutes: int = None    # 515, for arithmetic
    end_minutes: int = None
    room: str = ""
    delivery: str = "Unknown"    # In Person / Synchronous Session / ...
    first_date: date = None
    last_date: date = None

    @property
    def scheduled(self):
        return self.start_minutes is not None

    def clock(self):
        """'08:35-09:55', or the delivery mode when there is no fixed time."""
        if not self.scheduled:
            return self.delivery
        return "%s-%s" % (self.start, self.end)

    def letters(self):
        """('Monday', 'Wednesday') -> 'MW'."""
        text = ""
        for day in self.days:
            for letter, name in DAY_LETTERS.items():
                if name == day:
                    text += letter
        return text


@dataclass(frozen=True)
class Section:
    """One registerable section of one course."""

    term: str
    crn: str
    subject: str
    number: str
    title: str
    component: str               # Lecture / Lab / Tutorial / ...
    section: str                 # 01, 02, B01, T01
    credit_hours: float = 0
    link: str = None             # ties a lecture to its required lab/tutorial
    capacity: int = None
    enrolled: int = None
    seats_available: int = None
    meetings: tuple = ()

    @property
    def course(self):
        return "%s %s" % (self.subject, self.number)

    @property
    def level(self):
        """'2134' -> 2000. Returns None if the number does not start with a digit."""
        if self.number and self.number[0].isdigit():
            return int(self.number[0]) * 1000
        return None

    @property
    def scheduled(self):
        for meeting in self.meetings:
            if meeting.scheduled:
                return True
        return False

    def days(self):
        """Every weekday this section meets on, across all its meetings."""
        found = []
        for meeting in self.meetings:
            for day in meeting.days:
                if day not in found:
                    found.append(day)
        found.sort(key=DAY_NAMES.index)
        return tuple(found)

    def __str__(self):
        times = []
        for meeting in self.meetings:
            times.append(meeting.letters() + " " + meeting.clock())
        return "%s %s %s  %s" % (self.course, self.component,
                                 self.section, "; ".join(times))


# ---------------------------------------------------------------------------
# A list of sections you can narrow
# ---------------------------------------------------------------------------

class SectionSet(list):
    """
    A list of Section objects with a few filters that Banner cannot do itself.

    Every filter returns a new SectionSet, so they chain, and the result is
    still an ordinary list you can iterate, index and len().
    """

    def level(self, level):
        """.level(4000) keeps 4000-4999."""
        kept = SectionSet()
        for section in self:
            if section.level == level:
                kept.append(section)
        return kept

    def component(self, name):
        """.component('Lecture') -- also accepts Banner's 'Lec'."""
        wanted = COMPONENTS.get(name, name)
        kept = SectionSet()
        for section in self:
            if section.component == wanted:
                kept.append(section)
        return kept

    def on_days(self, days):
        """
        Keep sections that meet only on these weekdays.

        Accepts "TR", "MWF" or ["Tuesday", "Thursday"]. A section with no fixed
        meeting time meets on no day, so it is kept -- it cannot violate a day
        preference.
        """
        allowed = _read_days(days)
        kept = SectionSet()
        for section in self:
            ok = True
            for meeting in section.meetings:
                for day in meeting.days:
                    if day not in allowed:
                        ok = False
            if ok:
                kept.append(section)
        return kept

    def between(self, earliest, latest):
        """
        Keep sections whose every meeting falls inside the window.

        .between("10:00", "17:00") drops both the 08:35s and the evening
        classes. Sections with no fixed time are kept.
        """
        floor = _read_clock(earliest)
        ceiling = _read_clock(latest)
        kept = SectionSet()
        for section in self:
            ok = True
            for meeting in section.meetings:
                if not meeting.scheduled:
                    continue
                if meeting.start_minutes < floor or meeting.end_minutes > ceiling:
                    ok = False
            if ok:
                kept.append(section)
        return kept

    def with_seats(self):
        """
        Keep sections that had a free seat when the timetable was read.

        Seat counts are a snapshot and drift daily -- see the README.
        Sections whose count Banner did not report are dropped.
        """
        kept = SectionSet()
        for section in self:
            if section.seats_available is not None and section.seats_available > 0:
                kept.append(section)
        return kept

    def courses(self):
        """
        Collapse to distinct courses: [('CSCI 2134', 'Software Development'), ...]

        A course with four sections appears once. Sorted by course code.
        """
        titles = {}
        for section in self:
            if section.course not in titles:
                titles[section.course] = section.title
        rows = []
        for course in sorted(titles):
            rows.append((course, titles[course]))
        return rows

    def terms(self):
        """The distinct term codes present, in order."""
        found = []
        for section in self:
            if section.term not in found:
                found.append(section.term)
        found.sort()
        return found


def _read_days(days):
    """"TR" or ["Tuesday","Thursday"] -> {"Tuesday","Thursday"}."""
    allowed = set()
    if isinstance(days, str):
        for letter in days.upper():
            if letter in DAY_LETTERS:
                allowed.add(DAY_LETTERS[letter])
            else:
                raise TimetableError(
                    "'%s' is not a day letter -- use U M T W R F S "
                    "(R is Thursday)" % letter)
    else:
        for day in days:
            name = str(day).strip().title()
            if name not in DAY_NAMES:
                raise TimetableError("'%s' is not a weekday" % day)
            allowed.add(name)
    return allowed


def _read_clock(text):
    """"10:00" or "1000" -> 600."""
    cleaned = str(text).strip().replace(":", "")
    if len(cleaned) != 4 or not cleaned.isdigit():
        raise TimetableError("'%s' is not a time -- use '10:00'" % text)
    return int(cleaned[:2]) * 60 + int(cleaned[2:])


# ---------------------------------------------------------------------------
# Parsing Banner's rows
# ---------------------------------------------------------------------------

def _strip_html(text):
    return HTML_TAG.sub("", text or "").strip()


def _split_multi(value, length):
    if value is None:
        parts = [""]
    else:
        parts = value.split("<br>")
    while len(parts) < length:
        parts.append("")
    return parts[:length]


def _clock_from(text):
    text = text.strip()
    if len(text) != 4 or not text.isdigit():
        return (None, None)
    minutes = int(text[:2]) * 60 + int(text[2:])
    return ("%s:%s" % (text[:2], text[2:]), minutes)


def _time_range(text):
    text = (text or "").strip()
    if text == "" or text == NO_FIXED_TIME or "-" not in text:
        return (None, None, None, None)
    start_text, _, end_text = text.partition("-")
    start, start_minutes = _clock_from(start_text)
    end, end_minutes = _clock_from(end_text)
    return (start, end, start_minutes, end_minutes)


def _read_date(text):
    """'08-SEP-2026' -> date(2026, 9, 8)."""
    if not text:
        return None
    parts = str(text).strip().split("-")
    if len(parts) != 3:
        return None
    day, month, year = parts
    if month.upper() not in MONTHS:
        return None
    try:
        return date(int(year), MONTHS[month.upper()], int(day))
    except ValueError:
        return None


def tidy_room(location):
    """'Studley GOLDBERG COMPUTER SCIENCE BLDG 134' -> 'Goldberg 134'."""
    if not location:
        return "room TBA"
    text = location.strip()
    for campus in CAMPUS_WORDS:
        if text.startswith(campus + " "):
            text = text[len(campus) + 1:]
            break
    for long_name, short_name in BUILDING_SHORT:
        if text.startswith(long_name):
            remainder = text[len(long_name):].strip()
            if remainder:
                return "%s %s" % (short_name, remainder)
            return short_name
    if text.lower().startswith("consult"):
        return "room TBA"
    if text.startswith("Online-"):
        return text[len("Online-"):].strip().title()
    return text


def _delivery(location):
    text = (location or "").strip()
    if text.startswith("Online-"):
        return text[len("Online-"):].strip().title()
    if text.startswith("Consult"):
        return "Consult Department"
    if text == "":
        return "Unknown"
    return "In Person"


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _meetings_from(row):
    """
    Unpack a Banner row's parallel <br>-joined lists into Meeting objects.

    Two slot kinds are not meetings: date-range headers, which scope the
    meetings that follow to a narrower window, and blank padding slots.
    """
    time_slots = (row.get("TIMES") or "").split("<br>")
    slot_count = len(time_slots)

    locations = _split_multi(row.get("LOCATIONS"), slot_count)
    day_slots = {}
    for column, day_name in DAY_COLUMNS:
        day_slots[day_name] = _split_multi(row.get(column), slot_count)

    active_from = _read_date(row.get("START_DATE"))
    active_to = _read_date(row.get("END_DATE"))

    meetings = []
    for index in range(slot_count):
        raw_location = locations[index]

        header = DATE_RANGE_HEADER.search(raw_location)
        if header is not None:
            active_from = _read_date(header.group(1)) or active_from
            active_to = _read_date(header.group(2)) or active_to
            continue

        days = []
        for column, day_name in DAY_COLUMNS:
            if day_slots[day_name][index].strip() != "":
                days.append(day_name)

        start, end, start_minutes, end_minutes = _time_range(time_slots[index])
        raw_room = _strip_html(raw_location)

        if not days and start is None and raw_room == "":
            continue

        meetings.append(Meeting(
            days=tuple(days),
            start=start,
            end=end,
            start_minutes=start_minutes,
            end_minutes=end_minutes,
            room=tidy_room(raw_room),
            delivery=_delivery(raw_room),
            first_date=active_from,
            last_date=active_to,
        ))
    return tuple(meetings)


def section_from_row(row):
    """Turn one raw Banner row into a Section."""
    component = row.get("SCHD_TYPE") or ""
    return Section(
        term=row.get("TERM_CODE"),
        crn=row.get("CRN"),
        subject=row.get("SUBJ_CODE"),
        number=row.get("CRSE_NUMB"),
        title=(row.get("CRSE_TITLE") or "").strip(),
        component=COMPONENTS.get(component, component),
        section=row.get("SEQ_NUMB"),
        credit_hours=row.get("CREDIT_HRS") or 0,
        link=row.get("LINK_CONN"),
        capacity=_to_int(row.get("MAX_ENRL")),
        enrolled=_to_int(row.get("ENRL")),
        seats_available=_to_int(row.get("SEATS")),
        meetings=_meetings_from(row),
    )


# ---------------------------------------------------------------------------
# The timetable itself
# ---------------------------------------------------------------------------

class DalTimetable:
    """
    Read-only access to Dalhousie's published timetable.

        timetable = DalTimetable()
        timetable.available_terms()
        timetable.sections(terms=["202720"], subjects=["CSCI"])

    Results are cached per (term, subject) for the life of the object, so
    asking twice costs one request.
    """

    def __init__(self, campuses=None, workers=6):
        self.campuses = list(campuses) if campuses else list(ALL_CAMPUSES)
        self.workers = workers
        self._sections_cache = {}
        self._subjects_cache = {}

    # -- endpoints ----------------------------------------------------------

    def _request(self, domain, params, attempts=3):
        import time as _time
        url = BASE_URL + domain + "?" + urllib.parse.urlencode(params)
        request = urllib.request.Request(url, headers={
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        })
        last_error = None
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    return json.loads(response.read().decode("utf-8"))
            except (urllib.error.URLError, ValueError, OSError) as error:
                last_error = error
                _time.sleep(1.5 * (attempt + 1))
        raise TimetableError(
            "could not reach the Dalhousie timetable (%s): %s" % (domain, last_error))

    def available_terms(self, in_progress=False):
        """
        [('202710', '2026/2027 Fall'), ...] -- oldest first.

        in_progress=True switches to the timetable still being built.
        """
        rows = self._request("dal_stuweb_academicTimetable_terms", {
            "in_progress": "Y" if in_progress else "N",
            "max": 100, "offset": 0,
        })
        terms = []
        for row in rows:
            terms.append((row["CODE"], _clean_term_name(row["DESCR"])))
        return terms

    def subjects(self, terms):
        """[('CSCI', 'Computer Science'), ...] for the given term(s)."""
        key = tuple(sorted(_as_list(terms)))
        if key in self._subjects_cache:
            return self._subjects_cache[key]
        rows = self._request("dal_stuweb_academicTimetable_subjects", {
            "terms": _semicolons(terms),
            "districts": _semicolons(self.campuses),
            "max": 999, "offset": 0,
        })
        found = []
        for row in rows:
            found.append((row["CODE"], _clean_subject_name(row["DESCR"])))
        self._subjects_cache[key] = found
        return found

    def subject_codes(self, terms):
        codes = []
        for code, _ in self.subjects(terms):
            codes.append(code)
        return codes

    # -- sections -----------------------------------------------------------

    def sections(self, terms, subjects=None, course=None):
        """
        Every section matching the query, as a SectionSet.

        terms and subjects each take a string or a list. Leave subjects out to
        pull every subject offered in those terms -- that is 156 requests and
        a few thousand sections, so name your subjects when you can.
        """
        term_list = _as_list(terms)
        if not term_list:
            raise TimetableError("at least one term is required")

        if subjects is None:
            subject_list = self.subject_codes(term_list)
        else:
            subject_list = []
            for entry in _as_list(subjects):
                subject_list.append(str(entry).strip().upper())
            self._check_subjects(subject_list, term_list)

        jobs = []
        for term in term_list:
            for subject in subject_list:
                if (term, subject) not in self._sections_cache:
                    jobs.append((term, subject))

        if jobs:
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                for (term, subject), rows in zip(jobs, pool.map(self._fetch, jobs)):
                    self._sections_cache[(term, subject)] = rows

        found = SectionSet()
        wanted_number = None
        if course is not None:
            _, wanted_number = split_course(course)
        for term in term_list:
            for subject in subject_list:
                for section in self._sections_cache[(term, subject)]:
                    if wanted_number is not None and section.number != wanted_number:
                        continue
                    found.append(section)
        return found

    def _fetch(self, job):
        """One request covers one subject in one term; Banner rejects more."""
        term, subject = job
        rows = self._request("dal_stuweb_academicTimetable", {
            "terms": _semicolons([term]),
            "subj_code": subject,
            "districts": _semicolons(self.campuses),
            "crse_numb": "",
            "page_num": 1,
            "page_size": 9999,
        })
        sections = []
        for row in rows:
            sections.append(section_from_row(row))
        return sections

    def check_subjects(self, subjects, terms):
        """Raise UnknownSubject if any of these codes is not a Dal subject."""
        codes = []
        for entry in _as_list(subjects):
            codes.append(str(entry).strip().upper())
        self._check_subjects(codes, _as_list(terms))

    def _check_subjects(self, subject_list, terms):
        known = self.subject_codes(terms)
        for subject in subject_list:
            if subject in known:
                continue
            raise UnknownSubject(
                "'%s' is not a valid subject code. "
                "Run browser.py --subjects for the list." % subject)

    def section(self, term, course, section):
        """
        One specific section: timetable.section("202710", "CSCI 1109", "B01")

        Section codes are Banner's: 01 and 02 are lectures, B01 is a lab, T01
        is a tutorial, and the numbering has gaps. Use this to pin down a lab
        you TA or any other fixed commitment that is really a Dal section.
        """
        course_name = normalize_course(course)
        subject, _ = split_course(course)
        wanted = str(section).strip().upper()
        candidates = self.sections([term], [subject], course=course_name)
        if not candidates:
            raise NotFound("%s is not offered in term %s" % (course_name, term))
        for item in candidates:
            if (item.section or "").upper() == wanted:
                return item
        available = []
        for item in candidates:
            available.append(item.section)
        raise NotFound("%s has no section '%s' in term %s -- it has %s"
                       % (course_name, section, term, ", ".join(available)))

    def offered(self, courses, terms):
        """
        Which of these courses run, and when.

        {'CSCI 3151': ['202710'], 'CSCI 2115': ['202710', '202720']}

        An empty list means the course is not offered in any of those terms.
        Point it at your degree checklist when the timetable comes out.
        """
        term_list = _as_list(terms)
        wanted = []
        subjects = []
        for entry in courses:
            name = normalize_course(entry)
            subject, _ = split_course(name)
            wanted.append(name)
            if subject not in subjects:
                subjects.append(subject)

        sections = self.sections(term_list, subjects)
        seen = {}
        for section in sections:
            seen.setdefault(section.course, set()).add(section.term)

        result = {}
        for name in wanted:
            found = sorted(seen.get(name, set()))
            result[name] = found
        return result

    def titles(self, courses, terms):
        """{'CSCI 2134': 'Software Development'} for whatever is offered."""
        term_list = _as_list(terms)
        subjects = []
        wanted = []
        for entry in courses:
            name = normalize_course(entry)
            subject, _ = split_course(name)
            wanted.append(name)
            if subject not in subjects:
                subjects.append(subject)
        found = {}
        for section in self.sections(term_list, subjects):
            if section.course in wanted and section.course not in found:
                found[section.course] = section.title
        return found


# ---------------------------------------------------------------------------

def _as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _semicolons(values):
    """Banner wants semicolon-terminated lists: ['202710'] -> '202710;'."""
    text = ""
    for value in _as_list(values):
        text += str(value) + ";"
    return text


def _clean_term_name(text):
    """'(202710) 2026/2027 Fall' -> '2026/2027 Fall'."""
    cleaned = (text or "").strip()
    if cleaned.startswith("(") and ")" in cleaned:
        cleaned = cleaned.split(")", 1)[1].strip()
    return cleaned


def _clean_subject_name(text):
    """'(CSCI) Computer Science' -> 'Computer Science'."""
    return _clean_term_name(text)
