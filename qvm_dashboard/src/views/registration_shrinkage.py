"""The Shrinkage sub-view of the Pad-to-Via and Via-to-Pad tabs.

Layout, top to bottom: overview of every Build Up / Panel / Side with the Excel
download, one block per group (tiles, panel map, quadrant table, bars), and a
fold-out explaining the calculation.

All numbers come from ``src.registration_shrinkage`` and all figures from
``src.visuals.shrinkage``; this module only lays them out.
"""

import html
import logging
from io import BytesIO

import pandas as pd
import streamlit as st

from src.excel_export import write_shrinkage_excel
from src.registration_shrinkage import (
    GroupShrinkage,
    compute_shrinkage_by_group,
    shrinkage_config,
    summary_frame,
)
from src.views.base import full_width
from src.visuals.shrinkage import plot_quadrant_bars, plot_shrinkage_panel

logger = logging.getLogger(__name__)

_EXCEL_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
_QUADRANT_COLUMNS = [
    'Quadrant', 'Delta X (um)', 'Shrinkage X (ppm)', 'Delta Y (um)', 'Shrinkage Y (ppm)',
    'X Design (mm)', 'X Measured (mm)', 'Y Design (mm)', 'Y Measured (mm)', 'Status',
]
_EXPLANATION = """
**What is measured.** How much the panel changed size against its design.
Everything is *measured minus design*, so **negative = shrink**.

**The calculation** is the company workbook's. In each quadrant, with points
1 (top-left), 2 (bottom-left), 3 (bottom-right) and 4 (top-right):

- X1 = x4 − x1, X2 = x3 − x2, Y1 = y1 − y2, Y2 = y4 − y3
- quadrant shrinkage = average of (measured length − design length) over the two lengths
- panel shrinkage = average of the four quadrants

**The ten numbers.** X and Y for each of the four quadrants, and X and Y for the
panel. Each is given in µm (the change over one quadrant length) and in ppm
(that change divided by the design length).

**Uniformity.** *Quadrant range* is the largest minus the smallest quadrant.
A quadrant further than the alert limit from the panel value is listed.

**The design** is two numbers: the size of one quadrant in X and in Y, set in
the sidebar under *Shrinkage design size*. All four quadrants have that size.

**When no number is shown.** Either the file holds positions relative to each
site (no panel geometry), or the measured quadrant size is too far from the
design size to be shrinkage (wrong design size, or another product). In the
second case the measured quadrant sizes are still listed.

The **Documentation** tab explains every step with an example.
"""


@st.cache_data(max_entries=8, show_spinner='Building shrinkage workbook…')
def build_shrinkage_workbook(df: pd.DataFrame, settings: dict, meta: dict) -> tuple:
    """Render the shrinkage workbook to bytes. Returns ``(data, error_message)``.

    Cached for the same reason as the main export: the charts are rendered to
    PNG, and Streamlit reruns the script on every click.
    """
    buffer = BytesIO()
    error = None
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        try:
            write_shrinkage_excel(writer, df, settings, meta)
        except Exception as exc:
            logger.warning('Shrinkage export error: %s', exc, exc_info=True)
            error = str(exc)
            pd.DataFrame({'error': [error]}).to_excel(writer, sheet_name='Error', index=False)
    return buffer.getvalue(), error


