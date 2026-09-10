#!/usr/bin/env python3
"""
browser.py -- look up what Dalhousie is offering.

    python3 browser.py --terms
    python3 browser.py --subjects --term 202720
    python3 browser.py --list CSCI --term 202720
    python3 browser.py --list CSCI 4000 --term 202720
    python3 browser.py --check CSCI 4192 CSCI 3130 CSCI 2115
    python3 browser.py --check checklist.txt

This file only reads the timetable. To actually build a schedule, edit plan.py.
"""

import argparse
import os
import sys

from daltimetable import DalTimetable, TimetableError, normalize_course


def short_term_name(description):
    """'2026/2027 Fall' -> 'Fall'."""
    parts = (description or "").split()
    if parts:
        return parts[-1]
    return description


def resolve_terms(timetable, requested):
    """
    The term codes to work with, and a code -> short name map.

    With no --term, every currently available term is used.
    """
    available = timetable.available_terms()
    names = {}
    for code, description in available:
        names[code] = short_term_name(description)

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
            labels.append(names.get(term, term))
        print("%-*s  %-*s  %s" % (code_width, course, title_width, title,
                                  ", ".join(labels)))


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


def print_check(timetable, entries, terms, names):
    """Which of these courses run, and when. Empty means not this year."""
    courses = read_checklist(entries)
    if not courses:
        raise SystemExit("nothing to check")

    tidy = []
    for course in courses:
        tidy.append(normalize_course(course))

    offered = timetable.offered(tidy, terms)
    titles = timetable.titles(tidy, terms)

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
                labels.append(names.get(term, term))
            status = ", ".join(labels)
        else:
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
                        help="courses offered, e.g. --list CSCI 4000")
    parser.add_argument("--check", nargs="+", metavar="COURSE",
                        help="which of these courses are offered; "
                             "accepts a file with one course per line")
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
            if len(args.list) > 1:
                try:
                    level = int(args.list[1])
                except ValueError:
                    raise SystemExit(
                        "'%s' is not a level -- use 1000, 2000, 3000 or 4000"
                        % args.list[1])
            print_courses(timetable, subject, level, terms, names, single_term)
            return 0

        if args.check:
            print_check(timetable, args.check, terms, names)
            return 0

    except TimetableError as error:
        print("error: %s" % error, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
