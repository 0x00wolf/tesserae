# Modules

For building your own tool. If you just want a schedule, use [README.md](../README.md).

```
daltimetable/
  __init__.py     re-exports everything below except the PDF renderer
  timetable.py    DalTimetable, Section, Meeting, SectionSet
  planner.py      SchedulePlanner, Elective, Commitment, Schedule
  pdf.py          TimetablePDF        (needs reportlab; imported only on demand)
```

Three classes, two handoffs:

```
DalTimetable ──Section objects──▶ SchedulePlanner ──Schedule objects──▶ TimetablePDF
```

You construct `DalTimetable`, `SchedulePlanner` and `TimetablePDF`, plus `Elective` and `Commitment` when you need them. Everything else — `Section`, `Meeting`, `SectionSet`, `CourseChoice`, `Schedule` — only ever arrives as a return value.

`timetable` and `planner` are standard library only, and `__init__` does not import `pdf`, so nothing pulls in reportlab unless you ask for a PDF:

```python
from daltimetable import DalTimetable, SchedulePlanner, Elective, Commitment
from daltimetable.pdf import TimetablePDF          # only when you want the PDF
```

---

## DalTimetable

```python
from daltimetable import DalTimetable

timetable = DalTimetable()                    # or DalTimetable(campuses=["100"])
```

| Call | Returns |
|---|---|
| `available_terms(in_progress=False)` | `[("202710", "2026/2027 Fall"), ...]` |
| `subjects(terms)` | `[("CSCI", "Computer Science"), ...]` |
| `sections(terms, subjects=None, course=None)` | `SectionSet` |
| `section(term, course, section)` | one `Section` |
| `offered(courses, terms)` | `{"CSCI 3151": ["202710"], ...}` |
| `titles(courses, terms)` | `{"CSCI 2134": "Software Development"}` |
| `check_subjects(subjects, terms)` | raises `UnknownSubject`, or nothing |

`terms` and `subjects` each take a string or a list. Results are cached per `(term, subject)` for the life of the object, so asking twice costs one request.

Omitting `subjects` pulls every subject in those terms — 156 requests and about 4,000 sections per term. Name your subjects when you can.

```python
timetable.sections("202720", "CSCI")
timetable.sections(["202710", "202720"], ["CSCI", "MATH"])
timetable.sections("202710", "CSCI", course="csci 2134")
timetable.section("202710", "CSCI 1109", "B01")
```

Campus codes: `100` Halifax, `200` Truro, `300` Online, `400` Others. All four unless you pass `campuses=`.

### Errors

- `UnknownSubject` — a subject code Dal doesn't have.
- `NotFound` — a course or section that isn't in the timetable. The section error lists what the course actually has.
- `TimetableError` — the base class; also raised for an unreadable course name, a bad day letter, a bad time, or an unreachable server.

---

## Section and Meeting

```python
section.term              # "202710"
section.crn               # "10727"
section.subject           # "CSCI"
section.number            # "2134"
section.course            # "CSCI 2134"
section.title             # "Software Development"
section.component         # "Lecture" | "Lab" | "Tutorial" | "Thesis" | ...
section.section           # "01", "B01", "T04"
section.level             # 2000
section.credit_hours      # 3
section.link              # "B0" -- see "Linked components" below
section.capacity          # 60
section.enrolled          # 51
section.seats_available   # 9
section.scheduled         # False for asynchronous / consult-department
section.days()            # ("Wednesday", "Friday") across all meetings
section.meetings          # (Meeting, ...)
```

```python
meeting.days              # ("Wednesday", "Friday")
meeting.start             # "14:35"     None when there is no fixed time
meeting.end               # "15:55"
meeting.start_minutes     # 875         for arithmetic
meeting.end_minutes       # 955
meeting.room              # "Dunn 101"  already shortened
meeting.delivery          # "In Person" | "Asynchronous Session" | ...
meeting.first_date        # datetime.date(2026, 9, 8)
meeting.last_date         # datetime.date(2026, 12, 9)
meeting.scheduled         # bool
meeting.clock()           # "14:35-15:55", or the delivery mode
meeting.letters()         # "WF"
```

