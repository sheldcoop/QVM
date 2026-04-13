"""Views module - Individual dashboard view implementations."""

from src.views.base import BaseView
from src.views.process_stability import ProcessStabilityView
from src.views.quality_control import QualityControlView
from src.views.optical_edge_confidence import OpticalEdgeConfidenceView
from src.views.analytics import AnalyticsView
from src.views.cam_compensation import CAMCompensationView
from src.views.polar_drift import PolarDriftView

__all__ = [
    'BaseView',
    'ProcessStabilityView',
    'QualityControlView',
    'OpticalEdgeConfidenceView',
    'AnalyticsView',
    'CAMCompensationView',
    'PolarDriftView'
]
