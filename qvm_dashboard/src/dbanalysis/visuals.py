import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from src import theme

# --- SPC unbiasing constants (functions of subgroup size n) ----------------- #
# Computed exactly from the Gamma function rather than table lookups, so they
# work for any subgroup size, including the unequal sizes the Horus data has.

def c4(n: int) -> float:
    """Unbiasing constant c4 for the sample standard deviation."""
    if n < 2:
        return float('nan')
    return math.sqrt(2.0 / (n - 1)) * math.gamma(n / 2.0) / math.gamma((n - 1) / 2.0)


def a3(n: int) -> float:
    """X-bar control-limit factor A3 (limits = X̿ ± A3·S̄)."""
    cc = c4(n)
    if n < 2 or not cc:
        return float('nan')
    return 3.0 / (cc * math.sqrt(n))


def b3(n: int) -> float:
    """S-chart lower-limit factor B3 (LCL_s = B3·S̄)."""
    cc = c4(n)
    if n < 2 or not cc:
        return float('nan')
    return max(0.0, 1.0 - 3.0 * math.sqrt(1.0 - cc * cc) / cc)


def b4(n: int) -> float:
    """S-chart upper-limit factor B4 (UCL_s = B4·S̄)."""
    cc = c4(n)
    if n < 2 or not cc:
        return float('nan')
    return 1.0 + 3.0 * math.sqrt(1.0 - cc * cc) / cc

def _sty(style, *path, default=None):
    """Read a nested key from the CHART_SETTINGS dict, falling back to ``default``."""
    cur = style or {}
    for k in path:
        if isinstance(cur, dict) and k in cur:
            cur = cur[k]
        else:
            return default
    return cur


def _bold(text, on: bool) -> str:
    """Wrap text in <b> when bold is on (robust across Plotly versions)."""
    return f"<b>{text}</b>" if on else str(text)


def _axis_style(style):
    """Resolve the shared axis font settings used by both charts."""
    txt = theme.TEXT if hasattr(theme, 'TEXT') else '#cdd6f4'
    return {
        'title_color': _sty(style, 'axis', 'title_color', default=txt),
        'title_size': _sty(style, 'axis', 'title_size', default=14),
        'tick_color': _sty(style, 'axis', 'tick_color', default=txt),
        'tick_size': _sty(style, 'axis', 'tick_size', default=12),
        'bold': _sty(style, 'axis', 'bold', default=False),
    }


