"""
Sidebar UI Module - Configuration and file upload controls.

Centralizes all sidebar logic for cleaner app.py.
"""

import streamlit as st
from typing import Dict, List, Optional


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
        
        st.markdown("---")
        
        # Meta data inputs inside expander
        with st.expander("📋 Job Information", expanded=False):
            project_name = st.text_input("Project Name", "")
            part_number  = st.text_input("Part Number", "")
            lot_number   = st.text_input("Lot Number", "")
            lot_name     = st.text_input("Lot Name", "")
            build_up     = st.text_input("Build Up", "")
            process      = st.text_input("Process", "")
            panel        = st.text_input("Panel", "")
        
        sidebar_config = {
            'uploaded_files': uploaded_files,
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
