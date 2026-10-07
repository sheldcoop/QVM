"""Registration Scatter View — Via-to-Pad bullseye and per-site SC bar chart."""

import streamlit as st
import pandas as pd

from .base import BaseView, full_width
from src.chart_helpers import get_rings
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

        # Same ring source the charts use, so the tiles and the bullseye rings
        # can never disagree about where pass/warn/fail sit.
        rings = get_rings(self.settings)
        ring_exceptional = rings.exceptional
        ring_acceptable = rings.acceptable

        sc_col = self.cols("ptv_distance")["ptv_distance"]

        # Summary metrics above the charts
        if sc_col in filtered_df.columns:
            sc_um = filtered_df[sc_col].dropna() * 1000
            n_total = len(sc_um)
            n_pass = int((sc_um <= ring_exceptional).sum())
            n_warn = int(
                ((sc_um > ring_exceptional) & (sc_um <= ring_acceptable)).sum()
            )
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
            st.plotly_chart(fig_bull, **full_width(st.plotly_chart))

        with col_right:
            fig_bars = plot_vtp_site_bars(filtered_df, self.settings)
            st.plotly_chart(fig_bars, **full_width(st.plotly_chart))
