import re
import os
import pandas as pd
from typing import Dict, Any, Optional

from src.utils import load_settings


class QVMParseError(Exception):
    """Custom exception for QVM file parsing errors."""
    pass


_PTS_RE = re.compile(r"From\s+(\d+)\s*Pts\.")
_PANEL_RE = re.compile(r'panel[\s_]*(\d+)', re.IGNORECASE)
_SIDE_RE = re.compile(r'[_\s]([fb])\s*$', re.IGNORECASE)


def parse_filename(filename: str) -> Dict[str, Optional[str]]:
    """Extract a format hint, Panel Number, and Side from an uploaded filename.

    Naming is lenient — any casing of 'VTP'/'PTV' (or the longer 'Via to Pad' /
    'Pad to Via') is accepted, anywhere in the name:

      Pad-to-Via:  ...PTV..._Panel <N>_<Side>.txt   e.g. PostPFC_PTV_Panel20_F.txt
      Via-to-Pad:  ...VTP..._Panel <N>_<Side>.txt   e.g. vtp_panel_25_f.txt

    Routing in the dashboard is content-driven (see parse_qvm_content). The
    format_hint here is informational — used by the upload code to warn when
    the filename and the parsed content disagree, or when no hint is present.

    Returns:
        {
            'format_hint': 'Via to Pad' | 'Pad to Via' | None,
            'Panel Number': str | 'Unknown',
            'Side': 'F' | 'B' | 'Unknown',
        }
    """
    basename = os.path.basename(filename)
    name_without_ext, _ = os.path.splitext(basename)
    lower = name_without_ext.lower()

    has_vtp = 'vtp' in lower or 'via to pad' in lower
    has_ptv = 'ptv' in lower or 'pad to via' in lower

    if has_vtp and not has_ptv:
        format_hint: Optional[str] = 'Via to Pad'
    elif has_ptv and not has_vtp:
        format_hint = 'Pad to Via'
    else:
        format_hint = None  # absent or ambiguous (both)

    panel_match = _PANEL_RE.search(name_without_ext)
    panel_number = panel_match.group(1) if panel_match else 'Unknown'

    side_match = _SIDE_RE.search(name_without_ext)
    side = side_match.group(1).upper() if side_match else 'Unknown'

    return {
        'format_hint': format_hint,
        'Panel Number': panel_number,
        'Side': side,
    }


def _emit_row(current: Dict[str, Any], block_index: int, settings: dict) -> dict:
    """Build a single output row dict from the accumulated parser state."""
    col_names = settings.get('COLUMN_NAMES', {})
    positional_mapping = settings.get('POSITIONAL_MAPPING', [])
    grid_id = positional_mapping[block_index] if block_index < len(positional_mapping) else None
    return {
        col_names.get('location', 'Location'): current.get('location', ''),
        col_names.get('grid_id', 'Grid ID'): int(grid_id) if grid_id is not None else None,
        col_names.get('outer_diameter', 'Pad Diameter'): current.get('pad_diameter'),
        col_names.get('inner_diameter', 'Via Parameter'): current.get('via_diameter'),
        col_names.get('coord_x', 'Coord. X'): current.get('via_coord_x'),
        col_names.get('coord_y', 'Coord. Y'): current.get('via_coord_y'),
        col_names.get('ptv_distance', 'PtV Distance'): current['sc'],
        col_names.get('total_shift', 'SC'): current['sc'],
        col_names.get('x_distance', 'Shift (DX)'): current['dx'],
        col_names.get('y_distance', 'Shift (DY)'): current['dy'],
        col_names.get('pad_pts', 'Pad Pts.'): current.get('pad_pts'),
        col_names.get('via_pts', 'Via Pts.'): current.get('via_pts'),
        col_names.get('item_type', 'Type'): 'Via',
    }


def _step_distance_tail(s: str, state: str, current: Dict[str, Any]):
    """Advance the shared DIST_HEADER → SC → DX → DY tail by one line.

    Returns (new_state, completed) where completed=True signals the block
    is fully parsed and the caller should emit a row.
    """
    if state == "DIST_HEADER" and s.startswith("Distance:"):
        return "SC", False
    if state == "SC" and s.startswith("SC"):
        current['sc'] = float(s.split('=')[1].strip())
        return "DX", False
    if state == "DX" and s.startswith("DX"):
        current['dx'] = float(s.split('=')[1].strip())
        return "DY", False
    if state == "DY" and s.startswith("DY"):
        current['dy'] = float(s.split('=')[1].strip())
        return "IDLE", True
    return state, False