def plot_roughness_box(df: pd.DataFrame, metric_col: str, group_col: str, title: str, color_by_col: str = None, limits: dict = None, measurement_unit: str = None, style: dict = None) -> go.Figure:
    """Panel-level box plot grouped by `group_col` (e.g. Lot Name).

    Layout: All | Lot A | Lot B | Lot C ...
    Narrow, tall boxes with bold jitter dots. Mean reference line. All sizing /
    fonts come from the optional ``style`` dict (CHART_SETTINGS); omitting it keeps
    the original hardcoded look.
    """
    df_plot = df.dropna(subset=[metric_col]).copy()
    
    # Ensure metric is numeric
    df_plot[metric_col] = pd.to_numeric(df_plot[metric_col], errors='coerce')
    df_plot = df_plot.dropna(subset=[metric_col])
    
    sc = df_plot[metric_col]
    n = len(sc)
    if n == 0:
        # Return empty figure
        fig = go.Figure()
        fig.update_layout(title=f"No data for {title}")
        return fig
        
    mean_v = float(sc.mean())
    std_v = float(sc.std())
    
    rng = np.random.default_rng(42)
    fig = go.Figure()

    # --- Resolve style (CHART_SETTINGS) with current defaults --------------- #
    fam = _sty(style, 'font_family', default='Inter, sans-serif')
    title_size = _sty(style, 'title_size', default=17)
    title_color = _sty(style, 'title_color', default='white')
    wm_size = _sty(style, 'watermark_size', default=17)
    badge_size = _sty(style, 'badge_size', default=14)
    grid_color = _sty(style, 'grid_color', default='rgba(255,255,255,0.05)')
    ax = _axis_style(style)
    box_h = _sty(style, 'box', 'height', default=700)
    box_w = _sty(style, 'box', 'box_width', default=0.35)
    jit = _sty(style, 'box', 'jitter', default=0.15)
    msize = _sty(style, 'box', 'marker_size', default=10)
    mopac = _sty(style, 'box', 'marker_opacity', default=0.9)
    mean_size = _sty(style, 'box', 'mean_label_size', default=13)

    # Ensure the grouping column is treated as a string (categorical)
    if group_col in df_plot.columns:
        df_plot[group_col] = df_plot[group_col].astype(str).str.replace(r'\.0$', '', regex=True)
        
    # Identify unique groups
    groups = df_plot[group_col].dropna().unique().tolist() if group_col in df_plot.columns else []
    # Sort groups if possible
    try:
        groups = sorted(groups)
    except:
        pass
        
    _x_order = groups
    _x_pos = {label: i for i, label in enumerate(_x_order)}
    
    # Setup coloring for dots
    added_legend_items = set()
    unit_colors = {}
    if color_by_col and color_by_col in df_plot.columns:
        unique_units = df_plot[color_by_col].dropna().unique().tolist()
        try:
            unique_units = sorted(unique_units)
        except:
            pass
        # Use a qualitative colorscale for units (Plotly's Safe colors are nice)
        import plotly.express as px
        base_colors = px.colors.qualitative.Safe + px.colors.qualitative.Pastel
        for i, u in enumerate(unique_units):
            unit_colors[u] = base_colors[i % len(base_colors)]
            
    def _add_box_and_dots(x_label: str, df_group: pd.DataFrame, color: str, fill: str) -> None:
        if df_group.empty:
            return
            
        values = df_group[metric_col].values
            
        pos = _x_pos[x_label]
        
        # Add box plot
        fig.add_trace(go.Box(
            x=[pos] * len(values),
            y=values,
            name=x_label,
            boxpoints=False,
            width=box_w,
            fillcolor=fill,
            line=dict(color=color, width=2),
            marker_color=color,
            showlegend=False,
            hoverinfo='skip',
        ))
        jitter = rng.uniform(-jit, jit, size=len(values))
        
        # Find panel column if it exists
        p_col = next((c for c in df_group.columns if str(c).lower().strip() == 'panel'), None)
        
        # Add scatter dots
        if color_by_col and color_by_col in df_group.columns:
            # Color dots by the categorical column
            for unit_val, df_unit in df_group.groupby(color_by_col):
                # find indices of this unit in the original group array
                indices = np.where(df_group[color_by_col].values == unit_val)[0]
                unit_vals = values[indices]
                unit_jit = jitter[indices]
                
                # Build custom hover texts
                panels = df_group[p_col].values[indices] if p_col else [''] * len(indices)
                hover_texts = [
                    f"<b>Lot: {x_label}</b><br>" +
                    f"<b>{color_by_col}: {unit_val}</b><br>" + 
                    (f"Panel: {panels[i]}<br>" if p_col else "") +
                    f"Value: {v:.2f}" 
                    for i, v in enumerate(unit_vals)
                ]
                
                show_leg = unit_val not in added_legend_items
                if show_leg:
                    added_legend_items.add(unit_val)
                    
                u_color = unit_colors.get(unit_val, color)
                
                fig.add_trace(go.Scatter(
                    x=pos + unit_jit,
                    y=unit_vals,
                    text=hover_texts,
                    mode='markers',
                    name=f"{color_by_col}: {unit_val}",
                    marker=dict(color=u_color, size=msize, opacity=mopac, line=dict(width=0.5, color='rgba(0,0,0,0.5)')),
                    hovertemplate="%{text}<extra></extra>",
                    showlegend=show_leg,
                    legendgroup=str(unit_val),
                ))
        else:
            panels = df_group[p_col].values if p_col else [''] * len(values)
            hover_texts = [
                f"<b>Lot: {x_label}</b><br>" +
                (f"Panel: {panels[i]}<br>" if p_col else "") + 
                f"Value: {v:.2f}" 
                for i, v in enumerate(values)
            ]
            # Default single color
            fig.add_trace(go.Scatter(
                x=pos + jitter,
                y=values,
                text=hover_texts,
                mode='markers',
                marker=dict(color=color, size=msize, opacity=mopac, line=dict(width=0)),
                hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            ))
        
    # Calculate max and offset for annotation placement
    max_val = sc.max()
    offset = (max_val - sc.min()) * 0.1 if max_val > sc.min() else 0.5
    
    # Group boxes
    colors = list(theme.QUARTER_COLORS.values()) if hasattr(theme, 'QUARTER_COLORS') else ['#F38BA8', '#FAB387', '#F9E2AF', '#A6E3A1', '#89B4FA', '#CBA6F7']
    
    for i, g in enumerate(groups):
        gdf = df_plot[df_plot[group_col] == g]
        if gdf.empty:
            continue
            
        g_color = colors[i % len(colors)]
        # Make a transparent fill color
        hx = g_color.lstrip('#')
        ri, gi, bi = int(hx[0:2], 16), int(hx[2:4], 16), int(hx[4:6], 16)
        g_fill = f'rgba({ri},{gi},{bi},0.13)'
        
        _add_box_and_dots(g, gdf, color=g_color, fill=g_fill)
        
        # Mean annotation
        fig.add_annotation(
            text=f"<b>{gdf[metric_col].mean():.2f}</b> ± {gdf[metric_col].std():.2f}",
            xref='x', yref='y',
            x=_x_pos[g], y=max_val + offset,
            xanchor='center', yanchor='bottom',
            showarrow=False,
            font=dict(size=mean_size, color=g_color),
        )
        
    # Global mean line
    fig.add_hline(
        y=mean_v,
        line_dash='dot',
        line_color='rgba(255,255,255,0.3)',
        annotation_text='Overall Mean',
        annotation_position='top left',
    )
    
    # Export Watermark in top left corner (extracts BU, Side, Process from title)
    watermark_text = title.split(' - ')[-1] if ' - ' in title else title
    fig.add_annotation(
        text=f"<b>{watermark_text}</b>",
        xref="paper", yref="paper",
        x=0.0, y=1.05,
        xanchor='left', yanchor='bottom',
        showarrow=False,
        font=dict(color='white', size=wm_size)
    )

    # Optional Spec Limits
    if limits:
        if limits.get("LSL") is not None:
            fig.add_hline(y=limits["LSL"], line_dash="dash", line_color="#F38BA8", annotation_text="LSL", annotation_position="bottom right")
        if limits.get("Target") is not None:
            fig.add_hline(y=limits["Target"], line_dash="dash", line_color="#A6E3A1", annotation_text="Target", annotation_position="bottom right")
        if limits.get("USL") is not None:
            fig.add_hline(y=limits["USL"], line_dash="dash", line_color="#F38BA8", annotation_text="USL", annotation_position="top right")
            
        # Process Performance (Pp / Ppk). This uses the OVERALL (long-term) sample
        # sigma, so it is Pp/Ppk, not Cp/Cpk (which require within-subgroup sigma).
        # One-sided specs are supported: with a single limit, Pp is N/A but Ppk is
        # still computed from that side.
        lsl = limits.get("LSL")
        usl = limits.get("USL")
        if std_v > 0 and (lsl is not None or usl is not None):
            try:
                pp_text = "N/A"
                if lsl is not None and usl is not None:
                    pp_text = f"{(float(usl) - float(lsl)) / (6 * std_v):.2f}"
                    ppk_val = min((float(usl) - mean_v) / (3 * std_v),
                                  (mean_v - float(lsl)) / (3 * std_v))
                elif usl is not None:
                    ppk_val = (float(usl) - mean_v) / (3 * std_v)
                else:
                    ppk_val = (mean_v - float(lsl)) / (3 * std_v)

                ppk_color = '#A6E3A1' if ppk_val >= 1.33 else ('#F9E2AF' if ppk_val >= 1.0 else '#F38BA8')
                badge_text = f"<b>Pp: {pp_text} | Ppk: {ppk_val:.2f}</b>"

                fig.add_annotation(
                    text=badge_text,
                    xref="paper", yref="paper",
                    x=1.0, y=1.05,
                    xanchor='right', yanchor='bottom',
                    showarrow=False,
                    font=dict(color=ppk_color, size=badge_size),
                    bgcolor='rgba(0,0,0,0.5)',
                    borderpad=4,
                    bordercolor=ppk_color,
                    borderwidth=1
                )
            except (ValueError, TypeError):
                pass
    
    # Dynamically scale x-axis range so that 1 or 2 lots don't become massively wide
    span = max(5.0, len(_x_order))
    center = (len(_x_order) - 1) / 2.0
    x_range = [center - span/2, center + span/2]
    
    y_title = f"{metric_col} ({measurement_unit})" if measurement_unit else metric_col
    
    fig.update_layout(
        title=dict(
            text=f"<b>{title}</b>",
            font=dict(color=title_color, size=title_size),
            x=0.5,
            xanchor='center'
        ),
        height=box_h,
        margin=dict(l=50, r=30, t=60, b=40),
        xaxis=dict(
            title=dict(text=_bold(group_col, ax['bold']),
                       font=dict(color=ax['title_color'], size=ax['title_size'])),
            tickfont=dict(color=ax['tick_color'], size=ax['tick_size']),
            tickmode='array',
            tickvals=list(_x_pos.values()),
            ticktext=[_bold(k, ax['bold']) for k in _x_pos.keys()],
            tickangle=-90,
            showgrid=False,
            zeroline=False,
            range=x_range
        ),
        yaxis=dict(
            title=dict(text=_bold(y_title, ax['bold']),
                       font=dict(color=ax['title_color'], size=ax['title_size'])),
            tickfont=dict(color=ax['tick_color'], size=ax['tick_size']),
            showgrid=True,
            gridcolor=grid_color,
            zeroline=False,
        ),
        plot_bgcolor=theme.BACKGROUND if hasattr(theme, 'BACKGROUND') else '#1e1e2e',
        paper_bgcolor=theme.BACKGROUND if hasattr(theme, 'BACKGROUND') else '#1e1e2e',
        font=dict(family=fam, color=theme.TEXT if hasattr(theme, 'TEXT') else '#cdd6f4'),
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
    )
    
    return fig


