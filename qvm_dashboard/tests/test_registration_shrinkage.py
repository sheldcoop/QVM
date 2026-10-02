"""Registration shrinkage: the company calculation, the two other methods, and
the design-position lookup."""

import re
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest

from src.parser import parse_qvm_content
from src.registration_shrinkage import (
    METHOD_AFFINE,
    METHOD_CENTRE,
    METHOD_COMPANY,
    METHOD_LABELS,
    compare_methods,
    compute_distance_shrinkage,
    compute_shrinkage,
    compute_shrinkage_by_group,
    design_for,
    measured_columns,
    measured_point,
    normalize_build_up,
)

COMPANY_WORKBOOK = (
    Path(__file__).resolve().parents[1] / 'sample_data' / 'Core Shrinkage Calculation.xlsx')
QUADRANTS = ('UL', 'LL', 'LR', 'UR')


# ------------------------------------------------------------------ helpers
def _design(settings, build_up='BU-01', process='Pad to Via'):
    design = design_for(settings, build_up, process)
    assert design is not None
    return design


def _points(design):
    return {name: np.array([xy['x'], xy['y']], dtype=float) for name, xy in design.items()}


def _frame(points, **extra):
    rows = [{'Location': name, 'Coord. X': xy[0], 'Coord. Y': xy[1], **extra}
            for name, xy in points.items()]
    return pd.DataFrame(rows)


def _panel(result):
    return result.full_panel.iloc[0]


def _quadrants_apart(points, microns=10.0):
    """Every quadrant keeps its size and is moved away from the panel centre."""
    step = microns / 1000.0
    return {
        name: xy + np.array([(-step if name[1] == 'L' else step),
                             (step if name[0] == 'U' else -step)])
        for name, xy in points.items()
    }


# ------------------------------------------------- the company workbook itself
def _evaluate_company_sheet(measured):
    """Fill the workbook's 'measured value' columns and evaluate its own formulas.

    Returns {cell: value} for the result cells, computed from the formula text
    stored in the workbook, so the test follows the sheet and not this code.
    """
    sheet = openpyxl.load_workbook(COMPANY_WORKBOOK)['Sheet1']
    values = {}
    for row in range(4, 20):
        location = sheet[f'B{row}'].value
        values[f'K{row}'], values[f'L{row}'] = measured[location]

    def cell(reference):
        if reference not in values:
            raw = sheet[reference].value
            if isinstance(raw, str) and raw.startswith('='):
                expression = re.sub(r'[A-Z]+\d+', lambda m: repr(cell(m.group(0))), raw[1:])
                values[reference] = eval(expression, {'__builtins__': {}})  # arithmetic only
            else:
                values[reference] = float(raw)
        return values[reference]

    quadrant = {name: (cell(f'T{row}'), cell(f'T{row + 1}'))
                for name, row in (('UL', 3), ('LL', 5), ('LR', 7), ('UR', 9))}
    return quadrant, (cell('T13'), cell('T14'))


def _workbook_design():
    sheet = openpyxl.load_workbook(COMPANY_WORKBOOK)['Sheet1']
    return {sheet[f'B{row}'].value: {'x': float(sheet[f'C{row}'].value),
                                     'y': float(sheet[f'D{row}'].value)}
            for row in range(4, 20)}


def test_company_method_matches_the_company_workbook_cell_for_cell():
    design = _workbook_design()
    rng = np.random.default_rng(7)
    measured = {name: (xy['x'] * 0.99985 + rng.normal(0, 0.004) + 301.4,
                       xy['y'] * 1.00012 + rng.normal(0, 0.004) + 323.7)
                for name, xy in design.items()}  # machine coordinates: shifted origin

    sheet_quadrants, (sheet_fp_x, sheet_fp_y) = _evaluate_company_sheet(measured)
    result = compute_distance_shrinkage(_frame(measured), design)

    table = result.quadrant.set_index('Quadrant')
    for name in QUADRANTS:
        # The sheet is in mm; the app shows the same value in um.
        assert table.loc[name, 'Delta X (um)'] == pytest.approx(sheet_quadrants[name][0] * 1000, abs=2e-3)
        assert table.loc[name, 'Delta Y (um)'] == pytest.approx(sheet_quadrants[name][1] * 1000, abs=2e-3)
    assert _panel(result)['Delta X (um)'] == pytest.approx(sheet_fp_x * 1000, abs=2e-3)
    assert _panel(result)['Delta Y (um)'] == pytest.approx(sheet_fp_y * 1000, abs=2e-3)
    assert result.method == METHOD_COMPANY


