import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import streamlit as st

from src.core_shrinkage_parser import parse_cs_filename, parse_core_shrinkage_content
from src.ingestion import ingest_uploaded_file
from src.panel_mapping import create_four_quarters_view
from src.parser import QVMParseError
from src.utils import is_via_to_pad as is_via_to_pad_mask, load_settings
from src.views.core_shrinkage import CoreShrinkageView
from src.views.quality_control import QualityControlView
from src.views.registration_scatter import RegistrationScatterView
from src.visuals import plot_quiver, plot_vtp_box
from ui.sidebar import render_nav_buttons, render_sidebar


pd.options.mode.copy_on_write = True

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def _settings() -> dict:
    """load_settings() memoised — it reads and validates YAML from disk, and
    Streamlit reruns this script on every widget interaction."""
    return load_settings()


@st.cache_data(max_entries=16, show_spinner=False)
def _parse_upload(name: str, data: bytes, settings: dict,
                  file_override: dict) -> tuple:
    """Parse one uploaded file, memoised on its content.

    Streamlit reruns the whole script on every widget interaction, so without
    this every nav click re-parsed every uploaded file. ``data`` is the file's
    bytes, which makes the cache key change exactly when the upload does.

    Returns the (df, parse_warnings, ui_warnings) slice that main() consumes.
    """
    uploaded = SimpleNamespace(name=name, getvalue=lambda: data)
    df, parse_warnings, ui_warnings, _, _ = ingest_uploaded_file(
        uploaded, settings, file_override=file_override)
    return df, parse_warnings, ui_warnings


@st.cache_data(max_entries=16, show_spinner=False)
def _parse_cs_upload(name: str, data: bytes, layer: str, panel: str,
                     grid_mapping: dict) -> pd.DataFrame:
    """Parse one Core Shrinkage upload, memoised on its content.

    Same reasoning as :func:`_parse_upload` — Streamlit reruns the script on
    every widget interaction, so keying on the file's bytes keeps a nav click
    from re-parsing every upload.
    """
    cs_df = parse_core_shrinkage_content(data.decode('utf-8'), layer)
    cs_df['Panel'] = panel
    cs_df['grid_id'] = cs_df['location'].map(grid_mapping)
    return cs_df


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


def _panel_sort_key(panel: str):
    """Order panels numerically ("9" before "10"), non-numeric ones last.

    Panel Number is a free-text override, so this has to survive anything the
    user types. isdecimal() rather than isdigit() because isdigit() accepts
    characters int() rejects — "²" among them — which would raise here.
    """
    text = str(panel)
    return (0, int(text), '') if text.isdecimal() else (1, 0, text)


def _scope_filters(df: pd.DataFrame, panel_key: str, filter_key: str, *,
                   filter_col: str = 'Side',
                   filter_label: str = 'Side') -> tuple[pd.DataFrame, str, str]:
    """Render Panel + a secondary scope filter; return the frame plus selections.

    Shared by every analysis tab. Pad-to-Via and Via-to-Pad take the defaults and
    filter on ``Side``; Core Shrinkage passes ``filter_col='layer'`` to filter on
    Front/Back instead. The secondary selector only offers "Both" when the data
    actually holds more than one value.
    """
    with st.expander("Analysis Scope", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            panel_list = sorted(df['Panel'].unique().tolist(), key=_panel_sort_key)
            if len(panel_list) > 1:
                panel_list.insert(0, "All")
            panel_display = ["All" if p == "All" else f"Panel-{p}" for p in panel_list]
            st.markdown("**Select Panel**")
            sel_display = render_nav_buttons(panel_display, state_key=panel_key, default=panel_display[0])
            selected_panel = "All" if sel_display == "All" else sel_display.replace("Panel-", "")
        with col2:
            opt_list = sorted(df[filter_col].unique().tolist())
            if len(opt_list) > 1:
                opt_list.insert(0, "Both")
            st.markdown(f"**Select {filter_label}**")
            selected_opt = render_nav_buttons(opt_list, state_key=filter_key, default=opt_list[0])

    filtered = _apply_scope_filters(df, selected_panel, selected_opt, filter_col=filter_col)
    return filtered, selected_panel, selected_opt


def _apply_scope_filters(df: pd.DataFrame, selected_panel: str, selected_value: str,
                         *, filter_col: str = 'Side') -> pd.DataFrame:
    """Apply the panel + secondary scope selection to any dataframe.

    The single home for the scope rules: "All" panels and "Both" secondary values
    mean no filtering, and a dataframe missing either column is passed through.
    """
    filtered = df.copy()
    if selected_panel and selected_panel != "All" and 'Panel' in filtered.columns:
        filtered = filtered[filtered['Panel'] == selected_panel]
    if selected_value and selected_value != "Both" and filter_col in filtered.columns:
        filtered = filtered[filtered[filter_col] == selected_value]
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
                      is_via_to_pad: bool = False, meta: dict = None,
                      export_df: pd.DataFrame | None = None) -> None:
    """Render whichever sub-view is active."""
    warnings = st.session_state.get('parse_warnings', [])
    if warnings:
        with st.expander(f"⚠️ {len(warnings)} parsing warning(s)", expanded=False):
            for w in warnings:
                st.warning(w)

    if sub_view == "Quality Control":
        QualityControlView(settings).render(
            filtered_df,
            is_via_to_pad=is_via_to_pad,
            meta=meta or {},
            export_df=export_df if export_df is not None else filtered_df,
        )
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


