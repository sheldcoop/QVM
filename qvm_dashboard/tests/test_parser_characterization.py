"""Characterization tests for parser micro-helpers.

Pins the exact behavior of the value extractors and filename router so later
milestones can refactor around them. All expectations were read off the
implementation, not invented.
"""

import pytest

from src.parser import (
    QVMParseError,
    _checked_value,
    _parse_value,
    _value_after_equals,
    parse_filename,
)


def test_parse_value_happy_path():
    assert _parse_value("Coord. X =        63.857203") == pytest.approx(63.857203)


def test_parse_value_missing_equals_raises():
    with pytest.raises(QVMParseError, match="missing '='"):
        _parse_value("Coord. X 63.857203")


def test_parse_value_bad_number_raises():
    with pytest.raises(QVMParseError, match="Could not parse number"):
        _parse_value("SC =   not-a-number")


def test_value_after_equals_happy_path():
    assert _value_after_equals("DX = 0.000592") == pytest.approx(0.000592)


def test_value_after_equals_missing_returns_none():
    assert _value_after_equals("DX") is None
    assert _value_after_equals("DX = abc") is None


def test_checked_value_records_non_finite_as_missing():
    site = {}
    assert _checked_value(site, "SC", "SC = nan") is None
    assert site["_dq_notes"] == ["SC value nan is not finite; treated as missing."]
    assert _checked_value({}, "DX", "DX = inf") is None


def test_checked_value_passes_finite_through():
    assert _checked_value({}, "SC", "SC = 0.003728") == pytest.approx(0.003728)


def test_parse_filename_full():
    r = parse_filename("Panel_28_BU_01_F_VtP.txt")
    assert r == {
        "format_hint": "Via to Pad",
        "Panel Number": "28",
        "Side": "F",
        "Build Up": "BU-01",
    }


def test_parse_filename_pad_to_via_back():
    r = parse_filename("C4F_PtV_Panel 28_Back_CAMorder.txt")
    assert r["format_hint"] == "Pad to Via"
    assert r["Panel Number"] == "28"
    assert r["Side"] == "B"


def test_parse_filename_unknowns_when_nothing_matches():
    r = parse_filename("random_export.txt")
    assert r == {
        "format_hint": None,
        "Panel Number": "Unknown",
        "Side": "Unknown",
        "Build Up": "Unknown",
    }


def test_parse_filename_conflicting_hints_give_none():
    # Both markers present: no trustworthy hint.
    r = parse_filename("vtp_ptv_panel1_f.txt")
    assert r["format_hint"] is None


def test_parse_filename_long_side_words():
    assert parse_filename("panel2_front.txt")["Side"] == "F"
    assert parse_filename("panel2_back.txt")["Side"] == "B"
