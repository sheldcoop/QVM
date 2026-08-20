"""Shared utility functions used across views and data processing."""

import os
import yaml
import pandas as pd
from typing import Dict, Iterable, List

_REQUIRED_SETTINGS_KEYS = [
    'COLUMN_NAMES', 'POSITIONAL_MAPPING', 'GRID_MAPPING',
    'VTP_REGISTRATION', 'EXCEL_EXPORT', 'DIAGNOSTICS',
]


def _validate_settings(settings: dict) -> None:
    missing = [k for k in _REQUIRED_SETTINGS_KEYS if k not in settings]
    if missing:
        raise ValueError(f"settings.yaml is missing required sections: {missing}")


def load_settings() -> dict:
    """Load and return the project settings.yaml as a dict.

    Canonical loader. Other modules should import this rather than
    defining their own.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config',
        'settings.yaml',
    )
    if not os.path.isfile(config_path):
        raise ValueError(f"settings.yaml not found at {config_path}")
    try:
        with open(config_path, 'r') as f:
            settings = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in settings.yaml: {e}") from e
    _validate_settings(settings)
    return settings


def is_via_to_pad(df: pd.DataFrame) -> pd.Series:
    """Boolean mask of the Via-to-Pad rows in a parsed frame.

    ``Process`` is the parser's source of truth for routing (see
    ``parser.parse_qvm_content``), so every consumer that splits by process
    must agree on how it is read. Rows with no usable Process value are
    treated as Pad-to-Via, matching the dashboard's default tab.
    """
    if 'Process' not in df.columns:
        return pd.Series(False, index=df.index)
    return df['Process'].astype(str).str.contains('Via to Pad', case=False, na=False)


def convert_to_microns(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    """Multiply named columns by 1000 (mm → µm) and round to 3 dp.

    Silently skips columns that are not present in df.
    """
    for col in cols:
        if col in df.columns:
            df[col] = (df[col] * 1000).round(3)
    return df


def calculate_annular_ring(df: pd.DataFrame, settings: Dict) -> pd.DataFrame:
    """Compute the minimum Annular Ring per row and store it on the DataFrame.

    Formula: (Outer Diameter / 2) - (Inner Diameter / 2) - PtV Distance
    """
    col_names = settings.get('COLUMN_NAMES', {})
    outer_col = col_names.get('outer_diameter', 'Outer Diameter')
    inner_col = col_names.get('inner_diameter', 'Inner Diameter')
    ptv_col = col_names.get('ptv_distance', 'PtV Distance')
    annular_col = col_names.get('annular_ring', 'Annular Ring')

    df[annular_col] = (df[outer_col] / 2) - (df[inner_col] / 2) - df[ptv_col]
    return df


def resolve_columns(settings: dict, keys: Iterable[str]) -> dict:
    """Resolve a set of column-name aliases from settings['COLUMN_NAMES'].

    Returns a {key: column_name} dict, falling back to a sensible default
    when a key is missing from settings (e.g. partial settings in tests).
    """
    col_names = settings.get('COLUMN_NAMES', {})
    return {k: col_names.get(k, _COLUMN_DEFAULTS.get(k, k)) for k in keys}


# Code-level safety net for column names absent from a (possibly partial)
# settings dict. config/settings.yaml remains the canonical source at runtime.
_COLUMN_DEFAULTS = {
    'location': 'Location',
    'grid_id': 'Grid ID',
    'outer_diameter': 'Pad Diameter',
    'inner_diameter': 'Via Parameter',
    'coord_x': 'Coord. X',
    'coord_y': 'Coord. Y',
    'ptv_distance': 'PtV Distance',
    'total_shift': 'VtP Distance (SC)',
    'x_distance': 'Shift (DX)',
    'y_distance': 'Shift (DY)',
    'pad_pts': 'Pad Pts.',
    'via_pts': 'Via Pts.',
    'item_type': 'Type',
    'annular_ring': 'Annular Ring',
}
