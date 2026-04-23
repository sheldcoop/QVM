"""Shared utility functions used across views and data processing."""

import pandas as pd
from typing import List


def convert_to_microns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Multiply named columns by 1000 (mm → µm) and round to 3 dp.

    Silently skips columns that are not present in df.
    """
    for col in cols:
        if col in df.columns:
            df[col] = (df[col] * 1000).round(3)
    return df
