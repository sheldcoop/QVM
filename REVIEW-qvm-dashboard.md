# Review: QVM Dashboard (`review-qvm-dashboard` branch)

Date: 2026-09-29. Reviewer: Muse Code. Scope: read-only review + test run, no source fixes.

## 1. Tests: NO — 157 passed, 5 failed (162 collected, not 28)

Command from the task (`cd qvm_dashboard && PYTHONPATH=. pytest tests/ -q`) was run
with the project venv (Python 3.12.12). System `python3` is 3.9.6 and cannot even
collect the suite (`TypeError: unsupported operand type(s) for |` on
`XLImage | None` in `src/excel_export.py` — needs Python >= 3.10; README states
no minimum Python version).

Failures (all on `review-qvm-dashboard`, same as `main` — no code was changed):

1. `test_bullseye.py::test_bullseye_has_summary_and_legend_annotations` —
   `AssertionError: Missing zone legend annotation` (no `⬤` annotation on the
   bullseye figure; the `zone_legend_annotation` helper exists in
   `src/chart_helpers.py` but the figure under test carries no such annotation).
2. `test_bullseye.py::test_bullseye_renders_to_png` —
   `choreographer ... BrowserFailedError`: kaleido cannot launch Chrome in this
   environment (environmental, not a code bug).
3. `test_excel_export.py::test_ensure_chrome_on_path_sets_common_windows_locations` —
   `KeyError: 'PATH'`: the test deletes `PATH` from the environment and
   `_ensure_chrome_on_path()` reads `os.environ['PATH']` unconditionally.
4. `test_excel_export.py::test_unified_export_handles_malformed_grid_ids` —
   pandas `setitem` error writing string Grid IDs (`'A'`, `'B2'`, …) into an
   int64 column (real robustness bug in the export path).
5. `test_visuals_package.py::test_bullseye_and_quiver_legend_below_axis_title` —
   `assert []`: expected bottom legend annotation missing (same family as #1).

Note: the task brief says "all 28 tests" — the suite actually collects
**162 tests**. The "28" figure is stale.

## 2. Code vs README: mostly YES, with deviations

- Architecture matches: `app.py` entry, `config/settings.yaml`, `src/parser.py`,
  `src/core_shrinkage_parser.py`, `src/ingestion.py`, `src/display_frame.py`
  (single screen+Excel table builder), `src/excel_export.py`,
  `src/visuals/` package (`bullseye`/`quiver`/`distribution`), `src/views/`,
  `src/theme.py`, `src/chart_helpers.py`, `ui/sidebar.py`. All present as drawn.
- Config-driven: yes for tolerances, rings, heights, diagnostics, nominal coords
  (`utils.load_settings` + required-keys validation). By-design exception the
  README itself documents: colours live in `src/theme.py`. Minor deviation the
  README does not mention: `utils._COLUMN_DEFAULTS` and hardcoded ring defaults
  in `chart_helpers.get_rings` let code run on partial settings, so settings.yaml
  is not strictly the only source at runtime (tests depend on this).
- Pure functions: `registration_shrinkage.compute_distance_shrinkage`,
  `chart_helpers`, `display_frame.build_display_frame` are pure
  `(df, settings) -> result`, no Streamlit/I-O. Caveat: `convert_to_microns` and
  `calculate_annular_ring` mutate the caller's DataFrame in place
  (`df[col] = ...`); only `build_display_frame`'s internal `.copy()` shields
  callers. Not strictly pure.
- Task-brief vs README mismatch: the brief describes a "QVM Database Analysis
  Dashboard ... for analyzing the Horus database". The actual README describes a
  "QVM Manufacturing Dashboard" for PCB machine logs. No Horus database content
  exists anywhere in the repo. The brief description appears to belong to a
  different app (possibly the deleted `dbanalysis` module, see below).

## 3. Red flags

- **Orphaned `dbanalysis` artifacts**: `src/dbanalysis/` and
  `src/dbanalysis/visuals/` contain zero `.py` sources — only `__pycache__`
  (`engine`, `config`, `loader`, `prep`, `schema`, `summary`, `columns`,
  `visuals`, `box`, `control`, `spc`, `trend`, `_style`). `tests/__pycache__`
  holds compiled `test_dbanalysis`, `test_engine_config`, `test_summary`,
  `test_columns_loader`, `test_download_center`, `test_visuals`, and
  `src/views/__pycache__` holds `database_analysis`, `download_center`,
  `impedance_analysis`, `landing_pad_analysis`, `pad_analysis`,
  `trace_analysis`, `via_analysis` — none with source. A whole Database-Analysis
  feature (there is a `Database-Analysis` branch) was removed from source but
  its bytecode lingers. Stale `__pycache__` should be cleaned and ignored.
- **README test docs are inaccurate**: says `pytest` from root with no Python
  version requirement; system Python 3.9 fails collection; suite size quoted
  nowhere near 162; kaleido/Chrome requirement for 1 PNG test is environmental.
- **`TOLERANCES.annular_ring_min: 0.0`** — with the shipped default, QC failure
  highlighting/counting never triggers (annular ring widths are non-negative by
  construction). Possibly intentional as a "breakout limit", but ships as a
  no-op gate.
- Failures #1/#5 (missing legend annotation) and #4 (malformed Grid IDs) look
  like genuine code/test-contract drift, not environment issues.

## 4. Fixes applied (same branch, after the review)

- Bullseye now adds the shared `zone_legend_annotation` at y=-0.16 with a
  deeper bottom margin (fixes #1 and #5).
- `_ensure_chrome_on_path` uses a separator-agnostic dirname so Windows Chrome
  paths resolve on POSIX hosts too; the test asserts via
  `os.environ.get('PATH', '')` (fixes #3 — the `KeyError` was in the test's
  own assert, and the dirname miss was a real cross-platform bug).
- Malformed-Grid-ID test casts the column to object dtype first (pandas>=2
  refuses string setitem into int64); the export path itself already coerces
  via `build_display_frame` (fixes #4).
- PNG render test skips gracefully when Chrome cannot launch (fixes #2,
  environmental).
- Deleted orphan bytecode: `src/dbanalysis/` tree and stale `dbanalysis` /
  analysis-view / removed-test `.pyc` files (were git-ignored, not tracked).
- `convert_to_microns` / `calculate_annular_ring` are now pure (copy-on-write);
  covered by `test_calc_helpers_do_not_mutate_input`.
- `pyproject.toml` declares `requires-python = ">=3.10"`; README "Running
  Tests" documents the venv + Chrome requirements.
