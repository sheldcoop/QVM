"""Helpers for resolving upload metadata with optional user overrides."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UploadMetadata:
    """Resolved metadata for a single uploaded file."""

    final_process: Optional[str]
    final_panel: str
    final_side: str
    parsed_panel: str
    parsed_side: str
    process_override: Optional[str]
    panel_override: Optional[str]
    side_override: Optional[str]


def resolve_override_value(
    override_value: Optional[str], parsed_value: str, unknown: str = "Unknown"
) -> str:
    """Return override value when provided, else parsed value, else unknown."""
    if override_value is not None and str(override_value).strip() != "":
        return str(override_value).strip()
    if parsed_value is not None and str(parsed_value).strip() != "":
        return str(parsed_value).strip()
    return unknown


def resolve_upload_metadata(
    filename_info: dict,
    detected_process: Optional[str],
    override: Optional[dict] = None,
) -> UploadMetadata:
    """Resolve final process/panel/side using precedence: override > parsed > unknown.

    Returns final values plus parsed/override fields for caller warning decisions.
    """
    override = override or {}
    process_override = override.get("process_override")
    panel_override = override.get("panel_override")
    side_override = override.get("side_override")

    parsed_panel = filename_info.get("Panel Number", "Unknown")
    parsed_side = filename_info.get("Side", "Unknown")

    final_process = process_override or detected_process
    final_panel = resolve_override_value(
        panel_override, parsed_panel, unknown="Unknown"
    )
    final_side = resolve_override_value(side_override, parsed_side, unknown="Unknown")

    return UploadMetadata(
        final_process=final_process,
        final_panel=final_panel,
        final_side=final_side,
        parsed_panel=parsed_panel,
        parsed_side=parsed_side,
        process_override=process_override,
        panel_override=panel_override,
        side_override=side_override,
    )
