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


def test_secondary_column_is_selectable(scoped_df):
    """Core Shrinkage filters on 'layer' (Front/Back) rather than 'Side', so the
    same helper has to take the column name."""
    cs = pd.DataFrame({
        'Panel': ['28', '28', '29', '29'],
        'layer': ['Front', 'Back', 'Front', 'Back'],
        'value': [1, 2, 3, 4],
    })
    out = _apply_scope_filters(cs, 'All', 'Front', filter_col='layer')
    assert out['value'].tolist() == [1, 3]

    out = _apply_scope_filters(cs, '28', 'Back', filter_col='layer')
    assert out['value'].tolist() == [2]

    assert len(_apply_scope_filters(cs, 'All', 'Both', filter_col='layer')) == 4


def test_side_remains_the_default_column(scoped_df):
    """Pad-to-Via / Via-to-Pad call sites pass no filter_col and must be unaffected."""
    assert _apply_scope_filters(scoped_df, 'All', 'F')['value'].tolist() == [1, 3]


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


def test_panel_sort_survives_anything_typed_into_the_override():
    """Panel Number is free text. "²" is isdigit() but not int()-able, so
    guarding on isdigit() would raise here instead of sorting."""
    for odd in ('²', '', ' ', '12a', '-3', 'Panel 4'):
        assert _panel_sort_key(odd)[0] == 1, f'{odd!r} should sort as non-numeric'
    # Unicode decimal digits are int()-able and should still sort numerically.
    assert _panel_sort_key('٢') == (0, 2, '')
