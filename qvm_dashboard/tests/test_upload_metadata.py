from src.upload_metadata import UploadMetadata, resolve_override_value, resolve_upload_metadata
from src.views.quality_control import QualityControlView


def test_resolve_override_value_prefers_override():
    assert resolve_override_value('30', '20') == '30'


def test_resolve_override_value_falls_back_to_parsed():
    assert resolve_override_value(None, '20') == '20'


def test_resolve_upload_metadata_precedence():
    filename_info = {
        'Panel Number': '20',
        'Side': 'F',
    }
    resolved = resolve_upload_metadata(
        filename_info,
        detected_process='Pad to Via',
        override={
            'process_override': 'Via to Pad',
            'panel_override': '77',
            'side_override': 'B',
        },
    )

    assert isinstance(resolved, UploadMetadata)
    assert resolved.final_process == 'Via to Pad'
    assert resolved.final_panel == '77'
    assert resolved.final_side == 'B'


def test_resolve_upload_metadata_uses_detected_when_no_override():
    filename_info = {
        'Panel Number': '20',
        'Side': 'F',
    }
    resolved = resolve_upload_metadata(filename_info, detected_process='Pad to Via', override={})

    assert resolved.final_process == 'Pad to Via'
    assert resolved.final_panel == '20'
    assert resolved.final_side == 'F'


def test_build_filename_uses_data_and_optional_meta():
    import pandas as pd

    df = pd.DataFrame({
        'Process': ['Via to Pad', 'Via to Pad'],
        'Panel': ['25', '25'],
        'Side': ['B', 'B'],
    })
    meta = {
        'build_up': 'BU-2',
        'lot_number': 'L123',
    }

    file_name = QualityControlView._build_filename(df, is_via_to_pad=False, meta=meta)

    assert file_name == 'QVM_VTP_P25_B_BU-2_Lot-L123.xlsx'


def test_build_filename_handles_mixed_data_tokens():
    import pandas as pd

    df = pd.DataFrame({
        'Process': ['Via to Pad', 'Pad to Via'],
        'Panel': ['20', '21'],
        'Side': ['F', 'B'],
    })

    file_name = QualityControlView._build_filename(df, is_via_to_pad=False, meta={})

    assert file_name == 'QVM_MIXED_PMulti_FB.xlsx'


def test_build_filename_uses_build_up_from_dataframe_when_available():
    import pandas as pd

    df = pd.DataFrame({
        'Process': ['Pad to Via'],
        'Panel': ['20'],
        'Side': ['F'],
        'Build Up': ['BU-03'],
    })

    file_name = QualityControlView._build_filename(
        df, is_via_to_pad=False, meta={'build_up': 'BU-01', 'lot_number': 'L9'})

    assert file_name == 'QVM_PTV_P20_F_BU-03_Lot-L9.xlsx'


def test_build_filename_uses_bumulti_for_mixed_build_up_data():
    import pandas as pd

    df = pd.DataFrame({
        'Process': ['Pad to Via', 'Pad to Via'],
        'Panel': ['20', '20'],
        'Side': ['F', 'F'],
        'Build Up': ['BU-01', 'BU-02'],
    })

    file_name = QualityControlView._build_filename(df, is_via_to_pad=False, meta={})

    assert file_name == 'QVM_PTV_P20_F_BUMulti.xlsx'
