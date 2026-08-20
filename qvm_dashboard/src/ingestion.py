"""File ingestion helpers for QVM uploads."""

import logging
import re
from typing import Optional, Tuple, List

import pandas as pd

from src.parser import parse_qvm_content, parse_filename, QVMParseError
from src.upload_metadata import UploadMetadata, resolve_upload_metadata
from src.utils import calculate_annular_ring

logger = logging.getLogger(__name__)


def _normalize_build_up(value: Optional[str]) -> Optional[str]:
    """Normalize Build Up values to canonical `BU-XX` when numeric.

    Examples:
    - `2`, `02`, `BU02`, `bu-2` -> `BU-02`
    - Unknown/blank -> None
    - Non-numeric custom values are returned as-is (trimmed).
    """
    if value is None:
        return None

    raw = str(value).strip()
    if not raw or raw.lower() == 'unknown':
        return None

    bu_match = re.fullmatch(r'(?i)bu[-_\s]?(\d+)', raw)
    if bu_match:
        return f"BU-{bu_match.group(1).zfill(2)}"

    if re.fullmatch(r'\d+', raw):
        return f"BU-{raw.zfill(2)}"

    return raw


def ingest_uploaded_file(uploaded_file, settings: dict,
                         file_override: Optional[dict] = None,
                         default_build_up: Optional[str] = None) -> Tuple[pd.DataFrame, List[str], List[str], UploadMetadata, dict]:
    """Parse one uploaded file and resolve metadata overrides.

    Returns:
        df: Parsed dataframe with annular ring calculated and Panel/Side set.
        (``default_build_up`` is the lowest tier of the Build Up precedence
        chain; the dashboard currently derives Build Up per file, so nothing
        in the app passes it.)
        parse_warnings: Parser warnings returned by parse_qvm_content.
        ui_warnings: User-facing warning strings for filename/override conflicts.
        resolved: Resolved upload metadata object.
        filename_info: Raw filename parse metadata.
    """
    file_override = file_override or {}
    build_up_override = _normalize_build_up(file_override.get('build_up_override'))
    default_build_up = _normalize_build_up(default_build_up)
    filename_info = parse_filename(uploaded_file.name)
    parsed_build_up = _normalize_build_up(filename_info.get('Build Up'))
    content = uploaded_file.getvalue().decode('utf-8')
    df, parse_warnings = parse_qvm_content(content, settings)
    df = calculate_annular_ring(df, settings)

    detected = df['Process'].iloc[0] if not df.empty else None
    resolved = resolve_upload_metadata(filename_info, detected, file_override)

    ui_warnings: List[str] = []
    hint = filename_info.get('format_hint')

    if resolved.process_override:
        if detected and resolved.process_override != detected:
            ui_warnings.append(
                f"⚠️ `{uploaded_file.name}`: user override sets type to **{resolved.process_override}** "
                f"(content detected **{detected}**). Using override."
            )
        df['Process'] = resolved.final_process
    elif hint is None:
        ui_warnings.append(
            f"⚠️ `{uploaded_file.name}`: filename doesn't include `VTP` or `PTV`. "
            f"Treated as **{detected}** based on file content."
        )
    elif detected is not None and hint != detected:
        ui_warnings.append(
            f"⚠️ `{uploaded_file.name}`: filename hints **{hint}** but content is "
            f"**{detected}**. Going with the content."
        )

    if resolved.panel_override and resolved.parsed_panel not in ('', 'Unknown') and resolved.panel_override != resolved.parsed_panel:
        ui_warnings.append(
            f"⚠️ `{uploaded_file.name}`: user override sets panel to **{resolved.panel_override}** "
            f"(filename panel **{resolved.parsed_panel}**). Using override."
        )
    if resolved.side_override and resolved.parsed_side not in ('', 'Unknown') and resolved.side_override != resolved.parsed_side:
        ui_warnings.append(
            f"⚠️ `{uploaded_file.name}`: user override sets side to **{resolved.side_override}** "
            f"(filename side **{resolved.parsed_side}**). Using override."
        )

    df['Panel'] = resolved.final_panel
    df['Side'] = resolved.final_side
    # Build Up precedence: explicit override > filename > sidebar default > Unknown
    df['Build Up'] = build_up_override or parsed_build_up or default_build_up or 'Unknown'

    return df, parse_warnings, ui_warnings, resolved, filename_info