def _render_process_tab(scoped_df: pd.DataFrame, settings: dict, meta: dict, *,
                        is_via_to_pad: bool) -> None:
    """Render one process tab: scope filters, sub-view nav, then the sub-view.

    Pad-to-Via and Via-to-Pad differ only in which rows they select, which
    session-state keys they own, and the hint shown when no matching file has
    been uploaded — so they share one body.
    """
    if is_via_to_pad:
        key_prefix, label = "vtp", "Via-to-Pad"
        example = "Via to Pad_Panel 25_F.txt"
    else:
        key_prefix, label = "ptv", "Pad-to-Via"
        example = "Post PFC_Pad to Via_Panel 20_F.txt"

    is_vtp_row = is_via_to_pad_mask(scoped_df)
    process_df = scoped_df[is_vtp_row if is_via_to_pad else ~is_vtp_row].copy()

    if process_df.empty:
        st.info(f"Please upload a {label} file (e.g. '{example}').")
        return

    filtered_df, selected_panel, selected_side = _scope_filters(
        process_df, panel_key=f"{key_prefix}_panel", filter_key=f"{key_prefix}_side")
    export_scope_df = _apply_scope_filters(scoped_df, selected_panel, selected_side)

    if filtered_df.empty:
        st.warning("No data matches the selected filters.")
        return

    st.markdown("<br>", unsafe_allow_html=True)

    sub_view = render_nav_buttons(
        ["Quality Control", "Analytics"],
        state_key=f"{key_prefix}_sub_view",
        default="Quality Control",
    )
    st.markdown("---")

    _render_sub_views(
        filtered_df, sub_view, settings,
        is_via_to_pad=is_via_to_pad, meta=meta, export_df=export_scope_df)


def _render_core_shrinkage_tab(cs_data: list, settings: dict, meta: dict) -> None:
    """Render the Core Shrinkage tab: Panel/Layer scope, then the sub-view.

    Core Shrinkage files carry their own format, parser and frame shape (Front/
    Back layers rather than F/B sides, and no Process column), so this tab runs
    on its own data and shares only the scope-filter widgets. It is deliberately
    outside the Build Up scope selector: CS filenames carry no Build Up token.
    """
    if not cs_data:
        st.info("Please upload Core Shrinkage files "
                "(e.g. '...Core_Shrinkage_Panel 28_Front_CAMorder.txt' / '...Back...').")
        return

    master_cs_df = pd.concat(cs_data, ignore_index=True)
    filtered_cs, _, _ = _scope_filters(
        master_cs_df, panel_key="cs_panel", filter_key="cs_layer",
        filter_col='layer', filter_label='Layer')

    if filtered_cs.empty:
        st.warning("No data matches the selected filters.")
        return

    st.markdown("<br>", unsafe_allow_html=True)

    cs_sub_view = render_nav_buttons(
        ["Quality Control", "Analytics", "Distortion Map", "Method"],
        state_key="cs_sub_view",
        default="Quality Control",
    )
    st.markdown("---")

    CoreShrinkageView(settings).render(filtered_cs, sub_view=cs_sub_view, meta=meta)


def main() -> None:
    settings = _settings()
    ui_strings = settings.get('UI_STRINGS', {})

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)
    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    sidebar_config = render_sidebar()
    uploaded_files = sidebar_config['uploaded_files']
    file_overrides = sidebar_config.get('file_overrides', [])
    meta = {
        'project_name': sidebar_config.get('project_name', ''),
        'part_number': sidebar_config.get('part_number', ''),
        'lot_number': sidebar_config.get('lot_number', ''),
        'lot_name': sidebar_config.get('lot_name', ''),
        # Build Up is file-derived; the Build Up scope selector fills it in below.
        'build_up': '',
    }

    all_data = []
    all_warnings = []
    cs_data = []
    if uploaded_files:
        for file_index, file in enumerate(uploaded_files):
            logger.info('Parsing file: %s', file.name)

            # Core Shrinkage files are a different format with a different
            # parser; they are identified by filename ("core_shrinkage") and
            # never reach parse_qvm_content.
            cs_info = parse_cs_filename(file.name)
            if cs_info['is_core_shrinkage']:
                try:
                    cs_data.append(_parse_cs_upload(
                        file.name, file.getvalue(), cs_info['layer'],
                        cs_info['Panel Number'], settings.get('GRID_MAPPING', {})))
                    logger.info('Parsed Core Shrinkage file %s: layer=%s panel=%s',
                                file.name, cs_info['layer'], cs_info['Panel Number'])
                except UnicodeDecodeError as e:
                    logger.warning('Decode failed for %s: %s', file.name, e)
                    st.sidebar.error(f"❌ `{file.name}`: not a valid text file ({e}).")
                except Exception as e:
                    logger.warning('Core Shrinkage parse failed for %s: %s', file.name, e)
                    st.sidebar.error(f"❌ `{file.name}`: {e}")
                continue

            try:
                file_override = file_overrides[file_index] if file_index < len(file_overrides) else {}
                df, file_warnings, ui_warnings = _parse_upload(
                    file.name, file.getvalue(), settings, file_override)
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
        ["Panel Map", "Pad to Via", "Via to Pad", "Core Shrinkage"],
        state_key="main_view",
        default="Panel Map",
    )

    if main_view == "Panel Map":
        fig = create_four_quarters_view(settings)
        st.plotly_chart(fig, use_container_width=True)
        return

    if main_view == "Core Shrinkage":
        _render_core_shrinkage_tab(cs_data, settings, meta)
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

    if main_view in ("Pad to Via", "Via to Pad"):
        _render_process_tab(scoped_df, settings, meta,
                            is_via_to_pad=(main_view == "Via to Pad"))


if __name__ == "__main__":
    main()