def plot_control_chart(df: pd.DataFrame, metric_col: str, lot_col: str,
                       panel_col: str = None, title: str = "",
                       measurement_unit: str = None, style: dict = None) -> go.Figure:
    """X-bar & S control chart with rational subgroups.

    Subgroups are ``(lot, panel)`` when a panel column is available — this gives
    enough points for meaningful limits with the Horus data (only a handful of
    lots) — otherwise lots alone. Control limits come from *within-subgroup*
    variation via the standard unbiasing constants: X-bar limits ``X̿ ± A3·S̄``
    and S-chart limits ``B3·S̄``/``B4·S̄``, evaluated per subgroup so unequal
    subgroup sizes get correct variable (stair-step) limits. Western Electric
    rules are checked in z-score space so they stay valid under variable limits.
    When every subgroup holds a single measurement, sigma falls back to the
    moving-range individuals estimate (``MR̄ / 1.128``) and the S-chart is omitted.

    Spec limits (USL/LSL/Target) are intentionally NOT drawn here: this chart
    plots subgroup *means* (voice of the process), whereas specs apply to
    *individual* parts (voice of the customer). Spec compliance lives on the box
    plot and the Pp/Ppk capability summary.

    All sizing / fonts come from the optional ``style`` dict (CHART_SETTINGS).
    """
    MIN_SUBGROUPS = 2

    # --- Resolve style (CHART_SETTINGS) with current defaults --------------- #
    fam = _sty(style, 'font_family', default='Inter, sans-serif')
    title_size = _sty(style, 'title_size', default=17)
    title_color = _sty(style, 'title_color', default='white')
    wm_size = _sty(style, 'watermark_size', default=17)
    grid_color = _sty(style, 'grid_color', default='rgba(255,255,255,0.05)')
    ax = _axis_style(style)
    cc_h = _sty(style, 'control', 'height', default=950)
    cc_msize = _sty(style, 'control', 'marker_size', default=10)
    subplot_size = _sty(style, 'control', 'subplot_title_size', default=14)

    work = df.copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors='coerce')
    work = work.dropna(subset=[metric_col])
    if work.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data for {title}")
        return fig

    # --- Build ordered subgroups -------------------------------------------- #
    by_panel = panel_col is not None and panel_col in work.columns
    key_cols = [lot_col, panel_col] if by_panel else [lot_col]
    for c in key_cols:
        work[c] = work[c].astype(str).str.replace(r'\.0$', '', regex=True)

    groups = []  # (label, values, lot)
    for key, g in work.groupby(key_cols, sort=True):
        vals = g[metric_col].to_numpy()
        if len(vals) == 0:
            continue
        if by_panel:
            lot_v, panel_v = key
            label = f"P{panel_v}"          # point label = panel; lot shown by band
        else:
            lot_v = key
            label = str(key)
        groups.append((label, vals, str(lot_v)))

    if len(groups) < MIN_SUBGROUPS:
        fig = go.Figure()
        fig.update_layout(
            title=(f"{title}: not enough subgroups for a control chart "
                   f"(need ≥{MIN_SUBGROUPS}, got {len(groups)}). Use the Box Plot."))
        return fig

    labels = [g[0] for g in groups]
    lots = [g[2] for g in groups]
    means = np.array([v.mean() for _, v, _ in groups], dtype=float)
    sizes = np.array([len(v) for _, v, _ in groups], dtype=int)
    stds = np.array([v.std(ddof=1) if len(v) > 1 else np.nan for _, v, _ in groups], dtype=float)
    x = list(range(len(groups)))
    grand_mean = float(work[metric_col].mean())  # size-weighted centre line

    # --- Estimate the standard error of each subgroup mean ------------------ #
    has_within = (~np.isnan(stds)).any() and np.nanmean(stds) > 0
    if has_within:
        s_bar = float(np.nanmean(stds))
        # SE_i = A3(n_i)·S̄ / 3  ==  sigma_hat / sqrt(n_i)
        se_mean = np.array([(a3(n) * s_bar / 3.0) if n > 1 else np.nan for n in sizes],
                           dtype=float)
        if np.isnan(se_mean).any():  # singletons fall back to the average SE
            fill = np.nanmean(se_mean) if not np.all(np.isnan(se_mean)) else np.nan
            se_mean = np.where(np.isnan(se_mean), fill, se_mean)
    else:
        # Individuals fallback: sigma from the moving range of the means.
        s_bar = None
        mr = np.abs(np.diff(means))
        mr_bar = float(mr.mean()) if mr.size else 0.0
        sigma_i = (mr_bar / 1.128) if mr_bar > 0 else (float(np.std(means, ddof=1)) or 1.0)
        se_mean = np.full(len(groups), sigma_i, dtype=float)

    se_mean = np.where((se_mean == 0), np.nan, se_mean)
    if np.all(np.isnan(se_mean)):
        fig = go.Figure()
        fig.update_layout(title=f"{title}: cannot estimate control limits (no variation).")
        return fig
    se_mean = np.where(np.isnan(se_mean), np.nanmean(se_mean), se_mean)

    ucl_x = grand_mean + 3 * se_mean
    lcl_x = grand_mean - 3 * se_mean
    z = (means - grand_mean) / se_mean

    # --- Western Electric rules (in z-space) -------------------------------- #
    colors_x = ['#89B4FA'] * len(z)
    sizes_x = [8] * len(z)
    viol_x = [''] * len(z)
    for i in range(len(z)):
        if abs(z[i]) > 3:
            viol_x[i] = "Rule 1: beyond 3σ"; colors_x[i] = '#F38BA8'; sizes_x[i] = 12; continue
        if i >= 2:
            w = z[i - 2:i + 1]
            if (np.sum(w > 2) >= 2) or (np.sum(w < -2) >= 2):
                viol_x[i] = "Rule 2: 2 of 3 beyond 2σ"; colors_x[i] = '#FAB387'; sizes_x[i] = 12; continue
        if i >= 4:
            w = z[i - 4:i + 1]
            if (np.sum(w > 1) >= 4) or (np.sum(w < -1) >= 4):
                viol_x[i] = "Rule 3: 4 of 5 beyond 1σ"; colors_x[i] = '#F9E2AF'; sizes_x[i] = 10; continue
        if i >= 7:
            w = z[i - 7:i + 1]
            if np.all(w > 0) or np.all(w < 0):
                viol_x[i] = "Rule 4: 8 in a row one side"; colors_x[i] = '#CBA6F7'; sizes_x[i] = 10

    hover_x = []
    for i in range(len(groups)):
        base = f"<b>{lots[i]} / {labels[i]}</b><br>N: {sizes[i]}<br>Mean: {means[i]:.2f}"
        if viol_x[i]:
            base = f"<span style='color:{colors_x[i]}'><b>{viol_x[i]}</b></span><br>" + base
        hover_x.append(base)

    # --- S-chart prep (only with genuine within-subgroup variation) --------- #
    show_s = has_within and (~np.isnan(stds)).any()
    if show_s:
        ucl_s = np.array([b4(n) * s_bar if n > 1 else np.nan for n in sizes], dtype=float)
        lcl_s = np.array([b3(n) * s_bar if n > 1 else np.nan for n in sizes], dtype=float)
        colors_s = ['#F38BA8' if (not np.isnan(stds[i]) and not np.isnan(ucl_s[i])
                                  and stds[i] > ucl_s[i]) else '#A6E3A1'
                    for i in range(len(stds))]
        hover_s = [f"<b>{lots[i]} / {labels[i]}</b><br>N: {sizes[i]}<br>Std Dev: "
                   f"{stds[i]:.2f}" if not np.isnan(stds[i]) else f"<b>{lots[i]} / {labels[i]}</b><br>N: {sizes[i]}"
                   for i in range(len(stds))]

    # --- Figure ------------------------------------------------------------- #
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
        row_heights=[0.6, 0.4],
        subplot_titles=("Accuracy (X-Bar)", "Precision (S-Chart)"))

    # Row 1: X-bar — variable control limits as step lines
    fig.add_trace(go.Scatter(x=x, y=ucl_x, mode='lines', line_shape='hv',
                             line=dict(color='rgba(243,139,168,0.8)', dash='dash'),
                             name='UCL', hoverinfo='skip'), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=lcl_x, mode='lines', line_shape='hv',
                             line=dict(color='rgba(243,139,168,0.8)', dash='dash'),
                             name='LCL', hoverinfo='skip'), row=1, col=1)
    fig.add_hline(y=grand_mean, line_dash='solid', line_color='rgba(137,180,250,0.8)',
                  annotation_text='Center Line', annotation_position='top left', row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=means, mode='lines',
                             line=dict(color='rgba(255,255,255,0.2)', width=2),
                             showlegend=False, hoverinfo='skip'), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=means, mode='markers',
                             marker=dict(color=colors_x, size=sizes_x,
                                         line=dict(width=1, color='rgba(0,0,0,0.5)')),
                             text=hover_x, hovertemplate="%{text}<extra></extra>",
                             showlegend=False), row=1, col=1)

    # (Spec limits are deliberately omitted — see the function docstring.)

    # Row 2: S-chart, or an explanatory note when unavailable
    if show_s:
        fig.add_trace(go.Scatter(x=x, y=ucl_s, mode='lines', line_shape='hv',
                                 line=dict(color='rgba(243,139,168,0.8)', dash='dash'),
                                 name='UCL_s', hoverinfo='skip'), row=2, col=1)
        fig.add_trace(go.Scatter(x=x, y=lcl_s, mode='lines', line_shape='hv',
                                 line=dict(color='rgba(243,139,168,0.8)', dash='dash'),
                                 name='LCL_s', hoverinfo='skip'), row=2, col=1)
        fig.add_hline(y=s_bar, line_dash='solid', line_color='rgba(166,227,161,0.8)',
                      annotation_text='Center Line (S)', annotation_position='top left',
                      row=2, col=1)
        fig.add_trace(go.Scatter(x=x, y=stds, mode='markers',
                                 marker=dict(color=colors_s, size=cc_msize,
                                             line=dict(width=1, color='rgba(0,0,0,0.5)')),
                                 text=hover_s, hovertemplate="%{text}<extra></extra>",
                                 showlegend=False), row=2, col=1)
    else:
        fig.add_annotation(text="S-chart unavailable (one measurement per subgroup)",
                           xref="paper", yref="paper", x=0.5, y=0.2,
                           showarrow=False, font=dict(color='rgba(255,255,255,0.6)', size=13))

    # Faint background bands grouping consecutive panels by lot (panel subgroups
    # only). Bands carry the lot identity so point colour stays free for the WECO
    # control-status signalling. Added AFTER the traces (Plotly requires data on a
    # subplot before add_vrect resolves its row/col axes); layer='below' keeps
    # them behind the data.
    if by_panel:
        start = 0
        band_idx = 0
        for i in range(1, len(lots) + 1):
            if i == len(lots) or lots[i] != lots[start]:
                fill = 'rgba(255,255,255,0.05)' if band_idx % 2 == 0 else 'rgba(255,255,255,0.0)'
                fig.add_vrect(x0=start - 0.5, x1=(i - 1) + 0.5, fillcolor=fill,
                              line_width=0, layer='below', row=1, col=1,
                              annotation_text=str(lots[start]), annotation_position="top",
                              annotation_font_size=11,
                              annotation_font_color='rgba(255,255,255,0.6)')
                fig.add_vrect(x0=start - 0.5, x1=(i - 1) + 0.5, fillcolor=fill,
                              line_width=0, layer='below', row=2, col=1)
                start = i
                band_idx += 1

    watermark = title.split(' - ')[-1] if ' - ' in title else title
    fig.add_annotation(text=f"<b>{watermark}</b>", xref="paper", yref="paper",
                       x=0.0, y=1.03, xanchor='left', yanchor='bottom',
                       showarrow=False, font=dict(color='white', size=wm_size))

    span = max(5.0, len(groups))
    center = (len(groups) - 1) / 2.0
    x_range = [center - span / 2, center + span / 2]
    y_title = f"{metric_col} ({measurement_unit})" if measurement_unit else metric_col

    fig.update_layout(
        title=dict(text=f"<b>{title} (X-Bar & S-Chart)</b>",
                   font=dict(color=title_color, size=title_size), x=0.5, xanchor='center'),
        height=cc_h, margin=dict(l=50, r=30, t=80, b=90), showlegend=False,
        plot_bgcolor=theme.BACKGROUND if hasattr(theme, 'BACKGROUND') else '#1e1e2e',
        paper_bgcolor=theme.BACKGROUND if hasattr(theme, 'BACKGROUND') else '#1e1e2e',
        font=dict(family=fam,
                  color=theme.TEXT if hasattr(theme, 'TEXT') else '#cdd6f4'))

    axis_title_font = dict(color=ax['title_color'], size=ax['title_size'])
    axis_tick_font = dict(color=ax['tick_color'], size=ax['tick_size'])
    x_title = "Panel (grouped by Lot)" if by_panel else "Lot"
    fig.update_xaxes(tickmode='array', tickvals=x, ticktext=[''] * len(labels),
                     tickfont=axis_tick_font, showgrid=False, zeroline=False,
                     range=x_range, row=1, col=1)
    fig.update_xaxes(title_text=_bold(x_title, ax['bold']), title_font=axis_title_font,
                     tickmode='array', tickvals=x,
                     ticktext=[_bold(l, ax['bold']) for l in labels], tickangle=-90,
                     tickfont=axis_tick_font, showgrid=False, zeroline=False,
                     range=x_range, row=2, col=1)
    fig.update_yaxes(title_text=_bold(f"Mean {y_title}", ax['bold']), title_font=axis_title_font,
                     tickfont=axis_tick_font, showgrid=True,
                     gridcolor=grid_color, zeroline=False, row=1, col=1)
    fig.update_yaxes(title_text=_bold(f"Std Dev {y_title}", ax['bold']), title_font=axis_title_font,
                     tickfont=axis_tick_font, showgrid=True,
                     gridcolor=grid_color, zeroline=False, row=2, col=1)

    for ann in fig['layout']['annotations']:
        if ann['text'] in ("Accuracy (X-Bar)", "Precision (S-Chart)"):
            ann['font'] = dict(size=subplot_size, color='rgba(255,255,255,0.7)')

    return fig


