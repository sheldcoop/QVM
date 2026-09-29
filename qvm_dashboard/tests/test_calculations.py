import pytest
import pandas as pd
from src.utils import calculate_annular_ring, convert_to_microns


def test_calculate_annular_ring():
    df = pd.DataFrame({
        'Outer Diameter': [0.300],
        'Inner Diameter': [0.010],
        'PtV Distance': [0.005]
    })

    settings = {
        'COLUMN_NAMES': {
            'outer_diameter': 'Outer Diameter',
            'inner_diameter': 'Inner Diameter',
            'ptv_distance': 'PtV Distance',
            'annular_ring': 'Annular Ring'
        }
    }

    result_df = calculate_annular_ring(df, settings)

    # Formula: (0.300 / 2) - (0.010 / 2) - 0.005 = 0.150 - 0.005 - 0.005 = 0.140
    assert 'Annular Ring' in result_df.columns
    assert result_df['Annular Ring'].iloc[0] == pytest.approx(0.140, abs=1e-5)


def test_calc_helpers_do_not_mutate_input():
    """Regression: calc helpers are pure — the caller's frame must be unchanged."""
    df = pd.DataFrame({
        'Outer Diameter': [0.300],
        'Inner Diameter': [0.010],
        'PtV Distance': [0.005],
    })
    settings = {
        'COLUMN_NAMES': {
            'outer_diameter': 'Outer Diameter',
            'inner_diameter': 'Inner Diameter',
            'ptv_distance': 'PtV Distance',
            'annular_ring': 'Annular Ring',
        }
    }
    before = df.copy(deep=True)

    calculate_annular_ring(df, settings)
    pd.testing.assert_frame_equal(df, before)

    convert_to_microns(df, ['Outer Diameter', 'PtV Distance'])
    pd.testing.assert_frame_equal(df, before)
