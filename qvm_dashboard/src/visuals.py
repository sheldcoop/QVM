"""
Chart rendering functions — all return Plotly figures.

Diagnostic computations live in src/diagnostics.py.
"""

import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Grid layout — single source of truth shared by quiver + heatmap + diagnostics
# ---------------------------------------------------------------------------

# Grid ID → (plot_x, plot_y) on the 4×4 grid (1-indexed, origin bottom-left)
_GRID_PLOT_POSITIONS: Dict[str, Tuple[int, int]] = {
    '11': (1, 4), '12': (1, 3), '13': (2, 3), '14': (2, 4),
    '21': (1, 2), '22': (1, 1), '23': (2, 1), '24': (2, 2),
    '31': (3, 2), '32': (3, 1), '33': (4, 1), '34': (4, 2),
    '41': (3, 4), '42': (3, 3), '43': (4, 3), '44': (4, 4),
}


def _plot_to_matrix(plot_x: int, plot_y: int) -> Tuple[int, int]:
    """Convert 1-indexed plot coords to 0-indexed (row, col) for Plotly heatmap."""
    return (plot_y - 1, plot_x - 1)


# Grid ID → (matrix_row, matrix_col)
_GRID_MATRIX_POSITIONS: Dict[str, Tuple[int, int]] = {
    gid: _plot_to_matrix(x, y) for gid, (x, y) in _GRID_PLOT_POSITIONS.items()
}

# ---------------------------------------------------------------------------
# Shared colour helper
# ---------------------------------------------------------------------------

