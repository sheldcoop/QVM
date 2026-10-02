"""Tests for the Via-to-Pad bullseye scatter.

Shared fixtures (`vtp_df`, `settings`) live in conftest.py.
"""

import pandas as pd
import plotly.graph_objects as go


def test_bullseye_draws_four_tolerance_rings(vtp_df, settings):
    """Regression: 4 rings (exceptional/excellent/good/acceptable) are drawn."""
    from src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(vtp_df, settings)
    circles = [s for s in fig.layout.shapes if s.type == 'circle']
    assert len(circles) == 4, f'Expected 4 rings, got {len(circles)}'

    radii = sorted([abs(c.x1) for c in circles])
    assert radii == [2.5, 5.0, 7.5, 10.0]


def test_bullseye_axes_reach_past_outermost_ring(settings):
    """Regression: axis must always show the outermost ring even with tight data."""
    from src.visuals import plot_vtp_bullseye

    df = pd.DataFrame({
        'Location': ['a', 'b'],
        'Grid ID': [11, 12],
        'Shift (DX)': [0.001, -0.002],
        'Shift (DY)': [0.002, 0.001],
        'PtV Distance': [0.0022, 0.0022],
    })
    fig = plot_vtp_bullseye(df, settings)
    xmax = fig.layout.xaxis.range[1]
    assert xmax >= 10.0, f'Axis must reach past ring_acceptable (10 µm); got {xmax}'


def test_bullseye_has_summary_and_legend_annotations(vtp_df, settings):
    """Regression: summary stats + zone legend present for the Excel export."""
    from src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(vtp_df, settings)
    texts = [a.text for a in fig.layout.annotations]
    assert any('max SC' in t for t in texts), 'Missing summary stats annotation'
    # Zone legend uses ⬤ symbols and zone thresholds
    assert any('⬤' in t for t in texts), 'Missing zone legend annotation'


def test_bullseye_point_colors_match_dark_zone_palette(vtp_df, settings):
    """Regression: point colours use the Catppuccin Mocha theme.ZONE palette."""
    from src.visuals import plot_vtp_bullseye
    from src.theme import ZONE

    fig = plot_vtp_bullseye(vtp_df, settings)
    trace = next(t for t in fig.data if isinstance(t, go.Scatter))
    colors = list(trace.marker.color)
    sc_um = vtp_df['PtV Distance'].values * 1000

    expected = [
        (ZONE['exceptional'] if v <= 2.5 else
         ZONE['excellent']   if v <= 5.0 else
         ZONE['good']        if v <= 7.5 else
         ZONE['acceptable']  if v <= 10.0 else
         ZONE['fail'])
        for v in sc_um
    ]
    assert colors == expected


def test_bullseye_renders_to_png(vtp_df, settings):
    """End-to-end: figure must convert to PNG (path used by the Excel export)."""
    import pytest
    pytest.importorskip('kaleido')
    from src.visuals import plot_vtp_bullseye

    fig = plot_vtp_bullseye(vtp_df, settings)
    try:
        png = fig.to_image(format='png', width=700, height=700, scale=2)
    except Exception as exc:  # Chrome missing/broken in this environment
        pytest.skip(f'kaleido PNG render unavailable: {exc}')
    assert len(png) > 1000


def test_bullseye_grid_labels_are_integer_like(settings):
    """Grid labels on bullseye markers should be 23/33 style, not 23.0/33.0."""
    from src.visuals import plot_vtp_bullseye

    df = pd.DataFrame({
        'Location': ['a', 'b', 'c'],
        'Grid ID': [23.0, 33.0, 34.0],
        'Shift (DX)': [0.001, -0.002, 0.0015],
        'Shift (DY)': [0.002, 0.001, -0.0005],
        'PtV Distance': [0.0022, 0.0022, 0.0025],
    })

    fig = plot_vtp_bullseye(df, settings)
    trace = next(t for t in fig.data if isinstance(t, go.Scatter))
    assert list(trace.text) == ['23', '33', '34']
