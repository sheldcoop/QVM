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
            DataFrame with added 'magnitude', 'angle' columns and location grouping
        """
        dx_col = col_names.get('x_distance', 'Shift (DX)')
        dy_col = col_names.get('y_distance', 'Shift (DY)')
        location_col = col_names.get('location', 'Location')
        
        if dx_col not in df.columns or dy_col not in df.columns:
            return pd.DataFrame()
        
        # Filter out rows with NaN shift values
        required_cols = [location_col, dx_col, dy_col]
        plot_df = df[required_cols].dropna().copy()
        
        # Add Side column if available
        if 'Side' in df.columns:
            plot_df['Side'] = df.loc[plot_df.index, 'Side']
        
        if plot_df.empty:
            return pd.DataFrame()
        
        # Extract location quadrant (UL, LL, LR, UR) from Location column
        # Location format: "UL_1", "LL_2", etc.
        plot_df['Quadrant'] = plot_df[location_col].str[:2]
        
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
        Render the polar scatter plot colored by Quadrant and Side.
        
        Args:
            plot_df: DataFrame with magnitude and angle columns
            chart_colors: Color configuration
            chart_heights: Chart height settings
        """
        # Define quadrant colors
        quadrant_colors = {
            'UL': '#1f77b4',  # Blue
            'UR': '#ff7f0e',  # Orange
            'LL': '#2ca02c',  # Green
            'LR': '#d62728'   # Red
        }
        
        # Check if Side column exists
        has_side = 'Side' in plot_df.columns
        
        fig = go.Figure()
        
        # Group by Quadrant and optionally by Side
        if has_side:
            # Group by both Quadrant and Side
            for quadrant in ['UL', 'UR', 'LL', 'LR']:
                for side in plot_df['Side'].unique():
                    mask = (plot_df['Quadrant'] == quadrant) & (plot_df['Side'] == side)
                    data = plot_df[mask]
                    
                    if not data.empty:
                        legend_name = f"{quadrant} ({side})"
                        # Use square marker for Back (B), diamond for Front (F)
                        marker_symbol = 'square' if side == 'B' else 'diamond'
                        fig.add_trace(go.Scatterpolar(
                            r=data['magnitude_um'],
                            theta=data['angle_deg'],
                            mode='markers',
                            name=legend_name,
                            marker=dict(
                                size=10,
                                color=quadrant_colors[quadrant],
                                symbol=marker_symbol,
                                line=dict(width=1, color='rgba(0,0,0,0.3)')
                            ),
                            text=data['Location'],
                            customdata=np.column_stack((
                                data['Location'],
                                data['Shift (DX) (µm)'],
                                data['Shift (DY) (µm)'],
                                data['magnitude_um'],
                                data['angle_deg']
                            )),
                            hovertemplate=(
                                '<b>%{customdata[0]}</b><br>' +
                                'DX: %{customdata[1]:.3f} µm<br>' +
                                'DY: %{customdata[2]:.3f} µm<br>' +
                                'Magnitude: %{customdata[3]:.3f} µm<br>' +
                                'Angle: %{customdata[4]:.1f}°<extra></extra>'
                            ),
                            showlegend=True
                        ))
        else:
            # Group by Quadrant only
            for quadrant in ['UL', 'UR', 'LL', 'LR']:
                mask = plot_df['Quadrant'] == quadrant
                data = plot_df[mask]
                
                if not data.empty:
                    fig.add_trace(go.Scatterpolar(
                        r=data['magnitude_um'],
                        theta=data['angle_deg'],
                        mode='markers',
                        name=quadrant,
                        marker=dict(
                            size=10,
                            color=quadrant_colors[quadrant],
                            line=dict(width=1, color='rgba(0,0,0,0.3)')
                        ),
                        text=data['Location'],
                        customdata=np.column_stack((
                            data['Location'],
                            data['Shift (DX) (µm)'],
                            data['Shift (DY) (µm)'],
                            data['magnitude_um'],
                            data['angle_deg']
                        )),
                        hovertemplate=(
                            '<b>%{customdata[0]}</b><br>' +
                            'DX: %{customdata[1]:.3f} µm<br>' +
                            'DY: %{customdata[2]:.3f} µm<br>' +
                            'Magnitude: %{customdata[3]:.3f} µm<br>' +
                            'Angle: %{customdata[4]:.1f}°<extra></extra>'
                        ),
                        showlegend=True
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
            font=dict(size=11),
            legend=dict(
                orientation="v",
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.02
            )
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    @staticmethod
    def _render_diagnostic_guide() -> None:
        """Render diagnostic interpretation guide."""
        st.markdown("---")
        st.info(
            "**🎯 UV Laser Polar Drift Guide**\n\n"
            "**Random Dots in the Center (The Cloud):** Everything is good. The laser is hitting the target. The tiny scattered dots are just normal process noise. No action needed.\n\n"
            "**Dots Clustered in One Direction (The Wedge):** The laser is constantly missing to one side. The laser's steering mirrors (galvo-scanner) need calibration, or the camera misread the panel's alignment marks.\n\n"
            "**Dots Forming a Straight Line (The Bow-Tie):** Something is vibrating back and forth while drilling. Check the machine table for looseness or check if the laser head is oscillating along the X or Y axis.\n\n"
            "**Ring or Donut Shape (Empty Center):** The laser beam is drawing a bad circle. The optics need a circularity calibration, or the shape of the laser beam itself has become distorted.\n\n"
            "**A Few Dots Far Away from the Rest (The Spikes):** A sudden failure on just one or two holes. The machine is fine, but the inspection camera was probably tricked by a speck of dust, resin debris, or rough copper plating in those specific spots."
        )
