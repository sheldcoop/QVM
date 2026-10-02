# Registration shrinkage: three ways to measure it

> **Status.** The app reports the **company method only**. The centre-based
> and affine-fit methods described here were built for this comparison and
> then removed from the app to keep it simple (last present in commit
> `6a43e7f`; the figures below were produced and tested with that code). This
> document is kept as the record of why the company number can be trusted and
> where it cannot see.

This explains the three methods on the **Shrinkage** tab of the Pad-to-Via and
Via-to-Pad views: what each one does, where the company method falls short, and
why finding the centre "indirectly" works.

All numbers below were produced by the app's own code on the C4F BU-01
Pad-to-Via design (16 points; quadrant 232.5 x 193.9 mm; panel span
475.5 x 437.9 mm) and are pinned by tests in
`tests/test_registration_shrinkage.py`. The measured positions are made up to
isolate one effect at a time; they are not production data.

Sign convention everywhere: **measured minus design**, so negative = shrink.

## The three methods

| | Company (distance) | Centre-based | Affine fit |
|---|---|---|---|
| Idea | Compare lengths inside each quadrant with the design lengths | Put measured and design points around their own centre, then compare | Fit shift, rotation, X scale, Y scale and shear to all points at once |
| Data used | 8 lengths per axis (2 per quadrant) | all 16 points | all 16 points |
| Full-panel value | mean of the 4 quadrant values | one fit over the whole panel | one fit over the whole panel |
| Sees distance between quadrants | no | yes | yes |
| Removes panel rotation | no | no | yes |
| Finds a bad point | no | no | yes, and leaves it out |
| Extra output | — | — | rotation, shear, residual per point |
| Where it comes from | `Core Shrinkage Calculation.xlsx` | this document | the Core Shrinkage tab (`core_shrinkage_math.py`) |

The company method is the default and the one written to the Excel report. It
is checked against the company workbook cell for cell by the test
`test_company_method_matches_the_company_workbook_cell_for_cell`.

## Can the centre be found indirectly?

Yes. The measuring machine reports positions from its own origin, which has
nothing to do with the panel centre. But the centre does not have to be known:
**the average of the points is the centre**, both for the design and for the
measurement. Subtract it and every position is expressed from the centre.

Take four points along one edge, two quadrants of 260 with a gap of 20:

| | Point 1 | Point 2 | Point 3 | Point 4 | Centre (average) |
|---|---|---|---|---|---|
| Design | 20 | 280 | 300 | 560 | 290 |
| Design from centre | −270 | −10 | +10 | +270 | 0 |

**Case A, the panel shrank evenly by 100 ppm** (machine origin 1000 away):

| | Point 1 | Point 2 | Point 3 | Point 4 | Centre |
|---|---|---|---|---|---|
| Measured | 1020.027 | 1280.001 | 1299.999 | 1559.973 | 1290.000 |
| Measured from centre | −269.973 | −9.999 | +9.999 | +269.973 | 0 |

- Company: both lengths are 259.974 instead of 260, so −26 µm, **−100 ppm**.
- Centre-based: every "from centre" value is 0.9999 times the design value,
  so **−100 ppm**.

Same answer. For even shrinkage the two methods always agree.

**Case B, the quadrants kept their size but moved 40 µm apart:**

| | Point 1 | Point 2 | Point 3 | Point 4 | Centre |
|---|---|---|---|---|---|
| Measured | 1019.980 | 1279.980 | 1300.020 | 1560.020 | 1290.000 |
| Measured from centre | −270.020 | −10.020 | +10.020 | +270.020 | 0 |

- Company: both lengths are still exactly 260, so **0 ppm**. It reports "no
  change" although the panel is 40 µm longer.
- Centre-based: the points sit further from the centre than designed,
  **+76.7 ppm**.

How the centre-based number is calculated: the scale is the slope of "measured
from centre" against "design from centre", i.e.
sum(design x measured) / sum(design x design). Minus 1 and times a million
gives ppm. X and Y are done separately.

Two facts worth knowing:

- **Inside one quadrant the centre-based value equals the company value.** For
  the four corners of a rectangle, the slope about the centre is the average of
  the two opposite lengths over the design length, which is the company
  formula. So the company method is the centre idea applied to each quadrant
  on its own.
- **The difference appears only for the whole panel**, where the company
  method averages four quadrant numbers and never looks at the distance
  between quadrants.

## Where the company method falls short

Four made-up panels. Each has only one thing wrong with it. Values are
full-panel X shrinkage in ppm.

