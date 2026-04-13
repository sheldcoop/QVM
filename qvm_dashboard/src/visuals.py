import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from typing import Dict, Any


def _default_valid_grid_ids() -> set:
    return {
        '11', '12', '13', '14',
        '21', '22', '23', '24',
        '31', '32', '33', '34',
        '41', '42', '43', '44',
    }


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
    df_work[grid_col] = pd.to_numeric(df_work[grid_col], errors='coerce')
    df_work[x_col] = pd.to_numeric(df_work[x_col], errors='coerce')
    df_work[y_col] = pd.to_numeric(df_work[y_col], errors='coerce')
    df_work[coord_x_col] = pd.to_numeric(df_work[coord_x_col], errors='coerce')
    df_work[coord_y_col] = pd.to_numeric(df_work[coord_y_col], errors='coerce')
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

    panel_center_x = float(diagnostics.get('panel_center_x', 255.0))
    panel_center_y = float(diagnostics.get('panel_center_y', 257.5))
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
    if confidence >= 0.72:
        confidence_band = 'High'
    elif confidence >= 0.45:
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
    panel_center_x = float(diagnostics.get('panel_center_x', 255.0))
    panel_center_y = float(diagnostics.get('panel_center_y', 257.5))

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

    work_df = df.copy()
    for col in required_cols:
        work_df[col] = pd.to_numeric(work_df[col], errors='coerce')

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
    radius = np.sqrt(pos_x**2 + pos_y**2)
    radius_safe = np.where(radius > 1e-6, radius, 1.0)
    dir_x = pos_x / radius_safe
    dir_y = pos_y / radius_safe
    radial_shift = shift_x * dir_x + shift_y * dir_y

    mean_radial_shift = float(np.mean(radial_shift))
    mean_radius = float(np.mean(radius))
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
        'mean_radius_um': round(mean_radius, 3),
        'expansion_ratio': expansion_ratio,
        'shrinkage_ratio': shrinkage_ratio,
        'valid_points': valid_points,
        'total_points': total_points,
        'recommendation': recommendation,
    }

def get_panel_image_path() -> str:
    """Return path to the panel background image."""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'assets', 'panel_background.png')

