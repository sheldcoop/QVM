"""SC distribution chart: panel-level box plot by quarter."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from src import theme
from src.chart_helpers import (
    get_rings, zone_colors, apply_dark_layout,
    stats_card_annotation, zone_legend_annotation,
)
from src.utils import resolve_columns


def plot_vtp_box(df: pd.DataFrame, settings: dict) -> go.Figure:
    """Panel-level box plot: one 'All sites' box + four quarter boxes side-by-side.

    Dark theme. Layout:  All | UL  LL  LR  UR
    Narrow, tall boxes with bold zone-coloured dots. Mean reference line.
    Stats card top-right. Zone legend bottom-left.
    """
    cols = resolve_columns(settings, ('ptv_distance', 'grid_id', 'location'))
    sc_col   = cols['ptv_distance']
    grid_col = cols['grid_id']
    loc_col  = cols['location']

    rings  = get_rings(settings)
    height = settings.get('CHART_HEIGHTS', {}).get('box', 640)

    # ---- Prepare data -------------------------------------------------------
    df_plot = df.dropna(subset=[sc_col]).copy()
    df_plot['sc_um'] = pd.to_numeric(df_plot[sc_col], errors='coerce') * 1000
    df_plot = df_plot.dropna(subset=['sc_um'])

    if grid_col in df_plot.columns:
        df_plot['grid_str'] = (pd.to_numeric(df_plot[grid_col], errors='coerce')
                               .astype('Int64').astype(str).str.zfill(2))
        df_plot['quarter']  = df_plot['grid_str'].str[0].map(theme.QUARTER_MAP)
    else:
        df_plot['grid_str'] = '??'
        df_plot['quarter']  = None

    df_plot['color'] = zone_colors(df_plot['sc_um'], rings)

    sc       = df_plot['sc_um']
    n        = len(sc)
    mean_v   = float(sc.mean())   if n else 0.0
    median_v = float(sc.median()) if n else 0.0
    std_v    = float(sc.std())    if n else 0.0
    n_fail   = int((sc > rings.acceptable).sum())
    pct_pass = 100.0 * (1 - n_fail / n) if n else 100.0

    rng = np.random.default_rng(42)

    fig = go.Figure()

    _x_order = ['All'] + theme.QUARTER_ORDER
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
            textfont=dict(size=9, color=theme.TEXT),
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
        x='All', y=rings.acceptable * 1.08,
        xanchor='center', yanchor='bottom',
        showarrow=False,
        font=dict(size=13, color='rgba(205,214,244,0.80)'),
    )

    # Quarter boxes — coloured dots + mean±std near USL in each quarter's colour
    for q in theme.QUARTER_ORDER:
        qdf = df_plot[df_plot['quarter'] == q]
        if qdf.empty:
            continue
        hx = theme.QUARTER_COLORS[q].lstrip('#')
        ri, gi, bi = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        _add_box_and_dots(
            q, qdf['sc_um'].values, qdf['color'].tolist(),
            [_hover(row) for _, row in qdf.iterrows()],
            qdf['grid_str'].tolist(),
            fill=f'rgba({ri},{gi},{bi},0.13)',
            border=theme.QUARTER_COLORS[q],
        )
        # Mean ± std anchored near USL in the quarter's own bright colour
        fig.add_annotation(
            text=f"<b>{qdf['sc_um'].mean():.1f}</b> ± {qdf['sc_um'].std():.1f}",
            xref='x', yref='y',
            x=q, y=rings.acceptable * 1.08,
            xanchor='center', yanchor='bottom',
            showarrow=False,
            font=dict(size=13, color=theme.QUARTER_COLORS[q]),
        )

    # ---- Reference lines ----------------------------------------------------
    # USL — bright red, top left
    fig.add_hline(
        y=rings.acceptable,
        line_dash='dash',
        line_color=theme.ZONE['fail'],
        line_width=2.5,
        annotation_text=f'  USL {rings.acceptable:.1f} µm',
        annotation_position='top left',
        annotation_font_size=11,
        annotation_font_color=theme.ZONE['fail'],
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
        font=dict(size=9, color=theme.TEXT_MUTED),
    )

    # Vertical separator between "All" and the four quarters
    fig.add_vline(x=0.5, line_color=theme.SEPARATOR, line_width=1, line_dash='dot')

    # ---- Annotations --------------------------------------------------------
    fig.add_annotation(**stats_card_annotation(n, mean_v, median_v, std_v, pct_pass))
    fig.add_annotation(**zone_legend_annotation(rings))

    # ---- Layout -------------------------------------------------------------
    n_cats = len(_x_order)
    apply_dark_layout(
        fig, height=height,
        title=dict(
            text='SC Distribution — Panel Overview by Quarter',
            font=dict(size=15, color=theme.TEXT),
            x=0.5, xanchor='center',
        ),
        xaxis=dict(
            type='category',
            categoryorder='array',
            categoryarray=_x_order,
            title='',
            tickfont=dict(size=13, color=theme.TEXT),
            showgrid=False,
            linecolor=theme.SEPARATOR,
        ),
        xaxis2=dict(
            overlaying='x',
            range=[-0.5, n_cats - 0.5],
            visible=False,
        ),
        yaxis=dict(
            title=dict(text='Registration SC (µm)', font=dict(color=theme.TEXT)),
            zeroline=False,
            showgrid=False,
            tickfont=dict(color=theme.TEXT),
        ),
        hovermode='closest',
        margin=dict(t=65, b=80, l=70, r=175),
        boxmode='group',
    )
    return fig
