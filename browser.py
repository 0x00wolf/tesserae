#!/usr/bin/env python3
"""
browser.py -- look up what Dalhousie is offering.

    python3 browser.py --terms
    python3 browser.py --subjects --term 202720
    python3 browser.py --list CSCI --term 202720
    python3 browser.py --list CSCI 4000 --term 202720
    python3 browser.py --list CSCI 2134 --term 202710 --sections
    python3 browser.py --check CSCI 4192 CSCI 3130 CSCI 2115
    python3 browser.py --check checklist.txt
    python3 browser.py --check CSCI 3151 --sections

This file only reads the timetable. To actually build a schedule, edit plan.py.
"""

import argparse
import os
import sys

from daltimetable import (
    DalTimetable, TimetableError, normalize_course, split_course,
)


def term_label(description):
    """
    '2026/2027 Fall' -> '26/27 Fall'.

    The academic year has to stay in the label. Dalhousie keeps several terms
    viewable at once, and right now that includes both 2025/2026 Winter and
    2026/2027 Winter -- a bare 'Winter' would let you plan around a term that
    has already happened.
    """
    parts = (description or "").strip().split()
    if len(parts) >= 2 and "/" in parts[0]:
        years = parts[0].split("/")
        if len(years) == 2 and len(years[0]) == 4 and len(years[1]) == 4:
            return "%s/%s %s" % (years[0][2:], years[1][2:], " ".join(parts[1:]))
    return description


def resolve_terms(timetable, requested):
    """
    The term codes to work with, and a code -> short name map.

    With no --term, every currently available term is used.
    """
    available = timetable.available_terms()
    names = {}
    for code, description in available:
        names[code] = term_label(description)

    if not requested:
        codes = []
        for code, _ in available:
            codes.append(code)
        return codes, names

    codes = []
    for entry in requested:
        code = str(entry).strip()
        if code not in names:
            known = []
            for other, description in available:
                known.append("%s (%s)" % (other, description))
            raise SystemExit(
                "no term '%s' is currently available.\nAvailable: %s"
                % (code, ", ".join(known)))
        codes.append(code)
    return codes, names


def print_terms(timetable):
    for code, description in timetable.available_terms():
        print("%s  %s" % (code, description))


def print_subjects(timetable, terms):
    for code, description in timetable.subjects(terms):
        print("%s  %s" % (code, description))


def print_courses(timetable, subject, level, terms, names, single_term):
    """
    One course per line, ready to paste into plan.py.

    With a single term the line is just the code and the title. With several,
    a column says which terms each course runs in.
    """
    sections = timetable.sections(terms, [subject])
    if level is not None:
        sections = sections.level(level)

    rows = sections.courses()
    if not rows:
        where = ", ".join(names.get(term, term) for term in terms)
        print("nothing offered for %s%s in %s"
              % (subject, "" if level is None else " at the %d level" % level, where))
        return

    if single_term:
        width = 0
        for course, _title in rows:
            width = max(width, len(course))
        for course, title in rows:
            print("%-*s  %s" % (width, course, title))
        return

    when = {}
    for section in sections:
        when.setdefault(section.course, set()).add(section.term)

    code_width = 0
    title_width = 0
    for course, title in rows:
        code_width = max(code_width, len(course))
        title_width = max(title_width, len(title))
    for course, title in rows:
        terms_here = sorted(when.get(course, set()))
        labels = []
        for term in terms_here:
            labels.append("[%s]" % names.get(term, term))
        print("%-*s  %-*s  %s" % (code_width, course, title_width, title,
                                  " ".join(labels)))


def component_order(section):
    """Lectures first, then labs and tutorials, then everything else."""
    order = {"Lecture": 0, "Lab": 1, "Tutorial": 2}
    return (order.get(section.component, 3), section.section or "")


def print_sections(timetable, subject, level, number, terms, names):
    """
    Every section, with its meeting times, grouped under its course.

    The term is always bracketed on the heading, even when you asked for one
    term -- it is the clearest demarcation between blocks, and it means no
    line of output is ever ambiguous about which term it describes.

    A section that meets on more than one pattern gets a line per pattern;
    one with no fixed time says so.
    """
    course = None
    if number is not None:
        course = "%s %s" % (subject, number)

    sections = timetable.sections(terms, [subject], course=course)
    if level is not None:
        sections = sections.level(level)

    if not sections:
        where = ", ".join(names.get(term, term) for term in terms)
        print("nothing offered for %s in %s" % (course or subject, where))
        return

    grouped = {}
    for section in sections:
        grouped.setdefault((section.term, section.course), []).append(section)

    first = True
    for term, course_code in sorted(grouped):
        if not first:
            print()
        first = False

        print("%s  %s  [%s]" % (course_code,
                                grouped[(term, course_code)][0].title,
                                names.get(term, term)))

        for section in sorted(grouped[(term, course_code)], key=component_order):
            label = "  %-9s %-4s" % (section.component, section.section)
            if not section.meetings:
                print("%s  (no meeting times listed)" % label)
                continue
            for meeting in section.meetings:
                if meeting.scheduled:
                    print("%s  %-6s %s  %s" % (label, meeting.letters(),
                                               meeting.clock(), meeting.room))
                else:
                    # room and delivery say the same thing here, so print one.
                    print("%s  %-6s %s" % (label, "--", meeting.delivery))
                label = "  %-9s %-4s" % ("", "")


