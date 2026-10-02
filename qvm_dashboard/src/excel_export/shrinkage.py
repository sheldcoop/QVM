"""Registration shrinkage workbook (the Shrinkage tab's own export).

Sheets:
- ``Summary``           one line per Build Up / Panel / Side
- ``Quadrants``         quadrant values of every group
- ``Quadrant Sizes``    measured against design size (also for groups without a result)
- ``Charts``            the panel map and the quadrant bars per group
- ``Notes``             method, measured point, design notes and warnings
"""

import logging

import pandas as pd

from src.registration_shrinkage import (
    METHOD_LABEL,
    compute_shrinkage_by_group,
    shrinkage_config,
    summary_frame,
)
from src.visuals.shrinkage import plot_quadrant_bars, plot_shrinkage_panel

from ._shared import WarnFn, _fig_to_xl_image, _notify, _safe_text, _sanitize_frame, _write_chart_fallback

logger = logging.getLogger(__name__)

_CHART_WIDTH, _CHART_HEIGHT = 520, 380
_ROWS_PER_CHART = 21


def _stack(groups, pick) -> pd.DataFrame:
    """Concatenate one frame per group, each prefixed with the group's labels."""
    frames = []
    for group in groups:
        frame = pick(group)
        if frame is None or frame.empty:
            continue
        frame = frame.copy()
        for position, (name, value) in enumerate(group.group.items()):
            frame.insert(position, name, value)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _write(writer: pd.ExcelWriter, name: str, frame: pd.DataFrame, empty_note: str) -> None:
    if frame.empty:
        frame = pd.DataFrame({'info': [empty_note]})
    frame.to_excel(writer, sheet_name=name, index=False)


def write_shrinkage_excel(writer: pd.ExcelWriter, df: pd.DataFrame, settings: dict,
                          meta: dict | None = None, warn: WarnFn | None = None) -> None:
    """Write the registration shrinkage workbook for the rows in ``df`` (one file type)."""
    if df is None or df.empty:
        pd.DataFrame({'info': ['No data available for export scope.']}).to_excel(
            writer, sheet_name='Summary', index=False)
        return

    # Same guard as the main export: no text cell may become a formula.
    groups = compute_shrinkage_by_group(_sanitize_frame(df), settings)

    _write(writer, 'Summary', summary_frame(groups), 'No groups in scope.')
    _write(writer, 'Quadrants', _stack(groups, lambda g: g.result.quadrant),
           'No shrinkage result in scope.')
    _write(writer, 'Quadrant Sizes', _stack(groups, lambda g: g.result.lengths),
           'No quadrant sizes in scope.')

    charts = writer.book.create_sheet('Charts')
    row = 1
    for group in groups:
        if group.result.quadrant.empty:
            continue
        charts.cell(row=row, column=1, value=_safe_text(f'{group.process} | {group.label}'))
        for column, (name, figure) in zip(('A', 'J'), (
                ('Panel map', plot_shrinkage_panel(group.result, group.design, 'Shrinkage map',
                                                   height=_CHART_HEIGHT)),
                ('Quadrant bars', plot_quadrant_bars(group.result, 'Shrinkage per quadrant',
                                                     height=_CHART_HEIGHT)))):
            anchor = f'{column}{row + 1}'
            try:
                charts.add_image(_fig_to_xl_image(figure, _CHART_WIDTH, _CHART_HEIGHT), anchor)
            except Exception as exc:  # no Chrome / kaleido: keep the workbook, mark the chart
                logger.warning('Shrinkage chart "%s" could not be rendered: %s', name, exc)
                _notify(warn, f'Shrinkage chart "{name}" could not be rendered: {exc}')
                _write_chart_fallback(charts, anchor, name, exc)
        row += _ROWS_PER_CHART
    if row == 1:
        charts.cell(row=1, column=1, value='No shrinkage result in scope, so there are no charts.')

    notes = writer.book.create_sheet('Notes')
    lines = [
        'Registration shrinkage',
        f'Method: {METHOD_LABEL}, as in the company workbook: per quadrant the two X and two Y '
        f'lengths against design, panel = mean of the four quadrants.',
        'Sign: measured minus design, so negative = shrink.',
        'um = change over one quadrant length; ppm = that change divided by the design length.',
        f"Outlier alert: a quadrant more than {float(shrinkage_config(settings).get('outlier_ppm', 50)):.0f} "
        f"ppm from the panel average.",
    ]
    for key in ('project_name', 'part_number', 'lot_number', 'lot_name'):
        if (meta or {}).get(key):
            lines.append(f"{key.replace('_', ' ').title()}: {meta[key]}")
    for group in groups:
        lines.append('')
        lines.append(f'{group.process} | {group.label} | {group.point} centres')
        if group.design_note:
            lines.append(group.design_note)
        lines.extend(group.result.warnings)
    for index, line in enumerate(lines, start=1):
        notes.cell(row=index, column=1, value=_safe_text(line))
