"""Registration shrinkage: the company calculation and the design-position lookup."""

import re
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
import pytest

from src.parser import parse_qvm_content
from src.registration_shrinkage import (
    compute_distance_shrinkage,
    compute_shrinkage_by_group,
    design_for,
    design_lengths,
    layout_from_lengths,
    with_design_lengths,
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
    assert result.method_label == 'Company (distance)'


# ------------------------------------------------------------ company method
def test_zero_when_measured_equals_design(settings):
    design = _design(settings)
    shifted = {n: xy + np.array([301.4, 323.7]) for n, xy in _points(design).items()}
    for points in (_points(design), shifted):  # the machine origin does not matter
        result = compute_distance_shrinkage(_frame(points), design)
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


# ------------------------------------------------------------- design size
def test_the_design_is_two_lengths_for_every_build_up_and_file_type(settings):
    assert design_lengths(settings) == (232.5, 193.9)
    design = design_for(settings)
    assert len(design) == 16 and design != settings['CORE_SHRINKAGE']['NOMINAL_COORDS']
    assert design == design_for(settings, 'BU-09', 'Via to Pad')  # one size for all
    result = compute_distance_shrinkage(_frame(_points(design)), design)
    assert set(result.quadrant['X Design (mm)']) == {232.5}
    assert set(result.quadrant['Y Design (mm)']) == {193.9}
    assert normalize_build_up(' BU 3 ') == 'BU-03'


def test_only_the_lengths_matter_not_where_the_quadrants_sit(settings):
    """The gap between quadrants is for the map; it changes no number."""
    rng = np.random.default_rng(3)
    measured = {n: xy * 0.99985 + rng.normal(0, 0.004, 2) + np.array([301.4, 323.7])
                for n, xy in _points(layout_from_lengths(232.5, 193.9, 9.75, 50.1)).items()}
    frame = _frame(measured)
    near = compute_distance_shrinkage(frame, layout_from_lengths(232.5, 193.9, 0.0, 0.0))
    far = compute_distance_shrinkage(frame, layout_from_lengths(232.5, 193.9, 80.0, 5.0))
    pd.testing.assert_frame_equal(near.quadrant, far.quadrant)
    pd.testing.assert_frame_equal(near.full_panel, far.full_panel)


def test_design_size_from_the_sidebar_replaces_the_settings_value(settings):
    typed = with_design_lengths(settings, 230.0, 190.0)
    assert design_lengths(typed) == (230.0, 190.0)
    assert design_lengths(settings) == (232.5, 193.9)  # the loaded settings are untouched

    frame = _frame({n: xy * 0.9999 for n, xy in _points(design_for(typed)).items()},
                   **{'Build Up': 'Unknown', 'Panel': '20', 'Side': 'F', 'Process': 'Pad to Via'})
    group = compute_shrinkage_by_group(frame, typed)[0]
    assert group.lengths == (230.0, 190.0) and group.point == 'via'
    assert group.label == 'Build Up: Unknown, Panel: 20, Side: F'
    assert _panel(group.result)['Shrinkage X (ppm)'] == pytest.approx(-100.0, abs=0.01)
    assert _panel(group.result)['Delta X (um)'] == pytest.approx(-23.0, abs=0.01)

    # The same panel against the wrong size is refused, not reported as shrinkage.
    wrong = compute_shrinkage_by_group(frame, settings)[0]
    assert wrong.result.quadrant.empty and 'does not match the design' in wrong.result.warnings[0]


@pytest.mark.parametrize('x, y', [(None, 193.9), (0, 193.9), ('abc', 1.0), (232.5, -1)])
def test_no_design_size_means_no_numbers_and_a_clear_reason(settings, x, y):
    blank = with_design_lengths(settings, x, y)
    assert design_lengths(blank) is None and design_for(blank) is None
    frame = _frame(_points(design_for(settings)),
                   **{'Build Up': 'BU-01', 'Panel': '1', 'Side': 'F', 'Process': 'Via to Pad'})
    group = compute_shrinkage_by_group(frame, blank)[0]
    assert group.result.quadrant.empty
    assert 'No design quadrant size is set' in group.result.warnings[0]


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


# --------------------------------------------- lessons from the first real files
def test_site_local_positions_are_refused_not_reported(settings):
    """Real case: a file whose every site is measured in its own local frame,
    so all 16 'positions' are within a few microns of (0, 0)."""
    design = _design(settings, 'BU-01', 'Via to Pad')
    rng = np.random.default_rng(1)
    local = _frame({name: rng.normal(0, 0.003, 2) for name in design})
    result = compute_distance_shrinkage(local, design)
    assert result.quadrant.empty and result.full_panel.empty and result.lengths.empty
    assert 'positions relative to each site' in result.warnings[0]
    assert 'Export the measurement in panel coordinates' in result.warnings[0]

    # The parser gives such a file labels like '[1,1][1,2]' instead of UL_1 ... UR_4.
    unnamed = local.assign(Location=[f'[1,1][{i},{i}]' for i in range(len(local))])
    refused = compute_distance_shrinkage(unnamed, design)
    assert refused.quadrant.empty and 'could not be placed on the panel' in refused.warnings[0]


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