def join_split_courses(entries):
    """
    Put 'CSCI 3152' back together after the shell has split it.

        browser.py --check CSCI 3152 CSCI 3151

    reaches argparse as four separate arguments. A four-letter subject code
    followed by a bare number is one course, not two, so quoting should not
    be required. Dalhousie subject codes are all exactly four letters, which
    is what makes this unambiguous.
    """
    joined = []
    index = 0
    while index < len(entries):
        token = str(entries[index]).strip()
        following = ""
        if index + 1 < len(entries):
            following = str(entries[index + 1]).strip()
        if len(token) == 4 and token.isalpha() and following.isdigit():
            joined.append("%s %s" % (token, following))
            index += 2
            continue
        joined.append(token)
        index += 1
    return joined


def read_checklist(entries):
    """Course names, either given directly or read from a file, one per line."""
    courses = []
    for entry in entries:
        if os.path.exists(entry):
            with open(entry, "r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.split("#", 1)[0].strip()
                    if line:
                        courses.append(line)
        else:
            courses.append(entry)
    return courses


def print_check(timetable, entries, terms, names, show_sections=False):
    """Which of these courses run, and when. Empty means not this year."""
    courses = join_split_courses(read_checklist(entries))
    if not courses:
        raise SystemExit("nothing to check")

    tidy = []
    for course in courses:
        tidy.append(normalize_course(course))

    offered = timetable.offered(tidy, terms)
    titles = timetable.titles(tidy, terms)

    if show_sections:
        # The section blocks carry the course, title and term already, so
        # printing the summary table as well would say everything twice.
        first = True
        for course in tidy:
            if not first:
                print()
            first = False
            if offered.get(course):
                subject, number = split_course(course)
                print_sections(timetable, subject, None, number, terms, names)
            else:
                print("%s  not offered" % course)
        return

    code_width = 0
    title_width = 1
    for course in tidy:
        code_width = max(code_width, len(course))
        title_width = max(title_width, len(titles.get(course, "—")))

    for course in tidy:
        where = offered.get(course, [])
        if where:
            labels = []
            for term in where:
                labels.append("[%s]" % names.get(term, term))
            status = " ".join(labels)
        else:
            # Left unbracketed on purpose, so it does not read as a term.
            status = "not offered"
        print("%-*s  %-*s  %s" % (code_width, course,
                                  title_width, titles.get(course, "—"), status))


def build_parser():
    parser = argparse.ArgumentParser(
        description="Look up what Dalhousie is offering.",
        epilog="To build a schedule, edit plan.py and run it.")
    parser.add_argument("--terms", action="store_true",
                        help="list the term codes currently available")
    parser.add_argument("--subjects", action="store_true",
                        help="list subject codes offered in the given term(s)")
    parser.add_argument("--list", nargs="+", metavar=("SUBJECT", "LEVEL"),
                        help="courses offered, e.g. --list CSCI, "
                             "--list CSCI 4000 (a level), or "
                             "--list CSCI 2134 (one course)")
    parser.add_argument("--sections", action="store_true",
                        help="show every section and its meeting times; "
                             "works with --list and --check")
    parser.add_argument("--check", nargs="+", metavar="COURSE",
                        help="which of these courses are offered; quoting is "
                             "optional, so CSCI 3151 CSCI 2115 works. "
                             "Also accepts a file with one course per line")
    parser.add_argument("--term", action="append", default=[], metavar="CODE",
                        help="restrict to this term; repeatable. "
                             "Omit to cover every available term.")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not (args.terms or args.subjects or args.list or args.check):
        build_parser().print_help()
        return 2

    timetable = DalTimetable()

    try:
        if args.terms:
            print_terms(timetable)
            return 0

        terms, names = resolve_terms(timetable, args.term)
        single_term = len(terms) == 1

        if args.subjects:
            print_subjects(timetable, terms)
            return 0

        if args.list:
            subject = args.list[0].strip().upper()
            level = None
            number = None
            if len(args.list) > 1:
                given = args.list[1].strip()
                if not given.isdigit():
                    raise SystemExit(
                        "'%s' is not a level or a course number -- try "
                        "4000 or 2134" % given)
                # A round number is a level; anything else is one course.
                if given.endswith("000"):
                    level = int(given)
                else:
                    number = given
            if args.sections:
                print_sections(timetable, subject, level, number,
                               terms, names)
            elif number is not None:
                print_sections(timetable, subject, level, number,
                               terms, names)
            else:
                print_courses(timetable, subject, level, terms, names, single_term)
            return 0

        if args.check:
            print_check(timetable, args.check, terms, names, args.sections)
            return 0

    except TimetableError as error:
        print("error: %s" % error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
