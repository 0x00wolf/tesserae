# Tessera

![banner](./assets/image.jfif)

A tessera (plural: tesserae, diminutive tessella) is an individual tile, usually formed in the shape of a square, used in creating a mosaic. 

This project is intended to vastly simplify the process of determining your ideal schedule at university. Currently it is designed to work out of the box for Dalhousie University, but the scraper isn't actually Dal-specific. It targets Ellucian Banner Extensibility, which a lot of universities run. Swap the base URL and the domain names and it should work for another school with minimal or no tweaking.

I made this when I was struggling to find a class schedule that let me take the courses I required without overlap. I was trying to plan for two semesters and every change caused course conflicts between the two semesters. It wasn't an experience I wanted to relive. 

## Important

This project is not endorsed by Dalhousie. I included the logo & public sans (Dal's font) purely for the my personal use. You can find out information about Dal's  

## Shoutout

This project was generated with the assistance of Opus 5.0.

## Main entrypoints

- **`browser.py`** — look up what Dal is offering this year.
- **`plan.py`** — list the courses you need, run it, get every conflict-free way to fit them across your terms.  Can generate a PDF of your potential outcomes in pretty formatting to visually analyze the schedule iterations generated.

It reads Dalhousie's published timetable directly. No login, no scraping of web pages, no account.

User browser.py to find out if the courses you want are being offered and then modify plan.py so that it outputs all of the potential non-conflicting schedules you can have with your desired courses. Use the planner to identify electives, block off TA'ing sessions. It has all the features I need to plan my semester, so I'm assuming it will work for yours as well :).

## What's here

```
plan.py            ← edit this, then run it
browser.py         ← run this to look things up
run_tests.py       run every test
README.md          this file

daltimetable/      the library — you don't need to open this
  timetable.py       reads the timetable. Can be adapted for other schools
  planner.py         finds the schedules
  pdf.py             draws the PDF

assets/            Public Sans (Dal's preferred font) + the Dal shield, used by the PDF
tests/             offline tests, and the captured sections they run on
docs/MODULES.md    the API, if you want to build your own tool
```

## Setup

Python 3.9 or newer. **No dependencies** (std. lib only), unless you want to generate a PDF of your selected schedule or of potential schedules for visual review. 

The project is setup with Astral's UV, so you can just run `uv sync` if you want to install the requirements, and then run the files with `uv run filename --arguments`:

Example:

```bash
$ uv sync
$ uv run browser.py --terms # find out term codes
$ uv run browser.py --check 3152 --sections --term 202710 # Example: Check to see if a specific course is offered in a specific term.
```

If you're using pip:

```bash
pip install reportlab pillow
```

## Detailed Guide

### Start here: what's being offered?

```
$ python3 browser.py --terms
202620  2025/2026 Winter
202630  2025/2026 Summer
202700  2026/2027 Medicine/Dentistry
202710  2026/2027 Fall
202720  2026/2027 Winter
```

Those five-digit codes are what everything else uses.

```
$ python3 browser.py --list CSCI 2000 --term 202710
CSCI 2110  Computer Structures
CSCI 2112  Discrete Structures II
CSCI 2115  Theory of Computer Science
CSCI 2122  Systems Programming
CSCI 2134  Software Development
CSCI 2141  Intro to Database Systems
```

One course per line, ready to paste into `plan.py`. Leave the level off to see the whole subject.

Leave `--term` off and each course gets its terms in brackets instead:

```
$ python3 browser.py --list CSCI 2000
CSCI 2115  Theory of Computer Science  [26/27 Fall] [26/27 Winter]
CSCI 2122  Systems Programming         [26/27 Fall] [26/27 Winter]
CSCI 2134  Software Development        [26/27 Fall] [26/27 Winter]
CSCI 2141  Intro to Database Systems   [26/27 Fall] [26/27 Winter]
```

The academic year is in the label on purpose. Dal keeps several terms viewable at once — right now that includes both 2025/2026 Winter and 2026/2027 Winter — so a bare "Winter" would let you plan around a term that has already happened.

### Seeing the actual times

Give a course number instead of a level, and you get every section with its meeting times:

