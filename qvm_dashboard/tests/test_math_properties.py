"""Property tests for the pure shrinkage-math kernels.

Identity / recovery / priority properties that must hold regardless of
implementation details. Complements the scenario tests in
test_core_shrinkage.py (which drive the kernels through fixtures).
"""

import numpy as np
import pandas as pd
import pytest

from src.core_shrinkage_math import (
    _affine_fit,
    _classify,
    _classify_vector,
    _detect_outliers,
    _matched_arrays,
    _rigid_fit,
    _to_ppm,
)

NOM = np.array(
    [
        [0.0, 0.0],
        [100.0, 0.0],
        [0.0, 100.0],
        [100.0, 100.0],
        [50.0, 50.0],
        [25.0, 75.0],
        [75.0, 25.0],
        [50.0, 0.0],
    ]
)
CFG = {"outlier_um": 10.0, "aniso_ppm": 50.0, "shrink_ppm": 100.0}


def test_affine_identity_fit():
    fit = _affine_fit(NOM, NOM.copy())
    assert fit["tx"] == pytest.approx(0.0, abs=1e-9)
    assert fit["ty"] == pytest.approx(0.0, abs=1e-9)
    assert fit["Sx"] == pytest.approx(1.0)
    assert fit["Sy"] == pytest.approx(1.0)
    assert fit["theta_deg"] == pytest.approx(0.0, abs=1e-9)
    assert fit["res_rms"] == pytest.approx(0.0, abs=1e-9)
    np.testing.assert_allclose(fit["M"], np.eye(2), atol=1e-9)


def test_affine_recovers_known_transform():
    theta = np.radians(0.05)
    R = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    M_true = R @ np.diag([1.0002, 0.9998])
    t_true = np.array([0.5, -0.3])
    meas = (M_true @ NOM.T).T + t_true
    fit = _affine_fit(NOM, meas)
    np.testing.assert_allclose(fit["M"], M_true, atol=1e-9)
    np.testing.assert_allclose(fit["t"], t_true, atol=1e-9)
    assert fit["res_rms"] == pytest.approx(0.0, abs=1e-9)


def test_to_ppm_zero_and_linear():
    assert _to_ppm(1.0) == 0.0
    assert _to_ppm(1.0002) == pytest.approx(200.0)
    assert _to_ppm(0.9998) == pytest.approx(-200.0)


def test_rigid_identity_fit():
    R, t = _rigid_fit(NOM, NOM.copy())
    np.testing.assert_allclose(R, np.eye(2), atol=1e-9)
    np.testing.assert_allclose(t, np.zeros(2), atol=1e-9)


def test_rigid_recovers_rotation_translation():
    theta = np.radians(2.0)
    R_true = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    t_true = np.array([1.5, -2.5])
    meas = (R_true @ NOM.T).T + t_true
    R, t = _rigid_fit(NOM, meas)
    np.testing.assert_allclose(R, R_true, atol=1e-9)
    np.testing.assert_allclose(t, t_true, atol=1e-9)


def test_classify_priority_order():
    assert _classify(0.0, 0.0, 5.0, CFG) == "Stable"
    assert _classify(200.0, 200.0, 5.0, CFG) == "Uniform shrinkage"
    assert _classify(0.0, 200.0, 5.0, CFG) == "Anisotropic shrinkage"
    # Local distortion outranks everything, even huge uniform shrink.
    assert _classify(5000.0, 5000.0, 20.0, CFG) == "Local distortion / outlier dot(s)"
    # Anisotropy outranks uniform shrink.
    assert _classify(0.0, 200.0, 5.0, CFG) == "Anisotropic shrinkage"


def test_classify_vector_directions():
    center = (50.0, 50.0)
    # Dots east of centre: +x displacement is outward.
    assert _classify_vector(10.0, 0.0, 90.0, 50.0, center) == "expansion"
    assert _classify_vector(-10.0, 0.0, 90.0, 50.0, center) == "contraction"
    assert _classify_vector(0.0, 10.0, 90.0, 50.0, center) == "twist"
    # Below the stability floor everything is stable.
    assert _classify_vector(1.0, 1.0, 90.0, 50.0, center) == "stable"
    # A dot exactly at the centre has no direction.
    assert _classify_vector(10.0, 0.0, 50.0, 50.0, center) == "stable"


def test_detect_outliers_clean_data():
    meas = NOM * 1.0001 + np.array([0.1, 0.1])
    removed, inlier, _ = _detect_outliers(NOM, meas, outlier_um=50.0)
    assert removed == []
    assert bool(inlier.all())


def test_detect_outliers_isolates_single_bad_dot():
    meas = NOM.copy()
    meas[3] += np.array([1.0, 0.0])  # 1 mm = 1000 um off
    removed, inlier, _ = _detect_outliers(NOM, meas, outlier_um=50.0)
    assert removed == [3]
    assert inlier.tolist() == [True, True, True, False, True, True, True, True]


def test_matched_arrays_skips_unknown_locations():
    df = pd.DataFrame(
        {
            "location": ["UL1", "XX9"],
            "coord_x": [1.0, 2.0],
            "coord_y": [3.0, 4.0],
            "quadrant": ["Q1", "Q2"],
        }
    )
    nom_arr, meas_arr, locations, _ = _matched_arrays(df, {"UL1": {"x": 0.0, "y": 0.0}})
    assert locations == ["UL1"]
    assert len(nom_arr) == 1
    np.testing.assert_allclose(meas_arr, [[1.0, 3.0]])
