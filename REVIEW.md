# Hardening Review — QVM (`review/hardening`)

Zero-feature refactor of `qvm_dashboard/` (the JS migration branch is out of
scope). Behavior changes: none (any genuine bug found is reported and
approved before fixing).

## M1 baseline (2026-10-07, .venv python 3.11)

- Suite: **227 passed, 1 skipped in ~28s** (25 test files).
- Coverage: **80% total** (2970 stmts, 590 missed).
- Weakest modules: `views/core_shrinkage.py` 14%, `views/registration_scatter.py`
  22%, `ui/sidebar.py` 24%, `src/scope.py` 26%, `views/quality_control.py` 56%,
  `views/base.py` 63%, `excel_export/_shared.py` 80%, `parser.py` 87%.
- Ruff (default rules): **392 errors** — C408 `dict()` calls 142, UP006/UP045
  py310 modernization 145, I001 import sort 41, RUF013/UP035/BLE001/ISC004/F401
  most of the rest. Format: 55 of 61 files would reformat.
- Mypy (default): **121 errors in 26 files**.
- Return-annotation rate: **91%** (177/195) — far better than faster-aoi's 52%.
- 13 bare `except Exception`; streamlit imported in all views + `scope.py`.

## Findings (risk x value)

1. **Biggest view nearly uncovered** (`views/core_shrinkage.py` 14%, 260 stmts):
   needs characterization tests before any refactor nearby.
2. **Scope/session coupling** (`scope.py` 26% + reads streamlit): Panel/Side
   helpers mixed with session access; candidate for purity split.
3. **Two READMEs + ARCHITECTURE + SHRINKAGE_METHODS**: docs are good; review
   must not let code drift from them (esp. `resolve_columns` contract).
4. **Lint debt is mechanical**: C408/UP/I001 are auto-fixable; BLE001 (9) and
   bare excepts (13) need per-site review.
5. **Mypy 121 errors, but 91% annotated**: strict-everywhere may be feasible
   here, unlike faster-aoi — decide in M10 after seeing error kinds.

## Milestone reports

- M1: branch created from `e574c69`; this file. Tests 227/227, coverage 80%.
- M2: tooling bootstrap (`requirements-dev.txt` floors: pytest/cov/ruff/mypy/
  pre-commit; pytest moved out of runtime reqs; CI + README install both).
  +12 parser characterization tests (value extractors, non-finite handling,
  filename router incl. Unknown fallbacks). Tests 239/239.
- M3: +10 math property tests (affine/rigid identity + known-transform
  recovery, ppm linearity, classify priority, vector directions, outlier
  isolation) — `core_shrinkage_math.py` 98%→100%. Unit cleanup:
  `UM_PER_MM` constant (math + registration deltas) and the parser's
  inline ppm formula now calls `_to_ppm`; zero new import coupling.
  Tests 249/249.
- M4: ingestion audit — no faster-aoi-style silent drops: parser warnings
  thread through ingestion to session state + UI; `load_settings` /
  `resolve_columns` already single-homed in `utils`. Dual BU normalizers
  VERIFIED intentionally different (Optional-vs-str, bare-number and
  zero-pad semantics) and pinned by +4 tests so nobody merges them.
  Tests 253/253.
