import logging
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ingestion import ingest_uploaded_file
from src.panel_mapping import create_four_quarters_view
from src.parser import QVMParseError
from src.utils import load_settings
from src.views.quality_control import QualityControlView
from src.views.registration_scatter import RegistrationScatterView
from src.visuals import plot_quiver, plot_vtp_box
from ui.sidebar import render_nav_buttons, render_sidebar


pd.options.mode.copy_on_write = True

logger = logging.getLogger(__name__)


def load_css(file_path: str, settings: dict = None) -> None:
    try:
        css = Path(file_path).read_text()
        colors = (settings or {}).get('COLORS', {})
        bg = colors.get('app_background', '#212121')
        text = colors.get('app_text', '#FFFFFF')
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


def _build_up_filter(df: pd.DataFrame, state_key: str) -> tuple[pd.DataFrame, str]:
    """Render top-level Build Up selector and apply BU filter."""
    if 'Build Up' not in df.columns:
        return df, "All"

    all_bu_values = sorted({str(v).strip() for v in df['Build Up'].dropna().tolist() if str(v).strip()})
    if not all_bu_values:
        return df, "All"

    normalized_values = [v for v in all_bu_values if v.lower() != 'unknown']
    has_unknown = any(v.lower() == 'unknown' for v in all_bu_values)

    # Show a selector when more than one BU state exists (including Unknown).
    total_states = len(normalized_values) + (1 if has_unknown else 0)

    if total_states == 1 and normalized_values:
        st.markdown(f"**Build Up:** {normalized_values[0]}")
        return df, normalized_values[0]

    if total_states == 1 and has_unknown:
        st.markdown("**Build Up:** Unknown")
        return df[df['Build Up'].astype(str).str.strip().str.lower() == 'unknown'].copy(), "Unknown"

    bu_options = ["All"] + normalized_values
    if has_unknown:
        bu_options.append("Unknown")
    st.markdown("**Select Build Up**")
    selected_bu = render_nav_buttons(bu_options, state_key=state_key, default="All")
    if selected_bu == "All":
        return df, selected_bu
    if selected_bu == "Unknown":
        return df[df['Build Up'].astype(str).str.strip().str.lower() == 'unknown'].copy(), selected_bu
    return df[df['Build Up'] == selected_bu].copy(), selected_bu


def _render_sub_views(filtered_df: pd.DataFrame, sub_view: str, settings: dict,
                      is_via_to_pad: bool = False, meta: dict = None) -> None:
    """Render whichever sub-view is active."""
    warnings = st.session_state.get('parse_warnings', [])
    if warnings:
        with st.expander(f"⚠️ {len(warnings)} parsing warning(s)", expanded=False):
            for w in warnings:
                st.warning(w)

    if sub_view == "Quality Control":
        QualityControlView(settings).render(filtered_df, is_via_to_pad=is_via_to_pad, meta=meta or {})
    elif sub_view == "Analytics":
        _render_registration_analytics(filtered_df, settings)


def _render_registration_analytics(filtered_df: pd.DataFrame, settings: dict) -> None:
    """Render the shared 3-tab registration analytics used by both processes."""
    tab1, tab2, tab3 = st.tabs(["Registration Scatter", "Quiver Plot", "Box Plot"])
    with tab1:
        if 'Side' in filtered_df.columns and filtered_df['Side'].nunique() > 1:
            side_options = ['Both'] + sorted(filtered_df['Side'].unique().tolist())
            chosen_side_scatter = st.selectbox("Select Side", side_options, key="scatter_side")
            scatter_df = filtered_df if chosen_side_scatter == 'Both' else filtered_df[filtered_df['Side'] == chosen_side_scatter].copy()
        else:
            scatter_df = filtered_df.copy()
        RegistrationScatterView(settings).render(scatter_df)
    with tab2:
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
            help="Exaggerates arrow length for visibility",
        )
        fig_q = plot_quiver(quiver_df, settings, multiplier=multiplier)
        st.plotly_chart(fig_q, use_container_width=True)
    with tab3:
        fig = plot_vtp_box(filtered_df, settings)
        st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    settings = load_settings()
    ui_strings = settings.get('UI_STRINGS', {})

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)
    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    sidebar_config = render_sidebar(settings)
    uploaded_files = sidebar_config['uploaded_files']
    file_overrides = sidebar_config.get('file_overrides', [])
    meta = {
        'project_name': sidebar_config.get('project_name', ''),
        'part_number': sidebar_config.get('part_number', ''),
        'lot_number': sidebar_config.get('lot_number', ''),
        'lot_name': sidebar_config.get('lot_name', ''),
        'build_up': sidebar_config.get('build_up', ''),
        'process': sidebar_config.get('process', ''),
        'panel': sidebar_config.get('panel', ''),
    }

    all_data = []
    all_warnings = []
    if uploaded_files:
        for file_index, file in enumerate(uploaded_files):
            logger.info('Parsing file: %s', file.name)
            try:
                file_override = file_overrides[file_index] if file_index < len(file_overrides) else {}
                df, file_warnings, ui_warnings, _, _ = ingest_uploaded_file(
                    file, settings, file_override=file_override,
                    default_build_up=meta.get('build_up'))
                all_warnings.extend(f"[{file.name}] {w}" for w in file_warnings)
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

            for warning in ui_warnings:
                st.sidebar.warning(warning)
            all_data.append(df)

    st.session_state['parse_warnings'] = all_warnings

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
    scoped_df, selected_build_up = _build_up_filter(master_df, state_key="build_up_scope")

    if selected_build_up != "All":
        meta['build_up'] = selected_build_up

    if scoped_df.empty:
        st.warning("No data matches the selected Build Up.")
        return

    if main_view == "Pad to Via":
        ptv_df = scoped_df[~scoped_df['Process'].str.contains('Via to Pad', case=False, na=False)].copy()

        if ptv_df.empty:
            st.info("Please upload a Pad-to-Via file (e.g. 'Post PFC_Pad to Via_Panel 20_F.txt').")
            return

        filtered_df = _scope_filters(ptv_df, panel_key="ptv_panel", side_key="ptv_side")

        if filtered_df.empty:
            st.warning("No data matches the selected filters.")
            return

        st.markdown("<br>", unsafe_allow_html=True)

        sub_view = render_nav_buttons(
            ["Quality Control", "Analytics"],
            state_key="ptv_sub_view",
            default="Quality Control",
        )
        st.markdown("---")

        _render_sub_views(filtered_df, sub_view, settings, is_via_to_pad=False, meta=meta)

    elif main_view == "Via to Pad":
        vtp_df = scoped_df[scoped_df['Process'].str.contains('Via to Pad', case=False, na=False)].copy()

        if vtp_df.empty:
            st.info("Please upload a Via-to-Pad file (e.g. 'Via to Pad_Panel 25_F.txt').")
            return

        filtered_vtp = _scope_filters(vtp_df, panel_key="vtp_panel", side_key="vtp_side")

        if filtered_vtp.empty:
            st.warning("No data matches the selected filters.")
            return

        st.markdown("<br>", unsafe_allow_html=True)

        sub_view = render_nav_buttons(
            ["Quality Control", "Analytics"],
            state_key="vtp_sub_view",
            default="Quality Control",
        )
        st.markdown("---")

        _render_sub_views(filtered_vtp, sub_view, settings, is_via_to_pad=True, meta=meta)

    elif main_view == "Alignment":
        st.markdown("### Alignment — Coming Soon")
        st.info(
            "Alignment analytics are being developed. This section will include registration skew, machine alignment diagnostics, and system calibration checks soon."
        )


if __name__ == "__main__":
    main()
