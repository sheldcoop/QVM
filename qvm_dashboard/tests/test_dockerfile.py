"""Container chart-rendering guard (Finding 4).

Excel chart embedding renders through kaleido, which needs a Chromium
binary in the image. Without one, every ProKube export silently degrades
to placeholder graphics. This pins the Dockerfile contract.
"""

import re
from pathlib import Path


def _dockerfile_text():
    root = Path(__file__).resolve().parent.parent.parent
    return (root / "Dockerfile").read_text()


def test_dockerfile_installs_a_chromium_binary():
    """The apt install must include a browser kaleido can discover on PATH
    (choreographer looks for chromium/chromium-browser)."""
    text = _dockerfile_text()
    assert "chromium" in text, "Dockerfile installs no browser for kaleido"


def test_dockerfile_documents_chart_dependency():
    text = _dockerfile_text()
    assert "kaleido" in text.lower() or "chromium" in text.lower()


"""Container privilege guard (Finding 9).

Restricted pod-security policies (runAsNonRoot) refuse root containers, and
a Streamlit/file-write flaw must not yield root. This pins the Dockerfile
contract: a non-root user owns /app, has a writable HOME for first-run
caches, and is switched to after the privileged install steps.
"""


def test_container_switches_to_a_non_root_user():
    text = _dockerfile_text()
    m = re.search(r"^USER\s+(\S+)\s*$", text, re.MULTILINE)
    assert m, "Dockerfile has no USER directive; container runs as root"
    assert m.group(1) != "root", "Dockerfile USER is root"


def test_non_root_user_is_created_with_home_and_owns_app():
    text = _dockerfile_text()
    assert "useradd" in text, "Dockerfile creates no non-root user"
    assert "HOME=" in text, "Dockerfile sets no HOME for the runtime user"
    assert "chown" in text and "/app" in text, (
        "Dockerfile does not hand /app to the runtime user"
    )


def test_user_switch_happens_after_privileged_installs():
    text = _dockerfile_text()
    m = re.search(r"^USER\s+\S+\s*$", text, re.MULTILINE)
    assert m, "Dockerfile has no USER directive; container runs as root"
    assert text.index("pip install") < m.start(), (
        "USER switch must come after dependency installation"
    )
    assert text.index("useradd") < m.start(), (
        "runtime user must be created before the USER switch"
    )
