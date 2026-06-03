import logging
import streamlit as st
import pandas as pd
import os
from pathlib import Path
from src.parser import parse_qvm_content, parse_filename, QVMParseError
from src.visuals import plot_quiver, plot_heatmap, plot_vtp_box
from src.utils import load_settings, calculate_annular_ring
from src.views.quality_control import QualityControlView
from src.views.analytics import AnalyticsView
from src.views.spatial_heatmap import SpatialHeatmapView
from src.views.registration_scatter import RegistrationScatterView
from ui.sidebar import render_sidebar, render_nav_buttons
from src.panel_mapping import create_four_quarters_view

pd.options.mode.copy_on_write = True

logger = logging.getLogger(__name__)

def load_css(file_path: str, settings: dict = None) -> None:
    try:
        css = Path(file_path).read_text()
        colors = (settings or {}).get('COLORS', {})
        bg    = colors.get('app_background', '#212121')
        text  = colors.get('app_text', '#FFFFFF')
        panel = colors.get('panel_ui', '#B87333')
        hover = colors.get('panel_ui_hover', '#d48c46')
        st.markdown(f'''
        <style>
            :root {{
                --background-color: {bg};
                --text-color: {text};
                --panel-color: {panel};
                --panel-hover-color: {hover};
            }}
            {css}
        </style>
        ''', unsafe_allow_html=True)
    except FileNotFoundError:
        pass

