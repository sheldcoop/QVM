"""
Quality Control View — statistical summary, data table, and Excel export.
"""

import logging
import re
from io import BytesIO

import pandas as pd
import streamlit as st

from src.views.base import BaseView
from src.display_frame import build_display_frame
from src.utils import is_via_to_pad as is_via_to_pad_mask
from src.excel_export import write_unified_excel

logger = logging.getLogger(__name__)


_EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@st.cache_data(max_entries=8, show_spinner="Building Excel report…")
def build_workbook(
    export_df: pd.DataFrame, settings: dict, meta: dict, warnings: list
) -> tuple:
    """Render the export workbook to bytes. Returns ``(data, error_message)``.

    Memoised because Streamlit reruns the whole script on every widget
    interaction, and this is by far the most expensive thing the page does:
    each Analytics sheet renders four Plotly figures to PNG through kaleido,
    and there is one such sheet per process per Build Up. Without the cache
    that work was repeated on every nav click, whether or not anyone
    downloaded the file.

    Errors are returned rather than raised so a failed export still yields a
    downloadable workbook containing the raw data.
    """
    buffer = BytesIO()
    error = None
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        try:
            write_unified_excel(
                writer,
                export_df,
                settings,
                meta,
                warnings=warnings,
                warn=st.sidebar.warning,
            )
        except Exception as exc:
            logger.warning(
                "Excel export error — writing fallback sheet: %s", exc, exc_info=True
            )
            error = str(exc)
            try:
                export_df.to_excel(writer, sheet_name="Data", index=False)
            except Exception:
                pd.DataFrame({"error": [error]}).to_excel(
                    writer, sheet_name="Data", index=False
                )
    return buffer.getvalue(), error


def annular_stats(values: pd.Series, threshold: float) -> dict | None:
    """Summarise a column of Annular Ring measurements (µm).

    Returns None when there is nothing to summarise, so the caller can skip the
    panel entirely rather than render empty tiles. ``threshold`` is the µm
    breakout limit from ``TOLERANCES.annular_ring_min``; rows below it are
    counted as failures.
    """
    values = values.dropna()
    if values.empty:
        return None
    fail_count = int((values < threshold).sum())
    return {
        "min": float(values.min()),
        "max": float(values.max()),
        "mean": float(values.mean()),
        "std": float(values.std()),
        "fail_count": fail_count,
        "fail_pct": fail_count / len(values) * 100,
        "worst_index": values.idxmin(),
    }


