"""Registration shrinkage charts (company method)."""

import plotly.graph_objects as go

from src import theme
from src.chart_helpers import apply_dark_layout

_CORNERS = ('1', '2', '3', '4')  # top-left, bottom-left, bottom-right, top-right
_ARROW_SHARE = 0.22              # longest arrow, as a share of the quadrant size


def _centre(points: dict, quadrant: str):
    xs = [float(points[f'{quadrant}_{c}']['x']) for c in _CORNERS]
    ys = [float(points[f'{quadrant}_{c}']['y']) for c in _CORNERS]
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, max(xs) - min(xs), max(ys) - min(ys)


def plot_shrinkage_panel(result, design: dict, title: str, *, height: int = 600) -> go.Figure:
    """The panel drawn to scale, with the shrinkage of each quadrant on it.

    Same look as the distortion quiver map: site dots with labels, a summary
    card top-left, a legend bottom-centre, quadrant crosshairs. Each quadrant
    carries one horizontal arrow (X) and one vertical arrow (Y): pointing
    outward from the quadrant centre and red when it grew, inward and sky-blue
    when it shrank. Arrow length is relative to the largest value on the panel;
    the numbers are written next to the arrows.
    """
    fig = go.Figure()
    if result.quadrant.empty or result.full_panel.empty or not design:
        return apply_dark_layout(fig, height=height, title=title)

    points = {str(name).upper(): xy for name, xy in design.items()}
    table = result.quadrant.set_index('Quadrant')
    largest = max(float(table['Shrinkage X (ppm)'].abs().max()),
                  float(table['Shrinkage Y (ppm)'].abs().max()), 1e-9)

    for quadrant, row in table.iterrows():
        if not all(f'{quadrant}_{c}' in points for c in _CORNERS):
            continue
        cx, cy, width, depth = _centre(points, quadrant)
        fig.add_shape(type='rect', x0=cx - width / 2, x1=cx + width / 2,
                      y0=cy - depth / 2, y1=cy + depth / 2,
                      line=dict(color=theme.CARD_BD, width=1.2), fillcolor=theme.CARD_BG,
                      layer='below')
        for axis, (ux, uy), size in (('X', (1, 0), width), ('Y', (0, 1), depth)):
            ppm = float(row[f'Shrinkage {axis} (ppm)'])
            length = size * _ARROW_SHARE * abs(ppm) / largest
            colour = theme.ARROW['expansion'] if ppm >= 0 else theme.ARROW['contraction']
            edge = size / 2 - size * 0.03  # arrows sit just inside the quadrant edge
            # X arrows run below the value box, Y arrows through the middle column.
            line_y = cy - depth * 0.30 if axis == 'X' else cy
            for side in (1, -1):  # both ends of the quadrant move
                outer = (cx + side * ux * edge, line_y + side * uy * edge)
                inner = (outer[0] - side * ux * length, outer[1] - side * uy * length)
                tail, head = (inner, outer) if ppm >= 0 else (outer, inner)
                fig.add_annotation(
                    x=head[0], y=head[1], ax=tail[0], ay=tail[1],
                    xref='x', yref='y', axref='x', ayref='y', text='', showarrow=True,
                    arrowhead=2, arrowsize=1.4, arrowwidth=2.4, arrowcolor=colour, opacity=0.95)
        fig.add_annotation(
            x=cx, y=cy, xref='x', yref='y', showarrow=False, align='center',
            text=(f"<b>{quadrant}</b><br>"
                  f"X {row['Delta X (um)']:+.1f} µm  ({row['Shrinkage X (ppm)']:+.0f} ppm)<br>"
                  f"Y {row['Delta Y (um)']:+.1f} µm  ({row['Shrinkage Y (ppm)']:+.0f} ppm)"),
            font=dict(size=11, color=theme.TEXT),
            bgcolor=theme.PLOT_BG, bordercolor=theme.CARD_BD, borderwidth=1, borderpad=4)

    names = sorted(points)
    # Labels point into their own quadrant, so neighbours across a gap do not collide.
    inward = {'1': 'bottom right', '2': 'top right', '3': 'top left', '4': 'bottom left'}
    fig.add_trace(go.Scatter(
        x=[float(points[n]['x']) for n in names], y=[float(points[n]['y']) for n in names],
        mode='markers+text', text=names,
        textposition=[inward.get(n[-1], 'top center') for n in names],
        textfont=dict(size=9, color=theme.TEXT_MUTED),
        marker=dict(size=9, color=theme.PALETTE['blue'], line=dict(width=0)),
        hovertemplate='%{text}<br>design %{x:.3f}, %{y:.3f} mm<extra></extra>', showlegend=False,
    ))

    crosshair = dict(color=theme.CROSSHAIR, width=1.2)
    fig.add_hline(y=0, line=crosshair)
    fig.add_vline(x=0, line=crosshair)

    panel = result.full_panel.iloc[0]
    uniformity = result.uniformity.iloc[0]
    fig.add_annotation(
        text=(f"<b>Panel X</b> {panel['Delta X (um)']:+.1f} µm ({panel['Shrinkage X (ppm)']:+.0f} ppm)  •  "
              f"<b>Panel Y</b> {panel['Delta Y (um)']:+.1f} µm ({panel['Shrinkage Y (ppm)']:+.0f} ppm)  •  "
              f"<b>Range</b> X {uniformity['QTQ Range X (ppm)']:.0f} / "
              f"Y {uniformity['QTQ Range Y (ppm)']:.0f} ppm"),
        xref='paper', yref='paper', x=0.0, y=1.0, xanchor='left', yanchor='bottom',
        showarrow=False, align='left', font=dict(size=11, color=theme.TEXT),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD, borderwidth=1, borderpad=5)
    arrows = theme.ARROW
    fig.add_annotation(
        text=(f"<span style='color:{arrows['expansion']}'>⬤</span> Grew (measured &gt; design)  "
              f"<span style='color:{arrows['contraction']}'>⬤</span> Shrank (measured &lt; design)"),
        xref='paper', yref='paper', x=0.5, y=-0.14, xanchor='center', yanchor='top',
        showarrow=False, font=dict(size=10, color=theme.TEXT),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD, borderwidth=1, borderpad=5)

    xs = [float(xy['x']) for xy in points.values()]
    ys = [float(xy['y']) for xy in points.values()]
    pad_x, pad_y = (max(xs) - min(xs)) * 0.08, (max(ys) - min(ys)) * 0.14
    fig.update_xaxes(range=[min(xs) - pad_x, max(xs) + pad_x], showgrid=False, zeroline=False,
                     showticklabels=False,
                     title=dict(text='Panel X (design, to scale)', font=dict(color=theme.TEXT)))
    fig.update_yaxes(range=[min(ys) - pad_y, max(ys) + pad_y], showgrid=False, zeroline=False,
                     showticklabels=False, scaleanchor='x', scaleratio=1,
                     title=dict(text='Panel Y', font=dict(color=theme.TEXT)))
    return apply_dark_layout(
        fig, height=height,
        title=dict(text=title, font=dict(size=14, color=theme.TEXT), x=0.5, xanchor='center'),
        hovermode='closest', margin=dict(t=85, b=95, l=60, r=60))


