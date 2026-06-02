"""
Excel export helpers for Via-to-Pad quality reports.

Provides chart-to-image rendering (kaleido) and sheet population.
Entry point: write_vtp_excel().
"""

import logging
import os
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openpyxl.drawing.image import Image as XLImage

from src.visuals import plot_vtp_bullseye, plot_vtp_site_bars, plot_vtp_box, plot_vtp_strip

logger = logging.getLogger(__name__)

# Quarter prefix → label for the Report sheet Fiducial column
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


def _load_panel_map_image(settings: dict) -> XLImage | None:
    """Load Panel_Map.png from the path configured in EXCEL_EXPORT settings.

    Returns None (with a logged warning) if the file does not exist.
    """
    export_cfg = settings.get('EXCEL_EXPORT', {})
    rel_path   = export_cfg.get('panel_map_image', 'assets/Panel_Map.png')
    panel_cm   = float(export_cfg.get('panel_image_cm', 8.5))
    panel_px   = int(panel_cm / 2.54 * 96)  # cm → px at 96 dpi

    # Resolve relative to the qvm_dashboard package root
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_path = os.path.join(base_dir, rel_path)

    if not os.path.isfile(abs_path):
        logger.warning('Panel map image not found: %s', abs_path)
        return None

    xl = XLImage(abs_path)
    xl.width  = panel_px
    xl.height = panel_px
    return xl


# ---------------------------------------------------------------------------
# Sheet-level chart embedders
# ---------------------------------------------------------------------------

def _add_panel_map(ws, settings: dict, label: str) -> None:
    """Embed Panel_Map.png at H1."""
    try:
        xl = _load_panel_map_image(settings)
        if xl is None:
            st.sidebar.warning(f"⚠️ Panel_Map.png not found — skipped in '{label}'.")
            return
        ws.add_image(xl, 'H1')
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
        st.sidebar.warning(f"⚠️ Bullseye not embedded in '{label}': {exc}")


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


def _embed_charts(ws, df_raw: pd.DataFrame, settings: dict,
                  label: str, data_row_count: int) -> None:
    """Embed panel map (PNG), bullseye, and bar chart into a worksheet."""
    _add_panel_map(ws, settings, label)
    _add_bullseye(ws, df_raw, settings, label, data_row_count)
    _add_bar_chart(ws, df_raw, settings, label, data_row_count)


def _add_analytics_sheet(writer: pd.ExcelWriter, df: pd.DataFrame,
                          settings: dict) -> None:
    """Create an 'Analytics' sheet with the Box Plot and Strip Chart side by side.

    Layout:
        A1  — title label
        A3  — Box Plot PNG  (700 × 580)
        M3  — Strip Chart PNG  (700 × 580)
    """
    try:
        ws = writer.book.create_sheet('Analytics')

        # Header label
        ws['A1'] = 'SC Distribution — Box Plot (left)  |  Strip Chart by Quarter (right)'
        ws['A1'].font = __import__('openpyxl').styles.Font(bold=True, size=12)

        # Render both charts as PNGs (narrower width fits two side-by-side)
        fig_box   = plot_vtp_box(df, settings)
        fig_strip = plot_vtp_strip(df, settings)
        xl_box   = _fig_to_xl_image(fig_box,   width_px=680, height_px=580)
        xl_strip = _fig_to_xl_image(fig_strip, width_px=680, height_px=580)

        ws.add_image(xl_box,   'A3')   # Box plot starts at column A
        ws.add_image(xl_strip, 'M3')   # Strip chart starts at column M (~700 px right)

    except ImportError as exc:
        logger.warning('Analytics sheet skipped — kaleido missing: %s', exc)
        st.sidebar.warning('⚠️ Analytics sheet not embedded: `kaleido` required.')
    except Exception as exc:
        logger.warning('Analytics sheet embed failed: %s', exc, exc_info=True)
        st.sidebar.warning(f'⚠️ Analytics sheet not embedded: {exc}')


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def _measurement_sheet(df: pd.DataFrame, grid_id_col: str) -> pd.DataFrame:
    """Measurement data frame ready to write (Grid ID column renamed)."""
    return df.copy().rename(columns={grid_id_col: 'Grid ID'})


def _report_sheet(df: pd.DataFrame, side_vals: pd.Series | None, grid_id_col: str,
                  meta: dict, settings: dict) -> pd.DataFrame:
    """Full report frame: metadata prepended, USL columns appended."""
    vtp_cfg = settings.get('VTP_REGISTRATION', {})
    vtp_usl = float(vtp_cfg.get('vtp_usl_um', 10.0))

    s = df.copy()
    grid_str = s[grid_id_col].astype(str).str.zfill(2)
    s.insert(0, 'Fiducial_Number', grid_str.str[1].astype(int))
    s.insert(0, 'Fiducial',        grid_str.str[0].map(_REGION_MAP))
    s.insert(0, 'Side',        side_vals if side_vals is not None else '')
    s.insert(0, 'Panel',       meta.get('panel', ''))
    s.insert(0, 'Process',     meta.get('process', ''))
    s.insert(0, 'Buildup',     meta.get('build_up', ''))
    s.insert(0, 'Lot_Name',    meta.get('lot_name', ''))
    s.insert(0, 'Lot_Number',  meta.get('lot_number', ''))
    s.insert(0, 'Part_Number', meta.get('part_number', ''))
    s.insert(0, 'Project_Name', meta.get('project_name', ''))
    s = s.drop(columns=[grid_id_col])

    # Append USL reference columns (X/Y USL intentionally left blank)
    s['VtP_USL'] = vtp_usl
    s['X_USL']   = None
    s['Y_USL']   = None

    return s


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def write_vtp_excel(writer: pd.ExcelWriter, display_df: pd.DataFrame,
                    filtered_df: pd.DataFrame, settings: dict,
                    meta: dict, grid_id_col: str) -> None:
    """Write Via-to-Pad data + embedded charts into the given ExcelWriter.

    Sheets written:
    - 'Via to Pad' (or 'Via to Pad - F/B') — measurement data + panel map, bullseye, bar chart
    - 'Report' — full metadata + measurements + USL reference columns
    """
    sides       = filtered_df['Side'].unique() if 'Side' in filtered_df.columns else []
    side_series = filtered_df['Side'].values   if 'Side' in filtered_df.columns else None
    report_frames = []

    if len(sides) > 1:
        for side in sorted(sides):
            mask       = filtered_df['Side'] == side
            side_disp  = display_df.loc[display_df.index.isin(filtered_df[mask].index)]
            side_raw   = filtered_df[mask].copy()
            side_vals  = filtered_df.loc[mask, 'Side'].values
            sheet_name = f'Via to Pad - {side}'

            _measurement_sheet(side_disp, grid_id_col).to_excel(
                writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            _embed_charts(ws, side_raw, settings, sheet_name, len(side_disp))
            report_frames.append(
                _report_sheet(side_disp, side_vals, grid_id_col, meta, settings))

        pd.concat(report_frames, ignore_index=True).to_excel(
            writer, sheet_name='Report', index=False)
    else:
        _measurement_sheet(display_df, grid_id_col).to_excel(
            writer, sheet_name='Via to Pad', index=False)
        ws = writer.sheets['Via to Pad']
        _embed_charts(ws, filtered_df, settings, 'Via to Pad', len(display_df))
        _report_sheet(display_df, side_series, grid_id_col, meta, settings).to_excel(
            writer, sheet_name='Report', index=False)

    # Analytics sheet — Box Plot + Strip Chart side by side
    _add_analytics_sheet(writer, filtered_df, settings)