# ------------------------------------------------------------ company method
def test_zero_when_measured_equals_design_for_every_method(settings):
    design = _design(settings)
    for method in METHOD_LABELS:
        result = compute_shrinkage(_frame(_points(design)), design, method=method)
        assert len(result.quadrant) == 4
        assert (result.quadrant['Shrinkage X (ppm)'].abs() < 1e-6).all()
        assert (result.quadrant['Delta Y (um)'].abs() < 1e-6).all()
        assert _panel(result)['Shrinkage X (ppm)'] == pytest.approx(0.0, abs=1e-6)
        assert result.outliers.empty and result.warnings == []


def test_company_method_reports_um_and_ppm_per_quadrant(settings):
    design = _design(settings)
    x_scales = {'UL': 1.00010, 'LL': 1.00000, 'LR': 0.99990, 'UR': 1.00020}
    y_scales = {'UL': 0.99980, 'LL': 1.00005, 'LR': 1.00000, 'UR': 1.00010}
    # Scale each quadrant about its own corner, so only its lengths change.
    measured = {}
    for name, xy in _points(design).items():
        corner = _points(design)[f'{name[:2]}_1']
        scale = np.array([x_scales[name[:2]], y_scales[name[:2]]])
        measured[name] = corner + (xy - corner) * scale

    result = compute_distance_shrinkage(_frame(measured), design, outlier_ppm=50.0)
    table = result.quadrant.set_index('Quadrant')
    for name in QUADRANTS:
        assert table.loc[name, 'Shrinkage X (ppm)'] == pytest.approx((x_scales[name] - 1) * 1e6, abs=0.2)
        assert table.loc[name, 'Shrinkage Y (ppm)'] == pytest.approx((y_scales[name] - 1) * 1e6, abs=0.2)
        assert table.loc[name, 'X Design (mm)'] == pytest.approx(232.5)
        assert table.loc[name, 'Delta X (um)'] == pytest.approx((x_scales[name] - 1) * 232.5e3, abs=0.01)

    panel = _panel(result)
    expected_x = sum((v - 1) * 1e6 for v in x_scales.values()) / 4
    expected_y = sum((v - 1) * 1e6 for v in y_scales.values()) / 4
    assert panel['Shrinkage X (ppm)'] == pytest.approx(expected_x, abs=0.2)
    assert panel['Shrinkage Y (ppm)'] == pytest.approx(expected_y, abs=0.2)
    assert panel['X-Y Offset (ppm)'] == pytest.approx(expected_x - expected_y, abs=0.3)
    assert result.uniformity.iloc[0]['QTQ Range X (ppm)'] == pytest.approx(300.0, abs=0.3)
    # Panel average is +50 / -12.5 ppm; every quadrant is more than 50 ppm from it in X or Y.
    assert set(result.outliers['Quadrant']) == {'UL', 'LL', 'LR', 'UR'}
    assert result.outliers.set_index('Quadrant').loc['LR', 'X Deviation from FP (ppm)'] == pytest.approx(150.0, abs=0.3)

    assert not any('%' in column for frame in (result.quadrant, result.full_panel, result.uniformity)
                   for column in frame.columns)
    assert 'Total 2D Spatial Distortion Vector' not in result.uniformity.columns


