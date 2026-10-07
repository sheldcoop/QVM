"""The Shrinkage sub-view: overview, details per group, explanation, export."""

import pytest

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402


def _screen(build_up: str = "BU-01", scale: float = 0.9999, kind: str = "good"):
    import pandas as pd

    from src.registration_shrinkage import design_for
    from src.utils import load_settings
    from src.views.registration_shrinkage import render_registration_shrinkage

    settings = load_settings()
    design = design_for(settings, "BU-01", "Via to Pad")
    rows = []
    sides = (
        [("F", kind)] if kind == "good" else [("F", "local"), ("B", "other product")]
    )
    for side, case in sides:
        for index, (name, xy) in enumerate(design.items()):
            if case == "local":
                x, y = index * 1e-4, -index * 1e-4
            elif case == "other product":
                x, y = xy["x"] * 0.992, xy["y"]
            else:
                x, y = xy["x"] * scale + 301.4, xy["y"] * scale
            rows.append(
                {
                    "Location": name,
                    "Coord. X": x,
                    "Coord. Y": y,
                    "Build Up": build_up,
                    "Panel": "25",
                    "Side": side,
                    "Process": "Via to Pad",
                }
            )
    render_registration_shrinkage(pd.DataFrame(rows), settings, key="vtp", meta={})


def _run(**kwargs):
    return AppTest.from_function(_screen, kwargs=kwargs, default_timeout=120).run()


def _tables(app):
    """The copper tables of the page, each as (header cells, list of row cell lists)."""
    import re

    out = []
    for block in app.markdown:
        if 'class="qvm-table"' not in block.value:
            continue
        head = re.findall(r"<th>(.*?)</th>", block.value)
        rows = [
            re.findall(r"<td>(.*?)</td>", row)
            for row in re.findall(r"<tr>(.*?)</tr>", block.value.split("<tbody>")[1])
        ]
        out.append((head, rows))
    return out


def test_overview_then_company_result_in_um_with_ppm():
    app = _run()
    assert not app.exception
    assert app.subheader[0].value == "📊 Shrinkage Summary"

    head, rows = _tables(app)[0]
    assert head[:5] == ["Build Up", "Panel", "Side", "Result", "Panel X (um)"]
    assert rows[0][:6] == ["BU-01", "25", "F", "Reported", "-23.2", "-100.0"]
    assert len(app.dataframe) == 0  # every table carries the copper header

    assert len(app.radio) == 0  # one method only: the company calculation
    shown = {metric.label: (metric.value, metric.delta) for metric in app.metric}
    assert shown["Panel X"] == ("-23.2 µm", "-100.0 ppm")
    assert shown["Panel Y"] == ("-19.4 µm", "-100.0 ppm")
    assert "Limit" not in shown  # no limit configured
    # Copper summary tiles on top; one panel in scope, so they are not repeated below.
    assert shown["Alerts"] == ("0", "✓ Uniform")
    assert "Quadrant range X / Y" in shown
    assert [m.label for m in app.metric].count("Panel X") == 1
    assert _tables(app)[1][0][:5] == [
        "Quadrant",
        "Delta X (um)",
        "Shrinkage X (ppm)",
        "Delta Y (um)",
        "Shrinkage Y (ppm)",
    ]
    assert any("design quadrant 232.5 × 193.9 mm" in c.value for c in app.caption)
    assert "No quadrant is more than 50 ppm" in app.success[0].value
    assert any("The ten numbers" in block.value for block in app.markdown)
    assert not any(
        "Affine" in block.value or "Centre-based" in block.value
        for block in app.markdown
    )


def test_unknown_build_up_needs_no_note_the_design_size_is_the_same_for_all():
    app = _run(build_up="Unknown")
    assert not app.exception
    assert {m.label: m.delta for m in app.metric}["Panel X"] == "-100.0 ppm"
    assert len(app.warning) == 0


def test_file_text_cannot_inject_markup_into_the_tables():
    app = _run(build_up="<script>alert(1)</script>")
    assert not app.exception
    page = " ".join(block.value for block in app.markdown)
    assert "<script>" not in page and "&lt;script&gt;" in page


def test_unusable_measurements_get_an_explanation_instead_of_numbers():
    app = _run(kind="bad")
    assert not app.exception
    assert len(app.metric) == 0
    head, rows = _tables(app)[0]
    result, why = head.index("Result"), head.index("Why")
    assert [row[result] for row in rows] == ["No result", "No result"]
    assert "does not match the design" in rows[0][why]  # side B sorts first
    assert "lie within" in rows[1][why]
    warnings = [w.value for w in app.warning]
    assert any("does not match the design" in w for w in warnings)
    assert any("positions relative to each site" in w for w in warnings)
    assert _tables(app)[1][0][:4] == [
        "Quadrant",
        "X Measured (mm)",
        "X Design (mm)",
        "X Difference (ppm)",
    ]
    assert any("needs no design" in c.value for c in app.caption)


def test_full_width_helper_fits_the_installed_streamlit():
    import streamlit as st

    from src.views.base import full_width

    assert full_width(st.dataframe) == {"width": "stretch"}
    assert full_width(st.plotly_chart) in (
        {"width": "stretch"},
        {"use_container_width": True},
    )
    assert full_width(lambda figure, use_container_width=False: None) == {
        "use_container_width": True
    }
