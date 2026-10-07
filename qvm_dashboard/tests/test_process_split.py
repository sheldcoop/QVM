"""Tests for the shared Via-to-Pad row mask.

app.py, excel_export.py and quality_control.py each used to test the Process
column their own way, with three different matching rules. They share this one.
"""

import pandas as pd

from src.utils import is_via_to_pad


def _frame(processes):
    return pd.DataFrame({"Process": processes, "value": range(len(processes))})


def test_splits_mixed_processes():
    mask = is_via_to_pad(_frame(["Via to Pad", "Pad to Via", "Via to Pad"]))
    assert mask.tolist() == [True, False, True]


def test_matching_is_case_insensitive():
    assert is_via_to_pad(_frame(["via to pad", "VIA TO PAD"])).all()


def test_nulls_are_not_via_to_pad():
    assert is_via_to_pad(_frame([None, "Pad to Via"])).tolist() == [False, False]


def test_missing_process_column_yields_all_false():
    """No Process column means no Via-to-Pad rows — the dashboard's default tab
    is Pad-to-Via, so unlabelled data lands there rather than vanishing."""
    mask = is_via_to_pad(pd.DataFrame({"value": [1, 2, 3]}))
    assert mask.tolist() == [False, False, False]
    assert len(mask) == 3


def test_mask_index_matches_the_frame():
    df = _frame(["Via to Pad", "Pad to Via"])
    df.index = ["a", "b"]
    assert is_via_to_pad(df).index.tolist() == ["a", "b"]
