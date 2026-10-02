"""The shared shrinkage screen renders for every method, with and without a design."""

import pytest

pytest.importorskip('streamlit.testing.v1')
from streamlit.testing.v1 import AppTest  # noqa: E402


def _screen(build_up: str, scale: float, in_expanders: bool):
    import pandas as pd

    from src.registration_shrinkage import design_for
    from src.utils import load_settings
    from src.views.registration_shrinkage import render_registration_shrinkage

    settings = load_settings()
    design = design_for(settings, 'BU-01', 'Via to Pad')
    rows = [{'Location': name, 'Coord. X': xy['x'] * scale + 301.4, 'Coord. Y': xy['y'] * scale,
             'Build Up': build_up, 'Panel': '25', 'Side': 'F', 'Process': 'Via to Pad'}
            for name, xy in design.items()]
    render_registration_shrinkage(
        pd.DataFrame(rows), settings, key='test', in_expanders=in_expanders)


def _run(build_up='BU-01', scale=0.9999, in_expanders=False):
    return AppTest.from_function(
        _screen, kwargs={'build_up': build_up, 'scale': scale, 'in_expanders': in_expanders},
        default_timeout=60).run()


def test_company_result_is_shown_first_in_um_with_ppm():
    app = _run()
    assert not app.exception
    assert app.radio(key='test_shrinkage_method').value == 'company'
    shown = {metric.label: (metric.value, metric.delta) for metric in app.metric}
    assert shown['Panel X'] == ('-23.2 µm', '-100.0 ppm')
    assert shown['Panel Y'] == ('-19.4 µm', '-100.0 ppm')
    assert 'Limit' not in shown  # no limit configured
    assert list(app.dataframe[0].value.columns)[:5] == [
        'Quadrant', 'Delta X (um)', 'Shrinkage X (ppm)', 'Delta Y (um)', 'Shrinkage Y (ppm)']
    assert 'No quadrant is more than 50 ppm' in app.success[0].value
    comparison = app.dataframe[-1].value
    assert list(comparison['Method']) == ['Company (distance)', 'Centre-based', 'Affine fit']


@pytest.mark.parametrize('method', ['centre', 'affine'])
def test_other_methods_can_be_chosen(method):
    app = _run()
    app.radio(key='test_shrinkage_method').set_value(method).run()
    assert not app.exception
    shown = {metric.label: metric.delta for metric in app.metric}
    assert shown['Panel X'] == '-100.0 ppm'
    if method == 'affine':
        assert 'Rotation (deg)' in app.dataframe[1].value.columns


def test_build_up_without_design_uses_an_equivalent_one_and_says_so():
    app = _run(build_up='Unknown', in_expanders=True)
    assert not app.exception
    note = app.info[0].value
    assert 'No design positions configured for Unknown / Via to Pad' in note
    assert 'those of BU-01 / Via to Pad are used' in note
    assert {m.label: m.delta for m in app.metric}['Panel X'] == '-100.0 ppm'
    assert len(app.warning) == 0


def _local_screen():
    import pandas as pd

    from src.registration_shrinkage import design_for
    from src.utils import load_settings
    from src.views.registration_shrinkage import render_registration_shrinkage

    settings = load_settings()
    design = design_for(settings, 'BU-01', 'Via to Pad')
    rows = []
    for side, wrong_product in (('F', False), ('B', True)):
        for index, (name, xy) in enumerate(design.items()):
            x, y = (xy['x'] * 0.992, xy['y']) if wrong_product else (index * 1e-4, -index * 1e-4)
            rows.append({'Location': name, 'Coord. X': x, 'Coord. Y': y, 'Build Up': 'BU-01',
                         'Panel': '09', 'Side': side, 'Process': 'Via to Pad'})
    render_registration_shrinkage(pd.DataFrame(rows), settings, key='real')


def test_unusable_measurements_get_an_explanation_instead_of_numbers():
    app = AppTest.from_function(_local_screen, default_timeout=60).run()
    assert not app.exception
    assert len(app.metric) == 0
    warnings = [w.value for w in app.warning]
    assert any('does not match the design' in w for w in warnings)  # side B
    assert any('positions relative to each site' in w for w in warnings)  # side F
    sizes = app.dataframe[0].value
    assert list(sizes.columns)[:4] == [
        'Quadrant', 'X Measured (mm)', 'X Design (mm)', 'X Difference (ppm)']
    assert any('needs no design' in c.value for c in app.caption)


def test_full_width_helper_fits_the_installed_streamlit():
    import streamlit as st

    from src.views.base import full_width

    assert full_width(st.dataframe) == {'width': 'stretch'}
    assert full_width(st.plotly_chart) in ({'width': 'stretch'}, {'use_container_width': True})
    assert full_width(lambda figure, use_container_width=False: None) == {'use_container_width': True}
