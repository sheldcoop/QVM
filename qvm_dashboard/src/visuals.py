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

    fig.update_xaxes(range=[-max_val, max_val], zeroline=False)
    fig.update_yaxes(range=[-max_val, max_val], zeroline=False)
    fig.update_layout(width=700, height=700)

    return fig


def plot_quiver(df: pd.DataFrame, settings: Dict, multiplier: float) -> go.Figure:
    """
    Create a Quiver/Vector Plot mapping shifts to a 4x4 grid.
    Arrows represent the direction and magnitude (exaggerated) of the DX/DY shift.
    Color-coded: Green (small) → Yellow → Red (large).
    Grid layout matches panel: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'Shift (DX)')
    y_col = col_names.get('y_distance', 'Shift (DY)')
    grid_col = col_names.get('grid_id', 'Grid ID')
    loc_col = col_names.get('location', 'Location')

    # Extract row and col from grid_id
    df_plot = df.dropna(subset=[grid_col]).copy()
    df_plot[grid_col] = df_plot[grid_col].astype(int).astype(str)

    # Create explicit mapping: Grid ID -> (plot_x, plot_y)
    # Pattern within each quadrant: 1=top-left, 2=bottom-left, 3=bottom-right, 4=top-right
    # Plot coordinates: (1,1)=bottom-left, (4,4)=top-right
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
    
    df_plot['plot_x'] = df_plot[grid_col].map(lambda gid: grid_position_map.get(gid, (0, 0))[0])
    df_plot['plot_y'] = df_plot[grid_col].map(lambda gid: grid_position_map.get(gid, (0, 0))[1])
    
    # Calculate magnitude for color mapping (use raw values, not multiplied)
    df_plot['magnitude'] = np.sqrt(df_plot[x_col]**2 + df_plot[y_col]**2) * 1000  # Convert to microns

    fig = go.Figure()
    
    # Define color scale thresholds (in microns)
    max_mag = df_plot['magnitude'].max()
    min_mag = df_plot['magnitude'].min()

    # Add quiver annotations with color coding
    for _, row in df_plot.iterrows():
        x = row['plot_x']
        y = row['plot_y']

        dx = row[x_col] * multiplier
        dy = row[y_col] * multiplier
        mag = row['magnitude']
        
        # Color mapping: green → yellow → red based on magnitude
        if max_mag > min_mag:
            normalized = (mag - min_mag) / (max_mag - min_mag)
        else:
            normalized = 0.5
            
        # RGB interpolation: Green(0,255,0) → Yellow(255,255,0) → Red(255,0,0)
        if normalized < 0.5:
            # Green to Yellow
            r = int(255 * (normalized * 2))
            g = 255
            b = 0
        else:
            # Yellow to Red
            r = 255
            g = int(255 * (1 - (normalized - 0.5) * 2))
            b = 0
        
        arrow_color = f'rgb({r},{g},{b})'

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
            arrowwidth=2.5,
            arrowcolor=arrow_color,
            opacity=0.8
        )

        # Add a dot at the origin with grid label
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='markers+text',
            marker=dict(color='darkblue', size=10, line=dict(color='white', width=1)),
            text=[row[grid_col]],
            textposition="middle center",
            textfont=dict(size=9, color='white', family='Arial Black'),
            hovertemplate=(
                f"<b>{row[loc_col]}</b><br>" +
                f"Grid: {row[grid_col]}<br>" +
                f"DX: {row[x_col]*1000:.3f} µm<br>" +
                f"DY: {row[y_col]*1000:.3f} µm<br>" +
                f"Magnitude: {mag:.3f} µm<br>" +
                "<extra></extra>"
            ),
            showlegend=False
        ))

    # Add colorbar legend using a dummy scatter trace
    colorbar_trace = go.Scatter(
        x=[None],
        y=[None],
        mode='markers',
        marker=dict(
            colorscale=[[0, 'green'], [0.5, 'yellow'], [1, 'red']],
            cmin=min_mag,
            cmax=max_mag,
            colorbar=dict(
                title="Shift<br>Magnitude<br>(µm)",
                thickness=15,
                len=0.7,
                x=1.12
            ),
            showscale=True
        ),
        hoverinfo='none',
        showlegend=False
    )
    fig.add_trace(colorbar_trace)

    # Setup the 4x4 grid layout
    fig.update_xaxes(range=[0.5, 4.5], dtick=1, showgrid=True, gridcolor='lightgray', title="Column")
    fig.update_yaxes(range=[0.5, 4.5], dtick=1, showgrid=True, gridcolor='lightgray', title="Row")
    fig.update_layout(
        title=f"Vector Shift Plot | {multiplier}x Multiplier | Grid: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR",
        width=750,
        height=700,
        plot_bgcolor='#f8f9fa',
        hovermode='closest'
    )

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
    # Matrix indexing: [0,0]=top-left, [3,3]=bottom-right
    # Pattern within each quadrant: 1=top-left, 2=bottom-left, 3=bottom-right, 4=top-right
    grid_matrix_map = {
        # Upper Left Quadrant (11-14)
        '11': (0, 0), '12': (1, 0), '13': (1, 1), '14': (0, 1),
        # Lower Left Quadrant (21-24)
        '21': (2, 0), '22': (3, 0), '23': (3, 1), '24': (2, 1),
        # Lower Right Quadrant (31-34)
        '31': (2, 2), '32': (3, 2), '33': (3, 3), '34': (2, 3),
        # Upper Right Quadrant (41-44)
        '41': (0, 2), '42': (1, 2), '43': (1, 3), '44': (0, 3),
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

    # Update axes to show grid labels matching the panel layout
    fig.update_layout(
        title="PtV Distance Heatmap | Grid Layout: 11-14=UL, 21-24=LL, 31-34=LR, 41-44=UR",
        xaxis=dict(
            title="Column", 
            tickmode='array', 
            tickvals=[0.5, 1.5, 2.5, 3.5], 
            ticktext=['', '', '', ''],
            showticklabels=False
        ),
        yaxis=dict(
            title="Row", 
            tickmode='array', 
            tickvals=[0.5, 1.5, 2.5, 3.5], 
            ticktext=['', '', '', ''],
            showticklabels=False
        ),
        width=700,
        height=700
    )

    return fig
