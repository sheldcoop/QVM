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

The dashboard accepts QVM text log files (`.txt`). Two formats are supported, distinguished by filename convention.

### Filename Convention

| Format | Example Filename | Parts |
|---|---|---|
| Pad-to-Via | `Post PFC_Pad to Via_Panel 20_F.txt` | `<process>_<type>_<panel>_<side>.txt` |
| Via-to-Pad | `Via to Pad_Panel 25_F.txt` | `<type>_<panel>_<side>.txt` |

The parser extracts Panel number, Side (F/B), and Process type from the filename automatically. Files that contain `Via to Pad` anywhere in the name are treated as Via-to-Pad format.

### Pad-to-Via (PtV) Format

Measures the offset between a pad center (absolute X/Y coordinates on the panel) and the drilled via center. Each block corresponds to one hole and contains:

```
Circle: Pad_UL_1
  X: 12.345
  Y: -6.789
  Diameter: 0.3125
Circle: Via[UL_1]
  X: 12.347
  Y: -6.791
  Diameter: 0.0200
Distance: Pad_UL_1 -> Via[UL_1]
  SC: 0.002
  DX: 0.002
  DY: -0.002
```

Each block produces one row. The file contains 16 blocks (one per fiducial site).

### Via-to-Pad (VtP) Format

Measures the registration between a laser-drilled via and its target pad in the **local reference frame** of each fiducial site. No absolute X/Y coordinates are available. Each block contains:

```
Circle: Via[LL_2]
  Diameter: 0.0201
Circle: Pad_LL_2
  Diameter: 0.3130
Distance: Via[LL_2] -> Pad_LL_2
  SC: 0.003
  DX: 0.001
  DY: -0.003
```

VtP has no global coordinates, so spatial analysis views (Quiver, Polar Drift, 2D Heatmap) are not available.

---

## Uploading Files

Use the sidebar to upload one or more `.txt` files. Multiple files (multiple panels or sides) can be uploaded at once — they are concatenated into a combined dataset. Use the **Panel** and **Side** scope filters that appear in each view to isolate a single panel or side.

---

## Navigation

The top navigation bar has four tabs:

| Tab | Purpose |
|---|---|
| **Panel Map** | Visual layout of all 16 fiducial sites on a PCB panel (always available) |
| **Pad to Via** | Analysis of PtV files — all 6 sub-views available |
| **Via to Pad** | Analysis of VtP files — 3 sub-views available (no coordinate-dependent views) |
| **Alignment** | Coming soon |

---

## Sub-Views

### Quality Control
Table of all measurements with pass/fail color coding against tolerances defined in `settings.yaml`. Includes an Excel export button. The export drops entirely-null columns (e.g., `Coord. X` / `Coord. Y` are omitted for VtP files since those files have no coordinates).

### Analytics (PtV only)
Two plot types:

- **Quiver/Vector Plot** — Directional error vectors at each fiducial site, color-coded by distortion class (red = expansion/shrinkage, gold = twist, blue = global offset). Includes a sensitivity slider to amplify small errors. Also shows the Root Cause Confidence Engine (Bayesian classifier scoring Expansion, Shrinkage, Twist, Offset) and CAM Compensation Estimate (net ppm shift guidance).
- **Heatmap** — Color-coded grid showing measurement magnitude across the 4×4 fiducial grid.

### Optical Edge Confidence
Bar charts scoring how reliably the machine's optical system detected each hole edge. Low point counts (< 40 pts) indicate poor edge detection, often from copper exposure variation or debris. Shows separate charts for Vias and Pads.

### Process Stability
Side-by-side scatter plots (Via diameter vs. Pad diameter) for each measurement location, plotted against user-configurable Upper/Lower Control Limits. Monitors tool wear (Via channel) and etch chemistry consistency (Pad channel).

### Polar Drift / Machine Health (PtV only)
Polar coordinate view of registration errors. Detects systematic angular drift in the laser positioning system — errors that cluster at specific angles indicate a machine calibration issue.

### 2D Spatial Heatmap / Laser Scan Field (PtV only)
Color-coded panel-level heatmap of registration error magnitude at each fiducial X/Y position. Identifies regions of the panel with consistently higher errors, which can indicate fixture warp or field distortion in the laser scanner.

---

## Configuration (`config/settings.yaml`)

### POSITIONAL_MAPPING
Maps block index (0–15, in the order blocks appear in the file top-to-bottom) to Grid ID. Grid IDs are two-digit codes where the tens digit is the quadrant (1=UL, 2=LL, 3=LR, 4=UR) and the units digit is the hole number within that quadrant (1–4).

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
Pass/fail thresholds for Quality Control coloring. Key fields:

