"""
2D Spatial Heatmap (Laser Scan Field) View - Detect spatial drilling distortions
Visualizes physical panel layout with color gradient showing laser drilling drift patterns
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from src.views.base import BaseView


class SpatialHeatmapView(BaseView):
    """
    SpatialHeatmapView: Analyzes laser drilling distortion patterns across the panel.
    
    Plots the physical board layout with coordinates normalized to panel origin
    and uses color gradient to expose spatial laser distortions (pincushion,
    barrel, field skew, etc.).
    
    Features:
    - Filters for Vias only (excludes Pads)
    - Normalizes coordinates to panel coordinate system (bottom-left = origin)
    - Uses SC (Total Shift) magnitude as heat indicator
    - True-to-life aspect ratio matching physical board dimensions
    - Hidden gridlines for clean board appearance
    """
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the 2D Spatial Heatmap view.
        
        Args:
            filtered_df: Input DataFrame with coordinate and shift data
            **kwargs: Additional context (col_names, chart_colors, etc.)
        """
        st.subheader("🎨 2D Spatial Heatmap: Laser Scan Field Analysis")
        st.write("Visualize the physical panel layout with spatial drilling distortion patterns. Color gradient reveals laser galvo-scanner field distortion.")
        
        col_names = kwargs.get('col_names', {})
        chart_colors = kwargs.get('chart_colors', {})
        
        # Prepare data
        plot_df = self._prepare_heatmap_data(filtered_df, col_names)
        
        if plot_df.empty:
            st.warning("No Via coordinate data available for spatial heatmap analysis")
            return
        
        # Create spatial heatmap
        self._render_heatmap(plot_df, col_names, chart_colors)
        
        # Add diagnostic guide
        self._render_diagnostic_guide()
    
    @staticmethod
    def _prepare_heatmap_data(df: pd.DataFrame, col_names: dict) -> pd.DataFrame:
        """
        Prepare data by filtering Vias only and normalizing coordinates.
        
        Args:
            df: Input DataFrame with coordinate data
            col_names: Column name mappings
            
        Returns:
            DataFrame with normalized coordinates and filtered to Vias only
        """
        # Column name mappings
        location_col = col_names.get('location', 'Location')
        coord_x_col = col_names.get('coord_x', 'Coord. X')
        coord_y_col = col_names.get('coord_y', 'Coord. Y')
        sc_col = col_names.get('total_shift', 'SC')
        dx_col = col_names.get('x_distance', 'Shift (DX)')
        dy_col = col_names.get('y_distance', 'Shift (DY)')
        pts_col = col_names.get('via_pts', 'Via Pts.')
        item_type_col = col_names.get('item_type', 'Type')
        
        # Filter for Vias only
        plot_df = df[df[item_type_col] == 'Via'].copy() if item_type_col in df.columns else df.copy()
        
        # Check for required columns
        required_cols = [location_col, coord_x_col, coord_y_col, sc_col]
        if not all(col in plot_df.columns for col in required_cols):
            return pd.DataFrame()
        
        # Filter out rows with NaN coordinates
        plot_df = plot_df[[location_col, coord_x_col, coord_y_col, sc_col, dx_col, dy_col, pts_col]].dropna(subset=[coord_x_col, coord_y_col, sc_col])
        
        if plot_df.empty:
            return pd.DataFrame()
        
        # Convert shift measurements to micrometers for display (mm -> µm)
        plot_df[sc_col] = (plot_df[sc_col] * 1000).round(3)
        plot_df[dx_col] = (plot_df[dx_col] * 1000).round(3)
        plot_df[dy_col] = (plot_df[dy_col] * 1000).round(3)
        
        # Store metadata for layout
        plot_df._metadata = {
            'max_x': plot_df[coord_x_col].max(),
            'max_y': plot_df[coord_y_col].max()
        }
        
        return plot_df
    
    @staticmethod
    def _render_heatmap(plot_df: pd.DataFrame, col_names: dict, chart_colors: dict) -> None:
        """
        Render the 2D spatial heatmap with absolute coordinates.
        
        Args:
            plot_df: DataFrame with coordinates and SC values
            col_names: Column name mappings
            chart_colors: Color configuration
        """
        # Get column names
        coord_x_col = col_names.get('coord_x', 'Coord. X')
        coord_y_col = col_names.get('coord_y', 'Coord. Y')
        
        # Extract metadata
        extent = plot_df._metadata if hasattr(plot_df, '_metadata') else {'max_x': 1, 'max_y': 1}
        max_x = extent.get('max_x', 1)
        max_y = extent.get('max_y', 1)
        
        # Create scatter plot with color gradient (SC magnitude as heat)
        fig = px.scatter(
            plot_df,
            x=coord_x_col,
            y=coord_y_col,
            color='SC',
            size='SC',
            hover_name='Location',
            custom_data=['SC', 'Shift (DX)', 'Shift (DY)', 'Via Pts.'],
            color_continuous_scale='RdYlGn_r',  # Red-Yellow-Green reversed (high=red, low=green)
            size_max=20,
            title='2D Spatial Heatmap: Laser Drilling Distortion Pattern'
        )
        
        # Update hover template
        fig.update_traces(
            hovertemplate=(
                '<b>%{hovertext}</b><br>' +
                'Position: (%.2f, %.2f) mm<br>' +
                'Total Shift (SC): %{customdata[0]:.3f} µm<br>' +
                'DX: %{customdata[1]:.3f} µm<br>' +
                'DY: %{customdata[2]:.3f} µm<br>' +
                'Via Pts: %{customdata[3]}<extra></extra>'
            )
        )
        
        # Update colorbar
        fig.update_coloraxes(
            colorbar=dict(
                title="Total Shift<br>(SC)",
                thickness=20,
                len=0.7,
                x=1.02
            )
        )
        
        # Update layout for true-to-life scaling
        fig.update_layout(
            xaxis=dict(
                title=dict(text='X Position (mm)', font=dict(color='#E8E8E8')),
                showgrid=False,
                zeroline=False,
                scaleanchor='y',
                scaleratio=1,
                range=[0, 600],
                dtick=50,
                tickfont=dict(color='#B0B0B0')
            ),
            yaxis=dict(
                title=dict(text='Y Position (mm)', font=dict(color='#E8E8E8')),
                showgrid=False,
                zeroline=False,
                scaleanchor='x',
                scaleratio=1,
                range=[0, 600],
                dtick=50,
                tickfont=dict(color='#B0B0B0')
            ),
            plot_bgcolor='#1a1a1a',
            paper_bgcolor='#1a1a1a',
            font=dict(color='#E8E8E8', size=12),
            title=dict(font=dict(color='#E8E8E8', size=16)),
            hovermode='closest',
            height=800,
            width=900,
            margin=dict(l=80, r=150, t=80, b=80)
        )
        
        st.plotly_chart(fig, use_container_width=False)
    
    @staticmethod
    def _render_diagnostic_guide() -> None:
        """Render diagnostic interpretation guide."""
        st.markdown("---")
        st.warning(
            "**🔍 Diagnostic Note:**\n\n"
            "Look for spatial color patterns. If the center is green but outer edges are red, "
            "inspect the laser galvo-scanner for field distortion or ABF pressing issues."
        )
