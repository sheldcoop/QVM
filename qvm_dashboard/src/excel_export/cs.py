"""Core Shrinkage workbook writer."""

import pandas as pd

from src.core_shrinkage_parser import (
    affine_residuals_um, both_frame, compute_affine_analysis,
    compute_centered_deviation_table, compute_scale_factor,
    compute_shrinkage_summary, layer_frame, qp_shrinkage_um, summary_frame,
)
from ._shared import _warnings_sheet


def write_core_shrinkage_excel(writer: pd.ExcelWriter,
                               front_df: pd.DataFrame,
                               back_df: pd.DataFrame,
                               meta: dict,
                               warnings: list = None,
                               nominal_coords: dict = None,
                               settings: dict = None) -> None:
    """Write Core Shrinkage data into the given ExcelWriter.

    Sheets written:
    - 'Core Shrinkage - Front'  Quarter | Grid | X | Y            (skipped if empty)
    - 'Core Shrinkage - Back'   Quarter | Grid | X | Y            (skipped if empty)
    - 'Core Shrinkage'          Quarter | Grid | Front X/Y | Back X/Y (both layers only)
    - 'CS Summary'              headline ppm / residual µm / outliers, per layer (nominal set)
    - 'QP Shrinkage - Front'    Quadrant | X1..Y2 pitch error in µm (when nominal_coords set)
    - 'QP Shrinkage - Back'     same                              (when nominal_coords set)
    - 'Scale Factor - Front'    Quadrant | X/Y Shrinkage (ppm)     (when nominal_coords set)
    - 'Scale Factor - Back'     same                              (when nominal_coords set)
    - 'Affine - Front'          affine decomposition params       (when nominal_coords set)
    - 'Affine - Back'           same                              (when nominal_coords set)
    - 'Raw Deviation - Front'   nominal vs physical raw deltas    (when nominal_coords set)
    - 'Raw Deviation - Back'    same                              (when nominal_coords set)
    - 'Residuals - Front'       per-fiducial residuals in µm + Outlier (nominal set)
    - 'Residuals - Back'        same                              (when nominal_coords set)
    - 'Report'                  job metadata + main measurement table
    - 'Warnings'                parser warnings

    Units: deviations/residuals/QP in µm, shrinkage in ppm (rationalised).
    """
    if not front_df.empty:
        layer_frame(front_df).to_excel(writer, sheet_name='Core Shrinkage - Front', index=False)
    if not back_df.empty:
        layer_frame(back_df).to_excel(writer, sheet_name='Core Shrinkage - Back', index=False)

    # Main table: side-by-side when both layers, else the single available layer
    if not front_df.empty and not back_df.empty:
        main = both_frame(front_df, back_df)
        main.to_excel(writer, sheet_name='Core Shrinkage', index=False)
    elif not front_df.empty:
        main = layer_frame(front_df)
    elif not back_df.empty:
        main = layer_frame(back_df)
    else:
        main = pd.DataFrame()

    # 3-level analysis sheets (only when nominal coords are available)
    if nominal_coords:
        outlier_um = float((settings or {}).get('CORE_SHRINKAGE', {}).get('outlier_um', 50.0))

        # CS Summary — headline numbers per layer, Metric | Front | Back
        summary_cols = {}
        for lbl, ldf in [('Front', front_df), ('Back', back_df)]:
            if ldf.empty:
                continue
            s = summary_frame(compute_shrinkage_summary(ldf, nominal_coords, settings))
            if not s.empty:
                summary_cols[lbl] = s.set_index('Metric')['Value']
        if summary_cols:
            cs_summary = pd.DataFrame(summary_cols)
            cs_summary.index.name = 'Metric'
            cs_summary.reset_index().to_excel(writer, sheet_name='CS Summary', index=False)

        for lbl, ldf in [('Front', front_df), ('Back', back_df)]:
            if ldf.empty:
                continue
            qp = qp_shrinkage_um(ldf)                       # µm pitch error
            sf = compute_scale_factor(ldf)
            if not qp.empty:
                qp.to_excel(writer, sheet_name=f'QP Shrinkage - {lbl}', index=False)
            if not sf.empty:
                # ppm only — drop the bare scale-factor columns
                sf_ppm = sf[['Quadrant', 'X Shrinkage (ppm)', 'Y Shrinkage (ppm)']]
                sf_ppm.to_excel(writer, sheet_name=f'Scale Factor - {lbl}', index=False)
            analysis = compute_affine_analysis(ldf, nominal_coords, settings)
            if analysis:
                analysis['params'].to_excel(
                    writer, sheet_name=f'Affine - {lbl}', index=False)
                affine_residuals_um(analysis, outlier_um).to_excel(
                    writer, sheet_name=f'Residuals - {lbl}', index=False)
                coords = compute_centered_deviation_table(ldf, nominal_coords, settings)
                if not coords.empty:
                    coords.to_excel(writer, sheet_name=f'Coordinates - {lbl}', index=False)

    # Report sheet — job metadata prepended to the main table
    report = main.copy()
    for meta_key, col_name in [
        ('project_name', 'Project_Name'),
        ('part_number',  'Part_Number'),
        ('lot_number',   'Lot_Number'),
        ('lot_name',     'Lot_Name'),
        ('build_up',     'Buildup'),
        ('process',      'Process'),
        ('panel',        'Job_Panel'),
    ]:
        report.insert(0, col_name, meta.get(meta_key, ''))
    report.to_excel(writer, sheet_name='Report', index=False)

    # Warnings sheet
    ws_warn = writer.book.create_sheet('Warnings')
    _warnings_sheet(ws_warn, warnings or [])
