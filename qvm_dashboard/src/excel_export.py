"""
Excel export helpers for Via-to-Pad quality reports.

Provides chart-to-image rendering (kaleido) and sheet population.
Entry point: write_vtp_excel().
"""

import logging
import os
import re
from io import BytesIO

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from openpyxl.drawing.image import Image as XLImage

from src.visuals import (
    plot_vtp_bullseye, plot_vtp_site_bars, plot_vtp_box, plot_quiver,
)
from src.utils import convert_to_microns

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


def _write_chart_fallback(ws, anchor: str, chart_name: str, exc: Exception) -> None:
    """Embed a lightweight placeholder PNG when a chart image cannot be rendered."""
    try:
        from PIL import Image as PILImage, ImageDraw, ImageFont

        width, height = 700, 220
        image = PILImage.new('RGB', (width, height), color=(255, 247, 247))
        draw = ImageDraw.Draw(image)
        title = f'{chart_name} unavailable'
        message = 'Chart rendering failed; workbook preserved without live graphic.'
        detail = str(exc)

        try:
            font = ImageFont.load_default()
        except Exception:
            font = None

        draw.text((20, 20), title, fill=(156, 0, 6), font=font)
        draw.text((20, 55), message, fill=(90, 90, 90), font=font)
        draw.text((20, 85), detail[:110], fill=(120, 120, 120), font=font)

        buf = BytesIO()
        image.save(buf, format='PNG')
        buf.seek(0)
        xl = XLImage(buf)
        xl.width = width
        xl.height = height
        ws.add_image(xl, anchor)
    except Exception:
        cell = ws[anchor]
        cell.value = f"{chart_name} chart unavailable: {exc}"
        try:
            import openpyxl.styles as xl_styles
            cell.font = xl_styles.Font(italic=True, color='9C0006')
            cell.fill = xl_styles.PatternFill(fill_type='solid', fgColor='FFC7CE')
        except ImportError:
            pass


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


def _embed_charts(ws, settings: dict, label: str) -> None:
    """Embed the reference Panel Map (PNG) into a measurement worksheet.

    The bullseye, SC bars, box, and quiver charts now live solely on the
    per-side Analytics sheet, so the measurement sheet keeps only the data
    table and the Panel Map reference image.
    """
    _add_panel_map(ws, settings, label)