def test_limit_is_off_until_set(settings):
    design = _design(settings)
    measured = _frame({name: xy * 0.9999 for name, xy in _points(design).items()})

    unchecked = compute_distance_shrinkage(measured, design)
    assert 'Status' not in unchecked.quadrant.columns
    assert 'Status' not in unchecked.full_panel.columns

    passing = compute_distance_shrinkage(measured, design, usl_ppm=150)
    failing = compute_distance_shrinkage(measured, design, usl_ppm=80)
    assert _panel(passing)['Status'] == 'Pass' and set(passing.quadrant['Status']) == {'Pass'}
    assert _panel(failing)['Status'] == 'Fail' and set(failing.quadrant['Status']) == {'Fail'}
    assert _panel(failing)['Shrinkage X (ppm)'] == pytest.approx(-100.0, abs=0.01)


def test_missing_points_and_missing_design_are_reported(settings):
    design = _design(settings)
    points = _points(design)
    del points['UR_3']
    result = compute_distance_shrinkage(_frame(points), design)
    assert list(result.quadrant['Quadrant']) == ['UL', 'LL', 'LR']
    assert result.warnings == ['Missing corner point(s) for quadrant UR; skipped.']

    nothing = compute_distance_shrinkage(_frame(_points(design)), None)
    assert nothing.quadrant.empty and nothing.warnings == ['No design positions configured.']
    with pytest.raises(ValueError, match='Unknown shrinkage method'):
        compute_shrinkage(_frame(_points(design)), design, method='guess')


# ------------------------------------------------------------- design lookup
def test_design_positions_come_per_build_up_and_file_type(settings):
    ptv_bu1 = design_for(settings, 'BU-1', 'Post PFC Pad to Via')
    vtp_bu1 = design_for(settings, 'bu01', 'Via to Pad')
    vtp_bu2 = design_for(settings, 'BU-02', 'Via to Pad')
    assert ptv_bu1['UL_1'] == {'x': -238.125, 'y': 218.075}
    assert vtp_bu1['UL_1'] == {'x': -237.375, 'y': 218.075}
    assert vtp_bu2['UL_1'] == {'x': -237.375, 'y': 219.575}

    # Not in the company's coordinate workbook: no numbers, and never the core design.
    assert design_for(settings, 'BU-02', 'Pad to Via') is None
    assert design_for(settings, 'BU-09', 'Via to Pad') is None
    assert design_for(settings, 'Unknown', 'Via to Pad') is None
    assert normalize_build_up(' BU 3 ') == 'BU-03'


def test_every_configured_design_has_the_registration_pitch(settings):
    designs = settings['REGISTRATION_SHRINKAGE']['DESIGNS']['C4F']
    core = settings['CORE_SHRINKAGE']['NOMINAL_COORDS']
    count = 0
    for by_process in designs.values():
        for design in by_process.values():
            count += 1
            assert len(design) == 16 and design != core
            result = compute_distance_shrinkage(_frame(_points(design)), design)
            assert set(result.quadrant['X Design (mm)']) == {232.5}
            assert set(result.quadrant['Y Design (mm)']) == {193.9}
    assert count == 4


def test_groups_use_their_own_design_and_say_when_there_is_none(settings):
    frames = []
    for build_up, process, scale in (('BU-01', 'Pad to Via', 0.9999), ('BU-02', 'Via to Pad', 1.0002),
                                     ('BU-02', 'Pad to Via', 1.0)):
        design = design_for(settings, build_up, process) or _design(settings)
        frames.append(_frame({n: xy * scale for n, xy in _points(design).items()},
                             **{'Build Up': build_up, 'Panel': '20', 'Side': 'F', 'Process': process}))

    strict = dict(settings)
    strict['REGISTRATION_SHRINKAGE'] = {
        **settings['REGISTRATION_SHRINKAGE'], 'fallback_to_equivalent_design': False}
    ptv = compute_shrinkage_by_group(pd.concat(frames[::2]), strict)
    vtp = compute_shrinkage_by_group(frames[1], settings)

    assert [g.group['Build Up'] for g in ptv] == ['BU-01', 'BU-02']
    assert _panel(ptv[0].result)['Shrinkage X (ppm)'] == pytest.approx(-100.0, abs=0.01)
    assert ptv[0].label == 'Build Up: BU-01, Panel: 20, Side: F' and ptv[0].point == 'via'
    assert ptv[0].design_note is None
    assert ptv[1].result.quadrant.empty and ptv[1].design is None
    assert 'No design positions configured for BU-02 / Pad to Via' in ptv[1].result.warnings[0]

    assert vtp[0].process == 'Via to Pad'
    assert _panel(vtp[0].result)['Shrinkage Y (ppm)'] == pytest.approx(200.0, abs=0.01)


