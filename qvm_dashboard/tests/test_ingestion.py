from types import SimpleNamespace

from qvm_dashboard.src.ingestion import ingest_uploaded_file


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


def test_ingest_uploaded_file_applies_overrides(settings):
    uploaded = SimpleNamespace(
        name='VTP_Panel_20_F.txt',
        getvalue=lambda: VALID_CONTENT.encode('utf-8'),
    )
    df, parse_warnings, ui_warnings, resolved, filename_info = ingest_uploaded_file(
        uploaded,
        settings,
        file_override={
            'process_override': 'Via to Pad',
            'panel_override': '77',
            'side_override': 'B',
            'build_up_override': 'BU-02',
        },
        default_build_up='BU-01',
    )

    assert parse_warnings
    assert df['Process'].iloc[0] == 'Via to Pad'
    assert df['Panel'].iloc[0] == '77'
    assert df['Side'].iloc[0] == 'B'
    assert df['Build Up'].iloc[0] == 'BU-02'
    assert resolved.final_panel == '77'
    assert resolved.final_side == 'B'
    assert filename_info['Panel Number'] == '20'
    assert any('user override sets type' in msg for msg in ui_warnings)


def test_ingest_uploaded_file_keeps_filename_defaults_when_no_override(settings):
    uploaded = SimpleNamespace(
        name='PTV_Panel_20_F.txt',
        getvalue=lambda: VALID_CONTENT.encode('utf-8'),
    )
    df, parse_warnings, ui_warnings, resolved, _ = ingest_uploaded_file(
        uploaded, settings, default_build_up='BU-01')

    assert parse_warnings
    assert df['Panel'].iloc[0] == '20'
    assert df['Side'].iloc[0] == 'F'
    assert df['Build Up'].iloc[0] == 'BU-01'
    assert resolved.final_process == 'Pad to Via'
    assert not ui_warnings


def test_ingest_uploaded_file_prefers_filename_build_up_over_sidebar_default(settings):
    uploaded = SimpleNamespace(
        name='PTV_Panel_20_F_BU-03.txt',
        getvalue=lambda: VALID_CONTENT.encode('utf-8'),
    )
    df, _, _, _, filename_info = ingest_uploaded_file(
        uploaded, settings, default_build_up='BU-01')

    assert filename_info['Build Up'] == 'BU-03'
    assert df['Build Up'].iloc[0] == 'BU-03'