| Panel | What really happened | Company | Centre-based | Affine fit |
|---|---|---|---|---|
| 1 | Even shrink of 100 ppm | −100.0 | −100.0 | −100.0 |
| 2 | Quadrants unchanged, each moved 10 µm away from the centre | **0.0** | +43.0 | +43.0 |
| 3 | No size change; panel lies rotated by 0.3° on the machine | **−13.7** | −13.7 | 0.0 (and reports 0.3°) |
| 4 | No size change; one point (UL_4) is 80 µm off in X | **+43.0** | −0.9 | 0.0 (UL_4 rejected) |
| 5 | No size change; panel sheared by 100 ppm | 0.0 | 0.0 | 0.0 (and reports the shear) |

What each row shows:

1. **Even shrinkage: all three agree.** The company method is not wrong; on a
   panel that only shrinks or grows evenly it gives the right number.
2. **It is blind between the quadrants.** The company panel value is the mean
   of four quadrant values, and each of those only uses lengths inside its own
   quadrant. A panel that stretches in the gaps, or quadrants that drift
   apart, do not show up at all. In Y the same panel reads +50.2 ppm with the
   other two methods and 0.0 with the company method.
3. **Rotation looks like shrinkage.** The company lengths are differences in
   X only (or Y only). A rotated panel projects shorter on each axis, by
   1 − cos(angle). At 0.3° that is 14 ppm of shrinkage that did not happen.
   The centre-based method has the same weakness, because it also treats X
   and Y separately. Only the affine fit takes the rotation out. For scale:
   0.1° gives 1.5 ppm, so this matters only when a panel is placed carelessly.
4. **One bad point moves the whole result, and nothing says so.** The length
   that uses UL_4 is 80 µm too long, the UL quadrant reads +40 µm (+172 ppm),
   and the panel average moves by +43 ppm. The table shows a high UL quadrant
   but not which point caused it. The affine fit reports UL_4 as 80 µm off the
   fit, leaves it out, and the panel result stays at 0.
5. **Shear is invisible to it.** A panel pushed into a parallelogram has the
   same X and Y lengths, so both simple methods report nothing. The affine fit
   reports the shear angle. This one does not make the company number wrong;
   it is information the company method cannot give.

**Repeatability.** With the same random measurement error on every point
(3 µm, panel truly unchanged, 1500 simulated measurements), the full-panel
result scatters by ±6.5 ppm with the company method and ±4.5 ppm with the
other two. The company method is about 40 % noisier, because it uses only the
short lengths inside the quadrants and not the long distance across the panel.

## What this means in practice

- Keep the **company method** as the reported number: it is the agreed
  calculation and it is right when the panel changes size evenly.
- Use the **comparison table** on the Shrinkage tab ("Compare the three
  methods") as a check. When the three agree, the company number can be
  trusted. When they differ, the table above says what to suspect:
  - company differs from both others → the quadrants moved against each other;
  - company and centre-based agree but the affine fit differs → the panel was
    rotated on the machine, or a point is off (see the residual table);
  - affine fit rejected a point → remeasure that point.
- The **affine fit** needs the exact design position of every point, which is
  why the design positions are stored per Build Up and file type in
  `settings.yaml`. The company and centre-based methods only need the
  distances, which are the same for all four C4F datasets.

## What the first real files showed

Two Via-to-Pad files of one panel (front and back) were run through all three
methods. Neither gave a shrinkage number, for two different reasons, and both
are now recognised by the app instead of being reported as shrinkage.

| File | What it contains | What a blind calculation would say | What the app says now |
|---|---|---|---|
| Front | Every via within 9 µm of (0, 0): each site measured in its own local coordinates | −999,994 ppm | Positions are relative to each site; export in panel coordinates |
| Back | Real panel positions; quadrants of 230.67 × 194.02 mm | −7,873 ppm in X, +641 ppm in Y | Does not match the configured design (232.5 × 193.9 mm); design is probably of another product |

What can be said about the back file without a design: the four quadrants
measure 230.675, 230.671, 230.661 and 230.672 mm in X (14 µm between largest
and smallest) and 194.028, 194.018, 194.023 and 194.028 mm in Y (10 µm). The
affine fit also shows the panel lay rotated by 0.058° on the machine, which
is harmless (0.5 ppm).

To get shrinkage for that product, its 16 design positions have to be added to
`REGISTRATION_SHRINKAGE.DESIGNS`.

## Limits of this comparison

- The example panels are constructed, not measured. They show what each method
  can and cannot see; they do not say how often each situation occurs on real
  panels. Running the comparison on real files will show that.
- Which centre the company sheet is filled from, pad or via, is not confirmed.
  The app uses the via centre and can be switched per file type
  (`REGISTRATION_SHRINKAGE.measured_point`).
- With only four points, the per-quadrant affine fit has little left over to
  judge by; its strength is the fit over all 16 points.
