"""Tests for the centralized design tokens in src/theme.py."""

import re
import subprocess
import sys
from pathlib import Path

from src import theme

_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def test_palette_values_are_valid_hex():
    assert theme.PALETTE, "palette must not be empty"
    for name, value in theme.PALETTE.items():
        assert _HEX.match(value), f"{name}={value!r} is not a 6-digit hex colour"


def test_semantic_maps_have_expected_sizes():
    assert len(theme.ZONE) == 5
    assert len(theme.ARROW) == 4
    assert set(theme.QUARTER_COLORS) == {"UL", "LL", "LR", "UR"}


def test_semantic_colours_are_drawn_from_palette():
    """Change the palette → the maps follow. Guards that contract."""
    palette_values = set(theme.PALETTE.values())
    for mapping in (theme.ZONE, theme.ARROW, theme.QUARTER_COLORS):
        for key, value in mapping.items():
            assert value in palette_values, f"{key}={value!r} not in PALETTE"


def test_grid_geometry_is_16_unique_cells():
    assert len(theme.GRID_PLOT_POSITIONS) == 16
    assert len(set(theme.GRID_PLOT_POSITIONS.values())) == 16, "cells must be unique"
    # 1-indexed 4×4 grid
    for x, y in theme.GRID_PLOT_POSITIONS.values():
        assert 1 <= x <= 4 and 1 <= y <= 4


def test_plot_to_matrix_round_trips():
    for gid, (x, y) in theme.GRID_PLOT_POSITIONS.items():
        assert theme.plot_to_matrix(x, y) == theme.GRID_MATRIX_POSITIONS[gid]
    # 0-indexed matrix coords stay in range
    for r, c in theme.GRID_MATRIX_POSITIONS.values():
        assert 0 <= r <= 3 and 0 <= c <= 3


def test_quarter_map_and_order_consistent():
    assert theme.QUARTER_ORDER == ["UL", "LL", "LR", "UR"]
    assert set(theme.QUARTER_MAP.values()) == set(theme.QUARTER_ORDER)
    # Grid ID first digit → quarter
    assert theme.QUARTER_MAP["1"] == "UL"
    assert theme.QUARTER_MAP["4"] == "UR"


def test_theme_import_does_not_pull_the_parser():
    """Finding 12: chart modules do `from src import theme`; the package
    init must not make them pay for pandas and the full parser."""
    package_root = Path(__file__).resolve().parent.parent
    probe = (
        "from src import theme; import sys; "
        'print("pandas" in sys.modules); print("src.parser" in sys.modules)'
    )
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=package_root,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    pandas_loaded, parser_loaded = completed.stdout.split()
    assert pandas_loaded == "False", "importing theme loads pandas"
    assert parser_loaded == "False", "importing theme loads src.parser"