def _parse_pad_to_via(content: str, settings: dict) -> pd.DataFrame:
    """Parse a Pad-to-Via QVM log.

    Per-block order in source: Pad circle → Via circle → Distance.
    """
    rows: list = []
    current: Dict[str, Any] = {}
    block_index = 0
    state = "IDLE"

    for line in content.splitlines():
        s = line.strip()

        if state == "IDLE":
            if s.startswith("Circle: Pad_"):
                pts_m = _PTS_RE.search(s)
                current = {
                    'location': s.split('(')[0].replace('Circle: Pad_', '').strip(),
                    'pad_pts': int(pts_m.group(1)) if pts_m else None,
                }
                state = "PAD_X"

        elif state == "PAD_X":
            if s.startswith("Coord.") and 'X' in s:
                current['pad_coord_x'] = float(s.split('=')[1].strip())
                state = "PAD_Y"

        elif state == "PAD_Y":
            if s.startswith("Coord.") and 'Y' in s:
                current['pad_coord_y'] = float(s.split('=')[1].strip())
                state = "PAD_DIAM"

        elif state == "PAD_DIAM":
            if 'Diameter' in s:
                current['pad_diameter'] = float(s.split('=')[1].strip())
                state = "VIA_HEADER"

        elif state == "VIA_HEADER":
            if s.startswith("Circle: Via_"):
                pts_m = _PTS_RE.search(s)
                current['via_pts'] = int(pts_m.group(1)) if pts_m else None
                state = "VIA_X"

        elif state == "VIA_X":
            if s.startswith("Coord.") and 'X' in s:
                current['via_coord_x'] = float(s.split('=')[1].strip())
                state = "VIA_Y"

        elif state == "VIA_Y":
            if s.startswith("Coord.") and 'Y' in s:
                current['via_coord_y'] = float(s.split('=')[1].strip())
                state = "VIA_DIAM"

        elif state == "VIA_DIAM":
            if 'Diameter' in s:
                current['via_diameter'] = float(s.split('=')[1].strip())
                state = "DIST_HEADER"

        else:
            state, completed = _step_distance_tail(s, state, current)
            if completed:
                rows.append(_emit_row(current, block_index, settings))
                block_index += 1
                current = {}

    if not rows:
        raise QVMParseError("No valid measurement blocks found in the file.")
    return pd.DataFrame(rows)


def _parse_via_to_pad(content: str, settings: dict) -> pd.DataFrame:
    """Parse a Via-to-Pad QVM log.

    Per-block order in source: Via circle → Pad circle → Distance.
    Via-to-Pad logs carry no absolute coordinates — only diameters and shifts.
    """
    rows: list = []
    current: Dict[str, Any] = {}
    block_index = 0
    state = "IDLE"

    for line in content.splitlines():
        s = line.strip()

        if state == "IDLE":
            if s.startswith("Circle: Via_"):
                pts_m = _PTS_RE.search(s)
                current = {
                    'location': s.split('(')[0].replace('Circle: Via_', '').strip(),
                    'via_pts': int(pts_m.group(1)) if pts_m else None,
                }
                state = "VIA_DIAM"

        elif state == "VIA_DIAM":
            if 'Diameter' in s:
                current['via_diameter'] = float(s.split('=')[1].strip())
                state = "PAD_HEADER"

        elif state == "PAD_HEADER":
            if s.startswith("Circle: Pad_"):
                pts_m = _PTS_RE.search(s)
                current['pad_pts'] = int(pts_m.group(1)) if pts_m else None
                state = "PAD_DIAM"

        elif state == "PAD_DIAM":
            if 'Diameter' in s:
                current['pad_diameter'] = float(s.split('=')[1].strip())
                state = "DIST_HEADER"

        else:
            state, completed = _step_distance_tail(s, state, current)
            if completed:
                rows.append(_emit_row(current, block_index, settings))
                block_index += 1
                current = {}

    if not rows:
        raise QVMParseError("No valid measurement blocks found in the file.")
    return pd.DataFrame(rows)


def parse_qvm_content(content: str, settings: Optional[dict] = None) -> pd.DataFrame:
    """Parse raw QVM text log content into a Pandas DataFrame.

    Auto-detects format by checking whether the first 'Circle: Via_' marker
    appears before any 'Circle: Pad_' marker (Via-to-Pad) or after one
    (Pad-to-Via). The resulting DataFrame carries a 'Process' column tagged
    'Via to Pad' or 'Pad to Via' — this is the source of truth for routing,
    regardless of what the user named the file.
    """
    if settings is None:
        settings = load_settings()
    first_via = content.find('Circle: Via_')
    first_pad = content.find('Circle: Pad_')
    via_first = first_via != -1 and (first_pad == -1 or first_via < first_pad)
    if via_first or 'VtP[' in content:
        df = _parse_via_to_pad(content, settings)
        df['Process'] = 'Via to Pad'
    else:
        df = _parse_pad_to_via(content, settings)
        df['Process'] = 'Pad to Via'
    return df


def parse_qvm_file(filepath: str, settings: Optional[dict] = None) -> pd.DataFrame:
    """Read a file and parse it."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise QVMParseError(f"Error reading file: {e}")
    return parse_qvm_content(content, settings)