def _traffic_light_color(
    sc_um: float,
    ring_exceptional: float,
    ring_excellent: float,
    ring_good: float,
    ring_acceptable: float,
    chart_colors: Dict,
) -> str:
    """Map an SC magnitude (µm) to a traffic-light colour (5 zones)."""
    if sc_um <= ring_exceptional:
        return chart_colors.get('traffic_light_blue', '#3498db')
    if sc_um <= ring_excellent:
        return chart_colors.get('traffic_light_dark_green', '#1e7e3a')
    if sc_um <= ring_good:
        return chart_colors.get('traffic_light_green', '#2ecc71')
    if sc_um <= ring_acceptable:
        return chart_colors.get('traffic_light_orange', '#e67e22')
    return chart_colors.get('traffic_light_red', '#e74c3c')


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def get_panel_image_path() -> str:
    """Return path to the panel background image."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_dir, 'assets', 'panel_background.png')


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------

def plot_vtp_bullseye(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """DX/DY bullseye scatter for Via-to-Pad registration.

    Each fiducial site is a single point at (DX, DY) in µm. Concentric
    tolerance rings make pass/warn/fail visually obvious.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    chart_colors = settings.get('CHART_COLORS', {})
    vtp_cfg = settings.get('VTP_REGISTRATION', {})

    dx_col = col_names.get('x_distance', 'Shift (DX)')
    dy_col = col_names.get('y_distance', 'Shift (DY)')
    sc_col = col_names.get('ptv_distance', 'PtV Distance')
    loc_col = col_names.get('location', 'Location')
    grid_col = col_names.get('grid_id', 'Grid ID')

    ring_exceptional = float(vtp_cfg.get('ring_exceptional_um', 2.5))
    ring_excellent   = float(vtp_cfg.get('ring_excellent_um', 5.0))
    ring_good        = float(vtp_cfg.get('ring_good_um', 7.5))
    ring_acceptable  = float(vtp_cfg.get('ring_acceptable_um', 10.0))

    work = df[[dx_col, dy_col, sc_col, loc_col, grid_col]].dropna().copy()
    work['dx_um'] = work[dx_col] * 1000
    work['dy_um'] = work[dy_col] * 1000
    work['sc_um'] = work[sc_col] * 1000
    work['color'] = work['sc_um'].apply(
        lambda v: _traffic_light_color(v, ring_exceptional, ring_excellent,
                                       ring_good, ring_acceptable, chart_colors)
    )

    bg              = chart_colors.get('chart_background', '#FFFFFF')
    blue_color      = chart_colors.get('traffic_light_blue', '#3498db')
    dark_green_color = chart_colors.get('traffic_light_dark_green', '#1e7e3a')
    green_color     = chart_colors.get('traffic_light_green', '#2ecc71')
    orange_color    = chart_colors.get('traffic_light_orange', '#e67e22')
    red_color       = chart_colors.get('traffic_light_red', '#e74c3c')

    spread = ring_acceptable + 2.0
    fig = go.Figure()

    for r, color, dash in [
        (ring_exceptional, blue_color, 'solid'),
        (ring_excellent, dark_green_color, 'dot'),
        (ring_good, green_color, 'dash'),
        (ring_acceptable, red_color, 'dot'),
    ]:
        fig.add_shape(
            type='circle', xref='x', yref='y',
            x0=-r, y0=-r, x1=r, y1=r,
            line=dict(color=color, width=2, dash=dash),
            fillcolor='rgba(0,0,0,0)', layer='below',
        )

    crosshair = dict(color='rgba(80,80,80,0.6)', width=1.5)
    fig.add_hline(y=0, line=crosshair)
    fig.add_vline(x=0, line=crosshair)

    fig.add_trace(go.Scatter(
        x=work['dx_um'], y=work['dy_um'],
        mode='markers+text',
        marker=dict(size=14, color=work['color'],
                    line=dict(width=1, color='rgba(0,0,0,0.5)')),
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

    sc = work['sc_um']
    n = int(len(sc))
    max_sc = float(sc.max()) if n else 0.0
    mean_sc = float(sc.mean()) if n else 0.0
    n_outside = int((sc > ring_acceptable).sum())
    fig.add_annotation(
        text=(f"<b>n</b> {n}  •  <b>max SC</b> {max_sc:.1f} µm  •  "
              f"<b>mean SC</b> {mean_sc:.1f} µm  •  <b>outside fail</b> {n_outside}"),
        xref='paper', yref='paper', x=0.02, y=0.98,
        xanchor='left', yanchor='top', showarrow=False, align='left',
        font=dict(size=11, color='#222222'),
        bgcolor='rgba(255,255,255,0.85)', bordercolor='#999999',
        borderwidth=1, borderpad=4,
    )
    fig.add_annotation(
        text=(
            f"<span style='color:{blue_color}'>●</span> r ≤ {ring_exceptional:.1f} µm (exceptional)<br>"
            f"<span style='color:{dark_green_color}'>●</span> r ≤ {ring_excellent:.1f} µm (excellent)<br>"
            f"<span style='color:{green_color}'>●</span> r ≤ {ring_good:.1f} µm (good)<br>"
            f"<span style='color:{orange_color}'>●</span> r ≤ {ring_acceptable:.1f} µm (acceptable)<br>"
            f"<span style='color:{red_color}'>●</span> r > {ring_acceptable:.1f} µm (fail)"
        ),
        xref='paper', yref='paper', x=0.98, y=0.02,
        xanchor='right', yanchor='bottom', showarrow=False, align='left',
        font=dict(size=10, color='#222222'),
        bgcolor='rgba(255,255,255,0.85)', bordercolor='#999999',
        borderwidth=1, borderpad=4,
    )

    fig.update_layout(
        title='DX vs DY Registration Bullseye — Via-to-Pad',
        xaxis=dict(title='DX Shift (µm)', zeroline=False, showgrid=True,
                   scaleanchor='y', scaleratio=1, range=[-spread, spread]),
        yaxis=dict(title='DY Shift (µm)', zeroline=False, showgrid=True,
                   range=[-spread, spread]),
        plot_bgcolor=bg, hovermode='closest', height=550,
    )
    return fig


def plot_vtp_site_bars(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """Per-fiducial-site SC bar chart for Via-to-Pad registration.

    Bars are ordered by Grid ID (UL → LL → LR → UR) and coloured by the
    same traffic-light thresholds as the bullseye.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    chart_colors = settings.get('CHART_COLORS', {})
    vtp_cfg = settings.get('VTP_REGISTRATION', {})

    sc_col   = col_names.get('ptv_distance', 'PtV Distance')
    loc_col  = col_names.get('location', 'Location')
    grid_col = col_names.get('grid_id', 'Grid ID')

    ring_exceptional = float(vtp_cfg.get('ring_exceptional_um', 2.5))
    ring_excellent   = float(vtp_cfg.get('ring_excellent_um', 5.0))
    ring_good        = float(vtp_cfg.get('ring_good_um', 7.5))
    ring_acceptable  = float(vtp_cfg.get('ring_acceptable_um', 10.0))

    work = df[[sc_col, loc_col, grid_col]].dropna().copy()
    work['sc_um'] = work[sc_col] * 1000
    work[grid_col] = pd.to_numeric(work[grid_col], errors='coerce')
    work = work.dropna(subset=[grid_col]).sort_values(grid_col)
    work[grid_col] = work[grid_col].astype(int).astype(str)
    work['color'] = work['sc_um'].apply(
        lambda v: _traffic_light_color(v, ring_exceptional, ring_excellent,
                                       ring_good, ring_acceptable, chart_colors)
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=work[grid_col], y=work['sc_um'],
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

    for y_val, color_key, label in [
        (ring_excellent, 'traffic_light_dark_green', f'Excellent limit {ring_excellent:.1f} µm'),
        (ring_good, 'traffic_light_green', f'Good limit {ring_good:.1f} µm'),
        (ring_acceptable, 'traffic_light_red', f'Acceptable limit {ring_acceptable:.0f} µm'),
    ]:
        fig.add_hline(
            y=y_val,
            line=dict(color=chart_colors.get(color_key, '#888'), width=1.5, dash='dash'),
            annotation_text=label, annotation_position='right',
            annotation_font_size=10,
        )

    bg = chart_colors.get('chart_background', '#FFFFFF')
    data_max = work['sc_um'].max()
    y_max = max(data_max * 1.3, 10.0)
    fig.update_layout(
        title='Registration SC per Fiducial Site (ordered by Grid ID: UL → LL → LR → UR)',
        xaxis=dict(title='Grid ID', showgrid=False, type='category'),
        yaxis=dict(title='SC Distance (µm)', range=[0, y_max], showgrid=True),
        plot_bgcolor=bg, hovermode='x unified', height=450,
    )
    return fig


def plot_quiver(df: pd.DataFrame, settings: Dict, multiplier: float) -> go.Figure:
    """Pattern Hunter: Quiver/vector plot with ABF distortion pattern detection.

    Colors:
    - Orange-red: Expansion (shift away from centre)
    - Cyan: Shrinkage (shift toward centre)
    - Gold: Twist (perpendicular)
    - Blue: Offset (uniform)
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col       = col_names.get('x_distance', 'Shift (DX)')
    y_col       = col_names.get('y_distance', 'Shift (DY)')
    coord_x_col = col_names.get('coord_x', 'Coord. X')
    coord_y_col = col_names.get('coord_y', 'Coord. Y')
    grid_col    = col_names.get('grid_id', 'Grid ID')
    loc_col     = col_names.get('location', 'Location')

    diag_cfg = settings.get('DIAGNOSTICS', {})
    panel_center_x = float(diag_cfg.get('panel_center_x', 255.0))
    panel_center_y = float(diag_cfg.get('panel_center_y', 257.5))
    min_arrow      = float(diag_cfg.get('quiver_min_arrow_length', 0.05))
    expansion_thr  = float(diag_cfg.get('quiver_expansion_dot_threshold', 0.5))
    twist_dot_thr  = float(diag_cfg.get('quiver_twist_dot_threshold', 0.2))
    twist_mag_thr  = float(diag_cfg.get('quiver_twist_magnitude_um', 10.0))

    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)
    df_plot['plot_x'] = df_plot[grid_col].map(
        lambda gid: _GRID_PLOT_POSITIONS.get(gid, (np.nan, np.nan))[0])
    df_plot['plot_y'] = df_plot[grid_col].map(
        lambda gid: _GRID_PLOT_POSITIONS.get(gid, (np.nan, np.nan))[1])
    df_plot = df_plot.dropna(subset=['plot_x', 'plot_y']).copy()
    df_plot['magnitude'] = np.sqrt(df_plot[x_col]**2 + df_plot[y_col]**2) * 1000

    fig = go.Figure()
    expansion_count = twist_count = offset_count = 0
    scatter_x, scatter_y, scatter_text, scatter_hover = [], [], [], []

    for _, row in df_plot.iterrows():
        x, y = row['plot_x'], row['plot_y']
        dx_um = row[x_col] * 1000
        dy_um = row[y_col] * 1000
        dx_s  = dx_um * multiplier * 0.001
        dy_s  = dy_um * multiplier * 0.001

        arrow_len = np.sqrt(dx_s**2 + dy_s**2)
        if arrow_len > 0 and arrow_len < min_arrow:
            scale_up = min_arrow / arrow_len
            dx_s *= scale_up
            dy_s *= scale_up

        mag = row['magnitude']
        raw_x = row.get(coord_x_col) if coord_x_col in row.index else None
        raw_y = row.get(coord_y_col) if coord_y_col in row.index else None
        has_coords = (raw_x is not None and not (isinstance(raw_x, float) and np.isnan(raw_x)))
        if has_coords:
            pos_x = raw_x - panel_center_x
            pos_y = raw_y - panel_center_y
        else:
            pos_x = x - 2.5
            pos_y = y - 2.5

        pos_mag = np.sqrt(pos_x**2 + pos_y**2)
        pxn = (pos_x / pos_mag) if pos_mag > 0 else 0
        pyn = (pos_y / pos_mag) if pos_mag > 0 else 0

        em = np.sqrt(dx_s**2 + dy_s**2)
        exn = (dx_s / em) if em > 0 else 0
        eyn = (dy_s / em) if em > 0 else 0
        dot = exn * pxn + eyn * pyn

        if abs(dot) > expansion_thr:
            arrow_color = 'rgb(255, 80, 0)' if dot > 0 else 'rgb(0, 210, 210)'
            pattern = 'Expansion' if dot > 0 else 'Contraction'
            expansion_count += 1
        elif abs(dot) < twist_dot_thr and mag > twist_mag_thr:
            arrow_color = 'rgb(255, 215, 0)'
            pattern = 'Twist'
            twist_count += 1
        else:
            arrow_color = 'rgb(100, 150, 255)'
            pattern = 'Offset'
            offset_count += 1

        fig.add_annotation(
            x=x + dx_s, y=y + dy_s, ax=x, ay=y,
            xref='x', yref='y', axref='x', ayref='y',
            text='', showarrow=True,
            arrowhead=2, arrowsize=1.5, arrowwidth=2.5,
            arrowcolor=arrow_color, opacity=0.9,
        )
        scatter_x.append(x)
        scatter_y.append(y)
        scatter_text.append(str(row[grid_col]))
        loc_name = row[loc_col] if loc_col in row.index else row[grid_col]
        scatter_hover.append(
            f"<b>{loc_name}</b><br>Grid: {row[grid_col]}<br>Pattern: {pattern}<br>"
            f"DX: {dx_um:.2f} µm<br>DY: {dy_um:.2f} µm<br>Magnitude: {mag:.2f} µm<br>"
            f"<extra></extra>"
        )

    fig.add_trace(go.Scatter(
        x=scatter_x, y=scatter_y, mode='markers+text',
        marker=dict(color='#333333', size=14, line=dict(color='#FFFF00', width=2)),
        text=scatter_text, textposition='top center',
        textfont=dict(size=11, color='#FFFF00', family='Arial Black'),
        hovertemplate=scatter_hover, showlegend=False,
    ))

    fig.add_annotation(
        x=2.5, y=0.2,
        text=(
            f"<b>Pattern Detection Summary</b><br>"
            f"🔴 <b>Expansion</b>: arrows pointing away from centre<br>"
            f"🩵 <b>Contraction</b>: arrows pointing toward centre<br>"
            f"🟡 <b>Twist</b>: perpendicular arrows<br>"
            f"🔵 <b>Offset</b>: uniform shift<br><br>"
            f"Expansion/Contraction: {expansion_count} &nbsp; "
            f"Twist: {twist_count} &nbsp; Offset: {offset_count}"
        ),
        showarrow=False,
        bgcolor='rgba(26, 26, 26, 0.8)', bordercolor='#666666', borderwidth=1,
        font=dict(color='#E8E8E8', size=11), align='left',
        xref='x', yref='y',
    )

    chart_colors = settings.get('CHART_COLORS', {})
    fig.update_xaxes(
        range=[0.5, 4.5], dtick=1,
        showgrid=chart_colors.get('chart_gridlines_visible', False),
        gridcolor='#444444', title=dict(text='Column', font=dict(color='#E8E8E8')),
    )
    fig.update_yaxes(
        range=[0.5, 4.5], dtick=1,
        showgrid=chart_colors.get('chart_gridlines_visible', False),
        gridcolor='#444444', title=dict(text='Row', font=dict(color='#E8E8E8')),
    )
    fig.update_layout(
        title=dict(
            text=f'Pattern Hunter: ABF Distortion Map | {multiplier}x Sensitivity',
            font=dict(color='#E8E8E8', size=14),
        ),
        width=700, height=700,
        plot_bgcolor='#1a1a1a', paper_bgcolor='#1a1a1a',
        font=dict(color='#B0B0B0', size=11),
        hovermode='closest',
    )

    panel_image_path = get_panel_image_path()
    try:
        fig.add_layout_image(
            source=panel_image_path,
            xref='x', yref='y',
            x=0.5, y=4.5, sizex=4, sizey=4,
            sizing='stretch', opacity=0.25, layer='below',
        )
    except Exception:
        pass

    return fig


def plot_heatmap(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """PtV Distance heatmap on a 4×4 grid.

    Grid layout: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR
    """
    col_names = settings.get('COLUMN_NAMES', {})
    ptv_col  = col_names.get('ptv_distance', 'PtV Distance')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col  = col_names.get('location', 'Location')

    matrix = np.full((4, 4), np.nan)
    text_matrix = np.empty((4, 4), dtype=object)
    text_matrix[:] = ''

    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)
    ptv_microns = df_plot[ptv_col] * 1000

    for idx, row in df_plot.iterrows():
        gid = row[grid_col]
        if gid in _GRID_MATRIX_POSITIONS:
            r, c = _GRID_MATRIX_POSITIONS[gid]
            matrix[r, c] = ptv_microns.loc[idx]
            text_matrix[r, c] = f"Grid {gid}<br>{row[loc_col]}<br>{ptv_microns.loc[idx]:.3f} µm"

    fig = go.Figure(data=go.Heatmap(
        z=matrix, text=text_matrix,
        texttemplate='%{text}', hoverinfo='text',
        colorscale='Viridis',
        colorbar=dict(title='PtV Distance<br>(µm)'),
    ))

    chart_colors = settings.get('CHART_COLORS', {})
    fig.update_layout(
        title='PtV Distance Heatmap | Grid Layout: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR',
        xaxis=dict(
            title='Column', tickmode='array',
            tickvals=[0.5, 1.5, 2.5, 3.5], ticktext=['', '', '', ''],
            showticklabels=False, constrain='domain',
            showgrid=chart_colors.get('chart_gridlines_visible', False),
        ),
        yaxis=dict(
            title='Row', tickmode='array',
            tickvals=[0.5, 1.5, 2.5, 3.5], ticktext=['', '', '', ''],
            showticklabels=False, scaleanchor='x', scaleratio=1,
            showgrid=chart_colors.get('chart_gridlines_visible', False),
        ),
        width=800, height=800,
        plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF'),
    )
    return fig


# ---------------------------------------------------------------------------
# Distribution charts — Box plot and Violin
# ---------------------------------------------------------------------------

_QUARTER_MAP = {'1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'}
_QUARTER_ORDER = ['UL', 'LL', 'LR', 'UR']
_DEFAULT_QUARTER_COLORS = {
    'UL': '#1f77b4', 'LL': '#ff7f0e', 'LR': '#2ca02c', 'UR': '#d62728'
}


def plot_vtp_box(df: pd.DataFrame, settings: dict) -> go.Figure:
    """Box plot of VtP Distance SC grouped by Grid ID, coloured by quarter."""
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})
    q_colors  = settings.get('QUARTER_COLORS', _DEFAULT_QUARTER_COLORS)

    sc_col   = col_names.get('total_shift', 'VtP Distance (SC)')
    grid_col = col_names.get('grid_id', 'Grid ID')
    usl      = float(vtp_cfg.get('vtp_usl_um', 10.0))

    df_plot = df.dropna(subset=[grid_col, sc_col]).copy()
    df_plot['sc_um']    = pd.to_numeric(df_plot[sc_col],   errors='coerce') * 1000
    df_plot['grid_str'] = pd.to_numeric(df_plot[grid_col], errors='coerce') \
                            .astype(int).astype(str).str.zfill(2)
    df_plot['quarter']  = df_plot['grid_str'].str[0].map(_QUARTER_MAP)
    df_plot = df_plot.dropna(subset=['sc_um', 'quarter'])

    grid_order = sorted(df_plot['grid_str'].unique(), key=int)
    fig = px.box(
        df_plot, x='grid_str', y='sc_um', color='quarter',
        color_discrete_map=q_colors,
        category_orders={'grid_str': grid_order},
        labels={'grid_str': 'Grid ID', 'sc_um': 'VtP Distance SC (µm)', 'quarter': 'Quarter'},
        title='VtP Distance Distribution by Position',
    )
    fig.add_hline(y=usl, line_dash='dash', line_color='red',
                  annotation_text=f'USL {usl} µm', annotation_position='top right')
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
    return fig


