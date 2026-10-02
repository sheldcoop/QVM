"""Registration shrinkage charts."""

import plotly.graph_objects as go

from src import theme
from src.chart_helpers import apply_dark_layout

# Where each quadrant sits on the schematic panel.
_POSITIONS = {'UL': (-1.0, 1.0), 'LL': (-1.0, -1.0), 'LR': (1.0, -1.0), 'UR': (1.0, 1.0)}


def plot_shrinkage_quiver(result, title: str, *, height: int = 420) -> go.Figure:
    """How each quadrant differs from the panel average, as one arrow per quadrant.

    Arrow = (quadrant X ppm - panel X ppm, quadrant Y ppm - panel Y ppm). The
    longest arrow is drawn at a fixed length, so the picture shows the pattern;
    the numbers are in the hover text and the quadrant table.
    """
    fig = go.Figure()
    if result.quadrant.empty or result.full_panel.empty:
        return apply_dark_layout(fig, height=height, title=title)

    panel = result.full_panel.iloc[0]
    frame = result.quadrant.copy()
    frame['dx'] = frame['Shrinkage X (ppm)'] - float(panel['Shrinkage X (ppm)'])
    frame['dy'] = frame['Shrinkage Y (ppm)'] - float(panel['Shrinkage Y (ppm)'])
    largest = float(max(frame['dx'].abs().max(), frame['dy'].abs().max(), 1.0))
    scale = 0.8 / largest

    xs, ys, labels, hover = [], [], [], []
    for _, row in frame.iterrows():
        quadrant = str(row['Quadrant'])
        if quadrant not in _POSITIONS:
            continue
        x0, y0 = _POSITIONS[quadrant]
        xs.append(x0)
        ys.append(y0)
        labels.append(quadrant)
        hover.append(
            f"{quadrant}<br>X: {row['Shrinkage X (ppm)']:.1f} ppm ({row['dx']:+.1f} vs panel)"
            f"<br>Y: {row['Shrinkage Y (ppm)']:.1f} ppm ({row['dy']:+.1f} vs panel)")
        fig.add_annotation(
            x=x0 + float(row['dx']) * scale, y=y0 + float(row['dy']) * scale, ax=x0, ay=y0,
            xref='x', yref='y', axref='x', ayref='y',
            showarrow=True, arrowhead=3, arrowsize=1, arrowwidth=2,
            arrowcolor=theme.PALETTE['peach'],
        )

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='markers+text', text=labels, textposition='top center',
        marker=dict(size=12, color=theme.PALETTE['blue']),
        hovertemplate='%{customdata}<extra></extra>', customdata=hover,
        name='Quadrant centre',
    ))
    return apply_dark_layout(
        fig, height=height, title=title,
        xaxis=dict(visible=False, range=[-2.0, 2.0]),
        yaxis=dict(visible=False, range=[-2.0, 2.0], scaleanchor='x', scaleratio=1),
        margin=dict(l=20, r=20, t=50, b=20), showlegend=False,
    )


def plot_quadrant_bars(result, title: str, *, height: int = 420) -> go.Figure:
    """X and Y shrinkage of each quadrant as bars, with the panel value as a line."""
    fig = go.Figure()
    if result.quadrant.empty or result.full_panel.empty:
        return apply_dark_layout(fig, height=height, title=title)

    panel = result.full_panel.iloc[0]
    quadrants = result.quadrant['Quadrant'].tolist()
    for axis, colour in (('X', theme.PALETTE['blue']), ('Y', theme.PALETTE['peach'])):
        values = result.quadrant[f'Shrinkage {axis} (ppm)']
        deltas = result.quadrant[f'Delta {axis} (um)']
        fig.add_trace(go.Bar(
            x=quadrants, y=values, name=f'{axis} quadrant', marker_color=colour,
            customdata=deltas,
            hovertemplate=f'%{{x}} {axis}: %{{y:.1f}} ppm (%{{customdata:.1f}} µm)<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=quadrants, y=[float(panel[f'Shrinkage {axis} (ppm)'])] * len(quadrants),
            mode='lines', name=f'{axis} panel', line=dict(color=colour, dash='dash', width=2),
            hovertemplate=f'Panel {axis}: %{{y:.1f}} ppm<extra></extra>',
        ))
    return apply_dark_layout(
        fig, height=height, title=title, barmode='group',
        yaxis=dict(title='ppm (negative = shrink)', zeroline=True,
                   zerolinecolor=theme.CROSSHAIR, gridcolor=theme.SEPARATOR),
        xaxis=dict(title='Quadrant'),
        legend=dict(orientation='h', y=-0.22), margin=dict(l=60, r=20, t=50, b=70),
    )


def plot_fit_residuals(result, design: dict, title: str, *, height: int = 460) -> go.Figure:
    """Affine fit: every point at its design position, sized and coloured by how far
    the measured point lies from the fit. Rejected points are drawn in red."""
    fig = go.Figure()
    if result.points.empty or not design:
        return apply_dark_layout(fig, height=height, title=title)

    points = result.points.copy()
    points['x'] = [float(design[name]['x']) for name in points['Location']]
    points['y'] = [float(design[name]['y']) for name in points['Location']]
    largest = max(float(points['Residual (um)'].max()), 1e-9)
    for rejected, colour, label in ((False, theme.PALETTE['green'], 'Used in the fit'),
                                    (True, theme.PALETTE['red'], 'Rejected')):
        part = points[points['Rejected'] == rejected]
        if part.empty:
            continue
        fig.add_trace(go.Scatter(
            x=part['x'], y=part['y'], mode='markers+text', name=label,
            text=part['Location'], textposition='top center',
            textfont=dict(color=theme.TEXT_MUTED, size=9),
            marker=dict(color=colour, size=8 + 22 * part['Residual (um)'] / largest,
                        line=dict(color=theme.TEXT, width=1)),
            customdata=part['Residual (um)'],
            hovertemplate='%{text}: %{customdata:.1f} µm off the fit<extra></extra>',
        ))
    return apply_dark_layout(
        fig, height=height, title=title,
        xaxis=dict(title='Design X (mm)', gridcolor=theme.SEPARATOR, zeroline=False),
        yaxis=dict(title='Design Y (mm)', gridcolor=theme.SEPARATOR, zeroline=False,
                   scaleanchor='x', scaleratio=1),
        legend=dict(orientation='h', y=-0.18), margin=dict(l=60, r=20, t=50, b=70),
    )
