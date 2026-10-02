"""Registration shrinkage on screen — one renderer for every place that shows it.

Used by the Shrinkage tab (Analytics) and by the Quality Control view, so the
two can no longer drift apart. All numbers come from
``src.registration_shrinkage``; this module only lays them out.
"""

import pandas as pd
import streamlit as st

from src.registration_shrinkage import (
    METHOD_LABELS,
    METHOD_USES,
    GroupShrinkage,
    compute_shrinkage_by_group,
    default_method,
    shrinkage_config,
)
from src.visuals.shrinkage import plot_shrinkage_quiver
from src.views.base import full_width

_QUADRANT_COLUMNS = [
    'Quadrant', 'Delta X (um)', 'Shrinkage X (ppm)', 'Delta Y (um)', 'Shrinkage Y (ppm)',
    'X Design (mm)', 'X Measured (mm)', 'Y Design (mm)', 'Y Measured (mm)', 'Status',
]
_COMPARE_HELP = (
    "All three methods use the same points and the same design positions. "
    "They agree when the panel has only shrunk or grown evenly. They differ when "
    "the quadrants have moved against each other, when the panel sits rotated on "
    "the machine, or when one point is off. See SHRINKAGE_METHODS.md."
)


def _show(frame: pd.DataFrame, columns=None) -> None:
    if columns is not None:
        frame = frame[[c for c in columns if c in frame.columns]]
    st.dataframe(frame, width='stretch', hide_index=True)


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

    if not result.details.empty:
        st.markdown('**Fit**')
        _show(result.details)
        with st.expander('Residual per point'):
            _show(result.points.sort_values('Residual (um)', ascending=False))

    st.markdown('**Uniformity**')
    if result.outliers.empty:
        st.success(f'No quadrant is more than {outlier_ppm:.0f} ppm from the panel average.')
    else:
        _show(result.outliers)
    st.plotly_chart(
        plot_shrinkage_quiver(result, f'Quadrant vs panel average — {group.label}'),
        **full_width(st.plotly_chart), key=f'{key}_quiver')

    with st.expander('Compare the three methods'):
        _show(group.compare(settings))
        st.caption(_COMPARE_HELP)


def render_registration_shrinkage(df: pd.DataFrame, settings: dict, *, key: str,
                                  in_expanders: bool = False) -> None:
    """Method choice, then one block per Build Up / Panel / Side.

    ``key`` keeps the widgets of different screens apart; ``in_expanders``
    folds each group away (used where shrinkage is not the main content).
    """
    methods = list(METHOD_LABELS)
    method = st.radio(
        'Method', methods, index=methods.index(default_method(settings)),
        format_func=METHOD_LABELS.get, horizontal=True, key=f'{key}_shrinkage_method',
        help='Company (distance) is the company workbook calculation and the one written '
             'to the Excel report.')
    st.caption(f'{METHOD_LABELS[method]}: {METHOD_USES[method]}.')

    outlier_ppm = float(shrinkage_config(settings).get('outlier_ppm', 50.0))
    groups = compute_shrinkage_by_group(df, settings, method=method)
    for index, group in enumerate(groups):
        group_key = f'{key}_{index}'
        if in_expanders:
            with st.expander(group.label, expanded=False):
                _render_group(group, settings, outlier_ppm, group_key)
        else:
            st.markdown(f'**{group.label}**')
            _render_group(group, settings, outlier_ppm, group_key)
