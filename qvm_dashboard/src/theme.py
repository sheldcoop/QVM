"""Catppuccin Mocha design tokens — the ONE home for all chart visuals.

Runtime / user-tunable numbers (thresholds, slider ranges, chart heights) live
in ``config/settings.yaml``.  Pure design tokens — colours, grid geometry,
quarter maps — live here so a re-theme touches a single file.

Every chart module and ``diagnostics.py`` imports from this module; nothing
here imports from the rest of the codebase, so it sits at the bottom of the
dependency graph with no risk of cycles.
"""

from typing import Dict, Tuple

# ---------------------------------------------------------------------------
# Raw Catppuccin Mocha palette — named swatches (https://catppuccin.com)
# ---------------------------------------------------------------------------
PALETTE: Dict[str, str] = {
    'base':     '#1e1e2e',   # darkest background
    'mantle':   '#181825',   # outer paper
    'text':     '#cdd6f4',   # near-white body text
    'overlay0': '#6c7086',   # muted text
    'blue':     '#89b4fa',
    'green':    '#a6e3a1',
    'teal':     '#94e2d5',
    'peach':    '#fab387',
    'red':      '#f38ba8',
    'sky':      '#89dceb',
    'yellow':   '#f9e2af',
    'mauve':    '#cba6f7',
}

# ---------------------------------------------------------------------------
# Semantic background / chrome tokens
# ---------------------------------------------------------------------------
PLOT_BG    = PALETTE['base']                  # inner plot area
PAPER_BG   = PALETTE['mantle']                # outer paper
TEXT       = PALETTE['text']                  # primary text
TEXT_MUTED = PALETTE['overlay0']              # axis hints / captions
SEPARATOR  = 'rgba(205,214,244,0.18)'         # thin divider lines
CARD_BG    = 'rgba(205,214,244,0.06)'         # annotation card fill
CARD_BD    = 'rgba(205,214,244,0.22)'         # annotation card border
CROSSHAIR  = 'rgba(205,214,244,0.25)'         # axis crosshairs

# ---------------------------------------------------------------------------
# Semantic colour maps (built from PALETTE — change the palette, not these)
# ---------------------------------------------------------------------------
# Five tolerance zones, best → worst (bullseye rings, SC bars, box dots).
ZONE: Dict[str, str] = {
    'exceptional': PALETTE['blue'],
    'excellent':   PALETTE['green'],
    'good':        PALETTE['teal'],
    'acceptable':  PALETTE['peach'],
    'fail':        PALETTE['red'],
}

# Quiver arrow patterns (ABF distortion map).
ARROW: Dict[str, str] = {
    'expansion':   PALETTE['red'],     # moving outward
    'contraction': PALETTE['sky'],     # moving inward
    'twist':       PALETTE['yellow'],  # tangential
    'offset':      PALETTE['blue'],    # uniform / unaligned
}

# Panel-quarter accent colours (box plot per-quarter boxes).
QUARTER_COLORS: Dict[str, str] = {
    'UL': PALETTE['sky'],
    'LL': PALETTE['yellow'],
    'LR': PALETTE['green'],
    'UR': PALETTE['mauve'],
}

# ---------------------------------------------------------------------------
# Structural grid constants (shared by quiver + heatmap + diagnostics)
# ---------------------------------------------------------------------------

# Grid ID → (plot_x, plot_y) on the 4×4 grid (1-indexed, origin bottom-left).
GRID_PLOT_POSITIONS: Dict[str, Tuple[int, int]] = {
    '11': (1, 4), '12': (1, 3), '13': (2, 3), '14': (2, 4),
    '21': (1, 2), '22': (1, 1), '23': (2, 1), '24': (2, 2),
    '31': (3, 2), '32': (3, 1), '33': (4, 1), '34': (4, 2),
    '41': (3, 4), '42': (3, 3), '43': (4, 3), '44': (4, 4),
}


def plot_to_matrix(plot_x: int, plot_y: int) -> Tuple[int, int]:
    """Convert 1-indexed plot coords to 0-indexed (row, col) for a heatmap."""
    return (plot_y - 1, plot_x - 1)


# Grid ID → (matrix_row, matrix_col).
GRID_MATRIX_POSITIONS: Dict[str, Tuple[int, int]] = {
    gid: plot_to_matrix(x, y) for gid, (x, y) in GRID_PLOT_POSITIONS.items()
}

# Quarter prefix (first Grid ID digit) → quarter label, and canonical order.
QUARTER_MAP: Dict[str, str] = {'1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'}
QUARTER_ORDER = ['UL', 'LL', 'LR', 'UR']
