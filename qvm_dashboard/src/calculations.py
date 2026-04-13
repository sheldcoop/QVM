import pandas as pd
from typing import Dict, Tuple

def calculate_annular_ring(df: pd.DataFrame, settings: Dict) -> pd.DataFrame:
    """
    Calculate the Minimum Annular Ring for each row in the DataFrame.
    Formula: (Outer Diameter / 2) - (Inner Diameter / 2) - PtV Distance
    """
    col_names = settings.get('COLUMN_NAMES', {})
    outer_col = col_names.get('outer_diameter', 'Outer Diameter')
    inner_col = col_names.get('inner_diameter', 'Inner Diameter')
    ptv_col = col_names.get('ptv_distance', 'PtV Distance')
    annular_col = col_names.get('annular_ring', 'Annular Ring')

    # Calculate annular ring
    df[annular_col] = (df[outer_col] / 2) - (df[inner_col] / 2) - df[ptv_col]

    return df

def calculate_cam_compensation(df: pd.DataFrame, settings: Dict) -> Tuple[float, float]:
    """
    Calculate the Average X shift and Average Y shift across the whole panel.
    Returns:
        tuple: (avg_x_shift, avg_y_shift)
    """
    col_names = settings.get('COLUMN_NAMES', {})
    x_col = col_names.get('x_distance', 'X Distance')
    y_col = col_names.get('y_distance', 'Y Distance')

    if x_col in df.columns and y_col in df.columns:
        avg_x = df[x_col].mean()
        avg_y = df[y_col].mean()
        return float(avg_x), float(avg_y)

    return 0.0, 0.0
