"""
Optical Edge Confidence View - Point count analysis for hole integrity and plating quality
Extracted from app.py for modularity and reusability.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import hashlib

from src.views.base import BaseView


class OpticalEdgeConfidenceView(BaseView):
    """
    OpticalEdgeConfidenceView: Analyzes Point Count (Pts.) metric for optical inspection.
    
    Features:
    - Via/Pad health bar charts with traffic light logic (green/orange/red)
    - Pad vs Via separation scatter plot with box plots
    - Detailed analysis tables sorted by lowest point count
    """

    @staticmethod
    def _tier_to_operator_status(risk_tier: str) -> tuple[str, str]:
        """Map model tier to operator-facing status label and message type."""
        mapping = {
            'Tier A': ('Stable - Run Normally', 'success'),
            'Tier B': ('Watch - Verify Machine', 'warning'),
            'Tier C': ('At Risk - Process Review Needed', 'warning'),
            'Tier D': ('Critical - Hold And Escalate', 'error'),
        }
        return mapping.get(risk_tier, ('Unknown - Review Needed', 'warning'))

    @staticmethod
    def _driver_to_owner_action(driver: str) -> tuple[str, str]:
        """Map explainability driver to owner and immediate check action."""
        mapping = {
            'Low Pad edge points': ('CAM/Imaging', 'Check pad edge detect window and thresholding.'),
            'Low Via edge points': ('Machine', 'Clean optics and verify via focus/lighting.'),
            'Pad-Via mismatch': ('CAM + Machine', 'Verify registration model and camera alignment.'),
            'High PtV shift': ('Material', 'Review lamination behavior and stack-up stability.'),
            'High vector shift': ('Machine', 'Run calibration and verify X/Y correction map.'),
        }
        return mapping.get(driver, ('Engineering', 'Review trend and inspect raw captures.'))

    @staticmethod
    def _deterministic_jitter(labels: pd.Series, scale: float, salt: str) -> np.ndarray:
        """Generate stable jitter values so points do not shift across reruns."""
        values = []
        for label in labels.astype(str).tolist():
            digest = hashlib.md5(f"{salt}:{label}".encode('utf-8')).hexdigest()
            normalized = int(digest[:8], 16) / 0xFFFFFFFF
            values.append((normalized * 2.0 - 1.0) * scale)
        return np.array(values)

    @staticmethod
    def _compute_optical_confidence(
        filtered_df: pd.DataFrame,
        pad_pts_col: str,
        via_pts_col: str,
        model_cfg: dict,
    ) -> tuple[pd.DataFrame, dict]:
        """Compute per-hole normalized optical confidence and panel-level summary."""
        required_cols = [pad_pts_col, via_pts_col, 'PtV Distance', 'Shift (DX)', 'Shift (DY)', 'Location', 'Grid ID']
        work_df = filtered_df.copy()
        total_rows = len(work_df)

        for col in [pad_pts_col, via_pts_col, 'PtV Distance', 'Shift (DX)', 'Shift (DY)']:
            work_df[col] = pd.to_numeric(work_df[col], errors='coerce')

        valid_df = work_df.dropna(subset=required_cols).copy()

        if valid_df.empty:
            return valid_df, {
                'status': 'insufficient_data',
                'message': 'No valid rows available to compute optical confidence.',
                'panel_score': 0.0,
                'panel_worst10': 0.0,
                'panel_uncertainty': 1.0,
                'quadrant_consistency': 0.0,
                'panel_confidence': 0.0,
                'risk_tier': 'Tier D',
                'recommended_action': 'Hold lot and perform engineering review before release.',
                'flagged_count': 0,
                'valid_rows': 0,
                'total_rows': total_rows,
            }

        pad_target = float(model_cfg.get('pad_pts_target', 180.0))
        via_target = float(model_cfg.get('via_pts_target', 70.0))
        pad_floor = float(model_cfg.get('pad_pts_floor', 40.0))
        via_floor = float(model_cfg.get('via_pts_floor', 25.0))
        ratio_tolerance = float(model_cfg.get('pad_via_ratio_tolerance', 0.30))
        ptv_ref_um = float(model_cfg.get('ptv_ref_um', 6.0))
        shift_ref_um = float(model_cfg.get('shift_ref_um', 6.0))

        w_pad = float(model_cfg.get('weight_pad', 0.25))
        w_via = float(model_cfg.get('weight_via', 0.25))
        w_ratio = float(model_cfg.get('weight_ratio', 0.15))
        w_ptv = float(model_cfg.get('weight_ptv', 0.20))
        w_shift = float(model_cfg.get('weight_shift', 0.15))
        w_sum = w_pad + w_via + w_ratio + w_ptv + w_shift
        if w_sum <= 0:
            w_pad, w_via, w_ratio, w_ptv, w_shift = 0.25, 0.25, 0.15, 0.20, 0.15
            w_sum = 1.0

        w_pad /= w_sum
        w_via /= w_sum
        w_ratio /= w_sum
        w_ptv /= w_sum
        w_shift /= w_sum

        pad_norm = np.clip((valid_df[pad_pts_col] - pad_floor) / max(pad_target - pad_floor, 1e-6), 0.0, 1.0)
        via_norm = np.clip((valid_df[via_pts_col] - via_floor) / max(via_target - via_floor, 1e-6), 0.0, 1.0)

        ratio_actual = valid_df[via_pts_col] / np.maximum(valid_df[pad_pts_col], 1.0)
        ratio_target = via_target / max(pad_target, 1e-6)
        ratio_score = 1.0 - np.clip(np.abs(ratio_actual - ratio_target) / max(ratio_tolerance, 1e-6), 0.0, 1.0)

        ptv_um = np.abs(valid_df['PtV Distance']) * 1000.0
        shift_um = np.sqrt(valid_df['Shift (DX)'] ** 2 + valid_df['Shift (DY)'] ** 2) * 1000.0
        ptv_score = np.exp(-ptv_um / max(ptv_ref_um, 1e-6))
        shift_score = np.exp(-shift_um / max(shift_ref_um, 1e-6))

        hole_score = 100.0 * (
            (w_pad * pad_norm) +
            (w_via * via_norm) +
            (w_ratio * ratio_score) +
            (w_ptv * ptv_score) +
            (w_shift * shift_score)
        )

        evidence_quality = 0.5 * (pad_norm + via_norm)
        metrology_consistency = 0.5 * (ptv_score + shift_score)
        hole_uncertainty = np.clip(1.0 - (0.6 * evidence_quality + 0.4 * metrology_consistency), 0.0, 1.0)

        def _primary_driver(row) -> str:
            deficits = {
                'Low Pad edge points': 1.0 - float(row['_pad_norm']),
                'Low Via edge points': 1.0 - float(row['_via_norm']),
                'Pad-Via mismatch': 1.0 - float(row['_ratio_score']),
                'High PtV shift': 1.0 - float(row['_ptv_score']),
                'High vector shift': 1.0 - float(row['_shift_score']),
            }
            return max(deficits, key=deficits.get)

        valid_df['_pad_norm'] = pad_norm
        valid_df['_via_norm'] = via_norm
        valid_df['_ratio_score'] = ratio_score
        valid_df['_ptv_score'] = ptv_score
        valid_df['_shift_score'] = shift_score
        valid_df['Optical Score'] = hole_score.round(2)
        valid_df['Optical Uncertainty'] = (hole_uncertainty * 100.0).round(2)
        valid_df['Primary Driver'] = valid_df.apply(_primary_driver, axis=1)
        valid_df['Quadrant'] = valid_df['Location'].astype(str).str.split('_').str[0]

        def _hole_risk_tier(score: float) -> str:
            if score >= 80:
                return 'Tier A'
            if score >= 65:
                return 'Tier B'
            if score >= 45:
                return 'Tier C'
            return 'Tier D'

        valid_df['Risk Tier'] = valid_df['Optical Score'].apply(_hole_risk_tier)

        panel_score = float(valid_df['Optical Score'].median())
        panel_worst10 = float(valid_df['Optical Score'].quantile(0.10))
        panel_uncertainty = float((valid_df['Optical Uncertainty'] / 100.0).mean())

        quadrant_medians = valid_df.groupby('Quadrant')['Optical Score'].median()
        if len(quadrant_medians) > 1:
            quadrant_consistency = float(np.clip(1.0 - (quadrant_medians.std() / 35.0), 0.0, 1.0))
        else:
            quadrant_consistency = 0.5

        missing_ratio = float(np.clip(1.0 - (len(valid_df) / max(total_rows, 1)), 0.0, 1.0))
        panel_confidence = float(np.clip((1.0 - panel_uncertainty) * quadrant_consistency * (1.0 - 0.7 * missing_ratio), 0.0, 1.0))

        if panel_score >= 80 and panel_worst10 >= 65 and panel_uncertainty <= 0.25:
            panel_tier = 'Tier A'
            action = 'Monitor only. Continue current recipe and routine checks.'
        elif panel_score >= 65 and panel_worst10 >= 50:
            panel_tier = 'Tier B'
            action = 'Machine check recommended: verify focus, calibration, and optics cleanliness.'
        elif panel_score >= 45:
            panel_tier = 'Tier C'
            action = 'Material/lamination review advised: inspect stack-up behavior and warp/twist factors.'
        else:
            panel_tier = 'Tier D'
            action = 'Hold lot and trigger CAM + machine + material joint review before release.'

        flagged_count = int((valid_df['Optical Score'] < 65).sum())

        # Cleanup helper columns
        valid_df = valid_df.drop(columns=['_pad_norm', '_via_norm', '_ratio_score', '_ptv_score', '_shift_score'])

        summary = {
            'status': 'ok',
            'message': 'Optical confidence calculated.',
            'panel_score': panel_score,
            'panel_worst10': panel_worst10,
            'panel_uncertainty': panel_uncertainty,
            'quadrant_consistency': quadrant_consistency,
            'panel_confidence': panel_confidence,
            'risk_tier': panel_tier,
            'recommended_action': action,
            'flagged_count': flagged_count,
            'valid_rows': int(len(valid_df)),
            'total_rows': int(total_rows),
            'operator_checklist': [
                'Verify flagged holes first (lowest score to highest score).',
                'Confirm optics cleanliness and focus before rerun.',
                'Escalate to CAM/Material only if machine checks pass.',
            ],
        }
        return valid_df, summary

    @staticmethod
    def _render_confidence_summary(summary: dict) -> None:
        """Render panel-level confidence metrics and recommended action."""
        st.markdown("### Operator View: Optical Health")

        if summary.get('status') != 'ok':
            st.info(summary.get('message', 'Optical confidence unavailable.'))
            return

        status_label, status_level = OpticalEdgeConfidenceView._tier_to_operator_status(summary.get('risk_tier', 'Tier D'))
        status_text = (
            f"Shift status: {status_label}. "
            f"Confidence {summary.get('panel_confidence', 0.0) * 100:.1f}%. "
            f"Flagged holes: {summary.get('flagged_count', 0)}."
        )
        if status_level == 'success':
            st.success(status_text)
        elif status_level == 'error':
            st.error(status_text)
        else:
            st.warning(status_text)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric('Panel Health', f"{summary.get('panel_score', 0.0):.1f}/100")
        col2.metric('Worst Zone', f"{summary.get('panel_worst10', 0.0):.1f}/100")
        col3.metric('Diagnosis Confidence', f"{summary.get('panel_confidence', 0.0) * 100:.1f}%")
        col4.metric('Action Level', summary.get('risk_tier', 'Tier D'))

        st.caption(
            f"Uncertainty: {summary.get('panel_uncertainty', 1.0) * 100:.1f}% | "
            f"Zone consistency: {summary.get('quadrant_consistency', 0.0) * 100:.1f}% | "
            f"Flagged holes: {summary.get('flagged_count', 0)}"
        )
        st.info(f"Recommended action: {summary.get('recommended_action', 'Review process settings.')}" )

        checklist = summary.get('operator_checklist', [])
        if checklist:
            st.markdown('**Next checks (operator sequence):**')
            for idx, item in enumerate(checklist, start=1):
                st.write(f"{idx}. {item}")

    @staticmethod
    def _render_flagged_holes(confidence_df: pd.DataFrame) -> None:
        """Render highest-priority flagged holes with explainability."""
        if confidence_df.empty:
            return

        flagged = confidence_df[confidence_df['Optical Score'] < 65].copy()
        if flagged.empty:
            st.success('No holes currently flagged by Optical Confidence model (score < 65).')
            return

        st.markdown("### 🚩 Flagged Holes (Priority Review)")
        flagged = flagged.sort_values(by='Optical Score', ascending=True)
        flagged['Owner'], flagged['What To Check'] = zip(*flagged['Primary Driver'].map(OpticalEdgeConfidenceView._driver_to_owner_action))
        display_cols = [
            'Location', 'Grid ID', 'Optical Score', 'Optical Uncertainty',
            'Risk Tier', 'Primary Driver', 'Owner', 'What To Check', 'PtV Distance', 'Shift (DX)', 'Shift (DY)'
        ]
        flagged_display = flagged[display_cols].copy()
        flagged_display['PtV (µm)'] = (flagged_display['PtV Distance'] * 1000).round(3)
        flagged_display['Shift DX (µm)'] = (flagged_display['Shift (DX)'] * 1000).round(3)
        flagged_display['Shift DY (µm)'] = (flagged_display['Shift (DY)'] * 1000).round(3)
        flagged_display = flagged_display.drop(columns=['PtV Distance', 'Shift (DX)', 'Shift (DY)'])
        st.dataframe(flagged_display, use_container_width=True, hide_index=True)
    
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
        optical_model = kwargs.get('optical_model', {})
        
        # Check if required columns exist
        pad_pts_col = 'Pad Pts.'
        via_pts_col = 'Via Pts.'
        
        if pad_pts_col not in filtered_df.columns or via_pts_col not in filtered_df.columns:
            st.error(f"Columns '{pad_pts_col}' and/or '{via_pts_col}' not found in data. Available columns: {list(filtered_df.columns)}")
            return

        confidence_df, panel_summary = self._compute_optical_confidence(
            filtered_df, pad_pts_col, via_pts_col, optical_model
        )
        self._render_confidence_summary(panel_summary)
        self._render_flagged_holes(confidence_df)
        
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
                jitter = OpticalEdgeConfidenceView._deterministic_jitter(scatter_df['Location'], 0.04, 'pad')
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
                jitter = OpticalEdgeConfidenceView._deterministic_jitter(scatter_df['Location'], 0.04, 'via')
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
