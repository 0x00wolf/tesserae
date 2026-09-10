"""
daltimetable.pdf -- draw schedules as a weekly PDF.

One title page, then one landscape page per term per variation. With two terms
that puts Fall and Winter on facing pages in a two-up view.

    from daltimetable.pdf import TimetablePDF

    TimetablePDF(term_names={"202710": "Fall 2026", "202720": "Winter 2027"}) \\
        .render(schedules, "timetable.pdf")

Needs reportlab (`pip install reportlab`). Everything else in this project is
standard library only, and nothing imports this module unless you ask for a PDF.

The Public Sans font files and the Dalhousie logo live in assets/ at the
project root. The fonts are required -- if they are missing this raises rather than
quietly substituting Helvetica.
"""

import os
import sys

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


def _find_assets():
    """
    assets/ lives at the project root, beside plan.py.

    The in-package location is checked first so this still works if the
    package is ever installed on its own.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    inside = os.path.join(here, "assets")
    if os.path.isdir(inside):
        return inside
    return os.path.join(os.path.dirname(here), "assets")


ASSETS = _find_assets()

FONT_FILES = {
    "PublicSans": "PublicSans-Regular.ttf",
    "PublicSans-Bold": "PublicSans-Bold.ttf",
    "PublicSans-Black": "PublicSans-Black.ttf",
}
LOGO_FILE = "dal-logo.png"

REGULAR = "PublicSans"
BOLD = "PublicSans-Bold"
BLACK = "PublicSans-Black"

PAGE_SIZE = landscape(letter)
MARGIN = 34
DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

INK = HexColor("#181c22")
INK_SOFT = HexColor("#4a545f")
INK_FAINT = HexColor("#8a949e")
RULE = HexColor("#c9d0d7")
RULE_FAINT = HexColor("#e6ebef")
DAL_GOLD = HexColor("#ffcc00")

# Fill and left-edge pairs. Courses take them in the order they first appear,
# so the same schedule always colours the same way.
PALETTE = [
    (HexColor("#dbeceb"), HexColor("#0e6a68")),   # teal
    (HexColor("#dee4f4"), HexColor("#2f4f9e")),   # blue
    (HexColor("#f8e3d9"), HexColor("#9c4a24")),   # rust
    (HexColor("#e7edda"), HexColor("#556928")),   # olive
    (HexColor("#f1e0ef"), HexColor("#7d3f76")),   # plum
    (HexColor("#dde8ee"), HexColor("#356179")),   # steel
    (HexColor("#f0e7d4"), HexColor("#7a5a12")),   # amber
]
COMMITMENT_COLOURS = (HexColor("#e8e9ea"), HexColor("#6b7280"))

_fonts_registered = False


class MissingAsset(Exception):
    """A bundled font or image is not where it should be."""


def register_fonts(assets=ASSETS):
    """Load Public Sans. Raises if the files are not in assets/."""
    global _fonts_registered
    if _fonts_registered:
        return
    missing = []
    for name, filename in FONT_FILES.items():
        path = os.path.join(assets, filename)
        if not os.path.exists(path):
            missing.append(filename)
    if missing:
        raise MissingAsset(
            "font missing in %s: %s\n"
            "Public Sans is required. Restore the files from the project's "
            "assets/ directory." % (assets, ", ".join(missing)))
    for name, filename in FONT_FILES.items():
        pdfmetrics.registerFont(TTFont(name, os.path.join(assets, filename)))
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD)
    _fonts_registered = True


# ---------------------------------------------------------------------------
# Turning a schedule into drawable blocks
# ---------------------------------------------------------------------------

def _blocks_for_term(schedule, term):
    """(blocks, unscheduled) for one term of one schedule."""
    blocks = []
    unscheduled = []

    for choice in schedule.terms.get(term, ()):
        for section in choice.sections:
            kind = "%s %s" % (section.component, section.section)
            for meeting in section.meetings:
                if not meeting.scheduled:
                    unscheduled.append("%s  %s  %s"
                                       % (choice.course, kind, meeting.delivery))
                    continue
                blocks.append(_block(choice.course, choice.title, kind,
                                     meeting, is_commitment=False))

    for busy in schedule.commitments:
        if busy.term is not None and busy.term != term:
            continue
        for meeting in busy.meetings:
            if not meeting.scheduled:
                continue
            if busy.section is not None:
                kind = "%s %s" % (busy.section.component, busy.section.section)
            else:
                kind = "kept free"
            blocks.append(_block(busy.label, busy.title, kind,
                                 meeting, is_commitment=True))

    return blocks, unscheduled


def _block(course, title, kind, meeting, is_commitment):
    return {
        "course": course,
        "title": title,
        "kind": kind,
        "days": list(meeting.days),
        "start": meeting.start_minutes,
        "end": meeting.end_minutes,
        "room": meeting.room or "room TBA",
        "commitment": is_commitment,
    }


def _clock(minutes):
    return "%02d:%02d" % (minutes // 60, minutes % 60)


def _assign_colours(blocks):
    colours = {}
    next_index = 0
    for item in blocks:
        if item["course"] in colours:
            continue
        if item["commitment"]:
            colours[item["course"]] = COMMITMENT_COLOURS
        else:
            colours[item["course"]] = PALETTE[next_index % len(PALETTE)]
            next_index += 1
    return colours


def _lanes(blocks):
    """
    Side-by-side placement for blocks that overlap on the same day.

    A schedule out of the planner never clashes with itself, but two blocks can
    still share a slot in odd cases; half-width pairs say so more plainly than
    one block hidden under another.
    """
    ordered = sorted(blocks, key=lambda item: (item["start"], item["end"]))
    clusters = []
    current = []
    cluster_end = None
    for item in ordered:
        if current and cluster_end is not None and item["start"] >= cluster_end:
            clusters.append(current)
            current = []
            cluster_end = None
        current.append(item)
        if cluster_end is None or item["end"] > cluster_end:
            cluster_end = item["end"]
    if current:
        clusters.append(current)

    for cluster in clusters:
        lane_ends = []
        for item in cluster:
            placed = False
            for index in range(len(lane_ends)):
                if lane_ends[index] <= item["start"]:
                    item["lane"] = index
                    lane_ends[index] = item["end"]
                    placed = True
                    break
            if not placed:
                item["lane"] = len(lane_ends)
                lane_ends.append(item["end"])
        for item in cluster:
            item["lanes"] = len(lane_ends)
    return ordered


# ---------------------------------------------------------------------------
# The renderer
# ---------------------------------------------------------------------------

class TimetablePDF:
    """
    Draw one or more schedules as a PDF.

        TimetablePDF(term_names={"202710": "Fall 2026"}).render(schedules, "out.pdf")

    term_names maps a term code to what should print on the page. day_start and
    day_end ("08:00", "20:00") pin every page to the same vertical range; leave
    them out and each page fits its own earliest and latest class.
    """

    def __init__(self, term_names=None, day_start=None, day_end=None,
                 assets=ASSETS, heading="Dalhousie Timetable"):
        self.term_names = dict(term_names) if term_names else {}
        self.day_start = day_start
        self.day_end = day_end
        self.assets = assets
        self.heading = heading
        register_fonts(assets)

    def term_name(self, term):
        return self.term_names.get(term, "Term %s" % term)

    def render(self, schedules, path, title=None):
        """
        Write the PDF. `schedules` is one Schedule or a list of them.

        Page 1 is the title page, then each variation contributes one page per
        term in term order. With two terms that lands Fall on the left and
        Winter on the right of every spread.
        """
        if not isinstance(schedules, (list, tuple)):
            schedules = [schedules]
        if not schedules:
            raise ValueError("no schedules to draw")

        terms = []
        for schedule in schedules:
            for term in sorted(schedule.terms):
                if term not in terms:
                    terms.append(term)

        page = canvas.Canvas(path, pagesize=PAGE_SIZE)
        page.setTitle(title or self.heading)
        page.setAuthor("dalhousie-timetable-planner")

        self._title_page(page, terms, len(schedules))
        page.showPage()

        for number in range(len(schedules)):
            schedule = schedules[number]
            for term in sorted(schedule.terms):
                blocks, unscheduled = _blocks_for_term(schedule, term)
                self._term_page(page, self.term_name(term), blocks, unscheduled,
                                number + 1, len(schedules))
                page.showPage()

        page.save()
        return path

    # -- pages --------------------------------------------------------------

    def _title_page(self, page, terms, count):
        width, height = PAGE_SIZE
        centre = width / 2.0

        # The block runs from the top of the logo down to the variation count,
        # roughly 270pt; this puts that block on the page's centre line.
        logo_path = os.path.join(self.assets, LOGO_FILE)
        logo_bottom = height / 2.0 - 16
        if os.path.exists(logo_path):
            try:
                image = ImageReader(logo_path)
                image_width, image_height = image.getSize()
                drawn_height = 150.0
                drawn_width = image_width * (drawn_height / image_height)
                page.drawImage(image, centre - drawn_width / 2.0, logo_bottom,
                               width=drawn_width, height=drawn_height,
                               mask="auto")
            except Exception as error:                      # noqa: BLE001
                print("timetable_pdf: skipping the logo (%s). "
                      "Install Pillow to include it: pip install pillow"
                      % error, file=sys.stderr)

        page.setFillColor(INK)
        page.setFont(BLACK, 34)
        page.drawCentredString(centre, logo_bottom - 54, self.heading)

        names = []
        for term in terms:
            names.append(self.term_name(term))
        page.setFillColor(INK_SOFT)
        page.setFont(REGULAR, 15)
        page.drawCentredString(centre, logo_bottom - 78, "  ·  ".join(names))

        page.setStrokeColor(DAL_GOLD)
        page.setLineWidth(3)
        page.line(centre - 70, logo_bottom - 96, centre + 70, logo_bottom - 96)

        page.setFillColor(INK_FAINT)
        page.setFont(REGULAR, 10)
        page.drawCentredString(centre, logo_bottom - 118,
                               "%d variation%s" % (count, "" if count == 1 else "s"))

    def _term_page(self, page, heading, blocks, unscheduled, variation, total):
        width, height = PAGE_SIZE
        colours = _assign_colours(blocks)
        window_start, window_end = self._window(blocks)

        top = height - MARGIN
        page.setFillColor(INK)
        page.setFont(BOLD, 20)
        page.drawString(MARGIN, top - 16, heading)

        courses = []
        for item in blocks:
            if not item["commitment"] and item["course"] not in courses:
                courses.append(item["course"])

        corner = "%d course%s" % (len(courses), "" if len(courses) == 1 else "s")
        if total > 1:
            corner = "Variation %d of %d  ·  %s" % (variation, total, corner)
        page.setFont(REGULAR, 9)
        page.setFillColor(INK_FAINT)
        page.drawRightString(width - MARGIN, top - 16, corner)

        page.setStrokeColor(INK)
        page.setLineWidth(1.2)
        page.line(MARGIN, top - 30, width - MARGIN, top - 30)

        footer_height = 26
        if unscheduled:
            footer_height += 10 * len(unscheduled)

        grid_top = top - 52
        grid_bottom = MARGIN + footer_height
        grid_left = MARGIN + 40
        column_width = (width - MARGIN - grid_left) / float(len(DAY_ORDER))
        span = window_end - window_start
        if span <= 0:
            span = 60
        scale = (grid_top - grid_bottom) / float(span)

        def y_at(minute):
            return grid_top - (minute - window_start) * scale

        page.setFont(BOLD, 10)
        page.setFillColor(INK_SOFT)
        for index in range(len(DAY_ORDER)):
            middle = grid_left + column_width * (index + 0.5)
            page.drawCentredString(middle, grid_top + 8, DAY_ORDER[index][:3].upper())

        page.setFont(REGULAR, 7.5)
        first_hour = (window_start + 59) // 60
        last_hour = window_end // 60
        for hour in range(first_hour, last_hour + 1):
            y = y_at(hour * 60)
            page.setStrokeColor(RULE_FAINT)
            page.setLineWidth(0.5)
            page.line(grid_left, y, width - MARGIN, y)
            page.setFillColor(INK_FAINT)
            page.drawRightString(grid_left - 6, y - 2.5, "%02d:00" % hour)

        page.setStrokeColor(RULE)
        page.setLineWidth(0.6)
        for index in range(len(DAY_ORDER) + 1):
            x = grid_left + column_width * index
            page.line(x, grid_top, x, grid_bottom)
        page.line(grid_left, grid_top, width - MARGIN, grid_top)
        page.line(grid_left, grid_bottom, width - MARGIN, grid_bottom)

        for day_index in range(len(DAY_ORDER)):
            day = DAY_ORDER[day_index]
            on_this_day = []
            for item in blocks:
                if day in item["days"]:
                    on_this_day.append(dict(item))
            for item in _lanes(on_this_day):
                self._draw_block(page, item, colours, day_index,
                                 grid_left, column_width, y_at)

        self._footer(page, colours, blocks, unscheduled)

    def _window(self, blocks):
        if self.day_start is not None and self.day_end is not None:
            return _minutes(self.day_start), _minutes(self.day_end)
        earliest = None
        latest = None
        for item in blocks:
            if earliest is None or item["start"] < earliest:
                earliest = item["start"]
            if latest is None or item["end"] > latest:
                latest = item["end"]
        if earliest is None:
            return 8 * 60, 18 * 60
        if self.day_start is not None:
            earliest = _minutes(self.day_start)
        else:
            earliest = (earliest // 60) * 60
        if self.day_end is not None:
            latest = _minutes(self.day_end)
        else:
            latest = ((latest + 59) // 60) * 60
        return earliest, latest

    def _draw_block(self, page, item, colours, day_index,
                    grid_left, column_width, y_at):
        fill, edge = colours[item["course"]]
        lanes = item.get("lanes", 1)
        lane = item.get("lane", 0)
        lane_width = (column_width - 5) / float(lanes)
        x = grid_left + column_width * day_index + 2.5 + lane_width * lane
        top_y = y_at(item["start"])
        bottom_y = y_at(item["end"])
        box_height = top_y - bottom_y

        page.setFillColor(fill)
        page.setStrokeColor(fill)
        page.roundRect(x, bottom_y + 1.2, lane_width - 1.5, box_height - 2.4,
                       2.5, stroke=0, fill=1)
        page.setFillColor(edge)
        page.rect(x, bottom_y + 1.2, 2.6, box_height - 2.4, stroke=0, fill=1)

        text_x = x + 6.5
        text_y = top_y - 11
        times = "%s-%s" % (_clock(item["start"]), _clock(item["end"]))

        page.setFillColor(INK)
        page.setFont(BOLD, 8.5)
        page.drawString(text_x, text_y, item["course"])
        if box_height >= 38:
            page.setFillColor(INK_SOFT)
            page.setFont(REGULAR, 7)
            page.drawString(text_x, text_y - 9, times)
            page.setFillColor(INK_FAINT)
            page.setFont(REGULAR, 6.5)
            page.drawString(text_x, text_y - 18, item["kind"])
            page.drawString(text_x, text_y - 26.5, item["room"])
        elif box_height >= 26:
            page.setFillColor(INK_SOFT)
            page.setFont(REGULAR, 7)
            page.drawString(text_x, text_y - 9, times)
            page.setFillColor(INK_FAINT)
            page.setFont(REGULAR, 6.5)
            page.drawString(text_x, text_y - 18,
                            "%s · %s" % (item["kind"], item["room"]))
        else:
            page.setFillColor(INK_SOFT)
            page.setFont(REGULAR, 6.5)
            page.drawString(text_x, text_y - 8.5,
                            "%s · %s" % (times, item["room"]))

    def _footer(self, page, colours, blocks, unscheduled):
        titles = {}
        for item in blocks:
            if item["course"] not in titles:
                titles[item["course"]] = item["title"]

        y = MARGIN + 12
        if unscheduled:
            y = MARGIN + 12 + 10 * len(unscheduled)

        parts = []
        for course in colours:
            parts.append("%s %s" % (course, titles.get(course, "")))
        page.setFont(REGULAR, 7.5)
        page.setFillColor(INK_FAINT)
        page.drawString(MARGIN, y, "   |   ".join(parts))

        if unscheduled:
            page.setFont(BOLD, 7.5)
            page.setFillColor(INK_SOFT)
            page.drawString(MARGIN, y - 12, "No fixed meeting time:")
            page.setFont(REGULAR, 7.5)
            page.setFillColor(INK_FAINT)
            offset = y - 22
            for line in sorted(set(unscheduled)):
                page.drawString(MARGIN + 8, offset, line)
                offset -= 10


def _minutes(text):
    cleaned = str(text).replace(":", "")
    return int(cleaned[:2]) * 60 + int(cleaned[2:])
