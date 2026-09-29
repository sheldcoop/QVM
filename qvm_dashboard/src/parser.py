"""Unified QVM registration parser.

This module parses both Pad-to-Via and Via-to-Pad exports through one
coordinate-first engine:

- Extract site measurements from loosely formatted Circle/Distance blocks.
- Infer process as a row tag (Via to Pad / Pad to Via).
- Assign canonical site identity (UL/LL/LR/UR + 1..4) from coordinates,
  independent of naming conventions and block order.

Location strings in headers are treated only as weak hints for diagnostics.
"""

import os
import re
import math
import logging
import itertools
from typing import Dict, Any, Optional, List, Tuple

import pandas as pd

from src.utils import load_settings, resolve_columns


logger = logging.getLogger(__name__)


class QVMParseError(Exception):
    """Custom exception for QVM file parsing errors."""
    pass


_PTS_RE = re.compile(r"From\s+(\d+)\s*Pts\.")
_PANEL_RE = re.compile(r'(?:panel[\s_]*|(?:^|[_\s-])p)(\d+)(?=$|[_\s-])', re.IGNORECASE)
_SIDE_RE = re.compile(r'(?:^|[_\s-])(front|back|[fb])(?=$|[_\s-])', re.IGNORECASE)
_BU_RE = re.compile(r'(?:^|[_\s-])bu[-_\s]?(\d+)(?=$|[_\s-])', re.IGNORECASE)
_CIRCLE_RE = re.compile(r'^Circle:\s*(.+?)\s*\(')
_LOC_RE = re.compile(r'\b([UL][LR])[_\s-]?(\d)\b', re.IGNORECASE)

_EMIT_KEYS = (
    'location', 'grid_id', 'outer_diameter', 'inner_diameter',
    'coord_x', 'coord_y', 'ptv_distance',
    'x_distance', 'y_distance', 'pad_pts', 'via_pts',
)


def _parse_value(line: str) -> float:
    if '=' not in line:
        raise QVMParseError(f"Malformed measurement line (missing '='): {line!r}")
    try:
        return float(line.split('=', 1)[1].strip())
    except ValueError as e:
        raise QVMParseError(f"Could not parse number from line {line!r}: {e}")


def _value_after_equals(s: str) -> Optional[float]:
    try:
        return float(s.split('=', 1)[1].strip())
    except (IndexError, ValueError):
        return None


def parse_filename(filename: str) -> Dict[str, Optional[str]]:
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
        format_hint = None

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


def _canonical_location(raw: str) -> str:
    m = _LOC_RE.search(raw or '')
    if not m:
        return ''
    quad, idx = m.group(1).upper(), m.group(2)
    return f"{quad}_{idx}"


def _extract_location_from_circle(label: str) -> str:
    if not label:
        return ''
    base = label.strip()
    direct = _canonical_location(base)
    if direct:
        return direct
    lowered = base.lower()
    for token in ('via', 'pad'):
        lowered = re.sub(rf'(^|[_\s-]){token}($|[_\s-])', '_', lowered, flags=re.IGNORECASE)
    return _canonical_location(lowered)


def _circle_kind(label: str) -> Optional[str]:
    s = (label or '').lower()
    has_via = 'via' in s
    has_pad = 'pad' in s
    if has_via and not has_pad:
        return 'via'
    if has_pad and not has_via:
        return 'pad'
    return None


def _distance_process_hint(label: str) -> Optional[str]:
    s = (label or '').lower()
    if 'ptv' in s:
        return 'Pad to Via'
    if 'vtp' in s or 'btp' in s:
        return 'Via to Pad'
    return None


def _new_site() -> Dict[str, Any]:
    return {
        'circles': [],
        'active_idx': None,
        'untyped_diams': [],
        'untyped_coords': [],
        'pending_x': None,
        'distance_label': '',
        'sc': None,
        'dx': None,
        'dy': None,
    }


def _add_coord(site: Dict[str, Any], axis: str, value: Optional[float]) -> None:
    if value is None:
        return
    idx = site.get('active_idx')
    if idx is not None and 0 <= idx < len(site['circles']):
        site['circles'][idx][axis] = value
        return

    if axis == 'x':
        site['pending_x'] = value
        return

    px = site.get('pending_x')
    if px is None:
        return
    site['untyped_coords'].append((px, value))
    site['pending_x'] = None


