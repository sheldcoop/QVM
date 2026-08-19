"""
Sidebar UI Module - Configuration and file upload controls.

Centralizes all sidebar logic for cleaner app.py.
"""

import streamlit as st
from typing import Dict, List, Optional
from src.parser import parse_filename


def render_sidebar(settings: Dict) -> Dict:
    """
    Render complete sidebar with file upload and configuration.
    
    Args:
        settings: Application settings from YAML
    
    Returns:
        Dictionary containing sidebar configuration and state
    """
    with st.sidebar:
        st.header("File Upload & Meta Data")
        
        # File upload
        uploaded_files = st.file_uploader(
            "Upload QVM Text Files",
            type=['txt'],
            accept_multiple_files=True
        )
        st.caption(
            "Recommended filename: `PTV_P20_F_BU-01.txt` or `VTP_P20_B_BU-02.txt` "
            "(PROCESS_PANEL_SIDE_BU). If naming is imperfect, use Optional Per-File Overrides below."
        )

        file_overrides = []
        if uploaded_files:
            with st.expander("Optional Per-File Overrides", expanded=False):
                st.caption(
                    "Leave values on Auto/blank to keep current behavior. "
                    "Set values only when you want to override file naming metadata."
                )
                for idx, uploaded_file in enumerate(uploaded_files):
                    inferred = parse_filename(uploaded_file.name)
                    inferred_hint = inferred.get('format_hint') or "Unknown"
                    inferred_side = inferred.get('Side', 'Unknown')
                    inferred_panel = inferred.get('Panel Number', 'Unknown')
                    inferred_build_up = inferred.get('Build Up', 'Unknown')

                    st.markdown(f"**{uploaded_file.name}**")
                    st.caption(
                        f"Inferred: Type={inferred_hint}, Side={inferred_side}, Panel={inferred_panel}, BU={inferred_build_up}"
                    )

                    selected_process = st.selectbox(
                        "Type",
                        [
                            "Auto (content-detected)",
                            "Pad to Via (PTV)",
                            "Via to Pad (VTP)",
                        ],
                        key=f"override_process_{idx}_{uploaded_file.name}",
                    )

                    selected_side = st.selectbox(
                        "Side",
                        [
                            "Auto (from filename)",
                            "Front (F)",
                            "Back (B)",
                        ],
                        key=f"override_side_{idx}_{uploaded_file.name}",
                    )

                    panel_text = st.text_input(
                        "Panel Number",
                        value="",
                        placeholder="Auto (from filename)",
                        key=f"override_panel_{idx}_{uploaded_file.name}",
                    ).strip()

                    build_up_text = st.text_input(
                        "Build Up (BU)",
                        value="",
                        placeholder="Optional, e.g. 2 (auto -> BU-02)",
                        key=f"override_build_up_{idx}_{uploaded_file.name}",
                    ).strip()

                    process_override = None
                    if selected_process == "Pad to Via (PTV)":
                        process_override = "Pad to Via"
                    elif selected_process == "Via to Pad (VTP)":
                        process_override = "Via to Pad"

                    side_override = None
                    if selected_side == "Front (F)":
                        side_override = "F"
                    elif selected_side == "Back (B)":
                        side_override = "B"

                    panel_override = panel_text if panel_text else None
                    build_up_override = build_up_text if build_up_text else None

                    file_overrides.append({
                        'file_name': uploaded_file.name,
                        'process_override': process_override,
                        'side_override': side_override,
                        'panel_override': panel_override,
                        'build_up_override': build_up_override,
                    })

                    st.markdown("---")
        
        st.markdown("---")
        
        # Meta data inputs inside expander
        with st.expander("📋 Job Information", expanded=False):
            project_name = st.text_input("Project Name", "")
            part_number  = st.text_input("Part Number", "")
            lot_number   = st.text_input("Lot Number", "")
            lot_name     = st.text_input("Lot Name", "")
            # Build Up/Process/Panel are file-derived now and managed through
            # per-file overrides and scope filters, not manual Job Information.
            build_up     = ""
            process      = ""
            panel        = ""
        
        sidebar_config = {
            'uploaded_files': uploaded_files,
            'file_overrides': file_overrides,
            'project_name':  project_name,
            'part_number':   part_number,
            'lot_number':    lot_number,
            'lot_name':      lot_name,
            'build_up':      build_up,
            'process':       process,
            'panel':         panel,
        }

        return sidebar_config


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
