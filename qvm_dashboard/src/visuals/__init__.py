"""Chart rendering package — all functions return Plotly figures.

Public API is re-exported here so existing imports (``from src.visuals import
plot_quiver``) keep working after the split into focused modules.

Diagnostic computations live in ``src/diagnostics.py``; shared design tokens in
``src/theme.py``; reusable chart helpers in ``src/chart_helpers.py``.
"""

from src.visuals.bullseye import plot_vtp_bullseye, plot_vtp_site_bars
from src.visuals.quiver import plot_quiver
from src.visuals.heatmap import plot_heatmap
from src.visuals.distribution import plot_vtp_box
from src.visuals.panel_image import get_panel_image_path

__all__ = [
    'plot_vtp_bullseye',
    'plot_vtp_site_bars',
    'plot_quiver',
    'plot_heatmap',
    'plot_vtp_box',
    'get_panel_image_path',
]
