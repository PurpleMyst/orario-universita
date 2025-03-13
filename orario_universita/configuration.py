COLUMNS = ["Day", "Name", "Room", "Start", "End"]

DAYS = ("LUN", "MAR", "MER", "GIO", "VEN")

HOURS = [f"{h:02d}:00" for h in range(8, 19)]

CELL_TEXT_WIDTH = 3.5  # cm
CELL_TOTAL_WIDTH = CELL_TEXT_WIDTH + 0.5  # cm
CELL_TEXT_COLOR = "FFFFFF"

COL_SEP = 2  # cm
ROW_SEP = 1.25 * 11 / len(HOURS)  # cm

CELLS_METADATA_KEY = "/PurpleMyst_Cells"

TO_HTML_KWARGS = {
    "classes": ["table", "table-hover", "border", "border-primary"],
    "justify": "unset",
    "index": False,
}
