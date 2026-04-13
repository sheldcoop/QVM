import pytest
import pandas as pd
from unittest.mock import patch
from qvm_dashboard.src.parser import parse_qvm_content, parse_filename, QVMParseError

# Sample valid content (excerpt from user's file)
VALID_CONTENT = """
Circle: Pad_LL_2(ID:1, From 180 Pts.)
     Coord. X =        63.857203
     Coord. Y =       104.634501
     Diameter =         0.308911

Circle: Via_LL_2(ID:2, From 70 Pts.)
     Coord. X =        63.856611
     Coord. Y =       104.630820
     Diameter =         0.016742

Distance: PtV_LL_2(ID:3) between Via_LL_2(ID:2) and Pad_LL_2(ID:1)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681
"""

INVALID_CONTENT = "This is a broken file that does not contain QVM format."

def test_parse_filename():
    result = parse_filename("Post PFC_Pad to Via_Panel 20_F.txt")
    assert result['Process'] == "Post PFC"
    assert result['Panel Number'] == "20"
    assert result['Side'] == "F"

@patch('qvm_dashboard.src.parser.load_settings')
def test_parse_qvm_content_valid(mock_settings):
    mock_settings.return_value = {
        'COLUMN_NAMES': {
            'location': 'Location',
            'grid_id': 'Grid ID',
            'outer_diameter': 'Outer Diameter',
            'inner_diameter': 'Inner Diameter',
            'ptv_distance': 'PtV Distance',
            'x_distance': 'Shift (DX)',
            'y_distance': 'Shift (DY)'
        },
        'GRID_MAPPING': {'LL_2': 22}
    }

    df = parse_qvm_content(VALID_CONTENT)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1

    row = df.iloc[0]
    assert row['Location'] == 'LL_2'
    assert row['Grid ID'] == 22
    assert row['Outer Diameter'] == 0.308911
    assert row['Inner Diameter'] == 0.016742
    assert row['PtV Distance'] == 0.003728
    assert row['X Distance'] == 0.000592
    assert row['Y Distance'] == 0.003681

def test_parse_qvm_content_invalid():
    with pytest.raises(QVMParseError):
        parse_qvm_content(INVALID_CONTENT)
