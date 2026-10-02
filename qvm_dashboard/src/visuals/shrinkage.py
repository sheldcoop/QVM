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
