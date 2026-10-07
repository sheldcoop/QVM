"""Export == display: the workbook measurement sheets must carry exactly the
table the Quality Control view shows.

Both go through ``src.display_frame.build_display_frame`` by construction;
these tests pin the equality end to end (through the real .xlsx bytes) so a
future exporter shortcut cannot silently diverge from the screen.
"""

from io import BytesIO

import pandas as pd
from pandas.testing import assert_series_equal


def _assert_same_cells(got: pd.DataFrame, expected: pd.DataFrame):
    """Cell-wise equality across an .xlsx round-trip.

    Excel coerces all-digit text ("25") back to int and whole floats
    (20.0) to int on read, while doubles are otherwise exact. Numeric
    columns therefore compare as floats, everything else as strings.
    """
    assert list(got.columns) == list(expected.columns)
    assert len(got) == len(expected)
    for col in expected.columns:
        if pd.api.types.is_numeric_dtype(expected[col]):
            assert_series_equal(
                got[col].astype(float).reset_index(drop=True),
                expected[col].astype(float).reset_index(drop=True),
                check_names=False,
            )
        else:
            assert_series_equal(
                got[col].astype(str).reset_index(drop=True),
                expected[col].astype(str).reset_index(drop=True),
                check_names=False,
            )


def _frame(process, settings):
    cn = settings["COLUMN_NAMES"]
    rows = []
    for i in range(4):
        rows.append(
            {
                cn["grid_id"]: 11 + i,
                cn["location"]: f"UL{i + 1}",
                cn["inner_diameter"]: 0.02,
                cn["outer_diameter"]: 0.3125,
                cn["coord_x"]: 100.0 + i,
                cn["coord_y"]: 200.0 + i,
                cn["x_distance"]: 0.001 * (i + 1),
                cn["y_distance"]: -0.001 * (i + 1),
                cn["ptv_distance"]: 0.002 * (i + 1),
                "Process": process,
                "Panel": "25",
                "Side": "F",
                "Build Up": "BU-01",
            }
        )
    return pd.DataFrame(rows)


def _sheet_df(buf, sheet):
    buf.seek(0)
    return pd.read_excel(buf, sheet_name=sheet)


def test_vtp_sheet_equals_display_frame(settings):
    from src.display_frame import build_display_frame
    from src.excel_export import write_unified_excel

    df = _frame("Via to Pad", settings)
    expected = build_display_frame(df, settings, is_via_to_pad=True)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        write_unified_excel(w, df.copy(), settings, {"panel": "25"})
    got = _sheet_df(buf, "Via to Pad")
    _assert_same_cells(got, expected)


def test_ptv_sheet_equals_display_frame(settings):
    from src.display_frame import build_display_frame
    from src.excel_export import write_unified_excel

    df = _frame("Pad to Via", settings)
    expected = build_display_frame(df, settings, is_via_to_pad=False)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        write_unified_excel(w, df.copy(), settings, {"panel": "25"})
    got = _sheet_df(buf, "Pad to Via")
    _assert_same_cells(got, expected)
