#!/usr/bin/env python3
"""
plan.py -- edit the settings below, then run:  python3 plan.py

It finds every conflict-free way to fit your courses into your terms and
prints them. Set PDF near the bottom if you also want a printable timetable.

Don't know your term codes, or what's being offered?  Use browser.py:

    python3 browser.py --terms
    python3 browser.py --list CSCI 4000 --term 202720
"""

# Elective and Commitment are imported for the commented-out examples below.
from daltimetable import (                                      # noqa: F401
    Commitment, DalTimetable, Elective, SchedulePlanner,
)


# ══════════════════════════════════════════════════════════════════════
#  1. TERMS
#     Which terms you are planning. Get the codes from:
#         python3 browser.py --terms
# ══════════════════════════════════════════════════════════════════════

TERMS = ["202710", "202720"]

# What to call them on screen and on the PDF.
TERM_NAMES = {
    "202710": "Fall 2026",
    "202720": "Winter 2027",
}


# ══════════════════════════════════════════════════════════════════════
#  2. COURSES YOU MUST TAKE
#     Any spelling works: "CSCI 2134", "csci 2134", "CSCI2134", "csci2134".
# ══════════════════════════════════════════════════════════════════════

COURSES = [
    "CSCI 2134",
    "CSCI 2141",
    "MATH 2060",
    "CSCI 1315",
]


# ══════════════════════════════════════════════════════════════════════
#  3. COURSE LOAD
#     How many courses you are willing to carry in each term.
# ══════════════════════════════════════════════════════════════════════

MIN_PER_TERM = 2
MAX_PER_TERM = 2


# ══════════════════════════════════════════════════════════════════════
#  4. ELECTIVES  (optional)
#     Slots filled from a pool instead of a named course.
#     Uncomment one of the examples, or leave the list empty.
# ══════════════════════════════════════════════════════════════════════

ELECTIVES = []

# One of these two specific courses, whichever fits:
# ELECTIVES = [Elective(["PHYC 2451", "PHYC 2452"], pick=1)]

# Any 1000-level physics course:
# ELECTIVES = [Elective(subject="PHYC", level=1000, pick=1)]

# Two of these, in whatever combination works:
# ELECTIVES = [Elective(["HIST 1000", "PHIL 1000", "ENGL 1000"], pick=2)]


# ══════════════════════════════════════════════════════════════════════
#  5. HOURS THAT MUST STAY FREE  (optional)
#     A lab you TA is a real section, so name it by term, course and
#     section code and its times come from the timetable itself.
#     Section codes: 01/02 lectures, B01 labs, T01 tutorials.
#     Anything that isn't a Dal course uses Commitment(...) instead.
# ══════════════════════════════════════════════════════════════════════

TA_SECTIONS = []

# A lab you TA, in both terms:
# TA_SECTIONS = [
#     ("202710", "CSCI 1109", "B01"),
#     ("202720", "CSCI 1109", "B01"),
# ]

OTHER_COMMITMENTS = []

# A job, a commute, anything Dal doesn't know about:
# OTHER_COMMITMENTS = [
#     Commitment("Work", "MW", "17:00", "21:00"),
#     Commitment("Volunteering", ["Friday"], "13:00", "16:00", term="202720"),
# ]


# ══════════════════════════════════════════════════════════════════════
#  6. NARROW THE SEARCH  (optional)
#     Leave as None / False to consider everything.
# ══════════════════════════════════════════════════════════════════════

NO_CLASSES_BEFORE = None        # e.g. "10:00" to skip the 08:35s
NO_CLASSES_AFTER = None         # e.g. "17:00" to skip evening classes
ONLY_WITH_SEATS = False         # True to skip sections that were full


# ══════════════════════════════════════════════════════════════════════
#  7. OUTPUT
# ══════════════════════════════════════════════════════════════════════

MAX_VARIATIONS = 10             # how many options to find

SHOW = "list"                   # "list" for a summary, "grid" for a week view

PDF = None                      # terminal only
# PDF = "timetable.pdf"         # also write a printable PDF (needs reportlab)


# ══════════════════════════════════════════════════════════════════════
#  ─────────────────────  nothing to edit below  ─────────────────────
# ══════════════════════════════════════════════════════════════════════

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
             "Saturday", "Sunday"]


