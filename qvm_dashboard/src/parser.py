import re
import pandas as pd
from typing import List, Dict, Any
import yaml
import os

class QVMParseError(Exception):
    """Custom exception for QVM file parsing errors."""
    pass

def load_settings():
    """Load settings from yaml file."""
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        raise

def parse_filename(filename: str) -> Dict[str, str]:
    """
    Extract Process, Panel Number, and Side from the filename.
    Supports two formats:
      4-part: [Process]_[Type]_Panel [N]_[Side].txt  e.g. Post PFC_Pad to Via_Panel 20_F.txt
      3-part: [Process]_Panel [N]_[Side].txt          e.g. Via to Pad_Panel 25_F.txt
    """
    basename = os.path.basename(filename)
    name_without_ext, _ = os.path.splitext(basename)
    parts = name_without_ext.split('_')

    result = {
        'Process': 'Unknown',
        'Panel Number': 'Unknown',
        'Side': 'Unknown'
    }

    if len(parts) >= 4:
        result['Process'] = parts[0]
        panel_part = parts[2]
        result['Panel Number'] = panel_part.replace('Panel ', '')
        result['Side'] = parts[3]
    elif len(parts) == 3:
        result['Process'] = parts[0]
        panel_part = parts[1]
        result['Panel Number'] = panel_part.replace('Panel ', '')
        result['Side'] = parts[2]
    elif len(parts) > 0:
        result['Process'] = parts[0]

    return result


def _parse_blocks(content: str, settings: dict, file_type: str) -> pd.DataFrame:
    """
    Shared positional state machine for both file formats.

    Pad-to-Via order:  Pad → Via → Distance (trigger: 'Circle: Pad_')
    Via-to-Pad order:  Via → Pad → Distance (trigger: 'Circle: Via[')

    Grid IDs are assigned from POSITIONAL_MAPPING by block index (0–15),
    ignoring any IDs or location names embedded in the file.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    positional_mapping = settings.get('POSITIONAL_MAPPING', [])
    pts_re = re.compile(r"From\s+(\d+)\s*Pts\.")

    is_ptv = (file_type == 'PadToVia')

    lines = content.splitlines()
    rows = []
    block_index = 0
    current: Dict[str, Any] = {}

    # States differ by file type but follow same progression:
    # PadToVia: IDLE → PAD_X → PAD_Y → PAD_DIAM → VIA_X → VIA_Y → VIA_DIAM → SC → DX → DY
    # ViaToVia: IDLE → VIA_DIAM → PAD_DIAM → SC → DX → DY
    state = "IDLE"

    for line in lines:
        s = line.strip()

        if state == "IDLE":
            if is_ptv and s.startswith("Circle: Pad_"):
                pts_m = pts_re.search(s)
                current = {
                    'location': s.split('(')[0].replace('Circle: Pad_', '').strip(),
                    'pad_pts': int(pts_m.group(1)) if pts_m else None,
                }
                state = "PAD_X"
            elif not is_ptv and s.startswith("Circle: Via["):
                pts_m = pts_re.search(s)
                current = {
                    'location': s.split('(')[0].replace('Circle: Via', '').strip(),
                    'via_pts': int(pts_m.group(1)) if pts_m else None,
                }
                state = "VIA_DIAM"

        # --- Pad-to-Via states ---
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
                state = "VIA_HEADER" if is_ptv else "DIST_HEADER"

        elif state == "VIA_HEADER":
            if s.startswith("Circle: Via_"):
                pts_m = pts_re.search(s)
                current['via_pts'] = int(pts_m.group(1)) if pts_m else None
                state = "VIA_X"

        elif state == "VIA_X":
            if s.startswith("Coord.") and 'X' in s:
                current['via_coord_x'] = float(s.split('=')[1].strip())
                state = "VIA_Y"

        elif state == "VIA_Y":
            if s.startswith("Coord.") and 'Y' in s:
                current['via_coord_y'] = float(s.split('=')[1].strip())
                state = "VIA_DIAM" if not is_ptv else "VIA_DIAM_PTV"

        elif state == "VIA_DIAM_PTV":
            if 'Diameter' in s:
                current['via_diameter'] = float(s.split('=')[1].strip())
                state = "DIST_HEADER"

        # --- Via-to-Pad states ---
        elif state == "VIA_DIAM":
            if 'Diameter' in s:
                current['via_diameter'] = float(s.split('=')[1].strip())
                state = "PAD_HEADER" if not is_ptv else state

        elif state == "PAD_HEADER":
            if s.startswith("Circle: Pad["):
                pts_m = pts_re.search(s)
                current['pad_pts'] = int(pts_m.group(1)) if pts_m else None
                state = "PAD_DIAM"

        # --- Shared Distance states ---
        elif state == "DIST_HEADER":
            if s.startswith("Distance:"):
                state = "SC"

        elif state == "SC":
            if s.startswith("SC"):
                current['sc'] = float(s.split('=')[1].strip())
                state = "DX"

        elif state == "DX":
            if s.startswith("DX"):
                current['dx'] = float(s.split('=')[1].strip())
                state = "DY"

        elif state == "DY":
            if s.startswith("DY"):
                current['dy'] = float(s.split('=')[1].strip())
                grid_id = positional_mapping[block_index] if block_index < len(positional_mapping) else None
                rows.append({
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
                })
                block_index += 1
                current = {}
                state = "IDLE"

    if not rows:
        raise QVMParseError("No valid measurement blocks found in the file.")

    return pd.DataFrame(rows)


def parse_qvm_content(content: str) -> pd.DataFrame:
    """
    Parse raw QVM text log content into a Pandas DataFrame.
    Auto-detects format: Via-to-Pad (VtP) or Pad-to-Via (PtV).

    Raises:
        QVMParseError: If the file format is invalid or expected data is missing.
    """
    settings = load_settings()
    file_type = 'ViaToVia' if 'VtP[' in content else 'PadToVia'
    return _parse_blocks(content, settings, file_type)


def parse_qvm_file(filepath: str) -> pd.DataFrame:
    """Read a file and parse it."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise QVMParseError(f"Error reading file: {e}")

    return parse_qvm_content(content)
