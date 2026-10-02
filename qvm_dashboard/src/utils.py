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

    Pure: works on a copy, so the caller's frame is never mutated.
    Silently skips columns that are not present in df.
    """
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = (out[col] * 1000).round(3)
    return out


def calculate_annular_ring(df: pd.DataFrame, settings: Dict) -> pd.DataFrame:
    """Compute the minimum Annular Ring per row and store it on the DataFrame.

    Pure: works on a copy, so the caller's frame is never mutated.

    Formula: (Outer Diameter / 2) - (Inner Diameter / 2) - PtV Distance
    """
    cols = resolve_columns(
        settings,
        ('outer_diameter', 'inner_diameter', 'ptv_distance', 'annular_ring'),
    )
    outer_col = cols['outer_diameter']
    inner_col = cols['inner_diameter']
    ptv_col = cols['ptv_distance']
    annular_col = cols['annular_ring']

    out = df.copy()
    out[annular_col] = (out[outer_col] / 2) - (out[inner_col] / 2) - out[ptv_col]
    return out


def decode_upload_bytes(data: bytes) -> tuple:
    """Decode uploaded file bytes to text, tolerating machine-export encodings.

    Detection order (first success wins):
    1. UTF-8 (BOM stripped when present) — preserves current behaviour for
       every file that already parses today.
    2. UTF-16, only when a UTF-16 BOM is present.
    3. Latin-1 (single-byte superset of ASCII; always succeeds).

    Returns (text, encoding_label) where the label is one of
    ``utf-8`` / ``utf-8-sig`` / ``utf-16`` / ``latin-1``. Callers must record
    the label so a workbook can show how each file was read.
    """
    import codecs
    if data.startswith(codecs.BOM_UTF8):
        return data.decode('utf-8-sig'), 'utf-8-sig'
    try:
        return data.decode('utf-8'), 'utf-8'
    except UnicodeDecodeError:
        pass
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode('utf-16'), 'utf-16'
    return data.decode('latin-1'), 'latin-1'


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
