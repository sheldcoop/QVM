"""
Sidebar UI Module - Configuration and file upload controls.

Centralizes all sidebar logic for cleaner app.py.
"""

import streamlit as st
import pandas as pd
from typing import Dict, List, Tuple, Optional


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
        
        # Meta data inputs
        material_build_up = st.text_input("Material Build-up", "")
        batch_id = st.text_input("Batch ID", "")
        
        # Process Stability Limits Configuration
        st.markdown("---")
        st.subheader("📊 Process Limits (µm)")
        
        process_config = _render_process_limits(settings)
        
        # Store all sidebar data
        sidebar_config = {
            'uploaded_files': uploaded_files,
            'material_build_up': material_build_up,
            'batch_id': batch_id,
            'process_limits': process_config
        }
        
        return sidebar_config


def _render_process_limits(settings: Dict) -> Dict:
    """
    Render Process Stability limits configuration.
    
    Args:
        settings: Application settings
    
    Returns:
        Dictionary with user-configured limits
    """
    process_stability = settings.get('PROCESS_STABILITY', {})
    
    # Via Drill Limits
    with st.expander("🔴 Via Drill Limits", expanded=False):
        default_via_nom = process_stability.get('via_nominal_diameter', 0.020) * 1000
        default_via_ucl = process_stability.get('via_ucl', 0.0215) * 1000
        default_via_lcl = process_stability.get('via_lcl', 0.0185) * 1000
        
        via_nom = st.number_input("Via Nominal (µm)", value=default_via_nom, step=0.1, key="via_nom_input")
        via_ucl = st.number_input("Via UCL (µm)", value=default_via_ucl, step=0.1, key="via_ucl_input")
        via_lcl = st.number_input("Via LCL (µm)", value=default_via_lcl, step=0.1, key="via_lcl_input")
        
        # Store in session state (convert back to mm)
        st.session_state['via_nominal'] = via_nom / 1000
        st.session_state['via_ucl'] = via_ucl / 1000
        st.session_state['via_lcl'] = via_lcl / 1000
    
    # Pad Etch Limits
    with st.expander("🟠 Pad Etch Limits", expanded=False):
        default_pad_nom = process_stability.get('pad_nominal_diameter', 0.3125) * 1000
        default_pad_ucl = process_stability.get('pad_ucl', 0.3157) * 1000
        default_pad_lcl = process_stability.get('pad_lcl', 0.3093) * 1000
        
        pad_nom = st.number_input("Pad Nominal (µm)", value=default_pad_nom, step=0.1, key="pad_nom_input")
        pad_ucl = st.number_input("Pad UCL (µm)", value=default_pad_ucl, step=0.1, key="pad_ucl_input")
        pad_lcl = st.number_input("Pad LCL (µm)", value=default_pad_lcl, step=0.1, key="pad_lcl_input")
        
        # Store in session state (convert back to mm)
        st.session_state['pad_nominal'] = pad_nom / 1000
        st.session_state['pad_ucl'] = pad_ucl / 1000
        st.session_state['pad_lcl'] = pad_lcl / 1000
    
    return {
        'via': {
            'nominal': st.session_state.get('via_nominal', process_stability.get('via_nominal_diameter', 0.020)),
            'ucl': st.session_state.get('via_ucl', process_stability.get('via_ucl', 0.0215)),
            'lcl': st.session_state.get('via_lcl', process_stability.get('via_lcl', 0.0185))
        },
        'pad': {
            'nominal': st.session_state.get('pad_nominal', process_stability.get('pad_nominal_diameter', 0.3125)),
            'ucl': st.session_state.get('pad_ucl', process_stability.get('pad_ucl', 0.3157)),
            'lcl': st.session_state.get('pad_lcl', process_stability.get('pad_lcl', 0.3093))
        }
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
