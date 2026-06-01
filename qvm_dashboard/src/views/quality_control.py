"""
Quality Control View - Statistical summary and annular ring analysis
Extracted from app.py for modularity and reusability.
"""

import streamlit as st
import pandas as pd
from io import BytesIO
import openpyxl
from openpyxl.styles import PatternFill
from openpyxl.drawing.image import Image as XLImage
from PIL import Image as PILImage

from src.views.base import BaseView
from src.utils import convert_to_microns
from src.visuals import plot_vtp_bullseye


class QualityControlView(BaseView):
    """
    QualityControlView: Displays statistical summary and detailed quality metrics.
    
    Features:
    - Statistical summary: min, max, mean, std of annular ring
    - Failure counts and percentages
    - Excel export with conditional highlighting
    - Interactive dataframe with custom formatting
    """
    
    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """Render the Quality Control analysis view.

        Kwargs:
            is_via_to_pad (bool): true when rendering Via-to-Pad data
            meta (dict): sidebar metadata (project_name, panel, process, …)
        """
        is_via_to_pad = kwargs.get('is_via_to_pad', False)
        meta = kwargs.get('meta', {})

        col_names = self.col_names
        annular_col = col_names.get('annular_ring', 'Annular Ring')
        threshold = self.tolerances.get('annular_ring_min', 0.0)
        grid_id_col = col_names.get('grid_id', 'Grid ID')

        via_diam_col = col_names.get('inner_diameter', 'Via Parameter')
        pad_diam_col = col_names.get('outer_diameter', 'Pad Diameter')
        dx_col       = col_names.get('x_distance', 'Shift (DX)')
        dy_col       = col_names.get('y_distance', 'Shift (DY)')
        sc_col       = col_names.get('total_shift', 'SC')

        # Determine file type: Via-to-Pad has no Annular Ring column
        # is_via_to_pad is passed explicitly from app.py

        # Prepare display dataframe
        if is_via_to_pad:
            # Keep ONLY the 6 required columns for Via-to-Pad display
            # Also carry Side for Excel export (dropped from display later)
            vtp_keep = [c for c in [grid_id_col, via_diam_col, pad_diam_col, dx_col, dy_col, sc_col]
                        if c in filtered_df.columns]
            display_df = filtered_df[vtp_keep].copy()
            # Keep Side separately for Excel (not shown in UI table)
            _side_series = filtered_df['Side'].values if 'Side' in filtered_df.columns else None
        else:
            display_df = filtered_df.copy()
            cols_to_drop = [col for col in ['Panel', 'Side'] if col in display_df.columns]
            display_df = display_df.drop(columns=cols_to_drop)
            _side_series = None

        # Convert measurements from mm to microns (applies to whichever columns exist)
        measurement_cols = [pad_diam_col, via_diam_col, sc_col, dx_col, dy_col,
                            col_names.get('ptv_distance', 'PtV Distance'), annular_col]
        display_df = convert_to_microns(display_df, measurement_cols)

        # Sort by Grid ID ascending
        if grid_id_col in display_df.columns:
            display_df = display_df.sort_values(by=grid_id_col, ascending=True)
        
        # --- Display Statistical Summary ---
        st.subheader("📊 Statistical Summary")
        summary_cols = st.columns(5)
        
        # Calculate stats for annular ring
        if annular_col in display_df.columns:
            ar_min = display_df[annular_col].min()
            ar_max = display_df[annular_col].max()
            ar_mean = display_df[annular_col].mean()
            ar_std = display_df[annular_col].std()
            fail_count = (display_df[annular_col] < threshold).sum()
            fail_pct = (fail_count / len(display_df) * 100) if len(display_df) > 0 else 0
            
            with summary_cols[0]:
                st.metric(
                    "Min Annular Ring",
                    f"{ar_min:.3f} µm",
                    delta=f"{ar_min - threshold:.3f}" if ar_min < threshold else None,
                    delta_color="inverse"
                )
            with summary_cols[1]:
                st.metric("Max Annular Ring", f"{ar_max:.3f} µm")
            with summary_cols[2]:
                st.metric("Mean ± StdDev", f"{ar_mean:.3f} ± {ar_std:.3f} µm")
            with summary_cols[3]:
                worst_idx = display_df[annular_col].idxmin()
                worst_grid = display_df.loc[worst_idx, grid_id_col] if grid_id_col in display_df.columns else 'N/A'
                st.metric("Worst Point", f"Grid {worst_grid}", f"{ar_min:.3f} µm")
            with summary_cols[4]:
                st.metric(
                    "Failures",
                    f"{fail_count} ({fail_pct:.1f}%)",
                    delta=f"{fail_count} points" if fail_count > 0 else "✓ All Pass",
                    delta_color="inverse" if fail_count > 0 else "off"
                )
        
        st.markdown("---")
        
        # --- Export to Excel button ---
        col_left, col_right = st.columns([3, 1])

        with col_left:
            if is_via_to_pad:
                st.write("Via-to-Pad export: Location Grid ID | Via Diameter | Pad Diameter | DX | DY | SC  (µm)")
            else:
                st.write(f"Highlighting rows where {annular_col} < {threshold}")
        with col_right:
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                if is_via_to_pad:
                    _region_map = {'1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'}

                    def _fig_to_xl_image(fig, width_px=600, height_px=500) -> XLImage:
                        """Convert a plotly figure to an openpyxl Image object."""
                        img_bytes = fig.to_image(format='png', width=width_px, height=height_px, scale=2)
                        img_buf = BytesIO(img_bytes)
                        # Resize via PIL to control final cell size
                        pil_img = PILImage.open(img_buf)
                        out_buf = BytesIO()
                        pil_img.save(out_buf, format='PNG')
                        out_buf.seek(0)
                        xl_img = XLImage(out_buf)
                        xl_img.width  = width_px
                        xl_img.height = height_px
                        return xl_img

                    def _add_chart_to_sheet(ws, df_for_chart, settings, anchor='A20'):
                        """Generate scatter plot and embed it below data in the sheet."""
                        try:
                            fig = plot_vtp_bullseye(df_for_chart, settings)
                            xl_img = _fig_to_xl_image(fig)
                            ws.add_image(xl_img, anchor)
                        except Exception:
                            pass  # silently skip if chart generation fails

                    def _make_measurement_sheet(df_in, side_vals):
                        """Grid ID + measurements, no metadata."""
                        s = df_in.copy()
                        s = s.rename(columns={grid_id_col: 'Grid ID'})
                        return s

                    def _make_report_sheet(df_in, side_vals):
                        """Metadata + Fiducial info + measurements."""
                        s = df_in.copy()
                        grid_str = s[grid_id_col].astype(str).str.zfill(2)
                        s.insert(0, 'Fiducial_Number', grid_str.str[1].astype(int))
                        s.insert(0, 'Fiducial',        grid_str.str[0].map(_region_map))
                        s.insert(0, 'Side',        side_vals if side_vals is not None else '')
                        s.insert(0, 'Panel',       meta.get('panel', ''))
                        s.insert(0, 'Process',     meta.get('process', ''))
                        s.insert(0, 'Buildup',     meta.get('build_up', ''))
                        s.insert(0, 'Lot_Name',    meta.get('lot_name', ''))
                        s.insert(0, 'Lot_Number',  meta.get('lot_number', ''))
                        s.insert(0, 'Part_Number', meta.get('part_number', ''))
                        s.insert(0, 'Project_Name', meta.get('project_name', ''))
                        s = s.drop(columns=[grid_id_col])
                        return s

                    # Split by Side if both Front and Back are present
                    sides = filtered_df['Side'].unique() if 'Side' in filtered_df.columns else []
                    report_frames = []

                    if len(sides) > 1:
                        for side in sorted(sides):
                            mask = filtered_df['Side'] == side
                            side_display = display_df.loc[display_df.index.isin(filtered_df[mask].index)]
                            side_df_raw  = filtered_df[mask].copy()
                            side_vals    = filtered_df.loc[mask, 'Side'].values
                            sheet_name   = f'Via to Pad - {side}'
                            # Write measurement data
                            _make_measurement_sheet(side_display, side_vals).to_excel(
                                writer, sheet_name=sheet_name, index=False)
                            # Embed DX vs DY scatter below data (row 20 = after 16 data rows + header + gap)
                            ws = writer.sheets[sheet_name]
                            _add_chart_to_sheet(ws, side_df_raw, self.settings, anchor='A20')
                            report_frames.append(_make_report_sheet(side_display, side_vals))
                        # Combined Report sheet
                        report_df = pd.concat(report_frames, ignore_index=True)
                        report_df.to_excel(writer, sheet_name='Report', index=False)
                    else:
                        # Single side
                        _make_measurement_sheet(display_df, _side_series).to_excel(
                            writer, sheet_name='Via to Pad', index=False)
                        ws = writer.sheets['Via to Pad']
                        _add_chart_to_sheet(ws, filtered_df, self.settings, anchor='A20')
                        _make_report_sheet(display_df, _side_series).to_excel(
                            writer, sheet_name='Report', index=False)
                else:
                    # Pad-to-Via: full export with conditional red highlighting
                    display_df_export = display_df.dropna(axis=1, how='all').copy()
                    display_df_export.to_excel(writer, sheet_name='QVM Data', index=False)

                    workbook = writer.book
                    worksheet = writer.sheets['QVM Data']
                    red_fill = PatternFill(start_color='FFCCCC', end_color='FFCCCC', fill_type='solid')

                    if annular_col in display_df_export.columns:
                        ar_col_idx = list(display_df_export.columns).index(annular_col) + 1
                        for row_idx, value in enumerate(display_df_export[annular_col], start=2):
                            if value < threshold:
                                for col_idx in range(1, len(display_df_export.columns) + 1):
                                    worksheet.cell(row=row_idx, column=col_idx).fill = red_fill

            buffer.seek(0)
            st.download_button(
                label="📥 Export to Excel",
                data=buffer,
                file_name=f"QVM_Quality_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary"
            )
        
        # Add clarification about Grid ID
        st.info(
            "📍 **Grid ID**: Position on the panel quarter — "
            "11–14 = Upper Left quarter, "
            "21–24 = Lower Left quarter, "
            "31–34 = Lower Right quarter, "
            "41–44 = Upper Right quarter. "
            "First digit = quarter, second digit = point (1–4). "
            "All measurements in **microns (µm)**."
        )
        
        # --- Display Interactive Dataframe ---
        styled_df = display_df.style.apply(
            self._highlight_annular_ring,
            col_name=annular_col,
            threshold=threshold,
            axis=1
        )
        
        # Apply custom formatting for 3 decimals
        format_dict = {}
        for col in display_df.columns:
            if display_df[col].dtype in ['float64', 'float32', 'int64', 'int32']:
                format_dict[col] = self.format_to_3_decimals
        
        if format_dict:
            styled_df = styled_df.format(format_dict)
        
        st.dataframe(styled_df, use_container_width=True)

    @staticmethod
    def _highlight_annular_ring(row, col_name, threshold):
        """
        Styling function to highlight rows with low annular ring.
        
        Args:
            row: DataFrame row
            col_name: Name of annular ring column
            threshold: Failure threshold
            
        Returns:
            List of CSS styles for each cell in the row
        """
        if col_name not in row.index:
            return [''] * len(row)
        
        value = row[col_name]
        if pd.isna(value):
            return [''] * len(row)
        
        # Highlight row in light red if value is below threshold
        if value < threshold:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)