def test_measured_point_can_be_switched_to_the_pad(settings):
    content = """
Circle: Via_LL_2(ID:1, From 70 Pts.)
     Coord. X =        64.071816
     Coord. Y =       103.848650
     Diameter =         0.016742

Circle: Pad_LL_2(ID:2, From 180 Pts.)
     Coord. X =        64.072222
     Coord. Y =       103.848064
     Diameter =         0.308911

Distance: VtP_LL_2(ID:3) between Pad_LL_2(ID:2) and Via_LL_2(ID:1)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681
"""
    parsed, _ = parse_qvm_content(content, settings)
    assert parsed.iloc[0]['Pad Coord. X'] == pytest.approx(64.072222)
    assert parsed.iloc[0]['Coord. X'] == pytest.approx(64.071816)

    assert measured_point(settings, 'Via to Pad') == 'via'
    assert measured_columns(settings, 'Via to Pad') == ('Location', 'Coord. X', 'Coord. Y')
    switched = dict(settings)
    switched['REGISTRATION_SHRINKAGE'] = {
        **settings['REGISTRATION_SHRINKAGE'], 'measured_point': {'Via to Pad': 'pad'}}
    assert measured_columns(switched, 'Via to Pad') == ('Location', 'Pad Coord. X', 'Pad Coord. Y')
    assert measured_point(switched, 'Pad to Via') == 'via'

    # Vias sit on the design; the pad pattern is 100 ppm smaller.
    design = _design(settings, 'BU-01', 'Via to Pad')
    frame = _frame(_points(design), **{'Build Up': 'BU-01', 'Panel': '20', 'Side': 'F',
                                       'Process': 'Via to Pad'})
    frame['Pad Coord. X'] = frame['Coord. X'] * 0.9999
    frame['Pad Coord. Y'] = frame['Coord. Y'] * 0.9999
    from_via = compute_shrinkage_by_group(frame, settings)[0]
    from_pad = compute_shrinkage_by_group(frame, switched)[0]
    assert _panel(from_via.result)['Shrinkage X (ppm)'] == pytest.approx(0.0, abs=0.01)
    assert _panel(from_pad.result)['Shrinkage X (ppm)'] == pytest.approx(-100.0, abs=0.01)
    assert from_pad.point == 'pad'


# ------------------------------------------- the three methods against each other
def test_all_methods_agree_on_an_evenly_shrunk_panel(settings):
    design = _design(settings)
    shifted = {name: xy * 0.9999 + np.array([301.4, 323.7])
               for name, xy in _points(design).items()}  # machine origin is elsewhere
    table = compare_methods(_frame(shifted), design)
    assert list(table['Method']) == ['Company (distance)', 'Centre-based', 'Affine fit']
    assert table['Shrinkage X (ppm)'].tolist() == pytest.approx([-100.0] * 3, abs=0.01)
    assert table['Shrinkage Y (ppm)'].tolist() == pytest.approx([-100.0] * 3, abs=0.01)


