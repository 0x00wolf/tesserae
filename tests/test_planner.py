"""Checks for daltimetable.planner, run against real sections with the network faked."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fixture
from daltimetable import (
    Commitment, Elective, PlannerError, SchedulePlanner, UnknownSubject,
    meetings_overlap,
)

failures = []


def check(label, actual, expected):
    if actual != expected:
        failures.append("%s\n   expected: %r\n   actual:   %r"
                        % (label, expected, actual))


def check_true(label, condition):
    if not condition:
        failures.append(label)


def check_raises(label, exception, call):
    try:
        call()
    except exception:
        return
    except Exception as error:                                  # noqa: BLE001
        failures.append("%s raised %r, wanted %s"
                        % (label, error, exception.__name__))
        return
    failures.append("%s did not raise %s" % (label, exception.__name__))


def assert_sane(schedules, courses, terms, low, high, note=""):
    """Every schedule must place every course once, in range, with no clash."""
    for schedule in schedules:
        placed = []
        for term in terms:
            choices = schedule.terms[term]
            check_true("%s: term %s holds %d courses, wanted %d-%d"
                       % (note, term, len(choices), low, high),
                       low <= len(choices) <= high)
            for choice in choices:
                placed.append(choice.course)

            sections = []
            for choice in choices:
                for section in choice.sections:
                    sections.append((choice.course, section))
            for busy in schedule.commitments:
                if busy.term is None or busy.term == term:
                    for meeting in busy.meetings:
                        sections.append((busy.label, _fake(meeting)))

            for index in range(len(sections)):
                for other in range(index + 1, len(sections)):
                    name_a, first = sections[index]
                    name_b, second = sections[other]
                    for meeting_a in first.meetings:
                        for meeting_b in second.meetings:
                            if meetings_overlap(meeting_a, meeting_b):
                                failures.append(
                                    "%s: clash in %s between %s and %s"
                                    % (note, term, name_a, name_b))
        check("%s: every course placed once" % note,
              sorted(placed), sorted(courses))


class _fake:
    """Wrap a bare meeting so the clash walk can treat it like a section."""

    def __init__(self, meeting):
        self.meetings = (meeting,)


TERMS = ["202710", "202720"]
timetable = fixture.timetable()


def planner(**kwargs):
    settings = dict(timetable=timetable, terms=TERMS,
                    min_per_term=1, max_per_term=2)
    settings.update(kwargs)
    return SchedulePlanner(**settings)


# --- bundles ----------------------------------------------------------------

base = planner(courses=["CSCI 2134"])
check("CSCI 2134 Fall: 2 lectures x 2 labs",
      len(base._bundles("202710", "CSCI 2134")), 4)
check("each bundle is a lecture plus a lab",
      sorted(s.component for s in base._bundles("202710", "CSCI 2134")[0]),
      ["Lab", "Lecture"])
check("CSCI 2134 Winter: 1 lecture x 2 labs",
      len(base._bundles("202720", "CSCI 2134")), 2)

solo = planner(courses=["CSCI 1315"])
check("CSCI 1315 has no lab to attach",
      len(solo._bundles("202710", "CSCI 1315")), 1)
check("and its bundle is one section",
      len(solo._bundles("202710", "CSCI 1315")[0]), 1)

maths = planner(courses=["MATH 2060"])
check("MATH 2060 Fall: 1 lecture x 4 tutorials",
      len(maths._bundles("202710", "MATH 2060")), 4)
check("lecture pairs with tutorial",
      sorted(s.component for s in maths._bundles("202710", "MATH 2060")[0]),
      ["Lecture", "Tutorial"])

theory = planner(courses=["CSCI 2115"])
check("CSCI 2115 Fall has no tutorial",
      len(theory._bundles("202710", "CSCI 2115")[0]), 1)
check("CSCI 2115 Winter attaches its tutorial",
      len(theory._bundles("202720", "CSCI 2115")[0]), 2)

check("CSCI 3151 is Fall only",
      (len(base._bundles("202710", "CSCI 3151")) > 0,
       len(base._bundles("202720", "CSCI 3151"))),
      (True, 0))

# --- the search -------------------------------------------------------------

courses = ["CSCI 2134", "CSCI 1315", "MATH 2060", "CSCI 2141"]
schedules = planner(courses=courses, min_per_term=2, max_per_term=2).schedules(limit=500)
check_true("found schedules", len(schedules) > 0)
assert_sane(schedules, courses, TERMS, 2, 2, "basic")

check("variations are numbered from 1",
      [s.variation for s in schedules[:3]], [1, 2, 3])

# --- lowercase and unspaced course names ------------------------------------

loose = planner(courses=["csci2134", "csci 1315", "MATH2060", "CSCI-2141"],
                min_per_term=2, max_per_term=2).schedules(limit=500)
check("any spelling finds the same schedules", len(loose), len(schedules))

# --- rows -------------------------------------------------------------------

rows = schedules[0].rows()
check_true("rows are 6-tuples", all(len(row) == 6 for row in rows))
for term, course, component, days, clock, room in rows:
    check_true("row term looks like a term code", term in TERMS)
    check_true("row course looks like a course", " " in course)
    check_true("row days is a list", isinstance(days, list))

# --- commitments ------------------------------------------------------------

work = Commitment("Work", "TR", "13:00", "17:00")
with_work = planner(courses=["CSCI 2134", "CSCI 1315"],
                    commitments=[work]).schedules(limit=500)
check_true("still solvable around work", len(with_work) > 0)
assert_sane(with_work, ["CSCI 2134", "CSCI 1315"], TERMS, 1, 2, "work")
for schedule in with_work:
    for choice in schedule.terms["202710"]:
        if choice.course == "CSCI 2134":
            check("Fall CSCI 2134 avoids the TR afternoon lecture",
                  choice.sections[0].section, "01")

ta_lab = timetable.section("202710", "CSCI 1109", "B01")
with_ta = planner(courses=["CSCI 2134", "CSCI 1315"],
                  commitments=[ta_lab]).schedules(limit=200)
check_true("solvable around a TA lab", len(with_ta) > 0)
assert_sane(with_ta, ["CSCI 2134", "CSCI 1315"], TERMS, 1, 2, "ta")
check("the TA lab rides along on the schedule",
      with_ta[0].commitments[0].label, "CSCI 1109")

check_raises("a commitment must be a Section or Commitment", PlannerError,
             lambda: planner(courses=["CSCI 1315"], commitments=["CSCI 1109 B01"]))
check_raises("a backwards commitment", PlannerError,
             lambda: Commitment("Bad", "M", "17:00", "09:00"))

# --- electives --------------------------------------------------------------

named = planner(courses=["CSCI 2134", "CSCI 1315"],
                electives=[Elective(["CSCI 2115", "CSCI 2122"], pick=1)],
                min_per_term=1, max_per_term=2).schedules(limit=500)
check_true("named elective pool produces schedules", len(named) > 0)
for schedule in named:
    names = schedule.course_names()
    check("three courses in total", len(names), 3)
    chosen = [name for name in names if name in ("CSCI 2115", "CSCI 2122")]
    check("exactly one elective chosen", len(chosen), 1)

by_level = planner(courses=["CSCI 1315"],
                   electives=[Elective(subject="CSCI", level=3000, pick=1)],
                   min_per_term=1, max_per_term=1).schedules(limit=200)
check_true("subject+level elective resolves", len(by_level) > 0)
for schedule in by_level:
    check_true("the 3000-level pool is CSCI 3151",
               "CSCI 3151" in schedule.course_names())

pick_two = planner(courses=["CSCI 1315"],
                   electives=[Elective(["CSCI 2115", "CSCI 2122", "CSCI 2141"],
                                       pick=2)],
                   min_per_term=1, max_per_term=2).schedules(limit=500)
check_true("pick=2 works", len(pick_two) > 0)
for schedule in pick_two:
    check("three courses when picking two", len(schedule.course_names()), 3)

check_raises("an elective needs a pool", PlannerError, lambda: Elective())
check_raises("pick must be positive", PlannerError,
             lambda: Elective(["CSCI 2115"], pick=0))

# --- narrowing --------------------------------------------------------------

late = planner(courses=["CSCI 2134", "CSCI 1315"],
               earliest="10:00").schedules(limit=500)
for schedule in late:
    for term in TERMS:
        for choice in schedule.terms[term]:
            for section in choice.sections:
                for meeting in section.meetings:
                    if meeting.scheduled:
                        check_true("earliest='10:00' let an early class through",
                                   meeting.start_minutes >= 600)

seats = planner(courses=["CSCI 2141"], min_per_term=0, max_per_term=1,
                require_seats=True)
check("require_seats drops the full Fall sections",
      len(seats._bundles("202710", "CSCI 2141")), 0)
check_true("Winter CSCI 2141 still has seats",
           len(seats._bundles("202720", "CSCI 2141")) > 0)

# --- impossible requests ----------------------------------------------------

check("too many courses for the cap",
      planner(courses=courses, min_per_term=1, max_per_term=1).schedules(), [])
check("min too large",
      planner(courses=["CSCI 1315"], min_per_term=3, max_per_term=4).schedules(), [])
check("a course nobody offers",
      planner(courses=["CSCI 1315", "CSCI 9999"]).schedules(), [])
check_raises("min above max", PlannerError,
             lambda: planner(courses=["CSCI 1315"], min_per_term=3, max_per_term=2))
check_raises("no terms", PlannerError,
             lambda: SchedulePlanner(timetable, ["CSCI 1315"], [], 1, 2))
check_raises("an unknown subject still raises through the planner",
             UnknownSubject,
             lambda: planner(courses=["CSC 1315"]).schedules())

# --- describe ---------------------------------------------------------------

text = schedules[0].describe({"202710": "Fall 2026", "202720": "Winter 2027"})
check_true("describe names the terms", "Fall 2026" in text and "Winter 2027" in text)
check_true("describe lists a course", "CSCI 2134" in text)

if failures:
    print("FAILED (%d)" % len(failures))
    for failure in failures:
        print(" -", failure)
    raise SystemExit(1)

print("planner:  all checks passed -- %d schedules in the main search"
      % len(schedules))