def _add_analytics_sheet(writer: pd.ExcelWriter, df: pd.DataFrame,
                          settings: dict,
                          sheet_label: str = 'Analytics') -> None:
    """Create an analytics sheet with all four Via-to-Pad charts in a 2×2 grid.

    Layout:
        A1   — title label (includes sheet_label for self-identification)
        A3   — Bullseye scatter (DX/DY)      K3   — Per-site SC bars
        A35  — Box plot (SC distribution)    K35  — Quiver (ABF distortion map)

    sheet_label is used as the worksheet name so that when both F and B sides
    are uploaded, each side gets its own sheet ("Analytics - F", "Analytics - B").

    Each chart is embedded independently so one failed render (or missing
    kaleido) never aborts the rest of the sheet or the workbook.
    """
    try:
        import openpyxl  # noqa: F401
    except ImportError as exc:
        logger.warning('Analytics sheet skipped — openpyxl missing: %s', exc)
        st.sidebar.warning('⚠️ Analytics sheet not embedded: `openpyxl` required.')
        return

    ws = writer.book.create_sheet(sheet_label)
    ws['A1'] = f'Registration Analytics — {sheet_label}'
    ws['A1'].font = openpyxl.styles.Font(bold=True, size=12)

    multiplier = settings.get('PLOT_SETTINGS', {}).get('vector_multiplier_default', 50)

    # 2×2 grid. Each chart is 700px (~11 columns) wide, so the right column
    # starts at N (col 14: cols L/M are the ~2-cell gap) and the bottom row at
    # 38 (the top row spans ~29-32 rows from row 3, plus a gap) — keeping all
    # four images clear of one another.
    # (anchor, chart name, figure factory, width, height)
    charts = [
        ('A3',  'Bullseye',  lambda: plot_vtp_bullseye(df, settings),    700, 580),
        ('N3',  'Site bars', lambda: plot_vtp_site_bars(df, settings),   700, 450),
        ('A38', 'Box plot',  lambda: plot_vtp_box(df, settings),         700, 640),
        ('N38', 'Quiver',    lambda: plot_quiver(df, settings, multiplier), 700, 600),
    ]
    for anchor, name, make_fig, w, h in charts:
        try:
            ws.add_image(_fig_to_xl_image(make_fig(), width_px=w, height_px=h), anchor)
        except Exception as exc:
            logger.warning('%s chart embed failed for %s: %s',
                           name, sheet_label, exc, exc_info=True)
            _write_chart_fallback(ws, anchor, name, exc)
            st.sidebar.warning(
                f'⚠️ {name} not embedded in "{sheet_label}": {exc}')


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def _warnings_sheet(ws, warnings: list) -> None:
    """Write parser warnings into a worksheet, one per row.

    Header row is bold with a red background. If there are no warnings, a
    placeholder 'No warnings for this file.' message is written.
    """
    try:
        import openpyxl.styles as xl_styles
    except ImportError:
        return

    header_fill = xl_styles.PatternFill(
        fill_type='solid', fgColor='C00000')  # dark red
    header_font = xl_styles.Font(bold=True, color='FFFFFF')

    ws.column_dimensions['A'].width = 100
    ws['A1'] = 'Warnings'
    ws['A1'].fill = header_fill
    ws['A1'].font = header_font

    if not warnings:
        ws['A2'] = 'No warnings for this file.'
    else:
        for i, msg in enumerate(warnings, start=2):
            ws.cell(row=i, column=1, value=msg)


def _measurement_sheet(df: pd.DataFrame, grid_id_col: str) -> pd.DataFrame:
    """Measurement data frame ready to write (Grid ID column renamed)."""
    return df.copy().rename(columns={grid_id_col: 'Grid ID'})


def _build_process_display(df: pd.DataFrame, settings: dict,
                           is_via_to_pad: bool) -> pd.DataFrame:
    """Build a process-specific display dataframe aligned with QC columns."""
    col_names = settings.get('COLUMN_NAMES', {})
    grid_id_col = col_names.get('grid_id', 'Grid ID')
    via_diam_col = col_names.get('inner_diameter', 'Via Parameter')
    pad_diam_col = col_names.get('outer_diameter', 'Pad Diameter')
    dx_col = col_names.get('x_distance', 'Shift (DX)')
    dy_col = col_names.get('y_distance', 'Shift (DY)')
    sc_col = col_names.get('total_shift', 'SC')
    ptv_dist_col = col_names.get('ptv_distance', 'PtV Distance')
    annular_col = col_names.get('annular_ring', 'Annular Ring')

    distance_col = sc_col if is_via_to_pad else ptv_dist_col
    keep = [grid_id_col, via_diam_col, pad_diam_col, dx_col, dy_col, distance_col]
    display_df = df[[c for c in keep if c in df.columns]].copy()

    measurement_cols = [pad_diam_col, via_diam_col, sc_col, dx_col, dy_col,
                        ptv_dist_col, annular_col]
    display_df = convert_to_microns(display_df, measurement_cols)

    if grid_id_col in display_df.columns:
        display_df = display_df.sort_values(by=grid_id_col, ascending=True)

    return display_df


def _safe_sheet_name(sheet_name: str, existing: set[str]) -> str:
    """Return an Excel-safe, unique worksheet name (<=31 chars)."""
    base = re.sub(r'[\[\]:*?/\\]', '-', str(sheet_name).strip()) or 'Sheet'
    base = re.sub(r'\s+', ' ', base)
    candidate = base[:31]
    counter = 2
    while candidate in existing:
        suffix = f' {counter}'
        candidate = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    existing.add(candidate)
    return candidate


