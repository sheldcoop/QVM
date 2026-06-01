import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from typing import Dict, Any, Iterable, Tuple

from src.utils import resolve_columns


# ---------------------------------------------------------------------------
# Module constants — hoisted out of inline magic numbers for clarity.
# ---------------------------------------------------------------------------

# Panel geometry defaults (mm). Overridable from settings['DIAGNOSTICS'].
PANEL_CENTER_X = 255.0  # 510 mm panel width / 2
PANEL_CENTER_Y = 257.5  # 515 mm panel height / 2

# Quiver rendering
MIN_ARROW_LENGTH_GRID_UNITS = 0.05  # Smallest visible arrow length in plot units
EXPANSION_DOT_THRESHOLD = 0.5       # |dot| above which an arrow is expansion/contraction
TWIST_DOT_THRESHOLD = 0.2           # |dot| below which a high-magnitude arrow is "twist"
TWIST_MAGNITUDE_THRESHOLD_UM = 10.0 # µm above which a low-dot arrow is "twist"

# Confidence-band cutoffs used by diagnose_root_cause_confidence
CONFIDENCE_HIGH = 0.72
CONFIDENCE_MEDIUM = 0.45

# Mapping: Grid ID → (plot_x, plot_y) on the 4×4 quiver grid (1-indexed).
# Single source of truth — the heatmap matrix layout is derived from it.
_GRID_PLOT_POSITIONS: Dict[str, Tuple[int, int]] = {
    # Upper Left quadrant (11-14)
    '11': (1, 4), '12': (1, 3), '13': (2, 3), '14': (2, 4),
    # Lower Left quadrant (21-24)
    '21': (1, 2), '22': (1, 1), '23': (2, 1), '24': (2, 2),
    # Lower Right quadrant (31-34)
    '31': (3, 2), '32': (3, 1), '33': (4, 1), '34': (4, 2),
    # Upper Right quadrant (41-44)
    '41': (3, 4), '42': (3, 3), '43': (4, 3), '44': (4, 4),
}


def _plot_to_matrix(plot_x: int, plot_y: int) -> Tuple[int, int]:
    """Convert 1-indexed plot coords to 0-indexed (row, col) for Plotly heatmap."""
    return (plot_y - 1, plot_x - 1)


# Derived map: Grid ID → (matrix_row, matrix_col). Plotly heatmap reads (row, col).
_GRID_MATRIX_POSITIONS: Dict[str, Tuple[int, int]] = {
    gid: _plot_to_matrix(x, y) for gid, (x, y) in _GRID_PLOT_POSITIONS.items()
}


def _coerce_numeric(df: pd.DataFrame, cols: Iterable[str]) -> pd.DataFrame:
    """In-place pd.to_numeric(errors='coerce') for each named column that exists."""
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def _default_valid_grid_ids() -> set:
    return set(_GRID_PLOT_POSITIONS.keys())


