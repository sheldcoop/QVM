"""Settings-key guard (Finding 11, updated).

The registration views and export once looked up a `REGISTRATION_SHRINKAGE`
settings section that did not exist in settings.yaml, so the lookups silently
fell back to the Core Shrinkage design positions. The section now exists and
holds the registration design positions. This pins the two halves of the fix:

* the section is read in exactly one place, so a lookup cannot go stale again;
* every key that place reads is defined in the shipped settings.yaml.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECTION = "REGISTRATION_SHRINKAGE"


def _sources():
    return [ROOT / "app.py", *sorted((ROOT / "src").rglob("*.py"))]


def test_registration_shrinkage_section_is_read_in_one_place():
    readers = [
        path.relative_to(ROOT).as_posix()
        for path in _sources()
        if f'"{SECTION}"' in path.read_text() or f"'{SECTION}'" in path.read_text()
    ]
    assert readers == ["src/registration_shrinkage.py"]


def test_every_key_the_code_reads_is_defined_in_settings(settings):
    section = settings[SECTION]
    source = (ROOT / "src" / "registration_shrinkage.py").read_text()
    source += (ROOT / "src" / "views" / "registration_shrinkage.py").read_text()
    source += (ROOT / "src" / "excel_export" / "qvm.py").read_text()
    read = set(
        re.findall(
            r'(?:cfg|shrinkage_config\(settings\))\.get\(\s*["\'](\w+)["\']', source
        )
    )
    assert read == {
        "design_quadrant_mm",
        "map_gap_mm",
        "measured_point",
        "outlier_ppm",
        "usl_ppm",
        "max_plausible_ppm",
    }
    assert read <= set(section), f"read but not defined: {sorted(read - set(section))}"
    assert set(section["design_quadrant_mm"]) == {"x", "y"}
    assert (
        "DESIGNS" not in section
    )  # the 16 design positions are gone: two lengths suffice


def test_registration_shrinkage_never_uses_the_core_design():
    for name in (
        "app.py",
        "src/registration_shrinkage.py",
        "src/views/registration_shrinkage.py",
        "src/views/quality_control.py",
        "src/excel_export/qvm.py",
    ):
        text = (ROOT / name).read_text()
        assert "CORE_SHRINKAGE" not in text, name
