"""Shrinkage of Pad-to-Via / Via-to-Pad registration files, the company way.

The calculation is the one of ``sample_data/Core Shrinkage Calculation.xlsx``.
Per quadrant, with points 1 (top-left), 2 (bottom-left), 3 (bottom-right) and
4 (top-right):

    X1 = x4 - x1,  X2 = x3 - x2,  Y1 = y1 - y2,  Y2 = y4 - y3

Quadrant shrinkage = mean of (measured length - design length) over the two
lengths of an axis. Full panel = mean of the four quadrants. Sign convention:
measured minus design, so negative = shrink. Only lengths are used, so the
position of the machine origin does not matter.

The design is two numbers: the size of one quadrant in X and in Y
(``REGISTRATION_SHRINKAGE.design_quadrant_mm``, or the boxes in the sidebar).
All four quadrants have that size. Nothing else of the design is needed,
because only lengths inside a quadrant are compared.

No numbers are reported either when the file holds positions relative to each
site, or when a quadrant is further from its design size than shrinkage can
explain (the design of another product).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import pandas as pd

from src.core_shrinkage_math import _to_ppm
from src.utils import resolve_columns

METHOD_LABEL = "Company (distance)"

PROCESS_PTV = "Pad to Via"
PROCESS_VTP = "Via to Pad"
GROUP_COLUMNS = ("Build Up", "Panel", "Side")

_QUADRANTS = ("UL", "LL", "LR", "UR")
# Point numbering inside every quadrant.
_TL, _BL, _BR, _TR = "1", "2", "3", "4"
_DEFAULT_OUTLIER_PPM = 50.0
# A quadrant further than this from its design size is not shrinkage but a wrong
# design (another product) or a wrong file; real shrinkage stays far below it.
_DEFAULT_MAX_PLAUSIBLE_PPM = 2000.0
# Measured points closer together than this fraction of the design span are not
# panel positions at all (each site reported in its own local coordinates).
_COLLAPSED_FRACTION = 0.01
_OUTLIER_COLUMNS = [
    "Quadrant", "X Deviation from FP (ppm)", "Y Deviation from FP (ppm)", "Alert",
]

PointMap = Dict[str, Dict[str, float]]


@dataclass
class ShrinkageResult:
    """Shrinkage of one group of measurements.

    ``lengths`` (measured against design quadrant size) is also filled when the
    result is withheld, so the reader can see why and still judge quadrant
    against quadrant.
    """

    quadrant: pd.DataFrame
    full_panel: pd.DataFrame
    uniformity: pd.DataFrame
    outliers: pd.DataFrame
    warnings: List[str]
    lengths: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def method_label(self) -> str:
        return METHOD_LABEL


def _empty(warnings: List[str], lengths: Optional[pd.DataFrame] = None) -> ShrinkageResult:
    return ShrinkageResult(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), warnings,
        lengths if lengths is not None else pd.DataFrame())


# --------------------------------------------------------------------- settings
def shrinkage_config(settings: dict) -> dict:
    return settings.get("REGISTRATION_SHRINKAGE") or {}


def normalize_build_up(value: object) -> str:
    """'BU-1', 'bu01', 'BU 01' -> 'BU-01'; anything else is returned stripped."""
    text = str(value).strip()
    match = re.fullmatch(r"(?i)bu[\s\-_]*0*(\d+)", text)
    return f"BU-{int(match.group(1)):02d}" if match else text


def normalize_process(value: object) -> str:
    return PROCESS_VTP if PROCESS_VTP.lower() in str(value).lower() else PROCESS_PTV


def design_lengths(settings: dict) -> Optional[tuple]:
    """(X, Y) design size of one quadrant in mm, or None when not set.

    Read from ``REGISTRATION_SHRINKAGE.design_quadrant_mm``; the sidebar boxes
    replace it for the session through :func:`with_design_lengths`.
    """
    size = shrinkage_config(settings).get("design_quadrant_mm") or {}
    try:
        x, y = float(size.get("x")), float(size.get("y"))
    except (TypeError, ValueError):
        return None
    return (x, y) if x > 0.0 and y > 0.0 else None


def with_design_lengths(settings: dict, x_mm: object, y_mm: object) -> dict:
    """A copy of the settings with the design quadrant size replaced."""
    out = dict(settings)
    out["REGISTRATION_SHRINKAGE"] = {
        **shrinkage_config(settings), "design_quadrant_mm": {"x": x_mm, "y": y_mm}}
    return out


def layout_from_lengths(x_mm: float, y_mm: float, gap_x: float = 10.0,
                        gap_y: float = 10.0) -> PointMap:
    """The 16 design points of a panel whose four quadrants are x_mm by y_mm.

    The calculation only uses the lengths inside a quadrant, so where the
    quadrants sit (the gap) changes no number; it is there for the map.
    """
    points: PointMap = {}
    for quadrant in _QUADRANTS:
        left = -(gap_x / 2.0 + x_mm) if quadrant[1] == "L" else gap_x / 2.0
        bottom = gap_y / 2.0 if quadrant[0] == "U" else -(gap_y / 2.0 + y_mm)
        corners = {_TL: (left, bottom + y_mm), _BL: (left, bottom),
                   _BR: (left + x_mm, bottom), _TR: (left + x_mm, bottom + y_mm)}
        for corner, (x, y) in corners.items():
            points[f"{quadrant}_{corner}"] = {"x": x, "y": y}
    return points


def design_for(settings: dict, build_up: object = None, process: object = None) -> Optional[PointMap]:
    """Design points built from the design quadrant size, or None when it is not set.

    One size applies to every Build Up and file type (``build_up`` and
    ``process`` are accepted for callers that have them, and not used).
    """
    lengths = design_lengths(settings)
    if lengths is None:
        return None
    gap = shrinkage_config(settings).get("map_gap_mm") or {}
    return layout_from_lengths(lengths[0], lengths[1],
                               float(gap.get("x", 10.0)), float(gap.get("y", 10.0)))


def measured_point(settings: dict, process: object) -> str:
    """'via' or 'pad': which measured centre the calculation uses for this file type."""
    choice = (shrinkage_config(settings).get("measured_point") or {}).get(
        normalize_process(process), "via")
    return "pad" if str(choice).strip().lower() == "pad" else "via"


def measured_columns(settings: dict, process: object) -> tuple:
    """(location, x, y) column names for the configured measured point."""
    point = measured_point(settings, process)
    keys = ("location", "pad_coord_x", "pad_coord_y") if point == "pad" else (
        "location", "coord_x", "coord_y")
    cols = resolve_columns(settings, keys)
    return cols[keys[0]], cols[keys[1]], cols[keys[2]]


# --------------------------------------------------------------------- geometry
def _point_map(df: pd.DataFrame, location_col: str, x_col: str, y_col: str) -> PointMap:
    points = df[[location_col, x_col, y_col]].dropna().copy()
    points[location_col] = points[location_col].astype(str).str.upper().str.strip()
    # Keep the first occurrence so duplicate rows cannot change the result.
    points = points.drop_duplicates(subset=[location_col], keep="first")
    return {
        row[location_col]: {"x": float(row[x_col]), "y": float(row[y_col])}
        for _, row in points.iterrows()
    }


def _design_map(nominal_coords: Optional[PointMap]) -> PointMap:
    return {
        str(location).upper().strip(): {"x": float(xy["x"]), "y": float(xy["y"])}
        for location, xy in (nominal_coords or {}).items()
        if xy is not None and xy.get("x") is not None and xy.get("y") is not None
    }


def _corners(points: PointMap, quadrant: str) -> Optional[Dict[str, Dict[str, float]]]:
    names = {corner: f"{quadrant}_{corner}" for corner in (_TL, _BL, _BR, _TR)}
    if not all(name in points for name in names.values()):
        return None
    return {corner: points[name] for corner, name in names.items()}


def _company_lengths(corners: Dict[str, Dict[str, float]]) -> Dict[str, float]:
    """The four signed lengths of the company sheet, averaged per axis (mm)."""
    x1 = corners[_TR]["x"] - corners[_TL]["x"]
    x2 = corners[_BR]["x"] - corners[_BL]["x"]
    y1 = corners[_TL]["y"] - corners[_BL]["y"]
    y2 = corners[_TR]["y"] - corners[_BR]["y"]
    return {"x": (x1 + x2) / 2.0, "y": (y1 + y2) / 2.0}


# ---------------------------------------------------------------------- results
def _status(x_ppm: float, y_ppm: float, usl_ppm: Optional[float]) -> Optional[str]:
    if usl_ppm is None:
        return None
    return "Pass" if max(abs(x_ppm), abs(y_ppm)) <= float(usl_ppm) else "Fail"


def _span(points: PointMap, names: List[str]) -> tuple:
    xs = [points[n]["x"] for n in names]
    ys = [points[n]["y"] for n in names]
    return max(xs) - min(xs), max(ys) - min(ys)


def _plausibility(design: PointMap, measured: PointMap,
                  max_plausible_ppm: Optional[float]) -> tuple:
    """(reason to withhold the result or None, measured-vs-design quadrant sizes).

    Two situations make every shrinkage number meaningless, and both occur in
    real files:

    * the file holds each site in its own local coordinates, so all points sit
      within a few microns of each other and there is no panel geometry;
    * the design positions are those of another product, so the "shrinkage" is
      really the difference between two layouts.
    """
    common = [name for name in design if name in measured]
    if len(common) >= 2:
        design_span, measured_span = _span(design, common), _span(measured, common)
        if all(m <= d * _COLLAPSED_FRACTION for m, d in zip(measured_span, design_span) if d > 0):
            return (
                f"The measured positions of all points lie within "
                f"{max(measured_span) * 1000:.0f} um of each other, while the design spans "
                f"{design_span[0]:.1f} x {design_span[1]:.1f} mm. This file holds positions "
                f"relative to each site, not positions on the panel, so shrinkage cannot be "
                f"calculated from it. Export the measurement in panel coordinates.",
                pd.DataFrame())

    rows = []
    for quadrant in _QUADRANTS:
        design_corners, measured_corners = _corners(design, quadrant), _corners(measured, quadrant)
        if design_corners is None or measured_corners is None:
            continue
        d, m = _company_lengths(design_corners), _company_lengths(measured_corners)
        if d["x"] <= 0.0 or d["y"] <= 0.0:
            continue
        rows.append({
            "Quadrant": quadrant,
            "X Measured (mm)": m["x"], "X Design (mm)": d["x"],
            "X Difference (ppm)": _to_ppm(m["x"] / d["x"]),
            "Y Measured (mm)": m["y"], "Y Design (mm)": d["y"],
            "Y Difference (ppm)": _to_ppm(m["y"] / d["y"]),
        })
    lengths = pd.DataFrame(rows).round(3)
    if lengths.empty or max_plausible_ppm is None:
        return None, lengths

    worst = max(lengths["X Difference (ppm)"].abs().max(), lengths["Y Difference (ppm)"].abs().max())
    if worst <= float(max_plausible_ppm):
        return None, lengths
    return (
        f"The measured quadrant size ({lengths['X Measured (mm)'].mean():.3f} x "
        f"{lengths['Y Measured (mm)'].mean():.3f} mm) does not match the design "
        f"({lengths['X Design (mm)'].mean():.3f} x {lengths['Y Design (mm)'].mean():.3f} mm): "
        f"up to {worst:.0f} ppm apart, more than shrinkage can explain (limit "
        f"{float(max_plausible_ppm):.0f} ppm). The design size is probably not that of "
        f"this product (see Shrinkage design size in the sidebar); check it before "
        f"trusting the shrinkage below.",
        lengths)


def compute_distance_shrinkage(
    measured_df: pd.DataFrame,
    nominal_coords: Optional[PointMap],
    location_col: str = "Location",
    x_col: str = "Coord. X",
    y_col: str = "Coord. Y",
    outlier_ppm: float = _DEFAULT_OUTLIER_PPM,
    usl_ppm: Optional[float] = None,
    max_plausible_ppm: Optional[float] = _DEFAULT_MAX_PLAUSIBLE_PPM,
) -> ShrinkageResult:
    """Company shrinkage of one group of measurements against its design."""
    if measured_df.empty:
        return _empty(["No measured rows in scope."])
    missing = [c for c in (location_col, x_col, y_col) if c not in measured_df.columns]
    if missing:
        return _empty([f"Measurement table lacks the column(s): {', '.join(missing)}."])

    design = _design_map(nominal_coords)
    if not design:
        return _empty(["No design positions configured."])
    measured = _point_map(measured_df, location_col, x_col, y_col)

    if not any(name in design for name in measured):
        return _empty([
            "The sites of this file could not be placed on the panel: its positions are "
            "relative to each site, not positions on the panel, so shrinkage cannot be "
            "calculated from it. Export the measurement in panel coordinates."])

    refusal, lengths = _plausibility(design, measured, max_plausible_ppm)
    warnings: List[str] = [] if refusal is None else [refusal]
    rows: List[dict] = []
    for quadrant in _QUADRANTS:
        design_corners = _corners(design, quadrant)
        measured_corners = _corners(measured, quadrant)
        if design_corners is None or measured_corners is None:
            warnings.append(f"Missing corner point(s) for quadrant {quadrant}; skipped.")
            continue
        design_len = _company_lengths(design_corners)
        if design_len["x"] <= 0.0 or design_len["y"] <= 0.0:
            warnings.append(f"Quadrant {quadrant} has no design length; skipped.")
            continue
        measured_len = _company_lengths(measured_corners)
        rows.append({
            "Quadrant": quadrant,
            "X Design (mm)": design_len["x"],
            "X Measured (mm)": measured_len["x"],
            "Delta X (um)": (measured_len["x"] - design_len["x"]) * 1000.0,
            "Shrinkage X (ppm)": _to_ppm(measured_len["x"] / design_len["x"]),
            "Y Design (mm)": design_len["y"],
            "Y Measured (mm)": measured_len["y"],
            "Delta Y (um)": (measured_len["y"] - design_len["y"]) * 1000.0,
            "Shrinkage Y (ppm)": _to_ppm(measured_len["y"] / design_len["y"]),
        })
    if not rows:
        return _empty(warnings or ["No shrinkage could be computed."], lengths)

    quadrants = pd.DataFrame(rows)
    # As in the company sheet: the panel value is the mean of the quadrants.
    fp_x = float(quadrants["Shrinkage X (ppm)"].mean())
    fp_y = float(quadrants["Shrinkage Y (ppm)"].mean())
    full_panel = {
        "Delta X (um)": float(quadrants["Delta X (um)"].mean()),
        "Delta Y (um)": float(quadrants["Delta Y (um)"].mean()),
        "Shrinkage X (ppm)": fp_x,
        "Shrinkage Y (ppm)": fp_y,
        "X-Y Offset (ppm)": fp_x - fp_y,
    }
    uniformity = pd.DataFrame([{
        "QTQ Range X (ppm)": float(quadrants["Shrinkage X (ppm)"].max()
                                   - quadrants["Shrinkage X (ppm)"].min()),
        "QTQ Range Y (ppm)": float(quadrants["Shrinkage Y (ppm)"].max()
                                   - quadrants["Shrinkage Y (ppm)"].min()),
    }])

    deviations = quadrants[["Quadrant"]].copy()
    deviations["X Deviation from FP (ppm)"] = (quadrants["Shrinkage X (ppm)"] - fp_x).abs()
    deviations["Y Deviation from FP (ppm)"] = (quadrants["Shrinkage Y (ppm)"] - fp_y).abs()
    over = deviations[
        (deviations["X Deviation from FP (ppm)"] > outlier_ppm)
        | (deviations["Y Deviation from FP (ppm)"] > outlier_ppm)
    ].copy()
    if over.empty:
        outliers = pd.DataFrame(columns=_OUTLIER_COLUMNS)
    else:
        over["Alert"] = f"More than {outlier_ppm:.0f} ppm from the panel average"
        outliers = over[_OUTLIER_COLUMNS]

    if usl_ppm is not None:
        quadrants["Status"] = [
            _status(x, y, usl_ppm)
            for x, y in zip(quadrants["Shrinkage X (ppm)"], quadrants["Shrinkage Y (ppm)"])
        ]
        full_panel["Status"] = _status(fp_x, fp_y, usl_ppm)

    return ShrinkageResult(
        quadrants.round(3), pd.DataFrame([full_panel]).round(3), uniformity.round(3),
        outliers.round(3), warnings, lengths)


# ----------------------------------------------------------------------- groups
@dataclass
class GroupShrinkage:
    """One Build Up / Panel / Side of one file type, with everything a screen needs."""

    group: Dict[str, str]
    process: str
    point: str
    design: Optional[PointMap]
    result: ShrinkageResult
    measured: pd.DataFrame
    columns: tuple
    lengths: Optional[tuple] = None  # design quadrant size (X, Y) in mm

    @property
    def label(self) -> str:
        return ", ".join(f"{k}: {v}" for k, v in self.group.items()) or "Current scope"



def compute_shrinkage_by_group(
    measured_df: pd.DataFrame,
    settings: dict,
    *,
    group_cols: tuple = GROUP_COLUMNS,
) -> List[GroupShrinkage]:
    """Shrinkage per Build Up / Panel / Side, against the design quadrant size."""
    cfg = shrinkage_config(settings)
    outlier_ppm = float(cfg.get("outlier_ppm", _DEFAULT_OUTLIER_PPM))
    usl_ppm = cfg.get("usl_ppm")
    max_plausible_ppm = cfg.get("max_plausible_ppm", _DEFAULT_MAX_PLAUSIBLE_PPM)
    lengths = design_lengths(settings)
    design = design_for(settings)

    present = [c for c in group_cols if c in measured_df.columns]
    if present and not measured_df.empty:
        groups = [(keys if isinstance(keys, tuple) else (keys,), frame)
                  for keys, frame in measured_df.groupby(present, dropna=False)]
    else:
        groups = [((), measured_df)]

    out: List[GroupShrinkage] = []
    for keys, frame in groups:
        labels = {
            column: ("Unknown" if pd.isna(value) or str(value).strip() == "" else str(value))
            for column, value in zip(present, keys)
        }
        process_values = frame["Process"] if "Process" in frame.columns else pd.Series(dtype=str)
        process = normalize_process(process_values.iloc[0]) if len(process_values) else PROCESS_PTV
        columns = measured_columns(settings, process)
        point = measured_point(settings, process)

        if design is None:
            result = _empty([
                "No design quadrant size is set, so shrinkage is not calculated. Enter it in "
                "the sidebar (Shrinkage design size) or in REGISTRATION_SHRINKAGE."
                "design_quadrant_mm in settings.yaml."])
        else:
            result = compute_distance_shrinkage(
                frame, design, location_col=columns[0], x_col=columns[1], y_col=columns[2],
                outlier_ppm=outlier_ppm, usl_ppm=usl_ppm, max_plausible_ppm=max_plausible_ppm)
        out.append(GroupShrinkage(labels, process, point, design, result, frame, columns, lengths))
    return out


# ---------------------------------------------------------------------- overview
def summary_frame(groups: List[GroupShrinkage]) -> pd.DataFrame:
    """One line per Build Up / Panel / Side: the panel result, or why there is none."""
    rows = []
    for group in groups:
        row: Dict[str, object] = dict(group.group)
        result = group.result
        if result.full_panel.empty:
            reason = result.warnings[0] if result.warnings else "No result"
            row.update({"Result": "No result", "Why": reason.split(". ")[0].rstrip(".") + "."})
        else:
            panel, uniformity = result.full_panel.iloc[0], result.uniformity.iloc[0]
            row.update({
                "Result": str(panel["Status"]) if "Status" in panel else "Reported",
                "Panel X (um)": panel["Delta X (um)"],
                "Panel X (ppm)": panel["Shrinkage X (ppm)"],
                "Panel Y (um)": panel["Delta Y (um)"],
                "Panel Y (ppm)": panel["Shrinkage Y (ppm)"],
                "Quadrant range X (ppm)": uniformity["QTQ Range X (ppm)"],
                "Quadrant range Y (ppm)": uniformity["QTQ Range Y (ppm)"],
                "Alerts": len(result.outliers),
                "Why": "",
            })
        rows.append(row)
    frame = pd.DataFrame(rows)
    if "Why" in frame.columns:  # reasons last
        frame = frame[[c for c in frame.columns if c != "Why"] + ["Why"]]
    return frame
