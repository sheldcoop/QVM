import pandas as pd
import pytest

from src.registration_shrinkage import compute_distance_shrinkage


def _nominal_coords(settings):
    return settings['CORE_SHRINKAGE']['NOMINAL_COORDS']


def _measured_from_nominal(nominal, x_scales=None, y_scales=None):
    x_scales = x_scales or {}
    y_scales = y_scales or {}
    rows = []
    for loc, xy in nominal.items():
        quad = loc.split('_')[0]
        sx = x_scales.get(quad, 1.0)
        sy = y_scales.get(quad, 1.0)
        rows.append({
            'Location': loc,
            'Coord. X': float(xy['x']) * sx,
            'Coord. Y': float(xy['y']) * sy,
        })
    return pd.DataFrame(rows)


def test_distance_shrinkage_zero_when_measured_equals_nominal(settings):
    nominal = _nominal_coords(settings)
    measured = _measured_from_nominal(nominal)

    res = compute_distance_shrinkage(measured, nominal)

    assert not res.quadrant.empty
    assert 'QP Shrinkage X (%)' in res.quadrant.columns
    assert 'QP Shrinkage Y (%)' in res.quadrant.columns
    assert 'Delta X (um)' in res.quadrant.columns
    assert 'Delta Y (um)' in res.quadrant.columns
    assert (res.quadrant['QP Shrinkage X (PPM)'].abs() < 1e-6).all()
    assert (res.quadrant['QP Shrinkage Y (PPM)'].abs() < 1e-6).all()
    assert (res.quadrant['QP Shrinkage X (%)'].abs() < 1e-9).all()
    assert (res.quadrant['QP Shrinkage Y (%)'].abs() < 1e-9).all()
    assert (res.quadrant['Delta X (um)'].abs() < 1e-6).all()
    assert (res.quadrant['Delta Y (um)'].abs() < 1e-6).all()
    assert res.full_panel.iloc[0]['Shrinkage X (FP)'] == pytest.approx(0.0)
    assert res.full_panel.iloc[0]['Shrinkage Y (FP)'] == pytest.approx(0.0)
    assert res.full_panel.iloc[0]['Shrinkage X (FP %)'] == pytest.approx(0.0)
    assert res.full_panel.iloc[0]['Shrinkage Y (FP %)'] == pytest.approx(0.0)


def test_distance_shrinkage_matches_quadrant_scales(settings):
    nominal = _nominal_coords(settings)
    x_scales = {'UL': 1.00010, 'LL': 1.00000, 'LR': 0.99990, 'UR': 1.00020}
    y_scales = {'UL': 0.99980, 'LL': 1.00005, 'LR': 1.00000, 'UR': 1.00010}
    measured = _measured_from_nominal(nominal, x_scales=x_scales, y_scales=y_scales)

    res = compute_distance_shrinkage(measured, nominal, outlier_ppm=50.0)
    q = res.quadrant.set_index('Quadrant')

    for quad, sx in x_scales.items():
        assert q.loc[quad, 'QP Shrinkage X (PPM)'] == pytest.approx((sx - 1.0) * 1_000_000.0, abs=0.2)
    for quad, sy in y_scales.items():
        assert q.loc[quad, 'QP Shrinkage Y (PPM)'] == pytest.approx((sy - 1.0) * 1_000_000.0, abs=0.2)

    fp = res.full_panel.iloc[0]
    expected_fp_x = sum((v - 1.0) * 1_000_000.0 for v in x_scales.values()) / 4.0
    expected_fp_y = sum((v - 1.0) * 1_000_000.0 for v in y_scales.values()) / 4.0
    assert fp['Shrinkage X (FP)'] == pytest.approx(expected_fp_x, abs=0.2)
    assert fp['Shrinkage Y (FP)'] == pytest.approx(expected_fp_y, abs=0.2)
    assert fp['Shrinkage X-Y Offset'] == pytest.approx(expected_fp_x - expected_fp_y, abs=0.2)

    assert not res.outliers.empty
