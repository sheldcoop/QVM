"""Scope-filter helpers shared by every analysis tab.

Pure rules (``_panel_sort_key``, ``_apply_scope_filters``) plus the thin
Streamlit selector widgets that render them (``_scope_filters``,
``_build_up_filter``). Extracted from ``app.py`` so the entry point stays
bootstrap + dispatch; ``app.py`` re-exports these names.
"""

import pandas as pd
import streamlit as st

from ui.sidebar import render_nav_buttons


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