| Key | Meaning |
|---|---|
| `annular_ring_min` | Minimum acceptable annular ring (mm) |
| `ptv_distance_max` | Maximum acceptable pad-to-via distance (mm) |
| `shift_max` | Maximum acceptable DX or DY shift (mm) |

### PROCESS_STABILITY
Default control limits and chart styling for Process Stability charts. These can be overridden per-session in the sidebar.

| Key | Meaning |
|---|---|
| `via_nominal_diameter` | Nominal via drill diameter (mm) |
| `via_ucl` / `via_lcl` | Upper/Lower Control Limits for via diameter (mm) |
| `pad_nominal_diameter` | Nominal pad etch diameter (mm) |
| `pad_ucl` / `pad_lcl` | Upper/Lower Control Limits for pad diameter (mm) |

### OPTICAL_EDGE_THRESHOLDS
Thresholds for color-coding optical edge confidence point counts.

| Key | Meaning |
|---|---|
| `green_min` | Points ≥ this → green (good detection) |
| `orange_min` | Points ≥ this → orange (marginal) |
| Below `orange_min` | Red (poor detection) |

---

## Column Reference

| Column | Unit | Meaning |
|---|---|---|
| `Location` | — | Fiducial site name (e.g., `UL_1`, `LL_2`) |
| `Grid ID` | — | Two-digit numeric site code (e.g., `11` = UL quadrant, hole 1) |
| `Coord. X` / `Coord. Y` | mm | Absolute pad center position on the panel (PtV only; absent in VtP) |
| `Pad Diameter` | µm (display) / mm (raw) | Outer diameter of the etched copper pad |
| `Via Parameter` | µm (display) / mm (raw) | Diameter of the laser-drilled or mechanically-drilled via |
| `Annular Ring` | µm (display) / mm (raw) | `(Pad Diameter − Via Diameter) / 2` — copper ring remaining around the hole |
| `PtV Distance` | µm (display) / mm (raw) | Straight-line distance between pad center and via center (SC field) |
| `Shift (DX)` | µm (display) / mm (raw) | Horizontal registration error (X component of pad→via vector) |
| `Shift (DY)` | µm (display) / mm (raw) | Vertical registration error (Y component of pad→via vector) |
| `Pts.` | count | Number of edge points the optical sensor used to fit each circle — higher is better |
| `Type` | — | `Via` or `Pad` (row type, used internally for optical edge filtering) |
| `Panel` | — | Panel number extracted from filename |
| `Side` | — | `F` (front) or `B` (back) extracted from filename |
| `Process` | — | `Pad to Via` or `Via to Pad` extracted from filename |

**Physical meanings:**

- **SC** (Straight-line Center distance): the magnitude of the registration error — how far the via landed from where the pad center is.
- **DX / DY**: signed X and Y components of that error. Useful for detecting directional bias (e.g., consistent +DX across all sites = global X offset).
- **Annular Ring**: the most safety-critical metric. If it falls below the minimum threshold, the via copper is not reliably connected to the pad — a functional defect.
- **Pts.**: optical edge confidence. The machine fits a circle to detected edge points. Fewer points = noisier fit = less trustworthy diameter and center measurement.

---

## Architecture

```
qvm_dashboard/
├── app.py                              # Entry point: navigation, data ingestion, view dispatch
├── panel_mapping.py                    # Panel map figure builder (4-quadrant Plotly layout)
├── requirements.txt
├── config/
│   └── settings.yaml                   # All thresholds, limits, colors, column names, mappings
├── assets/
│   └── styles.css                      # Custom CSS for dark theme and nav button styling
├── ui/
│   └── sidebar.py                      # Sidebar: file upload, process limits, nav button renderer
├── src/
│   ├── parser.py                       # QVM text log parser (state machine, auto-detects PtV vs VtP)
│   ├── calculations.py                 # Annular ring and CAM compensation calculations
│   ├── data_processor.py               # Shared DataFrame transformations (filters, stats)
│   ├── utils.py                        # convert_to_microns() shared utility
│   ├── visuals.py                      # Plotly figure builders: quiver, heatmap, bullseye scatter
│   └── views/
│       ├── base.py                     # BaseView: shared chart helpers (height, background, grid)
│       ├── quality_control.py          # QC table with pass/fail coloring and Excel export
│       ├── analytics.py                # Quiver/vector plot and heatmap with root cause engine
│       ├── optical_edge_confidence.py  # Optical edge point count bar charts
│       ├── process_stability.py        # Via/Pad diameter control charts
│       ├── polar_drift.py              # Polar registration error drift chart
│       └── spatial_heatmap.py          # 2D spatial heatmap of error magnitude
└── tests/
    └── ...                             # pytest test suite
```

---

## Running Tests

```bash
PYTHONPATH=. pytest tests/
```
