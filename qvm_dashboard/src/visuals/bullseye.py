"""Via-to-Pad registration charts: DX/DY bullseye scatter + per-site SC bars."""

import pandas as pd
import plotly.graph_objects as go
from typing import Dict

from src import theme
from src.chart_helpers import get_rings, apply_dark_layout


def plot_vtp_bullseye(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """DX/DY bullseye scatter for Via-to-Pad registration.

    Dark Catppuccin Mocha theme. Concentric tolerance rings (zone colours)
    make pass/warn/fail obvious. Data is split into Pass and Fail traces so
    clicking a legend entry actually filters the visible points.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    dx_col   = col_names.get('x_distance', 'Shift (DX)')
    dy_col   = col_names.get('y_distance', 'Shift (DY)')
    sc_col   = col_names.get('ptv_distance', 'PtV Distance')
    loc_col  = col_names.get('location', 'Location')
    grid_col = col_names.get('grid_id', 'Grid ID')

    rings  = get_rings(settings)
    height = settings.get('CHART_HEIGHTS', {}).get('bullseye', 580)

    work = df[[dx_col, dy_col, sc_col, loc_col, grid_col]].dropna().copy()
    work['dx_um'] = work[dx_col] * 1000
    work['dy_um'] = work[dy_col] * 1000
    work['sc_um'] = work[sc_col] * 1000

    spread = rings.acceptable + 2.0
    fig = go.Figure()

    # Concentric tolerance rings
    for r, color, dash in [
        (rings.exceptional, theme.ZONE['exceptional'], 'solid'),
        (rings.excellent,   theme.ZONE['excellent'],   'dot'),
        (rings.good,        theme.ZONE['good'],        'dash'),
        (rings.acceptable,  theme.ZONE['fail'],        'dot'),
    ]:
        fig.add_shape(
            type='circle', xref='x', yref='y',
            x0=-r, y0=-r, x1=r, y1=r,
            line=dict(color=color, width=2, dash=dash),
            fillcolor='rgba(0,0,0,0)', layer='below',
        )

    # Crosshairs
    crosshair = dict(color=theme.CROSSHAIR, width=1.2)
    fig.add_hline(y=0, line=crosshair)
    fig.add_vline(x=0, line=crosshair)

    # Split into Pass / Fail traces — clicking either in the legend filters points.
    hover = (
        '<b>%{text}</b><br>'
        'Grid ID: %{customdata[0]}<br>'
        'SC: %{customdata[1]:.2f} µm<br>'
        'DX: %{customdata[2]:.2f} µm<br>'
        'DY: %{customdata[3]:.2f} µm<br>'
        '<extra></extra>'
    )
    for label, mask, color in [
        (f'Pass ≤{rings.acceptable:.0f} µm',
         work['sc_um'] <= rings.acceptable, theme.ZONE['acceptable']),
        (f'Fail >{rings.acceptable:.0f} µm',
         work['sc_um'] > rings.acceptable,  theme.ZONE['fail']),
    ]:
        sub = work[mask]
        if sub.empty:
            # Keep the legend entry even when no points belong to this group.
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode='markers',
                marker=dict(size=14, color=color),
                name=label, showlegend=True,
            ))
        else:
            fig.add_trace(go.Scatter(
                x=sub['dx_um'], y=sub['dy_um'],
                mode='markers+text',
                marker=dict(size=14, color=color, line=dict(width=0)),
                text=sub[grid_col].astype(str),
                textposition='top center',
                textfont=dict(size=10, color=theme.TEXT),
                customdata=sub[[grid_col, 'sc_um', 'dx_um', 'dy_um']].values,
                hovertemplate=hover,
                name=label, showlegend=True,
            ))

    # Summary stats annotation (top left)
    sc = work['sc_um']
    n = int(len(sc))
    max_sc    = float(sc.max())  if n else 0.0
    mean_sc   = float(sc.mean()) if n else 0.0
    n_outside = int((sc > rings.acceptable).sum())
    fig.add_annotation(
        text=(f"<b>n</b> {n}  •  <b>max SC</b> {max_sc:.1f} µm  •  "
              f"<b>mean SC</b> {mean_sc:.1f} µm  •  <b>fail</b> {n_outside}"),
        xref='paper', yref='paper', x=0.02, y=0.98,
        xanchor='left', yanchor='top', showarrow=False, align='left',
        font=dict(size=11, color=theme.TEXT),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD,
        borderwidth=1, borderpad=5,
    )

    apply_dark_layout(
        fig, height=height,
        title=dict(text='DX vs DY Registration Bullseye — Via-to-Pad',
                   font=dict(size=14, color=theme.TEXT), x=0.5, xanchor='center'),
        xaxis=dict(title=dict(text='DX Shift (µm)', font=dict(color=theme.TEXT)),
                   zeroline=False, showgrid=False,
                   scaleanchor='y', scaleratio=1, range=[-spread, spread],
                   tickfont=dict(color=theme.TEXT)),
        yaxis=dict(title=dict(text='DY Shift (µm)', font=dict(color=theme.TEXT)),
                   zeroline=False, showgrid=False,
                   range=[-spread, spread],
                   tickfont=dict(color=theme.TEXT)),
        hovermode='closest',
        showlegend=True,
        legend=dict(
            x=0.5, y=-0.10, xanchor='center', yanchor='top',
            orientation='h',
            bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD, borderwidth=1,
            font=dict(color=theme.TEXT, size=11),
        ),
        margin=dict(t=55, b=80, l=60, r=60),
    )
    return fig


def plot_vtp_site_bars(df: pd.DataFrame, settings: Dict) -> go.Figure:
    """Per-fiducial-site SC bar chart for Via-to-Pad registration.

    Bars ordered by Grid ID (UL → LL → LR → UR). Split into Pass/Fail Bar
    traces so clicking a legend entry filters the visible bars.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    sc_col   = col_names.get('ptv_distance', 'PtV Distance')
    loc_col  = col_names.get('location', 'Location')
    grid_col = col_names.get('grid_id', 'Grid ID')

    rings  = get_rings(settings)
    height = settings.get('CHART_HEIGHTS', {}).get('site_bars', 450)
    cap_um = float(settings.get('VTP_REGISTRATION', {}).get('outlier_cap_um', 1000.0))

    work = df[[sc_col, loc_col, grid_col]].dropna().copy()
    work['sc_um'] = work[sc_col] * 1000
    work[grid_col] = pd.to_numeric(work[grid_col], errors='coerce')
    work = work.dropna(subset=[grid_col]).sort_values(grid_col)
    work[grid_col] = work[grid_col].astype(int).astype(str)

    pass_mask = work['sc_um'] <= rings.acceptable
    hover = (
        'Grid ID: <b>%{x}</b><br>'
        'Location: %{customdata[0]}<br>'
        'SC: %{customdata[1]:.2f} µm<br>'
        '<extra></extra>'
    )

    fig = go.Figure()

    # Two Bar traces (Pass / Fail) — NaN where the other group's bar would be,
    # so each x position shows exactly one bar. barmode='overlay' keeps bars
    # centred rather than side-by-side.
    for label, mask, color in [
        (f'Pass ≤{rings.acceptable:.0f} µm', pass_mask,  theme.ZONE['acceptable']),
        (f'Fail >{rings.acceptable:.0f} µm', ~pass_mask, theme.ZONE['fail']),
    ]:
        fig.add_trace(go.Bar(
            x=work[grid_col],
            y=work['sc_um'].where(mask),
            marker_color=color,
            marker_line=dict(width=0),
            name=label,
            showlegend=True,
            customdata=work[[loc_col, 'sc_um']].values,
            hovertemplate=hover,
        ))

    # Threshold hlines (reference lines, not part of legend)
    for y_val, color, label in [
        (rings.excellent,  theme.ZONE['excellent'],  f'Excellent {rings.excellent:.1f} µm'),
        (rings.good,       theme.ZONE['good'],       f'Good {rings.good:.1f} µm'),
        (rings.acceptable, theme.ZONE['fail'],       f'Fail >{rings.acceptable:.0f} µm'),
    ]:
        fig.add_hline(
            y=y_val,
            line=dict(color=color, width=1.5, dash='dash'),
            annotation_text=label, annotation_position='right',
            annotation_font_size=10,
            annotation_font_color=color,
        )

    data_max = work['sc_um'].max() if not work.empty else 0.0
    y_max = max(min(data_max, cap_um) * 1.3, rings.acceptable * 1.2)

    # Annotate bars that are clipped off-chart (sc_um > cap_um)
    for _, row in work[work['sc_um'] > cap_um].iterrows():
        fig.add_annotation(
            x=row[grid_col], y=1.0,
            xref='x', yref='paper',
            text=f"{row['sc_um']:.0f} µm ↑",
            showarrow=True, ax=0, ay=30,
            arrowhead=2, arrowcolor=theme.ZONE['fail'],
            font=dict(size=10, color=theme.ZONE['fail']),
            yanchor='bottom',
        )

    apply_dark_layout(
        fig, height=height,
        title=dict(
            text='Registration SC per Fiducial Site (UL → LL → LR → UR)',
            font=dict(size=14, color=theme.TEXT), x=0.5, xanchor='center',
        ),
        xaxis=dict(
            title='', showgrid=False, type='category',
            tickfont=dict(color=theme.TEXT, size=12),
        ),
        yaxis=dict(
            title=dict(text='SC Distance (µm)', font=dict(color=theme.TEXT)),
            range=[0, y_max], showgrid=False,
            tickfont=dict(color=theme.TEXT),
        ),
        barmode='overlay',   # keeps pass/fail bars at the same x position
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            x=0.5, y=-0.10, xanchor='center', yanchor='top',
            orientation='h',
            bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD, borderwidth=1,
            font=dict(color=theme.TEXT, size=11),
        ),
        margin=dict(t=55, b=80, l=60, r=110),
    )
    return fig
