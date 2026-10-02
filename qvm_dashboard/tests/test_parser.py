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


def test_sc_is_overridden_when_mismatch_is_large(settings):
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
           SC =         0.500000
           DX =         0.001000
           DY =         0.002000
"""
    df, warnings = parse_qvm_content(content, settings)

    assert len(df) == 1
    assert df.iloc[0]['PtV Distance'] == pytest.approx((0.001 ** 2 + 0.002 ** 2) ** 0.5)
    assert any('Using calculated SC' in w for w in warnings)


def test_sc_is_not_overridden_when_mismatch_is_small(settings):
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
           SC =         0.002250
           DX =         0.001000
           DY =         0.002000
"""
    df, warnings = parse_qvm_content(content, settings)

    assert len(df) == 1
    assert df.iloc[0]['PtV Distance'] == pytest.approx(0.002250)
    assert not any('Using calculated SC' in w for w in warnings)


def test_sc_missing_is_filled_from_dx_dy(settings):
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
           DX =         0.001000
           DY =         0.002000
"""
    df, warnings = parse_qvm_content(content, settings)

    assert len(df) == 1
    assert df.iloc[0]['PtV Distance'] == pytest.approx((0.001 ** 2 + 0.002 ** 2) ** 0.5)
    assert any('SC missing in source' in w for w in warnings)


# A single complete, self-consistent site block (SC matches DX/DY, so no
# SC warnings pollute truncation assertions). Truncation variants below are
# derived from it by dropping the DY terminator line.
_TRUNCATION_SITE_BLOCK = """
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


def _without_dy(block: str) -> str:
    return '\n'.join(
        line for line in block.splitlines()
        if not line.strip().startswith('DY')
    )


def test_truncated_single_block_error_mentions_truncation(settings):
    with pytest.raises(QVMParseError) as excinfo:
        parse_qvm_content(_without_dy(_TRUNCATION_SITE_BLOCK), settings)
    message = str(excinfo.value)
    assert 'No valid measurement blocks' in message
    assert 'truncat' in message.lower()


def test_mid_file_cut_warns_and_keeps_complete_sites(settings):
    content = _TRUNCATION_SITE_BLOCK + _without_dy(_TRUNCATION_SITE_BLOCK)
    df, warnings = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert any('truncat' in w.lower() for w in warnings)


def test_complete_file_has_no_truncation_warning(settings):
    content = _TRUNCATION_SITE_BLOCK + _TRUNCATION_SITE_BLOCK
    df, warnings = parse_qvm_content(content, settings)
    assert len(df) == 2
    assert not any('truncat' in w.lower() for w in warnings)


def test_trailing_noise_has_no_truncation_warning(settings):
    content = _TRUNCATION_SITE_BLOCK + '\nrandom trailing noise\n'
    df, warnings = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert not any('truncat' in w.lower() for w in warnings)


def _with_replaced_line(block: str, prefix: str, replacement: str) -> str:
    lines = []
    for line in block.splitlines():
        if line.strip().startswith(prefix):
            indent = line[:len(line) - len(line.lstrip())]
            lines.append(f"{indent}{replacement}")
        else:
            lines.append(line)
    return '\n'.join(lines)


def test_nan_sc_is_recomputed_and_flagged(settings):
    content = _with_replaced_line(_TRUNCATION_SITE_BLOCK, 'SC', 'SC = nan')
    df, warnings = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert df.iloc[0]['PtV Distance'] == pytest.approx((0.000592 ** 2 + 0.003681 ** 2) ** 0.5)
    assert any('SC' in w and 'not finite' in w for w in warnings)


def test_inf_dx_is_treated_as_missing_and_flagged(settings):
    content = _with_replaced_line(_TRUNCATION_SITE_BLOCK, 'DX', 'DX = inf')
    df, warnings = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert pd.isna(df.iloc[0]['Shift (DX)'])
    assert any('DX' in w and 'not finite' in w for w in warnings)


def test_nan_coord_is_treated_as_missing_and_flagged(settings):
    content = _with_replaced_line(
        _TRUNCATION_SITE_BLOCK, 'Coord. X', 'Coord. X = nan')
    df, warnings = parse_qvm_content(content, settings)
    assert len(df) == 1
    assert any('Coord' in w and 'not finite' in w for w in warnings)


