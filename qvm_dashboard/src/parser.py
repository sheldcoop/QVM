import re
import os
import logging
import pandas as pd
from typing import Dict, Any, Optional

from src.utils import load_settings, resolve_columns


logger = logging.getLogger(__name__)


class QVMParseError(Exception):
    """Custom exception for QVM file parsing errors."""
    pass


_PTS_RE = re.compile(r"From\s+(\d+)\s*Pts\.")
_PANEL_RE = re.compile(r'panel[\s_]*(\d+)', re.IGNORECASE)
_SIDE_RE = re.compile(r'[_\s]([fb])\s*$', re.IGNORECASE)


def _parse_value(line: str) -> float:
    """Parse `<label> = <number>` and return the number.

    Raises QVMParseError with the offending line if the format is malformed.
    """
    if '=' not in line:
        raise QVMParseError(f"Malformed measurement line (missing '='): {line!r}")
    try:
        return float(line.split('=', 1)[1].strip())
    except ValueError as e:
        raise QVMParseError(f"Could not parse number from line {line!r}: {e}")


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


_EMIT_KEYS = (
    'location', 'grid_id', 'outer_diameter', 'inner_diameter',
    'coord_x', 'coord_y', 'ptv_distance', 'total_shift',
    'x_distance', 'y_distance', 'pad_pts', 'via_pts',
)


def _emit_row(current: Dict[str, Any], block_index: int, settings: dict) -> dict:
    """Build a single output row dict from the accumulated parser state."""
    cols = resolve_columns(settings, _EMIT_KEYS)
    positional_mapping = settings.get('POSITIONAL_MAPPING', [])
    if block_index < len(positional_mapping):
        grid_id: Optional[int] = int(positional_mapping[block_index])
    else:
        logger.warning(
            "Block index %d exceeds POSITIONAL_MAPPING length %d; Grid ID will be None.",
            block_index, len(positional_mapping),
        )
        grid_id = None
    return {
        cols['location']: current.get('location', ''),
        cols['grid_id']: grid_id,
        cols['outer_diameter']: current.get('pad_diameter'),
        cols['inner_diameter']: current.get('via_diameter'),
        cols['coord_x']: current.get('via_coord_x'),
        cols['coord_y']: current.get('via_coord_y'),
        cols['ptv_distance']: current['sc'],
        cols['total_shift']: current['sc'],
        cols['x_distance']: current['dx'],
        cols['y_distance']: current['dy'],
        cols['pad_pts']: current.get('pad_pts'),
        cols['via_pts']: current.get('via_pts'),
    }


def _step_distance_tail(s: str, state: str, current: Dict[str, Any]):
    """Advance the shared DIST_HEADER → SC → DX → DY tail by one line.

    Returns (new_state, completed) where completed=True signals the block
    is fully parsed and the caller should emit a row.
    """
    if state == "DIST_HEADER" and s.startswith("Distance:"):
        return "SC", False
    if state == "SC" and s.startswith("SC"):
        current['sc'] = _parse_value(s)
        return "DX", False
    if state == "DX" and s.startswith("DX"):
        current['dx'] = _parse_value(s)
        return "DY", False
    if state == "DY" and s.startswith("DY"):
        current['dy'] = _parse_value(s)
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
                current['pad_coord_x'] = _parse_value(s)
                state = "PAD_Y"

        elif state == "PAD_Y":
            if s.startswith("Coord.") and 'Y' in s:
                current['pad_coord_y'] = _parse_value(s)
                state = "PAD_DIAM"

        elif state == "PAD_DIAM":
            if 'Diameter' in s:
                current['pad_diameter'] = _parse_value(s)
                state = "VIA_HEADER"

        elif state == "VIA_HEADER":
            if s.startswith("Circle: Via_"):
                pts_m = _PTS_RE.search(s)
                current['via_pts'] = int(pts_m.group(1)) if pts_m else None
                state = "VIA_X"

        elif state == "VIA_X":
            if s.startswith("Coord.") and 'X' in s:
                current['via_coord_x'] = _parse_value(s)
                state = "VIA_Y"

        elif state == "VIA_Y":
            if s.startswith("Coord.") and 'Y' in s:
                current['via_coord_y'] = _parse_value(s)
                state = "VIA_DIAM"

        elif state == "VIA_DIAM":
            if 'Diameter' in s:
                current['via_diameter'] = _parse_value(s)
                state = "DIST_HEADER"

        else:
            state, completed = _step_distance_tail(s, state, current)
            if completed:
                rows.append(_emit_row(current, block_index, settings))
                block_index += 1
                current = {}

    if state != "IDLE":
        logger.warning("Pad-to-Via file ended mid-block in state %s; trailing data discarded.", state)
    if not rows:
        raise QVMParseError("No valid measurement blocks found in the file.")
    return pd.DataFrame(rows)