class QualityControlView(BaseView):
    """Statistical summary, failure highlighting, and Excel export."""

    def render(self, filtered_df: pd.DataFrame, **kwargs) -> None:
        """Render the Quality Control analysis view.

        Kwargs:
            is_via_to_pad (bool): true when rendering Via-to-Pad data
            meta (dict): sidebar metadata (project_name, panel, process, …)
        """
        is_via_to_pad = kwargs.get("is_via_to_pad", False)
        meta = kwargs.get("meta", {})
        export_df = kwargs.get("export_df", filtered_df)

        cols = self.cols("annular_ring", "grid_id")
        annular_col = cols["annular_ring"]
        grid_id_col = cols["grid_id"]
        threshold = self.tolerances.get("annular_ring_min", 0.0)

        # Shared with every Excel measurement sheet — see src/display_frame.py.
        # Coord. X/Y, Pad/Via Pts. and the Process tag stay out of both.
        display_df = build_display_frame(
            filtered_df, self.settings, is_via_to_pad=is_via_to_pad
        )

        # --- Statistical Summary ---
        st.subheader("📊 Statistical Summary")
        self._render_stats(display_df, annular_col, threshold, grid_id_col)
        st.markdown("---")

        # --- Excel Export ---
        col_left, col_right = st.columns([3, 1])
        with col_left:
            st.write(
                "One workbook export: separate Via-to-Pad and Pad-to-Via sheets for current Build Up, Panel, and Side scope."
            )
        with col_right:
            self._render_export_button(filtered_df, export_df, is_via_to_pad, meta)

        # --- Grid ID legend ---
        st.info(
            "📍 **Grid ID**: Position on the panel quarter — "
            "11–14 = Upper Left quarter, "
            "21–24 = Lower Left quarter, "
            "31–34 = Lower Right quarter, "
            "41–44 = Upper Right quarter. "
            "First digit = quarter, second digit = point (1–4). "
            "All measurements in **microns (µm)**."
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
            self._highlight_annular_ring,
            col_name=annular_col,
            threshold=threshold,
            axis=1,
        )
        fmt: dict = {
            col: self.format_to_3_decimals
            for col in display_df.columns
            if col != grid_id_col
            and display_df[col].dtype in ("float64", "float32", "int64", "int32")
        }
        if fmt:
            styled = styled.format(fmt)
        st.dataframe(styled, width="stretch")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render_stats(
        self,
        display_df: pd.DataFrame,
        annular_col: str,
        threshold: float,
        grid_id_col: str,
    ) -> None:
        """Render the five Annular Ring summary tiles."""
        stats = (
            annular_stats(display_df[annular_col], threshold)
            if annular_col in display_df.columns
            else None
        )
        if stats is None:
            st.info("Annular Ring is unavailable for this selection.")
            return

        worst_grid = (
            display_df.loc[stats["worst_index"], grid_id_col]
            if grid_id_col in display_df.columns
            else "N/A"
        )
        fail_count = stats["fail_count"]

        summary_cols = st.columns(5)
        summary_cols[0].metric(
            "Min Annular Ring",
            f"{stats['min']:.3f} µm",
            delta=(
                f"{stats['min'] - threshold:.3f}" if stats["min"] < threshold else None
            ),
            delta_color="inverse",
        )
        summary_cols[1].metric("Max Annular Ring", f"{stats['max']:.3f} µm")
        summary_cols[2].metric(
            "Mean ± StdDev", f"{stats['mean']:.3f} ± {stats['std']:.3f} µm"
        )
        summary_cols[3].metric(
            "Worst Point", f"Grid {worst_grid}", f"{stats['min']:.3f} µm"
        )
        summary_cols[4].metric(
            "Failures",
            f"{fail_count} ({stats['fail_pct']:.1f}%)",
            delta=f"{fail_count} points" if fail_count > 0 else "✓ All Pass",
            delta_color="inverse" if fail_count > 0 else "off",
        )

    def _render_export_button(
        self,
        filtered_df: pd.DataFrame,
        export_df: pd.DataFrame,
        is_via_to_pad: bool,
        meta: dict,
    ) -> None:
        if filtered_df is None or filtered_df.empty:
            st.download_button(
                label="📥 Export to Excel",
                data=b"",
                file_name="QVM_Quality_Report.xlsx",
                mime=_EXCEL_MIME,
                type="primary",
                disabled=True,
            )
            return

        data, error = build_workbook(
            export_df,
            self.settings,
            meta,
            st.session_state.get("parse_warnings", []),
        )
        if error:
            st.warning(f"⚠️ Excel export encountered an issue: {error}")

        st.download_button(
            label="📥 Export to Excel",
            data=data,
            file_name=self._build_filename(export_df, is_via_to_pad, meta),
            mime=_EXCEL_MIME,
            type="primary",
        )

    @staticmethod
    def _safe_token(value: str) -> str:
        value = re.sub(r"\s+", "-", str(value).strip())
        value = re.sub(r"[^A-Za-z0-9._-]", "", value)
        return value.strip("-_")

    @classmethod
    def _build_filename(
        cls, filtered_df: pd.DataFrame, is_via_to_pad: bool, meta: dict
    ) -> str:
        process_token = "VTP" if is_via_to_pad else "PTV"
        if "Process" in filtered_df.columns and not filtered_df.empty:
            vtp_rows = is_via_to_pad_mask(filtered_df)
            if vtp_rows.all():
                process_token = "VTP"
            elif not vtp_rows.any():
                process_token = "PTV"
            else:
                process_token = "MIXED"

        panel_token = None
        if "Panel" in filtered_df.columns and not filtered_df.empty:
            panel_vals = sorted(
                {
                    str(v).strip()
                    for v in filtered_df["Panel"].dropna().tolist()
                    if str(v).strip() and str(v).strip().lower() != "unknown"
                }
            )
            if len(panel_vals) == 1:
                panel_token = f"P{panel_vals[0]}"
            elif len(panel_vals) > 1:
                panel_token = "PMulti"
        if panel_token is None:
            panel_val = str(meta.get("panel", "")).strip()
            if panel_val:
                panel_token = f"P{panel_val}"

        side_token = None
        if "Side" in filtered_df.columns and not filtered_df.empty:
            side_vals = sorted(
                {
                    str(v).strip().upper()
                    for v in filtered_df["Side"].dropna().tolist()
                    if str(v).strip() and str(v).strip().lower() != "unknown"
                }
            )
            if len(side_vals) == 1 and side_vals[0] in ("F", "B"):
                side_token = side_vals[0]
            elif len(side_vals) > 1:
                side_token = "FB"

        parts = ["QVM", process_token]
        if panel_token:
            parts.append(panel_token)
        if side_token:
            parts.append(side_token)

        build_up_token = None
        if "Build Up" in filtered_df.columns and not filtered_df.empty:
            bu_vals = sorted(
                {
                    str(v).strip()
                    for v in filtered_df["Build Up"].dropna().tolist()
                    if str(v).strip() and str(v).strip().lower() != "unknown"
                }
            )
            if len(bu_vals) == 1:
                build_up_token = bu_vals[0]
            elif len(bu_vals) > 1:
                build_up_token = "BUMulti"
        if build_up_token is None:
            build_up = str(meta.get("build_up", "")).strip()
            if build_up:
                build_up_token = build_up

        lot = str(meta.get("lot_number", "")).strip()
        if build_up_token:
            upper_bu = build_up_token.upper()
            if upper_bu.startswith("BU-") or upper_bu == "BUMULTI":
                bu_token = build_up_token
            else:
                bu_token = f"BU-{build_up_token}"
            parts.append(bu_token)
        if lot:
            lot_lower = lot.lower()
            lot_token = lot if lot_lower.startswith("lot-") else f"Lot-{lot}"
            parts.append(lot_token)

        safe_parts = [cls._safe_token(p) for p in parts if cls._safe_token(p)]
        return "_".join(safe_parts) + ".xlsx"

    @staticmethod
    def _highlight_annular_ring(row, col_name: str, threshold: float):
        """Row styler: light-red background when annular ring < threshold."""
        if col_name not in row.index or pd.isna(row[col_name]):
            return [""] * len(row)
        if row[col_name] < threshold:
            return ["background-color: #ffcccc"] * len(row)
        return [""] * len(row)