def test_finite_values_gain_no_data_quality_warning(settings):
    df, warnings = parse_qvm_content(_TRUNCATION_SITE_BLOCK, settings)
    assert len(df) == 1
    assert not any('not finite' in w for w in warnings)


def _site_block(via_name, pad_name, distance_name, x, y):
    return f"""
Circle: {via_name}(ID:1, From 70 Pts.)
     Coord. X =        {x:.6f}
     Coord. Y =        {y:.6f}
     Diameter =         0.016742

Circle: {pad_name}(ID:2, From 180 Pts.)
     Coord. X =        {x + 0.001:.6f}
     Coord. Y =        {y - 0.002:.6f}
     Diameter =         0.308911

Distance: {distance_name}(ID:3) between {pad_name}(ID:2) and {via_name}(ID:1)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681
"""


def _names():
    return [f'{q}{n}' for q in ('LL', 'UL', 'LR', 'UR') for n in (2, 1, 4, 3)]


def test_names_like_LL2_Via_are_read_and_positions_still_decide(settings):
    """Real layout: sites named 'LL2_Via', measured in panel coordinates."""
    position = {'LL': (65.0, 105.0), 'UL': (65.0, 349.0), 'LR': (309.0, 105.0), 'UR': (309.0, 349.0)}
    offset = {1: (0.0, 194.0), 2: (0.0, 0.0), 3: (230.7, 0.0), 4: (230.7, 194.0)}
    content = ''.join(
        _site_block(f'{name}_Via', f'{name}_Pad', f'{name}_VtP',
                    position[name[:2]][0] + offset[int(name[2])][0],
                    position[name[:2]][1] + offset[int(name[2])][1])
        for name in _names())
    df, warnings = parse_qvm_content(content, settings)
    assert list(df['Location']) == [f'{n[:2]}_{n[2]}' for n in _names()]
    assert df['Grid ID'].notna().all() and warnings == []


def test_site_local_positions_use_the_names_in_the_file(settings):
    """Every site exported in its own local frame: positions are all about zero,
    so names come from the labels and nothing is derived from micron noise."""
    content = ''.join(
        _site_block(f'{name}_Via', f'{name}_Pad', f'{name}_VtP', 0.0001 * i, -0.0002 * i)
        for i, name in enumerate(_names()))
    df, warnings = parse_qvm_content(content, settings)
    assert list(df['Location']) == [f'{n[:2]}_{n[2]}' for n in _names()]
    assert df['Grid ID'].tolist() == [int(settings['GRID_MAPPING'][loc]) for loc in df['Location']]
    assert len(warnings) == 1 and 'taken from the labels in the file' in warnings[0]


def test_site_local_positions_without_usable_names_follow_the_defined_order(settings):
    """Real case: labels 'Via[1,1][1,2]' and positions all about zero. The sites are
    then taken to be in the POSITIONAL_MAPPING order."""
    labels = [f'[{a},{b}][{c},{d}]' for a in (1, 2) for b in (1, 2) for c in (1, 2) for d in (1, 2)]
    content = ''.join(
        _site_block(f'Via{label}', f'Pad{label}', f'VtP{label}', 0.0001 * i, -0.0002 * i)
        for i, label in enumerate(labels))
    df, warnings = parse_qvm_content(content, settings)
    assert list(df['Location']) == [
        'LL_2', 'LL_1', 'LL_3', 'LL_4', 'UL_2', 'UL_1', 'UL_3', 'UL_4',
        'LR_2', 'LR_1', 'LR_3', 'LR_4', 'UR_2', 'UR_1', 'UR_3', 'UR_4']
    assert df['Grid ID'].tolist() == [int(g) for g in settings['POSITIONAL_MAPPING']]
    assert df['Shift (DX)'].notna().all()  # the registration values are untouched
    assert len(warnings) == 1
    assert 'assigned from the measurement order defined in POSITIONAL_MAPPING' in warnings[0]
    assert 'correct only if this file follows that order' in warnings[0]

    # More sites than the defined order: the extra ones are not guessed.
    extra = content + _site_block('Via[3,1][1,1]', 'Pad[3,1][1,1]', 'VtP[3,1][1,1]', 0.0, 0.0)
    more, more_warnings = parse_qvm_content(extra, settings)
    assert pd.isna(more['Grid ID'].iloc[-1]) and more['Location'].iloc[-1] == '[3,1][1,1]'
    assert '1 site(s) beyond that order have no Grid ID' in more_warnings[0]


