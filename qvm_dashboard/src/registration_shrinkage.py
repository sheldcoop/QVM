"""Shrinkage of Pad-to-Via / Via-to-Pad registration files.

Three methods answer the same question ("how much did the panel change size
against its design?") with different amounts of the measured data. Sign
convention everywhere: measured minus design, so negative = shrink.

``company`` — the company workbook (``sample_data/Core Shrinkage Calculation.xlsx``)
    Per quadrant, with points 1 (top-left), 2 (bottom-left), 3 (bottom-right),
    4 (top-right):  X1 = x4 - x1, X2 = x3 - x2, Y1 = y1 - y2, Y2 = y4 - y3.
    Quadrant shrinkage = mean of (measured length - design length) over the two
    lengths of an axis. Full panel = mean of the four quadrants. Uses only the
    8 lengths inside the quadrants; no alignment of any kind.

``centre`` — indirect centre
    The centre is taken as the average of the points (measured and design
    separately), every position is expressed relative to it, and the scale of
    an axis is the least-squares slope of measured against design. Per quadrant
    this gives the same number as the company method; for the full panel it
    also uses the distances *between* quadrants.

``affine`` — least-squares affine fit, as in the Core Shrinkage tab
    Fits translation, rotation, X scale, Y scale and shear to all points at
    once, rejects outlier points, and reports what is left over (residuals).
    Reuses the kernels in ``src.core_shrinkage_math``.

Design positions come from ``REGISTRATION_SHRINKAGE.DESIGNS`` in settings.yaml,
per Build Up and file type. When the data's Build Up / file type has no entry
(for example a file name without a Build Up), another configured design is
used, but only if all configured designs have the same shape and differ by a
pure shift: a shift changes none of the three methods' results. Otherwise the
group gets a warning and no numbers. The core design is never used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from src.core_shrinkage_math import _affine_fit, _detect_outliers, _to_ppm
from src.utils import resolve_columns

METHOD_COMPANY = "company"
METHOD_CENTRE = "centre"
METHOD_AFFINE = "affine"
METHOD_LABELS: Dict[str, str] = {
    METHOD_COMPANY: "Company (distance)",
    METHOD_CENTRE: "Centre-based",
    METHOD_AFFINE: "Affine fit",
}
METHOD_USES: Dict[str, str] = {
    METHOD_COMPANY: "8 lengths inside the quadrants; panel = mean of 4 quadrants",
    METHOD_CENTRE: "all points about their own centre; X and Y scale only",
    METHOD_AFFINE: "all points; scale, rotation and shear separated; outlier points rejected",
}

PROCESS_PTV = "Pad to Via"
PROCESS_VTP = "Via to Pad"
GROUP_COLUMNS = ("Build Up", "Panel", "Side")

_QUADRANTS = ("UL", "LL", "LR", "UR")
# Point numbering inside every quadrant.
_TL, _BL, _BR, _TR = "1", "2", "3", "4"
_DEFAULT_OUTLIER_PPM = 50.0
_DEFAULT_OUTLIER_UM = 50.0
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
    """Result of one method for one group of measurements.

    ``quadrant`` / ``full_panel`` / ``uniformity`` / ``outliers`` have the same
    columns for every method, so screens and reports can show any of them.
    ``details`` (one row) and ``points`` (one row per point) are only filled by
    the affine method.
    """

    quadrant: pd.DataFrame
    full_panel: pd.DataFrame
    uniformity: pd.DataFrame
    outliers: pd.DataFrame
    warnings: List[str]
    method: str = METHOD_COMPANY
    details: pd.DataFrame = field(default_factory=pd.DataFrame)
    points: pd.DataFrame = field(default_factory=pd.DataFrame)
    # Measured against design quadrant size. Also filled when the result is
    # withheld, so the reader can see why (and still judge quadrant against quadrant).
    lengths: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def method_label(self) -> str:
        return METHOD_LABELS.get(self.method, self.method)


def _empty(method: str, warnings: List[str],
           lengths: Optional[pd.DataFrame] = None) -> ShrinkageResult:
    return ShrinkageResult(
        pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), warnings, method,
        lengths=lengths if lengths is not None else pd.DataFrame())


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


def design_for(settings: dict, build_up: object, process: object) -> Optional[PointMap]:
    """Design positions for one Build Up and file type, or None when not configured."""
    cfg = shrinkage_config(settings)
    designs = cfg.get("DESIGNS") or {}
    product = designs.get(cfg.get("active_design")) or {}
    by_build_up = {normalize_build_up(k): v for k, v in product.items()}
    by_process = by_build_up.get(normalize_build_up(build_up)) or {}
    positions = {normalize_process(k): v for k, v in by_process.items()}.get(
        normalize_process(process))
    return positions or None


def _all_designs(settings: dict) -> List[tuple]:
    """Every configured design of the active product as (Build Up, file type, positions)."""
    cfg = shrinkage_config(settings)
    product = (cfg.get("DESIGNS") or {}).get(cfg.get("active_design")) or {}
    return [
        (normalize_build_up(build_up), normalize_process(process), positions)
        for build_up, by_process in product.items()
        for process, positions in (by_process or {}).items()
        if positions
    ]


def _same_shape(first: PointMap, second: PointMap, tolerance_mm: float = 1e-6) -> bool:
    """True when two designs have the same points and differ only by one shift."""
    a, b = _design_map(first), _design_map(second)
    if set(a) != set(b) or not a:
        return False
    names = sorted(a)
    delta = np.array([[b[n]["x"] - a[n]["x"], b[n]["y"] - a[n]["y"]] for n in names])
    return bool(np.all(np.abs(delta - delta[0]) <= tolerance_mm))


def resolve_design(settings: dict, build_up: object, process: object) -> tuple:
    """(design positions or None, note or None) for one Build Up and file type.

    The exact entry is used when there is one. Otherwise a stand-in is taken
    from the configured designs (same file type preferred), provided all of
    them have the same shape; the note says which one and why that is safe.
    """
    exact = design_for(settings, build_up, process)
    if exact is not None:
        return exact, None
    wanted = f"{normalize_build_up(build_up)} / {normalize_process(process)}"
    candidates = _all_designs(settings)
    if not candidates or not shrinkage_config(settings).get("fallback_to_equivalent_design", True):
        return None, None
    if not all(_same_shape(candidates[0][2], other[2]) for other in candidates[1:]):
        return None, (
            f"No design positions configured for {wanted}, and the configured designs "
            f"differ in shape, so none of them can stand in.")
    same_type = [c for c in candidates if c[1] == normalize_process(process)]
    source_build_up, source_process, positions = (same_type or candidates)[0]
    return positions, (
        f"No design positions configured for {wanted}; those of {source_build_up} / "
        f"{source_process} are used. All configured designs have the same shape and differ "
        f"only by a shift, which does not change the shrinkage result.")


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


def _matched(design: PointMap, measured: PointMap, locations: List[str]) -> tuple:
    names = [name for name in locations if name in design and name in measured]
    design_xy = np.array([[design[n]["x"], design[n]["y"]] for n in names], dtype=float)
    measured_xy = np.array([[measured[n]["x"], measured[n]["y"]] for n in names], dtype=float)
    return names, design_xy, measured_xy


def _centre_scale(design_xy: np.ndarray, measured_xy: np.ndarray) -> Optional[tuple]:
    """(scale_x, scale_y): slope of measured against design, both about their own centre."""
    if len(design_xy) < 2:
        return None
    design_c = design_xy - design_xy.mean(axis=0)
    measured_c = measured_xy - measured_xy.mean(axis=0)
    spread = (design_c ** 2).sum(axis=0)
    if spread[0] == 0.0 or spread[1] == 0.0:
        return None
    slopes = (design_c * measured_c).sum(axis=0) / spread
    return float(slopes[0]), float(slopes[1])


def _quadrant_locations(quadrant: str) -> List[str]:
    return [f"{quadrant}_{corner}" for corner in (_TL, _BL, _BR, _TR)]


# ---------------------------------------------------------------------- results
def _status(x_ppm: float, y_ppm: float, usl_ppm: Optional[float]) -> Optional[str]:
    if usl_ppm is None:
        return None
    return "Pass" if max(abs(x_ppm), abs(y_ppm)) <= float(usl_ppm) else "Fail"


def _assemble(
    method: str,
    quadrant_rows: List[dict],
    full_panel: dict,
    warnings: List[str],
    outlier_ppm: float,
    usl_ppm: Optional[float],
    details: Optional[pd.DataFrame] = None,
    points: Optional[pd.DataFrame] = None,
) -> ShrinkageResult:
    """Common tail of every method: uniformity, quadrant alerts, pass/fail, rounding."""
    quadrants = pd.DataFrame(quadrant_rows)
    fp_x, fp_y = full_panel["Shrinkage X (ppm)"], full_panel["Shrinkage Y (ppm)"]
    full_panel = dict(full_panel)
    full_panel["X-Y Offset (ppm)"] = fp_x - fp_y

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
        quadrants.round(3),
        pd.DataFrame([full_panel]).round(3),
        uniformity.round(3),
        outliers.round(3),
        warnings,
        method,
        details.round(4) if details is not None else pd.DataFrame(),
        points.round(3) if points is not None else pd.DataFrame(),
    )


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
        f"{float(max_plausible_ppm):.0f} ppm). The design positions are probably not those "
        f"of this product, so shrinkage is not reported. The measured sizes are listed below.",
        lengths)


def _quadrant_row(quadrant: str, design_len: Dict[str, float], scale_x: float, scale_y: float,
                  measured_len: Optional[Dict[str, float]] = None) -> dict:
    """One quadrant line; Delta is the change over the quadrant's design length."""
    if measured_len is None:
        measured_len = {"x": design_len["x"] * scale_x, "y": design_len["y"] * scale_y}
    return {
        "Quadrant": quadrant,
        "X Design (mm)": design_len["x"],
        "X Measured (mm)": measured_len["x"],
        "Delta X (um)": (measured_len["x"] - design_len["x"]) * 1000.0,
        "Shrinkage X (ppm)": _to_ppm(scale_x),
        "Y Design (mm)": design_len["y"],
        "Y Measured (mm)": measured_len["y"],
        "Delta Y (um)": (measured_len["y"] - design_len["y"]) * 1000.0,
        "Shrinkage Y (ppm)": _to_ppm(scale_y),
    }


