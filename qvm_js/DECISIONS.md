# QVM Dashboard - decisions

## D1 (M1): Memory only, no store machinery
The app keeps uploads in session memory; only tolerances and theme persist
(localStorage). The tracker's `store.js` save-to-folder, revision, backup,
undo, and audit machinery is NOT ported — analyst-only tool, nothing to save.

## D2 (M1): Same 4 tabs as the Streamlit app
Router views: Panel Map, Pad to Via, Via to Pad, Core Shrinkage (+ Health,
Help). Keeps every later milestone's scope identical to the Python app.

## D3 (M1): Verbatim clone, namespace-switched
`css/app.css` sections 1-4, `js/themes.js`, and `js/ui/` (core, components,
overlays, charts, glyphs) are verbatim copies from metrology-request-tracker
with only `MRT` → `QVM` (and `mrt.theme` → `qvm.theme`) renamed. No gate,
identity, save lamp, or user menu — analyst-only shell.
