"""The Documentation tab: how shrinkage is calculated, step by step.

The worked example is not typed in: it is run through the same functions as
the Shrinkage tab, with the design quadrant size currently set in the sidebar,
so the page cannot drift away from what the app does.
"""

import pandas as pd
import streamlit as st

from src.registration_shrinkage import (
    compute_distance_shrinkage,
    design_for,
    design_lengths,
    shrinkage_config,
)
from src.views.base import full_width
from src.views.registration_shrinkage import _show
from src.visuals.shrinkage import plot_quadrant_bars, plot_quadrant_diagram, plot_shrinkage_panel

# Change of each quadrant in the example, in ppm (X, Y). Made up, to show
# quadrants that differ a little from each other.
_EXAMPLE_PPM = {'UL': (-90.0, -40.0), 'LL': (-110.0, -50.0), 'LR': (-120.0, -60.0), 'UR': (-80.0, -50.0)}
_MACHINE_ORIGIN = (301.4, 323.7)  # the machine's own zero; it must not matter


def _example(settings: dict):
    """(design points, measured frame, result) of the made-up example panel."""
    design = design_for(settings)
    rows = []
    for name, xy in design.items():
        quadrant = name[:2]
        corners = [design[f'{quadrant}_{c}'] for c in '1234']
        cx = sum(c['x'] for c in corners) / 4
        cy = sum(c['y'] for c in corners) / 4
        ppm_x, ppm_y = _EXAMPLE_PPM[quadrant]
        rows.append({
            'Location': name,
            'Coord. X': cx + (xy['x'] - cx) * (1 + ppm_x / 1e6) + _MACHINE_ORIGIN[0],
            'Coord. Y': cy + (xy['y'] - cy) * (1 + ppm_y / 1e6) + _MACHINE_ORIGIN[1],
        })
    measured = pd.DataFrame(rows)
    outlier_ppm = float(shrinkage_config(settings).get('outlier_ppm', 50.0))
    return design, measured, compute_distance_shrinkage(measured, design, outlier_ppm=outlier_ppm)


def _chart(figure, key: str) -> None:
    st.plotly_chart(figure, key=key, theme=None, **full_width(st.plotly_chart))