def compute_shrinkage(
    measured_df: pd.DataFrame,
    nominal_coords: Optional[PointMap],
    *,
    method: str = METHOD_COMPANY,
    location_col: str = "Location",
    x_col: str = "Coord. X",
    y_col: str = "Coord. Y",
    outlier_ppm: float = _DEFAULT_OUTLIER_PPM,
    usl_ppm: Optional[float] = None,
    outlier_um: float = _DEFAULT_OUTLIER_UM,
    max_plausible_ppm: Optional[float] = _DEFAULT_MAX_PLAUSIBLE_PPM,
) -> ShrinkageResult:
    """Shrinkage of one group of measurements against its design, by ``method``.

    No numbers are reported when the measurement cannot be a panel measured
    against this design: positions that are local to each site, or a quadrant
    size further than ``max_plausible_ppm`` from the design.
    """
    if method not in METHOD_LABELS:
        raise ValueError(f"Unknown shrinkage method '{method}'. Use one of {list(METHOD_LABELS)}.")
    if measured_df.empty:
        return _empty(method, ["No measured rows in scope."])
    missing = [c for c in (location_col, x_col, y_col) if c not in measured_df.columns]
    if missing:
        return _empty(method, [f"Measurement table lacks the column(s): {', '.join(missing)}."])

    design = _design_map(nominal_coords)
    if not design:
        return _empty(method, ["No design positions configured."])
    measured = _point_map(measured_df, location_col, x_col, y_col)

    refusal, lengths = _plausibility(design, measured, max_plausible_ppm)
    if refusal is not None:
        return _empty(method, [refusal], lengths)

    warnings: List[str] = []
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

        if method == METHOD_COMPANY:
            measured_len = _company_lengths(measured_corners)
            rows.append(_quadrant_row(
                quadrant, design_len,
                measured_len["x"] / design_len["x"], measured_len["y"] / design_len["y"],
                measured_len))
            continue

        _, design_xy, measured_xy = _matched(design, measured, _quadrant_locations(quadrant))
        if method == METHOD_CENTRE:
            scales = _centre_scale(design_xy, measured_xy)
        else:
            fit = _affine_fit(design_xy, measured_xy)
            scales = (fit["Sx"], fit["Sy"])
        if scales is None:
            warnings.append(f"Quadrant {quadrant} cannot be fitted; skipped.")
            continue
        rows.append(_quadrant_row(quadrant, design_len, scales[0], scales[1]))

    if not rows:
        return _empty(method, warnings or ["No shrinkage could be computed."])
    quadrant_frame = pd.DataFrame(rows)

    if method == METHOD_COMPANY:
        # As in the company sheet: the panel value is the mean of the quadrants.
        full_panel = {
            "Delta X (um)": float(quadrant_frame["Delta X (um)"].mean()),
            "Delta Y (um)": float(quadrant_frame["Delta Y (um)"].mean()),
            "Shrinkage X (ppm)": float(quadrant_frame["Shrinkage X (ppm)"].mean()),
            "Shrinkage Y (ppm)": float(quadrant_frame["Shrinkage Y (ppm)"].mean()),
        }
        result = _assemble(method, rows, full_panel, warnings, outlier_ppm, usl_ppm)
        result.lengths = lengths
        return result

    used = [name for q in quadrant_frame["Quadrant"] for name in _quadrant_locations(q)]
    names, design_xy, measured_xy = _matched(design, measured, used)
    mean_len = {"x": float(quadrant_frame["X Design (mm)"].mean()),
                "y": float(quadrant_frame["Y Design (mm)"].mean())}
    details = points = None

    if method == METHOD_CENTRE:
        scales = _centre_scale(design_xy, measured_xy)
        if scales is None:
            return _empty(method, warnings + ["The points cannot be fitted."])
    else:
        removed, inlier, fit = _detect_outliers(design_xy, measured_xy, outlier_um)
        scales = (fit["Sx"], fit["Sy"])
        predicted = (fit["M"] @ design_xy.T).T + fit["t"]
        residual_um = np.linalg.norm(measured_xy - predicted, axis=1) * 1000.0
        points = pd.DataFrame({
            "Location": names,
            "Residual (um)": residual_um,
            "Rejected": [not keep for keep in inlier],
        })
        details = pd.DataFrame([{
            "Rotation (deg)": fit["theta_deg"],
            "Shear (deg)": fit["shear_deg"],
            "RMS Residual (um)": float(np.sqrt(np.mean(residual_um[inlier] ** 2))),
            "Points Used": int(inlier.sum()),
            "Points Rejected": len(removed),
        }])
        if removed:
            rejected = ", ".join(names[i] for i in removed)
            warnings.append(
                f"Point(s) {rejected} lie more than {outlier_um:g} um off the fit and were "
                f"left out of the panel result.")

    # Delta is expressed over one quadrant length, so it is comparable with the company value.
    full_panel = {
        "Delta X (um)": (scales[0] - 1.0) * mean_len["x"] * 1000.0,
        "Delta Y (um)": (scales[1] - 1.0) * mean_len["y"] * 1000.0,
        "Shrinkage X (ppm)": _to_ppm(scales[0]),
        "Shrinkage Y (ppm)": _to_ppm(scales[1]),
    }
    result = _assemble(method, rows, full_panel, warnings, outlier_ppm, usl_ppm, details, points)
    result.lengths = lengths
    return result


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
    """The company (distance) method. Kept as a named entry point."""
    return compute_shrinkage(
        measured_df, nominal_coords, method=METHOD_COMPANY, location_col=location_col,
        x_col=x_col, y_col=y_col, outlier_ppm=outlier_ppm, usl_ppm=usl_ppm,
        max_plausible_ppm=max_plausible_ppm)


