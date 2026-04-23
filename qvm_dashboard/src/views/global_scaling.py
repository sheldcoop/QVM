"""Global Scaling Calculator — Pad-to-Via sub-view.

Engineers input DX/DY offsets for the 4 outermost corner fiducials and the
tool computes the Global X/Y Scaling Factors (and PPM) needed for CAM
compensation.  Inputs are auto-populated from the uploaded PtV file.
"""

import streamlit as st
import pandas as pd

from .base import BaseView
from src.visuals import plot_scaling_panel


_CORNER_ORDER = ['UL', 'UR', 'LL', 'LR']


def _scale_status(scale: float) -> str:
    if scale < 1.0 - 1e-6:
        return 'SHRUNK'
    if scale > 1.0 + 1e-6:
        return 'STRETCHED'
    return 'NOMINAL'


def _badge_color(status: str, chart_colors: dict) -> str:
    return {
        'SHRUNK':    chart_colors.get('traffic_light_orange', '#f39c12'),
        'STRETCHED': chart_colors.get('traffic_light_red',    '#e74c3c'),
        'NOMINAL':   chart_colors.get('traffic_light_green',  '#2ecc71'),
    }.get(status, '#999999')


class GlobalScalingView(BaseView):
    """Interactive Global X/Y Scaling Calculator for CAM compensation."""

    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        gs_cfg      = self.settings.get('GLOBAL_SCALING', {})
        corners_cfg = gs_cfg.get('corners', {})
        rng         = float(gs_cfg.get('slider_range_mm', 0.05))
        step        = float(gs_cfg.get('slider_step_mm', 0.0001))
        exag_def    = int(gs_cfg.get('exaggeration_default', 2000))
        exag_min    = int(gs_cfg.get('exaggeration_min', 100))
        exag_max    = int(gs_cfg.get('exaggeration_max', 10000))

        dx_col  = self.col_names.get('x_distance', 'Shift (DX)')
        dy_col  = self.col_names.get('y_distance', 'Shift (DY)')
        grid_col = self.col_names.get('grid_id', 'Grid ID')

        st.subheader("Global Scaling Calculator")
        st.write(
            "Enter the DX/DY registration offsets for the 4 outermost corner fiducials. "
            "Inputs are pre-filled from the uploaded file. Adjust if needed."
        )

        # ── Section A: Corner inputs ──────────────────────────────────────
        st.markdown("#### Corner Fiducial Offsets")
        cols = st.columns(4)
        inputs: dict[str, dict] = {}

        for col_ui, label in zip(cols, _CORNER_ORDER):
            cfg = corners_cfg.get(label, {})
            gid = int(cfg.get('grid_id', 0))
            nom_x = float(cfg.get('x', 0.0))
            nom_y = float(cfg.get('y', 0.0))

            # Auto-populate from file
            match = filtered_df[pd.to_numeric(filtered_df[grid_col], errors='coerce') == gid]
            if not match.empty:
                file_dx = float(match[dx_col].iloc[0])
                file_dy = float(match[dy_col].iloc[0])
                note = f"Grid {gid} · from file"
            else:
                file_dx, file_dy = 0.0, 0.0
                note = f"Grid {gid} · **not found in upload**"

            with col_ui:
                st.markdown(f"**{label}** — {note}")
                dx_val = st.number_input(
                    f"DX {label} (mm)",
                    min_value=-rng, max_value=rng,
                    value=file_dx, step=step, format="%.4f",
                    key=f"gs_dx_{label}",
                )
                dy_val = st.number_input(
                    f"DY {label} (mm)",
                    min_value=-rng, max_value=rng,
                    value=file_dy, step=step, format="%.4f",
                    key=f"gs_dy_{label}",
                )

            inputs[label] = {'nom_x': nom_x, 'nom_y': nom_y, 'dx': dx_val, 'dy': dy_val}

        st.markdown("---")

        # ── Section B: Math engine ────────────────────────────────────────
        ul, ur, ll, lr = (inputs[k] for k in _CORNER_ORDER)

        # Step A — nominal spans
        nom_x_span = ((ur['nom_x'] + lr['nom_x']) / 2) - ((ul['nom_x'] + ll['nom_x']) / 2)
        nom_y_span = ((ul['nom_y'] + ur['nom_y']) / 2) - ((ll['nom_y'] + lr['nom_y']) / 2)

        # Step B — actual positions and actual spans
        act_ul_x = ul['nom_x'] + ul['dx'];  act_ul_y = ul['nom_y'] + ul['dy']
        act_ur_x = ur['nom_x'] + ur['dx'];  act_ur_y = ur['nom_y'] + ur['dy']
        act_ll_x = ll['nom_x'] + ll['dx'];  act_ll_y = ll['nom_y'] + ll['dy']
        act_lr_x = lr['nom_x'] + lr['dx'];  act_lr_y = lr['nom_y'] + lr['dy']

        act_x_span = ((act_ur_x + act_lr_x) / 2) - ((act_ul_x + act_ll_x) / 2)
        act_y_span = ((act_ul_y + act_ur_y) / 2) - ((act_ll_y + act_lr_y) / 2)

        # Step C — scale factors and PPM
        scale_x = act_x_span / nom_x_span if nom_x_span != 0 else 1.0
        scale_y = act_y_span / nom_y_span if nom_y_span != 0 else 1.0
        ppm_x   = (scale_x - 1.0) * 1_000_000
        ppm_y   = (scale_y - 1.0) * 1_000_000

        status_x = _scale_status(scale_x)
        status_y = _scale_status(scale_y)

        # ── Section C: Output display ─────────────────────────────────────
        st.markdown("#### Scaling Results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Scale X", f"{scale_x:.6f}")
        c2.metric("Scale Y", f"{scale_y:.6f}")
        c3.metric("PPM X",   f"{ppm_x:+.1f} ppm")
        c4.metric("PPM Y",   f"{ppm_y:+.1f} ppm")

        # Badges
        badge_x_color = _badge_color(status_x, self.chart_colors)
        badge_y_color = _badge_color(status_y, self.chart_colors)
        st.markdown(
            f'<span style="background:{badge_x_color};color:#fff;'
            f'padding:3px 10px;border-radius:4px;font-weight:600;margin-right:12px;">'
            f'X: {status_x}</span>'
            f'<span style="background:{badge_y_color};color:#fff;'
            f'padding:3px 10px;border-radius:4px;font-weight:600;">'
            f'Y: {status_y}</span>',
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # ── Section D: Panel visualization ────────────────────────────────
        st.markdown("#### Corner Displacement Map")
        exaggeration = st.slider(
            "Exaggeration multiplier (rendering only — does not affect math)",
            min_value=exag_min, max_value=exag_max, value=exag_def, step=100,
        )

        # Attach scale_status to each corner for arrow coloring
        for label, status in zip(_CORNER_ORDER, [status_x, status_y, status_x, status_y]):
            inputs[label]['scale_status'] = status
        # Use overall panel status per corner: color by whichever axis dominates
        inputs['UL']['scale_status'] = status_x if abs(ppm_x) >= abs(ppm_y) else status_y
        inputs['UR']['scale_status'] = inputs['UL']['scale_status']
        inputs['LL']['scale_status'] = inputs['UL']['scale_status']
        inputs['LR']['scale_status'] = inputs['UL']['scale_status']

        fig = plot_scaling_panel(inputs, self.settings, exaggeration)
        st.plotly_chart(fig, use_container_width=True)

        st.caption(
            f"Nominal X span: {nom_x_span:.4f} mm | "
            f"Actual X span: {act_x_span:.4f} mm | "
            f"Nominal Y span: {nom_y_span:.4f} mm | "
            f"Actual Y span: {act_y_span:.4f} mm"
        )
