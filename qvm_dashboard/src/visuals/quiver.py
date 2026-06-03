"""Pattern Hunter: ABF distortion quiver / vector plot."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Dict

from src import theme
from src.chart_helpers import apply_dark_layout


def plot_quiver(df: pd.DataFrame, settings: Dict, multiplier: float) -> go.Figure:
    """Pattern Hunter: ABF distortion quiver — Catppuccin Mocha dark theme.

    Small zone-coloured site dots with Grid ID labels above, summary card
    top-left, pattern legend bottom-centre, subtle quadrant crosshairs.

    Arrow palette (``theme.ARROW``):
        Expansion — red · Contraction — sky · Twist — yellow · Offset — blue
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

    height = settings.get('CHART_HEIGHTS', {}).get('quiver', 600)

    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)
    df_plot['plot_x'] = df_plot[grid_col].map(
        lambda gid: theme.GRID_PLOT_POSITIONS.get(gid, (np.nan, np.nan))[0])
    df_plot['plot_y'] = df_plot[grid_col].map(
        lambda gid: theme.GRID_PLOT_POSITIONS.get(gid, (np.nan, np.nan))[1])
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
                arrow_color = theme.ARROW['expansion']
                pattern = 'Expansion'
            else:
                arrow_color = theme.ARROW['contraction']
                pattern = 'Contraction'
            expansion_count += 1
        elif abs(dot) < twist_dot_thr and mag > twist_mag_thr:
            arrow_color = theme.ARROW['twist']
            pattern = 'Twist'
            twist_count += 1
        else:
            arrow_color = theme.ARROW['offset']
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
    crosshair = dict(color=theme.CROSSHAIR, width=1.2)
    fig.add_hline(y=2.5, line=crosshair)
    fig.add_vline(x=2.5, line=crosshair)

    # Site dots — bullseye-style: small, zone-coloured, label above
    fig.add_trace(go.Scatter(
        x=scatter_x, y=scatter_y, mode='markers+text',
        marker=dict(size=14, color=scatter_color, line=dict(width=0)),
        text=scatter_text,
        textposition='top center',
        textfont=dict(size=10, color=theme.TEXT),
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
        font=dict(size=11, color=theme.TEXT),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD,
        borderwidth=1, borderpad=5,
    )

    # Pattern legend — bottom-centre, matches bullseye zone legend
    _a = theme.ARROW
    fig.add_annotation(
        text=(
            f"<span style='color:{_a['expansion']}'>⬤</span> Expansion  "
            f"<span style='color:{_a['contraction']}'>⬤</span> Contraction  "
            f"<span style='color:{_a['twist']}'>⬤</span> Twist  "
            f"<span style='color:{_a['offset']}'>⬤</span> Offset"
        ),
        xref='paper', yref='paper', x=0.5, y=-0.08,
        xanchor='center', yanchor='top', showarrow=False,
        font=dict(size=10, color=theme.TEXT),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD,
        borderwidth=1, borderpad=5,
    )

    fig.update_xaxes(
        range=[0.5, 4.5], dtick=1,
        showgrid=False, zeroline=False, showticklabels=False,
        title=dict(text='Panel X (Grid Column)', font=dict(color=theme.TEXT)),
    )
    fig.update_yaxes(
        range=[0.5, 4.5], dtick=1,
        showgrid=False, zeroline=False, showticklabels=False,
        scaleanchor='x', scaleratio=1,
        title=dict(text='Panel Y (Grid Row)', font=dict(color=theme.TEXT)),
    )
    apply_dark_layout(
        fig, height=height,
        title=dict(
            text=f'ABF Distortion Map  ·  {multiplier}× Sensitivity',
            font=dict(size=14, color=theme.TEXT),
            x=0.5, xanchor='center',
        ),
        hovermode='closest',
        margin=dict(t=55, b=70, l=60, r=60),
    )
    return fig
