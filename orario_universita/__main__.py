import io
import json
import subprocess
import tempfile
from contextlib import chdir
from pathlib import Path
from uuid import uuid4

from flask import Flask, make_response, render_template, request
from PIL import Image
from pypdf import PdfReader, PdfWriter

from .calendar_parsing import (
    Cell,
    cells_to_subjects,
    extract_cells,
    extract_subjects,
    form_to_cells,
    load_calendar,
    years,
)
from .configuration import (
    CELL_TEXT_WIDTH,
    CELL_TOTAL_WIDTH,
    CELLS_METADATA_KEY,
    COL_SEP,
    HOURS,
    ROW_SEP,
    TO_HTML_KWARGS,
)
from .utilities import iterator_index, parse_multi_form

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/choose_subjects", methods=["POST"])
def choose_subjects():
    cal_file = request.files["file"]
    if cal_file:
        pdf = PdfReader(cal_file)  # type: ignore
        if cells := extract_cells(pdf):
            subjects = cells_to_subjects(cells)
        else:
            _, calendar = load_calendar(pdf)
            year_chosen = int(request.form["year"])
            if year_chosen < 1:
                raise ValueError("Year must be at least 1")
            year = iterator_index(years(calendar), year_chosen - 1)
            subjects = extract_subjects(year)
    else:
        subjects = {}

    return render_template("choose_subjects.html", subjects=subjects)


def do_render_timetable(tmpdir: str, cells: list[Cell], bg: str | None):
    texsrc = render_template(
        "orario.tex",
        cells=[cell.model_dump() for cell in cells],
        bg=bg,
        times=HOURS,
        col_sep=COL_SEP,
        row_sep=ROW_SEP,
        first_col_sep="-5mm",
        language="italian",
        name_fontsize=12,
        room_fontsize=8,
        cell_text_color="FFFFFF",
        cell_total_width=f"{CELL_TOTAL_WIDTH:.2}cm",
        cell_text_width=f"{CELL_TEXT_WIDTH:.2}cm",
    )

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

    writer = PdfWriter(clone_from=Path(tmpdir, "rendered_orario.pdf"))
    writer.add_metadata({CELLS_METADATA_KEY: json.dumps([cell.model_dump() for cell in cells])})

    data_buf = io.BytesIO()
    writer.write(data_buf)
    response = make_response(data_buf.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"inline; filename=orario.pdf"
    return response


@app.route("/render_timetable", methods=["POST"])
def route_render_timetable():
    form_data = parse_multi_form(request.form)

    with tempfile.TemporaryDirectory() as tmpdir, chdir(tmpdir):
        cells = form_to_cells(form_data)

        if bg_file := request.files["bg"]:
            bg_file_dest = Path(tmpdir, f"{uuid4()}.png")
            Image.open(bg_file).save(bg_file_dest, "png")  # type: ignore
            bg_file_dest = bg_file_dest.name
        else:
            bg_file_dest = None

        return do_render_timetable(tmpdir, cells, bg_file_dest)


@app.route("/show_calendar", methods=["GET", "POST"])
def show_calendar():
    if request.method == "GET":
        return render_template("calendar_choose.html")

    cal_file = request.files["file"]
    course, calendar = load_calendar(cal_file)
    [year1, year2, year3] = years(calendar)
    return render_template(
        "calendar_show.html",
        course=course,
        year1=year1.to_html(**TO_HTML_KWARGS),
        year2=year2.to_html(**TO_HTML_KWARGS),
        year3=year3.to_html(**TO_HTML_KWARGS),
        cal=calendar.to_html(**TO_HTML_KWARGS),
    )


if __name__ == "__main__":
    app.run(debug=True)
