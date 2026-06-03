"""Reusable chart building blocks shared across the ``visuals`` package.

Keeps the per-chart modules small by housing the logic they all repeat:
tolerance-ring extraction, zone-colour mapping, the dark layout preamble, and
the two shared annotation cards.  Pure helpers — no Streamlit, no I/O.
"""

from dataclasses import dataclass
from typing import Dict

import pandas as pd
import plotly.graph_objects as go

from src import theme


# ---------------------------------------------------------------------------
# Tolerance rings
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rings:
    """The four concentric tolerance boundaries (µm) that define five zones."""
    exceptional: float
    excellent: float
    good: float
    acceptable: float


def get_rings(settings: Dict) -> Rings:
    """Read the VtP registration tolerance rings from settings (with defaults)."""
    cfg = settings.get('VTP_REGISTRATION', {})
    return Rings(
        exceptional=float(cfg.get('ring_exceptional_um', 2.5)),
        excellent=float(cfg.get('ring_excellent_um', 5.0)),
        good=float(cfg.get('ring_good_um', 7.5)),
        acceptable=float(cfg.get('ring_acceptable_um', 10.0)),
    )


# ---------------------------------------------------------------------------
# Zone colours
# ---------------------------------------------------------------------------

def zone_color(value_um: float, rings: Rings) -> str:
    """Map an SC magnitude (µm) to its Catppuccin zone colour."""
    if value_um <= rings.exceptional:
        return theme.ZONE['exceptional']
    if value_um <= rings.excellent:
        return theme.ZONE['excellent']
    if value_um <= rings.good:
        return theme.ZONE['good']
    if value_um <= rings.acceptable:
        return theme.ZONE['acceptable']
    return theme.ZONE['fail']


def zone_colors(values_um: pd.Series, rings: Rings) -> pd.Series:
    """Vectorised :func:`zone_color` for a Series of SC magnitudes."""
    return values_um.apply(lambda v: zone_color(v, rings))


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

def apply_dark_layout(fig: go.Figure, *, height: int = None, **overrides) -> go.Figure:
    """Apply the shared Catppuccin dark layout, then any per-chart overrides."""
    layout = dict(
        plot_bgcolor=theme.PLOT_BG,
        paper_bgcolor=theme.PAPER_BG,
        font=dict(color=theme.TEXT, size=11),
    )
    if height is not None:
        layout['height'] = height
    layout.update(overrides)
    fig.update_layout(**layout)
    return fig


# ---------------------------------------------------------------------------
# Shared annotation cards (dark theme)
# ---------------------------------------------------------------------------

def zone_legend_annotation(rings: Rings, *, x: float = 0.5, y: float = -0.08,
                           xanchor: str = 'center', yanchor: str = 'top') -> dict:
    """Plotly annotation dict for the 5-zone colour legend (bottom-centre)."""
    z = theme.ZONE
    return dict(
        text=(
            f"<span style='color:{z['exceptional']}'>⬤</span> ≤{rings.exceptional:.1f}  "
            f"<span style='color:{z['excellent']}'>⬤</span> ≤{rings.excellent:.1f}  "
            f"<span style='color:{z['good']}'>⬤</span> ≤{rings.good:.1f}  "
            f"<span style='color:{z['acceptable']}'>⬤</span> ≤{rings.acceptable:.1f}  "
            f"<span style='color:{z['fail']}'>⬤</span> fail (µm)"
        ),
        xref='paper', yref='paper',
        x=x, y=y, xanchor=xanchor, yanchor=yanchor,
        showarrow=False,
        font=dict(size=11, color=theme.TEXT),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD,
        borderwidth=1, borderpad=6,
    )


def stats_card_annotation(n: int, mean_v: float, median_v: float,
                          std_v: float, pct_pass: float) -> dict:
    """Stats card placed just outside the chart on the right (margin.r ≥ 160)."""
    pass_color = theme.ZONE['excellent'] if pct_pass == 100 else (
        theme.ZONE['acceptable'] if pct_pass >= 75 else theme.ZONE['fail'])
    return dict(
        text=(
            f"<b>n</b>         {n}<br>"
            f"<b>Mean</b>    {mean_v:.2f} µm<br>"
            f"<b>Median</b>  {median_v:.2f} µm<br>"
            f"<b>Std Dev</b> {std_v:.2f} µm<br>"
            f"<b style='color:{pass_color}'>Pass</b>      {pct_pass:.0f}%"
        ),
        xref='paper', yref='paper',
        x=1.03, y=0.98, xanchor='left', yanchor='top',
        showarrow=False, align='left',
        font=dict(size=11, color=theme.TEXT, family='monospace'),
        bgcolor=theme.CARD_BG, bordercolor=theme.CARD_BD,
        borderwidth=1, borderpad=8,
    )
