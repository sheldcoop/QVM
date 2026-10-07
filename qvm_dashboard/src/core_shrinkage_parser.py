"""
Parser for Core Shrinkage measurement files.

File format: circle-coordinate-only text — no Distance/SC/DX/DY blocks.

Front files contain circles named 'Pad_<quadrant>_<num>' (e.g. Pad_LL_1).
Back files contain circles named '<quadrant>_<num>' (e.g. LL_1).
Both follow the same coordinate block structure:

    Circle: [Pad_]<quadrant>_<num>(ID:<n>, From <pts> Pts.)
         Coord. X = <value>
         Coord. Y = <value>
         Diameter = <value>
"""

import os
import re
import logging
from typing import Dict, Optional

import numpy as np
import pandas as pd

# Reuse the panel / points regexes already defined in the QVM parser rather than
# re-declaring them, keeping a single source of truth for those patterns.
from src.parser import _PANEL_RE, _PTS_RE

# Pure numeric kernels live in src.core_shrinkage_math; re-exported here so
# existing `from src.core_shrinkage_parser import _matched_arrays` callers
# (and tests) keep working.
from src.core_shrinkage_math import (
    _affine_fit,
    _classify,
    _classify_vector,
    _detect_outliers,
    _matched_arrays,
    _rigid_fit,
    _to_ppm,
)

logger = logging.getLogger(__name__)

_CIRCLE_RE = re.compile(r'Circle:\s*(?:Pad_)?([A-Z]{2})_(\d+)', re.IGNORECASE)


# ---------------------------------------------------------------------------
# Filename detection
# ---------------------------------------------------------------------------

def parse_cs_filename(filename: str) -> Dict[str, Optional[str]]:
    """Detect a Core Shrinkage file and return panel / layer metadata.

    Returns:
        {
            'is_core_shrinkage': bool,
            'Panel Number': str | 'Unknown',
            'layer': 'Front' | 'Back' | 'Unknown',
        }
    """
    stem  = os.path.splitext(os.path.basename(filename))[0]
    lower = stem.lower()

    is_cs = 'core_shrinkage' in lower or 'core shrinkage' in lower

    panel_m = _PANEL_RE.search(stem)
    panel   = panel_m.group(1) if panel_m else 'Unknown'

    if 'front' in lower:
        layer = 'Front'
    elif 'back' in lower:
        layer = 'Back'
    else:
        layer = 'Unknown'

    return {'is_core_shrinkage': is_cs, 'Panel Number': panel, 'layer': layer}


# ---------------------------------------------------------------------------
# Content parser
# ---------------------------------------------------------------------------

