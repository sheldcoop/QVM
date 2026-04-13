"""
Polar Drift (Machine Health) View - Detect systematic machine runout
Converts Cartesian DX/DY shifts into Polar coordinates for spindle/gantry analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math

from src.views.base import BaseView


class PolarDriftView(BaseView):
    """
    PolarDriftView: Analyzes machine runout through polar coordinate analysis.
    
    Converts Cartesian shift measurements (DX/DY) into polar coordinates
    (magnitude and angle) to detect systematic machine drift patterns.
    
    Features:
    - Calculates magnitude and angle from DX/DY shifts
    - Visualizes as polar scatter plot
    - Provides diagnostic interpretation
    """
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the Polar Drift analysis view.
        
        Args:
            filtered_df: Input DataFrame with DX/DY measurements
            **kwargs: Additional context (col_names, chart_colors, etc.)
        """
        st.subheader("🔄 Polar Drift: Machine Health Analysis")
        st.write("Convert Cartesian shifts (DX/DY) into Polar coordinates to detect systematic spindle runout and gantry skew.")
        
        col_names = kwargs.get('col_names', {})
        chart_colors = kwargs.get('chart_colors', {})
        chart_heights = kwargs.get('chart_heights', {})
        
        # Prepare data
        plot_df = self._prepare_polar_data(filtered_df, col_names)
        
        if plot_df.empty:
            st.warning("No shift data available for polar analysis")
            return
        
        # Create polar scatter plot
        self._render_polar_chart(plot_df, chart_colors, chart_heights)
        
        # Add diagnostic guide
        self._render_diagnostic_guide()
    
    @staticmethod
    def _prepare_polar_data(df: pd.DataFrame, col_names: dict) -> pd.DataFrame:
        """
        Prepare data by converting Cartesian coordinates to Polar.
        
        Args:
            df: Input DataFrame with DX and DY columns
            col_names: Column name mappings
            
        Returns:
            DataFrame with added 'magnitude', 'angle' columns
        """
        dx_col = col_names.get('x_distance', 'Shift (DX)')
        dy_col = col_names.get('y_distance', 'Shift (DY)')
        location_col = col_names.get('location', 'Location')
        
        if dx_col not in df.columns or dy_col not in df.columns:
            return pd.DataFrame()
        
        # Filter out rows with NaN shift values
        plot_df = df[[location_col, dx_col, dy_col]].dropna().copy()
        
        if plot_df.empty:
            return pd.DataFrame()
        
        # Calculate magnitude (r) in microns
        plot_df['magnitude_um'] = np.sqrt(
            (plot_df[dx_col] * 1000) ** 2 + 
            (plot_df[dy_col] * 1000) ** 2
        ).round(3)
        
        # Calculate angle (theta) in degrees, normalized to 0-360
        plot_df['angle_deg'] = plot_df.apply(
            lambda row: (
                math.degrees(math.atan2(row[dy_col] * 1000, row[dx_col] * 1000)) % 360
            ),
            axis=1
        ).round(1)
        
        # Convert shift values to microns for hover display
        plot_df[f'{dx_col} (µm)'] = (plot_df[dx_col] * 1000).round(3)
        plot_df[f'{dy_col} (µm)'] = (plot_df[dy_col] * 1000).round(3)
        
        return plot_df
    
    @staticmethod
    def _render_polar_chart(
        plot_df: pd.DataFrame, 
        chart_colors: dict,
        chart_heights: dict
    ) -> None:
        """
        Render the polar scatter plot.
        
        Args:
            plot_df: DataFrame with magnitude and angle columns
            chart_colors: Color configuration
            chart_heights: Chart height settings
        """
        # Create scatter polar plot
        fig = go.Figure(data=go.Scatterpolar(
            r=plot_df['magnitude_um'],
            theta=plot_df['angle_deg'],
            mode='markers',
            marker=dict(
                size=10,
                color=plot_df['magnitude_um'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(
                    title="Magnitude (µm)",
                    thickness=15,
                    len=0.7,
                    x=1.1
                ),
                line=dict(width=1, color='rgba(0,0,0,0.3)')
            ),
            text=plot_df['Location'],
            customdata=np.column_stack((
                plot_df['Location'],
                plot_df['Shift (DX) (µm)'],
                plot_df['Shift (DY) (µm)'],
                plot_df['magnitude_um'],
                plot_df['angle_deg']
            )),
            hovertemplate=(
                '<b>%{customdata[0]}</b><br>' +
                'DX: %{customdata[1]:.3f} µm<br>' +
                'DY: %{customdata[2]:.3f} µm<br>' +
                'Magnitude: %{customdata[3]:.3f} µm<br>' +
                'Angle: %{customdata[4]:.1f}°<extra></extra>'
            ),
            showlegend=False
        ))
        
        # Update layout
        fig.update_layout(
            title="Polar Drift Analysis: Machine Runout Detection",
            polar=dict(
                angularaxis=dict(
                    direction="counterclockwise",
                    rotation=0  # Start at East (0°)
                ),
                radialaxis=dict(
                    visible=True,
                    range=[0, plot_df['magnitude_um'].max() * 1.1]
                ),
                bgcolor=chart_colors.get('chart_background', '#FFFFFF')
            ),
            plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF'),
            height=600,
            hovermode='closest',
            font=dict(size=11)
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def _render_diagnostic_guide() -> None:
        """Render diagnostic interpretation guide."""
        st.markdown("---")
        st.info(
            "**📊 Diagnostic Guide:**\n\n"
            "• **Random scatter around center** → Process is stable (good spindle health)\n\n"
            "• **Heavy clustering in one quadrant** → Mechanical runout or gantry skew in that direction\n"
            "  - NE quadrant: Inspect spindle tilt or gantry alignment\n"
            "  - SE quadrant: Check spindle bearing wear\n"
            "  - SW quadrant: Verify gantry perpendicularity\n"
            "  - NW quadrant: Inspect spindle balance\n\n"
            "• **Ring pattern (equal radius, different angles)** → Systematic thermal drift\n\n"
            "• **High magnitude spikes** → Look for intermittent calibration errors or tool deflection"
        )
