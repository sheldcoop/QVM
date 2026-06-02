"""Tests for the Via-to-Pad bullseye scatter."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go


_SETTINGS = {
    'COLUMN_NAMES': {
        'x_distance': 'Shift (DX)',
        'y_distance': 'Shift (DY)',
        'ptv_distance': 'PtV Distance',
        'location': 'Location',
        'grid_id': 'Grid ID',
    },
    'CHART_COLORS': {
        'chart_background':        '#FFFFFF',
        'traffic_light_blue':      '#3498db',
        'traffic_light_dark_green':'#1e7e3a',
        'traffic_light_green':     '#2ecc71',
        'traffic_light_orange':    '#e67e22',
        'traffic_light_red':       '#e74c3c',
    },
    'VTP_REGISTRATION': {
        'ring_exceptional_um': 2.5,
        'ring_excellent_um':   5.0,
        'ring_good_um':        7.5,
        'ring_acceptable_um': 10.0,
    },
}


def _fixture_df() -> pd.DataFrame:
    """16-site dataset spanning all 5 traffic-light zones (σ ≈ 4 µm)."""
    np.random.seed(42)
    df = pd.DataFrame({
        'Location': [f'site_{i}' for i in range(16)],
        'Grid ID': (
            list(range(11, 15)) + list(range(21, 25)) +
            list(range(31, 35)) + list(range(41, 45))
        ),
        'Shift (DX)': np.random.normal(0, 0.004, 16),
        'Shift (DY)': np.random.normal(0, 0.004, 16),
    })
    df['PtV Distance'] = np.sqrt(df['Shift (DX)']**2 + df['Shift (DY)']**2)
    return df


def test_bullseye_draws_four_tolerance_rings():
    """Regression: 4 rings (exceptional/excellent/good/acceptable) are drawn."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(_fixture_df(), _SETTINGS)
    circles = [s for s in fig.layout.shapes if s.type == 'circle']
    assert len(circles) == 4, f'Expected 4 rings, got {len(circles)}'

    radii = sorted([abs(c.x1) for c in circles])
    assert radii == [2.5, 5.0, 7.5, 10.0]


def test_bullseye_axes_reach_past_outermost_ring():
    """Regression: axis must always show the outermost ring even with tight data."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    df = pd.DataFrame({
        'Location': ['a', 'b'],
        'Grid ID': [11, 12],
        'Shift (DX)': [0.001, -0.002],
        'Shift (DY)': [0.002, 0.001],
        'PtV Distance': [0.0022, 0.0022],
    })
    fig = plot_vtp_bullseye(df, _SETTINGS)
    xmax = fig.layout.xaxis.range[1]
    assert xmax >= 10.0, f'Axis must reach past ring_acceptable (10 µm); got {xmax}'


def test_bullseye_has_summary_and_legend_annotations():
    """Regression: summary stats + zone legend present for the Excel export."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(_fixture_df(), _SETTINGS)
    texts = [a.text for a in fig.layout.annotations]
    assert any('max SC' in t for t in texts), 'Missing summary stats annotation'
    # Zone legend uses ⬤ symbols and zone thresholds
    assert any('⬤' in t for t in texts), 'Missing zone legend annotation'


def test_bullseye_point_colors_match_dark_zone_palette():
    """Regression: point colours use the Catppuccin Mocha _DARK_ZONE palette."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye, _DARK_ZONE

    df = _fixture_df()
    fig = plot_vtp_bullseye(df, _SETTINGS)
    trace = next(t for t in fig.data if isinstance(t, go.Scatter))
    colors = list(trace.marker.color)
    sc_um = df['PtV Distance'].values * 1000

    expected = [
        (_DARK_ZONE['exceptional'] if v <= 2.5 else
         _DARK_ZONE['excellent']   if v <= 5.0 else
         _DARK_ZONE['good']        if v <= 7.5 else
         _DARK_ZONE['acceptable']  if v <= 10.0 else
         _DARK_ZONE['fail'])
        for v in sc_um
    ]
    assert colors == expected


def test_bullseye_renders_to_png():
    """End-to-end: figure must convert to PNG (path used by the Excel export)."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(_fixture_df(), _SETTINGS)
    png = fig.to_image(format='png', width=700, height=700, scale=2)
    assert len(png) > 1000