```
$ python3 browser.py --list CSCI 2134 --term 202710
CSCI 2134  Software Development  [26/27 Fall]
  Lecture   01    WF     14:35-15:55  Dunn 101
  Lecture   02    TR     13:05-14:25  Dunn 101
  Lab       B01   M      16:05-17:25  Goldberg 134
  Lab       B03   M      14:35-15:55  Goldberg 143
```

Lectures first, then labs, then tutorials. Add `--sections` to get the same detail for a whole level or subject — `--list CSCI 4000 --sections`.

A section that meets at two different times gets a line for each. One with no fixed time says so instead:

```
  Lecture   01    --     Asynchronous Session
```

### Checking a degree checklist

Put your remaining requirements in a text file, one per line:

```
# still need these
CSCI 3151
CSCI 2115
CSCI 4192
```

Then, the day the new timetable goes up:

```
$ python3 browser.py --check checklist.txt
CSCI 3151  Foundations of Machine Learning  [26/27 Fall]
CSCI 2115  Theory of Computer Science       [26/27 Fall] [26/27 Winter]
CSCI 4192  —                                not offered
```

That's the whole reason `--check` exists: courses that only run some years are easy to miss. `not offered` is deliberately left unbracketed, so it never reads as the name of a term.

You can also list them inline, and quoting is optional:

```
$ python3 browser.py --check CSCI 3151 CSCI 2115
```

Add `--sections` and you get the meeting times instead of the summary:

```
$ python3 browser.py --check CSCI 3151 CSCI 4192 --sections
CSCI 3151  Foundations of Machine Learning  [26/27 Fall]
  Lecture   01    MW     08:35-09:55  Dunn 135

CSCI 4192  not offered
```

### All of browser.py

| Command | Does |
|---|---|
| `--terms` | term codes currently available |
| `--subjects --term 202710` | subject codes offered that term |
| `--list CSCI --term 202710` | every CSCI course offered |
| `--list CSCI 4000 --term 202710` | the 4000-level CSCI courses in the fall 2026/2027 term |
| `--list CSCI 2134 --term 202710` | one course, with every lecture, lab and tutorial time |
| `--list CSCI 4000 --sections` | the same detail for a whole level |
| `--check CSCI 4192 CSCI 3152` | which of these run, and when |
| `--check checklist.txt` | same, read from a file |
| `--check CSCI 3151 --sections` | which terms, plus the times in each |

`--term` is repeatable. Omit it to cover every available term.

The second argument to `--list` is read as a level when it ends in `000`, and as a single course number otherwise — so `--list CSCI 4000` gives you the whole level and `--list CSCI 2134` gives you that one course.

## Building a schedule: plan.py

Open `plan.py`, edit the seven blocks at the top, then run it:

```
python3 plan.py
```

Everything below the `nothing to edit below` line can be ignored.

### 1. Terms

```python
TERMS = ["202710", "202720"]
TERM_NAMES = {"202710": "Fall 2026", "202720": "Winter 2027"}
```

`TERM_NAMES` is only what prints on screen and on the PDF.

### 2. Courses you must take

```python
COURSES = [
    "CSCI 2134",
    "CSCI 2141",
    "MATH 2060",
    "CSCI 1315",
]
```

Any spelling works — `CSCI 2134`, `csci 2134`, `CSCI2134`, `csci2134`, `CSCI-2134`.

If you insert a typo for the subject it throws an error:

```
'CSC'  is not a valid subject code. Run browser.py --subjects for the list.
```

### 3. Course load

```python
MIN_PER_TERM = 2
MAX_PER_TERM = 2
```

Every term ends up holding between these two numbers of courses.

### 4. Electives (optional)

A slot filled from a pool instead of a named course. Three forms:

```python
# whichever of these two fits
ELECTIVES = [Elective(["PHYC 2451", "PHYC 2452"], pick=1)]

# any 1000-level physics course
ELECTIVES = [Elective(subject="PHYC", level=1000, pick=1)]

# two of these three, in whatever combination works
ELECTIVES = [Elective(["HIST 1000", "PHIL 1000", "ENGL 1000"], pick=2)]
```

A wide pool multiplies the number of options — twenty candidate courses roughly means twenty times as many schedules. `MAX_VARIATIONS` caps what you get back.

