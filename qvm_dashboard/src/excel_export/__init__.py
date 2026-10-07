"""Excel export helpers for QVM quality reports.

Provides chart-to-image rendering (kaleido) and sheet population.

Layout:
- ``_shared`` — Chrome discovery, PNG rendering, panel-map image, warnings
  sheet, sheet-name safety. No Streamlit dependency.
- ``qvm`` — Pad-to-Via / Via-to-Pad workbook (``write_unified_excel``).
- ``cs`` — Core Shrinkage workbook (``write_core_shrinkage_excel``).
- ``shrinkage`` — registration shrinkage workbook (``write_shrinkage_excel``).

``import src.excel_export`` keeps working: the public entry points are
re-exported here.
"""

import os as os  # re-exported: tests patch ``excel_export.os.path``

from ._shared import PACKAGE_ROOT, WarnFn, _ensure_chrome_on_path
from .cs import write_core_shrinkage_excel
from .qvm import write_unified_excel
from .shrinkage import write_shrinkage_excel

__all__ = [
    "PACKAGE_ROOT",
    "WarnFn",
    "os",
    "write_core_shrinkage_excel",
    "write_unified_excel",
    "write_shrinkage_excel",
    "_ensure_chrome_on_path",
]
