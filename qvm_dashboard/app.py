import streamlit as st
import pandas as pd
import yaml
import os
from pathlib import Path
import plotly.graph_objects as go
import numpy as np

from src.parser import parse_qvm_content, parse_filename, QVMParseError
from src.calculations import calculate_annular_ring, calculate_cam_compensation
from src.visuals import plot_bullseye_scatter, plot_quiver, plot_heatmap
from src.data_processor import DataProcessor
from src.views.process_stability import ProcessStabilityView
from src.views.quality_control import QualityControlView
from src.views.optical_edge_confidence import OpticalEdgeConfidenceView
from src.views.analytics import AnalyticsView
from src.views.cam_compensation import CAMCompensationView
from src.views.polar_drift import PolarDriftView
from src.views.spatial_heatmap import SpatialHeatmapView
from ui.sidebar import render_sidebar, render_nav_buttons
from panel_mapping import create_four_quarters_view

# Enable Pandas Copy-on-Write for performance
pd.options.mode.copy_on_write = True

def load_settings():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def load_css(file_path: str, settings: dict = None) -> None:
    """Loads a CSS file and injects it into the Streamlit app."""
    try:
        css = Path(file_path).read_text()
        colors = (settings or {}).get('COLORS', {})
        bg      = colors.get('app_background', '#212121')
        text    = colors.get('app_text', '#FFFFFF')
        panel   = colors.get('panel_ui', '#B87333')
        hover   = colors.get('panel_ui_hover', '#d48c46')
        css_variables = f'''
        <style>
            :root {{
                --background-color: {bg};
                --text-color: {text};
                --panel-color: {panel};
                --panel-hover-color: {hover};
            }}
            {css}
        </style>
        '''
        st.markdown(css_variables, unsafe_allow_html=True)
    except FileNotFoundError:
        pass

def highlight_annular_ring(row, col_name, threshold):
    """Pandas styler function to highlight rows with low annular ring."""
    if pd.isna(row[col_name]):
        return [''] * len(row)
    if row[col_name] < threshold:
        return ['background-color: #ffcccc; color: #990000; font-weight: bold'] * len(row)
    return [''] * len(row)


