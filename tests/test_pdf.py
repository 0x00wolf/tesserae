"""
Checks for daltimetable.pdf: render real schedules, then read the PDF back.

Needs reportlab and pdfplumber. If either is missing this skips rather than
failing -- the PDF is optional in this project.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import os
import shutil
import tempfile

try:
    import pdfplumber
    import reportlab                                             # noqa: F401
except ImportError as error:                                    # noqa: BLE001
    print("pdf:      skipped (%s)" % error)
    raise SystemExit(0)

import fixture
from daltimetable import Commitment, SchedulePlanner
from daltimetable.pdf import ASSETS, MissingAsset, TimetablePDF

failures = []


def check(label, actual, expected):
    if actual != expected:
        failures.append("%s\n   expected: %r\n   actual:   %r"
                        % (label, expected, actual))


def check_true(label, condition):
    if not condition:
        failures.append(label)


TERMS = ["202710", "202720"]
TERM_NAMES = {"202710": "Fall 2026", "202720": "Winter 2027"}

timetable = fixture.timetable()
planner = SchedulePlanner(
    timetable,
    courses=["CSCI 2134", "CSCI 1315", "MATH 2060", "CSCI 2141"],
    terms=TERMS,
    min_per_term=2,
    max_per_term=2,
    commitments=[timetable.section("202710", "CSCI 1109", "B01"),
                 Commitment("Work", "F", "17:00", "20:00", term="202720")],
)
schedules = planner.schedules(limit=3)
check_true("the fixture produced schedules to draw", len(schedules) == 3)

workdir = tempfile.mkdtemp(prefix="timetable-pdf-")
path = os.path.join(workdir, "timetable.pdf")

TimetablePDF(term_names=TERM_NAMES).render(schedules, path)
check_true("the PDF exists", os.path.exists(path))
check_true("the PDF is not empty", os.path.getsize(path) > 5000)

with pdfplumber.open(path) as document:
    pages = []
    for page in document.pages:
        pages.append(page.extract_text() or "")

# 1 title page + 3 variations x 2 terms
check("page count", len(pages), 7)

title = pages[0]
check_true("title page names the tool", "Dalhousie Timetable" in title)
check_true("title page names both terms",
           "Fall 2026" in title and "Winter 2027" in title)
check_true("title page counts the variations", "3 variations" in title)

# Fall lands on even pages so a two-up view pairs it with Winter.
for index in range(1, 7):
    expected_term = "Fall 2026" if index % 2 == 1 else "Winter 2027"
    check_true("page %d is %s" % (index + 1, expected_term),
               pages[index].startswith(expected_term))

check_true("variation 1 is labelled", "Variation 1 of 3" in pages[1])
check_true("variation 3 is labelled", "Variation 3 of 3" in pages[6])
check_true("the course count is on the page", "courses" in pages[1])

body = "\n".join(pages)
check_true("a course appears", "CSCI 2134" in body)
check_true("rooms are shortened", "Goldberg" in body)
check_true("no raw Banner room strings", "GOLDBERG COMPUTER SCIENCE BLDG" not in body)
check_true("the TA lab is drawn", "CSCI 1109" in pages[1])
check_true("a hand-built commitment is drawn", "Work" in body)

# The TA lab is a commitment, so it must not inflate the course count.
check_true("commitments are not counted as courses", "2 courses" in pages[1])

with open(path, "rb") as handle:
    raw = handle.read()
check_true("Public Sans is embedded", b"PublicSans" in raw)

# reportlab always writes an unused default Helvetica resource, so the check
# that matters is which font the glyphs on the page actually use.
fonts_used = set()
with pdfplumber.open(path) as document:
    for page in document.pages:
        for character in page.chars:
            fonts_used.add(character["fontname"])
stripped = set()
for name in fonts_used:
    stripped.add(name.split("+", 1)[-1])
check("every glyph is Public Sans", sorted(stripped),
      ["PublicSans-Black", "PublicSans-Bold", "PublicSans-Regular"])

# A single schedule still renders, without the variation label.
single = os.path.join(workdir, "single.pdf")
TimetablePDF(term_names=TERM_NAMES).render(schedules[0], single)
with pdfplumber.open(single) as document:
    single_pages = [page.extract_text() or "" for page in document.pages]
check("single schedule page count", len(single_pages), 3)
check_true("one variation is not labelled", "Variation" not in single_pages[1])
check_true("title page says 1 variation", "1 variation" in single_pages[0])

# Pinning the window makes every page share a vertical range.
pinned = os.path.join(workdir, "pinned.pdf")
TimetablePDF(term_names=TERM_NAMES, day_start="08:00", day_end="20:00") \
    .render(schedules[0], pinned)
with pdfplumber.open(pinned) as document:
    pinned_text = document.pages[1].extract_text() or ""
check_true("pinned window starts at 08:00", "08:00" in pinned_text)
check_true("pinned window reaches 19:00", "19:00" in pinned_text)

# Missing fonts must raise, not fall back.
import daltimetable.pdf as module

empty = tempfile.mkdtemp(prefix="timetable-noassets-")
module._fonts_registered = False
raised = None
try:
    TimetablePDF(assets=empty)
except MissingAsset as error:
    raised = str(error)
check_true("missing fonts raise MissingAsset", raised is not None)
if raised:
    check_true("the error names the directory", empty in raised)
    check_true("the error names a font file", "PublicSans-Regular.ttf" in raised)
module._fonts_registered = False
module.register_fonts(ASSETS)

shutil.rmtree(workdir, ignore_errors=True)
shutil.rmtree(empty, ignore_errors=True)

if failures:
    print("FAILED (%d)" % len(failures))
    for failure in failures:
        print(" -", failure)
    raise SystemExit(1)

print("pdf:      all checks passed")
