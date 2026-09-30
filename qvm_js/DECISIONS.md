# QVM Dashboard - decisions

## D13 (flow redesign): Upload / Analyse / Export, verdict first — supersedes D2
The app no longer mirrors the Streamlit tabs 1:1. The user lands on Upload,
drops files, and the app auto-classifies the process (Pad-to-Via vs Via-to-Pad
vs Core Shrinkage) by filename/content (`parse.classifyAndIngest`); the user
never picks a process tab. Analyse opens with a verdict banner
(`domain.verdict`: annular fail / CS outlier dot = fail; shrinkage outlier /
non-Stable pattern / warnings = warn; else pass), then process pills, scope,
charts, and the measurement table. Export owns the workbook + PNGs + manifest.
Old per-process views (`ptv.js`, `vtp.js`, `coreshk.js`, `panelmap.js`,
`renderQcView`/`renderCsView`) retired; `qc.js` keeps only shared renderers
(tiles, table, analytics, shrinkage, stepper, warnings) plus `jobVerdict` /
`jobWorkbook`.

## D1 (M1): Memory only, no store machinery
The app keeps uploads in session memory; only tolerances and theme persist
(localStorage). The tracker's `store.js` save-to-folder, revision, backup,
undo, and audit machinery is NOT ported — analyst-only tool, nothing to save.

## D2 (M1): Same 4 tabs as the Streamlit app
Router views: Panel Map, Pad to Via, Via to Pad, Core Shrinkage (+ Health,
Help). Keeps every later milestone's scope identical to the Python app.

## D4 (M2): Full test battery, adapted
`vendor/` (Chart.js 4.5.1, SheetJS) verbatim. `fake-dom`, `a11y-audit`,
`contrast` verbatim/namespace-switched. `css-check`, `ui-smoke`, `run-tests`,
`test.html` adapted to QVM files. `app-smoke`, `dom-budget`, `tests.js`,
`ui-kit.js` written fresh (subset matching copied components).
`preview.*`/`make-preview`/`make-demo-data` deferred — tracker-data-specific,
revisit if QVM needs a demo-data preview (M9).

## D6 (M3): Rows use internal keys, mm units
Parsed rows are plain objects (`location`, `gridId`, `padDiameter`,
`viaDiameter`, `coordX/Y`, `sc`, `dx`, `dy`, `padPts`, `viaPts`, `process`,
`panel`, `side`, `buildUp`, `annularRing`) in mm — never display labels or
µm. Display mapping happens at render (M6) via COLUMN_NAMES.

## D12 (M9): Workbook parity minus embedded images
SheetJS Community Edition cannot embed PNGs, so the workbook carries chart
DATA tables while charts download as one-click PNGs (canvas, no Chrome).
Every other sheet matches Python: Report, process sheets, Shrinkage Summary,
Warnings. Sample data: generated PtV/VtP pair (seeded) + the real CS pair.

## D11 (M8): Quiver arrows are canvas, panel map is the PNG
Arrows/labels/crosshair/summary/legend drawn by an inline Chart.js plugin
(same pattern as M7 rings) so M9 PNG export captures everything. Arrow
palette: expansion→critical, contraction→c-blue, twist→warning,
offset→accent. Panel Map tab shows `assets/Panel_Map.png` (copied verbatim).

## D10 (M7): Zone colors follow the live theme
Python's Catppuccin zones map to theme tokens: exceptional→accent,
excellent→ok, good→c-teal, acceptable→warning, fail→critical. Builders read
`t.color()` at build time (rebuilt on theme change). Box plot = floating
IQR bars + range bars + median line-ticks (no boxplot plugin).

## D9 (M6): Session module + shared QC renderer
Uploads live in `QVM.session` (files, rows, overrides, scope); views read,
upload flow writes. PtV/VtP share `QVM.qc.renderQcView`; CS has
`renderCsView`. FileReader wiring lives in qc.js; engine stays pure.
CS filename/content parsing ported (state machine, grid-mapped).

## D8 (M5): Settings view, no PIN — resolves Q2
Tolerances, USLs, outlier caps, and CS thresholds live in a Settings view
(`QVM.settings`, localStorage `qvm.settings.v1`, deep-merged over defaults).
Analyst-editable, no PIN (analyst-only tool).

## D7 (M3): annularRing ships early
The one-formula `domain.annularRing` landed in M3 (ingest attaches it) rather
than waiting for the M4 statistics milestone.

## D5 (M2): Tracker's heatmap reserved for M8
`js/ui/heatmap.js` NOT copied yet; it is the prime candidate for the Core
Shrinkage distortion-map warp surface. Copy then, not now.

## D3 (M1): Verbatim clone, namespace-switched
`css/app.css` sections 1-4, `js/themes.js`, and `js/ui/` (core, components,
overlays, charts, glyphs) are verbatim copies from metrology-request-tracker
with only `MRT` → `QVM` (and `mrt.theme` → `qvm.theme`) renamed. No gate,
identity, save lamp, or user menu — analyst-only shell.
