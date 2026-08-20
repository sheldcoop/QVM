"""Tests for the Quality Control statistics helper.

annular_stats() is pure so the summary panel's arithmetic can be checked
without standing up Streamlit — the panel was silently broken for a long time
precisely because nothing exercised it.
"""

import numpy as np
import pandas as pd
import pytest

from src.views.quality_control import annular_stats


def test_summarises_a_normal_column():
    stats = annular_stats(pd.Series([10.0, 20.0, 30.0, 40.0]), threshold=0.0)
    assert stats['min'] == 10.0
    assert stats['max'] == 40.0
    assert stats['mean'] == pytest.approx(25.0)
    assert stats['std'] == pytest.approx(pd.Series([10.0, 20.0, 30.0, 40.0]).std())
    assert stats['fail_count'] == 0
    assert stats['fail_pct'] == 0.0


def test_counts_values_below_threshold_as_failures():
    stats = annular_stats(pd.Series([-5.0, -1.0, 3.0, 8.0]), threshold=0.0)
    assert stats['fail_count'] == 2
    assert stats['fail_pct'] == pytest.approx(50.0)


def test_threshold_is_exclusive_at_the_boundary():
    stats = annular_stats(pd.Series([0.0, 0.0]), threshold=0.0)
    assert stats['fail_count'] == 0


def test_worst_index_points_at_the_minimum():
    values = pd.Series([9.0, 2.0, 7.0], index=['a', 'b', 'c'])
    assert annular_stats(values, threshold=0.0)['worst_index'] == 'b'


def test_nulls_are_ignored():
    stats = annular_stats(pd.Series([np.nan, 4.0, np.nan, 6.0]), threshold=5.0)
    assert stats['min'] == 4.0
    assert stats['fail_count'] == 1
    assert stats['fail_pct'] == pytest.approx(50.0)


def test_returns_none_for_an_empty_column():
    """The caller skips the panel entirely rather than rendering blank tiles."""
    assert annular_stats(pd.Series([], dtype=float), threshold=0.0) is None
    assert annular_stats(pd.Series([np.nan, np.nan]), threshold=0.0) is None
