"""Views module - Individual dashboard view implementations."""

from src.views.base import BaseView
from src.views.quality_control import QualityControlView
from src.views.registration_scatter import RegistrationScatterView
from src.views.spatial_heatmap import SpatialHeatmapView

__all__ = [
    'BaseView',
    'QualityControlView',
    'RegistrationScatterView',
    'SpatialHeatmapView',
]
