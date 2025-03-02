# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "flask",
#     "pandas",
#     "pypdf",
#     "python-slugify",
# ]
# ///
import colorsys
import random
import re
import subprocess
import tempfile
from itertools import chain
from pathlib import Path

import pandas as pd
from flask import Flask, make_response, render_template, request
from pypdf import PdfReader
from slugify import slugify

COLUMNS = ["Day", "Name", "CFU", "Teacher", "Room", "Start", "End"]

DAYS = ("LUN", "MAR", "MER", "GIO", "VEN")

HOURS = [f"{h:02d}:00" for h in range(8, 19)]

CELL_TEXT_WIDTH = 3.5  # cm
CELL_TOTAL_WIDTH = CELL_TEXT_WIDTH + 0.5
COL_SEP = 2

ROW_SEP = 1.25 * 11 / len(HOURS)

TO_HTML_KWARGS = {
    "classes": ["table", "table-hover", "border", "border-primary"],
    "justify": "unset",
    "index": False,
}

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
\((?P<cfu>\d+)\s+cfu\) # credits
\s+-\s+
(?P<teacher>\w\.\s*[\w ']+)  # teacher
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

app = Flask(__name__)


def random_hex_color():
    while True:
        h, s, l = (
            random.random(),
            0.5 + random.random() / 2.0,
            0.4 + random.random() / 5.0,
        )
        r, g, b = [int(256 * i) for i in colorsys.hls_to_rgb(h, l, s)]
        yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
        if yiq < 128:
            # ensure text is readable
            break
    return f"#{r:02X}{g:02X}{b:02X}"


app.jinja_env.globals.update(random_hex_color=random_hex_color)


def load_calendar(path):
    pdf = PdfReader(path)
    if m := COURSE_RE.search(pdf.pages[0].extract_text()):
        course = m.groupdict()
    else:
        course = {"id": "???", "name": "???", "class": "???"}
    data = chain.from_iterable(TIMETABLE_ROW_RE.findall(p.extract_text()) for p in pdf.pages)
    return course, pd.DataFrame(data, columns=COLUMNS)  # type: ignore


def split_years(cal: pd.DataFrame):
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/choose_subjects", methods=["POST"])
def choose_subjects():
    subjects = {}

    cal_file = request.files["file"]
    if cal_file:
        _, rest = load_calendar(cal_file)
        year_chosen = int(request.form["year"])
        if year_chosen < 1:
            raise ValueError("Year must be at least 1")
        year = None
        for _ in range(year_chosen):
            year, rest = split_years(rest)
        assert year is not None
        for _, row in year.iterrows():
            subject = subjects.setdefault(row["Name"], [])
            subject.append(row.to_dict())
        subjects = [
            {"id": slugify(name), "name": name, "rows": rows} for name, rows in subjects.items()
        ]

    return render_template("choose_subjects.html", subjects=subjects)


# https://stackoverflow.com/a/49819417/13204109
def parse_multi_form(form):
    result = {}
    for full_key in form:
        value = form[full_key]

        key_path = []
        while full_key:
            if "[" in full_key:
                k, r = full_key.split("[", 1)
                key_path.append(k)
                assert r[0] != "]"
                full_key = r.replace("]", "", 1)
            else:
                key_path.append(full_key)
                break

        sub_data = result
        last_key = key_path.pop()
        for k in key_path:
            assert isinstance(sub_data, dict)
            sub_data = sub_data.setdefault(int(k) if k.isdigit() else k, {})
        assert isinstance(sub_data, dict)
        sub_data[last_key] = value

    return result


@app.route("/render_timetable", methods=["POST"])
def route_render_timetable():
    form_data = parse_multi_form(request.form)

    has_bg = False
    if bg_file := request.files["bg"]:
        bg_file.save("bg.png")
        has_bg = True

    cells = []
    for subject in form_data.values():
        name = subject.pop("name")
        color = subject.pop("color", "#000000")
        cells.extend(
            {
                "name": name.capitalize(),
                "room": f"{row['room'].replace(chr(10), ' ')}",
                "color": color.lstrip("#"),
                "text_color": "FFFFFF",
                "day": 2 + DAYS.index(row["day"]),
                "start": 2 + HOURS.index(row["start"].replace(":30", ":00")),
                "end": 2 + HOURS.index(row["end"].replace(":30", ":00")),
                "total_width": f"{CELL_TOTAL_WIDTH:.2}cm",
                "text_width": f"{CELL_TEXT_WIDTH:.2}cm",
                "half_start": row["start"].endswith(":30"),
                "half_end": row["end"].endswith(":30"),
            }
            for row in subject.values()
        )

    texsrc = render_template(
        "orario.tex",
        cells=cells,
        times=HOURS,
        col_sep=COL_SEP,
        row_sep=ROW_SEP,
        has_bg=has_bg,
        language="italian",
        name_fontsize=12,
        room_fontsize=8,
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        texfile = Path(tmpdir, "rendered_orario.tex")
        texfile.write_text(texsrc, encoding="utf-8")
        subprocess.run(
            [
                "latexmk",
                "-pdf",
                "-halt-on-error",
                texfile,
                f"-output-directory={tmpdir}",
            ],
            check=True,
        )
        pdf_data = Path(tmpdir, "rendered_orario.pdf").read_bytes()
    response = make_response(pdf_data)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "inline; filename=orario.pdf"
    return response


@app.route("/show_calendar", methods=["GET", "POST"])
def show_calendar():
    if request.method == "GET":
        return render_template("calendar_choose.html")

    cal_file = request.files["file"]
    course, cal = load_calendar(cal_file)
    year1, rest = split_years(cal)
    year2, rest = split_years(rest)
    year3, _ = split_years(rest)
    return render_template(
        "calendar_show.html",
        course=course,
        year1=year1.to_html(**TO_HTML_KWARGS),
        year2=year2.to_html(**TO_HTML_KWARGS),
        year3=year3.to_html(**TO_HTML_KWARGS),
        cal=cal.to_html(**TO_HTML_KWARGS),
    )


if __name__ == "__main__":
    app.run(debug=True)
