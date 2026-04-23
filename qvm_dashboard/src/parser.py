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


def _parse_via_to_pad_content(content: str, settings: dict) -> pd.DataFrame:
    """
    Parse Via-to-Pad format files using positional block counting.

    Format (Via comes first per block):
        Circle: Via[row,col][x,y](ID:N, From P Pts.)
             Diameter =   0.019730
        Circle: Pad[row,col][x,y](ID:N, From P Pts.)
             Diameter =   0.361984
        Distance: VtP[row,col][x,y](ID:N) between Pad[...] and Via[...]
                   SC =   0.004525
                   DX =  -0.001962
                   DY =   0.004077

    Assigns Grid IDs from POSITIONAL_MAPPING (index 0-15) based on
    top-to-bottom block order, ignoring the messy array IDs in the file.
    """
    col_names = settings.get('COLUMN_NAMES', {})
    positional_mapping = settings.get('POSITIONAL_MAPPING', [])

    lines = content.splitlines()
    rows = []
    block_index = 0
    current: Dict[str, Any] = {}
    # State machine: IDLE → VIA_DIAM → PAD_DIAM → SC → DX → DY
    state = "IDLE"

    via_pts_pattern = re.compile(r"From\s+(\d+)\s*Pts\.")
    array_key_pattern = re.compile(r"([\[\d,\]\s]+\[[\d,]+\])")

    for line in lines:
        stripped = line.strip()

        if state == "IDLE":
            if stripped.startswith("Circle: Via["):
                pts_match = via_pts_pattern.search(stripped)
                key_match = array_key_pattern.search(stripped.replace("Circle: Via", ""))
                current = {
                    'via_pts': int(pts_match.group(1)) if pts_match else None,
                    'location': stripped.split('(')[0].replace('Circle: Via', '').strip(),
                }
                state = "VIA_DIAM"

        elif state == "VIA_DIAM":
            if 'Diameter' in stripped:
                current['via_diameter'] = float(stripped.split('=')[1].strip())
                state = "PAD_HEADER"

        elif state == "PAD_HEADER":
            if stripped.startswith("Circle: Pad["):
                pts_match = via_pts_pattern.search(stripped)
                current['pad_pts'] = int(pts_match.group(1)) if pts_match else None
                state = "PAD_DIAM"

        elif state == "PAD_DIAM":
            if 'Diameter' in stripped:
                current['pad_diameter'] = float(stripped.split('=')[1].strip())
                state = "DIST_HEADER"

        elif state == "DIST_HEADER":
            if stripped.startswith("Distance: VtP["):
                state = "SC"

        elif state == "SC":
            if stripped.startswith("SC"):
                current['sc'] = float(stripped.split('=')[1].strip())
                state = "DX"

        elif state == "DX":
            if stripped.startswith("DX"):
                current['dx'] = float(stripped.split('=')[1].strip())
                state = "DY"

        elif state == "DY":
            if stripped.startswith("DY"):
                current['dy'] = float(stripped.split('=')[1].strip())
                # Block complete — assign positional Grid ID
                grid_id = positional_mapping[block_index] if block_index < len(positional_mapping) else None
                rows.append({
                    col_names.get('location', 'Location'): current.get('location', ''),
                    col_names.get('grid_id', 'Grid ID'): int(grid_id) if grid_id is not None else None,
                    col_names.get('outer_diameter', 'Pad Diameter'): current.get('pad_diameter'),
                    col_names.get('inner_diameter', 'Via Parameter'): current.get('via_diameter'),
                    col_names.get('coord_x', 'Coord. X'): None,
                    col_names.get('coord_y', 'Coord. Y'): None,
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
        raise QVMParseError("No valid Via-to-Pad blocks found in the file.")

    return pd.DataFrame(rows)


def parse_qvm_content(content: str) -> pd.DataFrame:
    """
    Parse raw QVM text log content into a Pandas DataFrame.
    Auto-detects format: Via-to-Pad (VtP) or Pad-to-Via (PtV).

    Raises:
        QVMParseError: If the file format is invalid or expected data is missing.
    """
    settings = load_settings()

    if "VtP[" in content:
        return _parse_via_to_pad_content(content, settings)

    col_names = settings.get('COLUMN_NAMES', {})
    grid_mapping = settings.get('GRID_MAPPING', {})

    pad_pattern = re.compile(
        r"Circle:\s+Pad_([A-Z]{2}_\d+)\(ID:\d+,\s*From\s+(\d+)\s*Pts\.\).*?\s*"
        r"Coord\.\s*X\s*=\s*([-\d.]+)\s*"
        r"Coord\.\s*Y\s*=\s*([-\d.]+)\s*"
        r"Diameter\s*=\s*([-\d.]+)",
        re.DOTALL
    )

    via_pattern = re.compile(
        r"Circle:\s+Via_([A-Z]{2}_\d+)\(ID:\d+,\s*From\s+(\d+)\s*Pts\.\).*?\s*"
        r"Coord\.\s*X\s*=\s*([-\d.]+)\s*"
        r"Coord\.\s*Y\s*=\s*([-\d.]+)\s*"
        r"Diameter\s*=\s*([-\d.]+)",
        re.DOTALL
    )

    dist_pattern = re.compile(
        r"Distance:\s+PtV_([A-Z]{2}_\d+)\(ID:\d+\).*?\s*"
        r"SC\s*=\s*([-\d.]+)\s*"
        r"DX\s*=\s*([-\d.]+)\s*"
        r"DY\s*=\s*([-\d.]+)",
        re.DOTALL
    )

    parsed_data = {}

    for match in pad_pattern.finditer(content):
        loc = match.group(1)
        if loc not in parsed_data:
            parsed_data[loc] = {}
        parsed_data[loc]['pad_diameter'] = float(match.group(5))
        parsed_data[loc]['pad_pts'] = int(match.group(2))
        parsed_data[loc]['pad_coord_x'] = float(match.group(3))
        parsed_data[loc]['pad_coord_y'] = float(match.group(4))

    for match in via_pattern.finditer(content):
        loc = match.group(1)
        if loc not in parsed_data:
            parsed_data[loc] = {}
        parsed_data[loc]['via_diameter'] = float(match.group(5))
        parsed_data[loc]['via_pts'] = int(match.group(2))
        parsed_data[loc]['via_coord_x'] = float(match.group(3))
        parsed_data[loc]['via_coord_y'] = float(match.group(4))

    for match in dist_pattern.finditer(content):
        loc = match.group(1)
        if loc not in parsed_data:
            parsed_data[loc] = {}
        parsed_data[loc]['sc'] = float(match.group(2))
        parsed_data[loc]['dx'] = float(match.group(3))
        parsed_data[loc]['dy'] = float(match.group(4))

    if not parsed_data:
        raise QVMParseError("No valid Pad, Via, or Distance blocks found in the file.")

    rows = []
    for loc, data in parsed_data.items():
        if 'pad_diameter' not in data or 'via_diameter' not in data or 'sc' not in data:
            continue
        row = {
            col_names.get('location', 'Location'): loc,
            col_names.get('grid_id', 'Grid ID'): grid_mapping.get(loc, None),
            col_names.get('ptv_distance', 'PtV Distance'): data['sc'],
            col_names.get('x_distance', 'Shift (DX)'): data['dx'],
            col_names.get('y_distance', 'Shift (DY)'): data['dy'],
            col_names.get('outer_diameter', 'Pad Diameter'): data['pad_diameter'],
            col_names.get('inner_diameter', 'Via Parameter'): data['via_diameter'],
            col_names.get('coord_x', 'Coord. X'): data.get('via_coord_x'),
            col_names.get('coord_y', 'Coord. Y'): data.get('via_coord_y'),
            col_names.get('total_shift', 'SC'): data['sc'],
            col_names.get('item_type', 'Type'): 'Via',
            col_names.get('pad_pts', 'Pad Pts.'): data.get('pad_pts'),
            col_names.get('via_pts', 'Via Pts.'): data.get('via_pts'),
        }
        rows.append(row)

    if not rows:
        raise QVMParseError("Failed to parse complete records from the file.")

    return pd.DataFrame(rows)


def parse_qvm_file(filepath: str) -> pd.DataFrame:
    """Read a file and parse it."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise QVMParseError(f"Error reading file: {e}")

    return parse_qvm_content(content)
