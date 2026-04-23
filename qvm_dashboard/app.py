import streamlit as st
import pandas as pd
import yaml
import os
from pathlib import Path
from src.parser import parse_qvm_content, parse_filename, QVMParseError
from src.calculations import calculate_annular_ring, calculate_cam_compensation
from src.visuals import plot_bullseye_scatter, plot_quiver, plot_heatmap
from src.data_processor import DataProcessor
from src.views.process_stability import ProcessStabilityView
from src.views.quality_control import QualityControlView
from src.views.optical_edge_confidence import OpticalEdgeConfidenceView
from src.views.analytics import AnalyticsView
from src.views.polar_drift import PolarDriftView
from src.views.spatial_heatmap import SpatialHeatmapView
from src.views.registration_scatter import RegistrationScatterView
from src.views.global_scaling import GlobalScalingView
from ui.sidebar import render_sidebar, render_nav_buttons
from panel_mapping import create_four_quarters_view

pd.options.mode.copy_on_write = True

def load_settings():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

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

def _scope_filters(df: pd.DataFrame, panel_key: str, side_key: str):
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
                      data_processor, col_names: dict, tolerances: dict,
                      chart_colors: dict, chart_heights: dict, chart_markers: dict,
                      optical_thresholds: dict, optical_model: dict, process_limits: dict):
    """Render whichever sub-view is active."""
    if sub_view == "Quality Control":
        QualityControlView(settings, data_processor).render(
            filtered_df, col_names=col_names, tolerances=tolerances)

    elif sub_view == "Analytics":
        AnalyticsView(settings, data_processor).render(filtered_df, settings=settings)

    elif sub_view == "Optical Edge Confidence":
        OpticalEdgeConfidenceView(settings, data_processor).render(
            filtered_df,
            col_names=col_names,
            chart_colors=chart_colors,
            chart_heights=chart_heights,
            chart_markers=chart_markers,
            optical_thresholds=optical_thresholds,
            optical_model=optical_model,
        )

    elif sub_view == "Process Stability":
        ProcessStabilityView(settings, data_processor).render(
            filtered_df, process_limits=process_limits)

    elif sub_view == "Polar Drift (Machine Health)":
        PolarDriftView(settings, data_processor).render(
            filtered_df, col_names=col_names, chart_colors=chart_colors, chart_heights=chart_heights)

    elif sub_view == "2D Spatial Heatmap (Laser Scan Field)":
        SpatialHeatmapView(settings, data_processor).render(
            filtered_df, col_names=col_names, chart_colors=chart_colors)

    elif sub_view == "Registration Scatter":
        RegistrationScatterView(settings, data_processor).render(filtered_df)

    elif sub_view == "Global Scaling Calculator":
        GlobalScalingView(settings, data_processor).render(filtered_df)


def main():
    settings = load_settings()
    ui_strings = settings.get('UI_STRINGS', {})
    col_names = settings.get('COLUMN_NAMES', {})
    tolerances = settings.get('TOLERANCES', {})
    chart_colors = settings.get('CHART_COLORS', {})
    chart_heights = settings.get('CHART_HEIGHTS', {})
    optical_thresholds = settings.get('OPTICAL_EDGE_THRESHOLDS', {})
    optical_model = settings.get('OPTICAL_CONFIDENCE_MODEL', {})
    chart_markers = settings.get('CHART_MARKERS', {})

    data_processor = DataProcessor(settings)

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)
    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    sidebar_config = render_sidebar(settings)
    uploaded_files = sidebar_config['uploaded_files']
    material_build_up = sidebar_config['material_build_up']
    batch_id = sidebar_config['batch_id']
    process_limits = sidebar_config['process_limits']

    # --- Data Ingestion ---
    all_data = []
    if uploaded_files:
        for file in uploaded_files:
            try:
                filename_info = parse_filename(file.name)
                content = file.getvalue().decode('utf-8')
                df = parse_qvm_content(content)
                df = calculate_annular_ring(df, settings)
                df['Panel'] = filename_info.get('Panel Number', 'Unknown')
                df['Side'] = filename_info.get('Side', 'Unknown')
                df['Process'] = filename_info.get('Process', 'Unknown')
                all_data.append(df)
            except Exception as e:
                st.sidebar.error(f"Error parsing {file.name}: {e}")

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
            ["Quality Control", "Analytics", "Global Scaling Calculator",
             "Optical Edge Confidence", "Process Stability",
             "Polar Drift (Machine Health)", "2D Spatial Heatmap (Laser Scan Field)"],
            state_key="ptv_sub_view",
            default="Quality Control",
        )
        st.markdown("---")

        _render_sub_views(
            filtered_df, sub_view, settings, data_processor,
            col_names, tolerances, chart_colors, chart_heights,
            chart_markers, optical_thresholds, optical_model, process_limits,
        )

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
            ["Quality Control", "Registration Scatter", "Process Stability", "Optical Edge Confidence"],
            state_key="vtp_sub_view",
            default="Quality Control",
        )
        st.markdown("---")

        _render_sub_views(
            filtered_vtp, sub_view, settings, data_processor,
            col_names, tolerances, chart_colors, chart_heights,
            chart_markers, optical_thresholds, optical_model, process_limits,
        )

    elif main_view == "Alignment":
        st.markdown("### Alignment — Coming Soon")
        st.info("Alignment analytics are being developed. This section will include registration skew, machine alignment diagnostics, and system calibration checks soon.")

if __name__ == "__main__":
    main()
