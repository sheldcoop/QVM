"""Core Shrinkage view — 3-level model across 3 sub-views (PTV/VTP style).

The Front/Back/Both scope is chosen by the shared Analysis Scope buttons in
app.py (`_scope_filters`); the sub-view (Quality Control / Analytics /
Distortion Map) is chosen by `render_nav_buttons` in app.py and passed in.

The three sub-views are a deliberate drill-down:
  - Quality Control  global headline ppm + pass/fail + outlier flag (operator)
  - Analytics        Global → Per-quadrant (QP) → Per-dot → Front vs Back
  - Distortion Map   residual vector field, dots zone-coloured, bad dots ringed

Nominal CAM coordinates come from settings CORE_SHRINKAGE.NOMINAL_COORDS.
Units: deviations/residuals in µm, shrinkage in ppm, rotation/shear in degrees.
"""

import logging
from io import BytesIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.views.base import BaseView, full_width
from src.chart_helpers import apply_dark_layout
from src.panel_mapping import get_rounded_rect_path
from src import theme
from src.core_shrinkage_parser import (
    layer_frame,
    both_frame,
    analyze_layer,
    compute_scale_factor,
    compute_affine_analysis,
    compute_shrinkage_summary,
    summary_frame,
    qp_shrinkage_um,
    affine_residuals_um,
    compute_front_back_registration,
    compute_deviation_field,
    compute_centered_deviation_table,
)
from src.excel_export import write_core_shrinkage_excel

# Direction → arrow/marker colour (reuses the shared ABF distortion palette).
_KLASS_COLOR = {
    "expansion": theme.ARROW["expansion"],  # outward — red
    "contraction": theme.ARROW["contraction"],  # inward  — sky
    "twist": theme.ARROW["twist"],  # tangential — yellow
    "stable": theme.ARROW["offset"],  # negligible — blue
    "outlier": theme.ZONE["fail"],  # flagged bad dot — red ring
}
_KLASS_LABEL = {
    "expansion": "Expansion",
    "contraction": "Contraction",
    "twist": "Twist",
    "stable": "Stable",
    "outlier": "Outlier",
}

# Etched-panel look: darker copper substrate, bright shiny copper pads.
_BLOCK_COPPER = "#9C5E2E"  # substrate (darker so pads stand out)
_BLOCK_EDGE = "#5E3415"
_PAD_COPPER = "#F0A24E"  # shiny etched-copper pad
_PAD_RIM = "#FFE0B0"  # light rim = sheen

logger = logging.getLogger(__name__)


