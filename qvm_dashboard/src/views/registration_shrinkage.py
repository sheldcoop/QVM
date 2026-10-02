"""The Shrinkage sub-view of the Pad-to-Via and Via-to-Pad tabs.

Layout, top to bottom: overview of every Build Up / Panel / Side with the Excel
download, method choice, one block per group (tiles, quadrant table, charts,
method comparison), and a fold-out explaining the calculation.

All numbers come from ``src.registration_shrinkage`` and all figures from
``src.visuals.shrinkage``; this module only lays them out.
"""

import logging
from io import BytesIO

import pandas as pd
import streamlit as st

from src.excel_export import write_shrinkage_excel
from src.registration_shrinkage import (
    METHOD_AFFINE,
    METHOD_LABELS,
    METHOD_USES,
    GroupShrinkage,
    compute_shrinkage_by_group,
    default_method,
    shrinkage_config,
    summary_frame,
)
from src.views.base import full_width
from src.visuals.shrinkage import plot_fit_residuals, plot_quadrant_bars, plot_shrinkage_quiver

logger = logging.getLogger(__name__)

_EXCEL_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
_QUADRANT_COLUMNS = [
    'Quadrant', 'Delta X (um)', 'Shrinkage X (ppm)', 'Delta Y (um)', 'Shrinkage Y (ppm)',
    'X Design (mm)', 'X Measured (mm)', 'Y Design (mm)', 'Y Measured (mm)', 'Status',
]
_COMPARE_HELP = (
    "All three methods use the same points and the same design positions. "
    "They agree when the panel has only shrunk or grown evenly. They differ when "
    "the quadrants have moved against each other, when the panel sits rotated on "
    "the machine, or when one point is off."
)
_EXPLANATION = """
**What is measured.** How much the panel changed size against its design.
Everything is *measured minus design*, so **negative = shrink**. µm is the change
over one quadrant length; ppm is that change divided by the design length.

**Company (distance).** In each quadrant, with points 1 (top-left), 2 (bottom-left),
3 (bottom-right) and 4 (top-right):

- X1 = x4 − x1, X2 = x3 − x2, Y1 = y1 − y2, Y2 = y4 − y3
- quadrant shrinkage = average of (measured length − design length) over the two lengths
- panel shrinkage = average of the four quadrants

This is the company workbook calculation and the one written to the Excel report.

**Centre-based.** The centre does not have to be known: the average of the points
*is* the centre. Example with four points along one edge:

| | Point 1 | Point 2 | Point 3 | Point 4 | Average |
|---|---|---|---|---|---|
| Design | 20 | 280 | 300 | 560 | 290 |
| From the centre | −270 | −10 | +10 | +270 | 0 |

The measured points are treated the same way, and the scale is the slope of
"measured from centre" against "design from centre". Inside one quadrant this
gives the same number as the company method. For the whole panel it also uses
the distance *between* quadrants, which the company method never looks at.

**Affine fit.** Fits shift, rotation, X scale, Y scale and shear to all points at
once (the Core Shrinkage calculation). A rotated panel is not mistaken for a
shrunk one, and a point far off the fit is named and left out.

**Reading the comparison.**

- All three agree → the company number can be trusted.
- Company differs from the other two → the quadrants moved against each other.
- Affine differs from the other two → the panel lay rotated, or a point is off.

**When no number is shown.** Either the file holds positions relative to each
site (no panel geometry), or the measured quadrant size is too far from the
design to be shrinkage (design of another product). The measured quadrant sizes
are still listed in the second case.
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


def _show(frame: pd.DataFrame, columns=None) -> None:
    if columns is not None:
        frame = frame[[c for c in columns if c in frame.columns]]
    st.dataframe(frame, width='stretch', hide_index=True)


def _chart(figure, key: str) -> None:
    st.plotly_chart(figure, key=key, **full_width(st.plotly_chart))


def _render_group(group: GroupShrinkage, settings: dict, outlier_ppm: float, key: str) -> None:
    result = group.result
    if group.design_note:
        st.info(group.design_note)
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
    st.caption(
        f"{result.method_label} · {group.process} · {group.point} centres · "
        f"measured − design (negative = shrink). µm is the change over one quadrant length.")

    st.markdown('**Quadrants**')
    _show(result.quadrant, _QUADRANT_COLUMNS)

    left, right = st.columns(2)
    with left:
        _chart(plot_quadrant_bars(result, 'Shrinkage per quadrant'), f'{key}_bars')
    with right:
        _chart(plot_shrinkage_quiver(result, 'Quadrant vs panel average'), f'{key}_quiver')

    if result.method == METHOD_AFFINE and not result.details.empty:
        st.markdown('**Fit**')
        _show(result.details)
        _chart(plot_fit_residuals(result, group.design, 'Distance of each point from the fit'),
               f'{key}_residuals')
        with st.expander('Residual per point'):
            _show(result.points.sort_values('Residual (um)', ascending=False))

    st.markdown('**Uniformity**')
    if result.outliers.empty:
        st.success(f'No quadrant is more than {outlier_ppm:.0f} ppm from the panel average.')
    else:
        _show(result.outliers)

    with st.expander('Compare the three methods'):
        _show(group.compare(settings))
        st.caption(_COMPARE_HELP)


def render_registration_shrinkage(df: pd.DataFrame, settings: dict, *, key: str,
                                  meta: dict | None = None) -> None:
    """The whole Shrinkage sub-view for one file type.

    ``key`` keeps the widgets of the Pad-to-Via and Via-to-Pad tabs apart.
    """
    st.subheader('📐 Shrinkage')
    outlier_ppm = float(shrinkage_config(settings).get('outlier_ppm', 50.0))

    # Overview and export always use the report method, like the workbook.
    report_groups = compute_shrinkage_by_group(df, settings)
    report_label = METHOD_LABELS[default_method(settings)]
    left, right = st.columns([3, 1])
    with left:
        st.markdown(f'**Overview** — {report_label}, one line per Build Up, Panel and Side')
    with right:
        data, error = build_shrinkage_workbook(df, settings, meta or {})
        if error:
            st.warning(f'⚠️ Shrinkage export encountered an issue: {error}')
        st.download_button(
            label='📥 Shrinkage Excel', data=data, file_name=f'QVM_Shrinkage_{key.upper()}.xlsx',
            mime=_EXCEL_MIME, type='primary', key=f'{key}_shrinkage_download')
    _show(summary_frame(report_groups))
    st.markdown('---')

    methods = list(METHOD_LABELS)
    method = st.radio(
        'Method for the details below', methods, index=methods.index(default_method(settings)),
        format_func=METHOD_LABELS.get, horizontal=True, key=f'{key}_shrinkage_method',
        help='Company (distance) is the company workbook calculation and the one written '
             'to the Excel report.')
    st.caption(f'{METHOD_LABELS[method]}: {METHOD_USES[method]}.')

    groups = (report_groups if method == default_method(settings)
              else compute_shrinkage_by_group(df, settings, method=method))
    for index, group in enumerate(groups):
        with st.expander(group.label, expanded=len(groups) <= 2):
            _render_group(group, settings, outlier_ppm, f'{key}_{index}')

    with st.expander('ℹ️ How is this calculated?'):
        st.markdown(_EXPLANATION)
