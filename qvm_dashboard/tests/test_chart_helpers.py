"""Tests for the reusable chart helpers in src/chart_helpers.py."""

import pandas as pd
import plotly.graph_objects as go

from src import theme
from src.chart_helpers import (
    Rings, get_rings, zone_color, zone_colors, apply_dark_layout,
    stats_card_annotation, zone_legend_annotation,
)


def test_get_rings_reads_settings():
    settings = {'VTP_REGISTRATION': {
        'ring_exceptional_um': 1.0, 'ring_excellent_um': 2.0,
        'ring_good_um': 3.0, 'ring_acceptable_um': 4.0,
    }}
    rings = get_rings(settings)
    assert (rings.exceptional, rings.excellent, rings.good, rings.acceptable) == (1.0, 2.0, 3.0, 4.0)


def test_get_rings_defaults_on_empty_settings():
    rings = get_rings({})
    assert rings == Rings(2.5, 5.0, 7.5, 10.0)


def test_zone_color_boundaries():
    rings = Rings(2.5, 5.0, 7.5, 10.0)
    assert zone_color(2.5, rings) == theme.ZONE['exceptional']   # inclusive
    assert zone_color(2.6, rings) == theme.ZONE['excellent']
    assert zone_color(7.5, rings) == theme.ZONE['good']
    assert zone_color(10.0, rings) == theme.ZONE['acceptable']
    assert zone_color(10.1, rings) == theme.ZONE['fail']


def test_zone_colors_matches_scalar():
    rings = Rings(2.5, 5.0, 7.5, 10.0)
    s = pd.Series([1.0, 4.0, 6.0, 9.0, 12.0])
    vectorised = list(zone_colors(s, rings))
    scalar = [zone_color(v, rings) for v in s]
    assert vectorised == scalar


def test_apply_dark_layout_sets_theme_and_overrides():
    fig = go.Figure()
    apply_dark_layout(fig, height=321, hovermode='x unified')
    assert fig.layout.plot_bgcolor == theme.PLOT_BG
    assert fig.layout.paper_bgcolor == theme.PAPER_BG
    assert fig.layout.font.color == theme.TEXT
    assert fig.layout.height == 321
    assert fig.layout.hovermode == 'x unified'


def test_annotation_cards_have_expected_shape():
    rings = Rings(2.5, 5.0, 7.5, 10.0)
    legend = zone_legend_annotation(rings)
    assert '⬤' in legend['text']
    assert legend['xref'] == 'paper' and legend['yref'] == 'paper'

    card = stats_card_annotation(n=16, mean_v=5.0, median_v=4.0, std_v=1.0, pct_pass=100.0)
    assert 'Mean' in card['text'] and 'Pass' in card['text']
    assert card['xanchor'] == 'left'
