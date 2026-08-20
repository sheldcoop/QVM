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
    }, '__all__ must list exactly the charts the dashboard renders'


def test_quiver_returns_figure_with_dots_and_arrows(vtp_df, settings):
    from src.visuals import plot_quiver
    fig = plot_quiver(vtp_df, settings, multiplier=100)
    assert isinstance(fig, go.Figure)
    # one site-dot scatter trace
    assert any(isinstance(t, go.Scatter) for t in fig.data)
    # arrow annotations coloured from the theme ARROW palette
    arrows = [a for a in fig.layout.annotations if a.showarrow]
    assert arrows, 'expected arrow annotations'
    assert all(a.arrowcolor in theme.ARROW.values() for a in arrows)


def test_box_returns_figure_with_boxes_and_cards(vtp_df, settings):
    from src.visuals import plot_vtp_box
    fig = plot_vtp_box(vtp_df, settings)
    assert any(isinstance(t, go.Box) for t in fig.data)
    texts = [a.text for a in fig.layout.annotations]
    assert any('Pass' in (t or '') for t in texts)      # stats card
    assert any('⬤' in (t or '') for t in texts)         # zone legend


def test_site_bars_sorted_by_grid_id(vtp_df, settings):
    from src.visuals import plot_vtp_site_bars
    fig = plot_vtp_site_bars(vtp_df, settings)
    bar = next(t for t in fig.data if isinstance(t, go.Bar))
    xs = [int(x) for x in bar.x]
    assert xs == sorted(xs)


def test_bullseye_and_quiver_legend_below_axis_title(vtp_df, settings):
    """Regression: zone/pattern legend must sit clear of the centered x-axis
    title (previously both at y=-0.08 → overlap)."""
    from src.visuals import plot_vtp_bullseye, plot_quiver

    for fig in (plot_vtp_bullseye(vtp_df, settings),
                plot_quiver(vtp_df, settings, multiplier=100)):
        legends = [a for a in fig.layout.annotations
                   if a.text and '⬤' in a.text]
        assert legends, 'expected a bottom legend annotation'
        assert all(a.y < -0.12 for a in legends), \
            'legend must be moved below the axis-title band'
