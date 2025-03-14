import itertools
import json
import re

import pandas as pd
import pydantic
from slugify import slugify

from .configuration import CELLS_METADATA_KEY, COLUMNS, DAYS, HOURS
from .utilities import random_hex_color

COURSE_RE = re.compile(
    r"CORSO\s*(?P<id>\d+) \s*-\s* (?P<name>[\w\s]+) \s*-\s* CLASSE\s*(?P<class>[\w-]+)",
    re.VERBOSE | re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
TIMETABLE_ROW_RE = re.compile(
    r"""
(?P<day>LUN|MAR|MER|GIO|VEN)  # day of the week
\s+
(?:[ \w']+\sC\.I\.\s+-\s+Mod\.\s*(?:MODULO)?\s*)?  # integrated course name
(?P<name>[\w ',]+)  # name of the course
\s+
\((?:\d+)\s+cfu\) # credits
\s+-\s+
(?:\w\.\s*[\w ']+)  # teacher
\s+
(?P<room>
    aula\s+\w+\s+\(\w+\)\s+-\s+n\.\s*\w+
    |
    laboratorio\s+\w+\s+\(\w+\)\s+-\s+n\.\s*\w+
    |
    \w\d{3}\s+-\s+e\.\d+
)  # room
\s+
(?P<start>\d{2}:\d{2})  # start time
\s+-\s+
(?P<end>\d{2}:\d{2})  # end time
""",
    re.VERBOSE | re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def load_calendar(pdf):
    if m := COURSE_RE.search(pdf.pages[0].extract_text()):
        course = m.groupdict()
    else:
        course = {"id": "???", "name": "???", "class": "???"}
    data = itertools.chain.from_iterable(
        TIMETABLE_ROW_RE.findall(p.extract_text()) for p in pdf.pages
    )
    return course, pd.DataFrame(data, columns=COLUMNS)  # type: ignore


def _split_years(cal: pd.DataFrame):
    rows = cal.iterrows()
    _, first_row = next(rows)  # type: ignore
    last = first_row["Day"]
    for i, row in rows:
        if DAYS.index(row["Day"]) < DAYS.index(last):
            year, rest = cal.iloc[:i], cal.iloc[i:]
            rest = rest.reset_index(drop=True)
            return year, rest
        last = row["Day"]
    raise ValueError("No split found")


def years(cal: pd.DataFrame):
    while True:
        year, cal = _split_years(cal)
        yield year


class Cell(pydantic.BaseModel):
    name: str
    room: str
    color: str

    day_idx: int

    start_hour_idx: int
    end_hour_idx: int
    start_minute: int
    end_minute: int


def extract_subjects(year):
    subjects = {}
    for _, row in year.iterrows():
        subject = subjects.setdefault(row["Name"], [])
        subject.append(row.to_dict())
    return [
        {
            "id": slugify(name),
            "color": random_hex_color(),
            "name": name,
            "rows": rows,
        }
        for name, rows in subjects.items()
    ]


def extract_cells(pdf):
    if pdf.metadata and (cells := pdf.metadata.get(CELLS_METADATA_KEY)):
        return [Cell.model_validate(cell) for cell in json.loads(str(cells))]
    else:
        return None


def cells_to_subjects(cells):
    subjects = {}
    colors = {}
    for cell in cells:
        subjects.setdefault(cell.name, []).append(
            {
                "Day": DAYS[cell.day - 2],
                "Name": cell.name,
                "Start": f"{HOURS[cell.start_hour_idx - 2]}:{cell.start_minute}",
                "End": f"{HOURS[cell.end_hour_idx - 2]}:{cell.end_minute}",
                "Room": cell.room,
            }
        )
        colors.setdefault(cell.name, f"#{cell.color}")

    return [
        {
            "id": slugify(name),
            "color": colors.get(name, random_hex_color()),
            "name": name,
            "rows": rows,
        }
        for name, rows in subjects.items()
    ]


def form_to_cells(form_data):
    cells = []
    for subject in form_data.values():
        name = subject.pop("name")
        color = subject.pop("color", "#000000")
        cells.extend(
            Cell(
                name=name.capitalize(),
                room=f"{row['room'].replace(chr(10), ' ')}",
                color=color.lstrip("#"),
                day_idx=2 + DAYS.index(row["day"]),
                start_hour_idx=2 + HOURS.index(row["start"].replace(":30", ":00")),
                end_hour_idx=2 + HOURS.index(row["end"].replace(":30", ":00")),
                start_minute=int(row["start"][3:]),
                end_minute=int(row["end"][3:]),
            )
            for row in subject.values()
        )
    print(cells)
    return cells