def _extract_sites(content: str) -> List[Dict[str, Any]]:
    sites: List[Dict[str, Any]] = []
    site = _new_site()

    for line in content.splitlines():
        s = line.strip()
        if not s:
            continue

        m = _CIRCLE_RE.match(s)
        if m:
            label = m.group(1).strip()
            pts_m = _PTS_RE.search(s)
            site['circles'].append({
                'label': label,
                'kind': _circle_kind(label),
                'location': _extract_location_from_circle(label),
                'pts': int(pts_m.group(1)) if pts_m else None,
                'x': None,
                'y': None,
                'diameter': None,
            })
            site['active_idx'] = len(site['circles']) - 1
            continue

        if s.startswith('Distance:'):
            site['distance_label'] = s
            site['active_idx'] = None
            continue

        if s.startswith('Coord.') and 'X' in s:
            _add_coord(site, 'x', _value_after_equals(s))
            continue

        if s.startswith('Coord.') and 'Y' in s:
            _add_coord(site, 'y', _value_after_equals(s))
            continue

        if 'Diameter' in s:
            val = _value_after_equals(s)
            idx = site.get('active_idx')
            if idx is not None and 0 <= idx < len(site['circles']):
                site['circles'][idx]['diameter'] = val
            else:
                site['untyped_diams'].append(val)
            continue

        if s.startswith('SC'):
            site['sc'] = _value_after_equals(s)
            continue

        if s.startswith('DX'):
            site['dx'] = _value_after_equals(s)
            continue

        if s.startswith('DY'):
            site['dy'] = _value_after_equals(s)
            sites.append(site)
            site = _new_site()

    return sites


def _resolve_site_measurements(site: Dict[str, Any]) -> Dict[str, Any]:
    circles = site['circles']
    via_circle = next((c for c in circles if c.get('kind') == 'via'), None)
    pad_circle = next((c for c in circles if c.get('kind') == 'pad'), None)

    if via_circle is None and circles:
        via_circle = circles[0]
    if pad_circle is None and len(circles) > 1:
        pad_circle = circles[1]

    untyped_diams = list(site.get('untyped_diams') or [])
    untyped_coords = list(site.get('untyped_coords') or [])

    via_diam = via_circle.get('diameter') if via_circle else None
    pad_diam = pad_circle.get('diameter') if pad_circle else None
    if via_diam is None and untyped_diams:
        via_diam = untyped_diams.pop(0)
    if pad_diam is None and untyped_diams:
        pad_diam = untyped_diams.pop(0)

    via_xy = None
    if via_circle and via_circle.get('x') is not None and via_circle.get('y') is not None:
        via_xy = (via_circle['x'], via_circle['y'])
    elif untyped_coords:
        via_xy = untyped_coords.pop(0)

    pad_xy = None
    if pad_circle and pad_circle.get('x') is not None and pad_circle.get('y') is not None:
        pad_xy = (pad_circle['x'], pad_circle['y'])
    elif untyped_coords:
        pad_xy = untyped_coords.pop(0)

    location_hint = ''
    if via_circle and via_circle.get('location'):
        location_hint = via_circle['location']
    elif pad_circle and pad_circle.get('location'):
        location_hint = pad_circle['location']

    process_hint = _distance_process_hint(site.get('distance_label', ''))
    if process_hint is None:
        via_idx = next((i for i, c in enumerate(circles) if c.get('kind') == 'via'), None)
        pad_idx = next((i for i, c in enumerate(circles) if c.get('kind') == 'pad'), None)
        if via_idx is not None and pad_idx is not None:
            process_hint = 'Via to Pad' if via_idx < pad_idx else 'Pad to Via'

    return {
        'location_hint': location_hint,
        'via_diameter': via_diam,
        'pad_diameter': pad_diam,
        'via_coord_x': via_xy[0] if via_xy else None,
        'via_coord_y': via_xy[1] if via_xy else None,
        'pad_coord_x': pad_xy[0] if pad_xy else None,
        'pad_coord_y': pad_xy[1] if pad_xy else None,
        'via_pts': via_circle.get('pts') if via_circle else None,
        'pad_pts': pad_circle.get('pts') if pad_circle else None,
        'sc': site.get('sc'),
        'dx': site.get('dx'),
        'dy': site.get('dy'),
        'process_hint': process_hint,
    }


def _pick_process(sites: List[Dict[str, Any]]) -> str:
    via_to_pad = sum(1 for s in sites if s.get('process_hint') == 'Via to Pad')
    pad_to_via = sum(1 for s in sites if s.get('process_hint') == 'Pad to Via')
    if via_to_pad >= pad_to_via:
        return 'Via to Pad'
    return 'Pad to Via'