class CoreShrinkageView(BaseView):
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        sub_view = kwargs.get("sub_view", "Quality Control")
        meta = kwargs.get("meta", {}) or {}
        cs_cfg = self.settings.get("CORE_SHRINKAGE", {})
        nominal = cs_cfg.get("NOMINAL_COORDS", {})
        logger.info("Rendering CoreShrinkageView (%s)", sub_view)

        front_df = filtered_df[filtered_df["layer"] == "Front"].copy()
        back_df = filtered_df[filtered_df["layer"] == "Back"].copy()
        if front_df.empty and back_df.empty:
            st.warning("No data available.")
            return
        if not nominal:
            st.warning(
                "CORE_SHRINKAGE.NOMINAL_COORDS missing from settings — "
                "shrinkage analysis unavailable. Showing raw coordinates."
            )
            self._raw_tables(front_df, back_df)
            return

        layers = [
            (lbl, ldf)
            for lbl, ldf in (("Front", front_df), ("Back", back_df))
            if not ldf.empty
        ]

        if sub_view == "Quality Control":
            self._quality_control(layers, nominal)
        elif sub_view == "Analytics":
            self._analytics(layers, front_df, back_df, nominal)
        elif sub_view == "Distortion Map":
            self._distortion_map(layers, nominal, cs_cfg)
        elif sub_view == "Method":
            _method()
            return  # explainer is static — no export button needed

        st.markdown("---")
        self._show_export(front_df, back_df, meta, nominal)

    # -- shared scope helpers ------------------------------------------------

    def _analyze(self, ldf: pd.DataFrame, nominal: dict) -> dict:
        """Single-pass analysis for one layer (fit + outliers + rigid), computed
        once and reused by every builder in the active sub-view."""
        return analyze_layer(ldf, nominal, self.settings)

    def _outlier_um(self) -> float:
        return float(self.settings.get("CORE_SHRINKAGE", {}).get("outlier_um", 50.0))

    # -- Sub-view 1: Quality Control ----------------------------------------

    def _quality_control(self, layers, nominal) -> None:
        usl = float(
            self.settings.get("CORE_SHRINKAGE", {}).get("shrink_usl_ppm", 1000.0)
        )
        for lbl, ldf in layers:
            a = self._analyze(ldf, nominal)
            s = compute_shrinkage_summary(ldf, nominal, self.settings, analysis=a)
            st.subheader(f"{lbl} — Quality Control")
            if not s:
                st.info(
                    "Needs at least 4 matched fiducials with a valid "
                    "(non-degenerate) fit — otherwise no headline is reported."
                )
                continue

            worst = max(abs(s["Sx_ppm_robust"]), abs(s["Sy_ppm_robust"]))
            passed = worst <= usl and s["n_outliers"] == 0

            c = st.columns(6)
            c[0].metric("X Scale", _ppm_dir(s["Sx_ppm_robust"]))
            c[1].metric("Y Scale", _ppm_dir(s["Sy_ppm_robust"]))
            c[2].metric("Residual RMS", f"{s['residual_rms_um']:.1f} µm")
            c[3].metric("Max deviation", f"{s['max_residual_um']:.1f} µm")
            c[4].metric(
                "Outliers",
                s["n_outliers"],
                delta="remeasure" if s["n_outliers"] else "✓ none",
                delta_color="inverse" if s["n_outliers"] else "off",
            )
            c[5].metric(
                "Status",
                "PASS" if passed else "FAIL",
                delta=None if passed else "action",
                delta_color="off" if passed else "inverse",
            )

            if s["n_outliers"]:
                st.caption(
                    f"⚠️ Outlier dot(s) excluded from the headline ppm: "
                    f"**{', '.join(s['outliers'])}** — likely bad/misdetected pad(s), remeasure. "
                    f"All-dot scale (skewed): X {s['Sx_ppm']:.0f} / Y {s['Sy_ppm']:.0f} ppm."
                )
            else:
                st.caption(
                    f"Rotation {s['rotation_deg']:.3f}° · Shear {s['shear_deg']:.3f}° · "
                    f"{s['n_points']} fiducials · spec ±{usl:.0f} ppm · "
                    f"sign: **− shrink / + expand** (measured − nominal)."
                )

            st.dataframe(
                self._styled_residuals(ldf, nominal, a),
                width="stretch",
                hide_index=True,
            )
            st.markdown("---")

    def _styled_residuals(self, ldf: pd.DataFrame, nominal: dict, a: dict):
        """Per-dot deviation table (µm) with outlier rows highlighted red."""
        aff = compute_affine_analysis(ldf, nominal, self.settings, analysis=a)
        res = affine_residuals_um(aff, self._outlier_um())
        if res.empty:
            return res
        res.insert(1, "Grid", res["location"].map(a.get("grid_map", {})))
        return res.style.apply(_highlight_outlier, axis=1)

    # -- Sub-view 2: Analytics ----------------------------------------------

    def _analytics(self, layers, front_df, back_df, nominal) -> None:
        # One analysis per layer for the whole sub-view (no repeat fitting).
        ana = {lbl: self._analyze(ldf, nominal) for lbl, ldf in layers}
        t_global, t_qp, t_dot, t_coord, t_fb = st.tabs(
            [
                "🌐 Global",
                "🔍 Per-quadrant (QP)",
                "🔬 Per-dot residuals",
                "📐 Coordinates",
                "🔁 Front vs Back",
            ]
        )

        with t_global:
            st.caption(
                "Whole-panel best-fit. Translation = datum offset (not a defect); "
                "robust ppm excludes flagged outlier dots. "
                "Shrinkage ppm sign: **− shrink / + expand** (measured − nominal)."
            )
            cols = st.columns(len(layers))
            for col, (lbl, ldf) in zip(cols, layers):
                with col:
                    st.markdown(f"**{lbl}**")
                    sframe = summary_frame(
                        compute_shrinkage_summary(
                            ldf, nominal, self.settings, analysis=ana[lbl]
                        )
                    )
                    if sframe.empty:
                        st.info("Needs ≥ 4 fiducials.")
                    else:
                        st.dataframe(sframe, width="stretch", hide_index=True)
            if len(layers) == 2 and ana["Front"] and ana["Back"]:
                tf, tb = (
                    ana["Front"]["fit"]["theta_deg"],
                    ana["Back"]["fit"]["theta_deg"],
                )
                st.info(
                    f"**Layer-to-layer twist:** {tf - tb:.4f}°  "
                    f"(Front {tf:.4f}° − Back {tb:.4f}°)"
                )

        with t_qp:
            st.caption(
                "Per-quadrant pitch error (µm) and ppm — the uniformity check. "
                "Quadrants close together ⇒ uniform. ppm: **− shrink / + expand**."
            )
            for lbl, ldf in layers:
                st.markdown(f"**{lbl}**")
                qp = qp_shrinkage_um(ldf)
                if qp.empty:
                    st.info("Needs all 16 fiducials.")
                    continue
                sf = compute_scale_factor(ldf)
                merged = pd.merge(
                    qp,
                    sf[["Quadrant", "X Shrinkage (ppm)", "Y Shrinkage (ppm)"]],
                    on="Quadrant",
                    how="right",
                )
                merged.loc[merged["Quadrant"] == "Overall", "Quadrant"] = (
                    "Full Panel (Avg)"
                )
                st.dataframe(merged, width="stretch", hide_index=True)
                chart = sf[sf["Quadrant"] != "Overall"].set_index("Quadrant")
                if not chart.empty:
                    st.bar_chart(chart[["X Shrinkage (ppm)", "Y Shrinkage (ppm)"]])

        with t_dot:
            st.caption(
                "Residual per dot after removing the best-fit transform — the "
                "defect locator. Outlier rows are flagged."
            )
            for lbl, ldf in layers:
                st.markdown(f"**{lbl}**")
                st.dataframe(
                    self._styled_residuals(ldf, nominal, ana[lbl]),
                    width="stretch",
                    hide_index=True,
                )

        with t_coord:
            st.caption(
                "CAM nominal vs raw physical vs physical re-centred on the CAM datum "
                "(machine setup removed), with the resulting Δ per dot (µm). The "
                "Δ Dist is the same total deviation shown on the Distortion Map."
            )
            for lbl, ldf in layers:
                st.markdown(f"**{lbl}**")
                st.dataframe(
                    compute_centered_deviation_table(
                        ldf, nominal, self.settings, analysis=ana[lbl]
                    ),
                    width="stretch",
                    hide_index=True,
                )

        with t_fb:
            if len(layers) == 2:
                st.caption("Front-pad vs Back-land overlay per dot (µm).")
                fb = compute_front_back_registration(front_df, back_df)
                st.dataframe(fb, width="stretch", hide_index=True)
            else:
                st.info("Front vs Back registration needs both layers uploaded.")

    # -- Sub-view 3: Distortion Map -----------------------------------------

    def _distortion_map(self, layers, nominal, cs_cfg) -> None:
        if len(layers) == 2:
            lbl = st.radio(
                "Layer",
                [name for name, _ in layers],
                horizontal=True,
                key="cs_dm_layer",
            )
            ldf = dict(layers)[lbl]
        else:
            lbl, ldf = layers[0]

        st.caption(
            "Each arrow = how far a pad sits from its CAM target (machine setup removed). "
            "Outward arrows = the panel **expanding** vs CAM; inward = shrinking. "
            "Arrow colour = direction; a red-ringed pad is a flagged outlier. "
            "Measured markers are magnified."
        )

        dev = compute_deviation_field(
            ldf, nominal, self.settings, "total", analysis=self._analyze(ldf, nominal)
        )
        if dev.empty:
            st.info("Distortion map needs at least 4 matched fiducials.")
            return

        scale = st.slider(
            "Arrow magnification",
            50,
            20000,
            200,
            step=50,
            key=f"cs_dm_scale_{lbl}",
            help="Displacements are tiny vs the panel; magnify to see the pattern.",
        )
        st.plotly_chart(
            self._distortion_fig(dev, nominal, lbl, scale),
            **full_width(st.plotly_chart),
        )

        st.markdown("---")
        st.caption(
            "**3D warp** — height = per-dot deviation (µm). Reveals panel bow/dish; "
            "drag to rotate."
        )
        st.plotly_chart(self._warp_surface(dev, lbl), **full_width(st.plotly_chart))

    def _panel_shapes(self, nominal):
        """Four equal copper quarter blocks separated by a clean cross-gap, drawn
        in the nominal-mm frame so every dot sits inside its block. No outer frame.
        Returns (shapes, (x0, x1, y0, y1)) — the tuple is the axis range incl. margin."""
        pv = self.settings.get("PANEL_VIEW", {})
        W = float(pv.get("frame_width", 510.0))
        H = float(pv.get("frame_height", 515.0))
        g = (
            8.0 / 2.0
        )  # half of the cross-gap (mm); ≈ the real centre gap so all dots stay inside

        xs = [c["x"] for c in nominal.values()]
        ys = [c["y"] for c in nominal.values()]
        cx = (min(xs) + max(xs)) / 2.0
        cy = (min(ys) + max(ys)) / 2.0
        hw, hh = W / 2.0, H / 2.0

        rects = {
            "UL": (cx - hw, cy + g, cx - g, cy + hh),
            "LL": (cx - hw, cy - hh, cx - g, cy - g),
            "LR": (cx + g, cy - hh, cx + hw, cy - g),
            "UR": (cx + g, cy + g, cx + hw, cy + hh),
        }
        shapes = [
            dict(
                type="path",
                path=get_rounded_rect_path(x0, y0, x1, y1, 14.0),
                fillcolor=_BLOCK_COPPER,
                line=dict(color=_BLOCK_EDGE, width=2),
                layer="below",
            )
            for (x0, y0, x1, y1) in rects.values()
        ]
        return shapes, (cx - hw - 12, cx + hw + 12, cy - hh - 12, cy + hh + 12), rects

    def _pad_positions(self, nominal, rects, pull: float = 0.22):
        """Display anchor for each pad: the true nominal pulled `pull` toward its
        block centre, so pads sit neatly inside each quarter — off the rounded
        corners and off the centre gap (deviation arrows keep their true direction)."""
        pos = {}
        for q, (x0, y0, x1, y1) in rects.items():
            bcx, bcy = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            for loc, c in nominal.items():
                if loc.startswith(q):
                    pos[loc] = (
                        c["x"] + (bcx - c["x"]) * pull,
                        c["y"] + (bcy - c["y"]) * pull,
                    )
        return pos

    def _distortion_fig(self, dev, nominal, lbl, scale):
        """2D vector field on the etched panel: copper pads (CAM anchor) + a
        class-coloured deviation arrow to the magnified measured point."""
        shapes, (rx0, rx1, ry0, ry1), rects = self._panel_shapes(nominal)
        pos = self._pad_positions(nominal, rects)

        nx, ny, labels, tpos = [], [], [], []
        mx, my, mcolor, hovers = [], [], [], []
        annotations, out_x, out_y = [], [], []
        for _, r in dev.iterrows():
            x0, y0 = pos.get(r["location"], (r["nom_x"], r["nom_y"]))
            x1 = x0 + (r["dev_x_um"] / 1000.0) * scale
            y1 = y0 + (r["dev_y_um"] / 1000.0) * scale
            col = _KLASS_COLOR.get(r["klass"], theme.ARROW["offset"])
            nx.append(x0)
            ny.append(y0)
            labels.append(r["location"])
            # Push label outward so centre-straddling pairs don't collide.
            tpos.append(
                ("top" if r["nom_y"] >= 0 else "bottom")
                + (" left" if r["nom_x"] < 0 else " right")
            )
            mx.append(x1)
            my.append(y1)
            mcolor.append(col)
            hovers.append(
                f"{r['location']} · <b>{_KLASS_LABEL.get(r['klass'], r['klass'])}</b>"
                f"<br>{r['mag_um']:.1f} µm (ΔX {r['dev_x_um']:.1f}, ΔY {r['dev_y_um']:.1f})"
            )
            annotations.append(
                dict(
                    ax=x0,
                    ay=y0,
                    x=x1,
                    y=y1,
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    arrowhead=2,
                    arrowcolor=col,
                    arrowwidth=2.0,
                    showarrow=True,
                    text="",
                )
            )
            if r["outlier"]:
                out_x.append(x0)
                out_y.append(y0)

        fig = go.Figure()
        # Copper pads (the physical fiducial / CAM anchor)
        fig.add_trace(
            go.Scatter(
                x=nx,
                y=ny,
                mode="markers+text",
                text=labels,
                textposition=tpos,
                textfont=dict(size=11, color="#f3e9dd", family="Arial Black"),
                hoverinfo="skip",
                name="Copper pad (CAM)",
                marker=dict(
                    symbol="circle",
                    size=16,
                    color=_PAD_COPPER,
                    line=dict(width=2.5, color=_PAD_RIM),
                ),
            )
        )
        # Magnified measured point, coloured by direction class
        fig.add_trace(
            go.Scatter(
                x=mx,
                y=my,
                mode="markers",
                hovertext=hovers,
                hoverinfo="text",
                name=f"Measured (×{scale})",
                marker=dict(size=8, color=mcolor, line=dict(width=1, color="#11111b")),
            )
        )
        if out_x:
            fig.add_trace(
                go.Scatter(
                    x=out_x,
                    y=out_y,
                    mode="markers",
                    name="Outlier (remeasure)",
                    marker=dict(
                        symbol="circle-open",
                        size=30,
                        color=theme.ZONE["fail"],
                        line=dict(width=4),
                    ),
                )
            )

        # Colour-meaning legend (bottom annotation) — keeps the plotly legend clean.
        present = [
            k
            for k in ("expansion", "contraction", "twist", "stable")
            if (dev["klass"] == k).any()
        ]
        legend_txt = "   ".join(
            f"<span style='color:{_KLASS_COLOR[k]}'>⬤</span> {_KLASS_LABEL[k]}"
            for k in present
        )

        apply_dark_layout(
            fig,
            height=560,
            plot_bgcolor=theme.PLOT_BG,
            shapes=shapes,
            annotations=annotations
            + (
                [
                    dict(
                        text=legend_txt,
                        xref="paper",
                        yref="paper",
                        x=0.5,
                        y=-0.04,
                        xanchor="center",
                        yanchor="top",
                        showarrow=False,
                        font=dict(size=11, color=theme.TEXT),
                        bgcolor=theme.CARD_BG,
                        bordercolor=theme.CARD_BD,
                        borderwidth=1,
                        borderpad=5,
                    )
                ]
                if legend_txt
                else []
            ),
            xaxis=dict(range=[rx0, rx1], scaleanchor="y", scaleratio=1, visible=False),
            yaxis=dict(range=[ry0, ry1], visible=False),
            legend=dict(
                orientation="v",
                yanchor="middle",
                y=0.5,
                xanchor="left",
                x=1.01,
                font=dict(color=theme.TEXT),
            ),
            margin=dict(l=10, r=130, t=44, b=46),
            title=dict(
                text=f"{lbl} — total deviation ({scale}× magnified)",
                font=dict(size=13, color=theme.TEXT),
            ),
        )
        return fig

    def _warp_surface(self, dev, lbl):
        """3D warp: Mesh3d over the 16 dots, height = deviation magnitude (µm)."""
        x = dev["nom_x"].tolist()
        y = dev["nom_y"].tolist()
        z = dev["mag_um"].tolist()
        fig = go.Figure()
        fig.add_trace(
            go.Mesh3d(
                x=x,
                y=y,
                z=z,
                intensity=z,
                colorscale="YlOrRd",
                opacity=0.85,
                delaunayaxis="z",
                showscale=True,
                colorbar=dict(title="µm"),
                name="warp",
            )
        )
        fig.add_trace(
            go.Scatter3d(
                x=x,
                y=y,
                z=z,
                mode="markers+text",
                text=dev["location"].tolist(),
                textfont=dict(size=9, color=theme.TEXT),
                hoverinfo="text",
                hovertext=[
                    f"{loc}: {m:.1f} µm"
                    for loc, m in zip(dev["location"], dev["mag_um"])
                ],
                marker=dict(size=4, color="#11111b"),
                name="dots",
            )
        )
        apply_dark_layout(
            fig,
            height=520,
            margin=dict(l=0, r=0, t=40, b=0),
            title=dict(
                text=f"{lbl} — deviation warp (height = µm)",
                font=dict(size=13, color=theme.TEXT),
            ),
            scene=dict(
                xaxis=dict(
                    title="X (mm)",
                    backgroundcolor=theme.PLOT_BG,
                    color=theme.TEXT_MUTED,
                ),
                yaxis=dict(
                    title="Y (mm)",
                    backgroundcolor=theme.PLOT_BG,
                    color=theme.TEXT_MUTED,
                ),
                zaxis=dict(
                    title="µm", backgroundcolor=theme.PLOT_BG, color=theme.TEXT_MUTED
                ),
            ),
        )
        return fig

    # -- fallback + export ---------------------------------------------------

    def _raw_tables(self, front_df, back_df) -> None:
        if not front_df.empty and not back_df.empty:
            st.subheader("Front vs Back")
            st.dataframe(
                both_frame(front_df, back_df), width="stretch", hide_index=True
            )
        elif not front_df.empty:
            st.dataframe(layer_frame(front_df), width="stretch", hide_index=True)
        else:
            st.dataframe(layer_frame(back_df), width="stretch", hide_index=True)

    def _show_export(self, front_df, back_df, meta, nominal_coords) -> None:
        buffer = BytesIO()
        warnings = st.session_state.get("parse_warnings", [])
        try:
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                write_core_shrinkage_excel(
                    writer,
                    front_df,
                    back_df,
                    meta,
                    warnings,
                    nominal_coords,
                    self.settings,
                )
            buffer.seek(0)
            st.download_button(
                label="📥 Export to Excel",
                data=buffer,
                file_name=_build_cs_filename(meta),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
            )
        except Exception as exc:
            logger.error("Core Shrinkage Excel export failed: %s", exc, exc_info=True)
            st.error(f"Export failed: {exc}")


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def _ppm_dir(v) -> str:
    """Format a scale-error ppm with its physical direction. The code reports
    ppm = (scale − 1)·1e6 (measured − nominal), so negative = shrink,
    positive = expand."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    v = float(v)
    if abs(v) < 0.5:
        return "0 ppm"
    return f"{v:+.0f} ppm ({'shrink' if v < 0 else 'expand'})"


def _highlight_outlier(row):
    """Row styler: light-red background when the dot is flagged as an outlier."""
    if bool(row.get("Outlier", False)):
        return ["background-color: #ffcccc"] * len(row)
    return [""] * len(row)


def _method() -> None:
    """Static explainer of every Core Shrinkage number — how it's computed and read."""
    st.subheader("How Core Shrinkage is calculated")
    st.markdown(
        "Each measured fiducial is compared to its **CAM nominal** position. A single "
        "best-fit transform (shift + rotation + X/Y scale + shear) is fitted across all "
        "16 dots; what the fit can't explain is the **per-dot residual**. Read it as a "
        "drill-down: **global** (headline) → **per-quadrant** (uniformity) → **per-dot** "
        "(defect locator)."
    )

    with st.expander("Correspondence — why dot numbering matters", expanded=False):
        st.markdown(
            "Measured `LL_1` must be the *same physical dot* as CAM `LL_1`. The QVM numbers "
            "each quadrant from the bottom-left; CAM from the top-left, so a raw export maps "
            "QVM `1,2,3,4` → CAM `2,1,4,3`. Files are standardised to **CAM order** before "
            "loading. If they aren't, every Y comparison blows up (the −471 mm symptom)."
        )

    with st.expander("Res X / Res Y / Res Distance (µm)", expanded=False):
        st.markdown(
            "After the best-fit transform predicts where each dot *should* land:\n\n"
            "- **Res X** = measured X − predicted X\n"
            "- **Res Y** = measured Y − predicted Y\n"
            "- **Res Distance** = √(Res X² + Res Y²)\n\n"
            "Reported in µm. Small everywhere = a clean panel; one large value = a bad/"
            "misdetected dot (e.g. `UL_2` here is a 0.76 mm Y mis-fit — its X is dead-on, "
            "so it's a bad measurement, not a numbering swap)."
        )

    with st.expander("X / Y Shrinkage (ppm) — the headline", expanded=False):
        st.markdown(
            "The fit's 2×2 matrix is split (QR decomposition) into rotation × per-axis "
            "scale, so **X Scale** is genuinely the X-axis stretch (SVD could swap X/Y).\n\n"
            "**ppm = (scale − 1) × 1,000,000** (measured − nominal, same sign as "
            "the registration Analytics tab)\n\n"
            "- **negative ppm → panel SHRANK** (smaller than CAM)\n"
            "- **positive ppm → panel EXPANDED** (larger than CAM)\n\n"
            "Example: scale 0.999535 → ppm = (0.999535 − 1)·1e6 = **−465 ppm = shrinkage**. "
            "This is the number you feed back as artwork pre-scale compensation."
        )

    with st.expander("Residual RMS (µm) — fit quality", expanded=False):
        st.markdown(
            "**Residual RMS** = √(mean of Res Distance²) over all dots — the typical "
            "leftover after removing shift/rotation/scale. Low (single-digit µm) = the "
            "panel is well described by a uniform transform. High = local distortion or "
            "a bad dot dragging the fit. **Max deviation** reports the single worst dot."
        )

    with st.expander("Outlier handling & robust scale", expanded=False):
        st.markdown(
            "Dots are rejected one at a time: fit → flag the worst dot whose residual "
            "exceeds the **outlier_um** threshold → refit → repeat. One-at-a-time keeps a "
            "single bad dot from smearing into its neighbours. The **headline ppm uses the "
            "robust (outlier-excluded) fit**, while the all-dot value is shown alongside so "
            "nothing is hidden. Flagged dots are listed for remeasure."
        )

    with st.expander("QP & Scale Factor (per-quadrant uniformity)", expanded=False):
        st.markdown(
            "**QP** measures the pitch between dot pairs *within* a quadrant and compares "
            "to the nominal pitch (X 200.65 mm, Y 235.75 mm); the error is shown in µm. "
            "**Scale Factor** turns those pitches into per-quadrant ppm. If all four "
            "quadrants agree, the shrinkage is uniform and a single global number is valid."
        )

    with st.expander("Front ↔ Back registration (µm)", expanded=False):
        st.markdown(
            "Per dot, **Front − Back** coordinate (each referenced to the same CAM, so the "
            "nominal cancels). This is the pad-to-land overlay in µm — how well the two "
            "layers line up."
        )


# ---------------------------------------------------------------------------
# Filename builder
# ---------------------------------------------------------------------------


def _build_cs_filename(meta: dict) -> str:
    parts = ["CS"]
    for key in ("build_up", "lot_number", "part_number"):
        val = str(meta.get(key, "")).strip()
        if val:
            parts.append(val)
    panel_val = str(meta.get("panel", "")).strip()
    if panel_val:
        parts.append(f"Panel-{panel_val}")
    process_val = str(meta.get("process", "")).strip()
    if process_val:
        parts.append(process_val)
    parts.append(pd.Timestamp.now().strftime("%Y%m%d"))
    return "_".join(parts) + ".xlsx"