def compare_methods(
    measured_df: pd.DataFrame,
    nominal_coords: Optional[PointMap],
    *,
    location_col: str = "Location",
    x_col: str = "Coord. X",
    y_col: str = "Coord. Y",
    outlier_um: float = _DEFAULT_OUTLIER_UM,
) -> pd.DataFrame:
    """Full-panel result of every method side by side, one row per method."""
    rows = []
    for method in METHOD_LABELS:
        result = compute_shrinkage(
            measured_df, nominal_coords, method=method, location_col=location_col,
            x_col=x_col, y_col=y_col, outlier_um=outlier_um)
        if result.full_panel.empty:
            continue
        panel = result.full_panel.iloc[0]
        row = {
            "Method": result.method_label,
            "Shrinkage X (ppm)": panel["Shrinkage X (ppm)"],
            "Shrinkage Y (ppm)": panel["Shrinkage Y (ppm)"],
            "Rotation (deg)": None,
            "Shear (deg)": None,
            "RMS Residual (um)": None,
            "Points Rejected": None,
            "Uses": METHOD_USES[method],
        }
        if not result.details.empty:
            detail = result.details.iloc[0]
            for name in ("Rotation (deg)", "Shear (deg)", "RMS Residual (um)", "Points Rejected"):
                row[name] = detail[name]
        rows.append(row)
    return pd.DataFrame(rows)


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
    design_note: Optional[str] = None  # set when a stand-in design was used

    @property
    def label(self) -> str:
        return ", ".join(f"{k}: {v}" for k, v in self.group.items()) or "Current scope"

    def compare(self, settings: dict) -> pd.DataFrame:
        location_col, x_col, y_col = self.columns
        return compare_methods(
            self.measured, self.design, location_col=location_col, x_col=x_col, y_col=y_col,
            outlier_um=float(shrinkage_config(settings).get("outlier_um", _DEFAULT_OUTLIER_UM)))


