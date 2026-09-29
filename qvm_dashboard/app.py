import logging
import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.core_shrinkage_parser import parse_cs_filename, parse_core_shrinkage_content
from src.ingestion import ingest_uploaded_file
from src.panel_mapping import create_four_quarters_view
from src.parser import QVMParseError
from src.utils import is_via_to_pad as is_via_to_pad_mask, load_settings
from src.views.core_shrinkage import CoreShrinkageView
from src.views.quality_control import QualityControlView
from src.views.registration_scatter import RegistrationScatterView
from src.registration_shrinkage import compute_distance_shrinkage_by_group
from src.scope import (
    _apply_scope_filters,
    _build_up_filter,
    _panel_sort_key,
    _scope_filters,
)
from src.visuals import plot_quiver, plot_vtp_box
from ui.sidebar import render_nav_buttons, render_sidebar


logging.basicConfig(level=logging.INFO, format='%(levelname)s %(name)s: %(message)s')

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def _settings() -> dict:
    """load_settings() memoised — it reads and validates YAML from disk, and
    Streamlit reruns this script on every widget interaction."""
    return load_settings()


@st.cache_data(max_entries=8, ttl=3600, show_spinner=False)
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


@st.cache_data(max_entries=8, ttl=3600, show_spinner=False)
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

    def _shrinkage_quiver_figure(res, title: str) -> go.Figure:
        qdf = res.quadrant.copy()
        if qdf.empty:
            return go.Figure()

        fp = res.full_panel.iloc[0]
        fp_x = float(fp.get('Shrinkage X (FP PPM)', fp.get('Shrinkage X (FP)', 0.0)))
        fp_y = float(fp.get('Shrinkage Y (FP PPM)', fp.get('Shrinkage Y (FP)', 0.0)))
        qdf['dx'] = qdf['QP Shrinkage X (PPM)'] - fp_x
        qdf['dy'] = qdf['QP Shrinkage Y (PPM)'] - fp_y

        positions = {
            'UL': (-1.0, 1.0),
            'LL': (-1.0, -1.0),
            'LR': (1.0, -1.0),
            'UR': (1.0, 1.0),
        }
        max_dev = float(max(qdf['dx'].abs().max(), qdf['dy'].abs().max(), 1.0))
        arrow_scale = 0.8 / max_dev

        fig = go.Figure()
        xs, ys, labels, hover = [], [], [], []
        for _, row in qdf.iterrows():
            quad = str(row['Quadrant'])
            if quad not in positions:
                continue
            x0, y0 = positions[quad]
            xs.append(x0)
            ys.append(y0)
            labels.append(quad)
            hover.append(
                f"{quad}<br>ΔX from FP: {row['dx']:.1f} ppm<br>ΔY from FP: {row['dy']:.1f} ppm"
            )
            x1 = x0 + float(row['dx']) * arrow_scale
            y1 = y0 + float(row['dy']) * arrow_scale
            fig.add_annotation(
                x=x1,
                y=y1,
                ax=x0,
                ay=y0,
                xref='x',
                yref='y',
                axref='x',
                ayref='y',
                showarrow=True,
                arrowhead=3,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor='#F4B486',
            )

        fig.add_trace(go.Scatter(
            x=xs,
            y=ys,
            mode='markers+text',
            text=labels,
            textposition='top center',
            marker=dict(size=12, color='#8B4513'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover,
            name='Quadrant center',
        ))
        fig.update_layout(
            title=title,
            xaxis=dict(visible=False, range=[-2.0, 2.0]),
            yaxis=dict(visible=False, range=[-2.0, 2.0], scaleanchor='x', scaleratio=1),
            margin=dict(l=20, r=20, t=50, b=20),
            showlegend=False,
        )
        return fig

    tab1, tab2, tab3, tab4 = st.tabs(["Registration Scatter", "Quiver Plot", "Box Plot", "Shrinkage"])
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

    with tab4:
        cs_cfg = settings.get('CORE_SHRINKAGE', {})
        nominal_coords = (
            settings.get('REGISTRATION_SHRINKAGE', {}).get('NOMINAL_COORDS')
            or cs_cfg.get('NOMINAL_COORDS', {})
        )
        if not nominal_coords:
            st.info('Nominal coordinates are not configured for shrinkage analytics.')
        else:
            col_names = settings.get('COLUMN_NAMES', {})
            loc_col = col_names.get('location', 'Location')
            x_col = col_names.get('coord_x', 'Coord. X')
            y_col = col_names.get('coord_y', 'Coord. Y')
            if any(c not in filtered_df.columns for c in (loc_col, x_col, y_col)):
                st.info('Shrinkage analytics requires Location, Coord. X, and Coord. Y columns.')
            else:
                outlier_ppm = float(settings.get('REGISTRATION_SHRINKAGE', {}).get('outlier_ppm', 50.0))
                groups = compute_distance_shrinkage_by_group(
                    filtered_df,
                    nominal_coords,
                    location_col=loc_col,
                    x_col=x_col,
                    y_col=y_col,
                    outlier_ppm=outlier_ppm,
                    group_cols=['Build Up', 'Panel', 'Side'],
                )
                st.caption('Distance-based only; no coordinate transform/alignment is applied.')
                for g in groups:
                    gmeta = g['group']
                    res = g['result']
                    label = ', '.join(f'{k}: {v}' for k, v in gmeta.items()) if gmeta else 'Current scope'
                    st.markdown(f'**{label}**')
                    if res.warnings:
                        for w in res.warnings:
                            st.warning(w)
                    if res.quadrant.empty:
                        st.info('No shrinkage output for this scope.')
                        continue
                    q_cols = [
                        'Quadrant',
                        'QP Shrinkage X (%)',
                        'QP Shrinkage Y (%)',
                        'Delta X (um)',
                        'Delta Y (um)',
                        'QP Shrinkage X (PPM)',
                        'QP Shrinkage Y (PPM)',
                    ]
                    show_q_cols = [c for c in q_cols if c in res.quadrant.columns]
                    st.dataframe(res.quadrant[show_q_cols], use_container_width=True, hide_index=True)
                    chart = res.quadrant.set_index('Quadrant')[['QP Shrinkage X (%)', 'QP Shrinkage Y (%)']]
                    st.bar_chart(chart)
                    st.plotly_chart(_shrinkage_quiver_figure(res, f'Shrinkage Quiver — {label}'), use_container_width=True)
                    fp_cols = [
                        'Shrinkage X (FP %)',
                        'Shrinkage Y (FP %)',
                        'Shrinkage X-Y Offset (%)',
                        'Shrinkage X (FP PPM)',
                        'Shrinkage Y (FP PPM)',
                        'Shrinkage X-Y Offset (PPM)',
                    ]
                    show_fp_cols = [c for c in fp_cols if c in res.full_panel.columns]
                    st.dataframe(res.full_panel[show_fp_cols], use_container_width=True, hide_index=True)
                    u_cols = [
                        'QTQ Range X (%)',
                        'QTQ Range Y (%)',
                        'QTQ Range X',
                        'QTQ Range Y',
                        'Total 2D Spatial Distortion Vector',
                    ]
                    show_u_cols = [c for c in u_cols if c in res.uniformity.columns]
                    st.dataframe(res.uniformity[show_u_cols], use_container_width=True, hide_index=True)
                    if not res.outliers.empty:
                        st.dataframe(res.outliers, use_container_width=True, hide_index=True)


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
