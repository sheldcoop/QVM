"""Tests for src/display_frame.py — the single builder behind the on-screen
Quality Control table and every Excel measurement sheet."""

import numpy as np
import pandas as pd
import pytest

from src.display_frame import build_display_frame


@pytest.fixture
def parsed_df(settings):
    """A frame shaped like parser output: measurements in mm, one distance column."""
    cn = settings['COLUMN_NAMES']
    n = 4
    return pd.DataFrame({
        cn['grid_id']:        [22, 11, 44, 13],
        cn['location']:       ['LL_2', 'UL_1', 'UR_4', 'UL_3'],
        cn['inner_diameter']: np.full(n, 0.0200),
        cn['outer_diameter']: np.full(n, 0.3125),
        cn['x_distance']:     np.full(n, 0.0010),
        cn['y_distance']:     np.full(n, -0.0020),
        cn['ptv_distance']:   np.full(n, 0.0050),
        cn['coord_x']:        np.linspace(50, 450, n),
        cn['coord_y']:        np.linspace(50, 450, n),
        'Build Up':           ['BU-01'] * n,
        'Panel':              ['20'] * n,
        'Side':               ['F'] * n,
    })


def test_annular_ring_is_present(parsed_df, settings):
    """Regression: the Quality Control statistics panel and the fail-row
    highlighting both key on this column. When it was dropped here, the panel
    silently rendered empty and no failing row was ever coloured."""
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    assert settings['COLUMN_NAMES']['annular_ring'] in out.columns


def test_annular_ring_is_computed_when_absent(parsed_df, settings):
    cn = settings['COLUMN_NAMES']
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    # (pad/2 - via/2 - distance) in mm, then ×1000 for display:
    # (0.3125/2 - 0.0200/2 - 0.0050) * 1000 = 141.25 µm
    assert out[cn['annular_ring']].iloc[0] == pytest.approx(141.25)


def test_distance_header_is_process_specific(parsed_df, settings):
    """The parser stores one distance value; the header naming it is the only
    thing that differs between processes, and it is applied only here."""
    cn = settings['COLUMN_NAMES']
    ptv = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    vtp = build_display_frame(parsed_df, settings, is_via_to_pad=True)

    assert cn['ptv_distance'] in ptv.columns
    assert cn['total_shift'] not in ptv.columns
    assert cn['total_shift'] in vtp.columns
    assert cn['ptv_distance'] not in vtp.columns
    # Same underlying numbers, only the label changes.
    assert vtp[cn['total_shift']].tolist() == ptv[cn['ptv_distance']].tolist()


def test_measurements_are_converted_to_microns(parsed_df, settings):
    cn = settings['COLUMN_NAMES']
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    assert out[cn['outer_diameter']].iloc[0] == pytest.approx(312.5)
    assert out[cn['inner_diameter']].iloc[0] == pytest.approx(20.0)
    assert out[cn['ptv_distance']].iloc[0] == pytest.approx(5.0)
    assert out[cn['x_distance']].iloc[0] == pytest.approx(1.0)
    assert out[cn['y_distance']].iloc[0] == pytest.approx(-2.0)


def test_rows_are_sorted_numerically_by_grid_id(parsed_df, settings):
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    assert out[settings['COLUMN_NAMES']['grid_id']].tolist() == [11, 13, 22, 44]


def test_malformed_grid_id_sorts_last_without_reordering_the_rest(parsed_df, settings):
    cn = settings['COLUMN_NAMES']
    parsed_df.loc[0, cn['grid_id']] = None
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    assert out[cn['grid_id']].tolist()[:3] == [11, 13, 44]
    assert pd.isna(out[cn['grid_id']].tolist()[3])


def test_noise_columns_are_excluded(parsed_df, settings):
    """Coord. X/Y, Location and the Process tag stay out of the table."""
    cn = settings['COLUMN_NAMES']
    parsed_df['Process'] = 'Pad to Via'
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    for absent in (cn['coord_x'], cn['coord_y'], cn['location'], 'Process'):
        assert absent not in out.columns


def test_provenance_columns_come_first(parsed_df, settings):
    out = build_display_frame(parsed_df, settings, is_via_to_pad=False)
    assert out.columns.tolist()[:3] == ['Build Up', 'Panel', 'Side']


def test_input_frame_is_not_mutated(parsed_df, settings):
    before = parsed_df.copy(deep=True)
    build_display_frame(parsed_df, settings, is_via_to_pad=True)
    pd.testing.assert_frame_equal(parsed_df, before)


def test_missing_optional_columns_are_tolerated(parsed_df, settings):
    """Frames scoped down by the UI may lack provenance columns entirely."""
    out = build_display_frame(
        parsed_df.drop(columns=['Build Up', 'Panel', 'Side']),
        settings, is_via_to_pad=False)
    assert 'Build Up' not in out.columns
    assert settings['COLUMN_NAMES']['grid_id'] in out.columns
