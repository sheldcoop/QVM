"""
Analytics View - Quiver and Heatmap plot selector
Extracted from app.py for modularity and reusability.
"""

import streamlit as st
import pandas as pd

from src.views.base import BaseView
from src.visuals import plot_quiver, plot_heatmap, diagnose_root_cause_confidence, calculate_cam_compensation_summary


class AnalyticsView(BaseView):
    """
    AnalyticsView: Provides interactive plot type selection and rendering.
    
    Supported plot types:
    - Quiver/Vector Plot: Directional shift with configurable exaggeration
    - Heatmap: Measurement distribution across quadrants
    """

    def _render_root_cause_confidence(self, diagnosis: dict) -> None:
        """Render root cause confidence summary and class probabilities."""
        st.markdown("**Root Cause Confidence Engine**")

        if diagnosis.get('status') != 'ok':
            st.info(diagnosis.get('message', 'Diagnosis unavailable for current selection.'))
            return

        scores = diagnosis.get('scores', {})
        top_cause = diagnosis.get('top_cause', 'N/A')
        top_probability = diagnosis.get('top_probability', 0.0)
        confidence = diagnosis.get('confidence', 0.0)
        confidence_band = diagnosis.get('confidence_band', 'Low')
        stats = diagnosis.get('stats', {})

        col1, col2, col3 = st.columns(3)
        col1.metric("Top Cause", top_cause, f"{top_probability * 100:.1f}%")
        col2.metric("Confidence", f"{confidence * 100:.1f}%", confidence_band)
        col3.metric("Data Quality", f"{stats.get('data_quality', 0.0) * 100:.1f}%")

        col4, col5 = st.columns(2)
        col4.metric("Class Certainty", f"{stats.get('certainty', 0.0) * 100:.1f}%")
        col5.metric("Quadrant Stability", f"{stats.get('stability', 0.0) * 100:.1f}%")

        st.caption(
            f"Valid points: {stats.get('valid_points', 0)}/{stats.get('expected_points', 0)} | "
            f"Mean signal: {stats.get('mean_magnitude_um', 0.0):.2f} µm | "
            f"Directional coherence: {stats.get('directional_coherence', 0.0) * 100:.1f}%"
        )

        for label in ["Expansion", "Shrinkage", "Twist", "Offset"]:
            score_pct = scores.get(label, 0.0) * 100.0
            st.write(f"{label}: {score_pct:.1f}%")
            st.progress(int(round(score_pct)))

        reasons = diagnosis.get('reasons', [])
        if reasons:
            st.caption(" | ".join(reasons))

    def _show_grid_id_warnings(self, filtered_df: pd.DataFrame, settings: dict) -> None:
        """Display data-quality warnings for missing or unknown Grid IDs."""
        col_names = settings.get('COLUMN_NAMES', {})
        grid_col = col_names.get('grid_id', 'Grid ID')

        if grid_col not in filtered_df.columns:
            st.warning(f"Grid ID warning: Column '{grid_col}' is missing from data.")
            return

        configured_grid_ids = {str(v) for v in settings.get('GRID_MAPPING', {}).values()}
        valid_grid_ids = configured_grid_ids or {
            '11', '12', '13', '14',
            '21', '22', '23', '24',
            '31', '32', '33', '34',
            '41', '42', '43', '44',
        }

        grid_series = filtered_df[grid_col]
        missing_count = int(grid_series.isna().sum())

        numeric_grid = pd.to_numeric(grid_series, errors='coerce').dropna().astype(int)
        unknown_ids = sorted({str(gid) for gid in numeric_grid.unique() if str(gid) not in valid_grid_ids})

        warning_parts = []
        if missing_count > 0:
            warning_parts.append(f"{missing_count} row(s) have missing Grid ID")
        if unknown_ids:
            warning_parts.append(f"unknown Grid ID(s): {', '.join(unknown_ids)}")

        if warning_parts:
            st.warning("Grid ID data quality warning: " + "; ".join(warning_parts) + ".")
    
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

        self._show_grid_id_warnings(filtered_df, settings)
        
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

            cam_summary = calculate_cam_compensation_summary(filtered_df, settings)
            self._render_cam_compensation_summary(cam_summary)

            diagnosis = diagnose_root_cause_confidence(filtered_df, settings)
            self._render_root_cause_confidence(diagnosis)
            
            multiplier = st.slider(
                "Vector Exaggeration Multiplier (Sensitivity)",
                min_value=plot_settings.get('vector_multiplier_min', 1),
                max_value=plot_settings.get('vector_multiplier_max', 100),
                value=plot_settings.get('vector_multiplier_default', 50),
                help="Higher values amplify error vectors to reveal spatial distortion patterns"
            )
            fig = plot_quiver(filtered_df, settings, multiplier)
            st.plotly_chart(fig, use_container_width=True, height=chart_heights.get('analytics_plot', 600))
        
        elif plot_type == "Heatmap":
            fig = plot_heatmap(filtered_df, settings)
            st.plotly_chart(fig, use_container_width=True, height=chart_heights.get('analytics_plot', 600))

    def _render_cam_compensation_summary(self, summary: dict) -> None:
        """Render CAM expansion/shrinkage summary for compensation guidance."""
        st.markdown("**CAM Compensation Estimate**")

        if summary.get('status') != 'Monitor' and summary.get('status') != 'Caution' and summary.get('status') != 'Consider Compensation':
            st.warning(summary.get('message', 'CAM compensation estimate unavailable for current selection.'))
            return

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Net ppm", f"{summary.get('ppm', 0.0):+.1f} ppm")
        col2.metric("Direction", summary.get('direction', 'Neutral'))
        col3.metric("Expansion holes", f"{summary.get('expansion_ratio', 0.0) * 100:.0f}%")
        col4.metric("Shrinkage holes", f"{summary.get('shrinkage_ratio', 0.0) * 100:.0f}%")

        st.caption(
            f"Valid holes: {summary.get('valid_points', 0)}/{summary.get('total_points', 0)} | "
            f"Mean radial shift: {summary.get('mean_radial_shift_um', 0.0):.3f} µm | "
            f"""Mean radius: {summary.get('mean_radius_um', 0.0):.1f} µm"""
        )
        st.info(summary.get('recommendation', 'Review CAM compensation thresholds and data quality.'))
