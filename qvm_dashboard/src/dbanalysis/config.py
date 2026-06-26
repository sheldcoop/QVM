"""Declarative configuration for every Database Analysis sub-view.

Each Horus sheet used to have its own ~180-line view module that differed only in
the sheet name, which columns are metrics, the spec-limit column prefix, the
display unit, and a Streamlit state-key prefix. That variation is captured here as
data; :mod:`src.dbanalysis.engine` renders all of them with one code path.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Metric:
    """A single measured quantity on a sheet.

    Attributes:
        name:          Display label (e.g. "Ra Mean").
        col:           Column to read, as a normalised name (e.g. "ra mean").
        limit_prefix:  Normalised prefix for spec-limit columns
                       (e.g. "line" -> "line lsl"/"line target"/"line usl"),
                       or ``None`` when the sheet carries no spec limits.
        display_scale: Multiplier applied once before plotting/summarising
                       (e.g. 1000 to show µm source data in nm).
        display_unit:  Unit label shown on axes/titles.
    """
    name: str
    col: str
    limit_prefix: Optional[str] = None
    display_scale: float = 1.0
    display_unit: str = "um"


@dataclass(frozen=True)
class AnalysisConfig:
    """Everything the engine needs to render one sub-view."""
    key: str                      # sub-view label (matches the nav button)
    sheet_name: str               # Horus sheet to read (tolerant match)
    state_prefix: str             # unique prefix for Streamlit widget keys
    short_name: str               # compact label for export folders/filenames
    metrics: List[Metric] = field(default_factory=list)
    split_col: Optional[str] = None  # normalised col to split into separate
                                     # sections (never pooled), e.g. Roughness'
                                     # "measurement position" (BKM vs Next-to-via)


DB_ANALYSES = {
    "Roughness": AnalysisConfig(
        key="Roughness", sheet_name="Roughness", state_prefix="db",
        short_name="Roughness", split_col="measurement position",
        metrics=[
            Metric("Ra Mean", "ra mean", None, 1000.0, "nm"),
            Metric("Rz Mean", "rz mean", None, 1000.0, "nm"),
        ],
    ),
    "Impedance": AnalysisConfig(
        key="Impedance", sheet_name="IMP_Trace", state_prefix="imp",
        short_name="Impedance",
        metrics=[
            Metric("Line", "line", "line", 1.0, "um"),
            Metric("Space", "space", "space", 1.0, "um"),
        ],
    ),
    "Top to Bottom Via": AnalysisConfig(
        key="Top to Bottom Via", sheet_name="Top_to_Bottom_Via", state_prefix="via",
        short_name="Via",
        metrics=[
            Metric("Average Via Depth", "average via depth", None, 1.0, "um"),
            Metric("Top Diameter", "top diameter", None, 1.0, "um"),
            Metric("Bottom Diameter", "bottom diameter", None, 1.0, "um"),
        ],
    ),
    "Trace": AnalysisConfig(
        key="Trace", sheet_name="Trace", state_prefix="trace",
        short_name="Trace",
        metrics=[
            Metric("Line", "line", "line", 1.0, "um"),
            Metric("Space", "space", "space", 1.0, "um"),
        ],
    ),
    "Pad": AnalysisConfig(
        key="Pad", sheet_name="Pad", state_prefix="pad",
        short_name="Pad",
        metrics=[
            Metric("Diameter", "diameter", "diameter", 1.0, "um"),
        ],
    ),
    "Landing Pad": AnalysisConfig(
        key="Landing Pad", sheet_name="Landing_Pad", state_prefix="lp",
        short_name="Landing_Pad",
        metrics=[
            Metric("Landing Pad Diameter", "diameter", "landing pad diameter", 1.0, "um"),
        ],
    ),
}
