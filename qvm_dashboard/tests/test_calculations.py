import pytest
import pandas as pd
from qvm_dashboard.src.calculations import calculate_annular_ring, calculate_cam_compensation

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

def test_calculate_cam_compensation():
    df = pd.DataFrame({
        'X Distance': [0.01, -0.02, 0.04],  # sum = 0.03, avg = 0.01
        'Y Distance': [0.05, 0.05, -0.01]   # sum = 0.09, avg = 0.03
    })

    settings = {
        'COLUMN_NAMES': {
            'x_distance': 'Shift (DX)',
            'y_distance': 'Shift (DY)'
        }
    }

    avg_x, avg_y = calculate_cam_compensation(df, settings)

    assert avg_x == pytest.approx(0.01, abs=1e-5)
    assert avg_y == pytest.approx(0.03, abs=1e-5)
