"""Registration Scatter View — Via-to-Pad bullseye and per-site SC bar chart."""

import streamlit as st
import pandas as pd

from .base import BaseView
from src.visuals import plot_vtp_bullseye, plot_vtp_site_bars


class RegistrationScatterView(BaseView):
    """
    Two-chart registration diagnostic for Via-to-Pad files:

    1. Bullseye scatter — every site plotted at (DX, DY) with concentric
       tolerance rings. Quickly shows individual failures and overall spread.

    2. Per-site SC bar chart — ordered by Grid ID so quarter patterns jump
       out. Useful for spotting one rogue fiducial site versus a quarter-wide
       problem.
    """

    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        st.subheader("Registration Scatter — Via-to-Pad")
        st.write(
            "Each point is one fiducial site plotted at its (DX, DY) registration error. "
            "The pad centre is at (0, 0). Color indicates SC magnitude — darker = larger shift."
        )

        vtp_cfg = self.settings.get('VTP_REGISTRATION', {})
        ring_exceptional = float(vtp_cfg.get('ring_exceptional_um', 2.5))
        ring_excellent = float(vtp_cfg.get('ring_excellent_um', 5.0))
        ring_good = float(vtp_cfg.get('ring_good_um', 7.5))
        ring_acceptable = float(vtp_cfg.get('ring_acceptable_um', 10.0))

        sc_col = self.col_names.get('ptv_distance', 'PtV Distance')

        # Summary metrics above the charts
        if sc_col in filtered_df.columns:
            sc_um = filtered_df[sc_col].dropna() * 1000
            n_total = len(sc_um)
            n_pass = int((sc_um <= ring_exceptional).sum())
            n_warn = int(((sc_um > ring_exceptional) & (sc_um <= ring_acceptable)).sum())
            n_fail = int((sc_um > ring_acceptable).sum())

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Sites measured", n_total)
            c2.metric("Pass", n_pass, delta=None)
            c3.metric(
                "Warning",
                n_warn,
                delta="review" if n_warn > 0 else None,
                delta_color="inverse" if n_warn > 0 else "off",
            )
            c4.metric(
                "FAIL",
                n_fail,
                delta="action required" if n_fail > 0 else None,
                delta_color="inverse" if n_fail > 0 else "off",
            )

        st.markdown("---")

        col_left, col_right = st.columns(2)
        with col_left:
            fig_bull = plot_vtp_bullseye(filtered_df, self.settings)
            st.plotly_chart(fig_bull, use_container_width=True)

        with col_right:
            fig_bars = plot_vtp_site_bars(filtered_df, self.settings)
            st.plotly_chart(fig_bars, use_container_width=True)
            st.caption(
                f"Tolerance rings: blue ≤ {ring_exceptional:.1f} µm | "
                f"green {ring_exceptional:.1f}–{ring_excellent:.1f} µm | "
                f"green {ring_excellent:.1f}–{ring_good:.1f} µm | "
                f"orange {ring_good:.1f}–{ring_acceptable:.0f} µm | "
                f"red > {ring_acceptable:.0f} µm"
            )