_BAR_COLOURS = {'X': '#E0965A', 'Y': theme.PALETTE['sky']}  # copper, sky


def plot_quadrant_bars(result, title: str, *, height: int = 440) -> go.Figure:
    """X and Y shrinkage of each quadrant as bars, with the panel value as a line.

    Every text colour is set here on purpose: when the app runs in a light
    theme, anything left to the default turns black on the dark chart.
    """
    fig = go.Figure()
    if result.quadrant.empty or result.full_panel.empty:
        return apply_dark_layout(fig, height=height, title=title)

    panel = result.full_panel.iloc[0]
    quadrants = result.quadrant['Quadrant'].tolist()
    text = dict(color=theme.TEXT, size=12)
    for axis, colour in _BAR_COLOURS.items():
        values = result.quadrant[f'Shrinkage {axis} (ppm)']
        deltas = result.quadrant[f'Delta {axis} (um)']
        fig.add_trace(go.Bar(
            x=quadrants, y=values, name=f'{axis} per quadrant',
            marker=dict(color=colour, line=dict(color=theme.PLOT_BG, width=1)),
            text=[f'{v:+.0f}' for v in values], textposition='inside', insidetextanchor='end',
            textfont=dict(color=theme.PALETTE['mantle'], size=14), cliponaxis=False,
            customdata=deltas,
            hovertemplate=f'%{{x}} {axis}: %{{y:.1f}} ppm (%{{customdata:.1f}} µm)<extra></extra>',
        ))
        value = float(panel[f'Shrinkage {axis} (ppm)'])
        fig.add_trace(go.Scatter(
            x=quadrants, y=[value] * len(quadrants), mode='lines',
            name=f'Panel {axis}: {value:+.0f} ppm', line=dict(color=colour, dash='dash', width=2),
            hovertemplate=f'Panel {axis}: %{{y:.1f}} ppm<extra></extra>',
        ))

    axis_style = dict(tickfont=text, linecolor=theme.CARD_BD, gridcolor=theme.SEPARATOR)
    return apply_dark_layout(
        fig, height=height,
        title=dict(text=title, font=dict(size=15, color=theme.TEXT), x=0.5, xanchor='center'),
        barmode='group', bargap=0.3, bargroupgap=0.08,
        yaxis=dict(title=dict(text='ppm  (negative = shrink)', font=text), zeroline=True,
                   zerolinecolor=theme.TEXT_MUTED, zerolinewidth=1.5, **axis_style),
        xaxis=dict(title=dict(text='Quadrant', font=text), showgrid=False, **{
            k: v for k, v in axis_style.items() if k != 'gridcolor'}),
        legend=dict(orientation='h', y=-0.2, x=0.5, xanchor='center', font=text,
                    bgcolor='rgba(0,0,0,0)'),
        hoverlabel=dict(bgcolor=theme.PLOT_BG, font=dict(color=theme.TEXT)),
        margin=dict(l=70, r=30, t=60, b=80),
    )
