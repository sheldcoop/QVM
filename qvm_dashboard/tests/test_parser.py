import pandas as pd
import pytest

from src.parser import parse_qvm_content, parse_filename, QVMParseError


def test_parse_filename_vtp_panel_side_bu():
    r = parse_filename('VTP_P28_B_BU-03.txt')
    assert r['format_hint'] == 'Via to Pad'
    assert r['Panel Number'] == '28'
    assert r['Side'] == 'B'
    assert r['Build Up'] == 'BU-03'


def test_parse_filename_ptv_panel_side():
    r = parse_filename('postpfc_ptv_panel_30_f.txt')
    assert r['format_hint'] == 'Pad to Via'
    assert r['Panel Number'] == '30'
    assert r['Side'] == 'F'


def test_invalid_content_raises():
    with pytest.raises(QVMParseError):
        parse_qvm_content('broken content')


def test_unified_parser_handles_suffix_style_via_to_pad(settings):
    # Real-world naming style: LL2_Via / LL2_Pad (suffix token), not Via_LL_2.
    content = """
Circle: LL2_Via(ID:1, From 111 Pts.)
     Coord. X =        65.658627
     Coord. Y =       104.842738
     Diameter =         0.027020

Circle: LL2_Pad(ID:2, From 95 Pts.)
     Coord. X =        65.657937
     Coord. Y =       104.839409
     Diameter =         0.395066

Distance: LL2_VtP(ID:3) between LL2_Pad(ID:2) and LL2_Via(ID:1)
           SC =         0.003400
           DX =         0.000689
           DY =         0.003329
"""
    df, _ = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert df['Process'].iloc[0] == 'Via to Pad'
    assert df.iloc[0]['Via Parameter'] == pytest.approx(0.027020)
    assert df.iloc[0]['Pad Diameter'] == pytest.approx(0.395066)
    assert df.iloc[0]['PtV Distance'] == pytest.approx(0.003400)


def test_process_detected_from_distance_marker_ptv(settings):
    content = """
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
    df, _ = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert df['Process'].iloc[0] == 'Pad to Via'


def test_coordinates_are_retained_for_vtp(settings):
    content = """
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
"""
    df, _ = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert pd.notna(df.iloc[0]['Coord. X'])
    assert pd.notna(df.iloc[0]['Coord. Y'])


def test_out_of_order_blocks_still_parse(settings):
    # Two sites intentionally not in canonical file order.
    content = """
Circle: UR2_Via(ID:31, From 148 Pts.)
     Coord. X =       308.592118
     Coord. Y =       349.247338
     Diameter =         0.027559
Circle: UR2_Pad(ID:32, From 77 Pts.)
     Coord. X =       308.592392
     Coord. Y =       349.240003
     Diameter =         0.393693
Distance: UR2_VtP(ID:33) between UR2_Pad(ID:32) and UR2_Via(ID:31)
           SC =         0.007340
           DX =        -0.000275
           DY =         0.007335

Circle: LL2_Via(ID:1, From 111 Pts.)
     Coord. X =        65.658627
     Coord. Y =       104.842738
     Diameter =         0.027020
Circle: LL2_Pad(ID:2, From 95 Pts.)
     Coord. X =        65.657937
     Coord. Y =       104.839409
     Diameter =         0.395066
Distance: LL2_VtP(ID:3) between LL2_Pad(ID:2) and LL2_Via(ID:1)
           SC =         0.003400
           DX =         0.000689
           DY =         0.003329
"""
    df, _ = parse_qvm_content(content, settings)
    assert len(df) == 2
    assert (df['Process'] == 'Via to Pad').all()
    assert df['Grid ID'].notna().any()
