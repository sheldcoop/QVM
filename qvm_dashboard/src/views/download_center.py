"""Download Center — compile multi-sheet Excel summaries and a chart ZIP archive.

Reuses the shared data layer (config / loader / columns) so the per-sheet metric
definitions live in exactly one place (``src.dbanalysis.config``).
"""

import io
import zipfile
import logging

import pandas as pd
import streamlit as st

from src.dbanalysis.columns import normalize_col, find_col, resolve_limits
from src.dbanalysis.config import DB_ANALYSES, AnalysisConfig
from src.dbanalysis.loader import load_sheet
from src.dbanalysis.summary import (
    generate_summary_table,
    generate_lot_summary_table,
    generate_detailed_summary_table,
)
from src.dbanalysis.visuals import plot_roughness_box, plot_control_chart

logger = logging.getLogger(__name__)


class DownloadCenterView:
    def __init__(self, settings: dict, db_files: list):
        self.settings = settings
        self.db_files = db_files

    # ------------------------------------------------------------------ #
    #  UI
    # ------------------------------------------------------------------ #
    def render(self):
        st.header("📥 Download Center")
        st.markdown("Central hub for exporting compiled data and visualizations.")

        if not self.db_files:
            st.warning("Please upload a Horus database file in the sidebar first.")
            return

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Master Excel Summary")
            st.markdown("Generates a multi-sheet Excel file containing statistical summaries for all metrics.")
            if st.button("Compile Excel Summary", use_container_width=True, key="btn_compile_excel"):
                with st.spinner("Compiling Excel file..."):
                    try:
                        st.session_state['excel_bytes'] = self._generate_excel_summary()
                        st.success("Compilation complete! Click below to download.")
                    except Exception as e:  # noqa: BLE001 - surfaced to the user
                        logger.error("Failed to compile Excel: %s", e, exc_info=True)
                        st.error(f"Failed to compile Excel: {e}")
            if 'excel_bytes' in st.session_state:
                st.download_button(
                    label="Download Master Summary",
                    data=st.session_state['excel_bytes'],
                    file_name="Master_Summary.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, key="dl_excel",
                )

        with col2:
            st.subheader("Complete Chart Archive")
            st.markdown("Generates a ZIP file containing PNGs of every single chart (Box & Control).")
            st.warning("Warning: This requires `kaleido` and may take a few minutes to render.")
            if st.button("Generate Chart Archive (ZIP)", use_container_width=True, key="btn_compile_zip"):
                with st.spinner("Rendering charts headlessly... Please do not refresh the page..."):
                    try:
                        st.session_state['zip_bytes'] = self._generate_chart_zip()
                        st.success("Archive generated! Click below to download.")
                    except Exception as e:  # noqa: BLE001 - surfaced to the user
                        logger.error("Failed to generate archive: %s", e, exc_info=True)
                        if "kaleido" in str(e).lower() or "executable" in str(e).lower():
                            st.error("Kaleido issue detected. Install it (`pip install kaleido`) and restart Streamlit.")
                        else:
                            st.error(f"Failed to generate archive: {e}")
            if 'zip_bytes' in st.session_state:
                st.download_button(
                    label="Download ZIP Archive",
                    data=st.session_state['zip_bytes'],
                    file_name="Chart_Archive.zip",
                    mime="application/zip",
                    use_container_width=True, key="dl_zip",
                )

    # ------------------------------------------------------------------ #
    #  Excel summary
    # ------------------------------------------------------------------ #
    def _generate_excel_summary(self) -> bytes:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            for file in self.db_files:
                for config in DB_ANALYSES.values():
                    try:
                        df = load_sheet(file, config.sheet_name)
                        if df is None:
                            continue
                        agg, lot, detailed = self._compile_summary_for_sheet(df, config)
                        if agg.empty:
                            continue
                        sheet = f"{config.short_name} Summary"[:31]
                        offset = 0
                        offset = _write_parallel(writer, agg, "AGGREGATE SUMMARY (All Lots)", offset, sheet)
                        offset = _write_parallel(writer, lot, "LOT-BY-LOT AGGREGATE BREAKDOWN", offset, sheet)
                        offset = _write_parallel(writer, detailed, "DETAILED SUMMARY (Panel Level)", offset, sheet)
                    except Exception as e:  # noqa: BLE001
                        logger.error("Failed to process %s / %s for Excel: %s",
                                     file.name, config.sheet_name, e)
        return output.getvalue()

    def _compile_summary_for_sheet(self, df: pd.DataFrame, config: AnalysisConfig):
        df = _ensure_header(df)
        buildup_col = find_col(df, "buildup")
        side_col = find_col(df, "side")
        process_col = find_col(df, "process")
        lot_col = find_col(df, "lot number")
        panel_col = find_col(df, "panel")
        if not buildup_col or not side_col:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df = df.copy()
        df['_bu'] = df[buildup_col].astype(str).str.strip()
        df['_side'] = df[side_col].astype(str).str.strip()

        agg_all, lot_all, det_all = [], [], []
        for bu in df['_bu'].dropna().unique():
            for side in df['_side'].dropna().unique():
                sub = df[(df['_bu'] == bu) & (df['_side'] == side)].copy()
                if sub.empty:
                    continue
                metrics_def = _metrics_def(sub, config)
                if not metrics_def:
                    continue

                agg = generate_summary_table(sub, process_col, metrics_def)
                if _tag(agg, bu, side):
                    agg_all.append(agg)
                if lot_col:
                    lot = generate_lot_summary_table(sub, process_col, lot_col, metrics_def)
                    if _tag(lot, bu, side):
                        lot_all.append(lot)
                if lot_col and panel_col:
                    det = generate_detailed_summary_table(sub, process_col, lot_col, panel_col, metrics_def)
                    if _tag(det, bu, side):
                        det_all.append(det)

        return (
            pd.concat(agg_all, ignore_index=True) if agg_all else pd.DataFrame(),
            pd.concat(lot_all, ignore_index=True) if lot_all else pd.DataFrame(),
            pd.concat(det_all, ignore_index=True) if det_all else pd.DataFrame(),
        )

    # ------------------------------------------------------------------ #
    #  Chart ZIP
    # ------------------------------------------------------------------ #
    def _generate_chart_zip(self) -> bytes:
        output = io.BytesIO()
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file in self.db_files:
                for config in DB_ANALYSES.values():
                    df = load_sheet(file, config.sheet_name)
                    if df is None:
                        continue
                    self._process_sheet_for_zip(zipf, df, config)
        return output.getvalue()

    def _process_sheet_for_zip(self, zipf: zipfile.ZipFile, df: pd.DataFrame,
                               config: AnalysisConfig):
        df = _ensure_header(df)
        buildup_col = find_col(df, "buildup")
        side_col = find_col(df, "side")
        process_col = find_col(df, "process")
        lot_col = find_col(df, "lot number")
        panel_col = find_col(df, "panel")
        unit_col = find_col(df, "unit")
        if not buildup_col or not side_col or not lot_col:
            return

        df = df.copy()
        df['_bu'] = df[buildup_col].astype(str).str.strip()
        df['_side'] = df[side_col].astype(str).str.strip()

        for bu in df['_bu'].dropna().unique():
            for side in df['_side'].dropna().unique():
                sub = df[(df['_bu'] == bu) & (df['_side'] == side)].copy()
                if sub.empty:
                    continue
                _apply_scales(sub, config)
                processes = (sub[process_col].dropna().astype(str).str.strip().unique().tolist()
                             if process_col else [None])
                for proc in processes:
                    proc_df = (sub[sub[process_col].astype(str).str.strip() == proc].copy()
                               if proc and process_col else sub.copy())
                    if proc_df.empty:
                        continue
                    safe_proc = str(proc).replace(" ", "_").replace("/", "_") if proc else "All"
                    for m in config.metrics:
                        col = find_col(proc_df, m.col)
                        if col is None:
                            continue
                        limits = resolve_limits(proc_df, m.limit_prefix) if m.limit_prefix else {}
                        safe_metric = m.name.replace(" ", "_").replace("/", "_")
                        base = f"{config.short_name}/{bu}/{side}/{safe_metric}"
                        title = f"{config.short_name} - {bu} {side} - {m.name} {safe_proc}"

                        fig_box = plot_roughness_box(proc_df, col, lot_col, title,
                                                     color_by_col=unit_col, limits=limits,
                                                     measurement_unit=m.display_unit)
                        zipf.writestr(f"{base}/{safe_proc}_BoxPlot.png",
                                      fig_box.to_image(format="png", width=1200, height=600))

                        fig_cc = plot_control_chart(proc_df, col, lot_col, panel_col, title,
                                                    measurement_unit=m.display_unit)
                        zipf.writestr(f"{base}/{safe_proc}_ControlChart.png",
                                      fig_cc.to_image(format="png", width=1200, height=800))


