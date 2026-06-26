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


def _series_label(df: pd.DataFrame, series_cols: list) -> pd.Series:
    """Build the ' · '-joined series label (e.g. 'BU01 · Front · Post AOP')."""
    cols = [c for c in (series_cols or []) if c and c in df.columns]
    if not cols:
        return pd.Series(["All"] * len(df), index=df.index)
    parts = [df[c].astype(str).str.replace(r'\.0$', '', regex=True).str.strip() for c in cols]
    out = parts[0]
    for p in parts[1:]:
        out = out.str.cat(p, sep=' · ')
    return out


OUTLIER_K = 2.0  # flag values more than k standard deviations from the mean


def trend_outliers(df: pd.DataFrame, metric_col: str, lot_col: str, series_cols: list,
                   unit_col: str = None, panel_col: str = None, side_col: str = None,
                   k: float = OUTLIER_K) -> pd.DataFrame:
    """Outliers at two levels, using a simple ``|x - mean| > k·std`` rule.

    Within-lot: individual measurements that sit beyond ``mean ± k·std`` of their
    own (series, lot) group — pinpoints a specific Unit/Panel to chase. Lot-mean:
    a lot whose mean sits beyond ``mean ± k·std`` of the series' other lot-means —
    the dot you see jump on the trend. Each row carries the coordinates to find it
    plus an Impact note showing how much it moves the number it belongs to.

    Returns columns: Series, Lot, Type, Value, Unit, Panel, Side, Impact.
    """
    work = df.copy()
    work["__v"] = pd.to_numeric(work[metric_col], errors='coerce')
    work = work.dropna(subset=["__v"])
    if work.empty:
        return pd.DataFrame()

    work["__series"] = _series_label(work, series_cols)
    work["__lot"] = work[lot_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    def _cell(r, col, strip_dot=False):
        if not col or col not in work.columns:
            return "—"
        v = str(r[col])
        return v.replace('.0', '') if strip_dot else v

    rows = []

    # --- Within-lot: a measurement unusual vs its own lot's peers ----------- #
    for (series, lot), g in work.groupby(["__series", "__lot"]):
        if len(g) < 2:
            continue
        mean, std = g["__v"].mean(), g["__v"].std(ddof=1)
        if not std > 0:
            continue
        flagged = g[(g["__v"] - mean).abs() > k * std]
        for _, r in flagged.iterrows():
            without = g.loc[g.index != r.name, "__v"].mean()
            pct = (without - mean) / mean * 100 if mean else 0.0
            rows.append({
                "Series": series, "Lot": lot, "Type": "within-lot",
                "Value": round(float(r["__v"]), 2),
                "Unit": _cell(r, unit_col), "Panel": _cell(r, panel_col, True),
                "Side": _cell(r, side_col),
                "Impact": f"{mean:.1f} → {without:.1f} ({pct:+.1f}%)",
            })

    # --- Lot-mean: a lot whose mean jumped vs the series' other lots -------- #
    for series, g in work.groupby("__series"):
        lot_means = g.groupby("__lot")["__v"].mean()
        if len(lot_means) < 2:
            continue
        m, s = lot_means.mean(), lot_means.std(ddof=1)
        if not s > 0:
            continue
        for lot, lm in lot_means.items():
            if abs(lm - m) > k * s:
                pct = (lm - m) / m * 100 if m else 0.0
                rows.append({
                    "Series": series, "Lot": lot, "Type": "lot-mean",
                    "Value": round(float(lm), 2),
                    "Unit": "—", "Panel": "—", "Side": "—",
                    "Impact": f"{lm:.1f} vs series {m:.1f} ({pct:+.1f}%)",
                })

    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
            .sort_values(["Series", "Lot", "Type"])
            .reset_index(drop=True))


def trend_series_summary(df: pd.DataFrame, metric_col: str, lot_col: str,
                         series_cols: list) -> list:
    """One concise movement summary per series for the trend charts.

    For each series returns a string: overall direction, total first→last change
    across lots, and the largest single lot-to-lot jump with the lot pair.
    """
    work = df.copy()
    work["__v"] = pd.to_numeric(work[metric_col], errors='coerce')
    work = work.dropna(subset=["__v"])
    if work.empty:
        return []

    work["__series"] = _series_label(work, series_cols)
    work["__lot"] = work[lot_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    lines = []
    for series, g in work.groupby("__series"):
        means = g.groupby("__lot")["__v"].mean()
        lots = sorted(means.index.tolist())
        if len(lots) < 2:
            continue
        means = means.reindex(lots)
        delta = means.iloc[-1] - means.iloc[0]
        arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
        diffs = means.diff().dropna()
        jump_idx = diffs.abs().idxmax()
        jump_pos = lots.index(jump_idx)
        jump_from, jump_to = lots[jump_pos - 1], jump_idx
        jump_val = diffs.loc[jump_idx]
        lines.append(
            f"{arrow} **{series}** — {means.iloc[0]:.1f} → {means.iloc[-1]:.1f} "
            f"(Δ {delta:+.1f}) across {len(lots)} lots; "
            f"biggest jump {jump_val:+.1f} ({jump_from} → {jump_to})")
    return lines


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