def _process_slices(df: pd.DataFrame, meta: dict) -> dict[str, pd.DataFrame]:
    """Split scoped data into VTP/PTV dataframes for unified exports."""
    if 'Process' in df.columns:
        vtp_mask = df['Process'].astype(str).str.contains('Via to Pad', case=False, na=False)
        return {
            'VTP': df[vtp_mask].copy(),
            'PTV': df[~vtp_mask].copy(),
        }

    process_hint = str(meta.get('process', '')).lower()
    if 'via to pad' in process_hint or process_hint == 'vtp':
        return {'VTP': df.copy(), 'PTV': pd.DataFrame(columns=df.columns)}
    return {'VTP': pd.DataFrame(columns=df.columns), 'PTV': df.copy()}


def _report_sheet(df: pd.DataFrame, side_vals: pd.Series | None,
                  build_up_vals: pd.Series | None, grid_id_col: str,
                  meta: dict, usl_col_name: str, usl_value: float,
                  include_xy_usl: bool = False) -> pd.DataFrame:
    """Full report frame: metadata prepended, USL reference column(s) appended.

    `usl_col_name`/`usl_value` name the process-specific spec-limit column
    ('VtP_USL' for Via-to-Pad, 'PtV_USL' for Pad-to-Via). When `include_xy_usl`
    is set, blank X/Y USL columns are appended too (Via-to-Pad only).
    """
    s = df.copy()
    grid_str = s[grid_id_col].astype(str).str.zfill(2)
    s.insert(0, 'Fiducial_Number', grid_str.str[1].astype(int))
    s.insert(0, 'Fiducial',        grid_str.str[0].map(_REGION_MAP))
    s.insert(0, 'Side',        side_vals if side_vals is not None else '')
    s.insert(0, 'Panel',       meta.get('panel', ''))
    s.insert(0, 'Process',     meta.get('process', ''))
    s.insert(0, 'Buildup',     build_up_vals if build_up_vals is not None else meta.get('build_up', ''))
    s.insert(0, 'Lot_Name',    meta.get('lot_name', ''))
    s.insert(0, 'Lot_Number',  meta.get('lot_number', ''))
    s.insert(0, 'Part_Number', meta.get('part_number', ''))
    s.insert(0, 'Project_Name', meta.get('project_name', ''))
    s = s.drop(columns=[grid_id_col])

    # Append USL reference column(s) (X/Y USL intentionally left blank)
    s[usl_col_name] = usl_value
    if include_xy_usl:
        s['X_USL'] = None
        s['Y_USL'] = None

    return s


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def _write_process_workbook(writer: pd.ExcelWriter, display_df: pd.DataFrame,
                            filtered_df: pd.DataFrame, settings: dict, meta: dict,
                            grid_id_col: str, sheet_base: str, usl_col_name: str,
                            usl_value: float, include_xy_usl: bool,
                            warnings: list = None) -> None:
    """Shared workbook builder for both Pad-to-Via and Via-to-Pad exports.

    Sheets written:
    - '<sheet_base>' (or '<sheet_base> - F/B') — measurement data + Panel Map reference
    - 'Report' — full metadata + measurements + USL reference column(s)
    - 'Analytics' (or 'Analytics - F/B') — all four registration charts
    - 'Warnings' — parser warnings (empty message if none)

    `sheet_base` is 'Pad to Via' or 'Via to Pad'; `usl_col_name`/`usl_value`/
    `include_xy_usl` parametrise the Report sheet's spec-limit columns.
    """
    sides       = filtered_df['Side'].unique() if 'Side' in filtered_df.columns else []
    side_series = filtered_df['Side'].values   if 'Side' in filtered_df.columns else None
    report_frames = []

    if len(sides) > 1:
        for side in sorted(sides):
            mask       = filtered_df['Side'] == side
            side_disp  = display_df.loc[display_df.index.isin(filtered_df[mask].index)]
            side_vals  = filtered_df.loc[mask, 'Side'].values
            build_vals = (filtered_df.loc[mask, 'Build Up'].values
                          if 'Build Up' in filtered_df.columns else None)
            sheet_name = f'{sheet_base} - {side}'

            _measurement_sheet(side_disp, grid_id_col).to_excel(
                writer, sheet_name=sheet_name, index=False)
            ws = writer.sheets[sheet_name]
            _embed_charts(ws, settings, sheet_name)
            report_frames.append(
                _report_sheet(side_disp, side_vals, build_vals, grid_id_col, meta,
                              usl_col_name, usl_value, include_xy_usl))

        pd.concat(report_frames, ignore_index=True).to_excel(
            writer, sheet_name='Report', index=False)
    else:
        _measurement_sheet(display_df, grid_id_col).to_excel(
            writer, sheet_name=sheet_base, index=False)
        ws = writer.sheets[sheet_base]
        _embed_charts(ws, settings, sheet_base)
        build_series = filtered_df['Build Up'].values if 'Build Up' in filtered_df.columns else None
        _report_sheet(display_df, side_series, build_series, grid_id_col, meta,
                      usl_col_name, usl_value, include_xy_usl).to_excel(
            writer, sheet_name='Report', index=False)

    # Analytics sheet — one per side when both F and B are present, otherwise one combined
    if len(sides) > 1:
        for side in sorted(sides):
            mask = filtered_df['Side'] == side
            _add_analytics_sheet(writer, filtered_df[mask].copy(), settings,
                                  sheet_label=f'Analytics - {side}')
    else:
        _add_analytics_sheet(writer, filtered_df, settings, sheet_label='Analytics')

    # Warnings sheet — parser warnings from all uploaded files
    ws_warn = writer.book.create_sheet('Warnings')
    _warnings_sheet(ws_warn, warnings or [])


