"""Why two Build-Up normalizers exist — and why they must stay two.

``ingestion._normalize_build_up`` (Optional in/out) drives the upload
precedence chain, where missing means "fall through to the next tier".
``registration_shrinkage.normalize_build_up`` (str in/out) labels company
length tables, where every cell needs a printable string.

The semantics differ on purpose (None handling, bare numbers, zero
padding). Merging them changes behavior; these tests pin the split.
"""

from src.ingestion import _normalize_build_up as ingest_nbu
from src.registration_shrinkage import normalize_build_up as reg_nbu


def test_ingest_normalizer_missing_means_fall_through():
    assert ingest_nbu(None) is None
    assert ingest_nbu("") is None
    assert ingest_nbu("Unknown") is None
    assert ingest_nbu("  ") is None


def test_ingest_normalizer_bare_and_prefixed_numbers():
    assert ingest_nbu("2") == "BU-02"
    assert ingest_nbu("02") == "BU-02"
    assert ingest_nbu("BU02") == "BU-02"
    assert ingest_nbu("bu-2") == "BU-02"
    # zfill preserves width beyond two digits.
    assert ingest_nbu("007") == "BU-007"


def test_ingest_normalizer_keeps_custom_values():
    assert ingest_nbu("custom") == "custom"


def test_reg_normalizer_always_returns_printable_str():
    assert reg_nbu(" BU 3 ") == "BU-03"
    # int() collapses leading zeros — unlike the ingest variant.
    assert reg_nbu("BU007") == "BU-07"
    # Bare numbers are NOT recognized here — unlike the ingest variant.
    assert reg_nbu("007") == "007"
    # Nothing is ever missing here — unlike the ingest variant.
    assert reg_nbu(None) == "None"
    assert reg_nbu("Unknown") == "Unknown"