def _scope_filters(df: pd.DataFrame, panel_key: str, side_key: str) -> pd.DataFrame:
    """Render panel/side scope filters and return filtered DataFrame."""
    with st.expander("Analysis Scope", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            panel_list = sorted(df['Panel'].unique().tolist())
            if len(panel_list) > 1:
                panel_list.insert(0, "All")
            panel_display = ["All" if p == "All" else f"Panel-{p}" for p in panel_list]
            st.markdown("**Select Panel**")
            sel_display = render_nav_buttons(panel_display, state_key=panel_key, default=panel_display[0])
            selected_panel = "All" if sel_display == "All" else sel_display.replace("Panel-", "")
        with col2:
            side_list = sorted(df['Side'].unique().tolist())
            if len(side_list) > 1:
                side_list.insert(0, "Both")
            st.markdown("**Select Side**")
            selected_side = render_nav_buttons(side_list, state_key=side_key, default=side_list[0])

    filtered = df.copy()
    if selected_panel and selected_panel != "All":
        filtered = filtered[filtered['Panel'] == selected_panel]
    if selected_side and selected_side != "Both":
        filtered = filtered[filtered['Side'] == selected_side]
    return filtered


def _render_sub_views(filtered_df: pd.DataFrame, sub_view: str, settings: dict,
                      is_via_to_pad: bool = False, meta: dict = None) -> None:
    """Render whichever sub-view is active.

    Views pull their own settings slices from `self.settings` via BaseView, so
    only the per-render context (is_via_to_pad, meta) needs threading here.
    """
    if sub_view == "Quality Control":
        QualityControlView(settings).render(
            filtered_df, is_via_to_pad=is_via_to_pad, meta=meta or {})

    elif sub_view == "Analytics":
        if is_via_to_pad:
            tab1, tab2, tab3 = st.tabs([
                "Registration Scatter", "Quiver Plot", "Box Plot",
            ])
            with tab1:
                # Side selector for scatter when both sides uploaded
                if 'Side' in filtered_df.columns and filtered_df['Side'].nunique() > 1:
                    side_options = ['Both'] + sorted(filtered_df['Side'].unique().tolist())
                    chosen_side_scatter = st.selectbox("Select Side", side_options, key="scatter_side")
                    scatter_df = filtered_df if chosen_side_scatter == 'Both' else filtered_df[filtered_df['Side'] == chosen_side_scatter].copy()
                else:
                    scatter_df = filtered_df.copy()
                RegistrationScatterView(settings).render(scatter_df)
            with tab2:
                # Side selector for quiver — must be single side (16 points only)
                if 'Side' in filtered_df.columns and filtered_df['Side'].nunique() > 1:
                    side_options = sorted(filtered_df['Side'].unique().tolist())
                    chosen_side = st.selectbox("Select Side for Quiver Plot", side_options, key="quiver_side")
                    quiver_df = filtered_df[filtered_df['Side'] == chosen_side].copy()
                else:
                    quiver_df = filtered_df.copy()
                plot_settings = settings.get('PLOT_SETTINGS', {})
                multiplier = st.slider(
                    "Vector Multiplier",
                    min_value=plot_settings.get('vector_multiplier_min', 1),
                    max_value=plot_settings.get('vector_multiplier_max', 100),
                    value=plot_settings.get('vector_multiplier_default', 50),
                    step=1,
                    help="Exaggerates arrow length for visibility")
                fig_q = plot_quiver(quiver_df, settings, multiplier=multiplier)
                st.plotly_chart(fig_q, use_container_width=True)
            with tab3:
                fig = plot_vtp_box(filtered_df, settings)
                st.plotly_chart(fig, use_container_width=True)
        else:
            AnalyticsView(settings).render(filtered_df)

    elif sub_view == "2D Spatial Heatmap (Laser Scan Field)":
        SpatialHeatmapView(settings).render(filtered_df)



def main() -> None:
    settings = load_settings()
    ui_strings = settings.get('UI_STRINGS', {})

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)
    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    sidebar_config = render_sidebar(settings)
    uploaded_files = sidebar_config['uploaded_files']
    meta = {
        'project_name': sidebar_config.get('project_name', ''),
        'part_number':  sidebar_config.get('part_number', ''),
        'lot_number':   sidebar_config.get('lot_number', ''),
        'lot_name':     sidebar_config.get('lot_name', ''),
        'build_up':     sidebar_config.get('build_up', ''),
        'process':      sidebar_config.get('process', ''),
        'panel':        sidebar_config.get('panel', ''),
    }

    # --- Data Ingestion ---
    # Routing (Pad-to-Via vs Via-to-Pad) is decided by parse_qvm_content from
    # the file contents, not the filename. The filename only contributes Panel
    # and Side metadata, plus a hint we use to warn the user about mis-naming.
    all_data = []
    if uploaded_files:
        for file in uploaded_files:
            logger.info('Parsing file: %s', file.name)
            try:
                filename_info = parse_filename(file.name)
                content = file.getvalue().decode('utf-8')
                df = parse_qvm_content(content, settings)
                logger.info('Parsed %s: %d rows, process=%s',
                            file.name, len(df),
                            df['Process'].iloc[0] if not df.empty else 'unknown')
            except QVMParseError as e:
                logger.warning('Parse failed for %s: %s', file.name, e)
                st.sidebar.error(f"❌ `{file.name}`: {e}")
                continue
            except UnicodeDecodeError as e:
                logger.warning('Decode failed for %s: %s', file.name, e)
                st.sidebar.error(f"❌ `{file.name}`: not a valid text file ({e}).")
                continue

            df = calculate_annular_ring(df, settings)
            df['Panel'] = filename_info.get('Panel Number', 'Unknown')
            df['Side'] = filename_info.get('Side', 'Unknown')
            all_data.append(df)

            hint = filename_info.get('format_hint')
            detected = df['Process'].iloc[0] if not df.empty else None
            if hint is None:
                st.sidebar.warning(
                    f"⚠️ `{file.name}`: filename doesn't include `VTP` or `PTV`. "
                    f"Treated as **{detected}** based on file content."
                )
            elif detected is not None and hint != detected:
                st.sidebar.warning(
                    f"⚠️ `{file.name}`: filename hints **{hint}** but content is "
                    f"**{detected}**. Going with the content."
                )

    # --- Top-Level Navigation ---
    main_view = render_nav_buttons(
        ["Panel Map", "Pad to Via", "Via to Pad", "Alignment"],
        state_key="main_view",
        default="Panel Map",
    )

    if main_view == "Panel Map":
        fig = create_four_quarters_view(settings)
        st.plotly_chart(fig, use_container_width=True)
        return

    if not all_data:
        st.info("Please upload one or more QVM text log files in the sidebar to begin.")
        return

    master_df = pd.concat(all_data, ignore_index=True)

    # ------------------------------------------------------------------ #
    #  PAD TO VIA — all 6 sub-views (has absolute coordinates)            #
    # ------------------------------------------------------------------ #
    if main_view == "Pad to Via":
        ptv_df = master_df[~master_df['Process'].str.contains('Via to Pad', case=False, na=False)].copy()

        if ptv_df.empty:
            st.info("Please upload a Pad-to-Via file (e.g. 'Post PFC_Pad to Via_Panel 20_F.txt').")
            return

        filtered_df = _scope_filters(ptv_df, panel_key="ptv_panel", side_key="ptv_side")

        if filtered_df.empty:
            st.warning("No data matches the selected filters.")
            return

        st.markdown("<br>", unsafe_allow_html=True)

        sub_view = render_nav_buttons(
            ["Quality Control", "Analytics",
             "2D Spatial Heatmap (Laser Scan Field)"],
            state_key="ptv_sub_view",
            default="Quality Control",
        )
        st.markdown("---")

        _render_sub_views(filtered_df, sub_view, settings)

    # ------------------------------------------------------------------ #
    #  VIA TO PAD — 3 sub-views only (no absolute coordinates)            #
    # ------------------------------------------------------------------ #
    elif main_view == "Via to Pad":
        vtp_df = master_df[master_df['Process'].str.contains('Via to Pad', case=False, na=False)].copy()

        if vtp_df.empty:
            st.info("Please upload a Via-to-Pad file (e.g. 'Via to Pad_Panel 25_F.txt').")
            return

        filtered_vtp = _scope_filters(vtp_df, panel_key="vtp_panel", side_key="vtp_side")

        if filtered_vtp.empty:
            st.warning("No data matches the selected filters.")
            return

        st.markdown("<br>", unsafe_allow_html=True)

        # Analytics / Polar Drift / Spatial Heatmap require absolute coordinates
        # which Via-to-Pad files do not contain — those views are intentionally
        # excluded here as they would produce meaningless results without position data.
        sub_view = render_nav_buttons(
            ["Quality Control", "Analytics"],
            state_key="vtp_sub_view",
            default="Quality Control",
        )
        st.markdown("---")

        _render_sub_views(filtered_vtp, sub_view, settings, is_via_to_pad=True, meta=meta)

    elif main_view == "Alignment":
        st.markdown("### Alignment — Coming Soon")
        st.info("Alignment analytics are being developed. This section will include registration skew, machine alignment diagnostics, and system calibration checks soon.")

if __name__ == "__main__":
    main()