def _find_value(lines: list, label: str) -> Optional[float]:
    """Return the number after '=' on the first body line whose text starts with
    `label` (e.g. 'Diameter', 'SC', 'DX', 'DY'), or None if absent/malformed.

    Label-based and forgiving by design: a missing or unparseable line yields
    None rather than raising, so one omission can't abort the whole parse.
    """
    for line in lines:
        s = line.strip()
        if not s.startswith(label):
            continue
        # Guard against partial-word matches: the char after the label must be a
        # separator, not more letters (so 'DX' never matches 'Diameter').
        rest = s[len(label):]
        if rest[:1] not in ('', ' ', '\t', '='):
            continue
        if '=' not in s:
            return None
        try:
            return float(s.split('=', 1)[1].strip())
        except ValueError:
            return None
    return None


def _location_from_marker(marker: str, kind_word: str) -> str:
    """Extract the site location (e.g. 'LL_2') from a Circle marker line.

    Lenient: returns '' when the location suffix is omitted (e.g. a bare
    'Circle: Via(ID:1, ...)') instead of leaking the marker text.
    """
    head = marker.split('(', 1)[0].replace('Circle:', '').strip()  # 'Via_LL_2'
    if head.startswith(kind_word):
        head = head[len(kind_word):]
    return head.lstrip('_').strip()


def _parse_via_to_pad(content: str, settings: dict) -> pd.DataFrame:
    """Parse a Via-to-Pad QVM log.

    Per-block order in source is guaranteed: Via circle → Pad circle → Distance.
    The parser is order-driven and label-based: it segments the file by
    'Circle:'/'Distance:' marker lines, then reads each value by its label. A
    missing field (point count, location suffix, a diameter, or coordinates)
    leaves that field blank instead of derailing the parse, and a block with no
    SC/DX/DY measurement at all is skipped without disturbing its neighbours.

    Note: Via-to-Pad logs do contain absolute Coord. X/Y lines, but they are
    intentionally not captured here (the downstream VtP views work from shifts).
    """
    # --- Segment the file into marker-led blocks. ------------------------- #
    # Each 'Circle:'/'Distance:' line opens a segment; the indented lines below
    # it form that segment's body. Preamble/header lines are ignored naturally.
    markers: list = []  # (kind, marker_line, body_lines)
    body: Optional[list] = None
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("Circle:"):
            kind = "via" if "Via" in s else "pad" if "Pad" in s else "circle"
            body = []
            markers.append((kind, s, body))
        elif s.startswith("Distance:"):
            body = []
            markers.append(("distance", s, body))
        elif body is not None:
            body.append(line)

    # --- Assemble one row per Via-led block, in order. ------------------- #
    rows: list = []
    block_index = 0  # site ordinal; advances per Via block even when skipped
    i, n = 0, len(markers)
    while i < n:
        kind, marker, via_body = markers[i]
        if kind != "via":
            i += 1
            continue

        # Collect this site's pad + distance segments up to the next Via block.
        pad_marker: Optional[str] = None
        pad_body: Optional[list] = None
        dist_body: Optional[list] = None
        j = i + 1
        while j < n and markers[j][0] != "via":
            k2, m2, b2 = markers[j]
            if k2 == "pad" and pad_body is None:
                pad_marker, pad_body = m2, b2
            elif k2 == "distance" and dist_body is None:
                dist_body = b2
            j += 1

        sc = _find_value(dist_body, 'SC') if dist_body is not None else None
        dx = _find_value(dist_body, 'DX') if dist_body is not None else None
        dy = _find_value(dist_body, 'DY') if dist_body is not None else None

        if sc is None and dx is None and dy is None:
            logger.warning(
                "Via-to-Pad block %d (%s) has no SC/DX/DY measurement; skipping it.",
                block_index, _location_from_marker(marker, 'Via') or 'unknown',
            )
            block_index += 1
            i = j
            continue

        via_pts_m = _PTS_RE.search(marker)
        current: Dict[str, Any] = {
            'location': _location_from_marker(marker, 'Via'),
            'via_pts': int(via_pts_m.group(1)) if via_pts_m else None,
            'via_diameter': _find_value(via_body, 'Diameter'),
            'sc': sc, 'dx': dx, 'dy': dy,
        }
        if pad_marker is not None:
            pad_pts_m = _PTS_RE.search(pad_marker)
            current['pad_pts'] = int(pad_pts_m.group(1)) if pad_pts_m else None
            current['pad_diameter'] = _find_value(pad_body, 'Diameter')

        rows.append(_emit_row(current, block_index, settings))
        block_index += 1
        i = j

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
    # Underscore-agnostic so a circle missing its location suffix (e.g. a bare
    # 'Circle: Via(ID:1, ...)') is still detected and routed correctly.
    first_via = content.find('Circle: Via')
    first_pad = content.find('Circle: Pad')
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