# ---------------------------------------------------------------------- #
#  Module-level helpers
# ---------------------------------------------------------------------- #

def _ensure_header(df: pd.DataFrame) -> pd.DataFrame:
    """Promote a real header row if the sheet's first rows are not the header."""
    if any(normalize_col(c) in ('side', 'process', 'buildup') for c in df.columns):
        return df
    for idx, row in df.head(15).iterrows():
        if any(isinstance(v, str) and normalize_col(v) in ('side', 'process', 'buildup')
               for v in row.values):
            out = df.copy()
            out.columns = out.iloc[idx]
            return out.iloc[idx + 1:].reset_index(drop=True)
    return df


def _apply_scales(df: pd.DataFrame, config: AnalysisConfig) -> None:
    for m in config.metrics:
        if m.display_scale == 1.0:
            continue
        col = find_col(df, m.col)
        if col is not None:
            df[col] = pd.to_numeric(df[col], errors='coerce') * m.display_scale


def _metrics_def(df: pd.DataFrame, config: AnalysisConfig) -> list:
    _apply_scales(df, config)
    defs = []
    for m in config.metrics:
        col = find_col(df, m.col)
        if col is None:
            continue
        limits = resolve_limits(df, m.limit_prefix) if m.limit_prefix else {}
        defs.append({"name": m.name, "col": col, "limits": limits})
    return defs


