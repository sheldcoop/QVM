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

def test_parse_filename_legacy_long_form():
    result = parse_filename("Post PFC_Pad to Via_Panel 20_F.txt")
    assert result['format_hint'] == "Pad to Via"
    assert result['Panel Number'] == "20"
    assert result['Side'] == "F"


def test_parse_filename_vtp_shorthand():
    result = parse_filename("VTP_Panel 25_F.txt")
    assert result['format_hint'] == "Via to Pad"
    assert result['Panel Number'] == "25"
    assert result['Side'] == "F"


def test_parse_filename_lowercase_ptv():
    result = parse_filename("postpfc_ptv_panel_30_b.txt")
    assert result['format_hint'] == "Pad to Via"
    assert result['Panel Number'] == "30"
    assert result['Side'] == "B"


def test_parse_filename_mixed_case_vtp():
    result = parse_filename("VtP_Panel25_f.txt")
    assert result['format_hint'] == "Via to Pad"
    assert result['Panel Number'] == "25"
    assert result['Side'] == "F"


def test_parse_filename_no_hint():
    result = parse_filename("random_data.txt")
    assert result['format_hint'] is None

@patch('qvm_dashboard.src.parser.load_settings')
def test_parse_qvm_content_valid(mock_settings):
    mock_settings.return_value = {
        'COLUMN_NAMES': {
            'location': 'Location',
            'grid_id': 'Grid ID',
            'outer_diameter': 'Outer Diameter',
            'inner_diameter': 'Inner Diameter',
            'ptv_distance': 'PtV Distance',
            'x_distance': 'X Distance',
            'y_distance': 'Y Distance',
        },
        # Grid ID is assigned by block index against POSITIONAL_MAPPING — the
        # first (and only) block in VALID_CONTENT will be tagged 22.
        'POSITIONAL_MAPPING': ['22'],
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
    # Content-driven routing tag: Pad circle appears first → Pad-to-Via.
    assert row['Process'] == 'Pad to Via'

def test_parse_qvm_content_invalid():
    with pytest.raises(QVMParseError):
        parse_qvm_content(INVALID_CONTENT)


# ---------------------------------------------------------------------------
# Per-format multi-block parser tests
# ---------------------------------------------------------------------------

# Two Pad-to-Via blocks back-to-back. Pad circle appears BEFORE the Via circle
# in each block, so content sniffing should route to _parse_pad_to_via.
PTV_TWO_BLOCKS = """
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

Circle: Pad_LL_1(ID:4, From 180 Pts.)
     Coord. X =        63.10
     Coord. Y =       104.10
     Diameter =         0.305

Circle: Via_LL_1(ID:5, From 70 Pts.)
     Coord. X =        63.11
     Coord. Y =       104.12
     Diameter =         0.017

Distance: PtV_LL_1(ID:6) between Via_LL_1(ID:5) and Pad_LL_1(ID:4)
           SC =         0.0021
           DX =         0.0010
           DY =         0.0018
"""

# Two Via-to-Pad blocks. Via circle appears BEFORE the Pad circle in each
# block (no Coord. lines for these — VtP files carry only diameters + shifts).
VTP_TWO_BLOCKS = """
Circle: Via_LL_2(ID:1, From 70 Pts.)
     Diameter =         0.016742

Circle: Pad_LL_2(ID:2, From 180 Pts.)
     Diameter =         0.308911

Distance: PtV_LL_2(ID:3) between Via_LL_2(ID:1) and Pad_LL_2(ID:2)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681

Circle: Via_LL_1(ID:4, From 70 Pts.)
     Diameter =         0.0170

Circle: Pad_LL_1(ID:5, From 180 Pts.)
     Diameter =         0.3050

Distance: PtV_LL_1(ID:6) between Via_LL_1(ID:4) and Pad_LL_1(ID:5)
           SC =         0.0021
           DX =         0.0010
           DY =         0.0018
"""

_MOCK_SETTINGS = {
    'COLUMN_NAMES': {
        'location': 'Location',
        'grid_id': 'Grid ID',
        'outer_diameter': 'Outer Diameter',
        'inner_diameter': 'Inner Diameter',
        'ptv_distance': 'PtV Distance',
        'x_distance': 'X Distance',
        'y_distance': 'Y Distance',
        'total_shift': 'SC',
        'pad_pts': 'Pad Pts.',
        'via_pts': 'Via Pts.',
    },
    'POSITIONAL_MAPPING': ['22', '21'],
}


def test_pad_to_via_multi_block():
    df = parse_qvm_content(PTV_TWO_BLOCKS, _MOCK_SETTINGS)
    assert len(df) == 2
    # Each row is tagged as Pad to Via via content sniffing.
    assert (df['Process'] == 'Pad to Via').all()
    # POSITIONAL_MAPPING governs Grid IDs by block order.
    assert df['Grid ID'].tolist() == [22, 21]
    # Spot-check that the block-1 measurements survived parsing in mm.
    assert df.iloc[1]['DX' if 'DX' in df.columns else 'X Distance'] == pytest.approx(0.0010)


def test_via_to_pad_multi_block():
    df = parse_qvm_content(VTP_TWO_BLOCKS, _MOCK_SETTINGS)
    assert len(df) == 2
    assert (df['Process'] == 'Via to Pad').all()
    assert df['Grid ID'].tolist() == [22, 21]
    # Via-to-Pad files carry no absolute coordinates — those columns must be empty.
    assert pd.isna(df.iloc[0]['Coord. X'])
    assert pd.isna(df.iloc[0]['Coord. Y'])


def test_content_sniffing_tags_process_correctly():
    """Filename-agnostic routing: the parser tags Process from content order."""
    ptv = parse_qvm_content(PTV_TWO_BLOCKS, _MOCK_SETTINGS)
    vtp = parse_qvm_content(VTP_TWO_BLOCKS, _MOCK_SETTINGS)
    assert ptv['Process'].iloc[0] == 'Pad to Via'
    assert vtp['Process'].iloc[0] == 'Via to Pad'


# ---------------------------------------------------------------------------
# Error-handling tests for the hardened parser
# ---------------------------------------------------------------------------

def test_malformed_measurement_line_raises_qvm_error():
    """A 'Diameter' line without '=' should produce a clear QVMParseError, not IndexError."""
    bad_content = """
Circle: Pad_LL_2(ID:1, From 180 Pts.)
     Coord. X =        63.85
     Coord. Y =       104.63
     Diameter without equals sign
"""
    with pytest.raises(QVMParseError):
        parse_qvm_content(bad_content, _MOCK_SETTINGS)
