"""Process Stability (Diameters) View - Monitor tool wear and etching consistency."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict

from .base import BaseView


class ProcessStabilityView(BaseView):
    """Process Stability view - diameter consistency analysis."""
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render Process Stability view.
        
        Args:
            filtered_df: Filtered dataframe
            **kwargs: Contains 'process_limits' from sidebar config
        """
        self.log_render_start("Process Stability: Diameter Consistency Analysis")
        
        st.subheader("🔧 Process Stability: Diameter Consistency Analysis")
        st.write("Monitor tool wear and etching consistency through diameter variances. Two separate scales prevent Via precision from being masked by Pad dimensions.")
        
        # Get limits from kwargs or session state
        process_limits = kwargs.get('process_limits', {})
        
        via_nominal = st.session_state.get('via_nominal', process_limits.get('via', {}).get('nominal', 0.020))
        via_ucl = st.session_state.get('via_ucl', process_limits.get('via', {}).get('ucl', 0.0215))
        via_lcl = st.session_state.get('via_lcl', process_limits.get('via', {}).get('lcl', 0.0185))
        
        pad_nominal = st.session_state.get('pad_nominal', process_limits.get('pad', {}).get('nominal', 0.3125))
        pad_ucl = st.session_state.get('pad_ucl', process_limits.get('pad', {}).get('ucl', 0.3157))
        pad_lcl = st.session_state.get('pad_lcl', process_limits.get('pad', {}).get('lcl', 0.3093))
        
        # Create two columns for side-by-side charts
        col1, col2 = st.columns(2)
        
        # --- CHART 1: Via Drill Consistency ---
        with col1:
            self._render_via_chart(filtered_df, via_nominal, via_ucl, via_lcl)
        
        # --- CHART 2: Pad Etch Consistency ---
        with col2:
            self._render_pad_chart(filtered_df, pad_nominal, pad_ucl, pad_lcl)
    
    def _render_via_chart(
        self, 
        filtered_df: pd.DataFrame, 
        nominal: float, 
        ucl: float, 
        lcl: float
    ) -> None:
        """
        Render Via Drill Consistency chart.
        
        Args:
            filtered_df: Filtered dataframe
            nominal: Nominal diameter in mm
            ucl: Upper Control Limit in mm
            lcl: Lower Control Limit in mm
        """
        via_half_band = round((ucl - nominal) * 1000, 2)
        st.markdown("### 🔴 Via Drill Consistency")
        st.caption(f"Mechanical/Laser Health - Tight control ±{via_half_band:.1f} µm")

        location_col = self.col_names.get('location', 'Location')
        
        # Filter and prepare data
        plot_df, metrics = self.processor.prepare_process_stability_data(
            filtered_df, 'Via', nominal, ucl, lcl
        )
        
        if plot_df.empty:
            st.warning("No Via diameter data available")
            return
        
        # Create chart
        fig = go.Figure()
        
        # Add scatter plot
        fig.add_trace(go.Scatter(
            x=plot_df[location_col],
            y=plot_df['diameter_um'],
            mode='markers',
            marker=dict(
                size=self.settings.get('PROCESS_STABILITY', {}).get('marker_size', 8),
                color=plot_df['color'],
                line=dict(width=1, color='rgba(0,0,0,0.3)')
            ),
            text=plot_df[location_col],
            hovertemplate='<b>%{text}</b><br>Diameter: %{y:.1f} µm<extra></extra>',
            showlegend=False
        ))
        
        # Add control lines
        self._add_control_lines(fig, metrics)
        
        # Update layout
        fig.update_layout(
            title="Via Outer Diameter Distribution",
            xaxis_title="Target ID",
            yaxis_title="Diameter (µm)",
            height=self.get_chart_height('health_status'),
            plot_bgcolor=self.get_chart_background(),
            hovermode='closest',
            yaxis=dict(
                range=[metrics['y_min'], metrics['y_max']],
                showgrid=self.get_gridlines_visible()
            ),
            xaxis=dict(showgrid=self.get_gridlines_visible())
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary stats
        st.metric(
            "Out of Spec",
            f"{metrics['out_of_spec']} / {metrics['total']} ({metrics['pct_out_of_spec']:.1f}%)",
            delta="⚠️ Review needed" if metrics['out_of_spec'] > 0 else "✓ All Pass",
            delta_color="inverse" if metrics['out_of_spec'] > 0 else "off"
        )
    
    def _render_pad_chart(
        self, 
        filtered_df: pd.DataFrame, 
        nominal: float, 
        ucl: float, 
        lcl: float
    ) -> None:
        """
        Render Pad Etch Consistency chart.
        
        Args:
            filtered_df: Filtered dataframe
            nominal: Nominal diameter in mm
            ucl: Upper Control Limit in mm
            lcl: Lower Control Limit in mm
        """
        pad_half_band = round((ucl - nominal) * 1000, 2)
        st.markdown("### 🟠 Pad Etch Consistency")
        st.caption(f"Chemistry Health - Tight control ±{pad_half_band:.1f} µm")

        location_col = self.col_names.get('location', 'Location')
        
        # Filter and prepare data
        plot_df, metrics = self.processor.prepare_process_stability_data(
            filtered_df, 'Pad', nominal, ucl, lcl
        )
        
        if plot_df.empty:
            st.warning("No Pad diameter data available")
            return
        
        # Create chart
        fig = go.Figure()
        
        # Add scatter plot
        fig.add_trace(go.Scatter(
            x=plot_df[location_col],
            y=plot_df['diameter_um'],
            mode='markers',
            marker=dict(
                size=self.settings.get('PROCESS_STABILITY', {}).get('marker_size', 8),
                color=plot_df['color'],
                line=dict(width=1, color='rgba(0,0,0,0.3)')
            ),
            text=plot_df[location_col],
            hovertemplate='<b>%{text}</b><br>Diameter: %{y:.1f} µm<extra></extra>',
            showlegend=False
        ))
        
        # Add control lines
        self._add_control_lines(fig, metrics)
        
        # Update layout
        fig.update_layout(
            title="Pad Outer Diameter Distribution",
            xaxis_title="Target ID",
            yaxis_title="Diameter (µm)",
            height=self.get_chart_height('health_status'),
            plot_bgcolor=self.get_chart_background(),
            hovermode='closest',
            yaxis=dict(
                range=[metrics['y_min'], metrics['y_max']],
                showgrid=self.get_gridlines_visible()
            ),
            xaxis=dict(showgrid=self.get_gridlines_visible())
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Summary stats
        st.metric(
            "Out of Spec",
            f"{metrics['out_of_spec']} / {metrics['total']} ({metrics['pct_out_of_spec']:.1f}%)",
            delta="⚠️ Review needed" if metrics['out_of_spec'] > 0 else "✓ All Pass",
            delta_color="inverse" if metrics['out_of_spec'] > 0 else "off"
        )
    
    def _add_control_lines(self, fig: go.Figure, metrics: Dict) -> None:
        """
        Add nominal, UCL, and LCL lines to figure.
        
        Args:
            fig: Plotly figure
            metrics: Dictionary with nominal_um, ucl_um, lcl_um values
        """
        process_stability = self.settings.get('PROCESS_STABILITY', {})
        
        # Nominal line
        fig.add_hline(
            y=metrics['nominal_um'],
            line_dash="dash",
            line_color=process_stability.get('nominal_color', '#1f77b4'),
            line_width=process_stability.get('nominal_width', 2),
            annotation_text=f"Nominal: {metrics['nominal_um']:.1f} µm",
            annotation_position="right"
        )
        
        # UCL line
        fig.add_hline(
            y=metrics['ucl_um'],
            line_dash="dot",
            line_color=process_stability.get('control_limit_color', '#ff7f0e'),
            line_width=process_stability.get('control_limit_width', 2),
            annotation_text=f"UCL: {metrics['ucl_um']:.1f} µm",
            annotation_position="right"
        )
        
        # LCL line
        fig.add_hline(
            y=metrics['lcl_um'],
            line_dash="dot",
            line_color=process_stability.get('control_limit_color', '#ff7f0e'),
            line_width=process_stability.get('control_limit_width', 2),
            annotation_text=f"LCL: {metrics['lcl_um']:.1f} µm",
            annotation_position="right"
        )
