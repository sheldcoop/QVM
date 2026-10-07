"""Smoke tests: every view renders without exception on realistic data.

QVM views take dataframes (not session state), so each test builds its input
through the real parsers/fixtures and renders inside AppTest. Markers assert
the right page came up — not pixel-perfect content.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

# Resolved here, not inside the AppTest functions: __file__ in those points
# at the harness's temp script, not this file.
_SAMPLE = Path(__file__).resolve().parents[1] / "sample_data"
_FRONT_TEXT = (_SAMPLE / "C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt").read_text()
_BACK_TEXT = (_SAMPLE / "C4F_Core_Shrinkage_Panel 28_Back_CAMorder.txt").read_text()


def _qvm_screen(view_name):
    import pandas as pd

    from src.utils import load_settings

    settings = load_settings()
    import numpy as np

    rng = np.random.default_rng(42)
    grid = list(range(11, 15)) + list(range(21, 25)) + list(range(31, 35)) + list(range(41, 45))
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
    df["PtV Distance"] = np.sqrt(df["Shift (DX)"] ** 2 + df["Shift (DY)"] ** 2)
    if view_name == "scatter":
        from src.views.registration_scatter import RegistrationScatterView

        RegistrationScatterView(settings).render(df)
    else:
        from src.views.quality_control import QualityControlView

        QualityControlView(settings).render(
            df, is_via_to_pad=True, meta={}, export_df=df
        )


def _cs_screen(sub_view, front_text, back_text):
    import pandas as pd

    from src.core_shrinkage_parser import parse_core_shrinkage_content
    from src.utils import load_settings
    from src.views.core_shrinkage import CoreShrinkageView

    settings = load_settings()
    front = parse_core_shrinkage_content(front_text, "Front")
    back = parse_core_shrinkage_content(back_text, "Back")
    df = pd.concat([front, back], ignore_index=True)
    CoreShrinkageView(settings).render(df, sub_view=sub_view, meta={})


def _cs_empty_screen():
    import pandas as pd

    from src.utils import load_settings
    from src.views.core_shrinkage import CoreShrinkageView

    CoreShrinkageView(load_settings()).render(
        pd.DataFrame({"layer": []}), sub_view="Quality Control", meta={}
    )


def test_scatter_view_renders():
    app = AppTest.from_function(
        _qvm_screen, kwargs={"view_name": "scatter"}, default_timeout=120
    ).run()
    assert not app.exception
    assert app.subheader[0].value == "Registration Scatter — Via-to-Pad"


def test_qc_view_renders():
    app = AppTest.from_function(
        _qvm_screen, kwargs={"view_name": "qc"}, default_timeout=180
    ).run()
    assert not app.exception
    assert any("Statistical Summary" in s.value for s in app.subheader)


@pytest.mark.parametrize(
    "sub_view", ["Quality Control", "Analytics", "Distortion Map", "Method"]
)
def test_cs_view_renders_all_sub_views(sub_view):
    app = AppTest.from_function(
        _cs_screen,
        kwargs={
            "sub_view": sub_view,
            "front_text": _FRONT_TEXT,
            "back_text": _BACK_TEXT,
        },
        default_timeout=180,
    ).run()
    assert not app.exception


def test_cs_view_empty_data_guard():
    app = AppTest.from_function(_cs_empty_screen, default_timeout=60).run()
    assert not app.exception
    assert any("No data available" in w.value for w in app.warning)
