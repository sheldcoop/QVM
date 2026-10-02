"""The Documentation tab: renders, and its worked example is the app's own result."""

import pytest

pytest.importorskip('streamlit.testing.v1')
from streamlit.testing.v1 import AppTest  # noqa: E402


def _page(x_mm=None):
    from src.registration_shrinkage import with_design_lengths
    from src.utils import load_settings
    from src.views.documentation import render_documentation

    settings = load_settings()
    if x_mm is not None:
        settings = with_design_lengths(settings, x_mm, 100.0)
    render_documentation(settings)


def _text(app) -> str:
    return '\n'.join(block.value for block in app.markdown)


def test_documentation_explains_every_number_with_the_live_example():
    app = AppTest.from_function(_page, default_timeout=120).run()
    assert not app.exception
    assert app.subheader[0].value.startswith('📖 Documentation')
    text = _text(app)
    for heading in ('What shrinkage means', 'The four points and the four lengths',
                    'From a length to µm and ppm', 'Worked example', 'The panel numbers',
                    'How the app knows which point is which', 'When no shrinkage is shown',
                    'The Excel file', 'What this method does not see', 'Core Shrinkage'):
        assert heading in text
    # Example: quadrants of -90, -110, -120, -80 ppm in X give a panel of -100 and a range of 40.
    assert '**-100.0 ppm**' in text and '**40.0 ppm**' in text
    assert '232.5' in text and '193.9' in text  # the design size in use


def test_documentation_follows_the_design_size_of_the_sidebar():
    app = AppTest.from_function(_page, kwargs={'x_mm': 150.0}, default_timeout=120).run()
    assert not app.exception
    text = _text(app)
    assert '**150 mm**' in text and '**100 mm**' in text
    assert '**-100.0 ppm**' in text  # ppm of the example does not depend on the size


def test_documentation_without_a_design_size_says_what_to_do():
    app = AppTest.from_function(_page, kwargs={'x_mm': 0.0}, default_timeout=120).run()
    assert not app.exception
    assert 'Shrinkage design size' in app.warning[0].value