def _tag(summary_df: pd.DataFrame, bu: str, side: str) -> bool:
    """Prepend Buildup/Side columns in place; return True if non-empty."""
    if summary_df.empty:
        return False
    summary_df.insert(0, 'Side', side)
    summary_df.insert(0, 'Buildup', bu)
    return True


def _write_parallel(writer, df: pd.DataFrame, title: str, start_row: int, sheet: str) -> int:
    """Write Front/Back summaries side-by-side; return the next free row."""
    if df.empty:
        return start_row

    front = df[df['Side'].str.lower() == 'front'].copy()
    back = df[df['Side'].str.lower() == 'back'].copy()
    other = df[~df['Side'].str.lower().isin(['front', 'back'])].copy()
    col_width = len(df.columns)
    max_rows = 0

    if not front.empty:
        front.to_excel(writer, sheet_name=sheet, index=False, startrow=start_row + 1, startcol=0)
        writer.sheets[sheet].write_string(start_row, 0, f"{title} - FRONT")
        max_rows = max(max_rows, len(front))
    if not back.empty:
        back_col = col_width + 2
        back.to_excel(writer, sheet_name=sheet, index=False, startrow=start_row + 1, startcol=back_col)
        writer.sheets[sheet].write_string(start_row, back_col, f"{title} - BACK")
        max_rows = max(max_rows, len(back))
    if not other.empty and front.empty and back.empty:
        other.to_excel(writer, sheet_name=sheet, index=False, startrow=start_row + 1, startcol=0)
        writer.sheets[sheet].write_string(start_row, 0, f"{title}")
        max_rows = max(max_rows, len(other))

    return start_row + max_rows + 4
