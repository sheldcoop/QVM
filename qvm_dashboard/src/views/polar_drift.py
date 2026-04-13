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

    @staticmethod
    def _compute_polar_health(plot_df: pd.DataFrame) -> dict:
        """Compute operator-facing polar health metrics and status."""
        if plot_df.empty:
            return {
                'status': 'No Data',
                'status_level': 'warning',
                'health_score': 0.0,
                'confidence': 0.0,
                'dominant_angle': 0.0,
                'direction_concentration': 0.0,
                'median_um': 0.0,
                'p90_um': 0.0,
                'outlier_ratio': 0.0,
                'summary': 'No valid drift points available.',
                'action': 'Upload valid DX/DY data to run machine health diagnostics.',
            }

        mags = plot_df['magnitude_um'].to_numpy(dtype=float)
        angles_rad = np.deg2rad(plot_df['angle_deg'].to_numpy(dtype=float))

        # Direction concentration in [0,1]: 1 means vectors align to one direction.
        mean_x = float(np.mean(np.cos(angles_rad)))
        mean_y = float(np.mean(np.sin(angles_rad)))
        concentration = float(np.clip(np.sqrt(mean_x ** 2 + mean_y ** 2), 0.0, 1.0))
        dominant_angle = float((math.degrees(math.atan2(mean_y, mean_x)) + 360.0) % 360.0)

        median_um = float(np.median(mags))
        p90_um = float(np.percentile(mags, 90))

        # Robust outlier detection using IQR.
        q1, q3 = np.percentile(mags, [25, 75])
        iqr = float(q3 - q1)
        outlier_threshold = float(q3 + 1.5 * iqr)
        outlier_mask = mags > outlier_threshold
        outlier_ratio = float(np.mean(outlier_mask)) if len(mags) else 0.0

        center_score = float(np.clip(1.0 - (median_um / 10.0), 0.0, 1.0))
        tail_score = float(np.clip(1.0 - (p90_um / 16.0), 0.0, 1.0))
        stability_score = float(np.clip(1.0 - outlier_ratio, 0.0, 1.0))
        # Prefer moderate concentration; both random and ultra-aligned can be suspicious.
        direction_balance = float(np.clip(1.0 - abs(concentration - 0.45) / 0.45, 0.0, 1.0))

        health_score = 100.0 * (
            0.40 * center_score +
            0.25 * tail_score +
            0.20 * stability_score +
            0.15 * direction_balance
        )

        confidence = 100.0 * (
            0.45 * stability_score +
            0.30 * float(np.clip(len(mags) / 16.0, 0.0, 1.0)) +
            0.25 * float(np.clip(1.0 - (p90_um - median_um) / 12.0, 0.0, 1.0))
        )

        if health_score >= 80:
            status = 'Stable - Run Normally'
            status_level = 'success'
            action = 'No immediate action. Continue routine verification checks.'
        elif health_score >= 65:
            status = 'Watch - Verify Alignment'
            status_level = 'warning'
            action = 'Run quick galvo/camera alignment check and confirm optical cleanliness.'
        elif health_score >= 45:
            status = 'At Risk - Process Review'
            status_level = 'warning'
            action = 'Review spindle/gantry vibration and circularity calibration before next lot.'
        else:
            status = 'Critical - Hold And Escalate'
            status_level = 'error'
            action = 'Hold run and escalate to machine + process engineering team.'

        if outlier_ratio >= 0.20:
            summary = 'Spike-dominant behavior detected (possible contamination or sporadic vision miss).' 
        elif concentration >= 0.70:
            summary = f'Directional drift bias detected near {dominant_angle:.0f}° (possible alignment skew).'
        elif concentration <= 0.20 and p90_um > 8.0:
            summary = 'Broad ring-like spread detected (possible circularity/beam profile issue).'
        else:
            summary = 'Drift cloud appears balanced with no dominant failure signature.'

        return {
            'status': status,
            'status_level': status_level,
            'health_score': round(health_score, 1),
            'confidence': round(confidence, 1),
            'dominant_angle': round(dominant_angle, 1),
            'direction_concentration': round(concentration * 100.0, 1),
            'median_um': round(median_um, 3),
            'p90_um': round(p90_um, 3),
            'outlier_ratio': round(outlier_ratio * 100.0, 1),
            'summary': summary,
            'action': action,
            'outlier_threshold_um': outlier_threshold,
        }

    def _render_operator_summary(self, metrics: dict, plot_df: pd.DataFrame) -> None:
        """Render operator-first status summary for polar machine health."""
        st.markdown('### Operator View: Polar Machine Health')

        status_text = (
            f"Shift status: {metrics['status']}. "
            f"Polar health {metrics['health_score']:.1f}/100, "
            f"confidence {metrics['confidence']:.1f}%"
        )

        if metrics['status_level'] == 'success':
            st.success(status_text)
        elif metrics['status_level'] == 'error':
            st.error(status_text)
        else:
            st.warning(status_text)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Polar Health', f"{metrics['health_score']:.1f}/100")
        c2.metric('Diagnosis Confidence', f"{metrics['confidence']:.1f}%")
        c3.metric('Dominant Angle', f"{metrics['dominant_angle']:.1f}°")
        c4.metric('Outliers', f"{metrics['outlier_ratio']:.1f}%")

        st.caption(
            f"Median drift: {metrics['median_um']:.3f} µm | "
            f"P90 drift: {metrics['p90_um']:.3f} µm | "
            f"Direction concentration: {metrics['direction_concentration']:.1f}%"
        )
        st.info(f"Diagnostic summary: {metrics['summary']}")
        st.info(f"Recommended action: {metrics['action']}")

        # Side-to-side delta helps isolate Front/Back related process shifts.
        if 'Side' in plot_df.columns and {'F', 'B'}.issubset(set(plot_df['Side'].astype(str).unique())):
            f_df = plot_df[plot_df['Side'].astype(str) == 'F']
            b_df = plot_df[plot_df['Side'].astype(str) == 'B']
            if not f_df.empty and not b_df.empty:
                fx = float(np.mean(f_df['dx_um']))
                fy = float(np.mean(f_df['dy_um']))
                bx = float(np.mean(b_df['dx_um']))
                by = float(np.mean(b_df['dy_um']))
                side_delta = float(np.sqrt((fx - bx) ** 2 + (fy - by) ** 2))
                st.caption(f"Front vs Back mean vector delta: {side_delta:.3f} µm")
    
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

        metrics = self._compute_polar_health(plot_df)
        self._render_operator_summary(metrics, plot_df)

        # Mark outliers for visual separation.
        plot_df = plot_df.copy()
        plot_df['is_outlier'] = plot_df['magnitude_um'] > metrics['outlier_threshold_um']
        
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
        plot_df['dx_um'] = (plot_df[dx_col] * 1000).round(3)
        plot_df['dy_um'] = (plot_df[dy_col] * 1000).round(3)
        
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
                                size=np.where(data['is_outlier'], 14, 10),
                                color=quadrant_colors[quadrant],
                                symbol=marker_symbol,
                                line=dict(
                                    width=np.where(data['is_outlier'], 2, 1),
                                    color=np.where(data['is_outlier'], '#FFFF00', 'rgba(0,0,0,0.3)')
                                )
                            ),
                            text=data['Location'],
                            customdata=np.column_stack((
                                data['Location'],
                                data['dx_um'],
                                data['dy_um'],
                                data['magnitude_um'],
                                data['angle_deg'],
                                data['is_outlier']
                            )),
                            hovertemplate=(
                                '<b>%{customdata[0]}</b><br>' +
                                'DX: %{customdata[1]:.3f} µm<br>' +
                                'DY: %{customdata[2]:.3f} µm<br>' +
                                'Magnitude: %{customdata[3]:.3f} µm<br>' +
                                'Angle: %{customdata[4]:.1f}°<br>' +
                                'Outlier: %{customdata[5]}<extra></extra>'
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
                            size=np.where(data['is_outlier'], 14, 10),
                            color=quadrant_colors[quadrant],
                            line=dict(
                                width=np.where(data['is_outlier'], 2, 1),
                                color=np.where(data['is_outlier'], '#FFFF00', 'rgba(0,0,0,0.3)')
                            )
                        ),
                        text=data['Location'],
                        customdata=np.column_stack((
                            data['Location'],
                            data['dx_um'],
                            data['dy_um'],
                            data['magnitude_um'],
                            data['angle_deg'],
                            data['is_outlier']
                        )),
                        hovertemplate=(
                            '<b>%{customdata[0]}</b><br>' +
                            'DX: %{customdata[1]:.3f} µm<br>' +
                            'DY: %{customdata[2]:.3f} µm<br>' +
                            'Magnitude: %{customdata[3]:.3f} µm<br>' +
                            'Angle: %{customdata[4]:.1f}°<br>' +
                            'Outlier: %{customdata[5]}<extra></extra>'
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
            height=chart_heights.get('analytics_plot', 600),
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

        st.markdown(
            "**Meaning of points near 90° or 270°**\n\n"
            "In this chart convention:\n"
            "- 0° = +DX direction\n"
            "- 90° = +DY direction\n"
            "- 180° = -DX direction\n"
            "- 270° = -DY direction\n\n"
            "So if points cluster near:\n"
            "- 90°: drift is mostly in +Y direction\n"
            "- 270°: drift is mostly in -Y direction\n\n"
            "Useful insight:\n"
            "- Strong cluster at 90° or 270° can indicate Y-axis directional bias (alignment/calibration skew).\n"
            "- Mix around both 90° and 270° can indicate back-and-forth Y oscillation/vibration pattern.\n"
            "- If Front and Back show different angle clusters, that hints at side-dependent setup/process effects.\n\n"
            "Most useful interpretation is always angle + magnitude together:\n"
            "- angle tells direction of error\n"
            "- radial (distance from center) tells severity of error"
        )