def render_documentation(settings: dict) -> None:
    lengths = design_lengths(settings)
    st.subheader('📖 Documentation: how shrinkage is calculated')
    st.caption('For the Shrinkage sub-view of the Pad to Via and Via to Pad tabs. '
               'Core Shrinkage is a separate calculation, described at the end.')
    if lengths is None:
        st.warning('No design quadrant size is set. Enter it in the sidebar under '
                   '"Shrinkage design size" to see the worked example.')
        return
    x_mm, y_mm = lengths
    outlier_ppm = float(shrinkage_config(settings).get('outlier_ppm', 50.0))
    max_ppm = float(shrinkage_config(settings).get('max_plausible_ppm', 2000.0))

    st.markdown(f"""
### 1. What shrinkage means here

A panel changes size during processing. Shrinkage is **how much its size differs
from the design**: measured size minus design size.

- **Negative** = the panel is smaller than designed (it shrank).
- **Positive** = the panel is larger than designed (it grew).

It is reported separately for **X** (width) and **Y** (height), because a panel
rarely changes by the same amount in both directions.

### 2. What the calculation needs

| Input | Where it comes from |
|---|---|
| The measured position of the 16 points (4 per quadrant) | The Pad-to-Via or Via-to-Pad file you upload |
| The design size of one quadrant in X | Sidebar, *Shrinkage design size* (now **{x_mm:g} mm**) |
| The design size of one quadrant in Y | Sidebar, *Shrinkage design size* (now **{y_mm:g} mm**) |

That is all. The four quadrants have the same design size, so two numbers
describe the whole design. Where the machine has its zero point does not
matter, because only distances between points are used.

### 3. The four points and the four lengths

The panel has four quadrants: **UL** (upper left), **LL** (lower left),
**LR** (lower right), **UR** (upper right). Each has four measured points.
""")
    _chart(plot_quadrant_diagram(x_mm, y_mm), 'doc_diagram')
    st.markdown(f"""
In every quadrant the width is measured twice and the height twice:

| Length | Formula | What it is |
|---|---|---|
| X1 | x of point 4 − x of point 1 | top edge |
| X2 | x of point 3 − x of point 2 | bottom edge |
| Y1 | y of point 1 − y of point 2 | left edge |
| Y2 | y of point 4 − y of point 3 | right edge |

The quadrant's **X length** is the average of X1 and X2; its **Y length** is the
average of Y1 and Y2. This is the calculation of the company workbook
*Core Shrinkage Calculation.xlsx*; filled with real file data, the workbook and
the app give the same numbers.

### 4. From a length to µm and ppm

**Delta (µm)** is the change itself:

> Delta X = (measured X length − design X length) × 1000

**ppm** is the same change compared with the length (parts per million):

> Shrinkage X (ppm) = (measured X length ÷ design X length − 1) × 1,000,000

The two always belong together: **ppm = µm ÷ design length in mm × 1000**.
With the current design size, 100 ppm is {x_mm * 0.1:.1f} µm in X and
{y_mm * 0.1:.1f} µm in Y. That is why Y can show fewer µm than X and still more
ppm: the quadrant is shorter in Y, so the same change is a larger share of it.

### 5. Worked example

A made-up panel, calculated by the app with the design size from the sidebar.
""")

    design, measured, result = _example(settings)
    table = result.quadrant
    first = table.iloc[0]
    st.markdown(f"**Quadrant {first['Quadrant']}, step by step**")
    points = measured.set_index('Location')
    quadrant = first['Quadrant']
    x = {c: float(points.loc[f'{quadrant}_{c}', 'Coord. X']) for c in '1234'}
    y = {c: float(points.loc[f'{quadrant}_{c}', 'Coord. Y']) for c in '1234'}
    x1, x2 = x['4'] - x['1'], x['3'] - x['2']
    st.markdown(f"""
| Step | Calculation | Result |
|---|---|---|
| X1 (top edge) | {x['4']:.4f} − {x['1']:.4f} | {x1:.4f} mm |
| X2 (bottom edge) | {x['3']:.4f} − {x['2']:.4f} | {x2:.4f} mm |
| X length | ({x1:.4f} + {x2:.4f}) ÷ 2 | {(x1 + x2) / 2:.4f} mm |
| Delta X | ({(x1 + x2) / 2:.4f} − {x_mm:g}) × 1000 | **{first['Delta X (um)']:+.1f} µm** |
| Shrinkage X | {first['Delta X (um)']:+.1f} µm ÷ {x_mm:g} mm × 1000 | **{first['Shrinkage X (ppm)']:+.1f} ppm** |

Y is done the same way with Y1 and Y2 against {y_mm:g} mm:
**{first['Delta Y (um)']:+.1f} µm**, **{first['Shrinkage Y (ppm)']:+.1f} ppm**.
""")
    st.markdown('**All four quadrants**')
    _show(table, ['Quadrant', 'X Design (mm)', 'X Measured (mm)', 'Delta X (um)', 'Shrinkage X (ppm)',
                  'Y Design (mm)', 'Y Measured (mm)', 'Delta Y (um)', 'Shrinkage Y (ppm)'])

    panel, uniformity = result.full_panel.iloc[0], result.uniformity.iloc[0]
    ppm_x = ' + '.join(f'({v:.0f})' for v in table['Shrinkage X (ppm)'])
    st.markdown(f"""
### 6. The panel numbers

| Number | How it is calculated | In the example |
|---|---|---|
| **Panel X** | average of the four quadrants' X | [{ppm_x}] ÷ 4 = **{panel['Shrinkage X (ppm)']:.1f} ppm** ({panel['Delta X (um)']:+.1f} µm) |
| **Panel Y** | average of the four quadrants' Y | **{panel['Shrinkage Y (ppm)']:.1f} ppm** ({panel['Delta Y (um)']:+.1f} µm) |
| **X − Y** | Panel X ppm minus Panel Y ppm | {panel['Shrinkage X (ppm)']:.1f} − ({panel['Shrinkage Y (ppm)']:.1f}) = **{panel['X-Y Offset (ppm)']:.1f} ppm** |
| **Quadrant range X** | largest minus smallest quadrant X ppm | {table['Shrinkage X (ppm)'].max():.0f} − ({table['Shrinkage X (ppm)'].min():.0f}) = **{uniformity['QTQ Range X (ppm)']:.1f} ppm** |
| **Quadrant range Y** | largest minus smallest quadrant Y ppm | **{uniformity['QTQ Range Y (ppm)']:.1f} ppm** |
| **Alerts** | quadrants more than {outlier_ppm:.0f} ppm from the panel value | **{len(result.outliers)}** |

What they tell you:

- **Panel X, Panel Y**: the overall size change. These are the headline numbers.
- **X − Y**: whether the panel changes equally in both directions. Zero means equal.
- **Quadrant range**: whether the four quadrants behave alike. A small range means
  the panel changed evenly; a large one means one area changed more than another.
- **Alerts**: which quadrant is the odd one out.

Together that is ten numbers: X and Y for each of the four quadrants, and X and
Y for the panel.

### 7. Reading the charts
""")
    _chart(plot_shrinkage_panel(result, design, 'Shrinkage Map  ·  example'), 'doc_map')
    st.markdown("""
**Shrinkage Map.** The panel with its four quadrants. Each quadrant carries a
horizontal arrow pair (X) and a vertical one (Y). Arrows pointing **inward and
blue** mean the quadrant shrank; **outward and red** mean it grew. Longer arrows
mean a larger change; the exact values are written in the middle of each
quadrant. The gap between the quadrants is only for the drawing.
""")
    _chart(plot_quadrant_bars(result, 'Shrinkage per quadrant  ·  example'), 'doc_bars')
    st.markdown(f"""
**Shrinkage per quadrant.** Copper bars are X, blue bars are Y, one pair per
quadrant, in ppm. The dashed lines are the panel values. Bars of equal height
mean an even panel.

### 8. How the app knows which point is which

Each point must be recognised as, for example, *UL_3* before anything can be
calculated. The app does this in a fixed order:

1. **By position.** The middle of the measured area splits the points into four
   quadrants; inside a quadrant, left/right and top/bottom give point 1 to 4.
   This is used whenever the file holds positions on the panel. If a name in the
   file disagrees with the position, the position wins and a warning is shown.
2. **By name.** If all positions in the file are about zero (each site exported
   in its own local coordinates), names like *Via_UL_3* are used.
3. **By order.** If there are no usable names either, the points are taken in
   the measurement order defined in the settings (`POSITIONAL_MAPPING`), with a
   warning, because this is only right if the operator followed that order.

Shrinkage itself always needs real panel positions: in cases 2 and 3 the Grid
IDs are filled, but there is no panel geometry to measure.

### 9. When no shrinkage is shown

| What the app says | Why | What to do |
|---|---|---|
| Positions are relative to each site | All points are within microns of each other; the file has no panel geometry | Export the measurement in panel coordinates |
| Measured quadrant size does not match the design | A quadrant is more than {max_ppm:.0f} ppm from the design size, which is more than shrinkage can explain | Check the design size in the sidebar; it may be another product |
| Missing corner point(s) for a quadrant | A point of that quadrant is not in the file | That quadrant is skipped; the others are reported |

In the second case the measured quadrant sizes are still listed, so the
quadrants can be compared with each other.

**A caution on the design size.** A wrong value gives a wrong result without an
error, as long as it stays below {max_ppm:.0f} ppm: a typing error of 0.05 mm
on {x_mm:g} mm is {0.05 / x_mm * 1e6:.0f} ppm. Always enter the design value,
never a measured one; with a measured value the shrinkage is zero by definition.

### 10. The Excel file

The **📥 Shrinkage Excel** button on the Shrinkage tab gives:

| Sheet | Content |
|---|---|
| Summary | One line per Build Up, Panel and Side |
| Quadrants | The quadrant values of every panel |
| Quadrant Sizes | Measured against design size |
| Calculation | Every step as live Excel formulas: click a cell to see how it is built, or change the design size and watch the result follow. The app's numbers are printed below for comparison |
| Charts | The Shrinkage Map and the bars |
| Notes | Method, design size used, warnings |

### 11. What this method does not see

It compares lengths **inside** each quadrant. So:

- A change in the **gap between quadrants** (quadrants drifting apart) is not in
  the number.
- A panel lying **rotated** on the machine reads slightly short; at 0.1° this is
  about 1.5 ppm, so it matters only for careless placement.
- **One bad point** shifts its quadrant; the quadrant range and the alert show
  that something is off, but not which point.

For reporting the size change of a panel these limits are small.

### 12. Core Shrinkage (the other tab)

The **Core Shrinkage** tab is a different calculation for a different file
(CAM-order Front/Back files). It fits shift, rotation and scale to all points
at once and reports the residual of each point. Its own **Method** sub-view
explains it. The two tabs do not share design values.
""")
