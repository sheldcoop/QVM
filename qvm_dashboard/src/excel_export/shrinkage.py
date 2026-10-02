"""Registration shrinkage workbook (the Shrinkage tab's own export).

Sheets:
- ``Summary``           one line per Build Up / Panel / Side
- ``Quadrants``         quadrant values of every group
- ``Quadrant Sizes``    measured against design size (also for groups without a result)
- ``Calculation``       every step as live Excel formulas, from the positions to the panel value
- ``Charts``            the panel map and the quadrant bars per group
- ``Notes``             method, measured point, design notes and warnings
"""

import logging

import pandas as pd

from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from src.registration_shrinkage import (
    METHOD_LABEL,
    _design_map,
    _point_map,
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


_QUADRANTS = ('UL', 'LL', 'LR', 'UR')
_BOLD = Font(bold=True)
_HEAD = PatternFill('solid', start_color='B87333')            # copper, as in the app
_HEAD_FONT = Font(bold=True, color='FFFFFF')
_RESULT = PatternFill('solid', start_color='F6E3D0')
_EXPLAIN = (
    'How to read this sheet. Every number below the positions is an Excel formula: click a cell to see it.',
    'Points of a quadrant: 1 = top-left, 2 = bottom-left, 3 = bottom-right, 4 = top-right.',
    'X1 = x(4) - x(1), the top edge.  X2 = x(3) - x(2), the bottom edge.  X length = average of X1 and X2.',
    'Y1 = y(1) - y(2), the left edge.  Y2 = y(4) - y(3), the right edge.  Y length = average of Y1 and Y2.',
    'Delta (um) = (measured length - design length) x 1000.  This is how much one quadrant changed, in micrometres.',
    'ppm = (measured length / design length - 1) x 1,000,000.  The same change, relative to the length.',
    'Panel = average of the four quadrants.  X - Y = panel X ppm minus panel Y ppm.  '
    'Quadrant range = largest minus smallest quadrant ppm.',
    'Negative = shrink, positive = grown.',
)
_STEP_HEADERS = (
    'Quadrant',
    'X1 design', 'X2 design', 'X design (mm)', 'X1 measured', 'X2 measured', 'X measured (mm)',
    'Delta X (um)', 'Shrinkage X (ppm)',
    'Y1 design', 'Y2 design', 'Y design (mm)', 'Y1 measured', 'Y2 measured', 'Y measured (mm)',
    'Delta Y (um)', 'Shrinkage Y (ppm)',
)


def _header(sheet, row: int, titles) -> None:
    for column, title in enumerate(titles, start=1):
        cell = sheet.cell(row=row, column=column, value=title)
        cell.fill, cell.font = _HEAD, _HEAD_FONT


def _write_calculation(sheet, groups) -> None:
    """The company calculation as live formulas, one block per reported group.

    Only the positions are typed in as numbers; lengths, um, ppm, panel
    average, X - Y and range are formulas on them, so the user can follow and
    check every step. The app's own result is printed below for comparison.
    Formulas are built from cell addresses only, never from text of the file.
    """
    for row, line in enumerate(_EXPLAIN, start=1):
        sheet.cell(row=row, column=1, value=line)
    sheet.cell(row=1, column=1).font = _BOLD
    row = len(_EXPLAIN) + 2

    written = False
    for group in groups:
        if group.result.quadrant.empty or not group.design:
            continue
        design = _design_map(group.design)
        measured = _point_map(group.measured, *group.columns)
        quadrants = [q for q in _QUADRANTS
                     if all(f'{q}_{c}' in design and f'{q}_{c}' in measured for c in '1234')]
        if not quadrants:
            continue
        written = True

        sheet.cell(row=row, column=1,
                   value=_safe_text(f'{group.process} | {group.label} | {group.point} centres')).font = _BOLD
        row += 1
        sheet.cell(row=row, column=1, value='Step 1: positions (mm)').font = _BOLD
        row += 1
        _header(sheet, row, ('Point', 'Design X', 'Design Y', 'Measured X', 'Measured Y'))
        at = {}  # point name -> its row
        for quadrant in quadrants:
            for corner in '1234':
                row += 1
                name = f'{quadrant}_{corner}'
                at[name] = row
                values = (name, design[name]['x'], design[name]['y'],
                          measured[name]['x'], measured[name]['y'])
                for column, value in enumerate(values, start=1):
                    sheet.cell(row=row, column=column, value=value)

        row += 2
        sheet.cell(row=row, column=1, value='Step 2: lengths, change in um, change in ppm').font = _BOLD
        row += 1
        _header(sheet, row, _STEP_HEADERS)
        first = row + 1
        for quadrant in quadrants:
            row += 1
            p1, p2, p3, p4 = (at[f'{quadrant}_{c}'] for c in '1234')

            def lengths(x_column: str, y_column: str):
                return (f'={x_column}{p4}-{x_column}{p1}', f'={x_column}{p3}-{x_column}{p2}',
                        f'={y_column}{p1}-{y_column}{p2}', f'={y_column}{p4}-{y_column}{p3}')

            dx1, dx2, dy1, dy2 = lengths('B', 'C')
            mx1, mx2, my1, my2 = lengths('D', 'E')
            cells = (
                quadrant,
                dx1, dx2, f'=AVERAGE(B{row}:C{row})', mx1, mx2, f'=AVERAGE(E{row}:F{row})',
                f'=(G{row}-D{row})*1000', f'=(G{row}/D{row}-1)*1000000',
                dy1, dy2, f'=AVERAGE(J{row}:K{row})', my1, my2, f'=AVERAGE(M{row}:N{row})',
                f'=(O{row}-L{row})*1000', f'=(O{row}/L{row}-1)*1000000',
            )
            for column, value in enumerate(cells, start=1):
                sheet.cell(row=row, column=column, value=value)
        last = row

        row += 2
        sheet.cell(row=row, column=1, value='Step 3: panel').font = _BOLD
        row += 1
        _header(sheet, row, ('', 'Panel X (um)', 'Panel X (ppm)', 'Panel Y (um)', 'Panel Y (ppm)',
                             'X - Y (ppm)', 'Quadrant range X (ppm)', 'Quadrant range Y (ppm)'))
        row += 1
        formulas = ('From the formulas',
                    f'=AVERAGE(H{first}:H{last})', f'=AVERAGE(I{first}:I{last})',
                    f'=AVERAGE(P{first}:P{last})', f'=AVERAGE(Q{first}:Q{last})',
                    f'=C{row}-E{row}',
                    f'=MAX(I{first}:I{last})-MIN(I{first}:I{last})',
                    f'=MAX(Q{first}:Q{last})-MIN(Q{first}:Q{last})')
        for column, value in enumerate(formulas, start=1):
            sheet.cell(row=row, column=column, value=value).fill = _RESULT
        row += 1
        panel, uniformity = group.result.full_panel.iloc[0], group.result.uniformity.iloc[0]
        app = ('Shown in the app',
               panel['Delta X (um)'], panel['Shrinkage X (ppm)'],
               panel['Delta Y (um)'], panel['Shrinkage Y (ppm)'], panel['X-Y Offset (ppm)'],
               uniformity['QTQ Range X (ppm)'], uniformity['QTQ Range Y (ppm)'])
        for column, value in enumerate(app, start=1):
            sheet.cell(row=row, column=column,
                       value=value if isinstance(value, str) else float(value))
        row += 3

    if not written:
        sheet.cell(row=row, column=1, value='No shrinkage result in scope, so there is nothing to calculate.')
    for column in range(2, len(_STEP_HEADERS) + 1):
        sheet.column_dimensions[get_column_letter(column)].width = 18
        for cells in sheet.iter_rows(min_row=len(_EXPLAIN) + 2, min_col=column, max_col=column):
            cells[0].number_format = '0.000'
    sheet.column_dimensions['A'].width = 22


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

    _write_calculation(writer.book.create_sheet('Calculation'), groups)

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
