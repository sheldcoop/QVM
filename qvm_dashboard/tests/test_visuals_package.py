"""Tests for the src/visuals package: public API + each chart builder."""

import plotly.graph_objects as go

from src import theme


def test_public_api_is_importable():
    from src import visuals
    for name in ('plot_vtp_bullseye', 'plot_vtp_site_bars', 'plot_quiver',
                 'plot_vtp_box'):
        assert hasattr(visuals, name), f'visuals.{name} missing from public API'
    assert set(visuals.__all__) == {
        'plot_vtp_bullseye', 'plot_vtp_site_bars', 'plot_quiver', 'plot_vtp_box',
        'plot_shrinkage_panel', 'plot_quadrant_bars',
    }, '__all__ must list exactly the charts the dashboard renders'


def test_shrinkage_panel_map_and_bars(settings):
    import pandas as pd

    from src.registration_shrinkage import compute_distance_shrinkage, design_for
    from src.visuals import plot_quadrant_bars, plot_shrinkage_panel

    design = design_for(settings, 'BU-01', 'Pad to Via')
    rows = [{'Location': name,
             'Coord. X': xy['x'] * (1.0002 if name.startswith('UR') else 0.9999),
             'Coord. Y': xy['y'] * 0.9999} for name, xy in design.items()]
    result = compute_distance_shrinkage(pd.DataFrame(rows), design)

    panel = plot_shrinkage_panel(result, design, 'map')
    assert isinstance(panel, go.Figure)
    assert panel.layout.plot_bgcolor == theme.PLOT_BG and panel.layout.height == 600
    assert len(panel.data) == 1 and len(panel.data[0].x) == 16  # the 16 sites, to scale
    assert len([shape for shape in panel.layout.shapes if shape.type == 'rect']) == 4
    arrows = [a for a in panel.layout.annotations if a.showarrow]
    assert len(arrows) == 16  # per quadrant: X at both ends, Y at both ends
    colours = {a.arrowcolor for a in arrows}
    assert colours == {theme.ARROW['expansion'], theme.ARROW['contraction']}  # UR grew in X
    texts = ' '.join(a.text for a in panel.layout.annotations if a.text)
    assert 'Panel X' in texts and '<b>UR</b>' in texts and 'Grew' in texts and 'Shrank' in texts
    assert '(-100 ppm)' in texts and '(+200 ppm)' in texts

    bars = plot_quadrant_bars(result, 'bars')
    assert [type(t).__name__ for t in bars.data] == ['Bar', 'Scatter', 'Bar', 'Scatter']
    assert list(bars.data[0].x) == ['UL', 'LL', 'LR', 'UR']
    assert bars.data[0].marker.color == '#E0965A'  # copper for X
    # Every text colour is set, so a light app theme cannot turn it black.
    assert bars.layout.xaxis.tickfont.color == theme.TEXT
    assert bars.layout.yaxis.tickfont.color == theme.TEXT
    assert bars.layout.legend.font.color == theme.TEXT
    assert bars.data[1].name.startswith('Panel X: ')

    empty = compute_distance_shrinkage(pd.DataFrame(rows), None)
    assert len(plot_shrinkage_panel(empty, design, 'x').data) == 0  # nothing to draw, no error
