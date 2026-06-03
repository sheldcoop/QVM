"""
2D Spatial Heatmap (Laser Scan Field) View - Detect spatial drilling distortions
Visualizes physical panel layout with color gradient showing laser drilling drift patterns
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

from src import theme
from src.utils import convert_to_microns
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
        """Render the 2D Spatial Heatmap view."""
        st.subheader("🎨 2D Spatial Heatmap: Laser Scan Field Analysis")
        st.write("Visualize the physical panel layout with spatial drilling distortion patterns. Color gradient reveals laser galvo-scanner field distortion.")

        col_names = self.col_names

        plot_df = self._prepare_heatmap_data(filtered_df, col_names)

        if plot_df.empty:
            st.warning("No Via coordinate data available for spatial heatmap analysis")
            return

        # Create spatial heatmap
        self._render_heatmap(plot_df, col_names, self.settings.get('SPATIAL_HEATMAP', {}))
        
        # Add diagnostic guide
        self._render_diagnostic_guide()
    
    @staticmethod
    def _prepare_heatmap_data(df: pd.DataFrame, col_names: dict) -> pd.DataFrame:
        """Prepare coordinate + shift data for the spatial heatmap."""
        location_col = col_names.get('location', 'Location')
        coord_x_col = col_names.get('coord_x', 'Coord. X')
        coord_y_col = col_names.get('coord_y', 'Coord. Y')
        sc_col = col_names.get('total_shift', 'SC')
        dx_col = col_names.get('x_distance', 'Shift (DX)')
        dy_col = col_names.get('y_distance', 'Shift (DY)')
        pts_col = col_names.get('via_pts', 'Via Pts.')

        plot_df = df.copy()
        required_cols = [location_col, coord_x_col, coord_y_col, sc_col]
        if not all(col in plot_df.columns for col in required_cols):
            return pd.DataFrame()

        plot_df = plot_df[[location_col, coord_x_col, coord_y_col, sc_col, dx_col, dy_col, pts_col]].dropna(subset=[coord_x_col, coord_y_col, sc_col])
        if plot_df.empty:
            return pd.DataFrame()

        plot_df = convert_to_microns(plot_df, [sc_col, dx_col, dy_col])

        plot_df._metadata = {
            'max_x': plot_df[coord_x_col].max(),
            'max_y': plot_df[coord_y_col].max(),
        }
        return plot_df
    
    @staticmethod
    def _render_heatmap(plot_df: pd.DataFrame, col_names: dict, spatial_cfg: dict) -> None:
        """Render the 2D spatial heatmap with absolute coordinates."""
        location_col = col_names.get('location', 'Location')
        coord_x_col = col_names.get('coord_x', 'Coord. X')
        coord_y_col = col_names.get('coord_y', 'Coord. Y')
        sc_col = col_names.get('total_shift', 'SC')
        dx_col = col_names.get('x_distance', 'Shift (DX)')
        dy_col = col_names.get('y_distance', 'Shift (DY)')
        pts_col = col_names.get('via_pts', 'Via Pts.')

        # Create scatter plot with color gradient (SC magnitude as heat)
        fig = px.scatter(
            plot_df,
            x=coord_x_col,
            y=coord_y_col,
            color=sc_col,
            size=sc_col,
            hover_name=location_col,
            custom_data=[sc_col, dx_col, dy_col, pts_col],
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
        
        # Update layout for true-to-life scaling (Catppuccin Mocha dark theme)
        axis_max  = spatial_cfg.get('axis_max_mm', 600)
        axis_dtick = spatial_cfg.get('axis_dtick_mm', 50)
        fig.update_layout(
            xaxis=dict(
                title=dict(text='X Position (mm)', font=dict(color=theme.TEXT, size=12)),
                showgrid=False,
                zeroline=False,
                scaleanchor='y',
                scaleratio=1,
                range=[0, axis_max],
                dtick=axis_dtick
            ),
            yaxis=dict(
                title=dict(text='Y Position (mm)', font=dict(color=theme.TEXT, size=12)),
                showgrid=False,
                zeroline=False,
                scaleanchor='x',
                scaleratio=1,
                range=[0, axis_max],
                dtick=axis_dtick
            ),
            plot_bgcolor=theme.PLOT_BG,
            paper_bgcolor=theme.PAPER_BG,
            font=dict(color=theme.TEXT_MUTED, size=11),
            title=dict(text='2D Spatial Heatmap: Laser Drilling Distortion Pattern',
                       font=dict(color=theme.TEXT, size=16)),
            hovermode='closest',
            height=spatial_cfg.get('height', 800),
            width=spatial_cfg.get('width', 900),
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
