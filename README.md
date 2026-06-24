# QVM Database Analysis Dashboard

A [Streamlit](https://streamlit.io/) dashboard for statistical analysis of the
**Horus** manufacturing-metrology database. Upload the Horus Excel workbook and
explore measurement distributions, process stability, and capability across
build-ups, sides, processes, lots, and panels.

The app is intentionally focused: it does **one thing** — Database Analysis of the
Horus workbook — and does it through a single, configuration-driven engine.

---

## Features

- **Six analyses**, one per Horus sheet, plus a **Download Center**:

  | Sub-view            | Sheet               | Metrics                                          | Unit |
  |---------------------|---------------------|--------------------------------------------------|------|
  | Roughness           | `Roughness`         | Ra Mean, Rz Mean                                 | nm   |
  | Impedance           | `IMP_Trace`         | Line, Space                                      | µm   |
  | Top to Bottom Via   | `Top_to_Bottom_Via` | Average Via Depth, Top Diameter, Bottom Diameter | µm   |
  | Trace               | `Trace`             | Line, Space                                      | µm   |
  | Pad                 | `Pad`               | Diameter                                         | µm   |
  | Landing Pad         | `Landing_Pad`       | Landing Pad Diameter                             | µm   |

- **Scope filters** (derived from your data): Build-up, Side, and a Chart-Type
  toggle (Box Plot / Control Chart). Results are then broken out per Process.
- **Statistical summary tables**: overall, lot-by-lot, and panel-level
  (N, Mean, Std Dev, Min, Max, **Pp / Ppk**).
- **Box plots**: distribution per lot, dots colored by Unit, with spec limits
  (LSL / Target / USL) and a Pp/Ppk capability badge.
- **Control charts**: X-bar & S with statistically correct limits (see below).
- **Download Center**: a multi-sheet **Master Excel Summary** and a **ZIP archive**
  of every chart as PNG (box + control, for every build-up/side/process/metric).

---

## Charts & statistics — how to read them

### Box plot (distribution)
Compares the **distribution** of a metric across lots. Each dot is one
measurement (colored by Unit). Spec limits are drawn as horizontal lines and a
**Pp / Ppk** badge summarizes capability. This is the right view for comparing
lots, panels, or units.

### Control chart (X-bar & S)
Answers a different question: **is the process stable / predictable?**

- **Rational subgroups = (lot, panel).** Each point is one panel of one lot:
  the **X-bar** point is the mean of that panel's measurements, the **S** point is
  its within-panel standard deviation. Subgrouping by panel turns a handful of
  lots into ~20+ points, which is what makes control limits meaningful.
- **Lot bands.** Consecutive panels of the same lot sit under one faint shaded
  band labeled with the lot number. Alternating shading separates lots, so two
  points under the same shade are two panels of that lot.
- **Correct limits.** Control limits use **within-subgroup** variation via the
  standard unbiasing constants — X-bar: `X̿ ± A₃·S̄`; S-chart: `B₃·S̄` … `B₄·S̄` —
  computed per subgroup so unequal subgroup sizes get correct variable
  (stair-step) limits. Constants `c₄, A₃, B₃, B₄` are computed exactly from the
  Gamma function (`src/dbanalysis/visuals.py`). When every subgroup has a single
  measurement, sigma falls back to the moving-range individuals estimate
  (`MR̄ / 1.128`) and the S-chart is omitted.
- **Western Electric rules** are evaluated in z-score space (so they remain valid
  under variable limits) and color the points: blue = in control; red/orange/
  yellow/purple = Rule 1/2/3/4.
- **Gating.** With fewer than 2 subgroups the chart is replaced by a short note —
  control limits on 1 point are meaningless.
- **No spec limits on the control chart — by design.** An X-bar chart plots
  subgroup *means* (voice of the process); spec limits apply to *individual* parts
  (voice of the customer) and means cluster ~√n× tighter, so drawing specs here is
  a scale mismatch and a classic SPC error. Spec compliance lives on the box plot
  and the Pp/Ppk summary.

### Capability: Pp / Ppk (not Cp / Cpk)
Capability is computed from the **overall (long-term) sample sigma**, so it is
**Pp / Ppk** (process *performance*), not Cp / Cpk (which need within-subgroup
sigma). One-sided specs are supported: with a single limit, Pp is "N/A" but Ppk is
still computed from that side.

---

## Expected data format

The uploaded `.xlsx` is the Horus workbook with one sheet per analysis (see the
table above). Column matching is **case/space/underscore-insensitive**, so
`Lot_Number`, `lot number`, and `LOT NUMBER` all match. Each analysis sheet is
expected to contain:

- Grouping columns: `Lot Number`, `Buildup`, `Side`, `Process`, `Panel`, `Unit`
- One or more **metric** columns (per the table above)
- Optional **spec-limit** columns named `<metric> LSL` / `<metric> Target` /
  `<metric> USL` (e.g. `Line LSL`, `Diameter USL`; Landing Pad uses the prefix
  `Landing Pad Diameter`)

A sample workbook, `Horus database v3.xlsx`, is included at the repo root.

---

## Project structure

```
QVM/
├── Horus database v3.xlsx        # sample input
└── qvm_dashboard/
    ├── app.py                    # entry point: sidebar, sub-view nav, dispatch
    ├── config/settings.yaml      # UI title + theme colors (only used values)
    ├── assets/styles.css
    ├── requirements.txt
    ├── src/
    │   ├── utils.py              # load_settings()
    │   ├── theme.py              # design tokens (colors used by charts)
    │   ├── dbanalysis/           # the analysis engine + pure logic
    │   │   ├── config.py         # DB_ANALYSES: declarative per-sheet config
    │   │   ├── engine.py         # render_analysis(): one generic view path
    │   │   ├── loader.py         # cached single-sheet Excel reads
    │   │   ├── columns.py        # tolerant column / spec-limit resolution
    │   │   ├── summary.py        # summary tables + Pp/Ppk (pure pandas)
    │   │   └── visuals.py        # box plot + X-bar/S control chart (pure Plotly)
    │   └── views/download_center.py
    ├── ui/sidebar.py             # file upload + nav buttons
    └── tests/test_dbanalysis.py  # 28 tests (stats, SPC constants, data layer)
```

**Design notes (SoC / DRY / KISS):**
- The six analyses are **not** six files — they are entries in `DB_ANALYSES`
  (`config.py`) rendered by one `render_analysis()` engine (`engine.py`).
- Chart functions are **pure** `(DataFrame, …) -> go.Figure` — no Streamlit, no
  I/O — so they are unit-testable in isolation.
- Excel access is cached and reads **only the needed sheet** (`loader.py`).
- All column lookups go through `columns.py`, the single source of truth.

---

## Getting started

From the repository root:

```bash
# 1. Create a virtual environment (Python 3.10+)
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r qvm_dashboard/requirements.txt

# 3. Run the app
cd qvm_dashboard
streamlit run app.py
```

Then open the URL Streamlit prints (default http://localhost:8501), upload
`Horus database v3.xlsx` in the sidebar, pick a sub-view, and explore.

---

## Testing

The test suite covers the pure core and the data layer (no Streamlit runtime
needed):

```bash
cd qvm_dashboard
PYTHONPATH=. pytest tests/ -q
```

Covers: summary tables & Pp/Ppk (including one-sided specs), the SPC unbiasing
constants (hand-verified against standard tables), control-chart subgrouping /
gating / lot bands, box-plot rendering, and the column/loader/config helpers.

---

## Configuration

`config/settings.yaml` holds only what the app actually consumes:

- `UI_STRINGS.dashboard_title` — the page title
- `COLORS.*` — the theme variables injected into `assets/styles.css`

Chart colors/design tokens live in `src/theme.py`.

---

## Notes

- PNG export in the Download Center requires **`kaleido`** (in `requirements.txt`).
- The app works exclusively with Horus `.xlsx` / `.xls` workbooks; other file
  types uploaded in the sidebar are ignored with a warning.