def _quadrant(cx: float, cy: float, x: float, y: float) -> str:
    if x < cx and y >= cy:
        return 'UL'
    if x < cx and y < cy:
        return 'LL'
    if x >= cx and y < cy:
        return 'LR'
    return 'UR'


def _assign_indexes(points: List[Tuple[int, float, float]]) -> Dict[int, int]:
    if not points:
        return {}
    if len(points) == 1:
        return {points[0][0]: 1}

    xs = [p[1] for p in points]
    ys = [p[2] for p in points]
    x_left, x_right = min(xs), max(xs)
    y_top, y_bottom = max(ys), min(ys)

    templates = {
        1: (x_left, y_top),
        2: (x_left, y_bottom),
        3: (x_right, y_bottom),
        4: (x_right, y_top),
    }

    n = min(len(points), 4)
    best_cost = None
    best_assign: Dict[int, int] = {}

    for idx_perm in itertools.permutations((1, 2, 3, 4), n):
        total = 0.0
        local = {}
        for (site_idx, x, y), idx in zip(points[:n], idx_perm):
            tx, ty = templates[idx]
            total += (x - tx) ** 2 + (y - ty) ** 2
            local[site_idx] = idx
        if best_cost is None or total < best_cost:
            best_cost = total
            best_assign = local

    if len(points) > 4:
        # Best effort for unexpected extras: assign by nearest template.
        used = set(best_assign.values())
        for site_idx, x, y in points[4:]:
            nearest = min(
                (idx for idx in templates if idx not in used),
                key=lambda idx: (x - templates[idx][0]) ** 2 + (y - templates[idx][1]) ** 2,
                default=1,
            )
            best_assign[site_idx] = nearest
            used.add(nearest)

    return best_assign


def _assign_locations(sites: List[Dict[str, Any]], settings: dict, warnings: List[str]) -> None:
    grid_mapping = settings.get('GRID_MAPPING', {})
    diag_cfg = settings.get('DIAGNOSTICS', {})
    fallback_cx = float(diag_cfg.get('panel_center_x', 255.0))
    fallback_cy = float(diag_cfg.get('panel_center_y', 257.5))

    observed: List[Tuple[float, float]] = []
    for s in sites:
        x = s.get('via_coord_x')
        y = s.get('via_coord_y')
        if x is None or y is None:
            x = s.get('pad_coord_x')
            y = s.get('pad_coord_y')
        if x is not None and y is not None:
            observed.append((x, y))

    if len(observed) >= 4:
        xs = sorted(p[0] for p in observed)
        ys = sorted(p[1] for p in observed)
        mid = len(observed) // 2
        if len(observed) % 2 == 0:
            cx = (xs[mid - 1] + xs[mid]) / 2.0
            cy = (ys[mid - 1] + ys[mid]) / 2.0
        else:
            cx = xs[mid]
            cy = ys[mid]
    else:
        cx = fallback_cx
        cy = fallback_cy

    quadrant_points: Dict[str, List[Tuple[int, float, float]]] = {'UL': [], 'LL': [], 'LR': [], 'UR': []}

    for i, s in enumerate(sites):
        x = s.get('via_coord_x')
        y = s.get('via_coord_y')
        if x is None or y is None:
            x = s.get('pad_coord_x')
            y = s.get('pad_coord_y')
        if x is None or y is None:
            continue
        q = _quadrant(cx, cy, x, y)
        quadrant_points[q].append((i, x, y))

    resolved: Dict[int, str] = {}
    for q, points in quadrant_points.items():
        assigned = _assign_indexes(points)
        for site_idx, idx in assigned.items():
            resolved[site_idx] = f"{q}_{idx}"

    for i, s in enumerate(sites):
        loc = resolved.get(i, '')
        hint = s.get('location_hint', '')
        if hint and not loc:
            loc = hint
        if hint and loc and hint != loc:
            msg = (
                f"Site {i}: coordinate-based location {loc!r} differs from header location {hint!r}; "
                "using coordinates."
            )
            logger.warning(msg)
            warnings.append(msg)

        s['location'] = loc
        s['grid_id'] = int(grid_mapping[loc]) if loc in grid_mapping else None
        if not loc:
            msg = f"Site {i}: could not resolve location from coordinates."
            logger.warning(msg)
            warnings.append(msg)


