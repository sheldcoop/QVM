import streamlit as st
import pandas as pd
import yaml
import os
import io

from src.parser import parse_qvm_content, parse_filename, QVMParseError
from src.calculations import calculate_annular_ring, calculate_cam_compensation
from src.visuals import plot_bullseye_scatter, plot_quiver, plot_heatmap

def load_settings():
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

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

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    # Sidebar
    st.sidebar.header("File Upload & Info")

    uploaded_file = st.sidebar.file_uploader("Upload QVM Text File", type=['txt'])

    process = "Unknown"
    panel = "Unknown"
    side = "Unknown"

    if uploaded_file is not None:
        filename_info = parse_filename(uploaded_file.name)
        process = filename_info.get('Process', 'Unknown')
        panel = filename_info.get('Panel Number', 'Unknown')
        side = filename_info.get('Side', 'Unknown')

    st.sidebar.write(f"**Process:** {process}")
    st.sidebar.write(f"**Panel:** {panel}")
    st.sidebar.write(f"**Side:** {side}")

    st.sidebar.markdown("---")
    st.sidebar.header("Additional Meta Data")
    material_build_up = st.sidebar.text_input("Material Build-up", "")
    batch_id = st.sidebar.text_input("Batch ID", "")

    if uploaded_file is not None:
        # Read the file
        try:
            content = uploaded_file.getvalue().decode('utf-8')
            df = parse_qvm_content(content)

            # Calculate annular ring
            df = calculate_annular_ring(df, settings)

            # Tabs
            tab1, tab2, tab3 = st.tabs([
                ui_strings.get('tab_1_name', 'Quality Control'),
                ui_strings.get('tab_2_name', 'Analytics'),
                ui_strings.get('tab_3_name', 'CAM Compensation')
            ])

            # Tab 1: Quality Control
            with tab1:
                st.subheader("Annular Ring Analysis")
                annular_col = col_names.get('annular_ring', 'Annular Ring')
                threshold = tolerances.get('annular_ring_min', 0.0)

                st.write(f"Highlighting rows where {annular_col} < {threshold}")

                # Apply styling
                styled_df = df.style.apply(
                    highlight_annular_ring,
                    col_name=annular_col,
                    threshold=threshold,
                    axis=1
                )

                st.dataframe(styled_df, use_container_width=True)

            # Tab 2: Analytics
            with tab2:
                st.subheader("Machine Calibration Analytics")

                plot_type = st.selectbox(
                    "Select Plot Type",
                    ["Bullseye Scatter", "Quiver/Vector Plot", "Heatmap"]
                )

                if plot_type == "Bullseye Scatter":
                    fig = plot_bullseye_scatter(df, settings)
                    st.plotly_chart(fig, use_container_width=True)

                elif plot_type == "Quiver/Vector Plot":
                    multiplier = st.slider(
                        "Vector Exaggeration Multiplier",
                        min_value=plot_settings.get('vector_multiplier_min', 1),
                        max_value=plot_settings.get('vector_multiplier_max', 200),
                        value=plot_settings.get('vector_multiplier_default', 50)
                    )
                    fig = plot_quiver(df, settings, multiplier)
                    st.plotly_chart(fig, use_container_width=True)

                elif plot_type == "Heatmap":
                    fig = plot_heatmap(df, settings)
                    st.plotly_chart(fig, use_container_width=True)

            # Tab 3: CAM Compensation
            with tab3:
                st.subheader("Panel Average Shifts")
                avg_x, avg_y = calculate_cam_compensation(df, settings)

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Average X Shift (DX)", f"{avg_x:.6f} mm")
                with col2:
                    st.metric("Average Y Shift (DY)", f"{avg_y:.6f} mm")

        except QVMParseError as e:
            st.error(f"Failed to parse QVM file: {e}")
        except Exception as e:
            st.error(f"An unexpected error occurred: {e}")

    else:
        st.info("Please upload a QVM text log file to begin.")

if __name__ == "__main__":
    main()
