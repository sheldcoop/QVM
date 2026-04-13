"""
Base View Class - Common interface for all views.

Ensures consistent rendering patterns and provides shared utilities.
"""

import streamlit as st
import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class BaseView(ABC):
    """Abstract base class for all dashboard views."""
    
    def __init__(self, settings: Dict, data_processor):
        """
        Initialize base view.
        
        Args:
            settings: Application settings from YAML
            data_processor: DataProcessor instance
        """
        self.settings = settings
        self.processor = data_processor
        self.col_names = settings.get('COLUMN_NAMES', {})
        self.chart_colors = settings.get('CHART_COLORS', {})
        self.chart_heights = settings.get('CHART_HEIGHTS', {})
    
    @abstractmethod
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the view.
        
        Args:
            filtered_df: Filtered dataframe for this view
            **kwargs: Additional view-specific parameters
        """
        pass
    
    def get_chart_background(self) -> str:
        """Get background color for charts."""
        return self.chart_colors.get('chart_background', '#FFFFFF')
    
    def get_gridlines_visible(self) -> bool:
        """Check if gridlines should be visible."""
        return self.chart_colors.get('chart_gridlines_visible', False)
    
    def get_chart_height(self, chart_type: str) -> int:
        """Get chart height for specific type."""
        return self.chart_heights.get(chart_type, 600)
    
    def format_to_3_decimals(self, val):
        """Format value to 3 decimals without trailing zeros."""
        import pandas as pd
        if pd.isna(val):
            return ''
        try:
            formatted = f'{float(val):.3f}'.rstrip('0').rstrip('.')
            return formatted
        except:
            return str(val)
    
    def log_render_start(self, message: str = None) -> None:
        """Log view initialization."""
        view_name = self.__class__.__name__
        msg = message or f"Rendering {view_name}"
        logger.info(msg)
