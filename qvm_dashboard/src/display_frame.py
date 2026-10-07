"""The one place that turns a parsed measurement frame into a display table.

Both the on-screen Quality Control table and every Excel measurement sheet are
built here, so they cannot drift apart. (They previously had separate
implementations, and the drift between them is what left the Quality Control
statistics panel permanently empty.)

Pure — no Streamlit, no I/O.
"""

import pandas as pd

from src.utils import calculate_annular_ring, convert_to_microns, resolve_columns

# Per-file provenance columns, shown ahead of the measurements.
META_COLUMNS = ["Build Up", "Panel", "Side"]

# The Grid ID header users see, on screen and in every Excel sheet. Applying it
# here rather than in the Excel writer keeps every header decision in one place.
GRID_ID_HEADER = "Grid ID"

_COLUMN_KEYS = (
    "grid_id",
    "inner_diameter",
    "outer_diameter",
    "x_distance",
    "y_distance",
    "ptv_distance",
    "annular_ring",
    "total_shift",
)


def build_display_frame(
    df: pd.DataFrame, settings: dict, *, is_via_to_pad: bool
) -> pd.DataFrame:
    """Select, convert, label and sort the columns shown to the user.

    Steps, in order:

    1. Keep the provenance columns plus Grid ID, the two diameters, DX/DY, the
       registration distance, and the Annular Ring.
    2. Compute the Annular Ring if the caller's frame does not already carry it.
       Parsed frames get it on the ingest path, so this only fires for frames
       assembled directly (tests, and any future caller that skips ingestion).
    3. Convert every measurement from mm to µm.
    4. Apply the display headers: the distance column takes its process-specific
       name — Via-to-Pad reports it as ``VtP Distance (SC)``, Pad-to-Via as
       ``PtV Distance`` — and Grid ID takes ``GRID_ID_HEADER``. The parser
       stores one distance value under one name; this is the only place any
       header becomes process- or presentation-specific.
    5. Sort by Grid ID numerically, so a malformed ID sorts last instead of
       reordering the table.
    """
    cols = resolve_columns(settings, _COLUMN_KEYS)
    grid_id_col = cols["grid_id"]
    distance_col = cols["ptv_distance"]
    annular_col = cols["annular_ring"]

    work = df
    if annular_col not in work.columns:
        required = {cols["outer_diameter"], cols["inner_diameter"], distance_col}
        if required.issubset(work.columns):
            work = calculate_annular_ring(df.copy(), settings)

    keep = META_COLUMNS + [
        grid_id_col,
        cols["inner_diameter"],
        cols["outer_diameter"],
        cols["x_distance"],
        cols["y_distance"],
        distance_col,
        annular_col,
    ]
    display_df = work[[c for c in keep if c in work.columns]].copy()

    display_df = convert_to_microns(
        display_df,
        [
            cols["outer_diameter"],
            cols["inner_diameter"],
            distance_col,
            cols["x_distance"],
            cols["y_distance"],
            annular_col,
        ],
    )

    renames = {}
    if is_via_to_pad:
        renames[distance_col] = cols["total_shift"]
    if grid_id_col != GRID_ID_HEADER:
        renames[grid_id_col] = GRID_ID_HEADER
    if renames:
        display_df = display_df.rename(columns=renames)
        grid_id_col = renames.get(grid_id_col, grid_id_col)

    sort_cols = []

    if "Build Up" in display_df.columns:
        bu_text = display_df["Build Up"].astype(str).str.strip()
        bu_num = pd.to_numeric(bu_text.str.extract(r"(\d+)")[0], errors="coerce")
        display_df["_sort_bu_missing"] = bu_num.isna()
        display_df["_sort_bu_num"] = bu_num
        display_df["_sort_bu_text"] = bu_text.str.upper()
        sort_cols.extend(["_sort_bu_missing", "_sort_bu_num", "_sort_bu_text"])

    if "Side" in display_df.columns:
        side_text = display_df["Side"].astype(str).str.strip().str.upper()
        display_df["_sort_side_rank"] = side_text.map(
            {"F": 0, "FRONT": 0, "B": 1, "BACK": 1}
        ).fillna(2)
        display_df["_sort_side_text"] = side_text
        sort_cols.extend(["_sort_side_rank", "_sort_side_text"])

    if grid_id_col in display_df.columns:
        display_df["_sort_grid"] = pd.to_numeric(
            display_df[grid_id_col], errors="coerce"
        )
        sort_cols.append("_sort_grid")

    if sort_cols:
        display_df = display_df.sort_values(
            by=sort_cols, na_position="last", kind="mergesort"
        )
        drop_cols = [c for c in sort_cols if c.startswith("_sort_")]
        display_df = display_df.drop(columns=drop_cols)

    return display_df
