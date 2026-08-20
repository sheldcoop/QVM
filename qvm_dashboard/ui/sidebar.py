"""
Sidebar UI Module - Configuration and file upload controls.

Centralizes all sidebar logic for cleaner app.py.
"""

import streamlit as st
from typing import Dict, List, Optional
from src.parser import parse_filename

# Selectbox label → the value stored on the override. The first entry of each
# map is the "Auto" choice, which leaves the parsed value in charge.
_PROCESS_CHOICES: Dict[str, Optional[str]] = {
    "Auto (content-detected)": None,
    "Pad to Via (PTV)": "Pad to Via",
    "Via to Pad (VTP)": "Via to Pad",
}
_SIDE_CHOICES: Dict[str, Optional[str]] = {
    "Auto (from filename)": None,
    "Front (F)": "F",
    "Back (B)": "B",
}


def _render_uploader() -> List:
    """File uploader plus its naming hint. Returns the uploaded file objects."""
    uploaded_files = st.file_uploader(
        "Upload QVM Text Files",
        type=['txt'],
        accept_multiple_files=True
    )
    st.caption(
        "Recommended filename: `PTV_P20_F_BU-01.txt` or `VTP_P20_B_BU-02.txt` "
        "(PROCESS_PANEL_SIDE_BU). If naming is imperfect, use Optional Per-File Overrides below."
    )
    return uploaded_files


def _render_file_overrides(uploaded_files: List) -> List[Dict]:
    """Per-file metadata overrides. Returns one override dict per uploaded file.

    Blank text and the "Auto" selectbox entries resolve to ``None``, which
    leaves the filename-parsed value in charge (see
    ``src.upload_metadata.resolve_upload_metadata`` for the precedence rules).
    """
    if not uploaded_files:
        return []

    file_overrides = []
    with st.expander("Optional Per-File Overrides", expanded=False):
        st.caption(
            "Leave values on Auto/blank to keep current behavior. "
            "Set values only when you want to override file naming metadata."
        )
        for idx, uploaded_file in enumerate(uploaded_files):
            inferred = parse_filename(uploaded_file.name)

            st.markdown(f"**{uploaded_file.name}**")
            st.caption(
                f"Inferred: Type={inferred.get('format_hint') or 'Unknown'}, "
                f"Side={inferred.get('Side', 'Unknown')}, "
                f"Panel={inferred.get('Panel Number', 'Unknown')}, "
                f"BU={inferred.get('Build Up', 'Unknown')}"
            )

            key = f"{idx}_{uploaded_file.name}"
            selected_process = st.selectbox(
                "Type", list(_PROCESS_CHOICES), key=f"override_process_{key}")
            selected_side = st.selectbox(
                "Side", list(_SIDE_CHOICES), key=f"override_side_{key}")
            panel_text = st.text_input(
                "Panel Number", value="", placeholder="Auto (from filename)",
                key=f"override_panel_{key}").strip()
            build_up_text = st.text_input(
                "Build Up (BU)", value="", placeholder="Optional, e.g. 2 (auto -> BU-02)",
                key=f"override_build_up_{key}").strip()

            file_overrides.append({
                'file_name': uploaded_file.name,
                'process_override': _PROCESS_CHOICES[selected_process],
                'side_override': _SIDE_CHOICES[selected_side],
                'panel_override': panel_text or None,
                'build_up_override': build_up_text or None,
            })

            st.markdown("---")

    return file_overrides


def _render_job_info() -> Dict[str, str]:
    """Free-text job metadata that ends up on the Excel Report sheet.

    Build Up / Process / Panel are deliberately absent: they are file-derived,
    coming from the filename, the per-file overrides and the scope filters.
    """
    with st.expander("📋 Job Information", expanded=False):
        return {
            'project_name': st.text_input("Project Name", ""),
            'part_number':  st.text_input("Part Number", ""),
            'lot_number':   st.text_input("Lot Number", ""),
            'lot_name':     st.text_input("Lot Name", ""),
        }


def render_sidebar() -> Dict:
    """
    Render complete sidebar with file upload and configuration.

    Returns:
        Dictionary containing sidebar configuration and state
    """
    with st.sidebar:
        st.header("File Upload & Meta Data")

        uploaded_files = _render_uploader()
        file_overrides = _render_file_overrides(uploaded_files)

        st.markdown("---")

        return {
            'uploaded_files': uploaded_files,
            'file_overrides': file_overrides,
            **_render_job_info(),
        }


def render_nav_buttons(
    options: List[str],
    state_key: str,
    default: str = None,
    cols_gap: str = "small"
) -> str:
    """
    Render navigation buttons.

    Args:
        options: List of button labels
        state_key: Session state key for tracking selection
        default: Default selected option
        cols_gap: Column gap size

    Returns:
        Selected option
    """
    if state_key not in st.session_state or st.session_state[state_key] not in options:
        st.session_state[state_key] = default if default is not None else options[0]

    cols = st.columns(len(options), gap=cols_gap)
    for i, label in enumerate(options):
        is_active = st.session_state[state_key] == label
        cols[i].button(
            str(label),
            type="primary" if is_active else "secondary",
            width="stretch",
            key=f"{state_key}_{label}",
            on_click=lambda l=label: st.session_state.update({state_key: l}),
        )

    return st.session_state[state_key]
