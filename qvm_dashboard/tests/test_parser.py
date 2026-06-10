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

# Two Via-to-Pad blocks, mirroring the real exporter format: Via circle first,
# then Pad circle, then Distance. Real VtP files DO carry Coord. X/Y lines — they
# are present here but intentionally discarded by the parser (the VtP views work
# from shifts), so the Coord. columns must still come out blank.
VTP_TWO_BLOCKS = """
Circle: Via_LL_2(ID:1, From 70 Pts.)
     Coord. X =        64.071816
     Coord. Y =       103.848650
     Diameter =         0.016742

Circle: Pad_LL_2(ID:2, From 180 Pts.)
     Coord. X =        64.072222
     Coord. Y =       103.848064
     Diameter =         0.308911

Distance: VtP_LL_2(ID:3) between Pad_LL_2(ID:2) and Via_LL_2(ID:1)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681

Circle: Via_LL_1(ID:4, From 70 Pts.)
     Coord. X =        63.582100
     Coord. Y =       297.836866
     Diameter =         0.0170

Circle: Pad_LL_1(ID:5, From 180 Pts.)
     Coord. X =        63.584762
     Coord. Y =       297.838808
     Diameter =         0.3050

Distance: VtP_LL_1(ID:6) between Pad_LL_1(ID:5) and Via_LL_1(ID:4)
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


# ---------------------------------------------------------------------------
# Via-to-Pad robustness: tolerate engineer omissions without derailing the file
# ---------------------------------------------------------------------------

def test_vtp_missing_pts_count_still_parses():
    """A circle with no 'From N Pts.' should still emit a row; pts come out blank."""
    content = """
Circle: Via_LL_2(ID:1)
     Diameter =         0.0167
Circle: Pad_LL_2(ID:2)
     Diameter =         0.3089
Distance: VtP_LL_2(ID:3) between Pad_LL_2(ID:2) and Via_LL_2(ID:1)
           SC =         0.0037
           DX =         0.0006
           DY =         0.0037
"""
    df = parse_qvm_content(content, _MOCK_SETTINGS)
    assert len(df) == 1
    assert df.iloc[0]['Process'] == 'Via to Pad'
    assert pd.isna(df.iloc[0]['Via Pts.'])
    assert pd.isna(df.iloc[0]['Pad Pts.'])
    assert df.iloc[0]['PtV Distance'] == pytest.approx(0.0037)


def test_vtp_missing_location_suffix_still_parses():
    """Bare 'Circle: Via(...)' and 'Distance: VtP(...)' (no _LL_2) must still parse;
    values are read by label and the Grid ID still comes from block position."""
    content = """
Circle: Via(ID:1, From 65 Pts.)
     Diameter =         0.0332
Circle: Pad(ID:2, From 58 Pts.)
     Diameter =         0.3680
Distance: VtP(ID:3) between Pad(ID:2) and Via(ID:1)
           SC =         0.0007
           DX =        -0.0004
           DY =         0.0005
"""
    df = parse_qvm_content(content, _MOCK_SETTINGS)
    assert len(df) == 1
    row = df.iloc[0]
    assert row['Location'] == ''           # suffix absent → blank, not garbage
    assert row['Grid ID'] == 22            # still assigned by POSITIONAL_MAPPING[0]
    assert row['PtV Distance'] == pytest.approx(0.0007)
    assert row['X Distance'] == pytest.approx(-0.0004)


# ---------------------------------------------------------------------------
# Value-by-position parsing: identity and ownership come from ORDER, never from
# the Circle/Distance/location headers (the back-side exporter drops those).
# ---------------------------------------------------------------------------

# Like _MOCK_SETTINGS but with GRID_MAPPING, so the location name is derived from
# the positional Grid ID (Grid 22 → 'LL_2') with no dependence on file labels.
_MOCK_SETTINGS_WITH_GRID = {
    'COLUMN_NAMES': _MOCK_SETTINGS['COLUMN_NAMES'],
    'POSITIONAL_MAPPING': ['22', '21'],   # site 0 → 22 (LL_2), site 1 → 21 (LL_1)
    'GRID_MAPPING': {
        'UL_1': 11, 'UL_2': 12, 'LL_1': 21, 'LL_2': 22, 'LL_3': 23,
        'LR_1': 31, 'UR_1': 41,
    },
}

# Back-side exporter style: the 'Circle: Pad' header and the 'Distance:' header
# are GONE for site 0 (only the Via header survives), and site 1 has NO header at
# all — yet every value is present, in order. A by-position parser must still get
# both sites right.
VTP_HEADERS_STRIPPED = """
Circle: Via_LL_2(ID:1, From 105 Pts.)
     Coord. X =        64.064752
     Coord. Y =       103.555498
     Diameter =         0.034249
     Coord. X =        64.066150
     Coord. Y =       103.554815
     Diameter =         0.361774
           SC =         0.001556
           DX =        -0.001398
           DY =         0.000683

     Coord. X =        63.619628
     Coord. Y =       297.545339
     Diameter =         0.033642
     Coord. X =        63.621626
     Coord. Y =       297.548817
     Diameter =         0.358952
           SC =         0.004011
           DX =        -0.001998
           DY =        -0.003478
"""


def test_value_ownership_is_by_position():
    """1st diameter → Via (inner), 2nd diameter → Pad (outer); SC/DX/DY → shift —
    decided purely by order, with the headers present."""
    df = parse_qvm_content(VTP_TWO_BLOCKS, _MOCK_SETTINGS_WITH_GRID)
    assert len(df) == 2
    r = df.iloc[0]
    assert r['Inner Diameter'] == pytest.approx(0.016742)   # 1st diameter = via
    assert r['Outer Diameter'] == pytest.approx(0.308911)   # 2nd diameter = pad
    assert r['PtV Distance'] == pytest.approx(0.003728)


def test_grid_and_location_come_from_block_position():
    """Grid ID is assigned by block order via POSITIONAL_MAPPING, and Location is
    derived from that (Grid 22 → 'LL_2') — not read from the file's labels."""
    df = parse_qvm_content(VTP_TWO_BLOCKS, _MOCK_SETTINGS_WITH_GRID)
    assert df['Grid ID'].tolist() == [22, 21]
    assert df['Location'].tolist() == ['LL_2', 'LL_1']


def test_parses_when_pad_and_distance_headers_are_stripped():
    """The crux: with the Pad/Distance headers removed (and one site fully
    header-less), the values still parse by position into correct sites."""
    df = parse_qvm_content(VTP_HEADERS_STRIPPED, _MOCK_SETTINGS_WITH_GRID)
    assert len(df) == 2
    assert (df['Process'] == 'Via to Pad').all()
    # Identity still correct, taken from block position.
    assert df['Grid ID'].tolist() == [22, 21]
    assert df['Location'].tolist() == ['LL_2', 'LL_1']
    # Ownership still correct: 1st diameter → via, 2nd → pad.
    assert df.iloc[0]['Inner Diameter'] == pytest.approx(0.034249)
    assert df.iloc[0]['Outer Diameter'] == pytest.approx(0.361774)
    assert df.iloc[1]['Inner Diameter'] == pytest.approx(0.033642)
    assert df.iloc[1]['Outer Diameter'] == pytest.approx(0.358952)
    # Shifts mapped to the right site in order.
    assert df['PtV Distance'].tolist() == pytest.approx([0.001556, 0.004011])
    # Point counts are best-effort from whatever Circle headers survived: site 0
    # kept its Via header (105 pts); site 1 had none.
    assert df.iloc[0]['Via Pts.'] == 105
    assert pd.isna(df.iloc[1]['Via Pts.'])