def _get_valid_grid_ids(settings: Dict) -> set:
    configured = {str(v) for v in settings.get('GRID_MAPPING', {}).values()}
    return configured or _default_valid_grid_ids()


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

    if df.empty:
        return {
            'status': 'insufficient_data',
            'message': 'No data available for root cause diagnosis.',
            'scores': {'Expansion': 0.0, 'Shrinkage': 0.0, 'Twist': 0.0, 'Offset': 0.0},
            'top_cause': 'N/A',
            'top_probability': 0.0,
            'confidence': 0.0,
            'confidence_band': 'Low',
            'reasons': ['No rows available in current filter scope.'],
            'stats': {
                'valid_points': 0,
                'expected_points': expected_points,
                'missing_grid_count': 0,
                'unknown_grid_ids': [],
                'mean_magnitude_um': 0.0,
                'directional_coherence': 0.0,
                'data_quality': 0.0,
            },
        }

    required_cols = [x_col, y_col, coord_x_col, coord_y_col, grid_col]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        return {
            'status': 'insufficient_data',
            'message': f"Missing required column(s): {', '.join(missing_cols)}",
            'scores': {'Expansion': 0.0, 'Shrinkage': 0.0, 'Twist': 0.0, 'Offset': 0.0},
            'top_cause': 'N/A',
            'top_probability': 0.0,
            'confidence': 0.0,
            'confidence_band': 'Low',
            'reasons': [f"Cannot diagnose without: {', '.join(missing_cols)}"],
            'stats': {
                'valid_points': 0,
                'expected_points': expected_points,
                'missing_grid_count': 0,
                'unknown_grid_ids': [],
                'mean_magnitude_um': 0.0,
                'directional_coherence': 0.0,
                'data_quality': 0.0,
            },
        }

    df_work = df.copy()
    grid_series = df_work[grid_col]
    missing_grid_count = int(grid_series.isna().sum())
    numeric_grid = pd.to_numeric(grid_series, errors='coerce')
    grid_str = numeric_grid.dropna().astype(int).astype(str)
    unknown_grid_ids = sorted({gid for gid in grid_str.unique() if gid not in valid_grid_ids})

    # Keep only rows with valid numeric data and valid Grid IDs.
    df_work = _coerce_numeric(df_work, [grid_col, x_col, y_col, coord_x_col, coord_y_col])
    df_work = df_work.dropna(subset=[grid_col, x_col, y_col, coord_x_col, coord_y_col]).copy()
    df_work[grid_col] = df_work[grid_col].astype(int).astype(str)
    df_work = df_work[df_work[grid_col].isin(valid_grid_ids)].copy()

    if df_work.empty:
        return {
            'status': 'insufficient_data',
            'message': 'No valid rows remain after data-quality filtering.',
            'scores': {'Expansion': 0.0, 'Shrinkage': 0.0, 'Twist': 0.0, 'Offset': 0.0},
            'top_cause': 'N/A',
            'top_probability': 0.0,
            'confidence': 0.0,
            'confidence_band': 'Low',
            'reasons': ['All rows were missing required fields or had invalid Grid IDs.'],
            'stats': {
                'valid_points': 0,
                'expected_points': expected_points,
                'missing_grid_count': missing_grid_count,
                'unknown_grid_ids': unknown_grid_ids,
                'mean_magnitude_um': 0.0,
                'directional_coherence': 0.0,
                'data_quality': 0.0,
            },
        }

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
        return {
            'status': 'insufficient_data',
            'message': 'Signal is too small for a confident diagnosis.',
            'scores': {'Expansion': 0.0, 'Shrinkage': 0.0, 'Twist': 0.0, 'Offset': 0.0},
            'top_cause': 'N/A',
            'top_probability': 0.0,
            'confidence': 0.0,
            'confidence_band': 'Low',
            'reasons': ['All valid vectors are below minimum signal threshold (2 µm).'],
            'stats': {
                'valid_points': int(len(df_work)),
                'expected_points': expected_points,
                'missing_grid_count': missing_grid_count,
                'unknown_grid_ids': unknown_grid_ids,
                'mean_magnitude_um': float(np.mean(err_mag_um)) if len(err_mag_um) else 0.0,
                'directional_coherence': 0.0,
                'data_quality': 0.0,
            },
        }

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
    offset_norm = float(np.clip(directional_coherence * (1.0 - offset_primary_penalty * primary_dominance), 0.0, 1.0))

    # Convert evidence to probabilities with light sharpening.
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

    # Entropy-based certainty penalizes ambiguous class mixtures.
    probs = np.array(list(scores.values()), dtype=float)
    entropy = float(-np.sum(probs * np.log(np.clip(probs, 1e-12, 1.0))) / np.log(len(probs)))
    certainty = float(np.clip(1.0 - entropy, 0.0, 1.0))

    # Stability: top-cause agreement across panel quadrants.
    quad_masks = [
        (pos_x[signal_mask] < 0) & (pos_y[signal_mask] >= 0),   # UL
        (pos_x[signal_mask] < 0) & (pos_y[signal_mask] < 0),    # LL
        (pos_x[signal_mask] >= 0) & (pos_y[signal_mask] < 0),   # LR
        (pos_x[signal_mask] >= 0) & (pos_y[signal_mask] >= 0),  # UR
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
        local_off = float(np.clip(directional_coherence * (1.0 - offset_primary_penalty * max(local_ex, local_sh, local_tw)), 0.0, 1.0))
        local_scores = {
            'Expansion': local_ex,
            'Shrinkage': local_sh,
            'Twist': local_tw,
            'Offset': local_off,
        }
        return max(local_scores, key=local_scores.get)

    quadrant_top_causes = [cause for cause in (_top_cause_for_mask(mask) for mask in quad_masks) if cause]
    if quadrant_top_causes:
        agreement = sum(1 for cause in quadrant_top_causes if cause == top_cause)
        stability = float(np.clip(agreement / len(quadrant_top_causes), 0.0, 1.0))
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
        0.0,
        1.0
    ))
    if confidence >= CONFIDENCE_HIGH:
        confidence_band = 'High'
    elif confidence >= CONFIDENCE_MEDIUM:
        confidence_band = 'Medium'
    else:
        confidence_band = 'Low'

    reasons = [
        f"Top cause signal: {top_cause} ({top_probability * 100:.1f}%).",
        f"Class certainty: {certainty * 100:.1f}% (entropy-adjusted).",
        f"Quadrant stability: {stability * 100:.1f}% agreement.",
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
            'ppm': 0.0,
            'direction': 'N/A',
            'expansion_ratio': 0.0,
            'shrinkage_ratio': 0.0,
            'valid_points': 0,
            'total_points': len(df),
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
            'ppm': 0.0,
            'direction': 'N/A',
            'expansion_ratio': 0.0,
            'shrinkage_ratio': 0.0,
            'valid_points': 0,
            'total_points': total_points,
            'recommendation': 'Insufficient valid CAM data.'
        }

    shift_x = valid_df[x_col].to_numpy(dtype=float) * 1000.0
    shift_y = valid_df[y_col].to_numpy(dtype=float) * 1000.0
    pos_x = valid_df[coord_x_col].to_numpy(dtype=float) - panel_center_x
    pos_y = valid_df[coord_y_col].to_numpy(dtype=float) - panel_center_y
    radius_mm = np.sqrt(pos_x**2 + pos_y**2)
    radius_um = radius_mm * 1000.0
    radius_safe = np.where(radius_um > 1e-6, radius_um, 1.0)
    dir_x = pos_x / np.where(radius_mm > 1e-6, radius_mm, 1.0)
    dir_y = pos_y / np.where(radius_mm > 1e-6, radius_mm, 1.0)
    radial_shift = shift_x * dir_x + shift_y * dir_y

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
        recommendation = 'Net drift exceeds caution thresholds; CAM compensation may be appropriate with engineering approval.'

    direction = 'Expansion' if ppm > 0 else 'Shrinkage' if ppm < 0 else 'Neutral'

    return {
        'status': status,
        'message': 'CAM compensation summary calculated.',
        'ppm': round(ppm, 1),
        'direction': direction,
        'mean_radial_shift_um': round(mean_radial_shift, 3),
        'mean_radius_um': round(mean_radius, 1),
        'expansion_ratio': expansion_ratio,
        'shrinkage_ratio': shrinkage_ratio,
        'valid_points': valid_points,
        'total_points': total_points,
        'recommendation': recommendation,
    }

