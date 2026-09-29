"""
Base View Class - Common interface for all views.

Ensures consistent rendering patterns and provides shared utilities.
"""

import pandas as pd
from abc import ABC, abstractmethod
from typing import Dict
import logging

from src.utils import resolve_columns

logger = logging.getLogger(__name__)


class BaseView(ABC):
    """Abstract base class for all dashboard views."""

    def __init__(self, settings: Dict):
        """Initialize base view from application settings."""
        self.settings = settings
        self.col_names = settings.get('COLUMN_NAMES', {})
        self.tolerances = settings.get('TOLERANCES', {})

    def cols(self, *keys: str) -> Dict[str, str]:
        """Resolve column-name aliases via the single fallback table.

        Prefer this over ``self.col_names.get(key, 'Default')`` so every
        view shares one source of fallback truth (see ``utils._COLUMN_DEFAULTS``).
        """
        return resolve_columns(self.settings, keys)

    @abstractmethod
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """
        Render the view.

        Args:
            filtered_df: Filtered dataframe for this view
            **kwargs: Additional view-specific parameters
        """

    def format_to_3_decimals(self, val) -> str:
        """Format value to 3 decimals without trailing zeros."""
        if pd.isna(val):
            return ''
        try:
            return f'{float(val):.3f}'.rstrip('0').rstrip('.')
        except (ValueError, TypeError):
            return str(val)
