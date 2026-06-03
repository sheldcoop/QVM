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

    Dark Catppuccin Mocha theme — consistent with box / strip charts.
    Concentric tolerance rings (zone colours) make pass/warn/fail obvious.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})

    dx_col   = col_names.get('x_distance', 'Shift (DX)')
    dy_col   = col_names.get('y_distance', 'Shift (DY)')
    sc_col   = col_names.get('ptv_distance', 'PtV Distance')
    loc_col  = col_names.get('location', 'Location')
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
        lambda v: (
            _DARK_ZONE['exceptional'] if v <= ring_exceptional else
            _DARK_ZONE['excellent']   if v <= ring_excellent   else
            _DARK_ZONE['good']        if v <= ring_good        else
            _DARK_ZONE['acceptable']  if v <= ring_acceptable  else
            _DARK_ZONE['fail']
        )
    )

    spread = ring_acceptable + 2.0
    fig = go.Figure()

    # Concentric tolerance rings using Catppuccin zone colours
    for r, color, dash in [
        (ring_exceptional, _DARK_ZONE['exceptional'], 'solid'),
        (ring_excellent,   _DARK_ZONE['excellent'],   'dot'),
        (ring_good,        _DARK_ZONE['good'],        'dash'),
        (ring_acceptable,  _DARK_ZONE['fail'],        'dot'),
    ]:
        fig.add_shape(
            type='circle', xref='x', yref='y',
            x0=-r, y0=-r, x1=r, y1=r,
            line=dict(color=color, width=2, dash=dash),
            fillcolor='rgba(0,0,0,0)', layer='below',
        )

    # Crosshairs — subtle on dark
    crosshair = dict(color='rgba(205,214,244,0.25)', width=1.2)
    fig.add_hline(y=0, line=crosshair)
    fig.add_vline(x=0, line=crosshair)

    fig.add_trace(go.Scatter(
        x=work['dx_um'], y=work['dy_um'],
        mode='markers+text',
        marker=dict(size=14, color=work['color'], line=dict(width=0)),
        text=work[grid_col].astype(str),
        textposition='top center',
        textfont=dict(size=10, color=_DARK_TEXT),
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

    # Summary stats (top left)
    sc = work['sc_um']
    n = int(len(sc))
    max_sc   = float(sc.max())  if n else 0.0
    mean_sc  = float(sc.mean()) if n else 0.0
    n_outside = int((sc > ring_acceptable).sum())
    fig.add_annotation(
        text=(f"<b>n</b> {n}  •  <b>max SC</b> {max_sc:.1f} µm  •  "
              f"<b>mean SC</b> {mean_sc:.1f} µm  •  <b>fail</b> {n_outside}"),
        xref='paper', yref='paper', x=0.02, y=0.98,
        xanchor='left', yanchor='top', showarrow=False, align='left',
        font=dict(size=11, color=_DARK_TEXT),
        bgcolor=_DARK_CARD_BG, bordercolor=_DARK_CARD_BD,
        borderwidth=1, borderpad=5,
    )
    # Zone legend (bottom, centred)
    _z = _DARK_ZONE   # short alias to avoid f-string quoting conflicts
    fig.add_annotation(
        text=(
            f"<span style='color:{_z['exceptional']}'>⬤</span> ≤{ring_exceptional:.1f}  "
            f"<span style='color:{_z['excellent']}'>⬤</span> ≤{ring_excellent:.1f}  "
            f"<span style='color:{_z['good']}'>⬤</span> ≤{ring_good:.1f}  "
            f"<span style='color:{_z['acceptable']}'>⬤</span> ≤{ring_acceptable:.1f}  "
            f"<span style='color:{_z['fail']}'>⬤</span> fail (µm)"
        ),
        xref='paper', yref='paper', x=0.5, y=-0.08,
        xanchor='center', yanchor='top', showarrow=False,
        font=dict(size=10, color=_DARK_TEXT),
        bgcolor=_DARK_CARD_BG, bordercolor=_DARK_CARD_BD,
        borderwidth=1, borderpad=5,
    )

    fig.update_layout(
        title=dict(text='DX vs DY Registration Bullseye — Via-to-Pad',
                   font=dict(size=14, color=_DARK_TEXT), x=0.5, xanchor='center'),
        xaxis=dict(title=dict(text='DX Shift (µm)', font=dict(color=_DARK_TEXT)),
                   zeroline=False, showgrid=False,
                   scaleanchor='y', scaleratio=1, range=[-spread, spread],
                   tickfont=dict(color=_DARK_TEXT)),
        yaxis=dict(title=dict(text='DY Shift (µm)', font=dict(color=_DARK_TEXT)),
                   zeroline=False, showgrid=False,
                   range=[-spread, spread],
                   tickfont=dict(color=_DARK_TEXT)),
        plot_bgcolor=_DARK_PLOT,
        paper_bgcolor=_DARK_PAPER,
        hovermode='closest',
        height=580,
        margin=dict(t=55, b=70, l=60, r=60),
    )
    return fig


def plot_vtp_site_bars(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """Per-fiducial-site SC bar chart for Via-to-Pad registration.

    Bars ordered by Grid ID (UL → LL → LR → UR), coloured by zone.
    Dark Catppuccin Mocha theme — consistent with bullseye and box/strip charts.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})

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
        lambda v: (
            _DARK_ZONE['exceptional'] if v <= ring_exceptional else
            _DARK_ZONE['excellent']   if v <= ring_excellent   else
            _DARK_ZONE['good']        if v <= ring_good        else
            _DARK_ZONE['acceptable']  if v <= ring_acceptable  else
            _DARK_ZONE['fail']
        )
    )

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=work[grid_col], y=work['sc_um'],
        marker_color=work['color'],
        marker_line=dict(width=0),   # no border — colour pops on dark
        customdata=work[[loc_col, 'sc_um']].values,
        hovertemplate=(
            'Grid ID: <b>%{x}</b><br>'
            'Location: %{customdata[0]}<br>'
            'SC: %{customdata[1]:.2f} µm<br>'
            '<extra></extra>'
        ),
        showlegend=False,
    ))

    for y_val, color, label in [
        (ring_excellent,  _DARK_ZONE['excellent'],  f'Excellent {ring_excellent:.1f} µm'),
        (ring_good,       _DARK_ZONE['good'],       f'Good {ring_good:.1f} µm'),
        (ring_acceptable, _DARK_ZONE['fail'],       f'Fail >{ring_acceptable:.0f} µm'),
    ]:
        fig.add_hline(
            y=y_val,
            line=dict(color=color, width=1.5, dash='dash'),
            annotation_text=label, annotation_position='right',
            annotation_font_size=10,
            annotation_font_color=color,
        )

    data_max = work['sc_um'].max() if not work.empty else 0.0
    y_max = max(data_max * 1.3, ring_acceptable * 1.2)
    fig.update_layout(
        title=dict(
            text='Registration SC per Fiducial Site (UL → LL → LR → UR)',
            font=dict(size=14, color=_DARK_TEXT), x=0.5, xanchor='center',
        ),
        xaxis=dict(
            title='',
            showgrid=False,
            type='category',
            tickfont=dict(color=_DARK_TEXT, size=12),
        ),
        yaxis=dict(
            title=dict(text='SC Distance (µm)', font=dict(color=_DARK_TEXT)),
            range=[0, y_max],
            showgrid=False,
            tickfont=dict(color=_DARK_TEXT),
        ),
        plot_bgcolor=_DARK_PLOT,
        paper_bgcolor=_DARK_PAPER,
        hovermode='x unified',
        height=450,
        margin=dict(t=55, b=40, l=60, r=110),
    )
    return fig


def plot_quiver(df: pd.DataFrame, settings: Dict, multiplier: float) -> go.Figure:
    """Pattern Hunter: ABF distortion quiver — Catppuccin Mocha dark theme.

    Matches the visual language of `plot_vtp_bullseye` and `plot_vtp_site_bars`:
    small zone-coloured site dots, Grid ID labels above, summary card top-left,
    pattern legend bottom-centre, subtle quadrant crosshairs.

    Arrow palette (sourced from `_DARK_ARROW`):
        Expansion   — red    (#f38ba8)
        Contraction — sky    (#89dceb)
        Twist       — yellow (#f9e2af)
        Offset      — blue   (#89b4fa)
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
    scatter_x, scatter_y, scatter_text, scatter_hover, scatter_color = [], [], [], [], []

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
            if dot > 0:
                arrow_color = _DARK_ARROW['expansion']
                pattern = 'Expansion'
            else:
                arrow_color = _DARK_ARROW['contraction']
                pattern = 'Contraction'
            expansion_count += 1
        elif abs(dot) < twist_dot_thr and mag > twist_mag_thr:
            arrow_color = _DARK_ARROW['twist']
            pattern = 'Twist'
            twist_count += 1
        else:
            arrow_color = _DARK_ARROW['offset']
            pattern = 'Offset'
            offset_count += 1

        fig.add_annotation(
            x=x + dx_s, y=y + dy_s, ax=x, ay=y,
            xref='x', yref='y', axref='x', ayref='y',
            text='', showarrow=True,
            arrowhead=2, arrowsize=1.4, arrowwidth=2.4,
            arrowcolor=arrow_color, opacity=0.95,
        )
        scatter_x.append(x)
        scatter_y.append(y)
        scatter_text.append(str(row[grid_col]))
        scatter_color.append(arrow_color)
        loc_name = row[loc_col] if loc_col in row.index else row[grid_col]
        scatter_hover.append(
            f"<b>{loc_name}</b><br>Grid: {row[grid_col]}<br>Pattern: {pattern}<br>"
            f"DX: {dx_um:.2f} µm<br>DY: {dy_um:.2f} µm<br>Mag: {mag:.2f} µm"
        )

    # Subtle quadrant crosshairs (matching bullseye)
    crosshair = dict(color='rgba(205,214,244,0.25)', width=1.2)
    fig.add_hline(y=2.5, line=crosshair)
    fig.add_vline(x=2.5, line=crosshair)

    # Site dots — bullseye-style: small, zone-coloured, label above
    fig.add_trace(go.Scatter(
        x=scatter_x, y=scatter_y, mode='markers+text',
        marker=dict(size=14, color=scatter_color, line=dict(width=0)),
        text=scatter_text,
        textposition='top center',
        textfont=dict(size=10, color=_DARK_TEXT),
        customdata=scatter_hover,
        hovertemplate='%{customdata}<extra></extra>',
        showlegend=False,
    ))

    total = expansion_count + twist_count + offset_count
    # Summary card — top-left, matches bullseye stats card
    fig.add_annotation(
        text=(
            f"<b>n</b> {total}  •  "
            f"<b>Exp/Con</b> {expansion_count}  •  "
            f"<b>Twist</b> {twist_count}  •  "
            f"<b>Offset</b> {offset_count}"
        ),
        xref='paper', yref='paper', x=0.02, y=0.98,
        xanchor='left', yanchor='top', showarrow=False, align='left',
        font=dict(size=11, color=_DARK_TEXT),
        bgcolor=_DARK_CARD_BG, bordercolor=_DARK_CARD_BD,
        borderwidth=1, borderpad=5,
    )

    # Pattern legend — bottom-centre, matches bullseye zone legend
    _a = _DARK_ARROW
    fig.add_annotation(
        text=(
            f"<span style='color:{_a['expansion']}'>⬤</span> Expansion  "
            f"<span style='color:{_a['contraction']}'>⬤</span> Contraction  "
            f"<span style='color:{_a['twist']}'>⬤</span> Twist  "
            f"<span style='color:{_a['offset']}'>⬤</span> Offset"
        ),
        xref='paper', yref='paper', x=0.5, y=-0.08,
        xanchor='center', yanchor='top', showarrow=False,
        font=dict(size=10, color=_DARK_TEXT),
        bgcolor=_DARK_CARD_BG, bordercolor=_DARK_CARD_BD,
        borderwidth=1, borderpad=5,
    )

    fig.update_xaxes(
        range=[0.5, 4.5], dtick=1,
        showgrid=False, zeroline=False, showticklabels=False,
        title=dict(text='Panel X (Grid Column)',
                   font=dict(color=_DARK_TEXT)),
    )
    fig.update_yaxes(
        range=[0.5, 4.5], dtick=1,
        showgrid=False, zeroline=False, showticklabels=False,
        scaleanchor='x', scaleratio=1,
        title=dict(text='Panel Y (Grid Row)',
                   font=dict(color=_DARK_TEXT)),
    )
    fig.update_layout(
        title=dict(
            text=f'ABF Distortion Map  ·  {multiplier}× Sensitivity',
            font=dict(size=14, color=_DARK_TEXT),
            x=0.5, xanchor='center',
        ),
        height=600,
        plot_bgcolor=_DARK_PLOT,
        paper_bgcolor=_DARK_PAPER,
        font=dict(color=_DARK_TEXT, size=11),
        hovermode='closest',
        margin=dict(t=55, b=70, l=60, r=60),
    )
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

# ===========================================================================
# DARK THEME — Box Plot & Strip Chart
# All visual constants live here.  Change ONE value to retheme both charts.
# ===========================================================================

# --- Backgrounds -----------------------------------------------------------
_DARK_PLOT     = '#1e1e2e'   # Catppuccin Mocha "base"  ← change to retheme
_DARK_PAPER    = '#181825'   # Catppuccin Mocha "mantle" (outer paper)

# --- Text & chrome ---------------------------------------------------------
_DARK_TEXT     = '#cdd6f4'   # Catppuccin Mocha "text"  (near white)
_DARK_SUB      = '#6c7086'   # Catppuccin Mocha "overlay0" (muted)
_DARK_SEP      = 'rgba(205,214,244,0.18)'   # vertical separator
_DARK_CARD_BG  = 'rgba(205,214,244,0.06)'   # annotation card background
_DARK_CARD_BD  = 'rgba(205,214,244,0.22)'   # annotation card border

# --- Zone dot / ring colours (bright against dark bg) ----------------------
_DARK_ZONE = {
    'exceptional': '#89b4fa',  # Catppuccin "blue"
    'excellent':   '#a6e3a1',  # Catppuccin "green"
    'good':        '#94e2d5',  # Catppuccin "teal"
    'acceptable':  '#fab387',  # Catppuccin "peach"
    'fail':        '#f38ba8',  # Catppuccin "red"
}

# --- Quiver pattern colours (sourced from Catppuccin Mocha palette) --------
_DARK_ARROW = {
    'expansion':   '#f38ba8',  # Catppuccin "red"    — moving outward
    'contraction': '#89dceb',  # Catppuccin "sky"    — moving inward
    'twist':       '#f9e2af',  # Catppuccin "yellow" — tangential
    'offset':      '#89b4fa',  # Catppuccin "blue"   — unaligned
}

# --- Quarter box colours (bright against dark bg) --------------------------
_DARK_QUARTER_COLORS = {
    'UL': '#89dceb',   # Catppuccin "sky"
    'LL': '#f9e2af',   # Catppuccin "yellow"
    'LR': '#a6e3a1',   # Catppuccin "green"
    'UR': '#cba6f7',   # Catppuccin "mauve"
}

# ===========================================================================


def _zone_legend_annotation(chart_colors: dict,
                             ring_exceptional: float, ring_excellent: float,
                             ring_good: float, ring_acceptable: float,
                             x: float = 0.5, y: float = -0.08,
                             xanchor: str = 'center', yanchor: str = 'top',
                             dark: bool = False) -> dict:
    """Return a Plotly annotation dict for the 5-zone colour legend."""
    if dark:
        blue, dg, green, orange, red = (
            _DARK_ZONE['exceptional'], _DARK_ZONE['excellent'],
            _DARK_ZONE['good'], _DARK_ZONE['acceptable'], _DARK_ZONE['fail'],
        )
        txt_color  = _DARK_TEXT
        bg_color   = _DARK_CARD_BG
        bd_color   = _DARK_CARD_BD
        font_size  = 11
    else:
        blue       = chart_colors.get('traffic_light_blue',       '#3498db')
        dg         = chart_colors.get('traffic_light_dark_green', '#1e7e3a')
        green      = chart_colors.get('traffic_light_green',      '#2ecc71')
        orange     = chart_colors.get('traffic_light_orange',     '#e67e22')
        red        = chart_colors.get('traffic_light_red',        '#e74c3c')
        txt_color  = '#444444'
        bg_color   = 'rgba(255,255,255,0.90)'
        bd_color   = '#dddddd'
        font_size  = 9
    return dict(
        text=(
            f"<span style='color:{blue}'>⬤</span> ≤{ring_exceptional:.1f}  "
            f"<span style='color:{dg}'>⬤</span> ≤{ring_excellent:.1f}  "
            f"<span style='color:{green}'>⬤</span> ≤{ring_good:.1f}  "
            f"<span style='color:{orange}'>⬤</span> ≤{ring_acceptable:.1f}  "
            f"<span style='color:{red}'>⬤</span> fail (µm)"
        ),
        xref='paper', yref='paper',
        x=x, y=y,
        xanchor=xanchor, yanchor=yanchor,
        showarrow=False,
        font=dict(size=font_size, color=txt_color),
        bgcolor=bg_color,
        bordercolor=bd_color,
        borderwidth=1,
        borderpad=6,
    )


def _stats_card_annotation(n: int, mean_v: float, median_v: float,
                            std_v: float, pct_pass: float,
                            dark: bool = False) -> dict:
    """Stats card placed *outside* the chart to the right.

    Position: x=1.03 (past the right edge of the plot area), anchored left.
    The calling chart must set margin.r ≥ 160 to give it space.
    Shows n, Mean, Median, Std Dev, Pass%.
    """
    if dark:
        pass_color = _DARK_ZONE['excellent'] if pct_pass == 100 else (
            _DARK_ZONE['acceptable'] if pct_pass >= 75 else _DARK_ZONE['fail'])
        txt_color = _DARK_TEXT
        bg_color  = _DARK_CARD_BG
        bd_color  = _DARK_CARD_BD
        font_size = 11
    else:
        pass_color = '#1e7e3a' if pct_pass == 100 else ('#e67e22' if pct_pass >= 75 else '#e74c3c')
        txt_color = '#222222'
        bg_color  = 'rgba(255,255,255,0.93)'
        bd_color  = '#cccccc'
        font_size = 10
    return dict(
        text=(
            f"<b>n</b>         {n}<br>"
            f"<b>Mean</b>    {mean_v:.2f} µm<br>"
            f"<b>Median</b>  {median_v:.2f} µm<br>"
            f"<b>Std Dev</b> {std_v:.2f} µm<br>"
            f"<b style='color:{pass_color}'>Pass</b>      {pct_pass:.0f}%"
        ),
        xref='paper', yref='paper',
        x=1.03, y=0.98,            # outside chart to the right
        xanchor='left', yanchor='top',
        showarrow=False,
        align='left',
        font=dict(size=font_size, color=txt_color, family='monospace'),
        bgcolor=bg_color,
        bordercolor=bd_color,
        borderwidth=1,
        borderpad=8,
    )


def plot_vtp_box(df: pd.DataFrame, settings: dict) -> go.Figure:
    """Panel-level box plot: one 'All sites' box + four quarter boxes side-by-side.

    Dark theme. Layout:  All | UL  LL  LR  UR
    Narrow, tall boxes (width=0.22, height=620). Bold zone-coloured dots (size=12).
    Mean-only reference line. Stats card top-right. Zone legend bottom-left.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})

    sc_col   = col_names.get('total_shift', 'VtP Distance (SC)')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col  = col_names.get('location', 'Location')

    ring_exceptional = float(vtp_cfg.get('ring_exceptional_um', 2.5))
    ring_excellent   = float(vtp_cfg.get('ring_excellent_um', 5.0))
    ring_good        = float(vtp_cfg.get('ring_good_um', 7.5))
    ring_acceptable  = float(vtp_cfg.get('ring_acceptable_um', 10.0))

    # ---- Prepare data -------------------------------------------------------
    df_plot = df.dropna(subset=[sc_col]).copy()
    df_plot['sc_um'] = pd.to_numeric(df_plot[sc_col], errors='coerce') * 1000
    df_plot = df_plot.dropna(subset=['sc_um'])

    if grid_col in df_plot.columns:
        df_plot['grid_str'] = (pd.to_numeric(df_plot[grid_col], errors='coerce')
                               .astype('Int64').astype(str).str.zfill(2))
        df_plot['quarter']  = df_plot['grid_str'].str[0].map(_QUARTER_MAP)
    else:
        df_plot['grid_str'] = '??'
        df_plot['quarter']  = None

    # Zone colours for dark bg
    df_plot['color'] = df_plot['sc_um'].apply(
        lambda v: (
            _DARK_ZONE['exceptional'] if v <= ring_exceptional else
            _DARK_ZONE['excellent']   if v <= ring_excellent   else
            _DARK_ZONE['good']        if v <= ring_good        else
            _DARK_ZONE['acceptable']  if v <= ring_acceptable  else
            _DARK_ZONE['fail']
        )
    )

    sc       = df_plot['sc_um']
    n        = len(sc)
    mean_v   = float(sc.mean())   if n else 0.0
    median_v = float(sc.median()) if n else 0.0
    std_v    = float(sc.std())    if n else 0.0
    n_fail   = int((sc > ring_acceptable).sum())
    pct_pass = 100.0 * (1 - n_fail / n) if n else 100.0

    rng = np.random.default_rng(42)

    fig = go.Figure()

    _x_order = ['All'] + _QUARTER_ORDER
    _x_pos   = {label: i for i, label in enumerate(_x_order)}

    # ---- Helper: narrow box + bold jitter dots ------------------------------
    def _add_box_and_dots(x_label: str, values: np.ndarray, colors: list,
                          hover_texts: list, labels: list,
                          fill: str, border: str) -> None:
        """Narrow box + jittered dots with Grid ID text labels."""
        fig.add_trace(go.Box(
            x=[x_label] * len(values),
            y=values,
            name=x_label,
            boxpoints=False,
            width=0.22,
            fillcolor=fill,
            line=dict(color=border, width=1.8),
            marker_color=border,
            showlegend=False,
            hoverinfo='skip',
        ))
        pos    = _x_pos[x_label]
        jitter = rng.uniform(-0.13, 0.13, size=len(values))
        fig.add_trace(go.Scatter(
            x=pos + jitter,
            y=values,
            mode='markers+text',
            marker=dict(color=colors, size=11, line=dict(width=0)),
            text=labels,
            textposition='top center',
            textfont=dict(size=9, color=_DARK_TEXT),
            customdata=hover_texts,
            hovertemplate='%{customdata}<extra></extra>',
            showlegend=False,
            xaxis='x2',
        ))

    def _hover(row: pd.Series) -> str:
        loc   = row.get(loc_col, '') if loc_col in df_plot.columns else ''
        grid  = row.get('grid_str', '')
        q     = row.get('quarter', '') or ''
        parts = [p for p in [loc, f'Grid {grid}', q] if p and p != 'nan']
        return f"{' · '.join(parts)} — {row['sc_um']:.2f} µm"

    hover_all = [_hover(row) for _, row in df_plot.iterrows()]

    # "All" box — glass effect + Grid ID labels + mean±std near USL
    _add_box_and_dots('All', sc.values, df_plot['color'].tolist(),
                      hover_all, df_plot['grid_str'].tolist(),
                      fill='rgba(255,255,255,0.07)', border='rgba(255,255,255,0.50)')
    fig.add_annotation(
        text=f"<b>{mean_v:.1f}</b> ± {std_v:.1f}",
        xref='x', yref='y',
        x='All', y=ring_acceptable * 1.08,
        xanchor='center', yanchor='bottom',
        showarrow=False,
        font=dict(size=13, color='rgba(205,214,244,0.80)'),
    )

    # Quarter boxes — coloured dots + mean±std near USL in each quarter's colour
    for q in _QUARTER_ORDER:
        qdf = df_plot[df_plot['quarter'] == q]
        if qdf.empty:
            continue
        hx = _DARK_QUARTER_COLORS[q].lstrip('#')
        ri, gi, bi = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        _add_box_and_dots(
            q, qdf['sc_um'].values, qdf['color'].tolist(),
            [_hover(row) for _, row in qdf.iterrows()],
            qdf['grid_str'].tolist(),
            fill=f'rgba({ri},{gi},{bi},0.13)',
            border=_DARK_QUARTER_COLORS[q],
        )
        # Mean ± std anchored near USL in the quarter's own bright colour
        fig.add_annotation(
            text=f"<b>{qdf['sc_um'].mean():.1f}</b> ± {qdf['sc_um'].std():.1f}",
            xref='x', yref='y',
            x=q, y=ring_acceptable * 1.08,
            xanchor='center', yanchor='bottom',
            showarrow=False,
            font=dict(size=13, color=_DARK_QUARTER_COLORS[q]),
        )

    # ---- Reference lines ----------------------------------------------------
    # USL — bright red, top left
    fig.add_hline(
        y=ring_acceptable,
        line_dash='dash',
        line_color=_DARK_ZONE['fail'],
        line_width=2.5,
        annotation_text=f'  USL {ring_acceptable:.1f} µm',
        annotation_position='top left',
        annotation_font_size=11,
        annotation_font_color=_DARK_ZONE['fail'],
    )
    # Mean — white dotted, labelled subtly at right edge
    fig.add_hline(y=mean_v, line_dash='dot',
                  line_color='rgba(255,255,255,0.55)', line_width=1.5)
    fig.add_annotation(
        text='<i>mean</i>',
        xref='paper', yref='y',
        x=0.985, y=mean_v,
        xanchor='right', yanchor='bottom',
        showarrow=False,
        font=dict(size=9, color=_DARK_SUB),
    )

    # Vertical separator between "All" and the four quarters
    fig.add_vline(x=0.5, line_color=_DARK_SEP, line_width=1, line_dash='dot')

    # ---- Annotations --------------------------------------------------------
    fig.add_annotation(**_stats_card_annotation(
        n, mean_v, median_v, std_v, pct_pass, dark=True))
    fig.add_annotation(**_zone_legend_annotation(
        {}, ring_exceptional, ring_excellent, ring_good, ring_acceptable, dark=True))

    # ---- Layout -------------------------------------------------------------
    n_cats = len(_x_order)
    fig.update_layout(
        title=dict(
            text='SC Distribution — Panel Overview by Quarter',
            font=dict(size=15, color=_DARK_TEXT),
            x=0.5, xanchor='center',
        ),
        xaxis=dict(
            type='category',
            categoryorder='array',
            categoryarray=_x_order,
            title='',
            tickfont=dict(size=13, color=_DARK_TEXT),
            showgrid=False,
            linecolor=_DARK_SEP,
        ),
        xaxis2=dict(
            overlaying='x',
            range=[-0.5, n_cats - 0.5],
            visible=False,
        ),
        yaxis=dict(
            title=dict(text='VtP Distance SC (µm)', font=dict(color=_DARK_TEXT)),
            zeroline=False,
            showgrid=False,
            tickfont=dict(color=_DARK_TEXT),
        ),
        plot_bgcolor=_DARK_PLOT,
        paper_bgcolor=_DARK_PAPER,
        hovermode='closest',
        height=640,
        margin=dict(t=65, b=80, l=70, r=175),
        boxmode='group',
    )
    return fig


def plot_vtp_strip(df: pd.DataFrame, settings: dict) -> go.Figure:
    """Strip chart of SC by quarter: IQR box + bold jittered dots labelled with Grid ID.

    Dark theme. Same information level as the box plot: stats card, mean line,
    USL, zone legend. Points are bigger and bolder on dark for impact.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})

    sc_col   = col_names.get('total_shift', 'VtP Distance (SC)')
    grid_col = col_names.get('grid_id', 'Grid ID')

    ring_exceptional = float(vtp_cfg.get('ring_exceptional_um', 2.5))
    ring_excellent   = float(vtp_cfg.get('ring_excellent_um', 5.0))
    ring_good        = float(vtp_cfg.get('ring_good_um', 7.5))
    ring_acceptable  = float(vtp_cfg.get('ring_acceptable_um', 10.0))

    # ---- Prepare data -------------------------------------------------------
    df_plot = df.dropna(subset=[sc_col]).copy()
    df_plot['sc_um'] = pd.to_numeric(df_plot[sc_col], errors='coerce') * 1000
    if grid_col in df_plot.columns:
        df_plot['grid_str'] = (pd.to_numeric(df_plot[grid_col], errors='coerce')
                               .astype('Int64').astype(str).str.zfill(2))
        df_plot['quarter']  = df_plot['grid_str'].str[0].map(_QUARTER_MAP)
    else:
        df_plot['grid_str'] = '??'
        df_plot['quarter']  = None
    df_plot = df_plot.dropna(subset=['sc_um', 'quarter'])

    # Zone colours for dark bg
    df_plot['color'] = df_plot['sc_um'].apply(
        lambda v: (
            _DARK_ZONE['exceptional'] if v <= ring_exceptional else
            _DARK_ZONE['excellent']   if v <= ring_excellent   else
            _DARK_ZONE['good']        if v <= ring_good        else
            _DARK_ZONE['acceptable']  if v <= ring_acceptable  else
            _DARK_ZONE['fail']
        )
    )

    sc       = df_plot['sc_um']
    n        = len(sc)
    mean_v   = float(sc.mean())   if n else 0.0
    median_v = float(sc.median()) if n else 0.0
    std_v    = float(sc.std())    if n else 0.0
    n_fail   = int((sc > ring_acceptable).sum())
    pct_pass = 100.0 * (1 - n_fail / n) if n else 100.0

    rng = np.random.default_rng(7)

    fig = go.Figure()

    _q_pos = {q: i for i, q in enumerate(_QUARTER_ORDER)}

    for quarter in _QUARTER_ORDER:
        qdf = df_plot[df_plot['quarter'] == quarter]
        if qdf.empty:
            continue

        hx = _DARK_QUARTER_COLORS[quarter].lstrip('#')
        ri, gi, bi = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)

        # IQR box — subtle fill, bright border
        fig.add_trace(go.Box(
            y=qdf['sc_um'].values,
            x0=quarter,
            name=quarter,
            boxpoints=False,
            marker_color=_DARK_QUARTER_COLORS[quarter],
            line_color=_DARK_QUARTER_COLORS[quarter],
            line=dict(color=_DARK_QUARTER_COLORS[quarter], width=1.8),
            fillcolor=f'rgba({ri},{gi},{bi},0.12)',
            width=0.25,
            showlegend=False,
            hoverinfo='skip',
        ))

        # Bold jittered dots on numeric overlay axis
        pos    = _q_pos[quarter]
        jitter = rng.uniform(-0.14, 0.14, size=len(qdf))
        fig.add_trace(go.Scatter(
            x=pos + jitter,
            y=qdf['sc_um'].values,
            mode='markers+text',
            marker=dict(color=qdf['color'].values, size=13,
                        line=dict(width=0)),  # no border → bold pop on dark
            text=qdf['grid_str'].values,
            textposition='middle right',
            textfont=dict(size=11, color=_DARK_TEXT),
            customdata=qdf[['grid_str', 'sc_um']].values,
            hovertemplate='Grid %{customdata[0]} — %{customdata[1]:.2f} µm<extra></extra>',
            showlegend=False,
            xaxis='x2',
        ))

    # ---- Reference lines ----------------------------------------------------
    fig.add_hline(
        y=ring_acceptable,
        line_dash='dash',
        line_color=_DARK_ZONE['fail'],
        line_width=2.5,
        annotation_text=f'  USL {ring_acceptable:.1f} µm',
        annotation_position='top left',
        annotation_font_size=11,
        annotation_font_color=_DARK_ZONE['fail'],
    )
    fig.add_hline(y=mean_v, line_dash='dot',
                  line_color='rgba(255,255,255,0.55)', line_width=1.5)
    fig.add_annotation(
        text='<i>mean</i>',
        xref='paper', yref='y',
        x=0.985, y=mean_v,
        xanchor='right', yanchor='bottom',
        showarrow=False,
        font=dict(size=9, color=_DARK_SUB),
    )

    # Per-quarter mean ± std labels above each column
    for quarter in _QUARTER_ORDER:
        qsc = df_plot.loc[df_plot['quarter'] == quarter, 'sc_um']
        if qsc.empty:
            continue
        fig.add_annotation(
            text=f"<b>{qsc.mean():.1f}</b> ± {qsc.std():.1f}",
            xref='x', yref='paper',
            x=quarter, y=1.03,
            xanchor='center', yanchor='bottom',
            showarrow=False,
            font=dict(size=10, color=_DARK_TEXT),
        )

    # ---- Annotations --------------------------------------------------------
    fig.add_annotation(**_stats_card_annotation(
        n, mean_v, median_v, std_v, pct_pass, dark=True))
    fig.add_annotation(**_zone_legend_annotation(
        {}, ring_exceptional, ring_excellent, ring_good, ring_acceptable, dark=True))

    # ---- Layout -------------------------------------------------------------
    n_cats = len(_QUARTER_ORDER)
    fig.update_layout(
        title=dict(
            text='SC Distribution by Quarter — Strip Chart',
            font=dict(size=15, color=_DARK_TEXT),
            x=0.5, xanchor='center',
        ),
        xaxis=dict(
            type='category',
            categoryorder='array',
            categoryarray=_QUARTER_ORDER,
            title='',                          # "Quarter" label removed
            tickfont=dict(size=13, color=_DARK_TEXT),
            showgrid=False,
        ),
        xaxis2=dict(
            overlaying='x',
            range=[-0.5, n_cats - 0.5],
            visible=False,
        ),
        yaxis=dict(
            title=dict(text='VtP Distance SC (µm)', font=dict(color=_DARK_TEXT)),
            zeroline=False,
            showgrid=False,
            tickfont=dict(color=_DARK_TEXT),
        ),
        plot_bgcolor=_DARK_PLOT,
        paper_bgcolor=_DARK_PAPER,
        hovermode='closest',
        height=640,
        margin=dict(t=70, b=80, l=70, r=175),
        boxmode='overlay',
    )
    return fig
