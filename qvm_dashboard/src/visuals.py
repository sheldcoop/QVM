import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from typing import Dict

def plot_bullseye_scatter(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """
    Create a Bullseye Scatter plot of Shift (DX) vs Shift (DY).
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    loc_col = col_names.get('location', 'Location')

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        text=loc_col,
        title="Bullseye Scatter (X Shift vs Y Shift)",
        labels={x_col: 'DX Shift (mm)', y_col: 'DY Shift (mm)'}
    )

    # Update layout to make it a square and centered
    fig.update_traces(textposition='top center')

    # Add crosshairs
    fig.add_hline(y=0, line_dash="dash", line_color="red", opacity=0.5)
    fig.add_vline(x=0, line_dash="dash", line_color="red", opacity=0.5)

    # Make axes symmetric
    max_val = max(abs(df[x_col].max()), abs(df[x_col].min()),
                  abs(df[y_col].max()), abs(df[y_col].min()))

    # Add a little padding
    max_val = max_val * 1.2 if max_val > 0 else 0.1

    fig.update_xaxes(range=[-max_val, max_val], zeroline=False)
    fig.update_yaxes(range=[-max_val, max_val], zeroline=False)
    fig.update_layout(width=700, height=700)

    return fig


def plot_quiver(df: pd.DataFrame, settings: Dict, multiplier: float) -> go.Figure:
    """
    Create a Quiver/Vector Plot mapping shifts to a 4x4 grid.
    Arrows represent the direction and magnitude (exaggerated) of the DX/DY shift.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col = col_names.get('location', 'Location')

    # Extract row and col from grid_id (e.g., 11 -> row 1, col 1)
    df_plot = df.dropna(subset=[grid_col]).copy()

    # Handle grid_id properly
    # Convert to int to ensure correct string slicing if it comes as float
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)

    # Grid coordinates (1-4 for X and Y)
    # The grid IDs are like '11', '12', '13', '14' (Row, Col)
    # So Y is 4 - (Row - 1) to make Row 1 at the top. Let's map directly:
    df_plot['grid_col'] = df_plot[grid_col].str[1].astype(float)
    df_plot['grid_row'] = df_plot[grid_col].str[0].astype(float)

    # For plotting, row 1 should be at the top, so we invert Y
    df_plot['plot_y'] = 5 - df_plot['grid_row']
    df_plot['plot_x'] = df_plot['grid_col']

    fig = go.Figure()

    # Add quiver annotations
    for _, row in df_plot.iterrows():
        x = row['plot_x']
        y = row['plot_y']

        dx = row[x_col] * multiplier
        dy = row[y_col] * multiplier

        fig.add_annotation(
            x=x + dx,
            y=y + dy,
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
            arrowwidth=2,
            arrowcolor="blue"
        )

        # Add a dot at the origin
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='markers+text',
            marker=dict(color='red', size=8),
            text=[row[loc_col]],
            textposition="bottom center",
            showlegend=False
        ))

    # Setup the 4x4 grid layout
    fig.update_xaxes(range=[0.5, 4.5], dtick=1, showgrid=True, title="Grid Column")
    fig.update_yaxes(range=[0.5, 4.5], dtick=1, showgrid=True, title="Grid Row")
    fig.update_layout(
        title=f"Vector Shift Plot (Multiplier: {multiplier}x)",
        width=700,
        height=700
    )

    return fig


def plot_heatmap(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """
    Create a Heatmap based on the magnitude of the PtV distance on a 4x4 grid.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    ptv_col = col_names.get('ptv_distance', 'PtV Distance')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col = col_names.get('location', 'Location')

    # Create an empty 4x4 matrix
    matrix = np.zeros((4, 4))
    matrix[:] = np.nan # Use NaN for missing values

    text_matrix = np.empty((4, 4), dtype=object)

    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)

    for _, row in df_plot.iterrows():
        r = int(row[grid_col][0]) - 1 # 0-indexed row
        c = int(row[grid_col][1]) - 1 # 0-indexed col
        if 0 <= r < 4 and 0 <= c < 4:
            matrix[r, c] = row[ptv_col]
            text_matrix[r, c] = f"{row[loc_col]}<br>{row[ptv_col]:.4f}"

    fig = go.Figure(data=go.Heatmap(
        z=matrix,
        text=text_matrix,
        texttemplate="%{text}",
        hoverinfo="text",
        colorscale='Viridis'
    ))

    # Update axes to show grid labels
    fig.update_layout(
        title="PtV Distance Magnitude Heatmap",
        xaxis=dict(title="Column", tickmode='array', tickvals=[0, 1, 2, 3], ticktext=['1', '2', '3', '4']),
        yaxis=dict(title="Row", tickmode='array', tickvals=[0, 1, 2, 3], ticktext=['1', '2', '3', '4'], autorange='reversed'),
        width=700,
        height=700
    )

    return fig
