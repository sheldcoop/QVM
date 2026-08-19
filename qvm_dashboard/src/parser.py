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
# Accept both long form (Panel 28 / Panel_28 / Panel28) and shorthand (P28).
_PANEL_RE = re.compile(r'(?:panel[\s_]*|(?:^|[_\s-])p)(\d+)(?=$|[_\s-])', re.IGNORECASE)
_SIDE_RE = re.compile(r'(?:^|[_\s-])(front|back|[fb])(?=$|[_\s-])', re.IGNORECASE)
_BU_RE = re.compile(r'(?:^|[_\s-])bu[-_\s]?(\d+)(?=$|[_\s-])', re.IGNORECASE)


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
            'Build Up': 'BU-<NN>' | 'Unknown',
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
    if side_match:
        side_token = side_match.group(1).lower()
        side = 'F' if side_token in ('f', 'front') else 'B'
    else:
        side = 'Unknown'

    bu_match = _BU_RE.search(name_without_ext)
    build_up = f"BU-{bu_match.group(1)}" if bu_match else 'Unknown'

    return {
        'format_hint': format_hint,
        'Panel Number': panel_number,
        'Side': side,
        'Build Up': build_up,
    }


_EMIT_KEYS = (
    'location', 'grid_id', 'outer_diameter', 'inner_diameter',
    'coord_x', 'coord_y', 'ptv_distance', 'total_shift',
    'x_distance', 'y_distance', 'pad_pts', 'via_pts',
)


def _resolve_grid_id(location: str, block_index: int, settings: dict,
                     warnings: list = None) -> Optional[int]:
    """Resolve a site's Grid ID.

    The location name is the source of truth: it maps directly to a Grid ID via
    GRID_MAPPING and is recoverable from any of the Via/Pad/Distance lines, so
    this survives an engineer stripping the suffix off some lines or the blocks
    arriving out of order. POSITIONAL_MAPPING (block order) is the fallback used
    only when no location could be read at all.
    """
    grid_mapping = settings.get('GRID_MAPPING', {})
    if location and location in grid_mapping:
        return int(grid_mapping[location])
    positional_mapping = settings.get('POSITIONAL_MAPPING', [])
    if block_index < len(positional_mapping):
        return int(positional_mapping[block_index])
    msg = (
        "Location %r not in GRID_MAPPING and block index %d exceeds "
        "POSITIONAL_MAPPING length %d; Grid ID will be None."
        % (location, block_index, len(positional_mapping))
    )
    logger.warning(msg)
    if warnings is not None:
        warnings.append(msg)
    return None


def _resolve_location_with_order_check(header_location: Optional[str],
                                       block_index: int, settings: dict,
                                       process_label: str,
                                       warnings: list = None) -> str:
    """Resolve a site's location, label-first, warning if the order changed.

    The location read from the file's header label is the source of truth. It is
    cross-checked against the location POSITIONAL_MAPPING expects for this block
    position; if they disagree, the fiducials likely arrived out of order, so a
    warning is logged and the header-derived location is used. When no header
    label is present, the positional (expected) location is used as a fallback.
    """
    positional = settings.get('POSITIONAL_MAPPING', [])
    reverse_grid = {int(v): k for k, v in settings.get('GRID_MAPPING', {}).items()}
    expected_grid_id = int(positional[block_index]) if block_index < len(positional) else None
    expected_location = reverse_grid.get(expected_grid_id, '')
    if header_location:
        if header_location != expected_location:
            msg = (
                "%s block %d: header says %r but POSITIONAL_MAPPING expected %r — "
                "fiducial order may have changed. Using header-derived location."
                % (process_label, block_index, header_location, expected_location)
            )
            logger.warning(msg)
            if warnings is not None:
                warnings.append(msg)
        return header_location
    return expected_location


