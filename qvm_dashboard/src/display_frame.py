"""The one place that turns a parsed measurement frame into a display table.

Both the on-screen Quality Control table and every Excel measurement sheet are
built here, so they cannot drift apart. (They previously had separate
implementations, and the drift between them is what left the Quality Control
statistics panel permanently empty.)

Pure — no Streamlit, no I/O.
"""

import pandas as pd

from src.utils import convert_to_microns

# Per-file provenance columns, shown ahead of the measurements.
META_COLUMNS = ['Build Up', 'Panel', 'Side']


def build_display_frame(df: pd.DataFrame, settings: dict, *,
                        is_via_to_pad: bool) -> pd.DataFrame:
    """Select, convert, label and sort the columns shown to the user.

    Steps, in order:

    1. Keep the provenance columns plus Grid ID, the two diameters, DX/DY, the
       registration distance, and the Annular Ring.
    2. Compute the Annular Ring if the caller's frame does not already carry it
       (parsed frames get it from :func:`src.utils.calculate_annular_ring`).
    3. Convert every measurement from mm to µm.
    4. Rename the distance column to its process-specific header — Via-to-Pad
       reports it as ``VtP Distance (SC)``, Pad-to-Via as ``PtV Distance``.
       The parser stores one value under one name; this is the only place that
       name becomes process-specific.
    5. Sort by Grid ID numerically, so a malformed ID sorts last instead of
       reordering the table.
    """
    col_names    = settings.get('COLUMN_NAMES', {})
    grid_id_col  = col_names.get('grid_id', 'Grid ID')
    via_diam_col = col_names.get('inner_diameter', 'Via Parameter')
    pad_diam_col = col_names.get('outer_diameter', 'Pad Diameter')
    dx_col       = col_names.get('x_distance', 'Shift (DX)')
    dy_col       = col_names.get('y_distance', 'Shift (DY)')
    distance_col = col_names.get('ptv_distance', 'PtV Distance')
    annular_col  = col_names.get('annular_ring', 'Annular Ring')

    work = df.copy()

    if annular_col not in work.columns:
        required = {pad_diam_col, via_diam_col, distance_col}
        if required.issubset(work.columns):
            work[annular_col] = ((work[pad_diam_col] / 2)
                                 - (work[via_diam_col] / 2)
                                 - work[distance_col])

    keep = META_COLUMNS + [grid_id_col, via_diam_col, pad_diam_col,
                           dx_col, dy_col, distance_col, annular_col]
    display_df = work[[c for c in keep if c in work.columns]].copy()

    display_df = convert_to_microns(
        display_df,
        [pad_diam_col, via_diam_col, distance_col, dx_col, dy_col, annular_col],
    )

    if is_via_to_pad:
        display_df = display_df.rename(
            columns={distance_col: col_names.get('total_shift', 'VtP Distance (SC)')})

    if grid_id_col in display_df.columns:
        sort_key = pd.to_numeric(display_df[grid_id_col], errors='coerce')
        display_df = display_df.assign(_grid_sort_key=sort_key).sort_values(
            by=['_grid_sort_key', grid_id_col], ascending=True, na_position='last',
        ).drop(columns=['_grid_sort_key'])

    return display_df