def write_vtp_excel(writer: pd.ExcelWriter, display_df: pd.DataFrame,
                    filtered_df: pd.DataFrame, settings: dict,
                    meta: dict, grid_id_col: str,
                    warnings: list = None) -> None:
    """Write Via-to-Pad data + embedded charts into the given ExcelWriter."""
    usl = float(settings.get('VTP_REGISTRATION', {}).get('vtp_usl_um', 10.0))
    _write_process_workbook(
        writer, display_df, filtered_df, settings, meta, grid_id_col,
        sheet_base='Via to Pad', usl_col_name='VtP_USL',
        usl_value=usl, include_xy_usl=True, warnings=warnings)


def write_ptv_excel(writer: pd.ExcelWriter, display_df: pd.DataFrame,
                    filtered_df: pd.DataFrame, settings: dict,
                    meta: dict, grid_id_col: str,
                    warnings: list = None) -> None:
    """Write Pad-to-Via data + embedded charts into the given ExcelWriter.

    Mirrors the Via-to-Pad workbook structure (data + Report + Analytics charts),
    keyed on PtV Distance with a configurable PtV USL reference column.
    """
    usl = float(settings.get('PTV_REGISTRATION', {}).get('ptv_usl_um', 10.0))
    _write_process_workbook(
        writer, display_df, filtered_df, settings, meta, grid_id_col,
        sheet_base='Pad to Via', usl_col_name='PtV_USL',
        usl_value=usl, include_xy_usl=False, warnings=warnings)


