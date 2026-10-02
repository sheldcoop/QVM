"""Container chart-rendering guard (Finding 4).

Excel chart embedding renders through kaleido, which needs a Chromium
binary in the image. Without one, every ProKube export silently degrades
to placeholder graphics. This pins the Dockerfile contract.
"""
from pathlib import Path


def _dockerfile_text():
    root = Path(__file__).resolve().parent.parent.parent
    return (root / 'Dockerfile').read_text()


def test_dockerfile_installs_a_chromium_binary():
    """The apt install must include a browser kaleido can discover on PATH
    (choreographer looks for chromium/chromium-browser)."""
    text = _dockerfile_text()
    assert 'chromium' in text, 'Dockerfile installs no browser for kaleido'


def test_dockerfile_documents_chart_dependency():
    text = _dockerfile_text()
    assert 'kaleido' in text.lower() or 'chromium' in text.lower()
