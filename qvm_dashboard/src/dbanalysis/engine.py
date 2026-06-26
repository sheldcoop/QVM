"""Generic renderer for every Database Analysis sub-view.

One code path drives all Horus sheets, parameterised by an
:class:`~src.dbanalysis.config.AnalysisConfig`. This replaces the six near-identical
view modules that previously differed only in configuration.
"""

import logging
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

from src.dbanalysis.columns import find_col, group_limits
from src.dbanalysis.config import AnalysisConfig, Metric
from src.dbanalysis.loader import load_sheet, list_sheets
from src.dbanalysis.summary import (
    generate_summary_table,
    generate_lot_summary_table,
    generate_detailed_summary_table,
)
from src.dbanalysis.visuals import (
    plot_roughness_box,
    plot_control_chart,
    plot_roughness_trend,
)
from ui.sidebar import render_nav_buttons

logger = logging.getLogger(__name__)


def render_analysis(config: AnalysisConfig, files: list, settings: dict = None) -> None:
    """Render the analysis described by ``config`` for each uploaded file."""
    if not files:
        st.info("No database files uploaded.")
        return

    style = (settings or {}).get('CHART_SETTINGS', {})
    for file in files:
        try:
            with st.spinner(f"Loading {file.name}..."):
                df = load_sheet(file, config.sheet_name)
            if df is None:
                st.warning(
                    f"Could not find a sheet named '{config.sheet_name}' in "
                    f"{file.name}. Available sheets: {list_sheets(file)}"
                )
                continue
            _render_sheet(config, df, style)
        except FileNotFoundError as e:
            logger.error("File missing for %s: %s", file.name, e)
            st.error(f"Could not read {file.name}: {e}")
        except ValueError as e:
            # pandas/openpyxl raise ValueError for malformed workbooks/sheets.
            logger.error("Failed to parse %s: %s", file.name, e)
            st.error(f"Failed to parse {file.name}: {e}")


def _arrow_safe(df: pd.DataFrame) -> pd.DataFrame:
    """Cast object columns to str so st.dataframe's Arrow conversion never errors.

    Raw Horus columns like ``Ra_Std_dev`` store strings such as ``"0.89nm"`` mixed
    with numbers, which Arrow can't serialise. This only affects on-screen display.
    """
    out = df.copy()
    for c in out.columns:
        if out[c].dtype == object:
            out[c] = out[c].astype(str)
    return out


def _render_sheet(config: AnalysisConfig, df: pd.DataFrame, style: dict = None) -> None:
    buildup_col = find_col(df, "buildup")
    side_col = find_col(df, "side")
    if not buildup_col or not side_col:
        st.warning("Could not find 'Buildup' or 'Side' columns. Showing all data.")
        st.dataframe(_arrow_safe(df), width='stretch')
        return

    selected_bu, selected_side, chart_type = _scope_controls(
        df, config, buildup_col, side_col)

    side_df = _filter_scope(df, buildup_col, side_col, selected_bu, selected_side)
    if side_df.empty:
        st.info(f"No data found for {selected_bu} - {selected_side}")
        return

    lot_col = find_col(side_df, "lot number")
    panel_col = find_col(side_df, "panel")
    process_col = find_col(side_df, "process")
    unit_col = find_col(side_df, "unit")

    # Apply each metric's display scale once, up front, so summaries and charts agree.
    resolved = _resolve_metrics(side_df, config.metrics)
    for m, col in resolved:
        if m.display_scale != 1.0:
            side_df[col] = pd.to_numeric(side_df[col], errors='coerce') * m.display_scale

    if not lot_col:
        st.warning("Could not find 'Lot Number' column to group the charts by.")
        with st.expander("View Raw Filtered Data"):
            st.dataframe(_arrow_safe(side_df), width='stretch')
        return

    # Some sheets (Roughness) carry a sub-position that must NOT be pooled
    # (e.g. BKM vs Next-to-via). Render a separate section per split value.
    split_col = find_col(side_df, config.split_col) if config.split_col else None
    if split_col:
        for val in sorted(side_df[split_col].dropna().astype(str).str.strip().unique()):
            slice_df = side_df[side_df[split_col].astype(str).str.strip() == val].copy()
            if slice_df.empty:
                continue
            st.markdown(f"## {val}")
            _render_slice(slice_df, resolved, chart_type, selected_bu, selected_side,
                          lot_col, panel_col, process_col, unit_col, style, extra_scope=val)
            st.markdown("---")
    else:
        _render_slice(side_df, resolved, chart_type, selected_bu, selected_side,
                      lot_col, panel_col, process_col, unit_col, style)

    with st.expander("View Raw Filtered Data"):
        st.dataframe(side_df, width='stretch')


def _render_slice(df, resolved, chart_type, selected_bu, selected_side, lot_col,
                  panel_col, process_col, unit_col, style: dict = None,
                  extra_scope: str = "") -> None:
    _render_summaries(df, resolved, process_col, lot_col, panel_col)
    _render_charts(df, resolved, chart_type, selected_bu, selected_side,
                   lot_col, panel_col, process_col, unit_col, extra_scope, style)


