"""
Quality Control View — statistical summary, data table, and Excel export.
"""

import logging
import re
from io import BytesIO

import pandas as pd
import streamlit as st

from src.views.base import BaseView
from src.utils import convert_to_microns
from src.excel_export import write_vtp_excel, write_ptv_excel

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
        ptv_dist_col = col_names.get('ptv_distance', 'PtV Distance')

        # --- Build display dataframe ---
        # Both processes keep a clean, identical column set; the only difference
        # is the distance metric: VtP uses 'VtP Distance (SC)', PtV uses the
        # native 'PtV Distance'. Coord. X/Y, Pad/Via Pts., Annular Ring, and the
        # Process tag are intentionally excluded from both screen and export.
        distance_col = sc_col if is_via_to_pad else ptv_dist_col
        keep = [grid_id_col, via_diam_col, pad_diam_col, dx_col, dy_col, distance_col]
        display_df = filtered_df[[c for c in keep if c in filtered_df.columns]].copy()

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
                st.write('Pad-to-Via export: Grid ID | Via Ø | Pad Ø | DX | DY | PtV Distance  (µm)')
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
        parse_warnings = st.session_state.get('parse_warnings', [])
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            try:
                if is_via_to_pad:
                    write_vtp_excel(writer, display_df, filtered_df,
                                    self.settings, meta, grid_id_col,
                                    warnings=parse_warnings)
                else:
                    write_ptv_excel(writer, display_df, filtered_df,
                                    self.settings, meta, grid_id_col,
                                    warnings=parse_warnings)
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
            file_name=self._build_filename(filtered_df, is_via_to_pad, meta),
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            type='primary',
        )

    @staticmethod
    def _safe_token(value: str) -> str:
        value = re.sub(r'\s+', '-', str(value).strip())
        value = re.sub(r'[^A-Za-z0-9._-]', '', value)
        return value.strip('-_')

    @classmethod
    def _build_filename(cls, filtered_df: pd.DataFrame, is_via_to_pad: bool, meta: dict) -> str:
        process_token = "VTP" if is_via_to_pad else "PTV"
        if 'Process' in filtered_df.columns and not filtered_df.empty:
            proc_vals = sorted({str(v).strip() for v in filtered_df['Process'].dropna().tolist() if str(v).strip()})
            if len(proc_vals) == 1:
                p = proc_vals[0].lower()
                if 'via to pad' in p:
                    process_token = 'VTP'
                elif 'pad to via' in p:
                    process_token = 'PTV'
            elif len(proc_vals) > 1:
                process_token = 'MIXED'

        panel_token = None
        if 'Panel' in filtered_df.columns and not filtered_df.empty:
            panel_vals = sorted({str(v).strip() for v in filtered_df['Panel'].dropna().tolist()
                                 if str(v).strip() and str(v).strip().lower() != 'unknown'})
            if len(panel_vals) == 1:
                panel_token = f"P{panel_vals[0]}"
            elif len(panel_vals) > 1:
                panel_token = 'PMulti'
        if panel_token is None:
            panel_val = str(meta.get('panel', '')).strip()
            if panel_val:
                panel_token = f"P{panel_val}"

        side_token = None
        if 'Side' in filtered_df.columns and not filtered_df.empty:
            side_vals = sorted({str(v).strip().upper() for v in filtered_df['Side'].dropna().tolist()
                                if str(v).strip() and str(v).strip().lower() != 'unknown'})
            if len(side_vals) == 1 and side_vals[0] in ('F', 'B'):
                side_token = side_vals[0]
            elif len(side_vals) > 1:
                side_token = 'FB'

        parts = ['QVM', process_token]
        if panel_token:
            parts.append(panel_token)
        if side_token:
            parts.append(side_token)

        build_up_token = None
        if 'Build Up' in filtered_df.columns and not filtered_df.empty:
            bu_vals = sorted({str(v).strip() for v in filtered_df['Build Up'].dropna().tolist()
                              if str(v).strip() and str(v).strip().lower() != 'unknown'})
            if len(bu_vals) == 1:
                build_up_token = bu_vals[0]
            elif len(bu_vals) > 1:
                build_up_token = 'BUMulti'
        if build_up_token is None:
            build_up = str(meta.get('build_up', '')).strip()
            if build_up:
                build_up_token = build_up

        lot = str(meta.get('lot_number', '')).strip()
        if build_up_token:
            upper_bu = build_up_token.upper()
            if upper_bu.startswith('BU-') or upper_bu == 'BUMULTI':
                bu_token = build_up_token
            else:
                bu_token = f"BU-{build_up_token}"
            parts.append(bu_token)
        if lot:
            lot_lower = lot.lower()
            lot_token = lot if lot_lower.startswith('lot-') else f"Lot-{lot}"
            parts.append(lot_token)

        safe_parts = [cls._safe_token(p) for p in parts if cls._safe_token(p)]
        return "_".join(safe_parts) + ".xlsx"

    @staticmethod
    def _highlight_annular_ring(row, col_name: str, threshold: float):
        """Row styler: light-red background when annular ring < threshold."""
        if col_name not in row.index or pd.isna(row[col_name]):
            return [''] * len(row)
        if row[col_name] < threshold:
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)
