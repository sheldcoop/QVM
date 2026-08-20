"""Tests for app.py's scope helpers — the panel/side filter rules and ordering."""

import pandas as pd
import pytest

from app import _apply_scope_filters, _panel_sort_key


@pytest.fixture
def scoped_df():
    return pd.DataFrame({
        'Panel': ['9', '9', '10', '10'],
        'Side':  ['F', 'B', 'F', 'B'],
        'value': [1, 2, 3, 4],
    })


def test_all_and_both_do_not_filter(scoped_df):
    assert len(_apply_scope_filters(scoped_df, 'All', 'Both')) == 4


def test_single_panel(scoped_df):
    out = _apply_scope_filters(scoped_df, '10', 'Both')
    assert out['value'].tolist() == [3, 4]


def test_single_side(scoped_df):
    out = _apply_scope_filters(scoped_df, 'All', 'F')
    assert out['value'].tolist() == [1, 3]


def test_panel_and_side_together(scoped_df):
    out = _apply_scope_filters(scoped_df, '9', 'B')
    assert out['value'].tolist() == [2]


def test_missing_columns_pass_through(scoped_df):
    bare = scoped_df.drop(columns=['Panel', 'Side'])
    assert len(_apply_scope_filters(bare, '9', 'F')) == 4


def test_result_is_a_copy(scoped_df):
    out = _apply_scope_filters(scoped_df, 'All', 'Both')
    out.loc[0, 'value'] = 999
    assert scoped_df.loc[0, 'value'] == 1


def test_panels_sort_numerically():
    """Regression: string sorting put Panel-10 ahead of Panel-9."""
    assert sorted(['9', '10', '20', '2'], key=_panel_sort_key) == ['2', '9', '10', '20']


def test_non_numeric_panels_sort_last():
    assert sorted(['10', 'Unknown', '9'], key=_panel_sort_key) == ['9', '10', 'Unknown']
