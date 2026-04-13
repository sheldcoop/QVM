"""
Analytics View - Quiver and Heatmap plot selector
Extracted from app.py for modularity and reusability.
"""

import streamlit as st
import pandas as pd

from src.views.base import BaseView
from src.visuals import plot_quiver, plot_heatmap


class AnalyticsView(BaseView):
    """
    AnalyticsView: Provides interactive plot type selection and rendering.
    
    Supported plot types:
    - Quiver/Vector Plot: Directional shift with configurable exaggeration
    - Heatmap: Measurement distribution across quadrants
    """
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the Analytics view with plot type selector.
        
        Args:
            filtered_df: Input DataFrame with measurement data
            **kwargs: Additional context including 'settings'
        """
        settings = kwargs.get('settings', {})
        chart_heights = settings.get('CHART_HEIGHTS', {})
        plot_settings = settings.get('PLOT_SETTINGS', {})
        
        plot_type = st.selectbox(
            "Select Plot Type",
            ["Quiver/Vector Plot", "Heatmap"]
        )
        
        if plot_type == "Quiver/Vector Plot":
            st.markdown("**Pattern Hunter: ABF Distortion Diagnostic**")
            st.write("Use the sensitivity slider to amplify error vectors. Look for color patterns:")
            st.write("- 🔴 **RED**: Material expansion/shrinkage (errors point away from/toward center)")
            st.write("- 🟡 **GOLD**: Lamination twist (errors swirl around center)")
            st.write("- 🔵 **BLUE**: Global offset (uniform machine misalignment)")
            
            multiplier = st.slider(
                "Vector Exaggeration Multiplier (Sensitivity)",
                min_value=plot_settings.get('vector_multiplier_min', 1),
                max_value=plot_settings.get('vector_multiplier_max', 5000),
                value=plot_settings.get('vector_multiplier_default', 2500),
                help="Higher values amplify error vectors to reveal spatial distortion patterns"
            )
            fig = plot_quiver(filtered_df, settings, multiplier)
            st.plotly_chart(fig, use_container_width=True, height=chart_heights.get('analytics_plot', 600))
        
        elif plot_type == "Heatmap":
            fig = plot_heatmap(filtered_df, settings)
            st.plotly_chart(fig, use_container_width=True, height=chart_heights.get('analytics_plot', 600))
