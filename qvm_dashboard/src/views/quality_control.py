"""
Quality Control View — statistical summary, data table, and Excel export.
"""

import logging
from io import BytesIO

import pandas as pd
import streamlit as st
from openpyxl.styles import PatternFill

from src.views.base import BaseView
from src.utils import convert_to_microns
from src.excel_export import write_vtp_excel

logger = logging.getLogger(__name__)


class QualityControlView(BaseView):
    """Statistical summary, failure highlighting, and Excel export."""

    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """Render the Quality Control analysis view.

        Kwargs:
            is_via_to_pad (bool): true when rendering Via-to-Pad data
            meta (dict): sidebar metadata (project_name, panel, process, …)
        """
        is_via_to_pad = kwargs.get('is_via_to_pad', False)
        meta = kwargs.get('meta', {})

        col_names    = self.col_names
        annular_col  = col_names.get('annular_ring', 'Annular Ring')
        threshold    = self.tolerances.get('annular_ring_min', 0.0)
        grid_id_col  = col_names.get('grid_id', 'Grid ID')
        via_diam_col = col_names.get('inner_diameter', 'Via Parameter')
        pad_diam_col = col_names.get('outer_diameter', 'Pad Diameter')
        dx_col       = col_names.get('x_distance', 'Shift (DX)')
        dy_col       = col_names.get('y_distance', 'Shift (DY)')
        sc_col       = col_names.get('total_shift', 'SC')

        # --- Build display dataframe ---
        if is_via_to_pad:
            vtp_keep = [c for c in [grid_id_col, via_diam_col, pad_diam_col,
                                    dx_col, dy_col, sc_col]
                        if c in filtered_df.columns]
            display_df = filtered_df[vtp_keep].copy()
        else:
            display_df = filtered_df.drop(
                columns=[c for c in ['Panel', 'Side'] if c in filtered_df.columns]
            ).copy()

        measurement_cols = [pad_diam_col, via_diam_col, sc_col, dx_col, dy_col,
                            col_names.get('ptv_distance', 'PtV Distance'), annular_col]
        display_df = convert_to_microns(display_df, measurement_cols)

        if grid_id_col in display_df.columns:
            display_df = display_df.sort_values(by=grid_id_col, ascending=True)

        # --- Statistical Summary ---
        st.subheader("📊 Statistical Summary")
        self._render_stats(display_df, annular_col, threshold, grid_id_col)
        st.markdown('---')

        # --- Excel Export ---
        col_left, col_right = st.columns([3, 1])
        with col_left:
            if is_via_to_pad:
                st.write('Via-to-Pad export: Grid ID | Via Ø | Pad Ø | DX | DY | SC  (µm)')
            else:
                st.write(f'Highlighting rows where {annular_col} < {threshold}')
        with col_right:
            self._render_export_button(
                filtered_df, display_df, is_via_to_pad,
                annular_col, threshold, grid_id_col, meta,
            )

        # --- Grid ID legend ---
        st.info(
            '📍 **Grid ID**: Position on the panel quarter — '
            '11–14 = Upper Left quarter, '
            '21–24 = Lower Left quarter, '
            '31–34 = Lower Right quarter, '
            '41–44 = Upper Right quarter. '
            'First digit = quarter, second digit = point (1–4). '
            'All measurements in **microns (µm)**.'
        )

        # --- Magnitude explanation expander ---
        if is_via_to_pad:
            with st.expander("ℹ️ How are SC magnitude and Quiver magnitude calculated?"):
                st.markdown("""
**VtP Distance (SC)** — shown in the data table above — is read directly from the
QVM instrument. It is the measured centre-to-centre distance between the Via circle
and the Pad circle.

> **Formula:** Instrument scalar (no calculation) — converted from mm to µm for display.

---

**Quiver magnitude** — used to colour and scale arrows in the Pattern Hunter (Analytics tab)
— is reconstructed from the two shift components:

> **Formula:** magnitude (µm) = √(DX² + DY²) × 1,000

| Symbol | Column | Meaning |
|--------|--------|---------|
| DX | Shift (DX) | Horizontal displacement of Via from Pad centre (mm) |
| DY | Shift (DY) | Vertical displacement of Via from Pad centre (mm) |

---

Both quantities represent the same physical shift. Small differences can appear because
SC is the hardware measurement while the quiver magnitude is derived from the X/Y
component breakdown.
                """)

        # --- Interactive dataframe ---
        styled = display_df.style.apply(
            self._highlight_annular_ring, col_name=annular_col,
            threshold=threshold, axis=1,
        )
        fmt = {col: self.format_to_3_decimals
               for col in display_df.columns
               if display_df[col].dtype in ('float64', 'float32', 'int64', 'int32')}
        if fmt:
            styled = styled.format(fmt)
        st.dataframe(styled, use_container_width=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_stats(self, display_df: pd.DataFrame, annular_col: str,
                      threshold: float, grid_id_col: str) -> None:
        summary_cols = st.columns(5)
        if annular_col not in display_df.columns:
            return

        ar_min = display_df[annular_col].min()
        ar_max = display_df[annular_col].max()
        ar_mean = display_df[annular_col].mean()
        ar_std  = display_df[annular_col].std()
        fail_count = int((display_df[annular_col] < threshold).sum())
        fail_pct = fail_count / len(display_df) * 100 if len(display_df) > 0 else 0.0
        worst_idx  = display_df[annular_col].idxmin()
        worst_grid = (display_df.loc[worst_idx, grid_id_col]
                      if grid_id_col in display_df.columns else 'N/A')

        summary_cols[0].metric('Min Annular Ring', f'{ar_min:.3f} µm',
                               delta=f'{ar_min - threshold:.3f}' if ar_min < threshold else None,
                               delta_color='inverse')
        summary_cols[1].metric('Max Annular Ring', f'{ar_max:.3f} µm')
        summary_cols[2].metric('Mean ± StdDev', f'{ar_mean:.3f} ± {ar_std:.3f} µm')
        summary_cols[3].metric('Worst Point', f'Grid {worst_grid}', f'{ar_min:.3f} µm')
        summary_cols[4].metric(
            'Failures', f'{fail_count} ({fail_pct:.1f}%)',
            delta=f'{fail_count} points' if fail_count > 0 else '✓ All Pass',
            delta_color='inverse' if fail_count > 0 else 'off',
        )

    def _render_export_button(self, filtered_df: pd.DataFrame, display_df: pd.DataFrame,
                              is_via_to_pad: bool, annular_col: str, threshold: float,
                              grid_id_col: str, meta: dict) -> None:
        buffer = BytesIO()

        if filtered_df is None or filtered_df.empty:
            st.download_button(
                label='📥 Export to Excel',
                data=buffer,
                file_name='QVM_Quality_Report.xlsx',
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                type='primary', disabled=True,
            )
            return

        import openpyxl  # noqa: F401 — ensure engine available
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            try:
                if is_via_to_pad:
                    write_vtp_excel(writer, display_df, filtered_df,
                                    self.settings, meta, grid_id_col)
                else:
                    self._write_ptv_excel(writer, display_df, annular_col, threshold)
            except Exception as exc:
                logger.warning('Excel export error — writing fallback sheet: %s',
                               exc, exc_info=True)
                try:
                    filtered_df.to_excel(writer, sheet_name='Data', index=False)
                except Exception:
                    pd.DataFrame({'error': [str(exc)]}).to_excel(
                        writer, sheet_name='Data', index=False)
                st.warning(f'⚠️ Excel export encountered an issue: {exc}')

        buffer.seek(0)
        st.download_button(
            label='📥 Export to Excel',
            data=buffer,
            file_name=f"QVM_Quality_Report_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            type='primary',
        )

    @staticmethod
    def _write_ptv_excel(writer: pd.ExcelWriter, display_df: pd.DataFrame,
                         annular_col: str, threshold: float) -> None:
        """Pad-to-Via export: data table with conditional red row highlighting."""
        export_df = display_df.dropna(axis=1, how='all').copy()
        export_df.to_excel(writer, sheet_name='QVM Data', index=False)

        worksheet = writer.sheets['QVM Data']
        red_fill = PatternFill(start_color='FFCCCC', end_color='FFCCCC', fill_type='solid')

        if annular_col in export_df.columns:
            for row_idx, value in enumerate(export_df[annular_col], start=2):
                if value < threshold:
                    for col_idx in range(1, len(export_df.columns) + 1):
                        worksheet.cell(row=row_idx, column=col_idx).fill = red_fill

    @staticmethod
    def _highlight_annular_ring(row, col_name: str, threshold: float):
        """Row styler: light-red background when annular ring < threshold."""
        if col_name not in row.index or pd.isna(row[col_name]):
            return [''] * len(row)
        if row[col_name] < threshold:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)
