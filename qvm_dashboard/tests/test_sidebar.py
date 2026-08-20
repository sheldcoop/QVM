"""Tests for the sidebar's override mapping — the labels users pick from and
the values those labels resolve to."""

from ui.sidebar import _PROCESS_CHOICES, _SIDE_CHOICES


def test_auto_is_the_first_choice_and_means_no_override():
    """Streamlit selects the first entry by default, so "Auto" must lead and
    resolve to None — that is what leaves the parsed value in charge."""
    for choices in (_PROCESS_CHOICES, _SIDE_CHOICES):
        first_label = next(iter(choices))
        assert first_label.startswith('Auto')
        assert choices[first_label] is None


def test_process_labels_map_to_the_process_names_the_parser_emits():
    assert _PROCESS_CHOICES['Pad to Via (PTV)'] == 'Pad to Via'
    assert _PROCESS_CHOICES['Via to Pad (VTP)'] == 'Via to Pad'


def test_side_labels_map_to_single_letter_codes():
    assert _SIDE_CHOICES['Front (F)'] == 'F'
    assert _SIDE_CHOICES['Back (B)'] == 'B'