def plot_vtp_violin(df: pd.DataFrame, settings: dict) -> go.Figure:
    """Violin of VtP Distance SC grouped by quarter, with inner box and jitter overlay."""
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})
    q_colors  = settings.get('QUARTER_COLORS', _DEFAULT_QUARTER_COLORS)

    sc_col   = col_names.get('total_shift', 'VtP Distance (SC)')
    grid_col = col_names.get('grid_id', 'Grid ID')
    usl      = float(vtp_cfg.get('vtp_usl_um', 10.0))

    df_plot = df.dropna(subset=[grid_col, sc_col]).copy()
    df_plot['sc_um']   = pd.to_numeric(df_plot[sc_col],   errors='coerce') * 1000
    df_plot['quarter'] = pd.to_numeric(df_plot[grid_col], errors='coerce') \
                           .astype(int).astype(str).str.zfill(2).str[0].map(_QUARTER_MAP)
    df_plot = df_plot.dropna(subset=['sc_um', 'quarter'])

    fig = px.violin(
        df_plot, x='quarter', y='sc_um', color='quarter',
        color_discrete_map=q_colors,
        category_orders={'quarter': _QUARTER_ORDER},
        box=True, points='all',
        labels={'quarter': 'Quarter', 'sc_um': 'VtP Distance SC (µm)'},
        title='VtP Distance Distribution by Quarter',
    )
    fig.add_hline(y=usl, line_dash='dash', line_color='red',
                  annotation_text=f'USL {usl} µm', annotation_position='top right')
    fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
    return fig
