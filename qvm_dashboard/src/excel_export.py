"""
Excel export helpers for Via-to-Pad quality reports.

Provides chart-to-image rendering (kaleido) and sheet population.
Entry point: write_vtp_excel().
"""

import logging
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openpyxl.drawing.image import Image as XLImage

from src.visuals import plot_vtp_bullseye, plot_vtp_site_bars, plot_quiver, _GRID_PLOT_POSITIONS

logger = logging.getLogger(__name__)

# Panel map image size: 12 cm at 96 dpi ≈ 454 px
_PANEL_PX = 454

# Quarter prefix → label
_REGION_MAP = {'1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'}


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _fig_to_xl_image(fig: go.Figure, width_px: int = 700,
                     height_px: int = 700) -> XLImage:
    """Render a Plotly figure to PNG via kaleido and wrap it as an XLImage."""
    img_bytes = fig.to_image(format='png', width=width_px, height=height_px, scale=2)
    buf = BytesIO(img_bytes)
    xl = XLImage(buf)
    xl.width = width_px
    xl.height = height_px
    return xl


def plot_excel_panel_map(df: pd.DataFrame, settings: dict) -> go.Figure:
    """Build the 4×4 panel location map figure for Excel embedding.

    Each grid site is coloured by SC value using the same traffic-light
    palette as the bullseye chart. Size configured by caller via _PANEL_PX.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    vtp_cfg   = settings.get('VTP_REGISTRATION', {})
    sc_col    = col_names.get('ptv_distance', 'PtV Distance')
    grid_col  = col_names.get('grid_id', 'Grid ID')

    r_exc  = float(vtp_cfg.get('ring_exceptional_um',  2.5))
    r_xll  = float(vtp_cfg.get('ring_excellent_um',    5.0))
    r_good = float(vtp_cfg.get('ring_good_um',         7.5))
    r_acc  = float(vtp_cfg.get('ring_acceptable_um',  10.0))

    def _dot_color(v):
        if v is None:    return '#cccccc'
        if v <= r_exc:   return '#3498db'
        if v <= r_xll:   return '#1e7e3a'
        if v <= r_good:  return '#2ecc71'
        if v <= r_acc:   return '#e67e22'
        return '#e74c3c'

    sc_map: dict = {}
    if sc_col in df.columns and grid_col in df.columns:
        for _, row in df[[grid_col, sc_col]].dropna().iterrows():
            sc_map[str(int(row[grid_col]))] = float(row[sc_col]) * 1000

    fig = go.Figure()

    _quarters = {
        'UL': (0.5, 2.5, 0.5, 2.5, '#e8f4f8'),
        'LL': (0.5, 2.5, 2.5, 4.5, '#fef9e7'),
        'LR': (2.5, 4.5, 2.5, 4.5, '#eafaf1'),
        'UR': (2.5, 4.5, 0.5, 2.5, '#fdf2f8'),
    }
    for label, (x0, x1, y0, y1, bg) in _quarters.items():
        fig.add_shape(type='rect', x0=x0, x1=x1, y0=y0, y1=y1,
                      fillcolor=bg, line=dict(color='#aaaaaa', width=1), layer='below')
        fig.add_annotation(x=(x0 + x1) / 2, y=(y0 + y1) / 2, text=label,
                           font=dict(size=28, color='rgba(180,180,180,0.6)'),
                           showarrow=False)

    for v in [1.5, 2.5, 3.5]:
        fig.add_hline(y=v, line=dict(color='#bbbbbb', width=0.8))
        fig.add_vline(x=v, line=dict(color='#bbbbbb', width=0.8))

    xs, ys, texts, colours, hovers = [], [], [], [], []
    for gid, (px_x, px_y) in _GRID_PLOT_POSITIONS.items():
        sc_val = sc_map.get(gid)
        xs.append(px_x)
        ys.append(px_y)
        texts.append(gid)
        colours.append(_dot_color(sc_val))
        hovers.append(
            f"Grid {gid}<br>SC: {sc_val:.2f} µm" if sc_val is not None
            else f"Grid {gid}<br>No data"
        )

    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='markers+text',
        marker=dict(size=30, color=colours, line=dict(width=1, color='#333333')),
        text=texts, textposition='middle center',
        textfont=dict(size=10, color='white'),
        hovertext=hovers, hoverinfo='text', showlegend=False,
    ))

    fig.update_layout(
        title=dict(text='Panel Location Map', font=dict(size=13)),
        xaxis=dict(range=[0.5, 4.5], tickvals=[1, 2, 3, 4],
                   ticktext=['Col 1', 'Col 2', 'Col 3', 'Col 4'],
                   showgrid=False, zeroline=False),
        yaxis=dict(range=[0.5, 4.5], tickvals=[1, 2, 3, 4],
                   ticktext=['Row 1', 'Row 2', 'Row 3', 'Row 4'],
                   showgrid=False, zeroline=False, autorange='reversed'),
        plot_bgcolor='white', paper_bgcolor='white',
        margin=dict(l=40, r=20, t=40, b=40),
        width=_PANEL_PX, height=_PANEL_PX,
    )
    return fig


# ---------------------------------------------------------------------------
# Sheet-level chart embedders
# ---------------------------------------------------------------------------

def _add_panel_map(ws, df: pd.DataFrame, settings: dict, label: str) -> None:
    """Embed the panel location map at H1."""
    try:
        fig = plot_excel_panel_map(df, settings)
        ws.add_image(_fig_to_xl_image(fig, _PANEL_PX, _PANEL_PX), 'H1')
    except Exception as exc:
        logger.warning('Panel map embed failed for %s: %s', label, exc, exc_info=True)
        st.sidebar.warning(f"⚠️ Panel map not embedded in '{label}': {exc}")


def _add_bullseye(ws, df: pd.DataFrame, settings: dict, label: str,
                  data_row_count: int) -> None:
    """Embed the bullseye chart at column A below the data table."""
    anchor = f'A{data_row_count + 4}'
    try:
        fig = plot_vtp_bullseye(df, settings)
        ws.add_image(_fig_to_xl_image(fig), anchor)
    except Exception as exc:
        logger.warning('Bullseye embed failed for %s: %s', label, exc, exc_info=True)
        st.sidebar.warning(f"⚠️ Scatter not embedded in '{label}': {exc}")


def _add_bar_chart(ws, df: pd.DataFrame, settings: dict, label: str,
                   data_row_count: int) -> None:
    """Embed the SC-per-site bar chart at column J below the data table."""
    anchor = f'J{data_row_count + 4}'
    try:
        fig = plot_vtp_site_bars(df, settings)
        ws.add_image(_fig_to_xl_image(fig, width_px=700, height_px=450), anchor)
    except Exception as exc:
        logger.warning('Bar chart embed failed for %s: %s', label, exc, exc_info=True)
        st.sidebar.warning(f"⚠️ Bar chart not embedded in '{label}': {exc}")


def _add_quiver(ws, df: pd.DataFrame, settings: dict, label: str,
                data_row_count: int) -> None:
    """Embed the quiver plot at column S below the data table."""
    anchor = f'S{data_row_count + 4}'
    try:
        fig = plot_quiver(df, settings, multiplier=100)
        ws.add_image(_fig_to_xl_image(fig), anchor)
    except Exception as exc:
        logger.warning('Quiver embed failed for %s: %s', label, exc, exc_info=True)
        st.sidebar.warning(f"⚠️ Quiver not embedded in '{label}': {exc}")


def _embed_all_charts(ws, df_raw: pd.DataFrame, settings: dict,
                      label: str, data_row_count: int) -> None:
    """Embed all four charts into a worksheet."""
    _add_panel_map(ws, df_raw, settings, label)
    _add_bullseye(ws, df_raw, settings, label, data_row_count)
    _add_bar_chart(ws, df_raw, settings, label, data_row_count)
    _add_quiver(ws, df_raw, settings, label, data_row_count)


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def _measurement_sheet(df: pd.DataFrame, grid_id_col: str) -> pd.DataFrame:
    """Return the measurement data frame ready to write (Grid ID renamed)."""
    return df.copy().rename(columns={grid_id_col: 'Grid ID'})


def _report_sheet(df: pd.DataFrame, side_vals, grid_id_col: str,
                  meta: dict) -> pd.DataFrame:
    """Return the full report frame with metadata prepended."""
    region_map = _REGION_MAP
    s = df.copy()
    grid_str = s[grid_id_col].astype(str).str.zfill(2)
    s.insert(0, 'Fiducial_Number', grid_str.str[1].astype(int))
    s.insert(0, 'Fiducial',        grid_str.str[0].map(region_map))
    s.insert(0, 'Side',        side_vals if side_vals is not None else '')
    s.insert(0, 'Panel',       meta.get('panel', ''))
    s.insert(0, 'Process',     meta.get('process', ''))
    s.insert(0, 'Buildup',     meta.get('build_up', ''))
    s.insert(0, 'Lot_Name',    meta.get('lot_name', ''))
    s.insert(0, 'Lot_Number',  meta.get('lot_number', ''))
    s.insert(0, 'Part_Number', meta.get('part_number', ''))
    s.insert(0, 'Project_Name', meta.get('project_name', ''))
    return s.drop(columns=[grid_id_col])


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def write_vtp_excel(writer: pd.ExcelWriter, display_df: pd.DataFrame,
                    filtered_df: pd.DataFrame, settings: dict,
                    meta: dict, grid_id_col: str) -> None:
    """Write Via-to-Pad data + 4 embedded charts into the given ExcelWriter.

    Splits by Side when both Front and Back are present.
    Always appends a combined 'Report' sheet with full metadata.
    """
    sides = filtered_df['Side'].unique() if 'Side' in filtered_df.columns else []
    side_series = filtered_df['Side'].values if 'Side' in filtered_df.columns else None
    report_frames = []

    if len(sides) > 1:
        for side in sorted(sides):
            mask        = filtered_df['Side'] == side
            side_disp   = display_df.loc[display_df.index.isin(filtered_df[mask].index)]
            side_raw    = filtered_df[mask].copy()
            side_vals   = filtered_df.loc[mask, 'Side'].values
            sheet_name  = f'Via to Pad - {side}'

            _measurement_sheet(side_disp, grid_id_col).to_excel(
                writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            _embed_all_charts(ws, side_raw, settings, sheet_name, len(side_disp))
            report_frames.append(_report_sheet(side_disp, side_vals, grid_id_col, meta))

        pd.concat(report_frames, ignore_index=True).to_excel(
            writer, sheet_name='Report', index=False)
    else:
        _measurement_sheet(display_df, grid_id_col).to_excel(
            writer, sheet_name='Via to Pad', index=False)
        ws = writer.sheets['Via to Pad']
        _embed_all_charts(ws, filtered_df, settings, 'Via to Pad', len(display_df))
        _report_sheet(display_df, side_series, grid_id_col, meta).to_excel(
            writer, sheet_name='Report', index=False)
