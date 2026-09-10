"""
Checks that browser.py and plan.py actually run, against the fixture.

These are the two files a student touches, so a syntax slip or a bad format
string in either is the most visible possible bug.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import contextlib
import io
import os
import tempfile

import fixture

fixture.timetable()          # patches DalTimetable._request for everything below

import browser               # noqa: E402
import plan                  # noqa: E402

failures = []


def check_true(label, condition):
    if not condition:
        failures.append(label)


def run(function, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = function(*args)
    return code, out.getvalue()


# --- browser.py -------------------------------------------------------------

code, text = run(browser.main, ["--terms"])
check_true("--terms exits cleanly", code == 0)
check_true("--terms lists Fall", "202710  2026/2027 Fall" in text)

code, text = run(browser.main, ["--subjects", "--term", "202710"])
check_true("--subjects lists CSCI", "CSCI  Computer Science" in text)

code, text = run(browser.main, ["--list", "CSCI", "--term", "202710"])
check_true("--list is one course per line",
           "CSCI 2134  Software Development" in text)
check_true("--list collapses sections", text.count("CSCI 2134") == 1)
check_true("--list with a term has no term column", "Fall" not in text)

code, text = run(browser.main, ["--list", "CSCI", "3000", "--term", "202710"])
check_true("--list with a level narrows", "CSCI 3151" in text)
check_true("and drops the rest", "CSCI 2134" not in text)

code, text = run(browser.main, ["--list", "CSCI", "3000"])
check_true("--list without a term adds a bracketed term column",
           "[26/27 Fall]" in text)

code, text = run(browser.main, ["--list", "CSCI", "9000", "--term", "202710"])
check_true("an empty level says so", "nothing offered" in text)

# --sections shows meeting times; a bare course number implies it.
code, text = run(browser.main, ["--list", "CSCI", "2134", "--term", "202710"])
check_true("a course number shows its sections", "Lecture   01" in text)
check_true("and its labs", "Lab       B01" in text)
check_true("with days and times", "WF     14:35-15:55" in text)
check_true("and the room", "Dunn 101" in text)
check_true("other courses stay out", "CSCI 2141" not in text)

code, text = run(browser.main, ["--list", "CSCI", "3000", "--term", "202710",
                                "--sections"])
check_true("--sections works with a level", "CSCI 3151" in text)
check_true("and shows the time", "08:35-09:55" in text)

code, text = run(browser.main, ["--list", "CSCI", "2000", "--term", "202710"])
check_true("without --sections the list still collapses",
           "Lecture" not in text)

code, text = run(browser.main, ["--list", "AQUA", "--term", "202710",
                                "--sections"])
check_true("a two-pattern section shows both", text.count("11:35-12:25") == 1)
check_true("second pattern on its own line", "10:35-11:25" in text)

code, text = run(browser.main, ["--list", "ACSC", "--term", "202710",
                                "--sections"])
check_true("an unscheduled section names its mode",
           "Consult Department" in text)
check_true("and does not repeat it as a room", "room TBA" not in text)

code, text = run(browser.main, ["--list", "CSCI", "1109", "--sections"])
check_true("across terms each gets its own block", text.count("CSCI 1109") == 2)
check_true("labelled by term with the year",
           "[26/27 Fall]" in text and "[26/27 Winter]" in text)

# Term labels must carry the academic year. Dal lists 2025/2026 Winter and
# 2026/2027 Winter at the same time, and a bare "Winter" makes a course that
# already ran look like one you can still take.
check_true("term_label keeps the year",
           browser.term_label("2026/2027 Fall") == "26/27 Fall")
check_true("term_label separates the two winters",
           browser.term_label("2025/2026 Winter")
           != browser.term_label("2026/2027 Winter"))
check_true("term_label passes odd descriptions through",
           browser.term_label("Summer") == "Summer")

code, text = run(browser.main, ["--check", "CSCI 3152", "CSCI 1315"])
check_true("the old winter is labelled 25/26", "[25/26 Winter]" in text)
check_true("the new winter is labelled 26/27", "[26/27 Winter]" in text)
check_true("no bare 'Winter' anywhere", " Winter" not in text.replace("/26 Winter", "").replace("/27 Winter", ""))

code, text = run(browser.main, ["--check", "CSCI 3152", "--sections"])
check_true("--check --sections shows the section times", "10:05-11:25" in text)
check_true("tagged with the right term", "[25/26 Winter]" in text)
# The block already carries course, title and term, so the summary table
# would be saying all of it a second time.
check_true("the course is named once", text.count("CSCI 3152") == 1)
check_true("the title is printed once", text.count("Digital Media") == 1)
check_true("the term is printed once", text.count("25/26 Winter") == 1)

code, text = run(browser.main, ["--check", "CSCI 3151", "CSCI 9999",
                                "--sections"])
check_true("a missing course still gets a line", "CSCI 9999  not offered" in text)
check_true("alongside the offered one", "08:35-09:55" in text)

# Every section block is tagged, even when only one term was asked for.
code, text = run(browser.main, ["--list", "CSCI", "2134", "--term", "202710"])
check_true("a single-term block is still bracketed", "[26/27 Fall]" in text)

code, text = run(browser.main, ["--check", "CSCI 3151", "csci2115", "CSCI 9999"])
check_true("--check reports a Fall-only course", "CSCI 3151" in text)
check_true("--check brackets each term",
           "[26/27 Fall] [26/27 Winter]" in text)
check_true("--check reports a missing course", "not offered" in text)
check_true("'not offered' is not bracketed", "[not offered]" not in text)

# The shell splits `--check CSCI 3152 CSCI 3151` into four arguments, so a
# bare four-letter subject followed by a bare number has to be rejoined --
# otherwise the tool would demand quotes around every course.
check_true("rejoins split course names",
           browser.join_split_courses(["CSCI", "3152", "CSCI", "3151"])
           == ["CSCI 3152", "CSCI 3151"])
check_true("leaves already-quoted names alone",
           browser.join_split_courses(["CSCI 3152", "MATH 2060"])
           == ["CSCI 3152", "MATH 2060"])
check_true("leaves unspaced names alone",
           browser.join_split_courses(["csci2115"]) == ["csci2115"])
check_true("leaves a filename alone",
           browser.join_split_courses(["checklist.txt"]) == ["checklist.txt"])
check_true("does not swallow a trailing subject",
           browser.join_split_courses(["CSCI", "3152", "CSCI"])
           == ["CSCI 3152", "CSCI"])

code, text = run(browser.main, ["--check", "CSCI", "3152", "CSCI", "3151"])
check_true("unquoted --check works", code == 0)
check_true("and finds both courses",
           "CSCI 3152" in text and "CSCI 3151" in text)
check_true("without inventing a third", text.count("CSCI") == 2)

checklist = os.path.join(tempfile.mkdtemp(), "checklist.txt")
with open(checklist, "w", encoding="utf-8") as handle:
    handle.write("# my remaining requirements\ncsci 3151\nCSCI2115\n\n")
code, text = run(browser.main, ["--check", checklist])
check_true("--check reads a file", "CSCI 3151" in text and "CSCI 2115" in text)
check_true("--check ignores comments", "#" not in text)

code, text = run(browser.main, [])
check_true("no arguments prints help", code == 2)

# --- plan.py ----------------------------------------------------------------

plan.TERMS = ["202710", "202720"]
plan.TERM_NAMES = {"202710": "Fall 2026", "202720": "Winter 2027"}
plan.COURSES = ["CSCI 2134", "CSCI 1315", "MATH 2060", "CSCI 2141"]
plan.MIN_PER_TERM = 2
plan.MAX_PER_TERM = 2
plan.ELECTIVES = []
plan.TA_SECTIONS = [("202710", "CSCI 1109", "B01")]
plan.OTHER_COMMITMENTS = []
plan.MAX_VARIATIONS = 3
plan.SHOW = "list"
plan.PDF = None

code, text = run(plan.main)
check_true("plan.py succeeds", code == 0)
check_true("plan.py finds options", "Found 3 options" in text)
check_true("plan.py labels variations", "Variation 1" in text)
check_true("plan.py names the terms", "Fall 2026" in text)
check_true("plan.py shows the TA lab as kept free", "kept free" in text)

plan.SHOW = "grid"
code, text = run(plan.main)
check_true("the grid renders", "Mon" in text and "Tue" in text)
check_true("the grid shows a course", "CSCI 2134" in text)

plan.SHOW = "list"
plan.PDF = os.path.join(tempfile.mkdtemp(), "out.pdf")
code, text = run(plan.main)
check_true("plan.py writes a PDF when asked", os.path.exists(plan.PDF))
check_true("plan.py says where it wrote it", "Wrote" in text)
plan.PDF = None

# An impossible request must explain itself rather than printing nothing.
plan.COURSES = ["CSCI 2134", "CSCI 1315", "MATH 2060", "CSCI 2141", "CSCI 3151"]
plan.MIN_PER_TERM = 2
plan.MAX_PER_TERM = 2
code, text = run(plan.main)
check_true("an impossible request exits non-zero", code == 1)
check_true("and explains", "No schedule fits" in text)
check_true("and lists where each course is offered", "CSCI 3151" in text)

if failures:
    print("FAILED (%d)" % len(failures))
    for failure in failures:
        print(" -", failure)
    raise SystemExit(1)

print("cli:      all checks passed (browser.py, plan.py)")