def test_box_plot_draws_when_a_site_has_no_grid_id(settings):
    from src.visuals import plot_vtp_box

    labels = [f'[{a},{b}][{c},{d}]' for a in (1, 2) for b in (1, 2) for c in (1, 2) for d in (1, 2)]
    content = ''.join(
        _site_block(f'Via{label}', f'Pad{label}', f'VtP{label}', 0.0001 * i, -0.0002 * i)
        for i, label in enumerate(labels))
    content += _site_block('Via[3,1][1,1]', 'Pad[3,1][1,1]', 'VtP[3,1][1,1]', 0.0, 0.0)
    df, _ = parse_qvm_content(content, settings)
    assert len(plot_vtp_box(df, settings).data) > 0


def _numbered_block(name, first_id, x, y, dx):
    """One site with file-unique IDs, split into its circle part and distance part."""
    via, pad, dist = first_id, first_id + 1, first_id + 2
    circles = f"""
Circle: Via_{name}(ID:{via}, From 70 Pts.)
     Coord. X =        {x:.6f}
     Coord. Y =        {y:.6f}
     Diameter =         0.016742

Circle: Pad_{name}(ID:{pad}, From 180 Pts.)
     Coord. X =        {x + 0.001:.6f}
     Coord. Y =        {y - 0.002:.6f}
     Diameter =         0.308911
"""
    distance = f"""
Distance: VtP_{name}(ID:{dist}) between Pad_{name}(ID:{pad}) and Via_{name}(ID:{via})
           SC =         {abs(dx):.6f}
           DX =         {dx:.6f}
           DY =         0.000000
"""
    return circles, distance


def _panel_xy(name):
    quadrant = {'LL': (65.0, 105.0), 'UL': (65.0, 349.0), 'LR': (309.0, 105.0), 'UR': (309.0, 349.0)}
    corner = {'1': (0.0, 194.0), '2': (0.0, 0.0), '3': (232.5, 0.0), '4': (232.5, 194.0)}
    return (quadrant[name[:2]][0] + corner[name[3]][0], quadrant[name[:2]][1] + corner[name[3]][1])


def test_distance_blocks_written_out_of_order_keep_their_own_circles(settings):
    """Real case: the circles of UR_3 and UR_4 come first, then the distance of
    UR_4, then that of UR_3. Each distance names its circles by ID."""
    names = [f'{q}_{n}' for q in ('LL', 'UL', 'LR', 'UR') for n in (2, 1, 3, 4)]
    parts = {name: _numbered_block(name, 1 + 3 * i, *_panel_xy(name), dx=0.001 * (i + 1))
             for i, name in enumerate(names)}
    content = ''.join(parts[n][0] + parts[n][1] for n in names[:-2])
    content += parts['UR_3'][0] + parts['UR_4'][0] + parts['UR_4'][1] + parts['UR_3'][1]

    df, warnings = parse_qvm_content(content, settings)
    assert warnings == [] and len(df) == 16 and df['Grid ID'].notna().all()
    by_location = df.set_index('Location')
    for i, name in enumerate(names):  # DX stayed with the site it was measured on
        assert by_location.loc[name, 'Shift (DX)'] == pytest.approx(0.001 * (i + 1))
        assert by_location.loc[name, 'Coord. X'] == pytest.approx(_panel_xy(name)[0])


def test_a_missing_site_does_not_move_the_panel_centre(settings):
    """15 of 16 sites: the centre must still lie between the quadrants, not on a site."""
    names = [f'{q}_{n}' for q in ('LL', 'UL', 'LR', 'UR') for n in (2, 1, 3, 4)][:-1]
    content = ''.join(''.join(_numbered_block(name, 1 + 3 * i, *_panel_xy(name), dx=0.001))
                      for i, name in enumerate(names))
    df, warnings = parse_qvm_content(content, settings)
    assert list(df['Location']) == names and warnings == []