def _emit_row(current: Dict[str, Any], block_index: int, settings: dict,
              warnings: list = None) -> dict:
    """Build a single output row dict from the accumulated parser state."""
    cols = resolve_columns(settings, _EMIT_KEYS)
    grid_id: Optional[int] = _resolve_grid_id(
        current.get('location', ''), block_index, settings, warnings)
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


def _parse_pad_to_via(content: str, settings: dict, warnings: list) -> pd.DataFrame:
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
                # Label-first identity with a warning if the file's fiducial
                # order disagrees with POSITIONAL_MAPPING (mirrors Via-to-Pad).
                current['location'] = _resolve_location_with_order_check(
                    current.get('location', ''), block_index, settings, "Pad-to-Via", warnings)
                rows.append(_emit_row(current, block_index, settings, warnings))
                block_index += 1
                current = {}

    if state != "IDLE":
        msg = f"Pad-to-Via file ended mid-block in state {state}; trailing data discarded."
        logger.warning(msg)
        warnings.append(msg)
    if not rows:
        raise QVMParseError("No valid measurement blocks found in the file.")
    return pd.DataFrame(rows)


def _value_after_equals(s: str) -> Optional[float]:
    """Parse the number after '=' on a measurement line, or None if malformed."""
    try:
        return float(s.split('=', 1)[1].strip())
    except (IndexError, ValueError):
        return None


def _parse_via_to_pad(content: str, settings: dict, warnings: list) -> pd.DataFrame:
    """Parse a Via-to-Pad QVM log purely by VALUE position — never by headers.

    The exporter is unreliable about header/label lines: the back-side files drop
    the 'Circle: Pad' and 'Distance:' headers (and sometimes the 'Circle: Via'
    header and the 'LL_*' location suffix) entirely. The measurement VALUES,
    however, are always complete and always in the same order, so this parser
    reads only the value lines and ignores every header, location, and ID:

        per site, in order:   Diameter(via)  Diameter(pad)  SC  DX  DY

    The first diameter belongs to the Via (inner), the second to the Pad (outer);
    SC/DX/DY are that site's shift. Each DY closes a site, so a stray value can
    only disturb its own site, not the ones after it.

    When 'Circle: Via_<loc>' headers are present, the location suffix is extracted
    and cross-checked against POSITIONAL_MAPPING. A warning is logged if the order
    in the file differs from what POSITIONAL_MAPPING expects. When the suffix is
    absent (back-side files), site identity falls back to block order as before.

    Coord. X/Y lines are present in the file but intentionally not captured (the
    downstream VtP views work from shifts). Point counts ('From N Pts.') are read
    from Circle headers when present, on a best-effort basis.
    """
    rows: list = []
    block_index = 0
    diams: list = []          # diameters seen in the current site, in order
    pending_pts: list = []    # 'From N Pts.' from Circle headers in the current site
    header_location: Optional[str] = None   # location suffix from Circle: Via_ header
    sc = dx = dy = None

    for line in content.splitlines():
        s = line.strip()
        if s.startswith("Circle:"):
            m = _PTS_RE.search(s)
            pending_pts.append(int(m.group(1)) if m else None)
            # Best-effort: extract location suffix from Via header when present.
            if "Via_" in s:
                loc = s.split('(')[0].replace('Circle: Via_', '').strip()
                if loc:
                    header_location = loc
        elif s.startswith("Diameter"):
            diams.append(_value_after_equals(s))
        elif s.startswith("SC"):
            sc = _value_after_equals(s)
        elif s.startswith("DX"):
            dx = _value_after_equals(s)
        elif s.startswith("DY"):
            # DY is the last value of a site — close it out and emit.
            dy = _value_after_equals(s)
            location = _resolve_location_with_order_check(
                header_location, block_index, settings, "Via-to-Pad", warnings)
            current: Dict[str, Any] = {
                'location': location,
                'via_diameter': diams[0] if len(diams) > 0 else None,
                'pad_diameter': diams[1] if len(diams) > 1 else None,
                'via_pts': pending_pts[0] if len(pending_pts) > 0 else None,
                'pad_pts': pending_pts[1] if len(pending_pts) > 1 else None,
                'sc': sc, 'dx': dx, 'dy': dy,
            }
            rows.append(_emit_row(current, block_index, settings, warnings))
            block_index += 1
            diams = []
            pending_pts = []
            header_location = None
            sc = dx = dy = None

    if not rows:
        raise QVMParseError("No valid measurement blocks found in the file.")
    return pd.DataFrame(rows)


