"""
Diagnostics — root-cause analysis and CAM compensation calculations.

Pure computation: no charts, no Streamlit, no side-effects.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Iterable

# Panel geometry defaults (mm). Overridable from settings['DIAGNOSTICS'].
PANEL_CENTER_X = 255.0  # 510 mm panel width / 2
PANEL_CENTER_Y = 257.5  # 515 mm panel height / 2

# Confidence-band cutoffs used by diagnose_root_cause_confidence
CONFIDENCE_HIGH = 0.72
CONFIDENCE_MEDIUM = 0.45


def _coerce_numeric(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """In-place pd.to_numeric(errors='coerce') for each named column that exists."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def _get_valid_grid_ids(settings: Dict) -> set:
    from src.visuals import _GRID_PLOT_POSITIONS
    configured = {str(v) for v in settings.get('GRID_MAPPING', {}).values()}
    return configured or set(_GRID_PLOT_POSITIONS.keys())


def diagnose_root_cause_confidence(df: pd.DataFrame, settings: Dict) -> Dict[str, Any]:
    """
    Compute panel-level root cause confidence across four classes:
    Expansion, Shrinkage, Twist, Offset.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    coord_x_col = col_names.get('coord_x', 'Coord. X')
    coord_y_col = col_names.get('coord_y', 'Coord. Y')
    grid_col = col_names.get('grid_id', 'Grid ID')

    diagnostics = settings.get('DIAGNOSTICS', {})
    valid_grid_ids = _get_valid_grid_ids(settings)
    expected_points = len(valid_grid_ids)

    _empty = {
        'scores': {'Expansion': 0.0, 'Shrinkage': 0.0, 'Twist': 0.0, 'Offset': 0.0},
        'top_cause': 'N/A', 'top_probability': 0.0,
        'confidence': 0.0, 'confidence_band': 'Low',
        'stats': {
            'valid_points': 0, 'expected_points': expected_points,
            'missing_grid_count': 0, 'unknown_grid_ids': [],
            'mean_magnitude_um': 0.0, 'directional_coherence': 0.0,
            'data_quality': 0.0,
        },
    }

    if df.empty:
        return {**_empty, 'status': 'insufficient_data',
                'message': 'No data available for root cause diagnosis.',
                'reasons': ['No rows available in current filter scope.']}

    required_cols = [x_col, y_col, coord_x_col, coord_y_col, grid_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return {**_empty, 'status': 'insufficient_data',
                'message': f"Missing required column(s): {', '.join(missing_cols)}",
                'reasons': [f"Cannot diagnose without: {', '.join(missing_cols)}"]}

    df_work = df.copy()
    grid_series = df_work[grid_col]
    missing_grid_count = int(grid_series.isna().sum())
    numeric_grid = pd.to_numeric(grid_series, errors='coerce')
    grid_str = numeric_grid.dropna().astype(int).astype(str)
    unknown_grid_ids = sorted({gid for gid in grid_str.unique() if gid not in valid_grid_ids})

    df_work = _coerce_numeric(df_work, [grid_col, x_col, y_col, coord_x_col, coord_y_col])
    df_work = df_work.dropna(subset=[grid_col, x_col, y_col, coord_x_col, coord_y_col]).copy()
    df_work[grid_col] = df_work[grid_col].astype(int).astype(str)
    df_work = df_work[df_work[grid_col].isin(valid_grid_ids)].copy()

    _stats_base = {
        'expected_points': expected_points,
        'missing_grid_count': missing_grid_count,
        'unknown_grid_ids': unknown_grid_ids,
        'directional_coherence': 0.0,
        'data_quality': 0.0,
    }

    if df_work.empty:
        return {**_empty, 'status': 'insufficient_data',
                'message': 'No valid rows remain after data-quality filtering.',
                'reasons': ['All rows were missing required fields or had invalid Grid IDs.'],
                'stats': {**_empty['stats'], **_stats_base, 'valid_points': 0}}

    panel_center_x = float(diagnostics.get('panel_center_x', PANEL_CENTER_X))
    panel_center_y = float(diagnostics.get('panel_center_y', PANEL_CENTER_Y))
    min_signal_um = float(diagnostics.get('min_signal_um', 2.0))
    strength_scale_um = float(diagnostics.get('strength_scale_um', 12.0))
    score_sharpening_alpha = float(diagnostics.get('score_sharpening_alpha', 1.35))
    offset_primary_penalty = float(diagnostics.get('offset_primary_penalty', 0.7))

    dx = df_work[x_col].to_numpy(dtype=float)
    dy = df_work[y_col].to_numpy(dtype=float)
    coord_x = df_work[coord_x_col].to_numpy(dtype=float)
    coord_y = df_work[coord_y_col].to_numpy(dtype=float)

    err_mag = np.sqrt(dx ** 2 + dy ** 2)
    err_mag_um = err_mag * 1000.0
    pos_x = coord_x - panel_center_x
    pos_y = coord_y - panel_center_y
    pos_mag = np.sqrt(pos_x ** 2 + pos_y ** 2)

    safe_err = np.where(err_mag > 0, err_mag, 1.0)
    safe_pos = np.where(pos_mag > 0, pos_mag, 1.0)
    err_x_norm = dx / safe_err
    err_y_norm = dy / safe_err
    pos_x_norm = pos_x / safe_pos
    pos_y_norm = pos_y / safe_pos

    radial = (err_x_norm * pos_x_norm) + (err_y_norm * pos_y_norm)
    tangential = np.abs((err_x_norm * pos_y_norm) - (err_y_norm * pos_x_norm))

    strength = np.clip(err_mag_um / max(strength_scale_um, 1e-6), 0.0, 1.0)
    signal_mask = err_mag_um >= min_signal_um

    if not signal_mask.any():
        return {**_empty, 'status': 'insufficient_data',
                'message': 'Signal is too small for a confident diagnosis.',
                'reasons': ['All valid vectors are below minimum signal threshold (2 µm).'],
                'stats': {**_stats_base, 'valid_points': int(len(df_work)),
                          'mean_magnitude_um': float(np.mean(err_mag_um)) if len(err_mag_um) else 0.0,
                          'directional_coherence': 0.0, 'data_quality': 0.0}}

    radial_sig = radial[signal_mask]
    tangential_sig = tangential[signal_mask]
    strength_sig = strength[signal_mask]
    err_x_sig = err_x_norm[signal_mask]
    err_y_sig = err_y_norm[signal_mask]

    total_strength = float(np.sum(strength_sig))
    if total_strength <= 0:
        total_strength = float(len(strength_sig))
        strength_sig = np.ones_like(strength_sig)

    expansion_norm = float(np.sum(strength_sig * np.clip(radial_sig, 0.0, 1.0)) / total_strength)
    shrinkage_norm = float(np.sum(strength_sig * np.clip(-radial_sig, 0.0, 1.0)) / total_strength)
    twist_norm = float(np.sum(strength_sig * np.clip(tangential_sig, 0.0, 1.0)) / total_strength)

    mean_err_vector = np.array([np.mean(err_x_sig), np.mean(err_y_sig)])
    directional_coherence = float(np.clip(np.linalg.norm(mean_err_vector), 0.0, 1.0))
    primary_dominance = max(expansion_norm, shrinkage_norm, twist_norm)
    offset_norm = float(np.clip(
        directional_coherence * (1.0 - offset_primary_penalty * primary_dominance), 0.0, 1.0))

    alpha = max(score_sharpening_alpha, 1e-6)
    raw_scores = {
        'Expansion': max(expansion_norm, 1e-6) ** alpha,
        'Shrinkage': max(shrinkage_norm, 1e-6) ** alpha,
        'Twist': max(twist_norm, 1e-6) ** alpha,
        'Offset': max(offset_norm, 1e-6) ** alpha,
    }
    raw_total = float(sum(raw_scores.values()))
    scores = {name: (value / raw_total) for name, value in raw_scores.items()}
    sorted_scores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top_cause, top_probability = sorted_scores[0]
    second_probability = sorted_scores[1][1]
    separation = float(np.clip(top_probability - second_probability, 0.0, 1.0))

    probs = np.array(list(scores.values()), dtype=float)
    entropy = float(-np.sum(probs * np.log(np.clip(probs, 1e-12, 1.0))) / np.log(len(probs)))
    certainty = float(np.clip(1.0 - entropy, 0.0, 1.0))

    quad_masks = [
        (pos_x[signal_mask] < 0) & (pos_y[signal_mask] >= 0),
        (pos_x[signal_mask] < 0) & (pos_y[signal_mask] < 0),
        (pos_x[signal_mask] >= 0) & (pos_y[signal_mask] < 0),
        (pos_x[signal_mask] >= 0) & (pos_y[signal_mask] >= 0),
    ]

    def _top_cause_for_mask(mask: np.ndarray) -> str:
        if int(mask.sum()) == 0:
            return ''
        local_strength = strength_sig[mask]
        local_total = float(np.sum(local_strength))
        if local_total <= 0:
            local_strength = np.ones(int(mask.sum()), dtype=float)
            local_total = float(mask.sum())
        local_radial = radial_sig[mask]
        local_tangential = tangential_sig[mask]
        local_ex = float(np.sum(local_strength * np.clip(local_radial, 0.0, 1.0)) / local_total)
        local_sh = float(np.sum(local_strength * np.clip(-local_radial, 0.0, 1.0)) / local_total)
        local_tw = float(np.sum(local_strength * np.clip(local_tangential, 0.0, 1.0)) / local_total)
        local_off = float(np.clip(
            directional_coherence * (1.0 - offset_primary_penalty * max(local_ex, local_sh, local_tw)),
            0.0, 1.0))
        return max({'Expansion': local_ex, 'Shrinkage': local_sh,
                    'Twist': local_tw, 'Offset': local_off}, key=lambda k: {'Expansion': local_ex, 'Shrinkage': local_sh, 'Twist': local_tw, 'Offset': local_off}[k])

    quarter_top_causes = [c for c in (_top_cause_for_mask(m) for m in quad_masks) if c]
    if quarter_top_causes:
        agreement = sum(1 for c in quarter_top_causes if c == top_cause)
        stability = float(np.clip(agreement / len(quarter_top_causes), 0.0, 1.0))
    else:
        stability = 0.0

    valid_points = int(len(df_work))
    coverage = float(np.clip(valid_points / max(expected_points, 1), 0.0, 1.0))
    sample_quality = float(np.clip(valid_points / 10.0, 0.0, 1.0))
    unknown_penalty = 1.0 / (1.0 + 0.2 * len(unknown_grid_ids) + 0.08 * missing_grid_count)
    signal_quality = float(np.clip(np.mean(err_mag_um[signal_mask]) / 8.0, 0.0, 1.0))
    data_quality = float(np.clip(coverage * sample_quality * unknown_penalty, 0.0, 1.0))

    confidence = float(np.clip(
        (0.35 * top_probability + 0.30 * separation + 0.20 * certainty + 0.15 * stability)
        * data_quality * (0.6 + 0.4 * signal_quality),
        0.0, 1.0,
    ))
    confidence_band = 'High' if confidence >= CONFIDENCE_HIGH else (
        'Medium' if confidence >= CONFIDENCE_MEDIUM else 'Low')

    reasons = [
        f"Top cause signal: {top_cause} ({top_probability * 100:.1f}%).",
        f"Class certainty: {certainty * 100:.1f}% (entropy-adjusted).",
        f"Quarter stability: {stability * 100:.1f}% agreement.",
        f"Directional coherence: {directional_coherence * 100:.1f}%.",
        f"Coverage: {valid_points}/{expected_points} valid grid points.",
    ]
    if unknown_grid_ids:
        reasons.append(f"Unknown Grid IDs excluded: {', '.join(unknown_grid_ids)}.")
    if missing_grid_count > 0:
        reasons.append(f"Missing Grid IDs: {missing_grid_count} row(s).")

    return {
        'status': 'ok',
        'message': 'Diagnosis computed successfully.',
        'scores': scores,
        'top_cause': top_cause,
        'top_probability': top_probability,
        'confidence': confidence,
        'confidence_band': confidence_band,
        'reasons': reasons,
        'stats': {
            'valid_points': valid_points,
            'expected_points': expected_points,
            'missing_grid_count': missing_grid_count,
            'unknown_grid_ids': unknown_grid_ids,
            'mean_magnitude_um': float(np.mean(err_mag_um[signal_mask])) if signal_mask.any() else 0.0,
            'directional_coherence': directional_coherence,
            'certainty': certainty,
            'stability': stability,
            'data_quality': data_quality,
        },
    }


def calculate_cam_compensation_summary(df: pd.DataFrame, settings: Dict) -> Dict[str, Any]:
    """Calculate net expansion/shrinkage from shifts and coordinates."""
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    coord_x_col = col_names.get('coord_x', 'Coord. X')
    coord_y_col = col_names.get('coord_y', 'Coord. Y')

    diagnostics = settings.get('DIAGNOSTICS', {})
    cam_cfg = settings.get('CAM_COMPENSATION', {})
    panel_center_x = float(diagnostics.get('panel_center_x', PANEL_CENTER_X))
    panel_center_y = float(diagnostics.get('panel_center_y', PANEL_CENTER_Y))

    required_cols = [x_col, y_col, coord_x_col, coord_y_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return {
            'status': 'insufficient_data',
            'message': f"Missing required column(s): {', '.join(missing_cols)}",
            'ppm': 0.0, 'direction': 'N/A',
            'expansion_ratio': 0.0, 'shrinkage_ratio': 0.0,
            'valid_points': 0, 'total_points': len(df),
            'recommendation': 'Cannot calculate CAM compensation without the required fields.',
        }

    work_df = _coerce_numeric(df.copy(), required_cols)
    valid_df = work_df.dropna(subset=required_cols).copy()
    total_points = len(df)
    valid_points = len(valid_df)

    if valid_df.empty:
        return {
            'status': 'insufficient_data',
            'message': 'No valid rows available for CAM compensation calculation.',
            'ppm': 0.0, 'direction': 'N/A',
            'expansion_ratio': 0.0, 'shrinkage_ratio': 0.0,
            'valid_points': 0, 'total_points': total_points,
            'recommendation': 'Insufficient valid CAM data.',
        }

    shift_x = valid_df[x_col].to_numpy(dtype=float) * 1000.0
    shift_y = valid_df[y_col].to_numpy(dtype=float) * 1000.0
    pos_x = valid_df[coord_x_col].to_numpy(dtype=float) - panel_center_x
    pos_y = valid_df[coord_y_col].to_numpy(dtype=float) - panel_center_y
    radius_mm = np.sqrt(pos_x**2 + pos_y**2)
    dir_x = pos_x / np.where(radius_mm > 1e-6, radius_mm, 1.0)
    dir_y = pos_y / np.where(radius_mm > 1e-6, radius_mm, 1.0)
    radial_shift = shift_x * dir_x + shift_y * dir_y
    radius_um = radius_mm * 1000.0

    mean_radial_shift = float(np.mean(radial_shift))
    mean_radius = float(np.mean(radius_um))
    ppm = float(mean_radial_shift / max(mean_radius, 1e-6) * 1e6)
    expansion_ratio = float(np.count_nonzero(radial_shift > 0) / len(radial_shift))
    shrinkage_ratio = float(np.count_nonzero(radial_shift < 0) / len(radial_shift))

    abs_ppm = abs(ppm)
    monitor_ppm = float(cam_cfg.get('monitor_ppm', 50.0))
    caution_ppm = float(cam_cfg.get('caution_ppm', 120.0))
    min_valid_points = int(cam_cfg.get('min_valid_points', 12))
    min_valid_ratio = float(cam_cfg.get('min_valid_ratio', 0.75))

    if valid_points < min_valid_points or valid_points / max(total_points, 1) < min_valid_ratio:
        status = 'Insufficient data'
        recommendation = 'Not enough valid holes for CAM-worthy compensation.'
    elif abs_ppm < monitor_ppm:
        status = 'Monitor'
        recommendation = 'Net drift is low; no CAM compensation recommended yet.'
    elif abs_ppm < caution_ppm:
        status = 'Caution'
        recommendation = 'Drift is moderate; review before applying compensation.'
    else:
        status = 'Consider Compensation'
        recommendation = ('Net drift exceeds caution thresholds; CAM compensation may be '
                          'appropriate with engineering approval.')

    return {
        'status': status,
        'message': 'CAM compensation summary calculated.',
        'ppm': round(ppm, 1),
        'direction': 'Expansion' if ppm > 0 else 'Shrinkage' if ppm < 0 else 'Neutral',
        'mean_radial_shift_um': round(mean_radial_shift, 3),
        'mean_radius_um': round(mean_radius, 1),
        'expansion_ratio': expansion_ratio,
        'shrinkage_ratio': shrinkage_ratio,
        'valid_points': valid_points,
        'total_points': total_points,
        'recommendation': recommendation,
    }