**`meetings` is a list because a section can meet on more than one pattern.** 278 of Fall 2026's 3,999 sections do — a different day, time and room under one CRN. ARCH 3207 has four. Always walk `meetings`; never read `meetings[0]` and move on.

**About a quarter of all sections have no fixed time** — honours projects, asynchronous online courses, thesis credit. Check `scheduled` before doing anything with `start_minutes`.

**Meetings can be scoped to part of the term.** When a room or delivery mode changes partway through, `first_date`/`last_date` narrow to that window instead of the full term.

---

## SectionSet

A `list` subclass. Every filter returns a new `SectionSet`, so they chain, and the result is still an ordinary list.

| Filter | Keeps |
|---|---|
| `.level(4000)` | courses numbered 4000–4999 |
| `.component("Lab")` | one kind of section; also accepts Banner's `"Lec"` |
| `.on_days("TR")` | sections meeting **only** on those days |
| `.between("10:00", "17:00")` | sections whose every meeting fits the window |
| `.with_seats()` | sections that had a free seat when read |
| `.courses()` | terminal — `[("CSCI 2134", "Software Development"), ...]` |
| `.terms()` | terminal — the distinct term codes present |

`.on_days()` takes `"TR"` or `["Tuesday", "Thursday"]`. Day letters are `M T W R F S U`; **R is Thursday**.

Sections with no fixed meeting time are kept by `.on_days()` and `.between()` — they meet on no day and at no time, so they can't violate either preference. `.with_seats()` drops sections whose seat count Banner didn't report.

```python
timetable.sections("202720", "CSCI").level(4000).courses()
timetable.sections("202710", "CSCI").level(2000).component("Lecture").on_days("TR")
```

---

## SchedulePlanner

```python
from daltimetable import SchedulePlanner, Elective, Commitment

planner = SchedulePlanner(
    timetable,
    courses=["CSCI 2134", "CSCI 3130", "MATH 2060"],
    terms=["202710", "202720"],
    min_per_term=1,
    max_per_term=2,
    electives=[Elective(subject="PHYC", level=1000, pick=1)],
    commitments=[timetable.section("202710", "CSCI 1109", "B01")],
    earliest="10:00",
    latest="17:00",
    require_seats=False,
)
schedules = planner.schedules(limit=100)
```

`schedules(limit)` returns up to `limit` `Schedule` objects in a stable order — the same inputs always give the same first N. `offerings(course)` returns `{term: [bundle, ...]}` for one course, which is what to look at when nothing fits.

Subject codes are validated before the search runs, so a typo raises rather than returning an empty list.

### Elective

```python
Elective(["PHYC 2451", "PHYC 2452"], pick=1)     # from these courses
Elective(subject="PHYC", level=1000, pick=1)     # from a subject and level
Elective(some_section_set, pick=1)               # from a SectionSet you built
```

Each elective slot picks `pick` distinct courses from its pool. Multiple slots are independent. A pool of *n* courses multiplies the search by roughly *n choose pick*, so `limit` matters.

### Commitment

Hours that stay free. They block time but don't count toward the per-term totals.

```python
Commitment("Work", "MW", "17:00", "21:00")
Commitment("Commute", ["Friday"], "08:00", "09:00", term="202710", room="—")
```

`term=None` (the default) means every term.

Anything that **is** a Dal section — a lab you TA — should come from `timetable.section(...)` instead and be passed straight into `commitments=`. The planner accepts `Section` and `Commitment` objects interchangeably, and taking the section means the days, times and room are Banner's rather than typed by hand.

---

## Schedule

```python
schedule.terms            # {"202710": (CourseChoice, ...), ...}
schedule.commitments      # (Busy, ...)
schedule.variation        # 1-based index within the result list
schedule.choices(term)    # the CourseChoice tuple for one term
schedule.course_names()   # ["CSCI 2134", ...] across all terms
schedule.rows()           # flat tuples, see below
schedule.describe(term_names)   # plain text summary
```

`CourseChoice` is one course and the sections you'd register in together:

```python
choice.course     # "CSCI 2134"
choice.title      # "Software Development"
choice.sections   # (Section, ...) -- a lecture, plus its lab or tutorial
```