### 5. Hours that must stay free (optional)

If you TA, you might have a blocked off time slot, but don't need to take the associated lecture. You can block off just one portion of a class (lab, tutorial, etc.):

```python
TA_SECTIONS = [
    ("202710", "CSCI 1109", "B01"),
    ("202720", "CSCI 1109", "B01"),
]
```

**Section codes** are Banner's: `01`, `02` are lectures; `B01`, `B02` are labs; `T01` is a tutorial; `98`/`99` are usually the online section. The numbering has gaps — CSCI 2134 in Fall runs `01`, `02`, `B01`, `B03`, with no `B02`. Use `browser.py` or the error message to see what a course actually has.

For anything Dal doesn't know about:

```python
OTHER_COMMITMENTS = [
    Commitment("Work", "MW", "17:00", "21:00"),
    Commitment("Volunteering", ["Friday"], "13:00", "16:00", term="202720"),
]
```

Day letters are `M T W R F` — **R is Thursday**.

Commitments block those hours but don't count toward `MIN_PER_TERM` / `MAX_PER_TERM`, and they don't count as courses on the PDF.

### 6. Narrowing the search (optional)

```python
NO_CLASSES_BEFORE = "10:00"     # skip the 08:35s
NO_CLASSES_AFTER  = "17:00"     # skip evening classes
ONLY_WITH_SEATS   = True        # skip sections that were full
```

**About `ONLY_WITH_SEATS`:** seat counts are a snapshot from the moment the tool read the timetable. They change every day, and they change a lot once registration opens. A section that's full today may not be full when you register, and vice versa. Treat it as a hint, not a fact — and re-run the tool close to your registration time rather than trusting a plan you made in August.

### 7. Output

```python
MAX_VARIATIONS = 10
SHOW = "list"          # or "grid" for a week view
PDF = None             # or "timetable.pdf"
```

`SHOW = "list"` prints a compact summary per option:

```
Fall 2026 -- 2 courses
  CSCI 1315   Discrete Math for CS
    Lecture   01   TRF    08:35-09:25  Rowe 1009
  MATH 2060   Intro Probability & Statistics
    Lecture   01   TR     10:05-11:25  LSC C242
    Tutorial  T01  T      14:35-16:25  LSC C208
  CSCI 1109   T      11:35-12:55  Goldberg 134  (kept free)
```

`SHOW = "grid"` prints the same week as an ASCII timetable.

Setting `PDF` also writes a printable version: a title page, then one landscape page per term per variation, each labelled `Variation 2 of 6`. With two terms that puts Fall and Winter on facing pages in a two-page view — turn on "show cover page in two-page view" in your PDF reader.

## When nothing fits

`plan.py` tells you where each course is available rather than just failing:

```
No schedule fits those settings.

  CSCI 2134   Fall 2026 (4 options), Winter 2027 (2 options)
  CSCI 3151   Fall 2026 (1 option)
  CSCI 9999   not offered in your terms, or filtered out by section 6

Try widening MIN_PER_TERM / MAX_PER_TERM, adding a term, or relaxing section 6.
```

Most often it's `MAX_PER_TERM` being too small for the number of courses, or a course that only runs in one of your terms.

## Tests

```
python3 run_tests.py
```

Four test files, all offline, against real 2026/2027 sections captured from the live timetable. No network needed. Run one on its own with `python3 tests/test_planner.py`.

## Fonts and the logo

`assets/` holds Public Sans (Dalhousie's typeface) and the university shield, used by the PDF. **These are required** — if a font file is missing the PDF raises an error naming it rather than quietly substituting something else.

Public Sans is under the SIL Open Font License; `assets/OFL.txt` is the licence and must stay with the fonts if you redistribute this.

The logo needs Pillow to draw. Without it the title page still renders, minus the shield, and says so.

## Building on the modules

`browser.py` and `plan.py` are thin wrappers over the three classes in `daltimetable/`. If you want to write your own tool on top — **[docs/MODULES.md](docs/MODULES.md)**.

## A note on being polite

This reads a public endpoint that has no published rate limit. The tool uses six concurrent requests and caches everything for the life of a run, so a full plan is a few dozen requests. Don't put it in a loop.