def main():
    settings = load_settings()
    ui_strings = settings.get('UI_STRINGS', {})
    col_names = settings.get('COLUMN_NAMES', {})
    tolerances = settings.get('TOLERANCES', {})
    plot_settings = settings.get('PLOT_SETTINGS', {})
    chart_colors = settings.get('CHART_COLORS', {})
    chart_heights = settings.get('CHART_HEIGHTS', {})
    optical_thresholds = settings.get('OPTICAL_EDGE_THRESHOLDS', {})
    chart_markers = settings.get('CHART_MARKERS', {})
    
    # Initialize data processor (single source of truth for data operations)
    data_processor = DataProcessor(settings)

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)

    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    # --- Sidebar (Extracted to ui/sidebar.py) ---
    sidebar_config = render_sidebar(settings)
    uploaded_files = sidebar_config['uploaded_files']
    material_build_up = sidebar_config['material_build_up']
    batch_id = sidebar_config['batch_id']
    process_limits = sidebar_config['process_limits']

    # --- Data Ingestion ---
    all_data = []
    available_panels = set()
    available_sides = set()

    if uploaded_files:
        for file in uploaded_files:
            try:
                # Extract meta from filename
                filename_info = parse_filename(file.name)
                panel_id = filename_info.get('Panel Number', 'Unknown')
                side_id = filename_info.get('Side', 'Unknown')

                content = file.getvalue().decode('utf-8')
                df = parse_qvm_content(content)
                df = calculate_annular_ring(df, settings)

                # Tag dataframe with meta
                df['Panel'] = panel_id
                df['Side'] = side_id

                available_panels.add(panel_id)
                available_sides.add(side_id)
                all_data.append(df)
            except Exception as e:
                st.sidebar.error(f"Error parsing {file.name}: {e}")

    # --- Main UI ---
    # Top Level Navigation
    main_view = render_nav_buttons(
        ["Panel Map", "Pad to Via", "Via to Pad", "Alignment"],
        state_key="main_view",
        default="Panel Map",
    )

    # Panel Map requires no uploaded data
    if main_view == "Panel Map":
        fig = create_four_quarters_view(settings)
        st.plotly_chart(fig, use_container_width=True)
        return

    if not all_data:
        st.info("Please upload one or more QVM text log files in the sidebar to begin.")
        return

    # Combine all parsed data
    master_df = pd.concat(all_data, ignore_index=True)

    if main_view == "Pad to Via":
        # Expander for Scope
        with st.expander("Analysis Scope", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                panel_list = sorted(list(available_panels))
                if len(panel_list) > 1:
                    panel_list.insert(0, "All")
                # Create display names with "Panel-" prefix
                panel_display = ["All" if p == "All" else f"Panel-{p}" for p in panel_list]
                st.markdown("**Select Panel**")
                selected_panel_display = render_nav_buttons(panel_display, state_key="selected_panel", default=panel_display[0])
                # Map display back to actual panel ID
                selected_panel = "All" if selected_panel_display == "All" else selected_panel_display.replace("Panel-", "")

            with col2:
                side_list = sorted(list(available_sides))
                if len(side_list) > 1:
                    side_list.insert(0, "Both")
                st.markdown("**Select Side**")
                selected_side = render_nav_buttons(side_list, state_key="selected_side", default=side_list[0])

        # Filter Data
        filtered_df = master_df.copy()
        if selected_panel and selected_panel != "All":
            filtered_df = filtered_df[filtered_df['Panel'] == selected_panel]
        if selected_side and selected_side != "Both":
            filtered_df = filtered_df[filtered_df['Side'] == selected_side]

        if filtered_df.empty:
            st.warning("No data matches the selected filters.")
            return

        st.markdown("<br>", unsafe_allow_html=True)

        # Sub-level navigation
        sub_view = render_nav_buttons(
            ["Quality Control", "Analytics", "CAM Compensation", "Optical Edge Confidence", "Process Stability", "Polar Drift (Machine Health)", "2D Spatial Heatmap (Laser Scan Field)"],
            state_key="sub_view",
            default="Quality Control",
        )

        st.markdown("---")

        # --- Quality Control View ---
        if sub_view == "Quality Control":
            # Use refactored QualityControlView (extracted to src/views/quality_control.py)
            qc_view = QualityControlView(settings, data_processor)
            qc_view.render(filtered_df, col_names=col_names, tolerances=tolerances)

        # --- Analytics View ---
        elif sub_view == "Analytics":
            # Use refactored AnalyticsView (extracted to src/views/analytics.py)
            analytics_view = AnalyticsView(settings, data_processor)
            analytics_view.render(filtered_df, settings=settings)

        # --- CAM Compensation View ---
        elif sub_view == "CAM Compensation":
            # Use refactored CAMCompensationView (extracted to src/views/cam_compensation.py)
            cam_view = CAMCompensationView(settings, data_processor)
            cam_view.render(filtered_df, settings=settings)

        elif sub_view == "Optical Edge Confidence":
            # Use refactored OpticalEdgeConfidenceView (extracted to src/views/optical_edge_confidence.py)
            oec_view = OpticalEdgeConfidenceView(settings, data_processor)
            oec_view.render(
                filtered_df,
                col_names=col_names,
                chart_colors=chart_colors,
                chart_heights=chart_heights,
                chart_markers=chart_markers,
                optical_thresholds=optical_thresholds
            )

        # --- Process Stability View ---
        elif sub_view == "Process Stability":
            # Use refactored ProcessStabilityView (extracted to src/views/process_stability.py)
            ps_view = ProcessStabilityView(settings, data_processor)
            ps_view.render(filtered_df, process_limits=process_limits)

        # --- Polar Drift (Machine Health) View ---
        elif sub_view == "Polar Drift (Machine Health)":
            # Use refactored PolarDriftView (extracted to src/views/polar_drift.py)
            pd_view = PolarDriftView(settings, data_processor)
            pd_view.render(filtered_df, col_names=col_names, chart_colors=chart_colors, chart_heights=chart_heights)

        # --- 2D Spatial Heatmap (Laser Scan Field) View ---
        elif sub_view == "2D Spatial Heatmap (Laser Scan Field)":
            # Use refactored SpatialHeatmapView (extracted to src/views/spatial_heatmap.py)
            sh_view = SpatialHeatmapView(settings, data_processor)
            sh_view.render(filtered_df, col_names=col_names, chart_colors=chart_colors)

    elif main_view == "Via to Pad":
        st.info("Via to Pad analytics not yet implemented.")

    elif main_view == "Alignment":
        st.info("Alignment analytics not yet implemented.")

if __name__ == "__main__":
    main()
