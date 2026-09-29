"""
Excel export helpers for QVM quality reports.

Provides chart-to-image rendering (kaleido) and sheet population.
Entry point: write_unified_excel().
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
from src.core_shrinkage_parser import (
    affine_residuals_um, both_frame, compute_affine_analysis,
    compute_centered_deviation_table, compute_scale_factor,
    compute_shrinkage_summary, layer_frame, qp_shrinkage_um, summary_frame,
)
from src.display_frame import GRID_ID_HEADER, build_display_frame
from src.registration_shrinkage import compute_distance_shrinkage
from src.utils import is_via_to_pad

logger = logging.getLogger(__name__)

# Quarter prefix → label for the Report sheet Fiducial column
_REGION_MAP = {'1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'}


def _ensure_chrome_on_path() -> None:
    """Make Chrome discoverable to Kaleido when it is installed but not on PATH.

    This is most common on Windows, where Chrome can exist under one of the
    standard Program Files locations without being on the system PATH. Adding the
    chrome installation directory to PATH and exporting GOOGLE_CHROME_BIN helps
    Plotly/Kaleido locate the browser during fig.to_image().
    """
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expanduser(r'~\AppData\Local\Google\Chrome\Application\chrome.exe'),
        os.path.expanduser(r'~\AppData\Local\Google\Chrome SxS\Application\chrome.exe'),
        r'C:\Program Files\Chromium\Application\chrome.exe',
        r'C:\Program Files (x86)\Chromium\Application\chrome.exe',
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            # Separator-agnostic dirname: the candidates are Windows paths,
            # and os.path.dirname misses them entirely on POSIX hosts.
            chrome_dir = re.sub(r'[\\/][^\\/]+$', '', candidate)
            path_entries = os.environ.get('PATH', '').split(os.pathsep)
            if chrome_dir not in path_entries:
                os.environ['PATH'] = chrome_dir + os.pathsep + os.environ.get('PATH', '')
            os.environ['GOOGLE_CHROME_BIN'] = candidate
            os.environ['CHROME_BIN'] = candidate
            return


# ---------------------------------------------------------------------------
# Low-level helpers
# ---------------------------------------------------------------------------

def _fig_to_xl_image(fig: go.Figure, width_px: int = 300,
                     height_px: int = 400) -> XLImage:
    """Render a Plotly figure to PNG via kaleido and wrap it as an XLImage."""
    _ensure_chrome_on_path()
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

        width, height = 400, 220
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
    """Embed Panel_Map.png to the right of the data table to avoid overlap.

    Measurement sheets carry only the data table and this reference image; the
    bullseye, SC bars, box, and quiver charts live solely on the Analytics
    sheets built by :func:`_add_analytics_sheet`.
    """
    try:
        from openpyxl.utils.cell import get_column_letter

        xl = _load_panel_map_image(settings)
        if xl is None:
            st.sidebar.warning(f"⚠️ Panel_Map.png not found — skipped in '{label}'.")
            return

        data_end_col = max(int(getattr(ws, 'max_column', 1) or 1), 1)
        anchor_col = get_column_letter(data_end_col + 2)
        ws.add_image(xl, f'{anchor_col}1')
    except Exception as exc:
        logger.warning('Panel map embed failed for %s: %s', label, exc, exc_info=True)
        st.sidebar.warning(f"⚠️ Panel map not embedded in '{label}': {exc}")


def _add_analytics_sheet(writer: pd.ExcelWriter, df: pd.DataFrame,
                          settings: dict,
                          sheet_label: str = 'Analytics') -> None:
    """Create an analytics sheet with one horizontal 4-chart row per side.

    Layout:
        A1   — title label (includes sheet_label for self-identification)
        For each available side (Front then Back), place one horizontal row:
            <start>3    — Bullseye scatter (DX/DY)
            <start+13>3 — Per-site SC bars
            <start+26>3 — Box plot (SC distribution)
            <start+39>3 — Quiver (ABF distortion map)

    sheet_label is used as the worksheet name so that when both F and B sides
    are uploaded for the same Build Up, one sheet can still show both sides as
    separate horizontal rows, avoiding mixed/combined charts.

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

    multiplier = settings.get('PLOT_SETTINGS', {}).get('vector_multiplier_default', 100)

    side_order = {'F': 0, 'B': 1}
    side_labels = {'F': 'Front', 'B': 'Back'}
    side_values = []
    if 'Side' in df.columns:
        side_values = [
            str(v).strip().upper() for v in df['Side'].dropna().tolist()
            if str(v).strip()
        ]
        side_values = sorted(set(side_values), key=lambda s: (side_order.get(s, 2), s))
    if not side_values:
        side_values = ['ALL']

    # One side row spans four charts across the sheet.
    # Start each additional side row further down so Front/Back are stacked.
    from openpyxl.utils.cell import get_column_letter

    def _anchor(start_col: int, row: int) -> str:
        return f'{get_column_letter(start_col)}{row}'

    for block_idx, side in enumerate(side_values):
        start_row = 3 + (block_idx * 72)
        start_col = 2
        side_df = df if side == 'ALL' else df[df['Side'].astype(str).str.upper() == side].copy()
        if side_df.empty:
            continue

        side_label = side_labels.get(side, side)
        ws[_anchor(1, start_row - 1)] = f'Side: {side_label}'
        ws[_anchor(1, start_row - 1)].font = openpyxl.styles.Font(bold=True)

        charts = [
            (_anchor(start_col,      start_row), 'Bullseye',  lambda d=side_df: plot_vtp_bullseye(d, settings),    500, 500),
            (_anchor(start_col + 13, start_row), 'Site bars', lambda d=side_df: plot_vtp_site_bars(d, settings),   700, 500),
            (_anchor(start_col + 26, start_row), 'Box plot',  lambda d=side_df: plot_vtp_box(d, settings),         700, 500),
            (_anchor(start_col + 39, start_row), 'Quiver',    lambda d=side_df: plot_quiver(d, settings, multiplier), 500, 500),
        ]
        for anchor, name, make_fig, w, h in charts:
            chart_name = f'{name} [{side}]'
            try:
                ws.add_image(_fig_to_xl_image(make_fig(), width_px=w, height_px=h), anchor)
            except Exception as exc:
                logger.warning('%s chart embed failed for %s: %s',
                               chart_name, sheet_label, exc, exc_info=True)
                _write_chart_fallback(ws, anchor, chart_name, exc)
                st.sidebar.warning(
                    f'⚠️ {chart_name} not embedded in "{sheet_label}": {exc}')


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


