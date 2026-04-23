"""
Data Processor Module - Single Source of Truth for DataFrame Operations

Centralizes all data transformation, filtering, and metric calculations
to ensure consistency across all views.
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
import logging

from src.utils import convert_to_microns

logger = logging.getLogger(__name__)


class DataProcessor:
    """Handles all dataframe transformations and calculations."""
    
    def __init__(self, settings: Dict):
        """
        Initialize processor with application settings.
        
        Args:
            settings: Application configuration from settings.yaml
        """
        self.settings = settings
        self.col_names = settings.get('COLUMN_NAMES', {})
        self.process_stability = settings.get('PROCESS_STABILITY', {})
        
    def prepare_process_stability_data(
        self, 
        df: pd.DataFrame, 
        item_type: str,
        nominal_mm: float,
        ucl_mm: float,
        lcl_mm: float
    ) -> Tuple[pd.DataFrame, Dict]:
        """
        Prepare data for Process Stability charts (Via/Pad).
        
        Args:
            df: Filtered dataframe
            item_type: 'Via' or 'Pad'
            nominal_mm: Nominal diameter in mm
            ucl_mm: Upper Control Limit in mm
            lcl_mm: Lower Control Limit in mm
        
        Returns:
            Tuple of (processed_df, metrics_dict)
        """
        outer_diam_col = self.col_names.get('outer_diameter', 'Pad Diameter')
        inner_diam_col = self.col_names.get('inner_diameter', 'Via Parameter')
        location_col = self.col_names.get('location', 'Location')
        
        # Select the right diameter column based on item_type
        if item_type == 'Via':
            diameter_col = inner_diam_col
        else:  # Pad
            diameter_col = outer_diam_col
        
        if diameter_col not in df.columns:
            logger.warning(f"Column '{diameter_col}' not found in dataframe")
            return pd.DataFrame(), {}
        
        # Prepare data - use consolidated row structure
        plot_df = df[[location_col, diameter_col]].dropna().copy()
        
        if plot_df.empty:
            logger.warning(f"No {item_type} data after removing NaN")
            return pd.DataFrame(), {}
        
        plot_df = plot_df.sort_values(by=location_col)
        
        # Convert to microns
        plot_df['diameter_um'] = plot_df[diameter_col] * 1000
        
        # Calculate metrics in microns
        nominal_um = nominal_mm * 1000
        ucl_um = ucl_mm * 1000
        lcl_um = lcl_mm * 1000
        
        # Determine colors based on control limits
        plot_df['color'] = plot_df[diameter_col].apply(
            lambda x: self.process_stability.get('outlier_color', '#d62728')
            if (x < lcl_mm or x > ucl_mm)
            else self.process_stability.get('normal_color', '#2ca02c')
        )
        
        # Calculate metrics
        out_of_spec = (plot_df[diameter_col] < lcl_mm) | (plot_df[diameter_col] > ucl_mm)
        n_out = out_of_spec.sum()
        pct_out = (n_out / len(plot_df) * 100) if len(plot_df) > 0 else 0
        
        # Calculate Y-axis range
        margin = 2  # microns
        y_min = min(lcl_um, plot_df['diameter_um'].min()) - margin
        y_max = max(ucl_um, plot_df['diameter_um'].max()) + margin
        
        metrics = {
            'nominal_um': nominal_um,
            'ucl_um': ucl_um,
            'lcl_um': lcl_um,
            'y_min': y_min,
            'y_max': y_max,
            'out_of_spec': n_out,
            'total': len(plot_df),
            'pct_out_of_spec': pct_out
        }
        
        logger.info(f"{item_type} data: {len(plot_df)} points, {pct_out:.1f}% out of spec")
        
        return plot_df, metrics
    
    def prepare_quality_control_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data for Quality Control view.
        
        Args:
            df: Filtered dataframe
        
        Returns:
            Processed dataframe with measurements in microns
        """
        display_df = df.copy()
        
        # Drop meta columns
        cols_to_drop = [col for col in ['Panel', 'Side'] if col in display_df.columns]
        display_df = display_df.drop(columns=cols_to_drop)
        
        # Convert measurements from mm to microns
        measurement_cols = [
            self.col_names.get('outer_diameter', 'Outer Diameter'),
            self.col_names.get('inner_diameter', 'Inner Diameter'),
            self.col_names.get('ptv_distance', 'PtV Distance'),
            self.col_names.get('x_distance', 'Shift (DX)'),
            self.col_names.get('y_distance', 'Shift (DY)'),
            self.col_names.get('annular_ring', 'Annular Ring')
        ]
        
        display_df = convert_to_microns(display_df, measurement_cols)
        
        # Sort by Grid ID
        grid_id_col = self.col_names.get('grid_id', 'Grid ID')
        if grid_id_col in display_df.columns:
            display_df = display_df.sort_values(by=grid_id_col, ascending=True)
        
        logger.info(f"Quality Control data processed: {len(display_df)} records")
        return display_df
    
    def prepare_optical_edge_data(self, df: pd.DataFrame, item_type: str) -> pd.DataFrame:
        """
        Prepare data for Optical Edge Confidence tables.
        
        Args:
            df: Filtered dataframe
            item_type: 'Via' or 'Pad'
        
        Returns:
            Processed dataframe with measurements in microns
        """
        if 'Type' not in df.columns:
            return pd.DataFrame()
        
        pts_col = 'Pts.'
        type_df = df[df['Type'] == item_type].copy().dropna(subset=[pts_col])
        
        if type_df.empty:
            logger.info(f"No {item_type} data for Optical Edge Confidence")
            return pd.DataFrame()
        
        type_df = type_df.sort_values(by=pts_col, ascending=True)
        
        grid_id_col = self.col_names.get('grid_id', 'Grid ID')
        ptv_col = self.col_names.get('ptv_distance', 'PtV Distance')
        dx_col = self.col_names.get('x_distance', 'Shift (DX)')
        dy_col = self.col_names.get('y_distance', 'Shift (DY)')
        
        # Create display dataframe
        display = type_df[['Location', grid_id_col, pts_col, ptv_col, dx_col, dy_col]].copy()
        
        # Convert to microns
        if ptv_col in display.columns:
            display[f'{ptv_col} (µm)'] = (display[ptv_col] * 1000).round(3)
        if dx_col in display.columns:
            display[f'{dx_col} (µm)'] = (display[dx_col] * 1000).round(3)
        if dy_col in display.columns:
            display[f'{dy_col} (µm)'] = (display[dy_col] * 1000).round(3)
        
        # Drop original mm columns
        cols_to_keep = ['Location', grid_id_col, pts_col, f'{ptv_col} (µm)', f'{dx_col} (µm)', f'{dy_col} (µm)']
        cols_to_keep = [col for col in cols_to_keep if col in display.columns]
        display = display[cols_to_keep]
        display.columns = ['Location', 'Grid ID', 'Pts.', 'PtV (µm)', 'Shift DX (µm)', 'Shift DY (µm)']
        
        logger.info(f"{item_type} optical edge data: {len(display)} records")
        return display
    
    def calculate_annular_ring_stats(self, df: pd.DataFrame, threshold: float) -> Dict:
        """
        Calculate annular ring statistics.
        
        Args:
            df: Dataframe with annular ring column
            threshold: Minimum acceptable annular ring
        
        Returns:
            Dictionary with statistics
        """
        annular_col = self.col_names.get('annular_ring', 'Annular Ring')
        grid_id_col = self.col_names.get('grid_id', 'Grid ID')
        
        if annular_col not in df.columns:
            return {}
        
        ar_min = df[annular_col].min()
        ar_max = df[annular_col].max()
        ar_mean = df[annular_col].mean()
        ar_std = df[annular_col].std()
        
        fail_count = (df[annular_col] < threshold).sum()
        fail_pct = (fail_count / len(df) * 100) if len(df) > 0 else 0
        
        worst_idx = df[annular_col].idxmin()
        worst_grid = df.loc[worst_idx, grid_id_col] if grid_id_col in df.columns else 'N/A'
        
        return {
            'min': ar_min,
            'max': ar_max,
            'mean': ar_mean,
            'std': ar_std,
            'fail_count': fail_count,
            'fail_pct': fail_pct,
            'worst_grid': worst_grid,
            'threshold': threshold
        }
