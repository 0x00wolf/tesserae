"""
Shared test fixture: real 2026/2027 sections, captured from the live timetable.

The tests replace DalTimetable._request with a lookup into these rows, so
everything above the HTTP call -- parsing, caching, subject validation,
filtering, the search, the PDF -- runs for real. Only the network is faked.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daltimetable import DalTimetable

TERMS = [
    {"CODE": "202620", "DESCR": "(202620) 2025/2026 Winter", "SELECTED": "Y"},
    {"CODE": "202630", "DESCR": "(202630) 2025/2026 Summer", "SELECTED": "N"},
    {"CODE": "202700", "DESCR": "(202700) 2026/2027 Medicine/Dentistry", "SELECTED": "N"},
    {"CODE": "202710", "DESCR": "(202710) 2026/2027 Fall", "SELECTED": "N"},
    {"CODE": "202720", "DESCR": "(202720) 2026/2027 Winter", "SELECTED": "N"},
]

SUBJECTS = [
    ("ACSC", "Actuarial Science"),
    ("AQUA", "Aquaculture-Agricultural Camp"),
    ("ARCH", "Architecture"),
    ("BIOL", "Biology"),
    ("CSCI", "Computer Science"),
    ("MATH", "Mathematics"),
    ("NURS", "Nursing"),
    ("PHYC", "Physics & Atmospheric Science"),
]

# term, subject, number, title, crn, section, component, link,
# days, times, room, capacity, enrolled, seats
SECTIONS = [
    ("202710", "CSCI", "1109", "Practical Data Science", "10700", "01", "Lec", "B0",
     "MW", "1435-1555", "Studley SIR JAMES DUNN BUILDING 135", "60", "14", "46"),
    ("202710", "CSCI", "1109", "Practical Data Science", "10701", "B01", "Lab", "L0",
     "T", "1135-1255", "Studley GOLDBERG COMPUTER SCIENCE BLDG 134", "58", "14", "44"),
    ("202720", "CSCI", "1109", "Practical Data Science", "20659", "01", "Lec", "B0",
     "TR", "1005-1125", "Studley HENRY HICKS ACADEMIC ADMIN 212", "50", "39", "11"),
    ("202720", "CSCI", "1109", "Practical Data Science", "20660", "B01", "Lab", "L0",
     "M", "1335-1455", "Studley GOLDBERG COMPUTER SCIENCE BLDG 134", "50", "39", "11"),

    ("202710", "CSCI", "1315", "Discrete Math for CS", "10712", "01", "Lec", None,
     "TRF", "0835-0925", "Studley KENNETH C ROWE MANAGEMENT 1009", "80", "54", "26"),
    ("202720", "CSCI", "1315", "Discrete Math for CS", "20672", "01", "Lec", None,
     "MWF", "1235-1325", "Studley KENNETH C ROWE MANAGEMENT 1009", "80", "70", "10"),

    ("202710", "CSCI", "2115", "Theory of Computer Science", "10722", "01", "Lec", None,
     "TR", "1435-1555", "Studley GOLDBERG COMPUTER SCIENCE BLDG 127", "120", "99", "21"),
    ("202720", "CSCI", "2115", "Theory of Computer Science", "20682", "01", "Lec", "T0",
     "MW", "0835-0955", "Studley SIR JAMES DUNN BUILDING 101", "80", "27", "53"),
    ("202720", "CSCI", "2115", "Theory of Computer Science", "20683", "T01", "Tut", "L0",
     "R", "1735-1855", "Studley KENNETH C ROWE MANAGEMENT 1009", "80", "27", "53"),

    ("202710", "CSCI", "2122", "Systems Programming", "10725", "02", "Lec", "B0",
     "WF", "1135-1255", "Studley SIR JAMES DUNN BUILDING 135", "80", "67", "13"),
    ("202710", "CSCI", "2122", "Systems Programming", "10726", "B01", "Lab", "L0",
     "R", "1005-1125", "Consult Department", "80", "67", "13"),
    ("202720", "CSCI", "2122", "Systems Programming", "20684", "01", "Lec", "B0",
     "MW", "1135-1255", "Studley SIR JAMES DUNN BUILDING 101", "80", "60", "20"),
    ("202720", "CSCI", "2122", "Systems Programming", "20685", "B01", "Lab", "L0",
     "R", "1135-1255", "Studley SIR JAMES DUNN BUILDING 101", "80", "60", "20"),

    ("202710", "CSCI", "2134", "Software Development", "10727", "01", "Lec", "B0",
     "WF", "1435-1555", "Studley SIR JAMES DUNN BUILDING 101", "60", "51", "9"),
    ("202710", "CSCI", "2134", "Software Development", "10728", "02", "Lec", "B0",
     "TR", "1305-1425", "Studley SIR JAMES DUNN BUILDING 101", "60", "55", "5"),
    ("202710", "CSCI", "2134", "Software Development", "10729", "B01", "Lab", "L0",
     "M", "1605-1725", "Studley GOLDBERG COMPUTER SCIENCE BLDG 134", "60", "46", "14"),
    ("202710", "CSCI", "2134", "Software Development", "10731", "B03", "Lab", "L0",
     "M", "1435-1555", "Studley GOLDBERG COMPUTER SCIENCE BLDG 143", "60", "60", "0"),
    ("202720", "CSCI", "2134", "Software Development", "20686", "01", "Lec", "B0",
     "TR", "1605-1725", "Studley KENNETH C ROWE MANAGEMENT 1020", "90", "28", "62"),
    ("202720", "CSCI", "2134", "Software Development", "20687", "B01", "Lab", "L0",
     "F", "1305-1425", "Studley GOLDBERG COMPUTER SCIENCE BLDG 134", "45", "21", "24"),
    ("202720", "CSCI", "2134", "Software Development", "20688", "B02", "Lab", "L0",
     "F", "1305-1425", "Studley GOLDBERG COMPUTER SCIENCE BLDG 143", "45", "7", "38"),

    ("202710", "CSCI", "2141", "Intro to Database Systems", "10732", "01", "Lec", "B0",
     "TR", "0835-0955", "Studley CHEMISTRY 226", "90", "90", "0"),
    ("202710", "CSCI", "2141", "Intro to Database Systems", "10733", "B01", "Lab", "L0",
     "F", "1605-1725", "Studley GOLDBERG COMPUTER SCIENCE BLDG 127", "90", "90", "0"),
    ("202720", "CSCI", "2141", "Intro to Database Systems", "20689", "01", "Lec", "B0",
     "TR", "1305-1425", "Studley LSC-COMMON AREA C238", "75", "63", "12"),
    ("202720", "CSCI", "2141", "Intro to Database Systems", "20690", "02", "Lec", "B0",
     "MW", "1305-1425", "Studley SIR JAMES DUNN BUILDING 101", "75", "26", "49"),
    ("202720", "CSCI", "2141", "Intro to Database Systems", "20691", "B01", "Lab", "L0",
     "F", "0835-0955", "Studley CHEMISTRY 125", "150", "89", "61"),

    ("202710", "CSCI", "3151", "Foundations  of Machine Learn.", "10756", "01", "Lec", None,
     "MW", "0835-0955", "Studley SIR JAMES DUNN BUILDING 135", "80", "75", "5"),

    ("202710", "MATH", "2060", "Intro Probability & Statistics", "11880", "01", "Lec", "T0",
     "TR", "1005-1125", "Studley LSC-COMMON AREA C242", "39", "28", "11"),
    ("202710", "MATH", "2060", "Intro Probability & Statistics", "11881", "T01", "Tut", "L0",
     "T", "1435-1625", "Studley LSC-COMMON AREA C208", "11", "8", "3"),
    ("202710", "MATH", "2060", "Intro Probability & Statistics", "11882", "T02", "Tut", "L0",
     "F", "0835-1025", "Studley LSC-COMMON AREA C234", "11", "4", "7"),
    ("202710", "MATH", "2060", "Intro Probability & Statistics", "11883", "T03", "Tut", "L0",
     "M", "1435-1625", "Studley LSC-COMMON AREA C234", "11", "6", "5"),
    ("202710", "MATH", "2060", "Intro Probability & Statistics", "11884", "T04", "Tut", "L0",
     "M", "1135-1325", "Studley LSC-COMMON AREA C234", "11", "10", "1"),
    ("202720", "MATH", "2060", "Intro Probability & Statistics", "21858", "01", "Lec", "T0",
     "TR", "1305-1425", "Studley LSC-COMMON AREA C242", "27", "14", "13"),
    ("202720", "MATH", "2060", "Intro Probability & Statistics", "21859", "T01", "Tut", "L0",
     "M", "1235-1425", "Studley LSC-COMMON AREA C234", "11", "5", "6"),
    ("202720", "MATH", "2060", "Intro Probability & Statistics", "21860", "T02", "Tut", "L0",
     "M", "0835-1025", "Studley LSC-COMMON AREA C234", "11", "4", "7"),
    ("202720", "MATH", "2060", "Intro Probability & Statistics", "21861", "T03", "Tut", "L0",
     "W", "1235-1425", "Studley LSC-COMMON AREA C234", "11", "3", "8"),
    ("202720", "MATH", "2060", "Intro Probability & Statistics", "21862", "T04", "Tut", "L0",
     "W", "0835-1025", "Studley LSC-COMMON AREA C234", "11", "2", "9"),

    # No fixed meeting time.
    ("202710", "ACSC", "4950", "Honours Research Project", "10020", "01", "Lec", None,
     "", "C/D", "Consult Department", "10", "0", "10"),
]

DAY_COLUMN = {"U": "SUNDAYS", "M": "MONDAYS", "T": "TUESDAYS", "W": "WEDNESDAYS",
              "R": "THURSDAYS", "F": "FRIDAYS", "S": "SATURDAYS"}

TERM_DATES = {
    "202710": ("08-SEP-2026", "09-DEC-2026"),
    "202720": ("11-JAN-2027", "13-APR-2027"),
}


def _row(entry):
    (term, subject, number, title, crn, section, component, link,
     days, times, room, capacity, enrolled, seats) = entry
    start_date, end_date = TERM_DATES.get(term, ("08-SEP-2026", "09-DEC-2026"))
    row = {
        "TERM_CODE": term, "SUBJ_CODE": subject, "CRSE_NUMB": number,
        "CRSE_TITLE": title, "CRN": crn, "SEQ_NUMB": section,
        "SCHD_TYPE": component, "LINK_CONN": link,
        "CREDIT_HRS": 3 if component == "Lec" else 0,
        "START_DATE": start_date, "END_DATE": end_date,
        "TIMES": times, "LOCATIONS": room,
        "MAX_ENRL": capacity, "ENRL": enrolled, "SEATS": seats,
        "INSTRUCTORS": "Staff",
    }
    for letter, column in DAY_COLUMN.items():
        row[column] = letter if letter in days else None
    return row


# Sections whose shape the simple tuple form cannot express, copied verbatim.
EXOTIC = [
    # Two meeting patterns, different times and rooms.
    {
        "TERM_CODE": "202710", "SUBJ_CODE": "AQUA", "CRSE_NUMB": "4000",
        "CRSE_TITLE": "Finfish Production (A)", "CRN": "10075", "SEQ_NUMB": "01",
        "SCHD_TYPE": "Lec", "LINK_CONN": None, "CREDIT_HRS": 3,
        "START_DATE": "08-SEP-2026", "END_DATE": "09-DEC-2026",
        "SUNDAYS": "<br>", "MONDAYS": "<br>", "TUESDAYS": "T<br>",
        "WEDNESDAYS": "<br>W", "THURSDAYS": "<br>", "FRIDAYS": "<br>F",
        "SATURDAYS": "<br>",
        "TIMES": "1135-1225<br>1035-1125",
        "LOCATIONS": "Agricultural HALEY INSTITUTE 114<br>Agricultural HALEY INSTITUTE 111",
        "MAX_ENRL": "15", "ENRL": "3", "SEATS": "12", "INSTRUCTORS": "Duston J. ",
    },
    # Four patterns.
    {
        "TERM_CODE": "202710", "SUBJ_CODE": "ARCH", "CRSE_NUMB": "3207",
        "CRSE_TITLE": "Building Technology", "CRN": "10086", "SEQ_NUMB": "01",
        "SCHD_TYPE": "Lec", "LINK_CONN": None, "CREDIT_HRS": 3,
        "START_DATE": "08-SEP-2026", "END_DATE": "09-DEC-2026",
        "SUNDAYS": "<br><br><br>", "MONDAYS": "<br><br><br>",
        "TUESDAYS": "T<br>T<br>T<br>", "WEDNESDAYS": "<br><br><br>",
        "THURSDAYS": "<br><br><br>R", "FRIDAYS": "<br><br><br>",
        "SATURDAYS": "<br><br><br>",
        "TIMES": "1005-1255<br>1005-1255<br>1005-1255<br>1005-1125",
        "LOCATIONS": ("Sexton B BUILDING ADDITION B308<br>"
                      "Sexton RALPH M MEDJUCK BLDG 2107<br>"
                      "Sexton RALPH M MEDJUCK BLDG ADDITION 2135, 2135A, 2135B<br>"
                      "Sexton RALPH M MEDJUCK BLDG B015"),
        "MAX_ENRL": "80", "ENRL": "63", "SEATS": "17",
        "INSTRUCTORS": "Jannasch E. (P)<br>Lilley B. ",
    },
    # Date-range headers inside LOCATIONS.
    {
        "TERM_CODE": "202710", "SUBJ_CODE": "NURS", "CRSE_NUMB": "3730",
        "CRSE_TITLE": "Nurs in Context of Persist Ill", "CRN": "12354",
        "SEQ_NUMB": "01", "SCHD_TYPE": "Lec", "LINK_CONN": None, "CREDIT_HRS": 6,
        "START_DATE": "08-SEP-2026", "END_DATE": "09-DEC-2026",
        "SUNDAYS": "<br><br>", "MONDAYS": "<br><br>", "TUESDAYS": "<br>T<br>",
        "WEDNESDAYS": "<br><br>", "THURSDAYS": "<br><br>", "FRIDAYS": "<br><br>",
        "SATURDAYS": "<br><br>",
        "TIMES": "<br>1035-1325<br>",
        "LOCATIONS": ("     <b>*** 08-SEP-2026 - 08-SEP-2026 ***</b><br>"
                      "Studley STUDENT UNION BLDG C/D<br>"),
        "MAX_ENRL": "125", "ENRL": "116", "SEATS": "9",
        "INSTRUCTORS": "Curry K. (P)<br>McNamee C. ",
    },
]


def all_rows():
    rows = []
    for entry in SECTIONS:
        rows.append(_row(entry))
    for row in EXOTIC:
        rows.append(row)
    return rows


ROWS = all_rows()


def fake_request(self, domain, params, attempts=3):
    """Stand in for the network, answering from ROWS."""
    if domain.endswith("_terms"):
        return list(TERMS)
    if domain.endswith("_subjects"):
        out = []
        for index, (code, description) in enumerate(SUBJECTS):
            out.append({"CODE": code,
                        "DESCR": "(%s) %s" % (code, description),
                        "ROW_NUMBER": index + 1})
        return out
    if domain.endswith("academicTimetable"):
        term = params["terms"].rstrip(";")
        subject = params["subj_code"]
        found = []
        for row in ROWS:
            if row["TERM_CODE"] == term and row["SUBJ_CODE"] == subject:
                found.append(row)
        return found
    raise AssertionError("fixture has no answer for %s" % domain)


def timetable():
    """A DalTimetable that answers from the fixture instead of the network."""
    DalTimetable._request = fake_request
    return DalTimetable()
