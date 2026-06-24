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
    for each. Spec limits are assumed constant within a filtered slice, matching
    how the Horus sheets store them. Missing limits are simply omitted.
    """
    limits = {}
    for limit_type in ('LSL', 'Target', 'USL'):
        col = find_col(df, f"{prefix} {limit_type.lower()}")
        if col is not None and not df[col].isna().all():
            limits[limit_type] = df[col].dropna().iloc[0]
    return limits