def get_panel_image_path() -> str:
    """Return path to the panel background image."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'assets', 'panel_background.png')

def plot_vtp_bullseye(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """
    Clean DX/DY scatter for Via-to-Pad registration.
    Each point is one fiducial site labeled with its location name.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    chart_colors = settings.get('CHART_COLORS', {})

    dx_col = col_names.get('x_distance', 'Shift (DX)')
    dy_col = col_names.get('y_distance', 'Shift (DY)')
    sc_col = col_names.get('ptv_distance', 'PtV Distance')
    loc_col = col_names.get('location', 'Location')
    grid_col = col_names.get('grid_id', 'Grid ID')

    work = df[[dx_col, dy_col, sc_col, loc_col, grid_col]].dropna().copy()
    work['dx_um'] = work[dx_col] * 1000
    work['dy_um'] = work[dy_col] * 1000
    work['sc_um'] = work[sc_col] * 1000

    bg = chart_colors.get('chart_background', '#FFFFFF')

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=work['dx_um'],
        y=work['dy_um'],
        mode='markers+text',
        marker=dict(
            size=14,
            color=work['sc_um'],
            colorscale='Viridis',
            showscale=True,
            colorbar=dict(title='SC (µm)', thickness=14),
            line=dict(width=1, color='rgba(0,0,0,0.35)'),
        ),
        text=work[grid_col].astype(str),
        textposition='top center',
        textfont=dict(size=9),
        customdata=work[[grid_col, 'sc_um', 'dx_um', 'dy_um']].values,
        hovertemplate=(
            '<b>%{text}</b><br>'
            'Grid ID: %{customdata[0]}<br>'
            'SC: %{customdata[1]:.2f} µm<br>'
            'DX: %{customdata[2]:.2f} µm<br>'
            'DY: %{customdata[3]:.2f} µm<br>'
            '<extra></extra>'
        ),
        showlegend=False,
    ))

    # Light crosshairs at origin
    fig.add_hline(y=0, line=dict(color='rgba(150,150,150,0.4)', width=1))
    fig.add_vline(x=0, line=dict(color='rgba(150,150,150,0.4)', width=1))

    pad = max(work[['dx_um', 'dy_um']].abs().max().max() * 0.25, 1.0)
    spread = max(work[['dx_um', 'dy_um']].abs().max().max() + pad, 5.0)

    fig.update_layout(
        title='DX vs DY Registration Scatter — Via-to-Pad',
        xaxis=dict(title='DX Shift (µm)', zeroline=False, showgrid=True,
                   scaleanchor='y', scaleratio=1,
                   range=[-spread, spread]),
        yaxis=dict(title='DY Shift (µm)', zeroline=False, showgrid=True,
                   range=[-spread, spread]),
        plot_bgcolor=bg,
        hovermode='closest',
        height=550,
    )
    return fig


