import logging
import streamlit as st
import pandas as pd
import os
from pathlib import Path
from src.utils import load_settings
from src.dbanalysis.config import DB_ANALYSES
from src.dbanalysis.engine import render_analysis
from ui.sidebar import render_sidebar, render_nav_buttons

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


def main() -> None:
    settings = load_settings()
    ui_strings = settings.get('UI_STRINGS', {})

    st.set_page_config(page_title=ui_strings.get('dashboard_title', 'QVM Dashboard'), layout="wide")
    load_css(os.path.join(os.path.dirname(__file__), "assets", "styles.css"), settings)
    st.title(ui_strings.get('dashboard_title', 'QVM Dashboard'))

    sidebar_config = render_sidebar(settings)
    uploaded_files = sidebar_config['uploaded_files']

    # --- Data Ingestion ---
    # Database Analysis works exclusively from Horus database Excel files.
    db_files = []
    if uploaded_files:
        for file in uploaded_files:
            if file.name.lower().endswith(('.xlsx', '.xls')):
                db_files.append(file)
                logger.info('Routed Excel file %s to database analysis', file.name)
            else:
                st.sidebar.warning(
                    f"⚠️ `{file.name}`: ignored — only Excel files (.xlsx/.xls) are supported."
                )

    # --- Database Analysis (the only view) ---
    db_sub_view = render_nav_buttons(
        ["Roughness", "Impedance", "Top to Bottom Via", "Trace", "Pad", "Landing Pad", "Download Center"],
        state_key="db_sub_view",
        default="Roughness",
    )
    st.markdown("---")

    if not db_files:
        st.info("Please upload a Horus database Excel file (.xlsx or .xls) to begin.")
        return

    if db_sub_view in DB_ANALYSES:
        render_analysis(DB_ANALYSES[db_sub_view], db_files)
    elif db_sub_view == "Download Center":
        from src.views.download_center import DownloadCenterView
        DownloadCenterView(settings, db_files).render()


if __name__ == "__main__":
    main()
