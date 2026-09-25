"""Distance-only PTV/VTP shrinkage calculations.

Rules:
- Use only point-to-point distances between matching fiducials.
- Do not perform coordinate transforms/alignment/rotation/translation.
- Never compare absolute measured vs nominal coordinates directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd


_QUADRANTS = ("UL", "LL", "LR", "UR")
_CORNER_MAP = {
    # Existing panel mapping used throughout app/tests.
    "TL": "1",
    "TR": "4",
    "BL": "2",
    "BR": "3",
}


@dataclass
class ShrinkageResult:
    quadrant: pd.DataFrame
    full_panel: pd.DataFrame
    uniformity: pd.DataFrame
    outliers: pd.DataFrame
    warnings: List[str]


def _loc(quad: str, corner: str) -> str:
    return f"{quad}_{_CORNER_MAP[corner]}"


def _build_loc_map(df: pd.DataFrame, location_col: str, x_col: str, y_col: str) -> Dict[str, Dict[str, float]]:
    loc_df = df[[location_col, x_col, y_col]].dropna(subset=[location_col, x_col, y_col]).copy()
    loc_df[location_col] = loc_df[location_col].astype(str).str.upper().str.strip()
    # Keep first occurrence to remain stable when duplicate rows are present.
    loc_df = loc_df.drop_duplicates(subset=[location_col], keep="first")
    return {
        r[location_col]: {"x": float(r[x_col]), "y": float(r[y_col])}
        for _, r in loc_df.iterrows()
    }


def _lengths_for_quad(loc_map: Dict[str, Dict[str, float]], quad: str) -> Dict[str, float] | None:
    needed = [_loc(quad, c) for c in ("TL", "TR", "BL", "BR")]
    if not all(k in loc_map for k in needed):
        return None

    tl, tr, bl, br = (loc_map[_loc(quad, c)] for c in ("TL", "TR", "BL", "BR"))
    x_top = abs(tr["x"] - tl["x"])
    x_bot = abs(br["x"] - bl["x"])
    y_left = abs(tl["y"] - bl["y"])
    y_right = abs(tr["y"] - br["y"])
    return {
        "x_len": (x_top + x_bot) / 2.0,
        "y_len": (y_left + y_right) / 2.0,
    }


def compute_distance_shrinkage(
    measured_df: pd.DataFrame,
    nominal_coords: Dict[str, Dict[str, float]],
    location_col: str = "Location",
    x_col: str = "Coord. X",
    y_col: str = "Coord. Y",
    outlier_ppm: float = 50.0,
) -> ShrinkageResult:
    warnings: List[str] = []
    if measured_df.empty:
        return ShrinkageResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), ["No measured rows in scope."])

    measured_map = _build_loc_map(measured_df, location_col, x_col, y_col)
    nominal_df = pd.DataFrame(
        [{"location": k, "x": v.get("x"), "y": v.get("y")} for k, v in (nominal_coords or {}).items()]
    )
    nominal_map = _build_loc_map(nominal_df, "location", "x", "y")

    q_rows = []
    for quad in _QUADRANTS:
        n = _lengths_for_quad(nominal_map, quad)
        m = _lengths_for_quad(measured_map, quad)
        if n is None or m is None:
            warnings.append(f"Missing required corner point(s) for quadrant {quad}; skipped.")
            continue
        if n["x_len"] == 0.0 or n["y_len"] == 0.0:
            warnings.append(f"Quadrant {quad} has zero nominal pitch; skipped.")
            continue

        delta_x_mm = m["x_len"] - n["x_len"]
        delta_y_mm = m["y_len"] - n["y_len"]
        qx_ppm = (delta_x_mm / n["x_len"]) * 1_000_000.0
        qy_ppm = (delta_y_mm / n["y_len"]) * 1_000_000.0
        qx_pct = (delta_x_mm / n["x_len"]) * 100.0
        qy_pct = (delta_y_mm / n["y_len"]) * 100.0
        q_rows.append({
            "Quadrant": quad,
            "X Nominal (mm)": n["x_len"],
            "X Measured (mm)": m["x_len"],
            "Delta X (um)": delta_x_mm * 1000.0,
            "QP Shrinkage X (%)": qx_pct,
            "QP Shrinkage X (PPM)": qx_ppm,
            "Y Nominal (mm)": n["y_len"],
            "Y Measured (mm)": m["y_len"],
            "Delta Y (um)": delta_y_mm * 1000.0,
            "QP Shrinkage Y (%)": qy_pct,
            "QP Shrinkage Y (PPM)": qy_ppm,
        })

    if not q_rows:
        return ShrinkageResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), warnings or ["No shrinkage rows could be computed."])

    qdf = pd.DataFrame(q_rows)
    fp_x_ppm = float(qdf["QP Shrinkage X (PPM)"].mean())
    fp_y_ppm = float(qdf["QP Shrinkage Y (PPM)"].mean())
    fp_x_pct = float(qdf["QP Shrinkage X (%)"].mean())
    fp_y_pct = float(qdf["QP Shrinkage Y (%)"].mean())
    qtq_x_ppm = float(qdf["QP Shrinkage X (PPM)"].max() - qdf["QP Shrinkage X (PPM)"].min())
    qtq_y_ppm = float(qdf["QP Shrinkage Y (PPM)"].max() - qdf["QP Shrinkage Y (PPM)"].min())
    qtq_x_pct = float(qdf["QP Shrinkage X (%)"].max() - qdf["QP Shrinkage X (%)"].min())
    qtq_y_pct = float(qdf["QP Shrinkage Y (%)"].max() - qdf["QP Shrinkage Y (%)"].min())

    full_panel = pd.DataFrame([{
        "Shrinkage X (FP %)": fp_x_pct,
        "Shrinkage Y (FP %)": fp_y_pct,
        "Shrinkage X (FP PPM)": fp_x_ppm,
        "Shrinkage Y (FP PPM)": fp_y_ppm,
        "Shrinkage X-Y Offset (%)": fp_x_pct - fp_y_pct,
        "Shrinkage X-Y Offset (PPM)": fp_x_ppm - fp_y_ppm,
        # Backward-compatible aliases used in early tests and initial UI.
        "Shrinkage X (FP)": fp_x_ppm,
        "Shrinkage Y (FP)": fp_y_ppm,
        "Shrinkage X-Y Offset": fp_x_ppm - fp_y_ppm,
    }])
    uniformity = pd.DataFrame([{
        "QTQ Range X (%)": qtq_x_pct,
        "QTQ Range Y (%)": qtq_y_pct,
        "QTQ Range X": qtq_x_ppm,
        "QTQ Range Y": qtq_y_ppm,
        "Total 2D Spatial Distortion Vector": (qtq_x_ppm ** 2 + qtq_y_ppm ** 2) ** 0.5,
    }])

    odf = qdf.copy()
    odf["X Deviation from FP (PPM)"] = (odf["QP Shrinkage X (PPM)"] - fp_x_ppm).abs()
    odf["Y Deviation from FP (PPM)"] = (odf["QP Shrinkage Y (PPM)"] - fp_y_ppm).abs()
    odf["X Deviation from FP (%)"] = (odf["QP Shrinkage X (%)"] - fp_x_pct).abs()
    odf["Y Deviation from FP (%)"] = (odf["QP Shrinkage Y (%)"] - fp_y_pct).abs()
    odf = odf[(odf["X Deviation from FP (PPM)"] > outlier_ppm) | (odf["Y Deviation from FP (PPM)"] > outlier_ppm)].copy()

    if odf.empty:
        outliers = pd.DataFrame(columns=[
            "Quadrant",
            "X Deviation from FP (%)",
            "Y Deviation from FP (%)",
            "X Deviation from FP (PPM)",
            "Y Deviation from FP (PPM)",
            "Alert",
        ])
    else:
        odf["Alert"] = f"Deviation > {outlier_ppm:.0f} PPM from FP"
        outliers = odf[[
            "Quadrant",
            "X Deviation from FP (%)",
            "Y Deviation from FP (%)",
            "X Deviation from FP (PPM)",
            "Y Deviation from FP (PPM)",
            "Alert",
        ]]

    qdf = qdf.round(3)
    full_panel = full_panel.round(3)
    uniformity = uniformity.round(3)
    outliers = outliers.round(3)
    return ShrinkageResult(qdf, full_panel, uniformity, outliers, warnings)


def compute_distance_shrinkage_by_group(
    measured_df: pd.DataFrame,
    nominal_coords: Dict[str, Dict[str, float]],
    location_col: str = "Location",
    x_col: str = "Coord. X",
    y_col: str = "Coord. Y",
    outlier_ppm: float = 50.0,
    group_cols: List[str] | None = None,
) -> List[dict]:
    group_cols = group_cols or []
    valid_group_cols = [c for c in group_cols if c in measured_df.columns]
    if not valid_group_cols:
        res = compute_distance_shrinkage(
            measured_df,
            nominal_coords,
            location_col=location_col,
            x_col=x_col,
            y_col=y_col,
            outlier_ppm=outlier_ppm,
        )
        return [{"group": {}, "result": res}]

    outputs: List[dict] = []
    for keys, gdf in measured_df.groupby(valid_group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        gdict = {k: ("Unknown" if pd.isna(v) or str(v).strip() == "" else str(v)) for k, v in zip(valid_group_cols, keys)}
        res = compute_distance_shrinkage(
            gdf,
            nominal_coords,
            location_col=location_col,
            x_col=x_col,
            y_col=y_col,
            outlier_ppm=outlier_ppm,
        )
        outputs.append({"group": gdict, "result": res})
    return outputs