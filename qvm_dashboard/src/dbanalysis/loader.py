"""Cached Excel access for the Horus database.

The previous views called ``pd.read_excel(file, sheet_name=None)`` on every
Streamlit rerun, re-parsing the entire workbook (all sheets) on each button
click. Here we read only the requested sheet and cache the result on the file
bytes + sheet name, so repeated interactions are instant.
"""

import io
from typing import Iterable, List, Optional

import pandas as pd
import streamlit as st


def find_sheet(names: Iterable[str], wanted: str) -> Optional[str]:
    """Return the actual sheet name matching ``wanted`` case-insensitively."""
    target = str(wanted).strip().lower()
    return next((s for s in names if str(s).strip().lower() == target), None)


@st.cache_data(show_spinner=False)
def _sheet_names(file_bytes: bytes) -> List[str]:
    return pd.ExcelFile(io.BytesIO(file_bytes)).sheet_names


@st.cache_data(show_spinner=False)
def _read_sheet(file_bytes: bytes, sheet_name: str) -> pd.DataFrame:
    # sheet_name as a single string returns one DataFrame (only that sheet is parsed).
    return pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)


def load_sheet(file, wanted_sheet: str) -> Optional[pd.DataFrame]:
    """Load a single sheet by (tolerant) name from an uploaded Excel file.

    Returns ``None`` if the sheet is absent. Results are cached on the file
    content + resolved sheet name.
    """
    data = file.getvalue()
    actual = find_sheet(_sheet_names(data), wanted_sheet)
    if actual is None:
        return None
    return _read_sheet(data, actual)


def list_sheets(file) -> List[str]:
    """Return all sheet names in an uploaded Excel file (cached)."""
    return _sheet_names(file.getvalue())
