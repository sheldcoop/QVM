"""
Optical Edge Confidence View - Point count analysis for hole integrity and plating quality
Extracted from app.py for modularity and reusability.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from src.views.base import BaseView


class OpticalEdgeConfidenceView(BaseView):
    """
    OpticalEdgeConfidenceView: Analyzes Point Count (Pts.) metric for optical inspection.
    
    Features:
    - Via/Pad health bar charts with traffic light logic (green/orange/red)
    - Pad vs Via separation scatter plot with box plots
    - Detailed analysis tables sorted by lowest point count
    """
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the Optical Edge Confidence analysis view.
        
        Args:
            filtered_df: Input DataFrame with measurement data and Pts. column
            **kwargs: Additional context including 'col_names', 'chart_colors', etc.
        """
        st.subheader("🔍 Optical Edge Confidence Analysis")
        st.write(
            "Analyze Point Count (Pts.) metric from optical inspection for hole integrity "
            "and plating quality assessment."
        )
        
        col_names = kwargs.get('col_names', {})
        chart_colors = kwargs.get('chart_colors', {})
        chart_heights = kwargs.get('chart_heights', {})
        chart_markers = kwargs.get('chart_markers', {})
        optical_thresholds = kwargs.get('optical_thresholds', {})
        
        # Check if required columns exist
        pad_pts_col = 'Pad Pts.'
        via_pts_col = 'Via Pts.'
        
        if pad_pts_col not in filtered_df.columns or via_pts_col not in filtered_df.columns:
            st.error(f"Columns '{pad_pts_col}' and/or '{via_pts_col}' not found in data. Available columns: {list(filtered_df.columns)}")
            return
        
        # --- 1. Via Health Bar Chart ---
        st.markdown("### 1️⃣ Via Health Status (Traffic Light Logic)")
        self._render_via_health_chart(filtered_df, via_pts_col, col_names, chart_colors, chart_heights, optical_thresholds)
        
        # --- 1a. Pad Health Bar Chart ---
        st.markdown("### 1️⃣a Pad Health Status (Traffic Light Logic)")
        self._render_pad_health_chart(filtered_df, pad_pts_col, col_names, chart_colors, chart_heights, optical_thresholds)
        
        # --- 2. Pad vs Via Separation Scatter Plot ---
        st.markdown("### 2️⃣ Pad vs. Via Edge Detection Verification")
        self._render_comparison_scatter(filtered_df, pad_pts_col, via_pts_col, col_names, chart_colors, chart_heights, chart_markers)
        
        # --- 3. Detailed Analysis Tables for Vias and Pads ---
        st.markdown("### 3️⃣ Optical Edge Detection Details")
        self._render_detailed_tables(filtered_df, pad_pts_col, via_pts_col, col_names)
    
    @staticmethod
    def _render_via_health_chart(filtered_df, via_pts_col, col_names, chart_colors, chart_heights, optical_thresholds):
        """Render Via health bar chart with traffic light colors."""
        # Data already consolidated - each row has location with Via Pts.
        via_data = filtered_df[['Location', 'Grid ID', via_pts_col]].dropna(subset=[via_pts_col]).copy()
        
        if not via_data.empty:
            via_data.columns = ['Via ID', 'Grid ID', 'Point Count']
            
            # Define colors based on traffic light logic
            def get_health_color(points):
                if pd.isna(points):
                    return chart_colors.get('traffic_light_gray', '#999999')
                green_threshold = optical_thresholds.get('green_min', 75)
                orange_threshold = optical_thresholds.get('orange_min', 40)
                if points > green_threshold:
                    return chart_colors.get('traffic_light_green', '#2ecc71')
                elif points >= orange_threshold:
                    return chart_colors.get('traffic_light_orange', '#f39c12')
                else:
                    return chart_colors.get('traffic_light_red', '#e74c3c')
            
            via_data['Color'] = via_data['Point Count'].apply(get_health_color)
            
            # Create bar chart with Grid ID labels
            fig_via_health = go.Figure(data=[
                go.Bar(
                    x=via_data['Via ID'],
                    y=via_data['Point Count'],
                    marker=dict(color=via_data['Color']),
                    text=[f"{pts:.1f}<br>({gid})" for pts, gid in zip(via_data['Point Count'], via_data['Grid ID'])],
                    textposition='outside',
                    customdata=via_data['Grid ID'],
                    hovertemplate='<b>%{x}</b><br>Grid ID: %{customdata}<br>Points: %{y:.1f}<extra></extra>'
                )
            ])
            
            fig_via_health.update_layout(
                title="Via Health Status by Point Count",
                xaxis_title="Via ID",
                yaxis_title="Point Count (Pts.)",
                height=chart_heights.get('health_status', 550),
                showlegend=False,
                plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF'),
                hovermode='x unified',
                xaxis=dict(showgrid=chart_colors.get('chart_gridlines_visible', False)),
                yaxis=dict(showgrid=chart_colors.get('chart_gridlines_visible', False))
            )
            
            st.plotly_chart(fig_via_health, use_container_width=True)
        else:
            st.warning("No Via data found in the dataset.")
    
    @staticmethod
    def _render_pad_health_chart(filtered_df, pad_pts_col, col_names, chart_colors, chart_heights, optical_thresholds):
        """Render Pad health bar chart with traffic light colors."""
        # Data already consolidated - each row has location with Pad Pts.
        pad_data = filtered_df[['Location', 'Grid ID', pad_pts_col]].dropna(subset=[pad_pts_col]).copy()
        
        if not pad_data.empty:
            pad_data.columns = ['Pad ID', 'Grid ID', 'Point Count']
            
            # Define colors based on traffic light logic
            def get_health_color_pad(points):
                if pd.isna(points):
                    return chart_colors.get('traffic_light_gray', '#999999')
                green_threshold = optical_thresholds.get('green_min', 75)
                orange_threshold = optical_thresholds.get('orange_min', 40)
                if points > green_threshold:
                    return chart_colors.get('traffic_light_green', '#2ecc71')
                elif points >= orange_threshold:
                    return chart_colors.get('traffic_light_orange', '#f39c12')
                else:
                    return chart_colors.get('traffic_light_red', '#e74c3c')
            
            pad_data['Color'] = pad_data['Point Count'].apply(get_health_color_pad)
            
            # Create bar chart with Grid ID labels
            fig_pad_health = go.Figure(data=[
                go.Bar(
                    x=pad_data['Pad ID'],
                    y=pad_data['Point Count'],
                    marker=dict(color=pad_data['Color']),
                    text=[f"{pts:.1f}<br>({gid})" for pts, gid in zip(pad_data['Point Count'], pad_data['Grid ID'])],
                    textposition='outside',
                    customdata=pad_data['Grid ID'],
                    hovertemplate='<b>%{x}</b><br>Grid ID: %{customdata}<br>Points: %{y:.1f}<extra></extra>'
                )
            ])
            
            fig_pad_health.update_layout(
                title="Pad Health Status by Point Count",
                xaxis_title="Pad ID",
                yaxis_title="Point Count (Pts.)",
                height=chart_heights.get('health_status', 550),
                showlegend=False,
                plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF'),
                hovermode='x unified',
                xaxis=dict(showgrid=chart_colors.get('chart_gridlines_visible', False)),
                yaxis=dict(showgrid=chart_colors.get('chart_gridlines_visible', False))
            )
            
            st.plotly_chart(fig_pad_health, use_container_width=True)
        else:
            st.warning("No Pad data found in the dataset.")
    
    @staticmethod
    def _render_comparison_scatter(filtered_df, pad_pts_col, via_pts_col, col_names, chart_colors, chart_heights, chart_markers):
        """Render Pad vs Via separation scatter plot with box plots."""
        # Prepare consolidated data - both Pad and Via in same rows
        scatter_df = filtered_df[['Location', 'Grid ID', pad_pts_col, via_pts_col]].dropna(subset=[pad_pts_col, via_pts_col]).copy()
        
        if not scatter_df.empty:
            # Create box plot with scatter overlay
            fig_comparison = go.Figure()
            
            # Map categories to numeric positions for jitter
            category_to_num = {'Pad': 0, 'Via': 1}
            
            # Process Pad data
            pad_points = scatter_df[pad_pts_col]
            if len(pad_points) > 0:
                # Add box plot for Pads
                fig_comparison.add_trace(go.Box(
                    x=['Pad'] * len(pad_points),
                    y=pad_points,
                    name='Pad',
                    boxmean='sd',
                    marker_opacity=0.3,
                    boxpoints=False
                ))
                
                # Add scatter with jitter for Pads
                jitter = np.random.normal(0, 0.04, size=len(pad_points))
                x_numeric = np.array([category_to_num['Pad']] * len(pad_points))
                x_jittered = x_numeric + jitter
                
                # Create hover text with Location and Grid ID
                hover_text = [f"{loc}<br>Grid: {gid}" for loc, gid in zip(scatter_df['Location'], scatter_df['Grid ID'])]
                
                fig_comparison.add_trace(go.Scatter(
                    x=x_jittered,
                    y=pad_points,
                    mode='markers+text',
                    name='Pad (Individual)',
                    marker=dict(size=chart_markers.get('pad_via_scatter_size', 16), opacity=0.9),
                    text=scatter_df['Grid ID'],
                    textposition='middle center',
                    textfont=dict(size=chart_markers.get('pad_via_text_size', 10), color='white'),
                    showlegend=False,
                    hovertemplate='<b>%{customdata}</b><br>Points: %{y:.0f}<extra></extra>',
                    customdata=hover_text
                ))
            
            # Process Via data
            via_points = scatter_df[via_pts_col]
            if len(via_points) > 0:
                # Add box plot for Vias
                fig_comparison.add_trace(go.Box(
                    x=['Via'] * len(via_points),
                    y=via_points,
                    name='Via',
                    boxmean='sd',
                    marker_opacity=0.3,
                    boxpoints=False
                ))
                
                # Add scatter with jitter for Vias
                jitter = np.random.normal(0, 0.04, size=len(via_points))
                x_numeric = np.array([category_to_num['Via']] * len(via_points))
                x_jittered = x_numeric + jitter
                
                # Create hover text with Location and Grid ID
                hover_text = [f"{loc}<br>Grid: {gid}" for loc, gid in zip(scatter_df['Location'], scatter_df['Grid ID'])]
                
                fig_comparison.add_trace(go.Scatter(
                    x=x_jittered,
                    y=via_points,
                    mode='markers+text',
                    name='Via (Individual)',
                    marker=dict(size=chart_markers.get('pad_via_scatter_size', 16), opacity=0.9),
                    text=scatter_df['Grid ID'],
                    textposition='middle center',
                    textfont=dict(size=chart_markers.get('pad_via_text_size', 10), color='white'),
                    showlegend=False,
                    hovertemplate='<b>%{customdata}</b><br>Points: %{y:.0f}<extra></extra>',
                    customdata=hover_text
                ))
            
            fig_comparison.update_xaxes(tickvals=[0, 1], ticktext=['Pad', 'Via'], showgrid=chart_colors.get('chart_gridlines_visible', False))
            fig_comparison.update_layout(
                title="Edge Detection Verification: Pads vs Vias",
                yaxis_title="Point Count (Pts.)",
                height=chart_heights.get('comparison_plot', 400),
                plot_bgcolor=chart_colors.get('chart_background', '#FFFFFF'),
                hovermode='closest',
                boxmode='group',
                yaxis=dict(showgrid=chart_colors.get('chart_gridlines_visible', False))
            )
            
            st.plotly_chart(fig_comparison, use_container_width=True)
    
    @staticmethod
    def _render_detailed_tables(filtered_df, pad_pts_col, via_pts_col, col_names):
        """Render detailed analysis tables for Pads and Vias."""
        # --- Via Details Table ---
        st.markdown("#### 🔴 Via Analysis (All Vias by Lowest Point Count)")
        
        via_table_df = filtered_df[['Location', 'Grid ID', via_pts_col, 'PtV Distance', 'Shift (DX)', 'Shift (DY)']].copy()
        via_table_df = via_table_df.sort_values(by=via_pts_col, ascending=True)
        
        if not via_table_df.empty:
            via_display = via_table_df.copy()
            
            # Convert to microns (multiply by 1000)
            via_display['PtV Distance (µm)'] = (via_display['PtV Distance'] * 1000).round(3)
            via_display['Shift DX (µm)'] = (via_display['Shift (DX)'] * 1000).round(3)
            via_display['Shift DY (µm)'] = (via_display['Shift (DY)'] * 1000).round(3)
            
            # Keep only renamed columns
            via_display = via_display[['Location', 'Grid ID', via_pts_col, 'PtV Distance (µm)', 'Shift DX (µm)', 'Shift DY (µm)']]
            via_display.columns = ['Location', 'Grid ID', 'Pts.', 'PtV (µm)', 'Shift DX (µm)', 'Shift DY (µm)']
            
            st.dataframe(via_display, use_container_width=True, hide_index=True)
        else:
            st.info("No Via data available")
        
        st.markdown("---")
        
        # --- Pad Details Table ---
        st.markdown("#### 🟠 Pad Analysis (All Pads by Lowest Point Count)")
        
        pad_table_df = filtered_df[['Location', 'Grid ID', pad_pts_col, 'PtV Distance', 'Shift (DX)', 'Shift (DY)']].copy()
        pad_table_df = pad_table_df.sort_values(by=pad_pts_col, ascending=True)
        
        if not pad_table_df.empty:
            pad_display = pad_table_df.copy()
            
            # Convert to microns (multiply by 1000)
            pad_display['PtV Distance (µm)'] = (pad_display['PtV Distance'] * 1000).round(3)
            pad_display['Shift DX (µm)'] = (pad_display['Shift (DX)'] * 1000).round(3)
            pad_display['Shift DY (µm)'] = (pad_display['Shift (DY)'] * 1000).round(3)
            
            # Keep only renamed columns
            pad_display = pad_display[['Location', 'Grid ID', pad_pts_col, 'PtV Distance (µm)', 'Shift DX (µm)', 'Shift DY (µm)']]
            pad_display.columns = ['Location', 'Grid ID', 'Pts.', 'PtV (µm)', 'Shift DX (µm)', 'Shift DY (µm)']
            
            st.dataframe(pad_display, use_container_width=True, hide_index=True)
        else:
            st.info("No Pad data available")