def _process_slices(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Split scoped data into VTP/PTV dataframes for unified exports."""
    vtp_mask = is_via_to_pad(df)
    return {
        'VTP': df[vtp_mask].copy(),
        'PTV': df[~vtp_mask].copy(),
    }


def _iter_build_up_frames(proc_df: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    if proc_df.empty:
        return []
    if 'Build Up' in proc_df.columns:
        bu_values = sorted({str(v).strip() for v in proc_df['Build Up'].dropna().tolist() if str(v).strip()})
    else:
        bu_values = []
    if not bu_values:
        bu_values = ['Unknown']

    out = []
    for bu in bu_values:
        if 'Build Up' in proc_df.columns:
            if bu.lower() == 'unknown':
                bu_df = proc_df[proc_df['Build Up'].astype(str).str.strip().str.lower() == 'unknown'].copy()
            else:
                bu_df = proc_df[proc_df['Build Up'] == bu].copy()
        else:
            bu_df = proc_df.copy()
        if not bu_df.empty:
            out.append((bu, bu_df))
    return out


def _write_shrinkage_summary_sheet(
    writer: pd.ExcelWriter,
    settings: dict,
    process_frames: dict[str, pd.DataFrame],
    used_sheet_names: set[str],
) -> bool:
    col_names = settings.get('COLUMN_NAMES', {})
    loc_col = col_names.get('location', 'Location')
    x_col = col_names.get('coord_x', 'Coord. X')
    y_col = col_names.get('coord_y', 'Coord. Y')

    nominal_coords = (
        settings.get('REGISTRATION_SHRINKAGE', {}).get('NOMINAL_COORDS')
        or settings.get('CORE_SHRINKAGE', {}).get('NOMINAL_COORDS', {})
    )
    if not nominal_coords:
        return False

    outlier_ppm = float(settings.get('REGISTRATION_SHRINKAGE', {}).get('outlier_ppm', 50.0))
    sections = []
    summary_rows = []
    for process_code, proc_df in process_frames.items():
        if proc_df.empty or any(c not in proc_df.columns for c in (loc_col, x_col, y_col)):
            continue
        for bu, bu_df in _iter_build_up_frames(proc_df):
            result = compute_distance_shrinkage(
                bu_df,
                nominal_coords,
                location_col=loc_col,
                x_col=x_col,
                y_col=y_col,
                outlier_ppm=outlier_ppm,
            )
            if result.quadrant.empty:
                continue
            fp = result.full_panel.iloc[0]
            uni = result.uniformity.iloc[0]
            sections.append((process_code, bu, result))
            summary_rows.append({
                'Process': process_code,
                'Build Up': bu,
                'FP X (%)': fp.get('Shrinkage X (FP %)', 0.0),
                'FP Y (%)': fp.get('Shrinkage Y (FP %)', 0.0),
                'X-Y Offset (%)': fp.get('Shrinkage X-Y Offset (%)', 0.0),
                'FP X (PPM)': fp.get('Shrinkage X (FP PPM)', fp.get('Shrinkage X (FP)', 0.0)),
                'FP Y (PPM)': fp.get('Shrinkage Y (FP PPM)', fp.get('Shrinkage Y (FP)', 0.0)),
                'QTQ X (PPM)': uni.get('QTQ Range X', 0.0),
                'QTQ Y (PPM)': uni.get('QTQ Range Y', 0.0),
                '2D Distortion (PPM)': uni.get('Total 2D Spatial Distortion Vector', 0.0),
                'Alert Count': len(result.outliers),
            })

    if not sections:
        return False

    sheet_name = _safe_sheet_name('Shrinkage Summary', used_sheet_names)
    ws = writer.book.create_sheet(sheet_name)
    ws['A1'] = 'Distance-Based Shrinkage Summary (PTV + VTP)'
    ws['A2'] = 'Method: distance-only (no coordinate transform/alignment).'

    summary_df = pd.DataFrame(summary_rows).round(3)
    summary_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=3)

    row = 6 + len(summary_df)
    for process_code, bu, result in sections:
        ws.cell(row=row, column=1, value=f'{process_code} | Build Up: {bu}')
        row += 1
        ws.cell(row=row, column=1, value='Executive Summary')
        row += 1

        fp = result.full_panel.iloc[0]
        uni = result.uniformity.iloc[0]
        exec_df = pd.DataFrame([{
            'FP X (%)': fp.get('Shrinkage X (FP %)', 0.0),
            'FP Y (%)': fp.get('Shrinkage Y (FP %)', 0.0),
            'X-Y Offset (%)': fp.get('Shrinkage X-Y Offset (%)', 0.0),
            'FP X (PPM)': fp.get('Shrinkage X (FP PPM)', fp.get('Shrinkage X (FP)', 0.0)),
            'FP Y (PPM)': fp.get('Shrinkage Y (FP PPM)', fp.get('Shrinkage Y (FP)', 0.0)),
            'QTQ X (PPM)': uni.get('QTQ Range X', 0.0),
            'QTQ Y (PPM)': uni.get('QTQ Range Y', 0.0),
            '2D Distortion (PPM)': uni.get('Total 2D Spatial Distortion Vector', 0.0),
            'Alert Count': len(result.outliers),
        }]).round(3)
        exec_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=row - 1)
        row += len(exec_df) + 2

        ws.cell(row=row, column=1, value='Quadrant Summary')
        row += 1
        q_cols = [
            'Quadrant', 'QP Shrinkage X (%)', 'QP Shrinkage Y (%)',
            'Delta X (um)', 'Delta Y (um)',
            'QP Shrinkage X (PPM)', 'QP Shrinkage Y (PPM)',
        ]
        show_q_cols = [c for c in q_cols if c in result.quadrant.columns]
        result.quadrant[show_q_cols].to_excel(writer, sheet_name=sheet_name, index=False, startrow=row - 1)
        row += len(result.quadrant) + 2

        ws.cell(row=row, column=1, value='Uniformity')
        row += 1
        u_cols = [
            'QTQ Range X (%)', 'QTQ Range Y (%)', 'QTQ Range X', 'QTQ Range Y',
            'Total 2D Spatial Distortion Vector',
        ]
        show_u_cols = [c for c in u_cols if c in result.uniformity.columns]
        result.uniformity[show_u_cols].to_excel(writer, sheet_name=sheet_name, index=False, startrow=row - 1)
        row += len(result.uniformity) + 2

        ws.cell(row=row, column=1, value='Outlier Alerts')
        row += 1
        if result.outliers.empty:
            pd.DataFrame({'Alert': [f'No quadrant exceeds ±{outlier_ppm:.0f} ppm from FP average.']}).to_excel(
                writer, sheet_name=sheet_name, index=False, startrow=row - 1
            )
            row += 2
        else:
            result.outliers.to_excel(writer, sheet_name=sheet_name, index=False, startrow=row - 1)
            row += len(result.outliers) + 2

        if result.warnings:
            ws.cell(row=row, column=1, value='Warnings')
            row += 1
            for msg in result.warnings:
                ws.cell(row=row, column=1, value=msg)
                row += 1
            row += 1

    return True


def _report_sheet(df: pd.DataFrame, grid_id_col: str, meta: dict,
                  usl_col_name: str, usl_value: float,
                  include_xy_usl: bool = False) -> pd.DataFrame:
    """Full report frame: metadata prepended, USL reference column(s) appended.

    Per-row provenance (Build Up, Panel, Side) is read from ``df`` itself, which
    build_display_frame has already sorted, so each value stays with its own
    fiducial. Taking them from a separately-ordered source misattributed them:
    the display frame is sorted by Grid ID while the parsed frame is grouped by
    file, so a scope covering both sides interleaved the two orders and half the
    rows were labelled with the other side's values.

    Job-level metadata (project, part, lot) has no per-row variation and comes
    from ``meta``. `usl_col_name`/`usl_value` name the process-specific
    spec-limit column ('VtP_USL' for Via-to-Pad, 'PtV_USL' for Pad-to-Via). When
    `include_xy_usl` is set, blank X/Y USL columns are appended too
    (Via-to-Pad only).
    """
    s = df.copy()

    def _per_row(column: str, meta_key: str):
        """That column's own values when present, else the job-level fallback."""
        return s[column] if column in s.columns else meta.get(meta_key, '')

    side_vals     = _per_row('Side', 'side')
    panel_vals    = _per_row('Panel', 'panel')
    build_up_vals = _per_row('Build Up', 'build_up')

    drop_if_present = [
        'Project_Name', 'Part_Number', 'Lot_Number', 'Lot_Name',
        'Buildup', 'Build Up', 'Process', 'Panel', 'Side',
        'Fiducial', 'Fiducial_Number', 'VtP_USL', 'PtV_USL', 'X_USL', 'Y_USL',
    ]
    existing = [c for c in drop_if_present if c in s.columns]
    if existing:
        s = s.drop(columns=existing)

    # Keep report generation resilient when Grid ID is missing/malformed.
    if grid_id_col in s.columns:
        grid_str = s[grid_id_col].astype(str).str.replace(r'\D', '', regex=True).str.zfill(2)
        s.insert(0, 'Fiducial', grid_str.str[0].map(_REGION_MAP))
        s.insert(0, 'Fiducial_Number', pd.to_numeric(grid_str.str[1], errors='coerce'))
    else:
        logger.warning('Report export: missing grid id column "%s"; fiducial fields left blank', grid_id_col)
        s.insert(0, 'Fiducial', None)
        s.insert(0, 'Fiducial_Number', None)

    s.insert(0, 'Side',        side_vals)
    s.insert(0, 'Panel',       panel_vals)
    s.insert(0, 'Process',     meta.get('process', ''))
    s.insert(0, 'Buildup',     build_up_vals)
    s.insert(0, 'Lot_Name',    meta.get('lot_name', ''))
    s.insert(0, 'Lot_Number',  meta.get('lot_number', ''))
    s.insert(0, 'Part_Number', meta.get('part_number', ''))
    s.insert(0, 'Project_Name', meta.get('project_name', ''))
    if grid_id_col in s.columns:
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

def write_unified_excel(writer: pd.ExcelWriter, scoped_df: pd.DataFrame,
                        settings: dict, meta: dict,
                        warnings: list = None) -> None:
    """Write one workbook with process-separated sheets and BU analytics.

    Sheets written:
    - 'Via to Pad' — process data with panel map
    - 'Pad to Via' — process data with panel map
    - 'Report' — consolidated process-aware report table
    - 'Analytics <PROC> <BU>' — one analytics sheet per process and Build Up
    - 'Shrinkage Summary' — one combined shrinkage sheet for all process/BU sections
    - 'Warnings' — parser warnings
    """
    if scoped_df is None or scoped_df.empty:
        pd.DataFrame({'info': ['No data available for export scope.']}).to_excel(
            writer, sheet_name='Report', index=False)
        ws_warn = writer.book.create_sheet('Warnings')
        _warnings_sheet(ws_warn, warnings or [])
        return

    process_frames = _process_slices(scoped_df)
    vtp_usl = float(settings.get('VTP_REGISTRATION', {}).get('vtp_usl_um', 10.0))
    ptv_usl = float(settings.get('PTV_REGISTRATION', {}).get('ptv_usl_um', 10.0))

    report_frames = []
    for process_code, proc_df in process_frames.items():
        if proc_df.empty:
            continue

        is_vtp = process_code == 'VTP'
        sheet_base = 'Via to Pad' if is_vtp else 'Pad to Via'
        proc_display = build_display_frame(proc_df, settings, is_via_to_pad=is_vtp)
        proc_meta = dict(meta)
        proc_meta['process'] = sheet_base

        proc_display.to_excel(writer, sheet_name=sheet_base, index=False)
        _add_panel_map(writer.sheets[sheet_base], settings, sheet_base)

        report_frames.append(
            _report_sheet(
                proc_display,
                GRID_ID_HEADER,
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

        for bu, bu_df in _iter_build_up_frames(proc_df):

            label = _safe_sheet_name(f'Analytics {process_code} {bu}', used_sheet_names)
            _add_analytics_sheet(writer, bu_df, settings, sheet_label=label)

    _write_shrinkage_summary_sheet(writer, settings, process_frames, used_sheet_names)

    ws_warn = writer.book.create_sheet(_safe_sheet_name('Warnings', used_sheet_names))
    _warnings_sheet(ws_warn, warnings or [])


def write_core_shrinkage_excel(writer: pd.ExcelWriter,
                                front_df: pd.DataFrame,
                                back_df: pd.DataFrame,
                                meta: dict,
                                warnings: list = None,
                                nominal_coords: dict = None,
                                settings: dict = None) -> None:
    """Write Core Shrinkage data into the given ExcelWriter.

    Sheets written:
    - 'Core Shrinkage - Front'  Quarter | Grid | X | Y            (skipped if empty)
    - 'Core Shrinkage - Back'   Quarter | Grid | X | Y            (skipped if empty)
    - 'Core Shrinkage'          Quarter | Grid | Front X/Y | Back X/Y (both layers only)
    - 'CS Summary'              headline ppm / residual µm / outliers, per layer (nominal set)
    - 'QP Shrinkage - Front'    Quadrant | X1..Y2 pitch error in µm (when nominal_coords set)
    - 'QP Shrinkage - Back'     same                              (when nominal_coords set)
    - 'Scale Factor - Front'    Quadrant | X/Y Shrinkage (ppm)     (when nominal_coords set)
    - 'Scale Factor - Back'     same                              (when nominal_coords set)
    - 'Affine - Front'          affine decomposition params       (when nominal_coords set)
    - 'Affine - Back'           same                              (when nominal_coords set)
    - 'Raw Deviation - Front'   nominal vs physical raw deltas    (when nominal_coords set)
    - 'Raw Deviation - Back'    same                              (when nominal_coords set)
    - 'Residuals - Front'       per-fiducial residuals in µm + Outlier (nominal set)
    - 'Residuals - Back'        same                              (when nominal_coords set)
    - 'Report'                  job metadata + main measurement table
    - 'Warnings'                parser warnings

    Units: deviations/residuals/QP in µm, shrinkage in ppm (rationalised).
    """
    if not front_df.empty:
        layer_frame(front_df).to_excel(writer, sheet_name='Core Shrinkage - Front', index=False)
    if not back_df.empty:
        layer_frame(back_df).to_excel(writer, sheet_name='Core Shrinkage - Back', index=False)

    # Main table: side-by-side when both layers, else the single available layer
    if not front_df.empty and not back_df.empty:
        main = both_frame(front_df, back_df)
        main.to_excel(writer, sheet_name='Core Shrinkage', index=False)
    elif not front_df.empty:
        main = layer_frame(front_df)
    elif not back_df.empty:
        main = layer_frame(back_df)
    else:
        main = pd.DataFrame()

    # 3-level analysis sheets (only when nominal coords are available)
    if nominal_coords:
        outlier_um = float((settings or {}).get('CORE_SHRINKAGE', {}).get('outlier_um', 50.0))

        # CS Summary — headline numbers per layer, Metric | Front | Back
        summary_cols = {}
        for lbl, ldf in [('Front', front_df), ('Back', back_df)]:
            if ldf.empty:
                continue
            s = summary_frame(compute_shrinkage_summary(ldf, nominal_coords, settings))
            if not s.empty:
                summary_cols[lbl] = s.set_index('Metric')['Value']
        if summary_cols:
            cs_summary = pd.DataFrame(summary_cols)
            cs_summary.index.name = 'Metric'
            cs_summary.reset_index().to_excel(writer, sheet_name='CS Summary', index=False)

        for lbl, ldf in [('Front', front_df), ('Back', back_df)]:
            if ldf.empty:
                continue
            qp = qp_shrinkage_um(ldf)                       # µm pitch error
            sf = compute_scale_factor(ldf)
            if not qp.empty:
                qp.to_excel(writer, sheet_name=f'QP Shrinkage - {lbl}', index=False)
            if not sf.empty:
                # ppm only — drop the bare scale-factor columns
                sf_ppm = sf[['Quadrant', 'X Shrinkage (ppm)', 'Y Shrinkage (ppm)']]
                sf_ppm.to_excel(writer, sheet_name=f'Scale Factor - {lbl}', index=False)
            analysis = compute_affine_analysis(ldf, nominal_coords, settings)
            if analysis:
                analysis['params'].to_excel(
                    writer, sheet_name=f'Affine - {lbl}', index=False)
                affine_residuals_um(analysis, outlier_um).to_excel(
                    writer, sheet_name=f'Residuals - {lbl}', index=False)
                coords = compute_centered_deviation_table(ldf, nominal_coords, settings)
                if not coords.empty:
                    coords.to_excel(writer, sheet_name=f'Coordinates - {lbl}', index=False)

    # Report sheet — job metadata prepended to the main table
    report = main.copy()
    for meta_key, col_name in [
        ('project_name', 'Project_Name'),
        ('part_number',  'Part_Number'),
        ('lot_number',   'Lot_Number'),
        ('lot_name',     'Lot_Name'),
        ('build_up',     'Buildup'),
        ('process',      'Process'),
        ('panel',        'Job_Panel'),
    ]:
        report.insert(0, col_name, meta.get(meta_key, ''))
    report.to_excel(writer, sheet_name='Report', index=False)

    # Warnings sheet
    ws_warn = writer.book.create_sheet('Warnings')
    _warnings_sheet(ws_warn, warnings or [])
