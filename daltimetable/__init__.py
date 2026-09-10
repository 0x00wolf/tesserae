"""
daltimetable -- read Dalhousie's timetable and build schedules from it.

    from daltimetable import DalTimetable, SchedulePlanner, Elective, Commitment

The PDF renderer is deliberately not imported here, so nothing pulls in
reportlab unless you ask for it:

    from daltimetable.pdf import TimetablePDF

See docs/MODULES.md.
"""

from .timetable import (
    CAMPUSES,
    DalTimetable,
    Meeting,
    NotFound,
    Section,
    SectionSet,
    TimetableError,
    UnknownSubject,
    normalize_course,
    split_course,
    tidy_room,
)
from .planner import (
    Commitment,
    CourseChoice,
    Elective,
    PlannerError,
    Schedule,
    SchedulePlanner,
    meetings_overlap,
)

__all__ = [
    "CAMPUSES",
    "Commitment",
    "CourseChoice",
    "DalTimetable",
    "Elective",
    "Meeting",
    "NotFound",
    "PlannerError",
    "Schedule",
    "SchedulePlanner",
    "Section",
    "SectionSet",
    "TimetableError",
    "UnknownSubject",
    "meetings_overlap",
    "normalize_course",
    "split_course",
    "tidy_room",
]