def _scope_controls(df: pd.DataFrame, config: AnalysisConfig,
                    buildup_col: str, side_col: str) -> Tuple[str, str, str]:
    """Render the Buildup / Side / Chart-Type selectors; options come from data."""
    buildups = sorted(df[buildup_col].dropna().astype(str).str.strip().unique().tolist())
    sides = sorted(df[side_col].dropna().astype(str).str.strip().unique().tolist())
    p = config.state_prefix

    with st.expander("Analysis Scope", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown("**Select Buildup**")
            selected_bu = render_nav_buttons(buildups, state_key=f"{p}_bu")
        with col2:
            st.markdown("**Select Side**")
            selected_side = render_nav_buttons(sides, state_key=f"{p}_side")
        with col3:
            st.markdown("**Chart Type**")
            chart_type = render_nav_buttons(
                ["Box Plot", "Control Chart", "Trend Analysis"],
                state_key=f"{p}_chart")
    st.markdown("---")
    return selected_bu, selected_side, chart_type


def _filter_scope(df: pd.DataFrame, buildup_col: str, side_col: str,
                  selected_bu: str, selected_side: str) -> pd.DataFrame:
    bu_mask = df[buildup_col].astype(str).str.strip() == selected_bu
    side_mask = df[side_col].astype(str).str.strip() == selected_side
    return df[bu_mask & side_mask].copy()


def _resolve_metrics(df: pd.DataFrame, metrics: List[Metric]) -> List[Tuple[Metric, str]]:
    """Pair each configured metric with its actual column, dropping absent ones."""
    out = []
    for m in metrics:
        col = find_col(df, m.col)
        if col is not None:
            out.append((m, col))
    return out


def _metrics_def(resolved: List[Tuple[Metric, str]]) -> List[dict]:
    """Build the {name, col, limit_prefix} list consumed by the summary functions.

    The prefix (not a precomputed limit) is passed through so the summary resolves
    each aggregation group's spec from its own rows and guards mixed specs.
    """
    return [{"name": m.name, "col": col, "limit_prefix": m.limit_prefix}
            for m, col in resolved]


def _render_summaries(df: pd.DataFrame, resolved, process_col: Optional[str],
                      lot_col: str, panel_col: Optional[str]) -> None:
    metrics_def = _metrics_def(resolved)
    summary_df = generate_summary_table(df, process_col, metrics_def)
    if summary_df.empty:
        return

    st.markdown("### Statistical Summary")
    st.dataframe(summary_df, width='stretch', hide_index=True)

    lot_summary = generate_lot_summary_table(df, process_col, lot_col, metrics_def)
    if not lot_summary.empty:
        with st.expander("View Lot-by-Lot Aggregate Breakdown"):
            st.dataframe(lot_summary, width='stretch', hide_index=True)

    if panel_col:
        detailed = generate_detailed_summary_table(
            df, process_col, lot_col, panel_col, metrics_def)
        if not detailed.empty:
            with st.expander("View Detailed Summary (Panel Level)"):
                st.dataframe(detailed, width='stretch', hide_index=True)
    st.markdown("---")


def _render_charts(df: pd.DataFrame, resolved, chart_type: str,
                   selected_bu: str, selected_side: str, lot_col: str,
                   panel_col: Optional[str], process_col: Optional[str],
                   unit_col: Optional[str], extra_scope: str = "",
                   style: dict = None) -> None:
    # Trend Analysis overlays every process as its own line, so it is rendered
    # once per metric across all processes rather than inside the per-process
    # loop the box/control charts use.
    if chart_type == "Trend Analysis":
        base = f"{selected_bu} {selected_side}"
        if extra_scope:
            base = f"{base} {extra_scope}"
        for m, col in resolved:
            fig = plot_roughness_trend(
                df, col, lot_col, process_col,
                f"{m.name} - {base}", measurement_unit=m.display_unit, style=style)
            st.plotly_chart(fig, width='stretch')
            st.markdown("<br>", unsafe_allow_html=True)
        return

    processes = (df[process_col].dropna().astype(str).str.strip().unique().tolist()
                 if process_col else [None])

    for proc in processes:
        if proc and process_col:
            proc_df = df[df[process_col].astype(str).str.strip() == proc].copy()
        else:
            proc_df = df.copy()
        if proc_df.empty:
            continue

        if proc:
            st.markdown(f"### {proc}")
        suffix = f" ({proc})" if proc else ""

        for m, col in resolved:
            # Single spec → draw lines + badge; mixed/none → no misleading capability.
            limits = group_limits(proc_df, m.limit_prefix)[0] if m.limit_prefix else {}
            base = f"{selected_bu} {selected_side}"
            if extra_scope:
                base = f"{base} {extra_scope}"
            scope = f"{base}{suffix}"
            if chart_type == "Control Chart":
                # Spec limits intentionally not passed — they belong on the box plot.
                fig = plot_control_chart(
                    proc_df, col, lot_col, panel_col,
                    f"{m.name} - {scope}", measurement_unit=m.display_unit, style=style)
            else:
                fig = plot_roughness_box(
                    proc_df, col, lot_col,
                    f"{m.name} Distribution - {scope}", color_by_col=unit_col,
                    limits=limits, measurement_unit=m.display_unit, style=style)
            st.plotly_chart(fig, width='stretch')
            st.markdown("<br>", unsafe_allow_html=True)

        st.divider()