def _emit_row(current: Dict[str, Any], settings: dict) -> dict:
    cols = resolve_columns(settings, _EMIT_KEYS)
    return {
        cols['location']: current.get('location', ''),
        cols['grid_id']: current.get('grid_id'),
        cols['outer_diameter']: current.get('pad_diameter'),
        cols['inner_diameter']: current.get('via_diameter'),
        cols['coord_x']: current.get('via_coord_x'),
        cols['coord_y']: current.get('via_coord_y'),
        cols['ptv_distance']: current.get('sc'),
        cols['x_distance']: current.get('dx'),
        cols['y_distance']: current.get('dy'),
        cols['pad_pts']: current.get('pad_pts'),
        cols['via_pts']: current.get('via_pts'),
    }


def _normalize_sc_values(
    sites: List[Dict[str, Any]],
    settings: dict,
    process: str,
    warnings: List[str],
) -> None:
    cfg_key = 'VTP_REGISTRATION' if process == 'Via to Pad' else 'PTV_REGISTRATION'
    cfg = settings.get(cfg_key, {})

    override_enabled = bool(cfg.get('sc_override_enabled', True))
    abs_threshold_um = float(cfg.get('sc_override_abs_error_um', 100.0))
    rel_threshold_pct = float(cfg.get('sc_override_rel_error_pct', 10.0))

    for i, site in enumerate(sites):
        dx = site.get('dx')
        dy = site.get('dy')
        if dx is None or dy is None:
            continue

        calc_sc = math.hypot(dx, dy)
        parsed_sc = site.get('sc')

        if parsed_sc is None:
            site['sc'] = calc_sc
            msg = (
                f"Site {i}: SC missing in source; replaced with sqrt(DX^2+DY^2) = "
                f"{calc_sc * 1000:.1f} um."
            )
            logger.warning(msg)
            warnings.append(msg)
            continue

        abs_error_um = abs(parsed_sc - calc_sc) * 1000.0
        calc_um = abs(calc_sc) * 1000.0
        if calc_um > 0.0:
            rel_error_pct = (abs_error_um / calc_um) * 100.0
        else:
            rel_error_pct = 0.0 if abs_error_um == 0.0 else float('inf')

        is_large_mismatch = abs_error_um > abs_threshold_um and rel_error_pct > rel_threshold_pct
        if is_large_mismatch and override_enabled:
            site['sc'] = calc_sc
            msg = (
                f"Site {i}: SC mismatch detected (parsed={parsed_sc * 1000:.1f} um, "
                f"calculated={calc_um:.1f} um, abs_error={abs_error_um:.1f} um, "
                f"rel_error={rel_error_pct:.1f}%). Using calculated SC."
            )
            logger.warning(msg)
            warnings.append(msg)
        elif is_large_mismatch and not override_enabled:
            msg = (
                f"Site {i}: SC mismatch detected (parsed={parsed_sc * 1000:.1f} um, "
                f"calculated={calc_um:.1f} um, abs_error={abs_error_um:.1f} um, "
                f"rel_error={rel_error_pct:.1f}%). Keeping parsed SC per configuration."
            )
            logger.warning(msg)
            warnings.append(msg)


def parse_qvm_content(content: str, settings: Optional[dict] = None) -> tuple:
    if settings is None:
        settings = load_settings()
    warnings: List[str] = []

    raw_sites = _extract_sites(content)
    if not raw_sites:
        raise QVMParseError("No valid measurement blocks found in the file.")

    sites = [_resolve_site_measurements(s) for s in raw_sites]
    if not sites:
        raise QVMParseError("No valid measurement blocks found in the file.")

    process = _pick_process(sites)
    _assign_locations(sites, settings, warnings)
    _normalize_sc_values(sites, settings, process, warnings)

    rows = [_emit_row(s, settings) for s in sites]
    df = pd.DataFrame(rows)
    df['Process'] = process

    cols = resolve_columns(settings, ('grid_id', 'ptv_distance'))
    grid_id_col_name = cols['grid_id']

    dist_col_name = cols['ptv_distance']
    cfg_key = 'VTP_REGISTRATION' if process == 'Via to Pad' else 'PTV_REGISTRATION'
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

    if df.empty:
        raise QVMParseError("No valid measurement blocks found in the file.")

    return df, warnings


def parse_qvm_file(filepath: str, settings: Optional[dict] = None) -> tuple:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        raise QVMParseError(f"Error reading file: {e}")
    return parse_qvm_content(content, settings)