def test_centre_method_equals_company_per_quadrant_but_sees_the_gaps(settings):
    design = _design(settings)
    apart = _frame(_quadrants_apart(_points(design), microns=10.0))

    company = compute_shrinkage(apart, design, method=METHOD_COMPANY)
    centre = compute_shrinkage(apart, design, method=METHOD_CENTRE)

    # Inside each quadrant nothing changed: both methods say zero there.
    for result in (company, centre):
        assert (result.quadrant['Shrinkage X (ppm)'].abs() < 1e-6).all()
    # The panel is 20 um wider and taller between the quadrants. Only the
    # centre method notices, because the company value is a mean of quadrants.
    assert _panel(company)['Shrinkage X (ppm)'] == pytest.approx(0.0, abs=1e-6)
    assert _panel(centre)['Shrinkage X (ppm)'] == pytest.approx(42.969, abs=0.01)
    assert _panel(centre)['Shrinkage Y (ppm)'] == pytest.approx(50.240, abs=0.01)

    # With different shrinkage per quadrant the two still agree quadrant by quadrant.
    rng = np.random.default_rng(3)
    noisy = _frame({n: xy + rng.normal(0, 0.005, 2) for n, xy in _points(design).items()})
    a = compute_shrinkage(noisy, design, method=METHOD_COMPANY).quadrant
    b = compute_shrinkage(noisy, design, method=METHOD_CENTRE).quadrant
    assert a['Shrinkage X (ppm)'].tolist() == pytest.approx(b['Shrinkage X (ppm)'].tolist(), abs=0.01)
    assert a['Shrinkage Y (ppm)'].tolist() == pytest.approx(b['Shrinkage Y (ppm)'].tolist(), abs=0.01)


def test_affine_method_separates_rotation_shear_and_bad_points(settings):
    design = _design(settings)
    points = _points(design)

    angle = np.radians(0.3)
    turn = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    rotated = _frame({n: turn @ xy + np.array([5.0, -3.0]) for n, xy in points.items()})
    table = compare_methods(rotated, design).set_index('Method')
    # A rotated panel looks 14 ppm shorter to the two axis-by-axis methods.
    assert table.loc['Company (distance)', 'Shrinkage X (ppm)'] == pytest.approx(-13.708, abs=0.01)
    assert table.loc['Centre-based', 'Shrinkage X (ppm)'] == pytest.approx(-13.708, abs=0.01)
    assert table.loc['Affine fit', 'Shrinkage X (ppm)'] == pytest.approx(0.0, abs=0.01)
    assert table.loc['Affine fit', 'Rotation (deg)'] == pytest.approx(0.3, abs=1e-3)

    shear = np.array([[1.0, 100e-6], [0.0, 1.0]])
    sheared = compare_methods(_frame({n: shear @ xy for n, xy in points.items()}), design)
    assert sheared['Shrinkage X (ppm)'].tolist() == pytest.approx([0.0] * 3, abs=0.01)
    assert sheared.set_index('Method').loc['Affine fit', 'Shear (deg)'] == pytest.approx(0.0057, abs=2e-4)

    bad = dict(points)
    bad['UL_4'] = points['UL_4'] + np.array([0.080, 0.0])  # one point 80 um off
    company = compute_shrinkage(_frame(bad), design, method=METHOD_COMPANY)
    affine = compute_shrinkage(_frame(bad), design, method=METHOD_AFFINE, outlier_um=50.0)
    # Company: the whole UL quadrant, and with it the panel, moves.
    assert company.quadrant.set_index('Quadrant').loc['UL', 'Delta X (um)'] == pytest.approx(40.0, abs=0.01)
    assert _panel(company)['Shrinkage X (ppm)'] == pytest.approx(43.011, abs=0.01)
    assert company.warnings == []  # and nothing says which point caused it
    # Affine: the point is named and left out; the panel result is unaffected.
    assert _panel(affine)['Shrinkage X (ppm)'] == pytest.approx(0.0, abs=0.01)
    assert affine.details.iloc[0]['Points Rejected'] == 1
    rejected = affine.points[affine.points['Rejected']]
    assert list(rejected['Location']) == ['UL_4']
    assert rejected.iloc[0]['Residual (um)'] == pytest.approx(80.0, abs=0.01)
    assert 'UL_4' in affine.warnings[0]


