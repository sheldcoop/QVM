"""Phantom-config guard (Finding 11).

The registration views/export once looked up a `REGISTRATION_SHRINKAGE`
settings section that never existed in settings.yaml, so an operator
configuring that documented-looking key got silently ignored values.
The lookups now read the canonical `CORE_SHRINKAGE` key that actually
supplies the values. This pins the removal.
"""
from pathlib import Path


def _package_text():
    root = Path(__file__).resolve().parent.parent
    chunks = [(root / 'app.py').read_text()]
    for path in sorted((root / 'src').rglob('*.py')):
        chunks.append(path.read_text())
    return '\n'.join(chunks)


def test_no_phantom_registration_shrinkage_lookup():
    text = _package_text()
    assert 'REGISTRATION_SHRINKAGE' not in text, \
        'phantom settings key is referenced but never defined in settings.yaml'
