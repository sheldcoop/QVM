"""
CAM Compensation View - Average X/Y shift metrics display
Extracted from app.py for modularity and reusability.
"""

import streamlit as st
import pandas as pd

from src.views.base import BaseView
from src.calculations import calculate_cam_compensation


class CAMCompensationView(BaseView):
    """
    CAMCompensationView: Displays CAM compensation metrics.
    
    Features:
    - Average X Shift (DX) metric
    - Average Y Shift (DY) metric
    """
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the CAM Compensation view.
        
        Args:
            filtered_df: Input DataFrame with measurement data
            **kwargs: Additional context including 'settings'
        """
        settings = kwargs.get('settings', {})
        
        avg_x, avg_y = calculate_cam_compensation(filtered_df, settings)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Average X Shift (DX)", f"{avg_x:.6f} mm")
        with col2:
            st.metric("Average Y Shift (DY)", f"{avg_y:.6f} mm")