def plot_bullseye_scatter(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """
    Create a Bullseye Scatter plot of Shift (DX) vs Shift (DY).
    """
    col_names = settings.get('COLUMN_NAMES', {})
    chart_colors = settings.get('CHART_COLORS', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    loc_col = col_names.get('location', 'Location')
    
    # Convert to microns for consistency
    df_microns = df.copy()
    df_microns[x_col] = df[x_col] * 1000
    df_microns[y_col] = df[y_col] * 1000

    fig = px.scatter(
        df_microns,
        x=x_col,
        y=y_col,
        text=loc_col,
        title="Bullseye Scatter: Shift DX vs DY",
        labels={x_col: 'DX Shift (µm)', y_col: 'DY Shift (µm)'}
    )

    # Update layout to make it a square and centered
    fig.update_traces(textposition='top center')

    # Add crosshairs
    fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.5)
    fig.add_vline(x=0, line_dash="dash", line_color="red", opacity=0.5)

    # Make axes symmetric
    max_val = max(abs(df_microns[x_col].max()), abs(df_microns[x_col].min()),
                  abs(df_microns[y_col].max()), abs(df_microns[y_col].min()))

    # Add a little padding
    max_val = max_val * 1.2 if max_val > 0 else 0.1

    fig.update_xaxes(range=[-max_val, max_val], zeroline=False, showgrid=chart_colors.get('chart_gridlines_visible', False))
    fig.update_yaxes(range=[-max_val, max_val], zeroline=False, showgrid=chart_colors.get('chart_gridlines_visible', False))
    fig.update_layout(
        width=700, 
        height=700,
        plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF')
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

    # Create explicit mapping: Grid ID -> (plot_x, plot_y)
    grid_position_map = {
        # Upper Left Quadrant (11-14)
        '11': (1, 4), '12': (1, 3), '13': (2, 3), '14': (2, 4),
        # Lower Left Quadrant (21-24)
        '21': (1, 2), '22': (1, 1), '23': (2, 1), '24': (2, 2),
        # Lower Right Quadrant (31-34)
        '31': (3, 2), '32': (3, 1), '33': (4, 1), '34': (4, 2),
        # Upper Right Quadrant (41-44)
        '41': (3, 4), '42': (3, 3), '43': (4, 3), '44': (4, 4),
    }
    
    df_plot['plot_x'] = df_plot[grid_col].map(lambda gid: grid_position_map.get(gid, (np.nan, np.nan))[0])
    df_plot['plot_y'] = df_plot[grid_col].map(lambda gid: grid_position_map.get(gid, (np.nan, np.nan))[1])
    df_plot = df_plot.dropna(subset=['plot_x', 'plot_y']).copy()
    
    # Calculate magnitude for statistics
    df_plot['magnitude'] = np.sqrt(df_plot[x_col]**2 + df_plot[y_col]**2) * 1000  # Convert to microns

    # Panel center (510mm x 515mm panel)
    panel_center_x = 255.0
    panel_center_y = 257.5

    fig = go.Figure()
    
    # Pattern detection thresholds
    expansion_threshold = 0.5      # dot product threshold for expansion
    twist_dot_threshold = 0.2      # dot product threshold for twist (near zero)
    twist_mag_threshold = 10.0     # minimum magnitude for twist (microns)

    # Track pattern counts for legend
    expansion_count = 0
    twist_count = 0
    offset_count = 0

    # Add quiver annotations with pattern-based color coding
    for _, row in df_plot.iterrows():
        x = row['plot_x']
        y = row['plot_y']

        dx_scaled = row[x_col] * multiplier
        dy_scaled = row[y_col] * multiplier
        mag = row['magnitude']
        
        # Calculate position vector (from panel center to hole)
        pos_x = row[coord_x_col] - panel_center_x if coord_x_col in row.index else 0
        pos_y = row[coord_y_col] - panel_center_y if coord_y_col in row.index else 0
        
        # Normalize position vector
        pos_mag = np.sqrt(pos_x**2 + pos_y**2)
        if pos_mag > 0:
            pos_x_norm = pos_x / pos_mag
            pos_y_norm = pos_y / pos_mag
        else:
            pos_x_norm = 0
            pos_y_norm = 0
        
        # Normalize error vector
        err_mag = np.sqrt(dx_scaled**2 + dy_scaled**2)
        if err_mag > 0:
            err_x_norm = dx_scaled / err_mag
            err_y_norm = dy_scaled / err_mag
        else:
            err_x_norm = 0
            err_y_norm = 0
        
        # Calculate dot product
        dot_product = err_x_norm * pos_x_norm + err_y_norm * pos_y_norm
        
        # Pattern detection logic
        if abs(dot_product) > expansion_threshold:
            # RED: Material Expansion (Positive) or Shrinkage (Negative)
            arrow_color = 'rgb(255, 50, 50)'  # Bright Red
            pattern = "Expansion" if dot_product > 0 else "Shrinkage"
            expansion_count += 1
        elif abs(dot_product) < twist_dot_threshold and mag > twist_mag_threshold:
            # GOLD: Lamination Twist (Perpendicular)
            arrow_color = 'rgb(255, 215, 0)'  # Gold
            pattern = "Twist"
            twist_count += 1
        else:
            # BLUE: Global Offset (Uniform shift)
            arrow_color = 'rgb(100, 150, 255)'  # Light Blue
            pattern = "Offset"
            offset_count += 1

        fig.add_annotation(
            x=x + dx_scaled,
            y=y + dy_scaled,
            ax=x,
            ay=y,
            xref="x",
            yref="y",
            axref="x",
            ayref="y",
            text="",
            showarrow=True,
            arrowhead=2,
            arrowsize=1.5,
            arrowwidth=2.5,
            arrowcolor=arrow_color,
            opacity=0.85
        )

        # Add a dot at the origin with grid label
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='markers+text',
            marker=dict(color='#333333', size=14, line=dict(color='#FFFF00', width=2)),
            text=[row[grid_col]],
            textposition="top center",
            textfont=dict(size=11, color='#FFFF00', family='Arial Black'),
            hovertemplate=(
                f"<b>{row[loc_col]}</b><br>" +
                f"Grid: {row[grid_col]}<br>" +
                f"Pattern: {pattern}<br>" +
                f"Dot Product: {dot_product:.3f}<br>" +
                f"DX: {row[x_col]*1000:.3f} µm<br>" +
                f"DY: {row[y_col]*1000:.3f} µm<br>" +
                f"Magnitude: {mag:.3f} µm<br>" +
                "<extra></extra>"
            ),
            showlegend=False
        ))

    # Add legend annotations
    fig.add_annotation(
        x=2.5, y=0.2,
        text=(
            f"<b>Pattern Detection Summary</b><br>"
            f"🔴 <b>Material (Exp/Shrink)</b>: {expansion_count} holes<br>"
            f"🟡 <b>Twist</b>: {twist_count} holes<br>"
            f"🔵 <b>Offset</b>: {offset_count} holes"
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

    # Create an empty 4x4 matrix (row, col) where [0,0] is top-left
    matrix = np.zeros((4, 4))
    matrix[:] = np.nan # Use NaN for missing values

    text_matrix = np.empty((4, 4), dtype=object)
    text_matrix[:] = ''

    # Create explicit mapping: Grid ID -> (matrix_row, matrix_col)
    # Matrix indexing: Plotly displays rows from bottom to top, so reverse row order
    # Row 0 displays at BOTTOM, Row 3 displays at TOP
    # Pattern within each quadrant: 1=top-left, 2=bottom-left, 3=bottom-right, 4=top-right
    grid_matrix_map = {
        # Upper Left Quadrant (11-14) - displayed at TOP-LEFT
        '11': (3, 0), '12': (2, 0), '13': (2, 1), '14': (3, 1),
        # Lower Left Quadrant (21-24) - displayed at BOTTOM-LEFT
        '21': (1, 0), '22': (0, 0), '23': (0, 1), '24': (1, 1),
        # Lower Right Quadrant (31-34) - displayed at BOTTOM-RIGHT
        '31': (1, 2), '32': (0, 2), '33': (0, 3), '34': (1, 3),
        # Upper Right Quadrant (41-44) - displayed at TOP-RIGHT
        '41': (3, 2), '42': (2, 2), '43': (2, 3), '44': (3, 3),
    }

    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)

    # Convert PtV distance to microns for consistency
    ptv_microns = df_plot[ptv_col] * 1000

    for idx, row in df_plot.iterrows():
        grid_id = row[grid_col]
        if grid_id in grid_matrix_map:
            r, c = grid_matrix_map[grid_id]
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
