"""Shared utilities for the QVM Database Analysis dashboard."""

import os
import yaml

_REQUIRED_SETTINGS_KEYS = ['UI_STRINGS', 'COLORS']


def _validate_settings(settings: dict) -> None:
    missing = [k for k in _REQUIRED_SETTINGS_KEYS if k not in settings]
    if missing:
        raise ValueError(f"settings.yaml is missing required sections: {missing}")


def load_settings() -> dict:
    """Load and return the project settings.yaml as a dict.

    Canonical loader. Other modules should import this rather than
    defining their own.
    """
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'config',
        'settings.yaml',
    )
    if not os.path.isfile(config_path):
        raise ValueError(f"settings.yaml not found at {config_path}")
    try:
        with open(config_path, 'r') as f:
            settings = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in settings.yaml: {e}") from e
    _validate_settings(settings)
    return settings