def write_unified_excel(writer: pd.ExcelWriter, scoped_df: pd.DataFrame,
                        settings: dict, meta: dict,
                        warnings: list = None) -> None:
    """Write one workbook containing both processes and BU-specific analytics.

    Sheets written:
    - 'All Data' — scoped rows across all processes
    - 'Report' — consolidated report table (process-tagged, row-level BU)
    - 'Analytics <PROC> <BU>' — one analytics sheet per process and Build Up
    - 'Warnings' — parser warnings
    """
    if scoped_df is None or scoped_df.empty:
        pd.DataFrame({'info': ['No data available for export scope.']}).to_excel(
            writer, sheet_name='All Data', index=False)
        ws_warn = writer.book.create_sheet('Warnings')
        _warnings_sheet(ws_warn, warnings or [])
        return

    col_names = settings.get('COLUMN_NAMES', {})
    grid_id_col = col_names.get('grid_id', 'Grid ID')

    all_data = scoped_df.copy()
    measurement_cols = [
        col_names.get('outer_diameter', 'Pad Diameter'),
        col_names.get('inner_diameter', 'Via Parameter'),
        col_names.get('total_shift', 'SC'),
        col_names.get('x_distance', 'Shift (DX)'),
        col_names.get('y_distance', 'Shift (DY)'),
        col_names.get('ptv_distance', 'PtV Distance'),
        col_names.get('annular_ring', 'Annular Ring'),
    ]
    all_data = convert_to_microns(all_data, measurement_cols)
    if grid_id_col in all_data.columns:
        all_data = all_data.sort_values(by=grid_id_col, ascending=True)
    _measurement_sheet(all_data, grid_id_col).to_excel(writer, sheet_name='All Data', index=False)

    process_frames = _process_slices(scoped_df, meta)
    vtp_usl = float(settings.get('VTP_REGISTRATION', {}).get('vtp_usl_um', 10.0))
    ptv_usl = float(settings.get('PTV_REGISTRATION', {}).get('ptv_usl_um', 10.0))

    report_frames = []
    for process_code, proc_df in process_frames.items():
        if proc_df.empty:
            continue

        is_vtp = process_code == 'VTP'
        proc_display = _build_process_display(proc_df, settings, is_via_to_pad=is_vtp)
        side_vals = proc_df['Side'].values if 'Side' in proc_df.columns else None
        build_vals = proc_df['Build Up'].values if 'Build Up' in proc_df.columns else None
        proc_meta = dict(meta)
        proc_meta['process'] = 'Via to Pad' if is_vtp else 'Pad to Via'

        report_frames.append(
            _report_sheet(
                proc_display,
                side_vals,
                build_vals,
                grid_id_col,
                proc_meta,
                usl_col_name='VtP_USL' if is_vtp else 'PtV_USL',
                usl_value=vtp_usl if is_vtp else ptv_usl,
                include_xy_usl=is_vtp,
            )
        )

    if report_frames:
        pd.concat(report_frames, ignore_index=True).to_excel(
            writer, sheet_name='Report', index=False)
    else:
        pd.DataFrame({'info': ['No process-specific rows found.']}).to_excel(
            writer, sheet_name='Report', index=False)

    used_sheet_names = set(writer.book.sheetnames)
    for process_code, proc_df in process_frames.items():
        if proc_df.empty:
            continue

        if 'Build Up' in proc_df.columns:
            bu_values = sorted({str(v).strip() for v in proc_df['Build Up'].dropna().tolist() if str(v).strip()})
        else:
            bu_values = []
        if not bu_values:
            bu_values = ['Unknown']

        for bu in bu_values:
            if 'Build Up' in proc_df.columns:
                if bu.lower() == 'unknown':
                    bu_df = proc_df[proc_df['Build Up'].astype(str).str.strip().str.lower() == 'unknown'].copy()
                else:
                    bu_df = proc_df[proc_df['Build Up'] == bu].copy()
            else:
                bu_df = proc_df.copy()

            if bu_df.empty:
                continue

            label = _safe_sheet_name(f'Analytics {process_code} {bu}', used_sheet_names)
            _add_analytics_sheet(writer, bu_df, settings, sheet_label=label)

    ws_warn = writer.book.create_sheet(_safe_sheet_name('Warnings', used_sheet_names))
    _warnings_sheet(ws_warn, warnings or [])