def build_planner(timetable):
    commitments = []
    for term, course, section in TA_SECTIONS:
        commitments.append(timetable.section(term, course, section))
    for entry in OTHER_COMMITMENTS:
        commitments.append(entry)

    return SchedulePlanner(
        timetable,
        courses=COURSES,
        terms=TERMS,
        min_per_term=MIN_PER_TERM,
        max_per_term=MAX_PER_TERM,
        electives=ELECTIVES,
        commitments=commitments,
        earliest=NO_CLASSES_BEFORE,
        latest=NO_CLASSES_AFTER,
        require_seats=ONLY_WITH_SEATS,
    )


def weekly_grid(schedule, term, slot_minutes=30, column_width=16):
    """A text week for one term, printed when SHOW = "grid"."""
    entries = []
    unscheduled = []

    def add(label, meetings):
        for meeting in meetings:
            if not meeting.scheduled:
                unscheduled.append("%s (%s)" % (label, meeting.delivery))
                continue
            for day in meeting.days:
                entries.append({
                    "day": DAY_ORDER.index(day),
                    "start": meeting.start_minutes,
                    "end": meeting.end_minutes,
                    "label": label,
                })

    for choice in schedule.terms.get(term, ()):
        for section in choice.sections:
            add("%s %s" % (choice.course, section.section), section.meetings)
    for busy in schedule.commitments:
        if busy.term is None or busy.term == term:
            add(busy.label, busy.meetings)

    if not entries:
        lines = ["  (nothing with a fixed meeting time)"]
    else:
        lines = _grid_lines(entries, slot_minutes, column_width)

    if unscheduled:
        lines.append("")
        lines.append("  No fixed time:")
        for item in sorted(set(unscheduled)):
            lines.append("    " + item)
    return "\n".join(lines)


def _grid_lines(entries, slot_minutes, column_width):
    days = []
    earliest = None
    latest = None
    for entry in entries:
        if entry["day"] not in days:
            days.append(entry["day"])
        if earliest is None or entry["start"] < earliest:
            earliest = entry["start"]
        if latest is None or entry["end"] > latest:
            latest = entry["end"]
    days.sort()
    earliest = earliest - (earliest % slot_minutes)

    header = "        "
    for day in days:
        header += DAY_ORDER[day][:3].ljust(column_width)
    lines = [header, "        " + "-" * (column_width * len(days))]

    slot = earliest
    while slot < latest:
        slot_end = slot + slot_minutes
        row = "  %02d:%02d " % (slot // 60, slot % 60)
        for day in days:
            cell = ""
            for entry in entries:
                if entry["day"] != day:
                    continue
                if entry["start"] < slot_end and slot < entry["end"]:
                    cell = entry["label"]
                    break
            row += cell.ljust(column_width)
        lines.append(row.rstrip())
        slot = slot_end
    return lines


def main():
    timetable = DalTimetable()
    planner = build_planner(timetable)

    print("Searching...")
    schedules = planner.schedules(limit=MAX_VARIATIONS)

    if not schedules:
        print()
        print("No schedule fits those settings.")
        explain(planner)
        return 1

    print("Found %d option%s.\n" % (len(schedules),
                                    "" if len(schedules) == 1 else "s"))

    for schedule in schedules:
        print("=" * 68)
        print("Variation %d" % schedule.variation)
        print("=" * 68)
        if SHOW == "grid":
            for term in sorted(schedule.terms):
                print()
                print(TERM_NAMES.get(term, "Term %s" % term))
                print(weekly_grid(schedule, term))
        else:
            print(schedule.describe(TERM_NAMES))
        print()

    if PDF:
        from daltimetable.pdf import TimetablePDF
        TimetablePDF(term_names=TERM_NAMES).render(schedules, PDF)
        print("Wrote %s" % PDF)

    return 0


def explain(planner):
    """When nothing fits, say which course is the problem."""
    print()
    for course in planner.courses:
        available = planner.offerings(course)
        where = []
        for term in sorted(available):
            if available[term]:
                where.append("%s (%d option%s)" % (
                    TERM_NAMES.get(term, term), len(available[term]),
                    "" if len(available[term]) == 1 else "s"))
        if where:
            print("  %-11s %s" % (course, ", ".join(where)))
        else:
            print("  %-11s not offered in your terms, or filtered out by "
                  "section 6" % course)
    print()
    print("Try widening MIN_PER_TERM / MAX_PER_TERM, adding a term, or "
          "relaxing section 6.")


if __name__ == "__main__":
    raise SystemExit(main())
