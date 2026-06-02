"""
Quality Control View - Statistical summary and annular ring analysis
Extracted from app.py for modularity and reusability.
"""

import logging
import streamlit as st
import pandas as pd
from io import BytesIO
import openpyxl
from openpyxl.styles import PatternFill
from openpyxl.drawing.image import Image as XLImage

from src.views.base import BaseView
from src.utils import convert_to_microns


logger = logging.getLogger(__name__)


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
            # Guard: skip the writer entirely if there is nothing to export.
            # An empty workbook causes openpyxl to raise IndexError on close.
            _has_data = filtered_df is not None and not filtered_df.empty
            if not _has_data:
                st.download_button(
                    label="📥 Export to Excel",
                    data=buffer,
                    file_name="QVM_Quality_Report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    disabled=True,
                )
            else:
              with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                try:
                  if is_via_to_pad:
                    _region_map = {'1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'}

                    # ----------------------------------------------------------
                    # Matplotlib-based chart helpers (no kaleido / no subprocess)
                    # ----------------------------------------------------------
                    import matplotlib
                    matplotlib.use('Agg')   # non-interactive backend — safe in server env
                    import matplotlib.pyplot as plt
                    import matplotlib.patches as mpatches
                    import numpy as _np

                    _GRID_POS = {
                        '11': (1, 4), '12': (1, 3), '13': (2, 3), '14': (2, 4),
                        '21': (1, 2), '22': (1, 1), '23': (2, 1), '24': (2, 2),
                        '31': (3, 2), '32': (3, 1), '33': (4, 1), '34': (4, 2),
                        '41': (3, 4), '42': (3, 3), '43': (4, 3), '44': (4, 4),
                    }

                    # 12 cm at 96 dpi = 12/2.54 * 96 ≈ 454 px
                    _PANEL_PX = 454

                    def _buf_to_xl_image(buf: BytesIO, width_px: int, height_px: int) -> XLImage:
                        xl_img = XLImage(buf)
                        xl_img.width  = width_px
                        xl_img.height = height_px
                        return xl_img

                    def _mpl_bullseye(df_chart, settings, size_in: float = 6.5) -> XLImage:
                        """DX vs DY scatter with concentric tolerance rings (matplotlib)."""
                        col_names = settings.get('COLUMN_NAMES', {})
                        vtp_cfg   = settings.get('VTP_REGISTRATION', {})
                        dx_col = col_names.get('x_distance', 'Shift (DX)')
                        dy_col = col_names.get('y_distance', 'Shift (DY)')
                        sc_col = col_names.get('ptv_distance', 'PtV Distance')
                        grid_col = col_names.get('grid_id', 'Grid ID')

                        r_exc  = float(vtp_cfg.get('ring_exceptional_um', 2.5))
                        r_xll  = float(vtp_cfg.get('ring_excellent_um',   5.0))
                        r_good = float(vtp_cfg.get('ring_good_um',        7.5))
                        r_acc  = float(vtp_cfg.get('ring_acceptable_um', 10.0))

                        work = df_chart[[dx_col, dy_col, sc_col, grid_col]].dropna().copy()
                        work['dx_um'] = work[dx_col] * 1000
                        work['dy_um'] = work[dy_col] * 1000
                        work['sc_um'] = work[sc_col] * 1000

                        def _color(v):
                            if v <= r_exc:  return '#3498db'
                            if v <= r_xll:  return '#1e7e3a'
                            if v <= r_good: return '#2ecc71'
                            if v <= r_acc:  return '#e67e22'
                            return '#e74c3c'

                        work['c'] = work['sc_um'].apply(_color)

                        fig, ax = plt.subplots(figsize=(size_in, size_in), dpi=120)
                        ax.set_facecolor('#f8f8f8')
                        fig.patch.set_facecolor('white')

                        spread = r_acc + 2.0
                        for r, lc, ls in [
                            (r_exc,  '#3498db', '-'),
                            (r_xll,  '#1e7e3a', '--'),
                            (r_good, '#2ecc71', '--'),
                            (r_acc,  '#e74c3c', ':'),
                        ]:
                            ax.add_patch(mpatches.Circle((0, 0), r, fill=False,
                                                          edgecolor=lc, linestyle=ls, linewidth=1.5, zorder=2))
                        ax.axhline(0, color='gray', linewidth=0.8, zorder=1)
                        ax.axvline(0, color='gray', linewidth=0.8, zorder=1)

                        ax.scatter(work['dx_um'], work['dy_um'],
                                   c=work['c'], s=80, zorder=5, edgecolors='#333', linewidths=0.5)
                        for _, row in work.iterrows():
                            ax.annotate(str(int(row[grid_col])),
                                        (row['dx_um'], row['dy_um']),
                                        textcoords='offset points', xytext=(4, 4),
                                        fontsize=7, color='#222')

                        ax.set_xlim(-spread, spread)
                        ax.set_ylim(-spread, spread)
                        ax.set_aspect('equal')
                        ax.set_xlabel('DX (µm)', fontsize=9)
                        ax.set_ylabel('DY (µm)', fontsize=9)
                        ax.set_title('DX vs DY Registration (SC tolerance rings)', fontsize=10, fontweight='bold')

                        legend_els = [
                            mpatches.Patch(color='#3498db', label=f'≤{r_exc} µm exceptional'),
                            mpatches.Patch(color='#1e7e3a', label=f'≤{r_xll} µm excellent'),
                            mpatches.Patch(color='#2ecc71', label=f'≤{r_good} µm good'),
                            mpatches.Patch(color='#e67e22', label=f'≤{r_acc} µm acceptable'),
                            mpatches.Patch(color='#e74c3c', label=f'>{r_acc} µm fail'),
                        ]
                        ax.legend(handles=legend_els, fontsize=7, loc='upper right',
                                  framealpha=0.85, edgecolor='#aaa')

                        px = int(size_in * 120)
                        buf = BytesIO()
                        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                        plt.close(fig)
                        buf.seek(0)
                        return _buf_to_xl_image(buf, px, px)

                    def _mpl_quiver(df_chart, settings, multiplier: float = 100,
                                    size_in: float = 6.5) -> XLImage:
                        """Quiver/vector plot with pattern-colour arrows (matplotlib)."""
                        col_names = settings.get('COLUMN_NAMES', {})
                        dx_col   = col_names.get('x_distance', 'Shift (DX)')
                        dy_col   = col_names.get('y_distance', 'Shift (DY)')
                        grid_col = col_names.get('grid_id', 'Grid ID')

                        MIN_LEN = 0.05
                        EXP_THR = 0.5
                        TWI_DOT = 0.2
                        TWI_MAG = 10.0

                        df_q = df_chart.dropna(subset=[grid_col, dx_col, dy_col]).copy()
                        df_q[grid_col] = df_q[grid_col].astype(int).astype(str)

                        fig, ax = plt.subplots(figsize=(size_in, size_in), dpi=120)
                        ax.set_facecolor('#f8f8f8')
                        fig.patch.set_facecolor('white')

                        # Draw grid lines
                        for v in [1.5, 2.5, 3.5]:
                            ax.axhline(v, color='#cccccc', linewidth=0.6)
                            ax.axvline(v, color='#cccccc', linewidth=0.6)

                        for _, row in df_q.iterrows():
                            gid = str(row[grid_col])
                            pos = _GRID_POS.get(gid)
                            if pos is None:
                                continue
                            x, y = pos
                            dx_um = float(row[dx_col]) * 1000
                            dy_um = float(row[dy_col]) * 1000
                            mag   = _np.sqrt(dx_um**2 + dy_um**2)
                            dx_s  = dx_um * multiplier * 0.001
                            dy_s  = dy_um * multiplier * 0.001
                            arr   = _np.sqrt(dx_s**2 + dy_s**2)
                            if arr > 0 and arr < MIN_LEN:
                                sc = MIN_LEN / arr
                                dx_s *= sc; dy_s *= sc

                            pos_x = x - 2.5; pos_y = y - 2.5
                            pos_m = _np.sqrt(pos_x**2 + pos_y**2)
                            if pos_m > 0:
                                pxn, pyn = pos_x / pos_m, pos_y / pos_m
                            else:
                                pxn, pyn = 0.0, 0.0
                            em = _np.sqrt(dx_s**2 + dy_s**2)
                            exn = dx_s / em if em > 0 else 0
                            eyn = dy_s / em if em > 0 else 0
                            dot = exn * pxn + eyn * pyn

                            if abs(dot) > EXP_THR:
                                color = '#ff5000' if dot > 0 else '#00d2d2'
                            elif abs(dot) < TWI_DOT and mag > TWI_MAG:
                                color = '#ffd700'
                            else:
                                color = '#6496ff'

                            ax.annotate('', xy=(x + dx_s, y + dy_s), xytext=(x, y),
                                        arrowprops=dict(arrowstyle='->', color=color,
                                                        lw=2.0, mutation_scale=15))
                            ax.text(x, y, gid, fontsize=7, ha='center', va='center',
                                    color='#333', zorder=10)

                        ax.set_xlim(0.5, 4.5)
                        ax.set_ylim(0.5, 4.5)
                        ax.set_aspect('equal')
                        ax.set_xticks([1, 2, 3, 4])
                        ax.set_yticks([1, 2, 3, 4])
                        ax.set_xticklabels(['Col 1', 'Col 2', 'Col 3', 'Col 4'], fontsize=8)
                        ax.set_yticklabels(['Row 1', 'Row 2', 'Row 3', 'Row 4'], fontsize=8)
                        ax.set_title(f'Registration Quiver Plot (×{multiplier} magnification)',
                                     fontsize=10, fontweight='bold')

                        legend_els = [
                            mpatches.Patch(color='#ff5000', label='Expansion'),
                            mpatches.Patch(color='#00d2d2', label='Contraction'),
                            mpatches.Patch(color='#ffd700', label='Twist'),
                            mpatches.Patch(color='#6496ff', label='Offset'),
                        ]
                        ax.legend(handles=legend_els, fontsize=8, loc='upper right',
                                  framealpha=0.85, edgecolor='#aaa')

                        px = int(size_in * 120)
                        buf = BytesIO()
                        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
                        plt.close(fig)
                        buf.seek(0)
                        return _buf_to_xl_image(buf, px, px)

                    def _mpl_panel_map(df_chart, settings) -> XLImage:
                        """Draw the 4×4 panel location map with Grid IDs and quarter labels.

                        Each cell shows its Grid ID. Quarter regions (UL/LL/LR/UR) are
                        colour-banded. Points are coloured by SC value using the same
                        traffic-light palette as the bullseye. Size: 12 cm × 12 cm.
                        """
                        col_names = settings.get('COLUMN_NAMES', {})
                        vtp_cfg   = settings.get('VTP_REGISTRATION', {})
                        sc_col    = col_names.get('ptv_distance', 'PtV Distance')
                        grid_col  = col_names.get('grid_id', 'Grid ID')

                        r_exc  = float(vtp_cfg.get('ring_exceptional_um', 2.5))
                        r_xll  = float(vtp_cfg.get('ring_excellent_um',   5.0))
                        r_good = float(vtp_cfg.get('ring_good_um',        7.5))
                        r_acc  = float(vtp_cfg.get('ring_acceptable_um', 10.0))

                        def _dot_color(v):
                            if v <= r_exc:  return '#3498db'
                            if v <= r_xll:  return '#1e7e3a'
                            if v <= r_good: return '#2ecc71'
                            if v <= r_acc:  return '#e67e22'
                            return '#e74c3c'

                        # Build lookup: grid_id → sc_um
                        sc_map = {}
                        if sc_col in df_chart.columns and grid_col in df_chart.columns:
                            for _, row in df_chart[[grid_col, sc_col]].dropna().iterrows():
                                sc_map[str(int(row[grid_col]))] = float(row[sc_col]) * 1000

                        # Quarter background colours (very light)
                        _quarter_bg = {
                            '1': '#e8f4f8',  # UL — light blue
                            '2': '#fef9e7',  # LL — light yellow
                            '3': '#eafaf1',  # LR — light green
                            '4': '#fdf2f8',  # UR — light pink
                        }
                        _quarter_label = {
                            '1': 'UL', '2': 'LL', '3': 'LR', '4': 'UR'
                        }

                        size_in = _PANEL_PX / 96  # convert px → inches for dpi=96
                        fig, ax = plt.subplots(figsize=(size_in, size_in), dpi=96)
                        fig.patch.set_facecolor('white')
                        ax.set_facecolor('white')
                        ax.set_xlim(0.5, 4.5)
                        ax.set_ylim(0.5, 4.5)
                        ax.set_aspect('equal')
                        ax.invert_yaxis()   # row 1 at top

                        # Draw quarter background rectangles
                        _quarter_extents = {
                            '1': (0.5, 0.5, 2, 2),  # UL: x0,y0,w,h  (plot coords after invert)
                            '4': (2.5, 0.5, 2, 2),  # UR
                            '2': (0.5, 2.5, 2, 2),  # LL
                            '3': (2.5, 2.5, 2, 2),  # LR
                        }
                        for q, (x0, y0, w, h) in _quarter_extents.items():
                            ax.add_patch(mpatches.FancyBboxPatch(
                                (x0, y0), w, h,
                                boxstyle='square,pad=0',
                                facecolor=_quarter_bg[q],
                                edgecolor='#999999', linewidth=0.8,
                                zorder=1
                            ))
                            ax.text(x0 + w / 2, y0 + h / 2,
                                    _quarter_label[q],
                                    ha='center', va='center',
                                    fontsize=22, fontweight='bold',
                                    color='#cccccc', zorder=2)

                        # Draw grid lines
                        for v in [1.5, 2.5, 3.5]:
                            ax.axhline(v, color='#aaaaaa', linewidth=0.6, zorder=3)
                            ax.axvline(v, color='#aaaaaa', linewidth=0.6, zorder=3)

                        # Draw each site: coloured dot + Grid ID label
                        for gid, (px_x, px_y) in _GRID_POS.items():
                            sc_val = sc_map.get(gid)
                            dot_c  = _dot_color(sc_val) if sc_val is not None else '#dddddd'
                            ax.scatter(px_x, px_y, s=220, c=dot_c,
                                       edgecolors='#333333', linewidths=0.8, zorder=5)
                            ax.text(px_x, px_y, gid,
                                    ha='center', va='center',
                                    fontsize=8, fontweight='bold',
                                    color='white', zorder=6)

                        # Axis labels
                        ax.set_xticks([1, 2, 3, 4])
                        ax.set_yticks([1, 2, 3, 4])
                        ax.set_xticklabels(['Col 1', 'Col 2', 'Col 3', 'Col 4'], fontsize=7)
                        ax.set_yticklabels(['Row 1', 'Row 2', 'Row 3', 'Row 4'], fontsize=7)
                        ax.set_title('Panel Location Map', fontsize=9, fontweight='bold', pad=6)
                        ax.tick_params(length=0)
                        for spine in ax.spines.values():
                            spine.set_edgecolor('#999999')

                        # Legend
                        legend_els = [
                            mpatches.Patch(color='#3498db', label=f'≤{r_exc} µm'),
                            mpatches.Patch(color='#1e7e3a', label=f'≤{r_xll} µm'),
                            mpatches.Patch(color='#2ecc71', label=f'≤{r_good} µm'),
                            mpatches.Patch(color='#e67e22', label=f'≤{r_acc} µm'),
                            mpatches.Patch(color='#e74c3c', label=f'>{r_acc} µm'),
                            mpatches.Patch(color='#dddddd', label='No data'),
                        ]
                        ax.legend(handles=legend_els, fontsize=6, loc='lower right',
                                  framealpha=0.9, edgecolor='#aaa', title='SC', title_fontsize=6)

                        buf = BytesIO()
                        fig.savefig(buf, format='png', dpi=96, bbox_inches='tight')
                        plt.close(fig)
                        buf.seek(0)
                        return _buf_to_xl_image(buf, _PANEL_PX, _PANEL_PX)

                    # ----------------------------------------------------------
                    def _add_chart_to_sheet(ws, df_for_chart, settings, sheet_label: str):
                        """Embed bullseye scatter below data table."""
                        anchor = f'A{len(df_for_chart) + 4}'
                        try:
                            xl_img = _mpl_bullseye(df_for_chart, settings)
                            ws.add_image(xl_img, anchor)
                        except Exception as e:
                            logger.warning("Bullseye embed failed for %s: %s", sheet_label, e, exc_info=True)
                            st.sidebar.warning(f"⚠️ Could not embed scatter in '{sheet_label}': {e}")

                    def _add_panel_map_to_sheet(ws, df_for_chart, settings, sheet_label: str):
                        """Embed panel map at top-right of data table (column H, row 1)."""
                        try:
                            xl_img = _mpl_panel_map(df_for_chart, settings)
                            ws.add_image(xl_img, 'H1')
                        except Exception as e:
                            logger.warning("Panel map embed failed for %s: %s", sheet_label, e, exc_info=True)
                            st.sidebar.warning(f"⚠️ Could not embed panel map in '{sheet_label}': {e}")

                    def _add_quiver_to_sheet(ws, df_for_chart, settings, sheet_label: str,
                                            scatter_height_px: int = 700):
                        """Embed quiver plot to the right of the scatter (column J)."""
                        anchor_row = len(df_for_chart) + 4
                        anchor = f'J{anchor_row}'
                        try:
                            xl_img = _mpl_quiver(df_for_chart, settings, multiplier=100)
                            ws.add_image(xl_img, anchor)
                        except Exception as e:
                            logger.warning("Quiver embed failed for %s: %s", sheet_label, e, exc_info=True)
                            st.sidebar.warning(f"⚠️ Could not embed quiver in '{sheet_label}': {e}")

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
                            ws = writer.sheets[sheet_name]
                            _add_panel_map_to_sheet(ws, side_df_raw, self.settings, sheet_name)
                            _add_chart_to_sheet(ws, side_df_raw, self.settings, sheet_name)
                            _add_quiver_to_sheet(ws, side_df_raw, self.settings, sheet_name)
                            report_frames.append(_make_report_sheet(side_display, side_vals))
                        # Combined Report sheet
                        report_df = pd.concat(report_frames, ignore_index=True)
                        report_df.to_excel(writer, sheet_name='Report', index=False)
                    else:
                        # Single side
                        _make_measurement_sheet(display_df, _side_series).to_excel(
                            writer, sheet_name='Via to Pad', index=False)
                        ws = writer.sheets['Via to Pad']
                        _add_panel_map_to_sheet(ws, filtered_df, self.settings, 'Via to Pad')
                        _add_chart_to_sheet(ws, filtered_df, self.settings, 'Via to Pad')
                        _add_quiver_to_sheet(ws, filtered_df, self.settings, 'Via to Pad')
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

                except Exception as _exc:
                    # If anything went wrong before a sheet was written, add a
                    # fallback sheet so openpyxl can close cleanly (no IndexError).
                    logger.warning("Excel export error — writing fallback sheet: %s", _exc, exc_info=True)
                    try:
                        filtered_df.to_excel(writer, sheet_name='Data', index=False)
                    except Exception:
                        pd.DataFrame({'error': [str(_exc)]}).to_excel(
                            writer, sheet_name='Data', index=False)
                    st.warning(f"⚠️ Excel export encountered an issue: {_exc}")

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
