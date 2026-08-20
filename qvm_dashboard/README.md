# QVM Manufacturing Dashboard

A Streamlit dashboard for analyzing PCB Quality Vision Machine (QVM) text logs. It ingests machine output files, parses registration measurements, and provides interactive charts for process engineers and quality teams to detect alignment errors, tool wear, and lamination distortion.

---

## How to Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Navigate to `http://localhost:8501` in your browser.

---

## File Formats

The dashboard accepts text log files (`.txt`) in three formats: the two QVM
registration formats, and Core Shrinkage CAM-order files.

### Filename Convention

| Format | Example Filename | Parts |
|---|---|---|
| Pad-to-Via | `Post PFC_Pad to Via_Panel 20_F.txt` | `<process>_<type>_<panel>_<side>.txt` |
| Via-to-Pad | `Via to Pad_Panel 25_F.txt` | `<type>_<panel>_<side>.txt` |
| Core Shrinkage | `C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt` | matched on `core_shrinkage` + `Front`/`Back` |

Panel number and Side (F/B) come from the filename. **Pad-to-Via vs Via-to-Pad
is decided by file content**, not the name — the name only supplies a hint used
to warn you when the two disagree. Core Shrinkage is the exception: it is a
different format with a different parser, so it is routed by filename alone.

### Pad-to-Via (PtV) Format

Measures the offset between a pad center (absolute X/Y coordinates on the panel) and the drilled via center. Each block corresponds to one hole and contains:

```
Circle: Pad_LL_2(ID:1, From 180 Pts.)
     Coord. X =        63.857203
     Coord. Y =       104.634501
     Diameter =         0.308911

Circle: Via_LL_2(ID:2, From 70 Pts.)
     Coord. X =        63.856611
     Coord. Y =       104.630820
     Diameter =         0.016742

Distance: PtV_LL_2(ID:3) between Via_LL_2(ID:2) and Pad_LL_2(ID:1)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681
```

Each block produces one row. The file contains 16 blocks (one per fiducial site).
Measurement lines are `<label> = <number>`; `From N Pts.` on a Circle header is
the optical edge-point count and is optional.

### Via-to-Pad (VtP) Format

Measures the registration between a laser-drilled via and its target pad in the **local reference frame** of each fiducial site. No absolute X/Y coordinates are available. Each block contains:

```
Circle: Via_LL_2(ID:1, From 65 Pts.)
     Diameter =         0.016742
Circle: Pad_LL_2(ID:2, From 180 Pts.)
     Diameter =         0.308911
Distance: VtP_LL_2(ID:3) between Pad_LL_2(ID:2) and Via_LL_2(ID:1)
           SC =         0.003728
           DX =         0.000592
           DY =         0.003681
```

Via-to-Pad files are parsed **by value position, not by header**, because the
machine's exporter is unreliable about label lines: back-side files often drop
the `Circle: Pad`, `Distance:` and location-suffix labels entirely. Per site the
values always appear in the order *via diameter, pad diameter, SC, DX, DY*, and
each `DY` closes a site — so a stray value can only disturb its own site.

VtP files carry no absolute coordinates, so `Coord. X` / `Coord. Y` are absent
from VtP data and are dropped from its Excel sheets.

### Core Shrinkage (CS) Format

A different measurement entirely: the *as-built* position of each of the 16
fiducials on a core layer, compared against its nominal CAM design coordinate.
The difference across the panel is the core's shrinkage.

These files are routed by **filename**, not by content — any name containing
`core_shrinkage` or `core shrinkage` goes to the Core Shrinkage parser and never
reaches the QVM parser. `Front` or `Back` in the name sets the layer, and the
panel number is read the same way as for QVM files.

```
C4F_Core_Shrinkage_Panel 28_Front_CAMorder.txt
C4F_Core_Shrinkage_Panel 28_Back_CAMorder.txt
```

Front and Back are separate uploads. Upload both to get front↔back registration
and the side-by-side comparison sheets; either alone still analyses on its own.

Sample files for both layers, plus the reference calculation workbook, are in
[`sample_data/`](sample_data/).

---

## Uploading Files

Use the sidebar to upload one or more `.txt` files. Multiple files (multiple panels or sides) can be uploaded at once — they are concatenated into a combined dataset. Use the **Panel** and **Side** scope filters that appear in each view to isolate a single panel or side.

Filename defaults are still supported and recommended:

- Include `VTP` or `PTV` in the filename.
- Include panel number as `Panel <N>` or `Panel_<N>`.
- End with side marker `_F` or `_B` before `.txt`.

Optional per-file overrides are available in the sidebar under **Optional Per-File Overrides**. If set, override precedence is:

