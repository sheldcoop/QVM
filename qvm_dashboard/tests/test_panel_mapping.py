"""Smoke tests for the panel-map view."""

import plotly.graph_objects as go
import pytest


_SETTINGS = {
    'PANEL_VIEW': {
        'frame_width': 510.0, 'frame_height': 515.0,
        'offset_x': 13.5, 'offset_y': 15.0,
        'gap_x': 3.0, 'gap_y': 3.0,
        'dynamic_gap_x': 5.0, 'dynamic_gap_y': 3.5,
        'corner_radius': 20.0, 'point_margin_factor': 0.20,
    },
    'COLORS': {
        'panel_body': '#C87533', 'quarter_fill': '#F4B486',
        'grid_border': '#8B4513', 'background': '#2C3E50',
    },
    'FIGURE_SETTINGS': {'width': 800, 'height': 800, 'margin': 40,
                        'point_marker_size': 35, 'point_text_size': 14},
    'GRID_MAPPING': {
        'UL_1': 11, 'UL_2': 12, 'UL_3': 13, 'UL_4': 14,
        'LL_1': 21, 'LL_2': 22, 'LL_3': 23, 'LL_4': 24,
        'LR_1': 31, 'LR_2': 32, 'LR_3': 33, 'LR_4': 34,
        'UR_1': 41, 'UR_2': 42, 'UR_3': 43, 'UR_4': 44,
    },
    'POSITIONAL_MAPPING': ['22', '21', '23', '24', '12', '11', '13', '14',
                           '32', '31', '33', '34', '42', '41', '43', '44'],
}


def test_panel_map_renders_16_points():
    from src.panel_mapping import create_four_quarters_view

    fig = create_four_quarters_view(_SETTINGS)
    assert isinstance(fig, go.Figure)
    # One scatter trace with 16 points (4 per quarter × 4 quarters)
    assert len(fig.data) == 1
    assert len(fig.data[0].x) == 16


def test_panel_map_hover_has_no_vtp_index():
    """Regression test: 'VtP Index' was removed from the hover text."""
    from src.panel_mapping import create_four_quarters_view

    fig = create_four_quarters_view(_SETTINGS)
    customdata = fig.data[0].customdata
    assert all('VtP Index' not in entry for entry in customdata)
    # Hover should still carry Grid ID and Location.
    sample = customdata[0]
    assert 'Grid ID' in sample
    assert 'Location' in sample