def plot_vtp_site_bars(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """
    Per-fiducial-site SC bar chart for Via-to-Pad registration.

    Bars are ordered by Grid ID (UL → LL → LR → UR) and colored by the same
    traffic-light thresholds as the bullseye, making it easy to identify which
    specific sites are worst.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    chart_colors = settings.get('CHART_COLORS', {})
    vtp_cfg = settings.get('VTP_REGISTRATION', {})

    sc_col = col_names.get('ptv_distance', 'PtV Distance')
    loc_col = col_names.get('location', 'Location')
    grid_col = col_names.get('grid_id', 'Grid ID')

    ring_green = float(vtp_cfg.get('ring_green_um', 50.0))
    ring_orange = float(vtp_cfg.get('ring_orange_um', 96.0))
    bar_y_max = float(vtp_cfg.get('bar_y_max_um', 50.0))
    bar_y_dtick = float(vtp_cfg.get('bar_y_dtick_um', 5.0))

    work = df[[sc_col, loc_col, grid_col]].dropna().copy()
    work['sc_um'] = work[sc_col] * 1000
    work[grid_col] = pd.to_numeric(work[grid_col], errors='coerce')
    work = work.dropna(subset=[grid_col]).sort_values(grid_col)
    work[grid_col] = work[grid_col].astype(int).astype(str)

    def _bar_color(sc: float) -> str:
        if sc <= ring_green:
            return chart_colors.get('traffic_light_green', '#2ecc71')
        if sc <= ring_orange:
            return chart_colors.get('traffic_light_orange', '#f39c12')
        return chart_colors.get('traffic_light_red', '#e74c3c')

    work['color'] = work['sc_um'].apply(_bar_color)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=work[grid_col],
        y=work['sc_um'],
        marker_color=work['color'],
        marker_line=dict(width=1, color='rgba(0,0,0,0.3)'),
        customdata=work[[loc_col, 'sc_um']].values,
        hovertemplate=(
            'Grid ID: <b>%{x}</b><br>'
            'Location: %{customdata[0]}<br>'
            'SC: %{customdata[1]:.2f} µm<br>'
            '<extra></extra>'
        ),
        showlegend=False,
    ))

    # Threshold lines
    fig.add_hline(
        y=ring_green,
        line=dict(color=chart_colors.get('traffic_light_green', '#2ecc71'), width=1.5, dash='dash'),
        annotation_text=f'Pass limit {ring_green:.0f} µm',
        annotation_position='right',
        annotation_font_size=10,
    )
    fig.add_hline(
        y=ring_orange,
        line=dict(color=chart_colors.get('traffic_light_orange', '#f39c12'), width=1.5, dash='dot'),
        annotation_text=f'Warn limit {ring_orange:.0f} µm',
        annotation_position='right',
        annotation_font_size=10,
    )

    bg = chart_colors.get('chart_background', '#FFFFFF')
    data_max = work['sc_um'].max()
    # Y-axis: data + 30% headroom, minimum 10 µm so threshold lines are always legible
    y_max = max(data_max * 1.3, 10.0)
    fig.update_layout(
        title='Registration SC per Fiducial Site (ordered by Grid ID: UL → LL → LR → UR)',
        xaxis=dict(title='Grid ID', showgrid=False, type='category'),
        yaxis=dict(title='SC Distance (µm)', range=[0, y_max], showgrid=True),
        plot_bgcolor=bg,
        hovermode='x unified',
        height=450,
    )
    return fig


def plot_quiver(df: pd.DataFrame, settings: Dict, multiplier: float) -> go.Figure:
    """
    Pattern Hunter: Create a Quiver/Vector Plot with ABF distortion pattern detection.
    
    Colors arrows based on dot product to detect failure modes:
    - RED: Material Expansion (positive dot product) or Shrinkage (negative dot product)
    - GOLD: Lamination Twist (dot product ≈ 0, high magnitude)
    - BLUE: Global Offset (uniform misalignment)
    
    Grid layout matches panel: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    coord_x_col = col_names.get('coord_x', 'Coord. X')
    coord_y_col = col_names.get('coord_y', 'Coord. Y')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col = col_names.get('location', 'Location')

    # Extract row and col from grid_id
    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)

    df_plot['plot_x'] = df_plot[grid_col].map(lambda gid: _GRID_PLOT_POSITIONS.get(gid, (np.nan, np.nan))[0])
    df_plot['plot_y'] = df_plot[grid_col].map(lambda gid: _GRID_PLOT_POSITIONS.get(gid, (np.nan, np.nan))[1])
    df_plot = df_plot.dropna(subset=['plot_x', 'plot_y']).copy()

    # Calculate magnitude for statistics
    df_plot['magnitude'] = np.sqrt(df_plot[x_col]**2 + df_plot[y_col]**2) * 1000  # Convert to microns

    panel_center_x = PANEL_CENTER_X
    panel_center_y = PANEL_CENTER_Y

    fig = go.Figure()

    # Pattern detection thresholds (module-level constants)
    expansion_threshold = EXPANSION_DOT_THRESHOLD
    twist_dot_threshold = TWIST_DOT_THRESHOLD
    twist_mag_threshold = TWIST_MAGNITUDE_THRESHOLD_UM

    # Track pattern counts and collect scatter data
    expansion_count = 0
    twist_count = 0
    offset_count = 0

    scatter_x, scatter_y, scatter_text, scatter_hover = [], [], [], []

    # Add quiver annotations with pattern-based color coding
    for _, row in df_plot.iterrows():
        x = row['plot_x']
        y = row['plot_y']

        # DX/DY are in mm — convert to µm then scale to grid units
        dx_um = row[x_col] * 1000
        dy_um = row[y_col] * 1000
        dx_scaled = dx_um * multiplier * 0.001
        dy_scaled = dy_um * multiplier * 0.001

        # Guarantee a minimum visible arrow length
        arrow_len = np.sqrt(dx_scaled**2 + dy_scaled**2)
        if arrow_len > 0 and arrow_len < MIN_ARROW_LENGTH_GRID_UNITS:
            scale_up = MIN_ARROW_LENGTH_GRID_UNITS / arrow_len
            dx_scaled *= scale_up
            dy_scaled *= scale_up
        mag = row['magnitude']

        # Calculate position vector — use real coords if available,
        # otherwise fall back to grid position relative to grid centre (2.5, 2.5)
        raw_x = row.get(coord_x_col) if coord_x_col in row.index else None
        raw_y = row.get(coord_y_col) if coord_y_col in row.index else None
        has_coords = (raw_x is not None and not (isinstance(raw_x, float) and np.isnan(raw_x)))
        if has_coords:
            pos_x = raw_x - panel_center_x
            pos_y = raw_y - panel_center_y
        else:
            # Grid centre is at (2.5, 2.5) in plot space
            pos_x = x - 2.5
            pos_y = y - 2.5

        # Normalize position vector
        pos_mag = np.sqrt(pos_x**2 + pos_y**2)
        pos_x_norm = (pos_x / pos_mag) if pos_mag > 0 else 0
        pos_y_norm = (pos_y / pos_mag) if pos_mag > 0 else 0

        # Normalize error vector
        err_mag = np.sqrt(dx_scaled**2 + dy_scaled**2)
        err_x_norm = (dx_scaled / err_mag) if err_mag > 0 else 0
        err_y_norm = (dy_scaled / err_mag) if err_mag > 0 else 0

        dot_product = err_x_norm * pos_x_norm + err_y_norm * pos_y_norm

        if abs(dot_product) > expansion_threshold:
            if dot_product > 0:
                # ORANGE-RED: Material Expansion (shift away from center)
                arrow_color = 'rgb(255, 80, 0)'
                pattern = "Expansion"
            else:
                # CYAN: Material Shrinkage/Contraction (shift toward center)
                arrow_color = 'rgb(0, 210, 210)'
                pattern = "Contraction"
            expansion_count += 1
        elif abs(dot_product) < twist_dot_threshold and mag > twist_mag_threshold:
            arrow_color = 'rgb(255, 215, 0)'
            pattern = "Twist"
            twist_count += 1
        else:
            arrow_color = 'rgb(100, 150, 255)'
            pattern = "Offset"
            offset_count += 1

        fig.add_annotation(
            x=x + dx_scaled,
            y=y + dy_scaled,
            ax=x, ay=y,
            xref="x", yref="y", axref="x", ayref="y",
            text="", showarrow=True,
            arrowhead=2, arrowsize=1.5, arrowwidth=2.5,
            arrowcolor=arrow_color, opacity=0.9
        )

        # Collect for single consolidated scatter trace
        scatter_x.append(x)
        scatter_y.append(y)
        scatter_text.append(str(row[grid_col]))
        loc_name = row[loc_col] if loc_col in row.index else row[grid_col]
        scatter_hover.append(
            f"<b>{loc_name}</b><br>"
            f"Grid: {row[grid_col]}<br>"
            f"Pattern: {pattern}<br>"
            f"DX: {dx_um:.2f} µm<br>"
            f"DY: {dy_um:.2f} µm<br>"
            f"Magnitude: {mag:.2f} µm<br>"
            f"<extra></extra>"
        )

    # One single scatter trace for all points
    fig.add_trace(go.Scatter(
        x=scatter_x, y=scatter_y,
        mode='markers+text',
        marker=dict(color='#333333', size=14, line=dict(color='#FFFF00', width=2)),
        text=scatter_text,
        textposition="top center",
        textfont=dict(size=11, color='#FFFF00', family='Arial Black'),
        hovertemplate=scatter_hover,
        showlegend=False
    ))

    # Add legend annotations
    fig.add_annotation(
        x=2.5, y=0.2,
        text=(
            f"<b>Pattern Detection Summary</b><br>"
            f"� <b>Expansion</b>: arrows pointing away from centre<br>"
            f"🩵 <b>Contraction</b>: arrows pointing toward centre<br>"
            f"🟡 <b>Twist</b>: perpendicular arrows<br>"
            f"🔵 <b>Offset</b>: uniform shift<br>"
            f"<br>"
            f"Expansion/Contraction: {expansion_count} &nbsp; Twist: {twist_count} &nbsp; Offset: {offset_count}"
        ),
        showarrow=False,
        bgcolor='rgba(26, 26, 26, 0.8)',
        bordercolor='#666666',
        borderwidth=1,
        font=dict(color='#E8E8E8', size=11),
        align='left',
        xref='x',
        yref='y'
    )

    # Setup the 4x4 grid layout
    chart_colors = settings.get('CHART_COLORS', {})
    fig.update_xaxes(range=[0.5, 4.5], dtick=1, showgrid=chart_colors.get('chart_gridlines_visible', False), gridcolor='#444444', title=dict(text="Column", font=dict(color='#E8E8E8')))
    fig.update_yaxes(range=[0.5, 4.5], dtick=1, showgrid=chart_colors.get('chart_gridlines_visible', False), gridcolor='#444444', title=dict(text="Row", font=dict(color='#E8E8E8')))
    fig.update_layout(
        title=dict(text=f"Pattern Hunter: ABF Distortion Map | {multiplier}x Sensitivity", font=dict(color='#E8E8E8', size=14)),
        width=700,
        height=700,
        plot_bgcolor='#1a1a1a',
        paper_bgcolor='#1a1a1a',
        font=dict(color='#B0B0B0', size=11),
        hovermode='closest'
    )
    
    # Add panel image as background
    panel_image_path = get_panel_image_path()
    try:
        fig.add_layout_image(
            source=panel_image_path,
            xref="x",
            yref="y",
            x=0.5,
            y=4.5,
            sizex=4,
            sizey=4,
            sizing="stretch",
            opacity=0.25,
            layer="below"
        )
    except Exception as e:
        # If image loading fails, continue without it
        print(f"Warning: Could not load panel background image: {e}")
    
    return fig