def test_company_method_scatters_more_under_measurement_noise(settings):
    """Pins the repeatability figures quoted in SHRINKAGE_METHODS.md."""
    design = _design(settings)
    points = _points(design)
    rng = np.random.default_rng(11)
    panel_x = {method: [] for method in METHOD_LABELS}
    for _ in range(1500):
        noisy = _frame({n: xy + rng.normal(0, 0.003, 2) for n, xy in points.items()})
        for method in METHOD_LABELS:
            panel_x[method].append(
                _panel(compute_shrinkage(noisy, design, method=method))['Shrinkage X (ppm)'])
    spread = {method: float(np.std(values)) for method, values in panel_x.items()}
    assert spread[METHOD_COMPANY] == pytest.approx(6.5, abs=0.3)
    assert spread[METHOD_CENTRE] == pytest.approx(4.5, abs=0.3)
    assert spread[METHOD_AFFINE] == pytest.approx(4.5, abs=0.3)


def test_the_one_dimensional_example_of_the_methods_document():
    """20 / 280 / 300 / 560: the centre is the average of the points."""
    design = np.array([20.0, 280.0, 300.0, 560.0])
    assert design.mean() == 290.0 and list(design - design.mean()) == [-270.0, -10.0, 10.0, 270.0]

    def company_ppm(measured):
        return ((measured[1] - measured[0] - 260) + (measured[3] - measured[2] - 260)) / 2 / 260 * 1e6

    def centre_ppm(measured):
        d, m = design - design.mean(), measured - measured.mean()
        return ((d * m).sum() / (d * d).sum() - 1) * 1e6

    even = 290 + (design - 290) * 0.9999 + 1000
    apart = design + np.array([-0.02, -0.02, 0.02, 0.02]) + 1000
    assert company_ppm(even) == pytest.approx(-100.0, abs=0.01)
    assert centre_ppm(even) == pytest.approx(-100.0, abs=0.01)
    assert company_ppm(apart) == pytest.approx(0.0, abs=0.01)
    assert centre_ppm(apart) == pytest.approx(76.7, abs=0.05)


def test_missing_build_up_uses_an_equivalent_design_and_says_so(settings):
    from src.registration_shrinkage import resolve_design

    # A file name without a Build Up gives 'Unknown'; BU-02 Pad to Via is not configured.
    for build_up, process, source in (('Unknown', 'Via to Pad', 'BU-01 / Via to Pad'),
                                      ('BU-02', 'Pad to Via', 'BU-01 / Pad to Via'),
                                      ('Unknown', 'Pad to Via', 'BU-01 / Pad to Via')):
        design, note = resolve_design(settings, build_up, process)
        assert design is not None and f'those of {source} are used' in note
        assert 'differ only by a shift' in note
    exact, note = resolve_design(settings, 'BU-03', 'Pad to Via')
    assert exact == design_for(settings, 'BU-03', 'Pad to Via') and note is None

    # The stand-in gives exactly the result the right design would give, for every method:
    # measure a BU-03 panel, once against its own design and once as 'Unknown'.
    own = _design(settings, 'BU-03', 'Pad to Via')
    rng = np.random.default_rng(5)
    measured = {n: xy * 0.99988 + rng.normal(0, 0.004, 2) + np.array([301.4, 323.7])
                for n, xy in _points(own).items()}
    for method in METHOD_LABELS:
        results = []
        for build_up in ('BU-03', 'Unknown'):
            frame = _frame(measured, **{'Build Up': build_up, 'Panel': '20', 'Side': 'F',
                                        'Process': 'Pad to Via'})
            group = compute_shrinkage_by_group(frame, settings, method=method)[0]
            results.append(group)
        assert results[0].design_note is None and results[1].design_note is not None
        pd.testing.assert_frame_equal(results[0].result.quadrant, results[1].result.quadrant)
        pd.testing.assert_frame_equal(results[0].result.full_panel, results[1].result.full_panel)


