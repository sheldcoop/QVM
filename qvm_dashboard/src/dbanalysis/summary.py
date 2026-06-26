import pandas as pd
import numpy as np

from src.dbanalysis.columns import group_limits


def _capability(mean: float, std: float, limits: dict) -> tuple:
    """Return (Pp, Ppk) as formatted strings from OVERALL (long-term) sigma.

    These are Pp/Ppk (process *performance*), not Cp/Cpk, because ``std`` is the
    overall sample standard deviation rather than a within-subgroup estimate.
    One-sided specs are supported: with a single limit, Pp is "N/A" but Ppk is
    computed from that side. Returns ("N/A", "N/A") when capability is undefined.
    """
    if not limits or std is None or not std > 0:
        return "N/A", "N/A"
    lsl = limits.get("LSL")
    usl = limits.get("USL")
    try:
        if lsl is not None and usl is not None:
            lsl, usl = float(lsl), float(usl)
            pp = (usl - lsl) / (6 * std)
            ppk = min((usl - mean) / (3 * std), (mean - lsl) / (3 * std))
            return f"{pp:.2f}", f"{ppk:.2f}"
        if usl is not None:
            return "N/A", f"{(float(usl) - mean) / (3 * std):.2f}"
        if lsl is not None:
            return "N/A", f"{(mean - float(lsl)) / (3 * std):.2f}"
    except (ValueError, TypeError):
        return "N/A", "N/A"
    return "N/A", "N/A"


def _metric_stats(df: pd.DataFrame, col: str):
    """Clean ``col`` and return (n, mean, std, min, max), or None if no data."""
    val = pd.to_numeric(df[col], errors='coerce').dropna()
    if val.empty:
        return None
    return len(val), val.mean(), val.std(), val.min(), val.max()


def _metric_row(df: pd.DataFrame, metric: dict) -> dict:
    """Build the stats row for one metric on one group, or {} if absent/empty.

    Spec limits are resolved from THIS group's own rows when the metric carries a
    ``limit_prefix`` — so each process/lot/panel is scored against its own spec.
    A group that mixes more than one spec reports ``Ppk="N/A (mixed spec)"``
    rather than averaging across specs. Metrics with a precomputed ``limits``
    dict (and no prefix) keep the legacy behaviour.
    """
    col = metric.get("col")
    if not col or col not in df.columns:
        return {}
    stats = _metric_stats(df, col)
    if stats is None:
        return {}
    n, mean, std, min_val, max_val = stats

    prefix = metric.get("limit_prefix")
    if prefix:
        limits, mixed = group_limits(df, prefix)
        if mixed:
            pp, ppk = "N/A", "N/A (mixed spec)"
        else:
            pp, ppk = _capability(mean, std, limits)
    else:
        pp, ppk = _capability(mean, std, metric.get("limits", {}))
    return {
        "Metric": metric.get("name", "Unknown"),
        "N": n,
        "Mean": round(mean, 3),
        "Std Dev": round(std, 3),
        "Min": round(min_val, 3),
        "Max": round(max_val, 3),
        "Pp": pp,
        "Ppk": ppk,
    }


def _uniques(df: pd.DataFrame, col):
    """Non-null unique values of ``col``, or ``[None]`` when ``col`` is falsy."""
    return df[col].dropna().unique().tolist() if col else [None]


def _slice(df: pd.DataFrame, col, value) -> pd.DataFrame:
    """Rows where ``col == value``; the whole frame when ``col``/``value`` absent."""
    return df[df[col] == value].copy() if value is not None and col else df.copy()


def generate_summary_table(df: pd.DataFrame, process_col: str, metrics: list) -> pd.DataFrame:
    """Master statistical summary grouped by Process."""
    rows = []
    for proc in _uniques(df, process_col):
        proc_df = _slice(df, process_col, proc)
        if proc_df.empty:
            continue
        for metric in metrics:
            row = _metric_row(proc_df, metric)
            if row:
                rows.append({"Process": proc if proc is not None else "All", **row})
    return pd.DataFrame(rows)


def generate_lot_summary_table(df: pd.DataFrame, process_col: str, lot_col: str,
                               metrics: list) -> pd.DataFrame:
    """Statistical summary grouped by Lot Number, then Process."""
    rows = []
    for lot in _uniques(df, lot_col):
        lot_df = _slice(df, lot_col, lot)
        if lot_df.empty:
            continue
        for proc in _uniques(lot_df, process_col):
            proc_df = _slice(lot_df, process_col, proc)
            if proc_df.empty:
                continue
            for metric in metrics:
                row = _metric_row(proc_df, metric)
                if row:
                    rows.append({
                        "Lot Number": lot if lot is not None else "All",
                        "Process": proc if proc is not None else "All",
                        **row,
                    })
    return pd.DataFrame(rows)


def generate_detailed_summary_table(df: pd.DataFrame, process_col: str, lot_col: str,
                                    panel_col: str, metrics: list) -> pd.DataFrame:
    """Statistical summary grouped by Lot Number, Panel, then Process."""
    rows = []
    for lot in _uniques(df, lot_col):
        lot_df = _slice(df, lot_col, lot)
        if lot_df.empty:
            continue
        for panel in _uniques(lot_df, panel_col):
            panel_df = _slice(lot_df, panel_col, panel)
            if panel_df.empty:
                continue
            for proc in _uniques(panel_df, process_col):
                proc_df = _slice(panel_df, process_col, proc)
                if proc_df.empty:
                    continue
                for metric in metrics:
                    row = _metric_row(proc_df, metric)
                    if row:
                        rows.append({
                            "Lot Number": lot if lot is not None else "All",
                            "Panel": panel if panel is not None else "All",
                            "Process": proc if proc is not None else "All",
                            **row,
                        })
    return pd.DataFrame(rows)
