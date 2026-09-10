

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

"""Checks for daltimetable.timetable, run against real sections with the network faked."""

from datetime import date

import fixture
from daltimetable import (
    TimetableError, UnknownSubject, NotFound,
    normalize_course, split_course, tidy_room,
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


timetable = fixture.timetable()

# --- course names -----------------------------------------------------------

for spelling in ["csci2134", "CSCI 2134", "csci 2134", "CSCI2134",
                 "CSCI-2134", "  csci  2134  ", "csci_2134"]:
    check("normalize %r" % spelling, normalize_course(spelling), "CSCI 2134")

check("split keeps long numbers", split_course("CSCI 2134X"), ("CSCI", "2134X"))
check_raises("empty course name", TimetableError, lambda: normalize_course("CSCI"))
check_raises("not a string", TimetableError, lambda: normalize_course(2134))

# --- terms and subjects -----------------------------------------------------

terms = timetable.available_terms()
check("term count", len(terms), 5)
check("term codes come back clean", terms[3], ("202710", "2026/2027 Fall"))
check("subject names come back clean",
      timetable.subjects(["202710"])[4], ("CSCI", "Computer Science"))

# --- fetching ---------------------------------------------------------------

csci_fall = timetable.sections("202710", "CSCI")
check("CSCI sections in Fall", len(csci_fall), 13)

both = timetable.sections(["202710", "202720"], ["CSCI"])
check("both terms", len(both), 26)
check("terms present", both.terms(), ["202710", "202720"])

one_course = timetable.sections("202710", "CSCI", course="csci 2134")
check("course= narrows to one course", len(one_course), 4)

check_raises("unknown subject raises", UnknownSubject,
             lambda: timetable.sections("202710", "CSC"))
try:
    timetable.sections("202710", "CSC")
except UnknownSubject as error:
    check_true("the error names the bad code", "'CSC'" in str(error))
    check_true("the error says what to run", "browser.py --subjects" in str(error))
    check_true("the error offers no guesses", "did you mean" not in str(error).lower())

check_raises("no terms raises", TimetableError,
             lambda: timetable.sections([], ["CSCI"]))

# --- one section ------------------------------------------------------------

lab = timetable.section("202710", "csci 1109", "b01")
check("section lookup finds the lab", lab.crn, "10701")
check("section component", lab.component, "Lab")
check("section course", lab.course, "CSCI 1109")
check("section level", lab.level, 1000)
check("section day", lab.meetings[0].days, ("Tuesday",))
check("section time", lab.meetings[0].clock(), "11:35-12:55")
check("section room is tidied", lab.meetings[0].room, "Goldberg 134")
check("section dates", (lab.meetings[0].first_date, lab.meetings[0].last_date),
      (date(2026, 9, 8), date(2026, 12, 9)))

check_raises("missing section names the real ones", NotFound,
             lambda: timetable.section("202710", "CSCI 1109", "B09"))
check_raises("course not offered", NotFound,
             lambda: timetable.section("202710", "CSCI 9999", "01"))

# --- meetings ---------------------------------------------------------------

aqua = timetable.sections("202710", "AQUA")[0]
check("two meeting patterns", len(aqua.meetings), 2)
check("pattern 1", (aqua.meetings[0].days, aqua.meetings[0].clock()),
      (("Tuesday",), "11:35-12:25"))
check("pattern 2", (aqua.meetings[1].days, aqua.meetings[1].clock()),
      (("Wednesday", "Friday"), "10:35-11:25"))
check("days() merges patterns", aqua.days(),
      ("Tuesday", "Wednesday", "Friday"))

arch = timetable.sections("202710", "ARCH")[0]
check("four meeting patterns", len(arch.meetings), 4)
check("last pattern is Thursday", arch.meetings[3].days, ("Thursday",))

nurs = timetable.sections("202710", "NURS")[0]
check("date headers are not meetings", len(nurs.meetings), 1)
check("no header text leaks into the room",
      "***" in nurs.meetings[0].room, False)
check("header narrows the date window",
      (nurs.meetings[0].first_date, nurs.meetings[0].last_date),
      (date(2026, 9, 8), date(2026, 9, 8)))

acsc = timetable.sections("202710", "ACSC")[0]
check("no fixed time", acsc.meetings[0].scheduled, False)
check("clock() falls back to the delivery mode",
      acsc.meetings[0].clock(), "Consult Department")
check("section knows it is unscheduled", acsc.scheduled, False)

# --- filters ----------------------------------------------------------------

check("level 1000", len(csci_fall.level(1000)), 3)
check("level 3000 is one course", csci_fall.level(3000).courses(),
      [("CSCI 3151", "Foundations  of Machine Learn.")])
check("level 9000 is empty", len(csci_fall.level(9000)), 0)

check("component filter", len(csci_fall.component("Lab")), 5)
check("component accepts Banner's abbreviation",
      len(csci_fall.component("Lec")), 8)

mw_only = csci_fall.on_days("MW")
for section in mw_only:
    for meeting in section.meetings:
        for day in meeting.days:
            check_true("on_days('MW') kept a %s meeting" % day,
                       day in ("Monday", "Wednesday"))
check("on_days finds the two MW lectures and two Monday labs",
      len(mw_only), 4)
check_raises("bad day letter", TimetableError, lambda: csci_fall.on_days("MX"))

daytime = csci_fall.between("10:00", "16:00")
for section in daytime:
    for meeting in section.meetings:
        if meeting.scheduled:
            check_true("between() kept something outside the window",
                       meeting.start_minutes >= 600 and meeting.end_minutes <= 960)
check_true("between() drops the 08:35s", len(daytime) < len(csci_fall))
check_raises("bad time", TimetableError, lambda: csci_fall.between("10", "16"))

seated = csci_fall.with_seats()
for section in seated:
    check_true("with_seats kept a full section", section.seats_available > 0)
check("with_seats drops the three full sections",
      len(csci_fall) - len(seated), 3)

check("courses() collapses sections",
      csci_fall.courses(),
      [("CSCI 1109", "Practical Data Science"),
       ("CSCI 1315", "Discrete Math for CS"),
       ("CSCI 2115", "Theory of Computer Science"),
       ("CSCI 2122", "Systems Programming"),
       ("CSCI 2134", "Software Development"),
       ("CSCI 2141", "Intro to Database Systems"),
       ("CSCI 3151", "Foundations  of Machine Learn.")])

check("filters chain",
      csci_fall.level(2000).component("Lecture").on_days("TR").courses(),
      [("CSCI 2115", "Theory of Computer Science"),
       ("CSCI 2134", "Software Development"),
       ("CSCI 2141", "Intro to Database Systems")])

check_true("a filter returns something still list-like",
           isinstance(csci_fall.level(1000), list))

# --- offered ----------------------------------------------------------------

check("offered across terms",
      timetable.offered(["csci 3151", "CSCI2115", "CSCI 9999"],
                        ["202710", "202720"]),
      {"CSCI 3151": ["202710"],
       "CSCI 2115": ["202710", "202720"],
       "CSCI 9999": []})

check("titles", timetable.titles(["CSCI 2134"], ["202710"]),
      {"CSCI 2134": "Software Development"})

# --- room tidying -----------------------------------------------------------

check("goldberg", tidy_room("Studley GOLDBERG COMPUTER SCIENCE BLDG 134"),
      "Goldberg 134")
check("dunn", tidy_room("Studley SIR JAMES DUNN BUILDING 101"), "Dunn 101")
check("lsc", tidy_room("Studley LSC-COMMON AREA C242"), "LSC C242")
check("consult", tidy_room("Consult Department"), "room TBA")
check("online", tidy_room("Online-ASYNCHRONOUS SESSION"), "Asynchronous Session")
check("unknown passes through", tidy_room("Agricultural HALEY INSTITUTE 114"),
      "HALEY INSTITUTE 114")
check("nothing", tidy_room(None), "room TBA")

# --- caching ----------------------------------------------------------------

calls = []
original = fixture.fake_request


def counting_request(self, domain, params, attempts=3):
    calls.append(domain)
    return original(self, domain, params, attempts)


type(timetable)._request = counting_request
timetable.sections("202710", "CSCI")
first = len(calls)
timetable.sections("202710", "CSCI")
check("a repeat query costs no requests", len(calls), first)
type(timetable)._request = original

if failures:
    print("FAILED (%d)" % len(failures))
    for failure in failures:
        print(" -", failure)
    raise SystemExit(1)

print("timetable: all checks passed")
