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
check_true("--list without a term adds a term column", "Fall" in text)

code, text = run(browser.main, ["--list", "CSCI", "9000", "--term", "202710"])
check_true("an empty level says so", "nothing offered" in text)

code, text = run(browser.main, ["--check", "CSCI 3151", "csci2115", "CSCI 9999"])
check_true("--check reports a Fall-only course", "CSCI 3151" in text)
check_true("--check reports both terms", "Fall, Winter" in text)
check_true("--check reports a missing course", "not offered" in text)

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