def default_method(settings: dict) -> str:
    method = str(shrinkage_config(settings).get("default_method", METHOD_COMPANY)).lower()
    return method if method in METHOD_LABELS else METHOD_COMPANY


def compute_shrinkage_by_group(
    measured_df: pd.DataFrame,
    settings: dict,
    *,
    method: Optional[str] = None,
    group_cols: tuple = GROUP_COLUMNS,
) -> List[GroupShrinkage]:
    """Shrinkage per Build Up / Panel / Side, each against its own design positions."""
    cfg = shrinkage_config(settings)
    method = method or default_method(settings)
    outlier_ppm = float(cfg.get("outlier_ppm", _DEFAULT_OUTLIER_PPM))
    outlier_um = float(cfg.get("outlier_um", _DEFAULT_OUTLIER_UM))
    usl_ppm = cfg.get("usl_ppm")
    max_plausible_ppm = cfg.get("max_plausible_ppm", _DEFAULT_MAX_PLAUSIBLE_PPM)

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
        build_up = labels.get("Build Up", "Unknown")
        design, note = resolve_design(settings, build_up, process)
        columns = measured_columns(settings, process)
        point = measured_point(settings, process)

        if design is None:
            result = _empty(method, [note or (
                f"No design positions configured for {build_up} / {process} "
                f"(REGISTRATION_SHRINKAGE.DESIGNS in settings.yaml); shrinkage not calculated.")])
            note = None
        else:
            result = compute_shrinkage(
                frame, design, method=method, location_col=columns[0], x_col=columns[1],
                y_col=columns[2], outlier_ppm=outlier_ppm, usl_ppm=usl_ppm,
                outlier_um=outlier_um, max_plausible_ppm=max_plausible_ppm)
        out.append(GroupShrinkage(labels, process, point, design, result, frame, columns, note))
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
