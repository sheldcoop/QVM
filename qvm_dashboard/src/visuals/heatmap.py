"""PtV Distance heatmap on the 4×4 grid."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from typing import Dict

from src import theme


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
        if gid in theme.GRID_MATRIX_POSITIONS:
            r, c = theme.GRID_MATRIX_POSITIONS[gid]
            matrix[r, c] = ptv_microns.loc[idx]
            text_matrix[r, c] = f"Grid {gid}<br>{row[loc_col]}<br>{ptv_microns.loc[idx]:.3f} µm"

    fig = go.Figure(data=go.Heatmap(
        z=matrix, text=text_matrix,
        texttemplate='%{text}', hoverinfo='text',
        colorscale='Viridis',
        colorbar=dict(title='PtV Distance<br>(µm)'),
    ))

    chart_colors = settings.get('CHART_COLORS', {})
    size = settings.get('CHART_HEIGHTS', {}).get('heatmap', 800)
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
        width=size, height=size,
        plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF'),
    )
    return fig