def parse_core_shrinkage_content(content: str, layer: str) -> pd.DataFrame:
    """Parse a Core Shrinkage circle-coordinate file into a DataFrame.

    Args:
        content: Raw file text.
        layer:   'Front' or 'Back' (determined by the caller from the filename).

    Returns:
        DataFrame with columns: location, quadrant, point_num, coord_x, coord_y,
        diameter, pts_count, layer, Process.
    """
    rows = []
    state = 'IDLE'   # IDLE → X → Y → DIAM
    current_loc = current_quad = current_num = current_pts = None
    coord_x = coord_y = None

    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue

        if 'Circle:' in line:
            m = _CIRCLE_RE.search(line)
            if m:
                current_quad = m.group(1).upper()
                current_num  = int(m.group(2))
                current_loc  = f'{current_quad}_{current_num}'
                pts_m        = _PTS_RE.search(line)
                current_pts  = int(pts_m.group(1)) if pts_m else None
                state        = 'X'
            else:
                state = 'IDLE'
            continue

        if state == 'IDLE' or '=' not in line:
            continue

        try:
            val = float(line.split('=', 1)[1].strip())
        except ValueError:
            continue

        if state == 'X' and 'Coord. X' in line:
            coord_x = val
            state   = 'Y'
        elif state == 'Y' and 'Coord. Y' in line:
            coord_y = val
            state   = 'DIAM'
        elif state == 'DIAM' and 'Diameter' in line:
            rows.append({
                'location':  current_loc,
                'quadrant':  current_quad,
                'point_num': current_num,
                'coord_x':   coord_x,
                'coord_y':   coord_y,
                'diameter':  val,
                'pts_count': current_pts,
                'layer':     layer,
                'Process':   'Core Shrinkage',
            })
            state = 'IDLE'

    if not rows:
        logger.warning('parse_core_shrinkage_content: no circles parsed from %s layer', layer)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Display-frame builders (shared by the Streamlit view and the Excel export so
# the on-screen table and the exported sheet are built exactly once, from one
# definition). Pure pandas — no streamlit/openpyxl, so neither import cycles.
# ---------------------------------------------------------------------------

def sort_by_grid(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by grid_id ascending (11,12,…,44 → anticlockwise UL→LL→LR→UR).

    No-op when grid_id is absent, so rows keep their incoming (file) order as a
    fallback. Rows with an unmapped (NaN) grid_id sort last but are retained.
    """
    if df.empty or 'grid_id' not in df.columns:
        return df
    return df.sort_values('grid_id', na_position='last').reset_index(drop=True)


def layer_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Single-layer display frame: Quarter | Grid | X | Y."""
    out  = sort_by_grid(df)
    cols = [c for c in ['quadrant', 'grid_id', 'coord_x', 'coord_y'] if c in out.columns]
    disp = out[cols].rename(columns={
        'quadrant': 'Quarter', 'grid_id': 'Grid', 'coord_x': 'X', 'coord_y': 'Y'})
    for c in ('X', 'Y'):
        if c in disp.columns:
            disp[c] = disp[c].round(6)
    return disp


def both_frame(front: pd.DataFrame, back: pd.DataFrame) -> pd.DataFrame:
    """Side-by-side frame: Quarter | Grid | Front X | Front Y | Back X | Back Y.

    Merges on `location` (always emitted by the parser, unique per fiducial), so
    a fiducial with an unmapped/NaN grid_id is still aligned and retained. Grid
    and Quarter are carried from the Front side; grid is used only for sorting.
    """
    merge_keys = ['location']
    keep_front = merge_keys + [c for c in ['quadrant', 'grid_id', 'coord_x', 'coord_y'] if c in front.columns]
    keep_back  = merge_keys + [c for c in ['coord_x', 'coord_y'] if c in back.columns]

    merged = pd.merge(front[keep_front], back[keep_back], on=merge_keys, suffixes=('_front', '_back'))
    merged = sort_by_grid(merged)

    disp = merged.rename(columns={
        'quadrant':      'Quarter',
        'grid_id':       'Grid',
        'coord_x_front': 'Front X',
        'coord_y_front': 'Front Y',
        'coord_x_back':  'Back X',
        'coord_y_back':  'Back Y',
    })
    cols = [c for c in ['Quarter', 'Grid', 'Front X', 'Front Y', 'Back X', 'Back Y'] if c in disp.columns]
    disp = disp[cols].copy()
    for c in ('Front X', 'Front Y', 'Back X', 'Back Y'):
        if c in disp.columns:
            disp[c] = disp[c].round(6)
    return disp


# ---------------------------------------------------------------------------
# QP Shrinkage — per-quadrant pitch measurements vs. nominal design distances.
# Formulas decoded from Core_Shrinkage_Calculation.xlsx:
#   (label, sign, pt_a, pt_b, coord_col, nominal_pitch_mm)
# QP Shrinkage = sign*(measured[pt_a] − measured[pt_b]) − nominal_pitch
# ---------------------------------------------------------------------------

_QP_NOMINAL_X: float = 200.65   # nominal X pitch within any quadrant (mm)
_QP_NOMINAL_Y: float = 235.75   # nominal Y pitch within any quadrant (mm)

_QP_FORMULAS: Dict = {
    'UL': [
        ('X1', -1, 1, 4, 'coord_x', _QP_NOMINAL_X),
        ('X2', -1, 2, 3, 'coord_x', _QP_NOMINAL_X),
        ('Y1', +1, 1, 2, 'coord_y', _QP_NOMINAL_Y),
        ('Y2', +1, 4, 3, 'coord_y', _QP_NOMINAL_Y),
    ],
    'LL': [
        ('X1', -1, 1, 4, 'coord_x', _QP_NOMINAL_X),
        ('X2', -1, 2, 3, 'coord_x', _QP_NOMINAL_X),
        ('Y1', -1, 2, 1, 'coord_y', _QP_NOMINAL_Y),
        ('Y2', -1, 3, 4, 'coord_y', _QP_NOMINAL_Y),
    ],
    'LR': [
        ('X1', +1, 4, 1, 'coord_x', _QP_NOMINAL_X),
        ('X2', +1, 3, 2, 'coord_x', _QP_NOMINAL_X),
        ('Y1', -1, 2, 1, 'coord_y', _QP_NOMINAL_Y),
        ('Y2', -1, 3, 4, 'coord_y', _QP_NOMINAL_Y),
    ],
    'UR': [
        ('X1', +1, 4, 1, 'coord_x', _QP_NOMINAL_X),
        ('X2', +1, 3, 2, 'coord_x', _QP_NOMINAL_X),
        ('Y1', +1, 1, 2, 'coord_y', _QP_NOMINAL_Y),
        ('Y2', +1, 4, 3, 'coord_y', _QP_NOMINAL_Y),
    ],
}


def compute_qp_shrinkage(df: pd.DataFrame) -> pd.DataFrame:
    """Compute QP shrinkage for one layer vs. nominal design pitch distances.

    Returns a 4-row DataFrame: Quadrant | X1 | X2 | Y1 | Y2 (all in mm,
    negative = panel shrank). Missing fiducials yield NaN for that cell.
    Returns empty DataFrame if df is empty.
    """
    if df.empty:
        return pd.DataFrame()

    loc_map = df.set_index('location')[['coord_x', 'coord_y']].to_dict('index')

    rows = []
    for quad, formulas in _QP_FORMULAS.items():
        row: Dict = {'Quadrant': quad}
        for label, sign, pt_a, pt_b, col, nominal in formulas:
            loc_a = f'{quad}_{pt_a}'
            loc_b = f'{quad}_{pt_b}'
            try:
                val_a = loc_map[loc_a][col]
                val_b = loc_map[loc_b][col]
                row[label] = round(sign * (val_a - val_b) - nominal, 6)
            except KeyError:
                row[label] = float('nan')
        rows.append(row)

    return pd.DataFrame(rows)


def compute_scale_factor(df: pd.DataFrame) -> pd.DataFrame:
    """Compute X/Y scale factors per quadrant from QP pitch measurements.

    Returns a 5-row DataFrame (4 quadrants + Overall):
    Quadrant | X Scale | Y Scale | X Shrinkage (ppm) | Y Shrinkage (ppm)

    Scale = measured_pitch / nominal_pitch; ppm = (scale − 1) × 1,000,000.
    Negative ppm means the panel shrank; positive means it expanded
    (measured − nominal, matching the registration path and the customer
    reference workbook).
    Returns empty DataFrame if QP data is unavailable.
    """
    qp = compute_qp_shrinkage(df)
    if qp.empty:
        return pd.DataFrame()

    rows = []
    for _, r in qp.iterrows():
        x1_s = (r['X1'] + _QP_NOMINAL_X) / _QP_NOMINAL_X if pd.notna(r['X1']) else float('nan')
        x2_s = (r['X2'] + _QP_NOMINAL_X) / _QP_NOMINAL_X if pd.notna(r['X2']) else float('nan')
        y1_s = (r['Y1'] + _QP_NOMINAL_Y) / _QP_NOMINAL_Y if pd.notna(r['Y1']) else float('nan')
        y2_s = (r['Y2'] + _QP_NOMINAL_Y) / _QP_NOMINAL_Y if pd.notna(r['Y2']) else float('nan')

        x_scale = pd.Series([x1_s, x2_s]).mean()
        y_scale = pd.Series([y1_s, y2_s]).mean()

        rows.append({
            'Quadrant':           r['Quadrant'],
            'X Scale':            round(float(x_scale), 6),
            'Y Scale':            round(float(y_scale), 6),
            'X Shrinkage (ppm)':  round(_to_ppm(x_scale), 1),
            'Y Shrinkage (ppm)':  round(_to_ppm(y_scale), 1),
        })

    result = pd.DataFrame(rows)
    overall = pd.DataFrame([{
        'Quadrant':           'Overall',
        'X Scale':            round(float(result['X Scale'].mean()), 6),
        'Y Scale':            round(float(result['Y Scale'].mean()), 6),
        'X Shrinkage (ppm)':  round(float(result['X Shrinkage (ppm)'].mean()), 1),
        'Y Shrinkage (ppm)':  round(float(result['Y Shrinkage (ppm)'].mean()), 1),
    }])
    return pd.concat([result, overall], ignore_index=True)


# ---------------------------------------------------------------------------
# Affine Analysis — decompose nominal→measured mapping into interpretable
# engineering components: translation, rotation, anisotropic scale, shear.
#
# Three zoom levels build on this fit:
#   global  (this affine, headline ppm)  → compute_shrinkage_summary
#   quadrant (QP pitch, uniformity)       → compute_qp_shrinkage
#   per-dot  (residual, defect locator)   → analysis['residuals'] + flag_outliers
# ---------------------------------------------------------------------------

# Classifier / spec defaults — overridden by settings['CORE_SHRINKAGE'].
_CS_DEFAULTS = {
    'outlier_um':        50.0,   # per-dot residual above this = outlier / remeasure
    'rotation_warn_deg': 0.30,   # rotation above this is flagged (fixturing)
    'aniso_ppm':         100.0,  # |Sx_ppm − Sy_ppm| above this = anisotropic
    'shrink_ppm':        50.0,   # |scale| above this counts as real shrinkage
}


def _cs_cfg(settings: Optional[dict]) -> dict:
    """Merge CORE_SHRINKAGE settings over the built-in classifier defaults."""
    cfg = dict(_CS_DEFAULTS)
    if settings:
        cfg.update({k: settings.get('CORE_SHRINKAGE', {}).get(k, v)
                    for k, v in _CS_DEFAULTS.items()})
    return cfg


def analyze_layer(df: pd.DataFrame, nominal_coords: dict,
                  settings: Optional[dict] = None) -> dict:
    """Single-pass geometry analysis for one layer — the one place the matching,
    affine fit, outlier detection, and rigid fit run. Every Core-Shrinkage product
    (summary, residuals, deviation field, coordinate table) derives from this, so
    the heavy maths happen exactly once per layer per render.

    Returns {} if fewer than 4 fiducials can be matched, or if a fitted
    axis scale has collapsed (non-finite, or below 1% — a stuck probe or a
    mirrored/collapsed axis). Near zero the ppm mapping is singular (a 3e-16
    scale prints as a −1,000,000 ppm "headline"), so refusing to report is
    safer than printing authoritative-looking garbage. Large expansion stays
    reported: it is well-conditioned and the operator's judgment call
    (a numbering swap, e.g. Sy≈0.03 with huge residuals, keeps its
    outlier/distortion diagnostic).
    Otherwise a dict of raw products: nom_arr, meas_arr, locations,
    quadrants, cfg, fit (all-dot affine), fit_robust (outlier-excluded
    affine), removed, inlier, outliers, rigid_R, rigid_t, center, grid_map,
    n_points.
    """
    if df is None or df.empty or not nominal_coords:
        return {}
    nom_arr, meas_arr, locations, quadrants = _matched_arrays(df, nominal_coords)
    n = len(nom_arr)
    if n < 4:
        return {}
    cfg = _cs_cfg(settings)
    fit = _affine_fit(nom_arr, meas_arr)
    removed, inlier, fit_robust = _detect_outliers(nom_arr, meas_arr, cfg['outlier_um'])
    for _fit in (fit, fit_robust):
        sx, sy = _fit['Sx'], _fit['Sy']
        if not (np.isfinite(sx) and np.isfinite(sy) and sx >= 0.01 and sy >= 0.01):
            logger.warning(
                'analyze_layer: collapsed fit (Sx=%r, Sy=%r, n=%d); '
                'refusing to report shrinkage.', sx, sy, n)
            return {}
    R, t = _rigid_fit(nom_arr, meas_arr)
    grid_map = (df.set_index('location')['grid_id'].to_dict()
                if 'grid_id' in df.columns else {})
    return {
        'nom_arr': nom_arr, 'meas_arr': meas_arr,
        'locations': locations, 'quadrants': quadrants, 'cfg': cfg,
        'fit': fit, 'fit_robust': fit_robust,
        'removed': removed, 'inlier': inlier,
        'outliers': [locations[i] for i in removed],
        'rigid_R': R, 'rigid_t': t, 'center': nom_arr.mean(axis=0),
        'grid_map': grid_map, 'n_points': n,
    }


def _sort_by_grid_map(df: pd.DataFrame, grid_map: dict) -> pd.DataFrame:
    """Sort a per-dot frame by grid_id (via grid_map on its `location` column)."""
    if not grid_map or 'location' not in df.columns:
        return df
    out = df.copy()
    out['_g'] = out['location'].map(grid_map)
    return out.sort_values('_g', na_position='last').drop(columns='_g').reset_index(drop=True)


def compute_affine_analysis(df: pd.DataFrame, nominal_coords: dict,
                            settings: Optional[dict] = None,
                            analysis: Optional[dict] = None) -> dict:
    """Fit a best-fit affine transform from nominal → measured fiducial positions.

    Decomposes the transform into: Translation X/Y, Rotation (°), X/Y Scale,
    X/Y Shrinkage (ppm), Shear (°), and per-fiducial residuals that capture
    any non-linear / non-uniform distortion the affine model cannot explain.

    Args:
        df:             Single-layer DataFrame from parse_core_shrinkage_content
                        (must contain location, quadrant, coord_x, coord_y).
        nominal_coords: CORE_SHRINKAGE.NOMINAL_COORDS dict {loc: {x, y}}.
        settings:       Full settings dict (optional) — supplies classifier
                        thresholds from CORE_SHRINKAGE; defaults used otherwise.

    Returns:
        {
          'params':    DataFrame — Parameter | Value | Unit
          'residuals': DataFrame — location | Quadrant | Res X (mm) | Res Y (mm)
                                              | Res Distance (mm)
          'pattern':   str  — dominant distortion mode label
          'n_points':  int  — number of matched fiducials used in the fit
          'theta_deg': float — rotation angle (degrees); used for twist comparison
        }
        Returns empty dict if fewer than 4 fiducials can be matched.

    `analysis` (optional) — a precomputed `analyze_layer` result to reuse, so the
    fit isn't recomputed when the caller already has it.
    """
    a = analysis or analyze_layer(df, nominal_coords, settings)
    if not a:
        return {}

    fit       = a['fit']
    locations = a['locations']
    quadrants = a['quadrants']
    res_xy    = fit['res_xy']
    res_dist  = fit['res_dist']
    Sx_ppm    = _to_ppm(fit['Sx'])
    Sy_ppm    = _to_ppm(fit['Sy'])
    max_res_um = float(np.max(res_dist)) * 1000.0

    params_df = pd.DataFrame([
        {'Parameter': 'Translation X',  'Value': round(fit['tx'], 6),        'Unit': 'mm'},
        {'Parameter': 'Translation Y',  'Value': round(fit['ty'], 6),        'Unit': 'mm'},
        {'Parameter': 'Rotation',        'Value': round(fit['theta_deg'], 6), 'Unit': '°'},
        {'Parameter': 'X Scale',         'Value': round(fit['Sx'], 6),        'Unit': '×'},
        {'Parameter': 'Y Scale',         'Value': round(fit['Sy'], 6),        'Unit': '×'},
        {'Parameter': 'X Shrinkage',     'Value': round(Sx_ppm, 2),           'Unit': 'ppm'},
        {'Parameter': 'Y Shrinkage',     'Value': round(Sy_ppm, 2),           'Unit': 'ppm'},
        {'Parameter': 'Shear',           'Value': round(fit['shear_deg'], 6), 'Unit': '°'},
        {'Parameter': 'Residual RMS',    'Value': round(fit['res_rms'], 6),   'Unit': 'mm'},
    ])

    res_df = pd.DataFrame({
        'location':           locations,
        'Quadrant':           quadrants,
        'Res X (mm)':        [round(float(v), 6) for v in res_xy[:, 0]],
        'Res Y (mm)':        [round(float(v), 6) for v in res_xy[:, 1]],
        'Res Distance (mm)': [round(float(v), 6) for v in res_dist],
    })
    res_df = _sort_by_grid_map(res_df, a['grid_map'])

    return {
        'params':    params_df,
        'residuals': res_df,
        'pattern':   _classify(Sx_ppm, Sy_ppm, max_res_um, a['cfg']),
        'n_points':  a['n_points'],
        'theta_deg': fit['theta_deg'],
        'outliers':  a['outliers'],
    }


# ---------------------------------------------------------------------------
# Outlier flagging + headline summary + Front↔Back registration + µm display
# helpers. One source each, reused by the view and the Excel export.
# ---------------------------------------------------------------------------

def flag_outliers(analysis: dict, outlier_um: float = 50.0) -> pd.DataFrame:
    """Add an `Outlier` bool to the affine residuals frame, using the iterative
    detection carried on the analysis (exactly the offending dots — not every dot
    a single bad point smears into). Returns empty frame if analysis is empty.

    `outlier_um` is accepted for API symmetry; detection already ran with the
    configured threshold inside compute_affine_analysis.
    """
    if not analysis:
        return pd.DataFrame()
    res = analysis['residuals'].copy()
    res['Outlier'] = res['location'].isin(analysis.get('outliers', []))
    return res


def compute_shrinkage_summary(df: pd.DataFrame, nominal_coords: dict,
                              settings: Optional[dict] = None,
                              analysis: Optional[dict] = None) -> dict:
    """Headline (global) shrinkage numbers for one layer — the single source
    feeding the Quality-Control cards and the Excel summary sheet.

    Reports the all-dot scale AND an outlier-robust refit (fit excluding dots
    whose residual exceeds `outlier_um`) so a bad pad is visible without being
    silently dropped from the data. `analysis` (optional) reuses an
    `analyze_layer` result. Returns {} if fewer than 4 fiducials match.
    """
    a = analysis or analyze_layer(df, nominal_coords, settings)
    if not a:
        return {}
    fit, fit_r = a['fit'], a['fit_robust']
    res_um = fit['res_dist'] * 1000.0

    return {
        'Sx_ppm':          round(_to_ppm(fit['Sx']), 1),
        'Sy_ppm':          round(_to_ppm(fit['Sy']), 1),
        'Sx_ppm_robust':   round(_to_ppm(fit_r['Sx']), 1),
        'Sy_ppm_robust':   round(_to_ppm(fit_r['Sy']), 1),
        'rotation_deg':    round(fit['theta_deg'], 4),
        'shear_deg':       round(fit['shear_deg'], 4),
        'residual_rms_um': round(fit['res_rms'] * 1000.0, 1),
        'max_residual_um': round(float(res_um.max()), 1),
        'n_outliers':      len(a['outliers']),
        'outliers':        a['outliers'],
        'n_points':        a['n_points'],
    }


def compute_deviation_field(df: pd.DataFrame, nominal_coords: dict,
                            settings: Optional[dict] = None,
                            field: str = 'total',
                            analysis: Optional[dict] = None) -> pd.DataFrame:
    """Per-dot displacement field for the Distortion Map (and 3D warp). One source
    feeding both views.

    field='total'    → measured − rigid(nominal): keeps scale, so outward arrows
                       show expansion (panel larger than CAM).
    field='residual' → the affine residual: scale removed, isolates local warp /
                       bad dots.

    `analysis` (optional) reuses an `analyze_layer` result.
    Returns: location | Quadrant | nom_x | nom_y | dev_x_um | dev_y_um | mag_um
             | klass | outlier   (empty frame if < 4 matched fiducials).
    """
    a = analysis or analyze_layer(df, nominal_coords, settings)
    if not a:
        return pd.DataFrame()
    nom_arr, meas_arr = a['nom_arr'], a['meas_arr']
    locations, quadrants = a['locations'], a['quadrants']

    if field == 'residual':
        dev = a['fit']['res_xy']
    else:  # 'total'
        dev = meas_arr - ((a['rigid_R'] @ nom_arr.T).T + a['rigid_t'])

    outlier_locs = set(a['outliers'])
    center = a['center']

    dev_um = dev * 1000.0
    rows = []
    for i, loc in enumerate(locations):
        dxu, dyu = float(dev_um[i, 0]), float(dev_um[i, 1])
        rows.append({
            'location':  loc,
            'Quadrant':  quadrants[i],
            'nom_x':     float(nom_arr[i, 0]),
            'nom_y':     float(nom_arr[i, 1]),
            'dev_x_um':  round(dxu, 1),
            'dev_y_um':  round(dyu, 1),
            'mag_um':    round(float(np.hypot(dxu, dyu)), 1),
            'klass':     _classify_vector(dxu, dyu, nom_arr[i, 0], nom_arr[i, 1], center),
            'outlier':   loc in outlier_locs,
        })
    out = pd.DataFrame(rows)
    out.loc[out['outlier'], 'klass'] = 'outlier'
    return out


def compute_centered_deviation_table(df: pd.DataFrame, nominal_coords: dict,
                                     settings: Optional[dict] = None,
                                     analysis: Optional[dict] = None) -> pd.DataFrame:
    """Per-dot coordinate table matching the Excel mental model: CAM nominal vs
    raw physical vs physical re-expressed in the CAM datum (inverse rigid
    transform), with ΔX/ΔY/Δdist in µm and a SUMMARY (RMS) row.

    This is the same total deviation as compute_deviation_field, shown
    coordinate-by-coordinate. No per-coordinate "local ppm" — that estimate is
    noise-dominated for dots near a zero axis; the Scale-Factor tab is the
    authoritative ppm. Returns empty frame if < 4 matched fiducials.
    """
    a = analysis or analyze_layer(df, nominal_coords, settings)
    if not a:
        return pd.DataFrame()

    nom_arr, meas_arr = a['nom_arr'], a['meas_arr']
    R, t = a['rigid_R'], a['rigid_t']
    centered = (R.T @ (meas_arr - t).T).T        # physical → CAM datum: Rᵀ·(meas − t)
    dev_um  = (centered - nom_arr) * 1000.0
    dist_um = np.hypot(dev_um[:, 0], dev_um[:, 1])

    out = pd.DataFrame({
        'location':       a['locations'],
        'Quadrant':       a['quadrants'],
        'CAM Nominal X':  nom_arr[:, 0].round(6),
        'CAM Nominal Y':  nom_arr[:, 1].round(6),
        'Physical X':     meas_arr[:, 0].round(6),
        'Physical Y':     meas_arr[:, 1].round(6),
        'Centered X':     centered[:, 0].round(6),
        'Centered Y':     centered[:, 1].round(6),
        'ΔX (µm)':        dev_um[:, 0].round(1),
        'ΔY (µm)':        dev_um[:, 1].round(1),
        'Δ Dist (µm)':    dist_um.round(1),
    })
    out = _sort_by_grid_map(out, a['grid_map'])
    if a['grid_map']:
        out.insert(2, 'Grid', out['location'].map(a['grid_map']))

    # SUMMARY (RMS) row, assembled in one pass (no all-NA concat → no FutureWarning)
    summary = {c: '' for c in out.columns}
    summary['location']    = 'SUMMARY (RMS)'
    summary['Δ Dist (µm)'] = round(float(np.sqrt(np.mean(dist_um ** 2))), 1)
    return pd.concat([out, pd.DataFrame([summary])], ignore_index=True)


def compute_front_back_registration(front_df: pd.DataFrame,
                                    back_df: pd.DataFrame) -> pd.DataFrame:
    """Per-dot Front-pad vs Back-land overlay, in µm.

    Each layer is referenced to the same CAM, so the nominal cancels and this is
    the Front − Back coordinate difference per fiducial (the pad-to-land
    registration). Returns Quarter | Grid | ΔX (µm) | ΔY (µm) | Δ Dist (µm).
    """
    if front_df.empty or back_df.empty:
        return pd.DataFrame()

    keep_f = ['location', 'quadrant', 'coord_x', 'coord_y'] + (
        ['grid_id'] if 'grid_id' in front_df.columns else [])
    merged = pd.merge(front_df[keep_f], back_df[['location', 'coord_x', 'coord_y']],
                      on='location', suffixes=('_f', '_b'))
    merged = sort_by_grid(merged)

    dx_um = (merged['coord_x_f'] - merged['coord_x_b']) * 1000.0
    dy_um = (merged['coord_y_f'] - merged['coord_y_b']) * 1000.0
    out = pd.DataFrame({
        'Quarter':       merged['quadrant'],
        'Grid':          merged.get('grid_id'),
        'ΔX (µm)':       dx_um.round(1),
        'ΔY (µm)':       dy_um.round(1),
        'Δ Dist (µm)':   np.hypot(dx_um, dy_um).round(1),
    })
    return out


def qp_shrinkage_um(df: pd.DataFrame) -> pd.DataFrame:
    """QP pitch error in µm (the per-quadrant uniformity view). Same logic as
    compute_qp_shrinkage, just unit-converted for display/Excel."""
    qp = compute_qp_shrinkage(df)
    if qp.empty:
        return qp
    out = qp.copy()
    for c in ('X1', 'X2', 'Y1', 'Y2'):
        out[c] = (out[c] * 1000.0).round(1)
    return out.rename(columns={c: f'{c} (µm)' for c in ('X1', 'X2', 'Y1', 'Y2')})


def affine_residuals_um(analysis: dict, outlier_um: float = 50.0) -> pd.DataFrame:
    """Per-dot residual frame in µm with an Outlier flag (the defect locator)."""
    res = flag_outliers(analysis, outlier_um)
    if res.empty:
        return res
    out = pd.DataFrame({
        'location':       res['location'],
        'Quadrant':       res['Quadrant'],
        'Res X (µm)':     (res['Res X (mm)'] * 1000.0).round(1),
        'Res Y (µm)':     (res['Res Y (mm)'] * 1000.0).round(1),
        'Res Dist (µm)':  (res['Res Distance (mm)'] * 1000.0).round(1),
        'Outlier':        res['Outlier'],
    })
    return out


def summary_frame(summary: dict) -> pd.DataFrame:
    """Tidy 2-column (Metric | Value) frame from compute_shrinkage_summary, for
    the Global tab and the Excel CS Summary sheet."""
    if not summary:
        return pd.DataFrame()
    rows = [
        ('X Shrinkage (ppm)',        summary['Sx_ppm']),
        ('Y Shrinkage (ppm)',        summary['Sy_ppm']),
        ('X Shrinkage robust (ppm)', summary['Sx_ppm_robust']),
        ('Y Shrinkage robust (ppm)', summary['Sy_ppm_robust']),
        ('Rotation (°)',             summary['rotation_deg']),
        ('Shear (°)',                summary['shear_deg']),
        ('Residual RMS (µm)',        summary['residual_rms_um']),
        ('Max deviation (µm)',       summary['max_residual_um']),
        ('Outliers',                 summary['n_outliers']),
        ('Outlier dots',             ', '.join(summary['outliers']) or '—'),
        ('Fiducials used',           summary['n_points']),
    ]
    return pd.DataFrame(rows, columns=['Metric', 'Value'])