def test_no_stand_in_when_configured_designs_differ_in_shape(settings):
    from src.registration_shrinkage import resolve_design

    cfg = settings['REGISTRATION_SHRINKAGE']
    other = {name: {'x': xy['x'] * 1.1, 'y': xy['y']}
             for name, xy in cfg['DESIGNS']['C4F']['BU-01']['Pad to Via'].items()}
    mixed = dict(settings)
    mixed['REGISTRATION_SHRINKAGE'] = {
        **cfg, 'DESIGNS': {'C4F': {**cfg['DESIGNS']['C4F'], 'BU-05': {'Pad to Via': other}}}}
    design, note = resolve_design(mixed, 'Unknown', 'Pad to Via')
    assert design is None and 'differ in shape' in note
    frame = _frame(_points(other), **{'Build Up': 'Unknown', 'Panel': '1', 'Side': 'F',
                                      'Process': 'Pad to Via'})
    group = compute_shrinkage_by_group(frame, mixed)[0]
    assert group.result.quadrant.empty and 'differ in shape' in group.result.warnings[0]
    core = settings['CORE_SHRINKAGE']['NOMINAL_COORDS']
    assert resolve_design(settings, 'Unknown', 'Via to Pad')[0] != core


# --------------------------------------------- lessons from the first real files
def test_site_local_positions_are_refused_not_reported(settings):
    """Real case: a file whose every site is measured in its own local frame,
    so all 16 'positions' are within a few microns of (0, 0)."""
    design = _design(settings, 'BU-01', 'Via to Pad')
    rng = np.random.default_rng(1)
    local = _frame({name: rng.normal(0, 0.003, 2) for name in design})
    for method in METHOD_LABELS:
        result = compute_shrinkage(local, design, method=method)
        assert result.quadrant.empty and result.full_panel.empty and result.lengths.empty
        assert 'positions relative to each site' in result.warnings[0]
        assert 'Export the measurement in panel coordinates' in result.warnings[0]
    assert compare_methods(local, design).empty


def test_design_of_another_product_is_refused_with_the_measured_sizes(settings):
    """Real case: quadrants of 230.67 x 194.02 mm measured against a 232.5 x 193.9 design
    would read as -7900 ppm of 'shrinkage'."""
    design = _design(settings, 'BU-01', 'Via to Pad')
    other = {}
    for name, xy in _points(design).items():
        corner = _points(design)[f'{name[:2]}_2']  # bottom-left of the quadrant
        other[name] = corner + (xy - corner) * np.array([230.67 / 232.5, 194.02 / 193.9])

    result = compute_distance_shrinkage(_frame(other), design)
    assert result.quadrant.empty and result.full_panel.empty
    message = result.warnings[0]
    assert 'does not match the design (232.500 x 193.900 mm)' in message
    assert '230.670 x 194.020 mm' in message and 'limit 2000 ppm' in message
    assert list(result.lengths['Quadrant']) == ['UL', 'LL', 'LR', 'UR']
    assert result.lengths['X Difference (ppm)'].tolist() == pytest.approx([-7870.97] * 4, abs=0.1)
    assert result.lengths['Y Difference (ppm)'].tolist() == pytest.approx([618.88] * 4, abs=0.1)

    # The limit is a setting: with it off, the numbers come back (and say what they are).
    forced = compute_distance_shrinkage(_frame(other), design, max_plausible_ppm=None)
    assert _panel(forced)['Shrinkage X (ppm)'] == pytest.approx(-7870.97, abs=0.1)
    # Ordinary shrinkage is nowhere near the limit.
    fine = compute_distance_shrinkage(_frame({n: xy * 0.9992 for n, xy in _points(design).items()}), design)
    assert _panel(fine)['Shrinkage X (ppm)'] == pytest.approx(-800.0, abs=0.01)
    assert not fine.lengths.empty