def _cell(column: str, value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ''
    if isinstance(value, float):
        return f'{value:,.3f}' if '(mm)' in column else f'{value:,.1f}'
    return html.escape(str(value))  # file-derived text (Build Up, Panel) stays text


def _show(frame: pd.DataFrame, columns=None) -> None:
    """A table with the copper header of the app (styles.css: .qvm-table)."""
    if columns is not None:
        frame = frame[[c for c in columns if c in frame.columns]]
    head = ''.join(f'<th>{html.escape(str(c))}</th>' for c in frame.columns)
    body = ''.join(
        '<tr>' + ''.join(f'<td>{_cell(str(c), v)}</td>' for c, v in zip(frame.columns, row)) + '</tr>'
        for row in frame.itertuples(index=False, name=None))
    st.markdown(
        f'<div class="qvm-table-wrap"><table class="qvm-table"><thead><tr>{head}</tr></thead>'
        f'<tbody>{body}</tbody></table></div>', unsafe_allow_html=True)


def _chart(figure, key: str) -> None:
    # theme=None: keep the chart's own colours; Streamlit's theme would recolour the text.
    st.plotly_chart(figure, key=key, theme=None, **full_width(st.plotly_chart))


def _render_summary(groups: list) -> None:
    """The copper summary tiles, same look as the Statistical Summary of
    Quality Control. One panel in scope: its values. Several: their average,
    with the panel furthest from zero named."""
    reported = [g for g in groups if not g.result.full_panel.empty]
    if not reported:
        st.info('No shrinkage could be reported for this selection; the reason is given below.')
        return
    panels = pd.DataFrame([g.result.full_panel.iloc[0] for g in reported])
    ranges = pd.DataFrame([g.result.uniformity.iloc[0] for g in reported])
    alerts = sum(len(g.result.outliers) for g in reported)
    many = len(reported) > 1
    prefix = 'Mean ' if many else 'Panel '

    cells = st.columns(5)
    for cell, axis in zip(cells, ('X', 'Y')):
        cell.metric(f'{prefix}{axis}', f"{panels[f'Delta {axis} (um)'].mean():.1f} µm",
                    f"{panels[f'Shrinkage {axis} (ppm)'].mean():.1f} ppm", delta_color='off')
    cells[2].metric('X − Y', f"{panels['X-Y Offset (ppm)'].mean():.1f} ppm")
    cells[3].metric('Quadrant range X / Y',
                    f"{ranges['QTQ Range X (ppm)'].max():.0f} / "
                    f"{ranges['QTQ Range Y (ppm)'].max():.0f} ppm",
                    'largest of the panels' if many else None, delta_color='off')
    cells[4].metric('Alerts', str(alerts),
                    f'{alerts} quadrants' if alerts else '✓ Uniform',
                    delta_color='inverse' if alerts else 'off')

    note = 'Measured − design: negative = shrink, positive = grown.'
    if many:
        size = panels[['Shrinkage X (ppm)', 'Shrinkage Y (ppm)']].abs().max(axis=1)
        worst = reported[int(size.to_numpy().argmax())]
        note = (f'Average of {len(reported)} panels. Largest change: {worst.label} '
                f'({size.max():.0f} ppm). ' + note)
    if len(reported) < len(groups):
        note += f' {len(groups) - len(reported)} without a result, see the table.'
    st.caption(note)


def _render_group(group: GroupShrinkage, settings: dict, outlier_ppm: float, key: str,
                  tiles: bool = True) -> None:
    result = group.result
    for warning in result.warnings:
        st.warning(warning)
    if result.quadrant.empty:
        if result.lengths.empty:
            st.info('No shrinkage result for this scope.')
            return
        # Withheld because the design does not fit: the measured sizes still
        # show how the quadrants compare with each other.
        st.markdown('**Measured quadrant sizes**')
        _show(result.lengths)
        spread_x = (result.lengths['X Measured (mm)'].max()
                    - result.lengths['X Measured (mm)'].min()) * 1000
        spread_y = (result.lengths['Y Measured (mm)'].max()
                    - result.lengths['Y Measured (mm)'].min()) * 1000
        st.caption(f'Largest minus smallest quadrant: {spread_x:.0f} µm in X, '
                   f'{spread_y:.0f} µm in Y. This needs no design.')
        return

    if tiles:
        _render_group_tiles(group)
    st.caption(
        f"{result.method_label} · {group.process} · {group.point} centres · "
        f"design quadrant {group.lengths[0]:g} × {group.lengths[1]:g} mm · "
        f"measured − design (negative = shrink). µm is the change over one quadrant length.")
    _render_group_details(group, settings, outlier_ppm, key)


def _render_group_tiles(group: GroupShrinkage) -> None:
    result = group.result
    panel = result.full_panel.iloc[0]
    uniformity = result.uniformity.iloc[0]
    status = panel.get('Status')
    cells = st.columns(6 if status is not None else 5)
    cells[0].metric('Panel X', f"{panel['Delta X (um)']:.1f} µm",
                    f"{panel['Shrinkage X (ppm)']:.1f} ppm", delta_color='off')
    cells[1].metric('Panel Y', f"{panel['Delta Y (um)']:.1f} µm",
                    f"{panel['Shrinkage Y (ppm)']:.1f} ppm", delta_color='off')
    cells[2].metric('X − Y', f"{panel['X-Y Offset (ppm)']:.1f} ppm")
    cells[3].metric('Quadrant range X', f"{uniformity['QTQ Range X (ppm)']:.1f} ppm")
    cells[4].metric('Quadrant range Y', f"{uniformity['QTQ Range Y (ppm)']:.1f} ppm")
    if status is not None:
        cells[5].metric('Limit', str(status))


def _render_group_details(group: GroupShrinkage, settings: dict, outlier_ppm: float,
                          key: str) -> None:
    result = group.result
    height = settings.get('CHART_HEIGHTS', {}).get('quiver', 600)
    _chart(plot_shrinkage_panel(result, group.design, f'Shrinkage Map  ·  {group.label}',
                                height=height), f'{key}_map')

    st.markdown('**Quadrants**')
    _show(result.quadrant, _QUADRANT_COLUMNS)

    _chart(plot_quadrant_bars(result, 'Shrinkage per quadrant'), f'{key}_bars')

    st.markdown('**Uniformity**')
    if result.outliers.empty:
        st.success(f'No quadrant is more than {outlier_ppm:.0f} ppm from the panel average.')
    else:
        _show(result.outliers)


def render_registration_shrinkage(df: pd.DataFrame, settings: dict, *, key: str,
                                  meta: dict | None = None) -> None:
    """The whole Shrinkage sub-view for one file type.

    ``key`` keeps the widgets of the Pad-to-Via and Via-to-Pad tabs apart.
    """
    outlier_ppm = float(shrinkage_config(settings).get('outlier_ppm', 50.0))

    groups = compute_shrinkage_by_group(df, settings)
    st.subheader('📊 Shrinkage Summary')
    _render_summary(groups)
    st.markdown('---')

    left, right = st.columns([3, 1])
    with left:
        st.markdown('**Overview** — one line per Build Up, Panel and Side')
    with right:
        data, error = build_shrinkage_workbook(df, settings, meta or {})
        if error:
            st.warning(f'⚠️ Shrinkage export encountered an issue: {error}')
        st.download_button(
            label='📥 Shrinkage Excel', data=data, file_name=f'QVM_Shrinkage_{key.upper()}.xlsx',
            mime=_EXCEL_MIME, type='primary', key=f'{key}_shrinkage_download')
    _show(summary_frame(groups))
    st.markdown('---')

    # One panel in scope: its tiles are the summary above, so not drawn twice.
    single = len(groups) == 1

    for index, group in enumerate(groups):
        with st.expander(group.label, expanded=len(groups) <= 2):
            _render_group(group, settings, outlier_ppm, f'{key}_{index}', tiles=not single)

    with st.expander('ℹ️ How is this calculated?'):
        st.markdown(_EXPLANATION)
