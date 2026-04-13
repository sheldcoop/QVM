import streamlit as st
import pandas as pd
import yaml
import os
from pathlib import Path

from src.parser import parse_qvm_content, parse_filename, QVMParseError
from src.calculations import calculate_annular_ring, calculate_cam_compensation
from src.visuals import plot_bullseye_scatter, plot_quiver, plot_heatmap
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

def _nav_buttons(options, state_key, default=None, cols_gap="small"):
    """Render a row of primary/secondary buttons for navigation."""
    if state_key not in st.session_state or st.session_state[state_key] not in options:
        st.session_state[state_key] = default if default is not None else options[0]
    cols = st.columns(len(options), gap=cols_gap)
    for i, label in enumerate(options):
        is_active = st.session_state[state_key] == label
        cols[i].button(
            str(label),
            type="primary" if is_active else "secondary",
            width="stretch",
            key=f"{state_key}_{label}",
            on_click=lambda l=label: st.session_state.update({state_key: l}),
        )
    return st.session_state[state_key]


def main():
    settings = load_settings()
    ui_strings = settings.get('UI_STRINGS', {})
    col_names = settings.get('COLUMN_NAMES', {})
    tolerances = settings.get('TOLERANCES', {})
    plot_settings = settings.get('PLOT_SETTINGS', {})

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)

    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    # --- Sidebar ---
    with st.sidebar:
        st.header("File Upload & Meta Data")
        uploaded_files = st.file_uploader(
            "Upload QVM Text Files",
            type=['txt'],
            accept_multiple_files=True
        )

        if uploaded_files:
            if st.button("🔄 Run Analysis", type="primary", use_container_width=True):
                st.session_state['run_analysis'] = True

        st.markdown("---")
        material_build_up = st.text_input("Material Build-up", "")
        batch_id = st.text_input("Batch ID", "")

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
    main_view = _nav_buttons(
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
                selected_panel_display = _nav_buttons(panel_display, state_key="selected_panel", default=panel_display[0])
                # Map display back to actual panel ID
                selected_panel = "All" if selected_panel_display == "All" else selected_panel_display.replace("Panel-", "")

            with col2:
                side_list = sorted(list(available_sides))
                if len(side_list) > 1:
                    side_list.insert(0, "Both")
                st.markdown("**Select Side**")
                selected_side = _nav_buttons(side_list, state_key="selected_side", default=side_list[0])

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
        sub_view = _nav_buttons(
            ["Quality Control", "Analytics", "CAM Compensation"],
            state_key="sub_view",
            default="Quality Control",
        )

        st.markdown("---")

        # --- Quality Control View ---
        if sub_view == "Quality Control":
            annular_col = col_names.get('annular_ring', 'Annular Ring')
            threshold = tolerances.get('annular_ring_min', 0.0)
            st.write(f"Highlighting rows where {annular_col} < {threshold}")

            # Prepare display dataframe
            display_df = filtered_df.copy()
            
            # Drop Panel and Side columns (not needed in display)
            cols_to_drop = [col for col in ['Panel', 'Side'] if col in display_df.columns]
            display_df = display_df.drop(columns=cols_to_drop)
            
            # Convert all measurements from mm to microns (multiply by 1000)
            measurement_cols = [
                col_names.get('outer_diameter', 'Outer Diameter'),
                col_names.get('inner_diameter', 'Inner Diameter'),
                col_names.get('ptv_distance', 'PtV Distance'),
                col_names.get('x_distance', 'Shift (DX)'),
                col_names.get('y_distance', 'Shift (DY)'),
                col_names.get('annular_ring', 'Annular Ring')
            ]
            for col in measurement_cols:
                if col in display_df.columns:
                    display_df[col] = (display_df[col] * 1000).round(3)
            
            # Sort by Grid ID ascending
            grid_id_col = col_names.get('grid_id', 'Grid ID')
            if grid_id_col in display_df.columns:
                display_df = display_df.sort_values(by=grid_id_col, ascending=True)
            
            # Add clarification about Grid ID
            st.info("📍 **Grid ID**: Position on the PCB quadrant (11-14 = Upper Left, 21-24 = Lower Left, 31-34 = Lower Right, 41-44 = Upper Right). First digit = quadrant, second digit = point (1-4). All measurements in **microns (µm)**.")

            # Apply styling with custom formatter for 3 decimals without trailing zeros
            def format_to_3_decimals(val):
                if pd.isna(val):
                    return ''
                try:
                    # Format to 3 decimals, then strip trailing zeros and decimal point if needed
                    formatted = f'{float(val):.3f}'.rstrip('0').rstrip('.')
                    return formatted
                except:
                    return str(val)
            
            # Build format dict for all numeric columns at once
            format_dict = {}
            for col in display_df.columns:
                if display_df[col].dtype in ['float64', 'float32', 'int64', 'int32']:
                    format_dict[col] = format_to_3_decimals
            
            styled_df = display_df.style.apply(
                highlight_annular_ring,
                col_name=annular_col,
                threshold=threshold,
                axis=1
            )
            if format_dict:
                styled_df = styled_df.format(format_dict)
            st.dataframe(styled_df, use_container_width=True)

        # --- Analytics View ---
        elif sub_view == "Analytics":
            plot_type = st.selectbox(
                "Select Plot Type",
                ["Bullseye Scatter", "Quiver/Vector Plot", "Heatmap"]
            )

            if plot_type == "Bullseye Scatter":
                fig = plot_bullseye_scatter(filtered_df, settings)
                st.plotly_chart(fig, use_container_width=True, height=600)

            elif plot_type == "Quiver/Vector Plot":
                multiplier = st.slider(
                    "Vector Exaggeration Multiplier",
                    min_value=plot_settings.get('vector_multiplier_min', 1),
                    max_value=plot_settings.get('vector_multiplier_max', 200),
                    value=plot_settings.get('vector_multiplier_default', 50)
                )
                fig = plot_quiver(filtered_df, settings, multiplier)
                st.plotly_chart(fig, use_container_width=True, height=600)

            elif plot_type == "Heatmap":
                fig = plot_heatmap(filtered_df, settings)
                st.plotly_chart(fig, use_container_width=True, height=600)

        # --- CAM Compensation View ---
        elif sub_view == "CAM Compensation":
            avg_x, avg_y = calculate_cam_compensation(filtered_df, settings)
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Average X Shift (DX)", f"{avg_x:.6f} mm")
            with col2:
                st.metric("Average Y Shift (DY)", f"{avg_y:.6f} mm")

    elif main_view == "Via to Pad":
        st.info("Via to Pad analytics not yet implemented.")

    elif main_view == "Alignment":
        st.info("Alignment analytics not yet implemented.")

if __name__ == "__main__":
    main()