def parse_qvm_content(content: str, settings: Optional[dict] = None) -> tuple:
    """Parse raw QVM text log content into a DataFrame plus a list of warnings.

    Auto-detects format by checking whether the first 'Circle: Via_' marker
    appears before any 'Circle: Pad_' marker (Via-to-Pad) or after one
    (Pad-to-Via). The resulting DataFrame carries a 'Process' column tagged
    'Via to Pad' or 'Pad to Via' — this is the source of truth for routing,
    regardless of what the user named the file.

    Returns:
        (df, warnings) where warnings is a list of human-readable warning strings
        covering: fiducial order mismatches, unresolvable Grid IDs, missing sites,
        outlier SC distances, and mid-block file truncation.
    """
    if settings is None:
        settings = load_settings()
    warnings: list = []
    # Underscore-agnostic so a circle missing its location suffix (e.g. a bare
    # 'Circle: Via(ID:1, ...)') is still detected and routed correctly.
    first_via = content.find('Circle: Via')
    first_pad = content.find('Circle: Pad')
    via_first = first_via != -1 and (first_pad == -1 or first_via < first_pad)
    if via_first or 'VtP[' in content:
        df = _parse_via_to_pad(content, settings, warnings)
        df['Process'] = 'Via to Pad'
    else:
        df = _parse_pad_to_via(content, settings, warnings)
        df['Process'] = 'Pad to Via'

    col_names = settings.get('COLUMN_NAMES', {})
    grid_id_col_name = col_names.get('grid_id', 'Grid ID')
    positional = settings.get('POSITIONAL_MAPPING', [])
    reverse_grid = {int(v): k for k, v in settings.get('GRID_MAPPING', {}).items()}

    # Warn about fiducials expected by POSITIONAL_MAPPING but absent in the file.
    if grid_id_col_name in df.columns and positional:
        present_gids = set(df[grid_id_col_name].dropna().astype(int).tolist())
        for gid_str in positional:
            gid = int(gid_str)
            if gid not in present_gids:
                loc = reverse_grid.get(gid, f'Grid {gid}')
                msg = (f"Fiducial {gid} ({loc}) expected by POSITIONAL_MAPPING "
                       f"but not found in file.")
                logger.warning(msg)
                warnings.append(msg)

    # Warn about outlier SC distances (> configurable cap).
    dist_col_name = col_names.get('ptv_distance', 'PtV Distance')
    is_vtp = not df.empty and df['Process'].iloc[0] == 'Via to Pad'
    cfg_key = 'VTP_REGISTRATION' if is_vtp else 'PTV_REGISTRATION'
    cap_um = float(settings.get(cfg_key, {}).get('outlier_cap_um', 1000.0))
    cap_mm = cap_um / 1000.0
    if dist_col_name in df.columns:
        outliers = df[df[dist_col_name].notna() & (df[dist_col_name].abs() > cap_mm)]
        for _, row in outliers.iterrows():
            gid = row.get(grid_id_col_name, 'Unknown')
            val_um = row[dist_col_name] * 1000
            msg = (f"Grid ID {gid}: SC = {val_um:.1f} µm — "
                   f"exceeds outlier cap {cap_um:.0f} µm.")
            logger.warning(msg)
            warnings.append(msg)

    return df, warnings


def parse_qvm_file(filepath: str, settings: Optional[dict] = None) -> tuple:
    """Read a file and parse it. Returns (df, warnings) — see parse_qvm_content."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise QVMParseError(f"Error reading file: {e}")
    return parse_qvm_content(content, settings)