# White-background-friendly qualitative palette for overlaid trend lines.
_TREND_COLORS = [
    '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
    '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#7f7f7f',
]


def plot_roughness_trend(df: pd.DataFrame, metric_col: str, lot_col: str,
                         series_cols: list, title: str = "",
                         measurement_unit: str = None, style: dict = None) -> go.Figure:
    """Lot-over-lot trend of the per-lot mean, one line per series combination.

    X axis is Lot Number (sorted); each point is the mean of ``metric_col`` for
    that lot. ``series_cols`` are the columns whose combined value defines each
    line — e.g. ``[buildup_col, side_col, process_col]`` yields lines such as
    "BU01 · Front · Post AOP", all overlaid on one chart with a legend. This is
    the *between-lot* counterpart to the box/control charts (within-lot spread).

    Rendered on a plain white background (independent of the dark theme). Sizes
    and fonts still come from the optional ``style`` dict (CHART_SETTINGS).
    """
    fam = _sty(style, 'font_family', default='Inter, sans-serif')
    title_size = _sty(style, 'title_size', default=17)
    ax_title_size = _sty(style, 'axis', 'title_size', default=14)
    ax_tick_size = _sty(style, 'axis', 'tick_size', default=12)
    height = _sty(style, 'control', 'height', default=600)
    msize = _sty(style, 'control', 'marker_size', default=9)

    INK = '#333333'
    GRID = '#e6e6e6'

    work = df.copy()
    work[metric_col] = pd.to_numeric(work[metric_col], errors='coerce')
    work = work.dropna(subset=[metric_col])
    if work.empty:
        fig = go.Figure()
        fig.update_layout(title=f"No data for {title}",
                          plot_bgcolor='white', paper_bgcolor='white')
        return fig

    work[lot_col] = work[lot_col].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()
    lots = sorted(work[lot_col].dropna().unique().tolist())
    if len(lots) < 2:
        fig = go.Figure()
        fig.update_layout(
            title=(f"{title}: need ≥2 lots for a trend (got {len(lots)}). "
                   f"Use the Box Plot or Control Chart."),
            plot_bgcolor='white', paper_bgcolor='white')
        return fig

    cols = [c for c in (series_cols or []) if c and c in work.columns]
    for c in cols:
        work[c] = work[c].astype(str).str.replace(r'\.0$', '', regex=True).str.strip()

    if cols:
        keys = sorted(work.groupby(cols).groups.keys(),
                      key=lambda k: k if isinstance(k, tuple) else (k,))
    else:
        keys = [None]

    fig = go.Figure()
    for i, key in enumerate(keys):
        if cols:
            kv = key if isinstance(key, tuple) else (key,)
            mask = pd.Series(True, index=work.index)
            for c, v in zip(cols, kv):
                mask &= (work[c] == v)
            s_df = work[mask]
            label = " · ".join(str(v) for v in kv)
        else:
            s_df = work
            label = "All"

        grp = s_df.groupby(lot_col)[metric_col]
        means = grp.mean().reindex(lots)
        counts = grp.size().reindex(lots).fillna(0).astype(int)
        color = _TREND_COLORS[i % len(_TREND_COLORS)]

        fig.add_trace(go.Scatter(
            x=lots, y=means.tolist(), mode='lines+markers', name=f"<b>{label}</b>",
            line=dict(color=color, width=2),
            marker=dict(color=color, size=msize),
            connectgaps=True,
            customdata=counts.to_numpy(),
            hovertemplate=("Lot %{x}<br>Mean %{y:.2f}"
                           " (n=%{customdata})<extra>" + label + "</extra>")))

    y_title = f"{metric_col} ({measurement_unit})" if measurement_unit else metric_col
    big_axis_size = ax_title_size + 4   # larger, bolder axis titles
    big_legend_size = ax_tick_size + 4  # larger, bolder legend entries

    fig.update_layout(
        title=dict(text=f"<b>{title} (Lot Trend)</b>",
                   font=dict(color=INK, size=title_size), x=0.5, xanchor='center'),
        height=height, margin=dict(l=70, r=190, t=70, b=70),
        showlegend=True,
        legend=dict(orientation='v', xanchor='left', x=1.02, yanchor='top', y=1.0,
                    font=dict(color=INK, size=big_legend_size)),
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family=fam, color=INK))
    fig.update_xaxes(title_text="<b>Lot Number</b>",
                     title_font=dict(color=INK, size=big_axis_size),
                     type='category', categoryorder='array', categoryarray=lots,
                     tickfont=dict(color=INK, size=ax_tick_size),
                     showgrid=False, zeroline=False,
                     showline=True, linecolor=GRID, mirror=True)
    fig.update_yaxes(title_text=f"<b>Mean {y_title}</b>",
                     title_font=dict(color=INK, size=big_axis_size),
                     tickfont=dict(color=INK, size=ax_tick_size),
                     showgrid=True, gridcolor=GRID, zeroline=False,
                     showline=True, linecolor=GRID, mirror=True)
    return fig
