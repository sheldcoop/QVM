"""Shared pytest fixtures for the QVM dashboard test suite."""

import numpy as np
import pandas as pd
import pytest

from src.utils import load_settings


@pytest.fixture
def settings() -> dict:
    """The real project settings.yaml, loaded once per test."""
    return load_settings()


@pytest.fixture
def vtp_df() -> pd.DataFrame:
    """A 16-site Via-to-Pad dataset spanning all five tolerance zones.

    Includes Coord. X/Y so charts that need absolute coordinates (quiver)
    work. Column names match the settings.yaml defaults.
    """
    rng = np.random.default_rng(42)
    grid = (
        list(range(11, 15))
        + list(range(21, 25))
        + list(range(31, 35))
        + list(range(41, 45))
    )
    df = pd.DataFrame(
        {
            "Location": [f"site_{i}" for i in range(16)],
            "Grid ID": grid,
            "Coord. X": rng.uniform(50, 450, 16),
            "Coord. Y": rng.uniform(50, 450, 16),
            "Shift (DX)": rng.normal(0, 0.004, 16),
            "Shift (DY)": rng.normal(0, 0.004, 16),
        }
    )
    # One distance column, matching what the parser emits; the process-specific
    # header is applied later by src.display_frame.build_display_frame.
    df["PtV Distance"] = np.sqrt(df["Shift (DX)"] ** 2 + df["Shift (DY)"] ** 2)
    return df