def plot_heatmap(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """
    Create a Heatmap based on the magnitude of the PtV distance on a 4x4 grid.
    Grid layout matches panel: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR
    """
    col_names = settings.get('COLUMN_NAMES', {})
    ptv_col = col_names.get('ptv_distance', 'PtV Distance')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col = col_names.get('location', 'Location')

    # Create an empty 4x4 matrix (row, col) where [0,0] is bottom-left in Plotly heatmap
    matrix = np.full((4, 4), np.nan)
    text_matrix = np.empty((4, 4), dtype=object)
    text_matrix[:] = ''

    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)

    # Convert PtV distance to microns for consistency
    ptv_microns = df_plot[ptv_col] * 1000

    for idx, row in df_plot.iterrows():
        grid_id = row[grid_col]
        if grid_id in _GRID_MATRIX_POSITIONS:
            r, c = _GRID_MATRIX_POSITIONS[grid_id]
            matrix[r, c] = ptv_microns.loc[idx]
            text_matrix[r, c] = f"Grid {grid_id}<br>{row[loc_col]}<br>{ptv_microns.loc[idx]:.3f} µm"

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        text=text_matrix,
        texttemplate="%{text}",
        hoverinfo="text",
        colorscale='Viridis',
        colorbar=dict(title="PtV Distance<br>(µm)")
    ))
    
    chart_colors = settings.get('CHART_COLORS', {})

    # Update axes to show grid labels matching the panel layout
    fig.update_layout(
        title="PtV Distance Heatmap | Grid Layout: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR",
        xaxis=dict(
            title="Column", 
            tickmode='array', 
            tickvals=[0.5, 1.5, 2.5, 3.5], 
            ticktext=['', '', '', ''],
            showticklabels=False,
            constrain='domain',
            showgrid=chart_colors.get('chart_gridlines_visible', False)
        ),
        yaxis=dict(
            title="Row", 
            tickmode='array', 
            tickvals=[0.5, 1.5, 2.5, 3.5], 
            ticktext=['', '', '', ''],
            showticklabels=False,
            scaleanchor="x",
            scaleratio=1,
            showgrid=chart_colors.get('chart_gridlines_visible', False)
        ),
        width=800,
        height=800,
        plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF')
    )

    return fig
