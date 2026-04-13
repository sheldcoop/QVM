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
    # Assuming config is always relative to this file for now
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'settings.yaml')
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        # Fallback or handle differently
        raise

def parse_filename(filename: str) -> Dict[str, str]:
    """
    Extract Process, Panel Number, and Side from the filename.
    Format: [Process]_[Measurement Type]_Panel [Panel Number]_[Side].txt
    Example: Post PFC_Pad to Via_Panel 20_F.txt
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
        # parts[1] is measurement type

        # Panel
        panel_part = parts[2]
        if panel_part.startswith('Panel '):
            result['Panel Number'] = panel_part.replace('Panel ', '')
        else:
            result['Panel Number'] = panel_part

        # Side
        result['Side'] = parts[3]
    elif len(parts) > 0:
        # Best effort
        result['Process'] = parts[0]

    return result

def parse_qvm_content(content: str) -> pd.DataFrame:
    """
    Parse the raw QVM text log content into a Pandas DataFrame.

    Raises:
        QVMParseError: If the file format is invalid or expected data is missing.
    """
    settings = load_settings()
    col_names = settings.get('COLUMN_NAMES', {})
    grid_mapping = settings.get('GRID_MAPPING', {})

    # Regex patterns
    # Matches: Circle: Pad_LL_2(ID:1, From 180 Pts.)
    #          Coord. X =        63.857203
    #          Coord. Y =       104.634501
    #          Diameter =         0.308911
    pad_pattern = re.compile(
        r"Circle:\s+Pad_([A-Z]{2}_\d+)\(ID:\d+,\s*From\s+(\d+)\s*Pts\.\).*?\s*"
        r"Coord\.\s*X\s*=\s*([-\d.]+)\s*"
        r"Coord\.\s*Y\s*=\s*([-\d.]+)\s*"
        r"Diameter\s*=\s*([-\d.]+)",
        re.DOTALL
    )

    # Matches: Circle: Via_LL_2(ID:2, From 70 Pts.)
    #          Coord. X =        63.856611
    #          Coord. Y =       104.630820
    #          Diameter =         0.016742
    via_pattern = re.compile(
        r"Circle:\s+Via_([A-Z]{2}_\d+)\(ID:\d+,\s*From\s+(\d+)\s*Pts\.\).*?\s*"
        r"Coord\.\s*X\s*=\s*([-\d.]+)\s*"
        r"Coord\.\s*Y\s*=\s*([-\d.]+)\s*"
        r"Diameter\s*=\s*([-\d.]+)",
        re.DOTALL
    )

    # Matches: Distance: PtV_LL_2(ID:3) between Via_LL_2(ID:2) and Pad_LL_2(ID:1)
    #           SC =         0.003728
    #           DX =         0.000592
    #           DY =         0.003681
    dist_pattern = re.compile(
        r"Distance:\s+PtV_([A-Z]{2}_\d+)\(ID:\d+\).*?\s*"
        r"SC\s*=\s*([-\d.]+)\s*"
        r"DX\s*=\s*([-\d.]+)\s*"
        r"DY\s*=\s*([-\d.]+)",
        re.DOTALL
    )

    parsed_data = {}

    # Find all Pads and extract point count
    for match in pad_pattern.finditer(content):
        loc = match.group(1)
        pts = int(match.group(2))
        diameter = float(match.group(5))
        if loc not in parsed_data:
            parsed_data[loc] = {}
        parsed_data[loc]['pad_diameter'] = diameter
        parsed_data[loc]['pad_pts'] = pts

    # Find all Vias and extract point count
    for match in via_pattern.finditer(content):
        loc = match.group(1)
        pts = int(match.group(2))
        diameter = float(match.group(5))
        if loc not in parsed_data:
            parsed_data[loc] = {}
        parsed_data[loc]['via_diameter'] = diameter
        parsed_data[loc]['via_pts'] = pts

    # Find all Distances
    for match in dist_pattern.finditer(content):
        loc = match.group(1)
        sc = float(match.group(2))
        dx = float(match.group(3))
        dy = float(match.group(4))

        if loc not in parsed_data:
            parsed_data[loc] = {}
        parsed_data[loc]['sc'] = sc
        parsed_data[loc]['dx'] = dx
        parsed_data[loc]['dy'] = dy

    if not parsed_data:
        raise QVMParseError("No valid Pad, Via, or Distance blocks found in the file.")

    rows = []
    for loc, data in parsed_data.items():
        # Check for completeness
        if 'pad_diameter' not in data or 'via_diameter' not in data or 'sc' not in data:
            continue

        # Create base row with distance measurements
        base_row = {
            col_names.get('location', 'Location'): loc,
            col_names.get('grid_id', 'Grid ID'): grid_mapping.get(loc, None),
            col_names.get('outer_diameter', 'Outer Diameter'): data['pad_diameter'],
            col_names.get('inner_diameter', 'Inner Diameter'): data['via_diameter'],
            col_names.get('ptv_distance', 'PtV Distance'): data['sc'],
            col_names.get('x_distance', 'Shift (DX)'): data['dx'],
            col_names.get('y_distance', 'Shift (DY)'): data['dy'],
            'Type': 'PtV',  # Distance measurement type
            'Pts.': None   # PtV measurements don't have point count
        }
        rows.append(base_row)
        
        # Create separate rows for Pad and Via with point counts
        pad_row = base_row.copy()
        pad_row['Type'] = 'Pad'
        pad_row['Pts.'] = data.get('pad_pts', None)
        rows.append(pad_row)
        
        via_row = base_row.copy()
        via_row['Type'] = 'Via'
        via_row['Pts.'] = data.get('via_pts', None)
        rows.append(via_row)

    if not rows:
        raise QVMParseError("Failed to parse complete records from the file.")

    df = pd.DataFrame(rows)
    return df

def parse_qvm_file(filepath: str) -> pd.DataFrame:
    """Read a file and parse it."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise QVMParseError(f"Error reading file: {e}")

    return parse_qvm_content(content)
