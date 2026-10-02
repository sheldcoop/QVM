"""Chart rendering package — all functions return Plotly figures.

Public API is re-exported here so existing imports (``from src.visuals import
plot_quiver``) keep working after the split into focused modules.

Shared design tokens live in ``src/theme.py``; reusable chart helpers in
``src/chart_helpers.py``.
"""

from src.visuals.bullseye import plot_vtp_bullseye, plot_vtp_site_bars
from src.visuals.quiver import plot_quiver
from src.visuals.distribution import plot_vtp_box
from src.visuals.shrinkage import (
    plot_fit_residuals, plot_quadrant_bars, plot_shrinkage_quiver,
)

__all__ = [
    'plot_vtp_bullseye',
    'plot_vtp_site_bars',
    'plot_quiver',
    'plot_vtp_box',
    'plot_shrinkage_quiver',
    'plot_quadrant_bars',
    'plot_fit_residuals',
]
