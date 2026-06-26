"""Regression + unit suite for the Database Analysis feature.

Covers the pure computational core and the shared data layer (no Streamlit
rendering):

  - src/dbanalysis/summary.py   — summary tables, Pp/Ppk (incl. one-sided)
  - src/dbanalysis/visuals.py   — box plot, control chart, SPC constants
  - src/dbanalysis/columns.py   — column/limit resolution
  - src/dbanalysis/loader.py    — sheet-name matching
  - src/dbanalysis/config.py    — analysis configuration
  - import-smoke for the engine / download center

Run from the qvm_dashboard/ directory:

    PYTHONPATH=. pytest tests/test_dbanalysis.py -v
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

from src.dbanalysis.summary import (
    generate_summary_table,
    generate_lot_summary_table,
    generate_detailed_summary_table,
)
from src.dbanalysis.visuals import (
    plot_roughness_box, plot_control_chart, c4, a3, b3, b4,
)
from src.dbanalysis import columns as cols
from src.dbanalysis.columns import group_limits
from src.dbanalysis.loader import find_sheet


# --------------------------------------------------------------------------- #
#  Fixtures / helpers
# --------------------------------------------------------------------------- #

def _make_df() -> pd.DataFrame:
    return pd.DataFrame({
        "Process": ["A", "A", "A", "A", "B", "B", "B", "B"],
        "Lot":     ["L1", "L1", "L2", "L2", "L1", "L1", "L2", "L2"],
        "Panel":   ["P1", "P2", "P1", "P2", "P1", "P2", "P1", "P2"],
        "Roughness": [1.0, 2.0, 3.0, 4.0, 10.0, 20.0, 30.0, 40.0],
    })


METRIC = {"name": "Roughness", "col": "Roughness"}
METRIC_BOTH = {"name": "Roughness", "col": "Roughness", "limits": {"LSL": 0.0, "USL": 10.0}}


# --------------------------------------------------------------------------- #
#  summary.generate_summary_table
# --------------------------------------------------------------------------- #

def test_summary_basic_stats_per_process():
    df = _make_df()
    out = generate_summary_table(df, process_col="Process", metrics=[METRIC])

    assert list(out["Process"]) == ["A", "B"]
    row_a = out[out["Process"] == "A"].iloc[0]
    assert row_a["N"] == 4
    assert row_a["Mean"] == pytest.approx(2.5)
    assert row_a["Min"] == pytest.approx(1.0)
    assert row_a["Max"] == pytest.approx(4.0)
    expected_std = round(df[df["Process"] == "A"]["Roughness"].std(), 3)
    assert row_a["Std Dev"] == pytest.approx(expected_std)
    # no limits -> Pp/Ppk N/A
    assert row_a["Pp"] == "N/A"
    assert row_a["Ppk"] == "N/A"


def test_summary_pp_ppk_hand_computed_two_sided():
    """values [2,4,6,8] -> mean 5, std sqrt(20/3)=2.58199; LSL 0 USL 10.

    Pp  = 10/(6*std) = 0.6455 -> "0.65"; Ppk = min(...)=0.6455 -> "0.65".
    """
    df = pd.DataFrame({"Process": ["A"] * 4, "Roughness": [2.0, 4.0, 6.0, 8.0]})
    out = generate_summary_table(df, process_col="Process", metrics=[METRIC_BOTH])
    row = out.iloc[0]
    assert row["Mean"] == pytest.approx(5.0)
    assert row["Pp"] == "0.65"
    assert row["Ppk"] == "0.65"


def test_summary_ppk_one_sided_usl_only():
    df = pd.DataFrame({"Process": ["A"] * 4, "Roughness": [2.0, 4.0, 6.0, 8.0]})
    metric = {"name": "R", "col": "Roughness", "limits": {"USL": 10.0}}
    row = generate_summary_table(df, "Process", [metric]).iloc[0]
    assert row["Pp"] == "N/A"           # Pp undefined with one limit
    assert row["Ppk"] == "0.65"         # (10-5)/(3*2.582)


def test_summary_ppk_one_sided_lsl_only():
    df = pd.DataFrame({"Process": ["A"] * 4, "Roughness": [2.0, 4.0, 6.0, 8.0]})
    metric = {"name": "R", "col": "Roughness", "limits": {"LSL": 0.0}}
    row = generate_summary_table(df, "Process", [metric]).iloc[0]
    assert row["Pp"] == "N/A"
    assert row["Ppk"] == "0.65"         # (5-0)/(3*2.582)


def test_summary_pp_na_when_std_zero():
    df = pd.DataFrame({"Process": ["A"] * 4, "Roughness": [5.0, 5.0, 5.0, 5.0]})
    row = generate_summary_table(df, "Process", [METRIC_BOTH]).iloc[0]
    assert row["Std Dev"] == pytest.approx(0.0)
    assert row["Pp"] == "N/A"
    assert row["Ppk"] == "N/A"


def test_summary_coerces_and_drops_non_numeric():
    df = pd.DataFrame({"Process": ["A"] * 4, "Roughness": ["1.0", "bad", "3.0", None]})
    row = generate_summary_table(df, "Process", [METRIC]).iloc[0]
    assert row["N"] == 2
    assert row["Mean"] == pytest.approx(2.0)


def test_summary_no_rows_returns_empty():
    empty = pd.DataFrame({"Process": [], "Roughness": []})
    out = generate_summary_table(empty, "Process", [METRIC])
    assert isinstance(out, pd.DataFrame) and out.empty


def test_summary_missing_metric_column_skipped():
    out = generate_summary_table(_make_df(), "Process",
                                 [{"name": "Ghost", "col": "DoesNotExist"}])
    assert out.empty


def test_group_limits_single_mixed_none():
    one = pd.DataFrame({"Line": [1, 2], "Line_LSL": [35, 35], "Line_USL": [65, 65]})
    lim, mixed = group_limits(one, "line")
    assert mixed is False and lim == {"LSL": 35, "USL": 65}

    mix = pd.DataFrame({"Line": [1, 2], "Line_LSL": [45, 65], "Line_USL": [55, 75]})
    lim, mixed = group_limits(mix, "line")
    assert mixed is True and lim == {}

    none = pd.DataFrame({"Line": [1, 2]})
    lim, mixed = group_limits(none, "line")
    assert mixed is False and lim == {}


def test_summary_uses_each_groups_own_limits():
    # Process A spec 35/65; Process B spec 10/90 — each must use its own.
    df = pd.DataFrame({
        "Process": ["A", "A", "B", "B"],
        "Line": [48.0, 52.0, 48.0, 52.0],
        "Line_LSL": [35, 35, 10, 10],
        "Line_USL": [65, 65, 90, 90],
    })
    metric = {"name": "Line", "col": "Line", "limit_prefix": "line"}
    out = generate_summary_table(df, "Process", [metric])
    ppk_a = out[out["Process"] == "A"].iloc[0]["Ppk"]
    ppk_b = out[out["Process"] == "B"].iloc[0]["Ppk"]
    # tighter spec (A) -> lower Ppk than wider spec (B); B not scored on A's 35/65.
    assert float(ppk_a) < float(ppk_b)


def test_summary_mixed_spec_guard():
    df = pd.DataFrame({
        "Process": ["FET", "FET", "FET", "FET"],
        "Line": [48.0, 52.0, 68.0, 72.0],
        "Line_LSL": [45, 45, 65, 65],   # two distinct specs in one group
        "Line_USL": [55, 55, 75, 75],
    })
    metric = {"name": "Line", "col": "Line", "limit_prefix": "line"}
    row = generate_summary_table(df, "Process", [metric]).iloc[0]
    assert row["Ppk"] == "N/A (mixed spec)"
    assert row["Pp"] == "N/A"
    # descriptive stats still present
    assert row["N"] == 4


def test_lot_summary_grouping():
    out = generate_lot_summary_table(_make_df(), "Process", "Lot", [METRIC])
    assert {"Lot Number", "Process", "Metric", "N"}.issubset(out.columns)
    assert len(out) == 4
    assert set(out["N"]) == {2}


def test_detailed_summary_grouping():
    out = generate_detailed_summary_table(_make_df(), "Process", "Lot", "Panel", [METRIC])
    assert {"Lot Number", "Panel", "Process"}.issubset(out.columns)
    assert len(out) == 8
    assert set(out["N"]) == {1}


# --------------------------------------------------------------------------- #
#  SPC unbiasing constants (hand-verified against standard tables)
# --------------------------------------------------------------------------- #

def test_spc_constants_match_tables():
    assert c4(2) == pytest.approx(0.7979, abs=1e-3)
    assert c4(5) == pytest.approx(0.9400, abs=1e-3)
    assert c4(10) == pytest.approx(0.9727, abs=1e-3)
    assert a3(5) == pytest.approx(1.427, abs=1e-2)
    assert b3(5) == pytest.approx(0.0, abs=1e-6)
    assert b4(5) == pytest.approx(2.089, abs=1e-2)
    assert b3(10) == pytest.approx(0.284, abs=1e-2)
    assert b4(10) == pytest.approx(1.716, abs=1e-2)


def test_spc_constants_nan_for_singleton():
    assert np.isnan(c4(1))
    assert np.isnan(a3(1))


# --------------------------------------------------------------------------- #
#  visuals.plot_roughness_box
# --------------------------------------------------------------------------- #

def test_box_returns_figure_with_traces():
    fig = plot_roughness_box(_make_df(), "Roughness", "Lot", "Test - Roughness")
    assert isinstance(fig, go.Figure) and len(fig.data) > 0


def test_box_empty_data_returns_no_data_figure():
    df = pd.DataFrame({"Roughness": [np.nan, np.nan], "Lot": ["L1", "L1"]})
    fig = plot_roughness_box(df, "Roughness", "Lot", "Empty")
    assert "No data" in fig.layout.title.text


def test_box_with_limits_adds_spec_lines():
    fig = plot_roughness_box(_make_df(), "Roughness", "Lot", "Test",
                             limits={"LSL": 0.0, "USL": 10.0, "Target": 5.0})
    assert len(fig.layout.shapes) > 0


# --------------------------------------------------------------------------- #
#  visuals.plot_control_chart  (panel subgroups + variable limits)
# --------------------------------------------------------------------------- #

def _panel_df(n_lots: int, n_panels: int = 4, n_per: int = 5) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    for lot in range(n_lots):
        for panel in range(n_panels):
            for _ in range(n_per):
                rows.append({"Lot": f"L{lot:02d}", "Panel": f"P{panel}",
                             "Roughness": float(rng.normal(5, 1))})
    return pd.DataFrame(rows)


def test_control_chart_panel_subgroups_returns_figure():
    fig = plot_control_chart(_panel_df(3), "Roughness", "Lot", "Panel", "Test")
    assert isinstance(fig, go.Figure) and len(fig.data) > 0


def test_control_chart_lot_only_subgroups():
    # No panel column -> subgroup by lot; needs lots with >1 measurement.
    df = _panel_df(4, n_panels=1, n_per=6)
    fig = plot_control_chart(df, "Roughness", "Lot", None, "Test")
    assert isinstance(fig, go.Figure) and len(fig.data) > 0


def test_control_chart_empty_data():
    df = pd.DataFrame({"Roughness": [np.nan], "Lot": ["L1"], "Panel": ["P1"]})
    fig = plot_control_chart(df, "Roughness", "Lot", "Panel", "Empty")
    assert "No data" in fig.layout.title.text


def test_control_chart_gates_when_too_few_subgroups():
    df = pd.DataFrame({"Lot": ["L1"] * 5, "Panel": ["P1"] * 5,
                       "Roughness": [1.0, 2.0, 3.0, 4.0, 5.0]})
    fig = plot_control_chart(df, "Roughness", "Lot", "Panel", "Test")
    assert "not enough subgroups" in fig.layout.title.text
    assert len(fig.data) == 0


def test_control_chart_draws_lot_bands_for_panel_subgroups():
    """Panel subgroups get faint per-lot background bands + lot labels."""
    fig = plot_control_chart(_panel_df(3), "Roughness", "Lot", "Panel", "Test")
    rects = [s for s in fig.layout.shapes if s.type == 'rect']
    assert len(rects) == 6  # 3 lots x 2 chart rows
    labels = [a.text for a in fig.layout.annotations]
    assert {"L00", "L01", "L02"}.issubset(set(labels))


def test_control_chart_no_bands_for_lot_only_subgroups():
    fig = plot_control_chart(_panel_df(3, n_panels=1, n_per=6), "Roughness", "Lot", None, "Test")
    assert [s for s in fig.layout.shapes if s.type == 'rect'] == []


def test_control_chart_draws_no_spec_limits():
    """Spec limits live on the box plot, not the control chart.

    The chart's only horizontal lines are the control/center lines; none are
    annotated LSL/USL/Target.
    """
    fig = plot_control_chart(_panel_df(3), "Roughness", "Lot", "Panel", "Test")
    spec_labels = {"LSL", "USL", "Target"}
    annotations = [getattr(a, "text", "") for a in fig.layout.annotations]
    assert not (spec_labels & set(annotations))


# --------------------------------------------------------------------------- #
#  columns / loader / config
# --------------------------------------------------------------------------- #

def test_normalize_and_find_col():
    df = pd.DataFrame(columns=["Lot_Number", " RA Mean ", "Side"])
    assert cols.normalize_col("Lot_Number") == "lot number"
    assert cols.find_col(df, "lot number") == "Lot_Number"
    assert cols.find_col(df, "ra mean") == " RA Mean "
    assert cols.find_col(df, "missing") is None


def test_find_cols_preserves_order_and_dedupes():
    df = pd.DataFrame(columns=["Lot Number", "Side", "Unit"])
    assert cols.find_cols(df, ["unit", "lot number", "unit"]) == ["Unit", "Lot Number"]


def test_resolve_limits():
    df = pd.DataFrame({
        "Line": [1.0, 2.0],
        "Line LSL": [0.5, 0.5],
        "Line USL": [3.0, 3.0],
        "Line Target": [np.nan, np.nan],   # all-NaN -> omitted
    })
    limits = cols.resolve_limits(df, "line")
    assert limits == {"LSL": 0.5, "USL": 3.0}


def test_find_sheet_case_insensitive():
    names = ["Pad", "IMP_Trace", "Roughness"]
    assert find_sheet(names, "imp_trace") == "IMP_Trace"
    assert find_sheet(names, "ROUGHNESS") == "Roughness"
    assert find_sheet(names, "nope") is None


def test_config_covers_all_subviews():
    from src.dbanalysis.config import DB_ANALYSES
    assert set(DB_ANALYSES) == {
        "Roughness", "Impedance", "Top to Bottom Via", "Trace", "Pad", "Landing Pad",
    }
    rough = DB_ANALYSES["Roughness"]
    assert rough.sheet_name == "Roughness"
    assert any(m.display_unit == "nm" and m.display_scale == 1000.0 for m in rough.metrics)


# --------------------------------------------------------------------------- #
#  Import-smoke for the engine + download center
# --------------------------------------------------------------------------- #

def test_engine_and_download_center_import():
    from src.dbanalysis.engine import render_analysis
    from src.views.download_center import DownloadCenterView
    assert callable(render_analysis)
    assert isinstance(DownloadCenterView, type)