`rows()` flattens everything to one tuple per meeting:

```python
("202720", "CSCI 1315", "Lecture",
 ["Monday", "Wednesday", "Friday"], "12:35-13:25", "Rowe 1009")
```

A section that meets on two patterns produces two rows.

---

## TimetablePDF

```python
from daltimetable.pdf import TimetablePDF

TimetablePDF(
    term_names={"202710": "Fall 2026", "202720": "Winter 2027"},
    day_start=None,          # "08:00" to pin every page to the same range
    day_end=None,            # "20:00"
    heading="Dalhousie Timetable",
).render(schedules, "timetable.pdf")
```

`render()` takes one `Schedule` or a list. Page 1 is the title page; each variation then contributes one landscape page per term, in term order.

- Courses take colours from a seven-entry palette in the order they first appear on the page, so the same schedule always colours the same way.
- Commitments are drawn in grey and left out of the course count in the corner.
- Sections with no fixed time are listed under the grid rather than occupying a slot.
- Each page fits its own earliest and latest class unless you pin `day_start`/`day_end`.
- Overlapping blocks split into half-width lanes rather than hiding one another.

`register_fonts(assets)` raises `MissingAsset` if Public Sans isn't in `assets/` at the project root. There is deliberately no fallback font.

---

## What Banner does that shapes all of this

Worth knowing if you go around `DalTimetable` and hit the endpoints yourself.

**The endpoints.** `https://self-service.dal.ca/BannerExtensibility/internalPb/virtualDomains.<domain>` — public GETs, no login. `dal_stuweb_academicTimetable` is the section feed; `_terms`, `_subjects`, `_districts`, `_instructors`, `_restrictions` are the rest. The site's own requests base64-obfuscate parameter names and pass `encoded=true`; plain parameters work and are what this uses.

**One subject per request.** `subj_code=CSCI;MATH;` returns HTTP 500 and an empty one returns nothing, so a wide pull loops over subjects. `terms` *does* take several at once.

**`page_size`/`page_num` paginate by course, not by section**, so `page_size=9999, page_num=1` returns everything. `max`/`offset` do row-level paging separately, and `x-hedtech-totalcount` in the response headers gives the true total.

**Meetings are parallel `<br>`-joined lists.** `TIMES`, `LOCATIONS` and the seven day columns each split on `<br>`, and index *i* across all of them is one meeting. The arity always matches — verified on all 7,869 sections of 2026/2027.

**`TIMES` can be `C/D`** — consult department, no fixed time. It's the only non-`HHMM-HHMM` value in the whole corpus.

**`LOCATIONS` can contain date-range headers** like `<b>*** 08-SEP-2026 - 08-SEP-2026 ***</b>`, which scope the meetings that follow. 197 sections do this. They occupy their own `<br>` slot and are not meetings.

### Linked components

`link` ties a lecture to the lab or tutorial you must take with it. The letter names the *other* side of the pairing, which reads backwards until you've seen it once:

- a lecture carries `B0` (its labs) or `T0` (its tutorials), or `B0, T0` for both
- the matching lab or tutorial carries `L0` (its lecture)
- the digit groups them, so `B1`/`L1` is a separate pairing
- `None` means no required partner — most lectures

Verified on COMM 1010, where lecture `01` (`B0`) pairs with labs B01–B05 (`L0`) and lecture `02` (`B1`) pairs with labs B06–B10 (`L1`).

It's a comma-separated list, so split on `,` before comparing. A few courses point at a group with no members — BUSI 5551 has a lecture linked to a lab group that doesn't exist — so the planner falls back to any section of that component rather than dropping the course.

---

## Tests

`tests/fixture.py` holds real 2026/2027 sections and replaces `DalTimetable._request`, so parsing, caching, subject validation, filtering, the search and the PDF all run for real against real data with only the network faked.

```
python3 run_tests.py                 # all four
python3 tests/test_planner.py        # or one at a time
```

`tests/test_planner.py` independently re-checks every returned schedule for clashes rather than trusting the search. `tests/test_pdf.py` reads the PDF back to confirm the page order, the variation labels and that every glyph is Public Sans.