1. User override
2. Parsed filename value
3. `Unknown`

For process type, default routing is content-based; user type override is applied only when selected.

You can also set **Build Up (BU)** per uploaded file (for example `BU-01`, `BU-02`).
When multiple BUs are uploaded together, a top-level **Build Up** selector appears above analysis so you can switch between `All` and each BU value.

---

## Navigation

The top navigation bar has four tabs:

| Tab | Purpose |
|---|---|
| **Panel Map** | Visual layout of all 16 fiducial sites on a PCB panel (always available) |
| **Pad to Via** | Analysis of PtV files — Quality Control and Analytics |
| **Via to Pad** | Analysis of VtP files — Quality Control and Analytics |
| **Core Shrinkage** | Analysis of Core Shrinkage CAM-order files — 4 sub-views |

---

## Pad-to-Via / Via-to-Pad Sub-Views

Both QVM process tabs expose the same two sub-views. (Core Shrinkage has its
own four — see [below](#core-shrinkage-sub-views).)

### Quality Control
Table of all measurements with pass/fail colour coding against the Annular Ring
tolerance in `settings.yaml` — rows below `TOLERANCES.annular_ring_min` are
highlighted. Above the table, five summary tiles report the Annular Ring min,
max, mean ± standard deviation, worst site, and failure count.

The Excel export button produces **one workbook** covering the current Build Up,
Panel and Side scope, with separate Pad-to-Via and Via-to-Pad sheets. See
[Excel Export](#excel-export) below.

### Analytics
Three tabs, identical for both processes:

- **Registration Scatter** — DX/DY bullseye with concentric tolerance rings,
  plus a per-site SC bar chart ordered by Grid ID.
- **Quiver Plot** — directional error vectors at each fiducial site, coloured by
  distortion class (red = expansion, sky = contraction, yellow = twist,
  blue = global offset), with a sensitivity slider to amplify small errors.
- **Box Plot** — SC distribution: one "All sites" box plus one box per panel
  quarter.

---

## Core Shrinkage Sub-Views

Scope this tab with its own **Panel** and **Layer** (Front / Back / Both)
filters. It is independent of the Build Up selector — Core Shrinkage filenames
carry no Build Up token.

All analysis is measured against `CORE_SHRINKAGE.NOMINAL_COORDS`. Without that
config the tab degrades gracefully: it warns and shows the raw coordinate tables
instead of failing.

### Quality Control
Headline shrinkage in ppm per layer, checked against `shrink_usl_ppm`, with the
per-fiducial residual table. Residuals above `outlier_um` are flagged as
outliers to remeasure rather than silently averaged into the fit.

### Analytics
The three-level model, per layer:

1. **QP Shrinkage** — raw pitch error between fiducial pairs, in µm.
2. **Scale Factor** — X and Y shrinkage per quadrant, in ppm.
3. **Affine Analysis** — a least-squares affine fit decomposed into scale,
   rotation and shear, so fixturing rotation is separated from real shrinkage
   (`rotation_warn_deg`) and anisotropic shrinkage is called out
   (`aniso_ppm`). Includes front↔back registration when both layers are loaded.

### Distortion Map
The deviation field drawn on the panel layout — each fiducial's measured
displacement from nominal, exaggerated for visibility and coloured by the
`residual_zones_um` bands, plus a warp surface.

### Method
A static explainer of how the numbers are derived. No export button.

Every sub-view except Method offers an Excel export — see below.

---

## Excel Export

One workbook per download, containing:

| Sheet | Contents |
|---|---|
| `Pad to Via` | Pad-to-Via measurements + the Panel Map reference image |
| `Via to Pad` | Via-to-Pad measurements + the Panel Map reference image |
| `Report` | All rows with job metadata prepended and the process USL column appended |
| `Analytics <PROC> <BU>` | The four registration charts, one sheet per process per Build Up |
| `Warnings` | Parser warnings, or a note that there were none |

Process sheets are written only for processes present in the current scope.
Chart embedding needs **kaleido**; if a chart cannot be rendered, a placeholder
image is embedded in its place and the rest of the workbook is unaffected.

The filename is built from the data in scope, e.g.
`QVM_VTP_P20_F_BU-01_Lot-1234.xlsx`.

**Core Shrinkage** exports its own workbook: per-layer measurement sheets, the
side-by-side Front/Back table when both are loaded, and — when
`NOMINAL_COORDS` is configured — `CS Summary`, `QP Shrinkage`, `Scale Factor`,
`Affine`, `Coordinates` and `Residuals` sheets per layer, plus `Report` and
`Warnings`. Deviations and residuals are in µm, shrinkage in ppm.

## Configuration (`config/settings.yaml`)

### POSITIONAL_MAPPING
Maps block index (0–15, in the order blocks appear in the file top-to-bottom) to Grid ID. Grid IDs are two-digit codes where the tens digit is the quarter (1=UL, 2=LL, 3=LR, 4=UR) and the units digit is the hole number within that quarter (1–4).

```yaml
POSITIONAL_MAPPING:
  - "22"   # block 0  → LL_2
  - "21"   # block 1  → LL_1
  - "23"   # block 2  → LL_3
  - "24"   # block 3  → LL_4
  - "12"   # block 4  → UL_2
  - "11"   # block 5  → UL_1
  - "13"   # block 6  → UL_3
  - "14"   # block 7  → UL_4
  - "32"   # block 8  → LR_2
  - "31"   # block 9  → LR_1
  - "33"   # block 10 → LR_3
  - "34"   # block 11 → LR_4
  - "42"   # block 12 → UR_2
  - "41"   # block 13 → UR_1
  - "43"   # block 14 → UR_3
  - "44"   # block 15 → UR_4
```

Change this list if the machine's block output order changes.

### GRID_MAPPING
Maps location strings (e.g., `UL_1`) to Grid IDs (e.g., `11`). Used for display and filtering. Must be consistent with `POSITIONAL_MAPPING`.

### TOLERANCES
Pass/fail threshold for Quality Control colouring.

| Key | Meaning |
|---|---|
| `annular_ring_min` | Minimum acceptable annular ring (µm). Rows below it are highlighted and counted as failures. |

### VTP_REGISTRATION / PTV_REGISTRATION
Tolerance rings and spec limits. The bullseye's five zones are defined by four
concentric rings:

| Key | Meaning |
|---|---|
| `ring_exceptional_um` | Innermost boundary (blue zone) |
| `ring_excellent_um` | Excellent boundary (green zone) |
| `ring_good_um` | Good boundary (teal zone) |
| `ring_acceptable_um` | Acceptable boundary; beyond it is fail (red) |
| `vtp_usl_um` / `ptv_usl_um` | Upper spec limit written to the Excel Report sheet |
| `outlier_cap_um` | SC values above this are flagged as parser warnings and clipped on the site-bar chart |

`PTV_REGISTRATION` carries only `ptv_usl_um` and `outlier_cap_um`; the rings are
read from `VTP_REGISTRATION` for both processes.

### DIAGNOSTICS
Constants for the quiver plot's distortion classification: `panel_center_x` /
`panel_center_y` (panel centre in mm, used to decide whether an error points
outward or inward), `quiver_min_arrow_length`, `quiver_expansion_dot_threshold`,
`quiver_twist_dot_threshold` and `quiver_twist_magnitude_um`.

### CORE_SHRINKAGE
Everything the Core Shrinkage tab measures against.

| Key | Meaning |
|---|---|
| `NOMINAL_COORDS` | Nominal CAM design position (mm) of each of the 16 fiducials. All shrinkage is measured against this; every site in `GRID_MAPPING` needs an entry. |
| `shrink_usl_ppm` | Headline-shrinkage pass/fail spec (ppm) |
| `shrink_ppm` | Below this, a scale reading is noise rather than real shrinkage |
| `aniso_ppm` | Above this, X and Y differ enough to call it anisotropic |
| `rotation_warn_deg` | Rotation above this is flagged as fixturing, not shrinkage |
| `outlier_um` | Per-dot residual above this = outlier / remeasure |
| `residual_zones_um` | Colour bands for the Distortion Map (must be ascending, and within `outlier_um`) |
| `distance_usl_mm` / `outlier_cap_mm` | Front↔back offset spec and outlier cap |

### PLOT_SETTINGS, CHART_HEIGHTS, PANEL_VIEW, FIGURE_SETTINGS, COLORS, EXCEL_EXPORT
Vector-multiplier slider range; per-chart heights in pixels; panel-map geometry
and colours; and the Panel Map image path and embed size.

Chart **colours** are design tokens, not runtime config — they live in
`src/theme.py`.

---

## Column Reference

| Column | Unit | Meaning |
|---|---|---|
| `Location` | — | Fiducial site name (e.g., `UL_1`, `LL_2`) |
| `Grid ID` | — | Two-digit numeric site code (e.g., `11` = UL quarter, hole 1) |
| `Coord. X` / `Coord. Y` | mm | Absolute pad center position on the panel (PtV only; absent in VtP) |
| `Pad Diameter` | µm (display) / mm (raw) | Outer diameter of the etched copper pad |
| `Via Parameter` | µm (display) / mm (raw) | Diameter of the laser-drilled or mechanically-drilled via |
| `Annular Ring` | µm (display) / mm (raw) | `(Pad Diameter − Via Diameter) / 2 − Distance` — narrowest copper ring left around the hole |
| `PtV Distance` | µm (display) / mm (raw) | Straight-line distance between pad center and via center (the instrument's SC field). Shown under this header on Pad-to-Via, and as `VtP Distance (SC)` on Via-to-Pad — one measurement, two labels. |
| `Shift (DX)` | µm (display) / mm (raw) | Horizontal registration error (X component of pad→via vector) |
| `Shift (DY)` | µm (display) / mm (raw) | Vertical registration error (Y component of pad→via vector) |
| `Via Pts.` / `Pad Pts.` | count | Number of edge points the optical sensor used to fit each circle — higher is better. Parsed and exported, not currently charted. |
| `Panel` | — | Panel number, from the filename or a per-file override |
| `Side` | — | `F` (front) or `B` (back), from the filename or a per-file override |
| `Build Up` | — | Build-up tag resolved per uploaded file (override first, then job-level default) |
| `Process` | — | `Pad to Via` or `Via to Pad` detected from file content (optionally overridden in sidebar) |

**Physical meanings:**

- **SC** (Straight-line Center distance): the magnitude of the registration error — how far the via landed from where the pad center is.
- **DX / DY**: signed X and Y components of that error. Useful for detecting directional bias (e.g., consistent +DX across all sites = global X offset).
- **Annular Ring**: the most safety-critical metric. If it falls below the minimum threshold, the via copper is not reliably connected to the pad — a functional defect. Note the registration distance is subtracted: a via that lands off-centre eats into the ring on one side.
- **Pts.**: optical edge confidence. The machine fits a circle to detected edge points. Fewer points = noisier fit = less trustworthy diameter and center measurement.

---

## Architecture

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for module dependency + data-flow
diagrams and a "where do I change X?" guide.

```
QVM/
├── pyproject.toml                  # pytest configuration (import root, test paths)
└── qvm_dashboard/
    ├── app.py                      # Entry point: navigation, ingestion, view dispatch
    ├── ARCHITECTURE.md             # Diagrams + where-to-change-what guide
    ├── requirements.txt
    ├── config/
    │   └── settings.yaml           # Runtime config: tolerances, limits, column names, mappings, heights
    ├── sample_data/                # Core Shrinkage example logs + reference workbook
    ├── assets/
    │   ├── styles.css              # Custom CSS for dark theme and nav button styling
    │   └── Panel_Map.png           # Reference image embedded in Excel measurement sheets
    ├── ui/
    │   └── sidebar.py              # Upload, per-file overrides, job info, nav button renderer
    ├── src/
    │   ├── parser.py               # QVM text log parser (auto-detects PtV vs VtP)
    │   ├── core_shrinkage_parser.py # CS log parser + affine / shrinkage maths
    │   ├── ingestion.py            # Parse one upload + resolve its metadata overrides
    │   ├── upload_metadata.py      # Override > filename > Unknown precedence rules
    │   ├── display_frame.py        # THE display table builder (screen + Excel share it)
    │   ├── excel_export.py         # One workbook: process sheets, Report, Analytics, Warnings
    │   ├── panel_mapping.py        # Panel map figure builder (4-quarter Plotly layout)
    │   ├── utils.py                # load_settings, convert_to_microns, resolve_columns, annular ring
    │   ├── theme.py                # ONE home for design tokens (Catppuccin palette, grid geometry)
    │   ├── chart_helpers.py        # Reusable chart logic (rings, zone colours, dark layout, cards)
    │   ├── visuals/                # Plotly figure builders (package)
    │   │   ├── bullseye.py         #   plot_vtp_bullseye, plot_vtp_site_bars
    │   │   ├── quiver.py           #   plot_quiver (ABF distortion map)
    │   │   └── distribution.py     #   plot_vtp_box (SC distribution by quarter)
    │   └── views/
    │       ├── base.py             # BaseView: settings slices + shared number formatting
    │       ├── core_shrinkage.py   # Core Shrinkage: QC, Analytics, Distortion Map, Method
    │       ├── quality_control.py  # QC table, stats tiles, Excel export button
    │       └── registration_scatter.py  # Bullseye + per-site SC bars (shared PtV/VtP)
    └── tests/
        └── ...                     # pytest test suite
```

---

## Running Tests

From the repository root:

```bash
pytest
```

`pyproject.toml` puts `qvm_dashboard/` on the import path and points pytest at
`qvm_dashboard/tests`, so the suite imports `src.*` and `ui.*` exactly as the
app does. Excel chart-embedding tests are skipped automatically when `kaleido`
is unavailable.
