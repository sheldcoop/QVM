"""Tests for the Via-to-Pad bullseye scatter (regression on S2/S3 work)."""

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
        'chart_background': '#FFFFFF',
        'traffic_light_green': '#2ecc71',
        'traffic_light_orange': '#f39c12',
        'traffic_light_red': '#e74c3c',
    },
    'VTP_REGISTRATION': {
        'ring_green_um': 10.0,
        'ring_orange_um': 15.0,
        'bullseye_axis_half_um': 15.0,
    },
}


def _fixture_df() -> pd.DataFrame:
    """16-site dataset designed to land points in all three traffic-light bands.

    With ring_green=10 and ring_orange=15, shifts on the order of ±6 µm produce
    a healthy mix of green/orange/red points for the color test.
    """
    np.random.seed(42)
    df = pd.DataFrame({
        'Location': [f'site_{i}' for i in range(16)],
        'Grid ID': list(range(11, 15)) + list(range(21, 25)) + list(range(31, 35)) + list(range(41, 45)),
        'Shift (DX)': np.random.normal(0, 0.006, 16),
        'Shift (DY)': np.random.normal(0, 0.006, 16),
    })
    df['PtV Distance'] = np.sqrt(df['Shift (DX)']**2 + df['Shift (DY)']**2)
    return df


def test_bullseye_draws_two_tolerance_rings():
    """S2.1 regression: green and orange rings must appear on the scatter."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(_fixture_df(), _SETTINGS)
    circles = [s for s in fig.layout.shapes if s.type == 'circle']
    assert len(circles) == 2

    # Rings are centred at origin and span ±ring_um.
    radii = sorted([abs(c.x1) for c in circles])
    assert radii == [10.0, 15.0]


def test_bullseye_axes_use_fixed_half_width_from_settings():
    """S2.3 regression: axis range honours bullseye_axis_half_um regardless of data spread."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    # Tight data — should still produce a ±15 µm viewport because that's the configured half-width.
    df = pd.DataFrame({
        'Location': ['a', 'b'],
        'Grid ID': [11, 12],
        'Shift (DX)': [0.001, -0.002],
        'Shift (DY)': [0.002, 0.001],
        'PtV Distance': [0.0022, 0.0022],
    })
    fig = plot_vtp_bullseye(df, _SETTINGS)
    xmin, xmax = fig.layout.xaxis.range
    assert xmin == -15.0 and xmax == 15.0, f'Expected ±15 µm axis, got [{xmin}, {xmax}]'


def test_bullseye_has_summary_and_legend_annotations():
    """S3.1 regression: corner stats + ring legend must be present (PNG self-describing)."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(_fixture_df(), _SETTINGS)
    texts = [a.text for a in fig.layout.annotations]
    assert any('max SC' in t for t in texts), 'Missing summary stats annotation'
    assert any('pass' in t and 'warn' in t for t in texts), 'Missing ring legend'


def test_bullseye_point_colors_match_traffic_light_bands():
    """S2.2 regression: point colors must match the bar-chart traffic-light palette."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye, _traffic_light_color

    df = _fixture_df()
    fig = plot_vtp_bullseye(df, _SETTINGS)
    # The Scatter trace's marker.color is the per-point color list.
    trace = next(t for t in fig.data if isinstance(t, go.Scatter))
    colors = list(trace.marker.color)
    sc_um = df['PtV Distance'].values * 1000

    expected = [_traffic_light_color(sc, 10.0, 15.0, _SETTINGS['CHART_COLORS']) for sc in sc_um]
    assert colors == expected


def test_bullseye_renders_to_png():
    """End-to-end: the figure must convert to PNG (the path used by the Excel export)."""
    from qvm_dashboard.src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(_fixture_df(), _SETTINGS)
    png = fig.to_image(format='png', width=700, height=700, scale=2)
    assert len(png) > 1000  # non-trivial image
