"""Pure numeric kernels for Core Shrinkage geometry.

Least-squares affine fits, outlier rejection, distortion classification —
no pandas frames in or out (except the dot-matching helper), no settings
lookup, no I/O. Imported by ``src.core_shrinkage_parser``, which keeps the
file parsing, frame building, and settings glue.
"""

import numpy as np
import pandas as pd

# All linear kernel units are mm; display/export units convert through these.
UM_PER_MM = 1000.0


def _matched_arrays(df: pd.DataFrame, nominal_coords: dict):
    """Pair measured dots with their nominal coords by label.

    Returns (nom_arr, meas_arr, locations, quadrants) — arrays are (N, 2).
    """
    nom_pts, meas_pts, locations, quadrants = [], [], [], []
    for _, row in df.iterrows():
        nom = nominal_coords.get(row['location'])
        if nom is None:
            continue
        nom_pts.append([nom['x'], nom['y']])
        meas_pts.append([row['coord_x'], row['coord_y']])
        locations.append(row['location'])
        quadrants.append(row['quadrant'])
    return (np.array(nom_pts), np.array(meas_pts), locations, quadrants)


def _affine_fit(nom_arr: np.ndarray, meas_arr: np.ndarray) -> dict:
    """Least-squares affine fit nominal → measured, decomposed via SVD.

    Single source of truth for the geometry maths so the full analysis and the
    outlier-robust refit share identical code. All linear units are mm.
    """
    n = len(nom_arr)
    A = np.column_stack([nom_arr, np.ones(n)])           # (N, 3)
    params_x, *_ = np.linalg.lstsq(A, meas_arr[:, 0], rcond=None)
    params_y, *_ = np.linalg.lstsq(A, meas_arr[:, 1], rcond=None)
    a, b, tx = params_x
    c, d, ty = params_y

    # QR-style decomposition  M = R(θ) · [[Sx, shear],[0, Sy]]  — preserves axis
    # identity (Sx is the X-axis scale, Sy the Y-axis), unlike SVD whose singular
    # values can swap X/Y under anisotropy. Rotation is tiny here, so on near-axis
    # data this matches the previous numbers while being correct in general.
    M = np.array([[a, b], [c, d]])
    Sx = float(np.hypot(a, c))
    theta = np.arctan2(c, a)
    theta_deg = float(np.degrees(theta))
    cos_t, sin_t = a / Sx, c / Sx
    b2 =  cos_t * b + sin_t * d
    d2 = -sin_t * b + cos_t * d
    Sy = float(d2)
    shear_deg = float(np.degrees(np.arctan2(b2, d2)))

    predicted = (M @ nom_arr.T).T + np.array([float(tx), float(ty)])
    res_xy    = meas_arr - predicted
    res_dist  = np.linalg.norm(res_xy, axis=1)
    res_rms   = float(np.sqrt(np.mean(res_dist ** 2)))

    return {
        'tx': float(tx), 'ty': float(ty), 'theta_deg': theta_deg,
        'Sx': Sx, 'Sy': Sy, 'shear_deg': shear_deg,
        'res_xy': res_xy, 'res_dist': res_dist, 'res_rms': res_rms,
        'M': M, 't': np.array([float(tx), float(ty)]),
    }


def _detect_outliers(nom_arr: np.ndarray, meas_arr: np.ndarray, outlier_um: float):
    """Iteratively reject the single worst dot whose residual (under the fit of
    the *current* inliers) exceeds outlier_um, refitting each round. One-at-a-time
    rejection prevents a single bad dot from smearing into its neighbours via
    least-squares — so exactly the offending dots are isolated.

    Returns (removed_indices: list[int], inlier_mask: np.ndarray[bool],
             robust_fit: dict).
    """
    n = len(nom_arr)
    inlier = np.ones(n, dtype=bool)
    removed: list = []
    fit = _affine_fit(nom_arr, meas_arr)
    while int(inlier.sum()) > 4:
        fit = _affine_fit(nom_arr[inlier], meas_arr[inlier])
        pred = (fit['M'] @ nom_arr.T).T + fit['t']
        resid_um = np.linalg.norm(meas_arr - pred, axis=1) * UM_PER_MM
        resid_um[~inlier] = -1.0                 # ignore already-removed dots
        worst = int(np.argmax(resid_um))
        if resid_um[worst] > outlier_um:
            inlier[worst] = False
            removed.append(worst)
        else:
            break
    return removed, inlier, fit


def _classify(Sx_ppm: float, Sy_ppm: float, max_res_um: float, cfg: dict) -> str:
    """Physically-sane distortion label (priority order). Rotation/translation
    are deliberately NOT used: rotation is fixturing (removed by the fit) and
    translation is just the datum offset."""
    if max_res_um > cfg['outlier_um']:
        return 'Local distortion / outlier dot(s)'
    if abs(Sx_ppm - Sy_ppm) > cfg['aniso_ppm']:
        return 'Anisotropic shrinkage'
    if abs(Sx_ppm) > cfg['shrink_ppm'] or abs(Sy_ppm) > cfg['shrink_ppm']:
        return 'Uniform shrinkage'
    return 'Stable'


def _to_ppm(scale: float) -> float:
    """Scale factor → shrinkage ppm (measured − nominal: − = shrink, + = expand)."""
    return (float(scale) - 1.0) * 1e6


def _rigid_fit(nom_arr: np.ndarray, meas_arr: np.ndarray):
    """Best-fit rotation + translation only (Kabsch, no scale). Returns (R, t)
    mapping nominal → measured. Because scale is NOT removed, the leftover
    deviation (measured − R·nom − t) shows the panel's expansion/shrink outward."""
    nc = nom_arr.mean(axis=0)
    mc = meas_arr.mean(axis=0)
    H = (nom_arr - nc).T @ (meas_arr - mc)
    U, _, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1.0, d]) @ U.T
    t = mc - R @ nc
    return R, t


def _classify_vector(dx: float, dy: float, px: float, py: float,
                     center, stable_um: float = 3.0) -> str:
    """Label a per-dot displacement (µm) relative to the panel centre:
    expansion (outward) / contraction (inward) / twist (tangential) / stable."""
    mag = float(np.hypot(dx, dy))
    if mag < stable_um:
        return 'stable'
    rx, ry = px - center[0], py - center[1]
    rnorm = float(np.hypot(rx, ry))
    if rnorm < 1e-9:
        return 'stable'
    rhat = (rx / rnorm, ry / rnorm)
    radial = dx * rhat[0] + dy * rhat[1]
    tang   = dx * (-rhat[1]) + dy * rhat[0]
    if abs(radial) >= abs(tang):
        return 'expansion' if radial > 0 else 'contraction'
    return 'twist'
