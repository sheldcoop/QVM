"""Column-name resolution helpers for the Horus database sheets.

The Horus exports vary in casing, spacing and underscores between sheets, so
every lookup goes through :func:`normalize_col`. These helpers are the single
source of truth that the view engine and the download center both rely on.
"""

from typing import Iterable, Optional
import pandas as pd


def normalize_col(c) -> str:
    """Normalise a column label for tolerant matching.

    Lower-cases, trims, and treats underscores as spaces so that
    ``"Lot_Number"``, ``"lot number"`` and ``" LOT  NUMBER "`` all compare equal
    once whitespace is collapsed by the caller's exact-string comparison.
    """
    return str(c).strip().lower().replace('_', ' ')


def find_col(df: pd.DataFrame, name: str) -> Optional[str]:
    """Return the actual column in ``df`` whose normalised name equals ``name``.

    ``name`` is compared in normalised form, so pass it as a plain lower-case
    label (e.g. ``"lot number"``). Returns ``None`` when no column matches.
    """
    target = normalize_col(name)
    return next((col for col in df.columns if normalize_col(col) == target), None)


def find_cols(df: pd.DataFrame, names: Iterable[str]) -> list:
    """Return the actual columns matching any of ``names`` (order preserved)."""
    out = []
    for name in names:
        col = find_col(df, name)
        if col is not None and col not in out:
            out.append(col)
    return out


def resolve_limits(df: pd.DataFrame, prefix: str) -> dict:
    """Extract {LSL, Target, USL} spec limits for a metric ``prefix``.

    Looks for columns named ``"<prefix> lsl"`` / ``"<prefix> target"`` /
    ``"<prefix> usl"`` (normalised) and returns the first non-null value found
    for each. NOTE: this collapses a slice to a single spec; for capability use
    :func:`group_limits`, which detects when a group mixes more than one spec.
    """
    limits = {}
    for limit_type in ('LSL', 'Target', 'USL'):
        col = find_col(df, f"{prefix} {limit_type.lower()}")
        if col is not None and not df[col].isna().all():
            limits[limit_type] = df[col].dropna().iloc[0]
    return limits


def distinct_limits(df: pd.DataFrame, prefix: str) -> list:
    """Return the distinct spec dicts present in ``df`` for a metric ``prefix``.

    Distinctness is by the ``(LSL, USL)`` pair. Each returned dict carries
    whichever of ``LSL/Target/USL`` columns exist. Rows where both LSL and USL
    are null are ignored. Empty list when no spec columns / no spec rows exist.
    """
    lsl_c = find_col(df, f"{prefix} lsl")
    usl_c = find_col(df, f"{prefix} usl")
    tgt_c = find_col(df, f"{prefix} target")
    if lsl_c is None and usl_c is None:
        return []

    out, seen = [], set()
    for _, row in df.iterrows():
        lsl = row[lsl_c] if lsl_c is not None else None
        usl = row[usl_c] if usl_c is not None else None
        if pd.isna(lsl) and pd.isna(usl):
            continue
        key = (None if pd.isna(lsl) else lsl, None if pd.isna(usl) else usl)
        if key in seen:
            continue
        seen.add(key)
        d = {}
        if lsl_c is not None and not pd.isna(lsl):
            d["LSL"] = lsl
        if usl_c is not None and not pd.isna(usl):
            d["USL"] = usl
        if tgt_c is not None and not pd.isna(row[tgt_c]):
            d["Target"] = row[tgt_c]
        out.append(d)
    return out


def group_limits(df: pd.DataFrame, prefix: str) -> tuple:
    """Resolve a single spec for an aggregation group, flagging mixed specs.

    Returns ``(limits, mixed)``:
    - exactly one distinct spec → ``(that_dict, False)``
    - no spec present           → ``({}, False)``
    - more than one distinct spec → ``({}, True)`` (caller should report the
      capability as not applicable rather than averaging across specs).
    """
    specs = distinct_limits(df, prefix)
    if len(specs) == 1:
        return specs[0], False
    return {}, len(specs) > 1
