import os
import yaml
import plotly.graph_objects as go


def get_rounded_rect_path(x0: float, y0: float, x1: float, y1: float, r: float) -> str:
    """Generates an SVG path string for a rounded rectangle."""
    width = x1 - x0
    height = y1 - y0
    r = min(r, width / 2, height / 2)

    return (
        f"M {x0+r} {y0} "
        f"L {x1-r} {y0} "
        f"Q {x1} {y0} {x1} {y0+r} "
        f"L {x1} {y1-r} "
        f"Q {x1} {y1} {x1-r} {y1} "
        f"L {x0+r} {y1} "
        f"Q {x0} {y1} {x0} {y1-r} "
        f"L {x0} {y0+r} "
        f"Q {x0} {y0} {x0+r} {y0} "
        "Z"
    )


def _build_vtp_key(block_index: int) -> str:
    """Convert a 0-15 block index back to its Via-to-Pad array notation [r,c][x,y]."""
    quadrant = block_index // 4        # 0=LL, 1=UL, 2=LR, 3=UR → maps to [1,1],[1,2],[2,1],[2,2]
    position = block_index % 4         # 0-3 within quadrant
    quad_map = {0: (1, 1), 1: (1, 2), 2: (2, 1), 3: (2, 2)}
    pos_map  = {0: (1, 1), 1: (1, 2), 2: (2, 1), 3: (2, 2)}
    qr, qc = quad_map[quadrant]
    pr, pc = pos_map[position]
    return f"[{qr},{qc}][{pr},{pc}]"


def create_four_quarters_view(settings: dict) -> go.Figure:
    pv = settings.get('PANEL_VIEW', {})
    colors = settings.get('COLORS', {})
    fig_cfg = settings.get('FIGURE_SETTINGS', {})

    # --- Geometry ---
    FRAME_WIDTH     = pv.get('frame_width', 510.0)
    FRAME_HEIGHT    = pv.get('frame_height', 515.0)
    OFFSET_X        = pv.get('offset_x', 13.5)
    OFFSET_Y        = pv.get('offset_y', 15.0)
    GAP_X           = pv.get('gap_x', 3.0)
    GAP_Y           = pv.get('gap_y', 3.0)
    DYNAMIC_GAP_X   = pv.get('dynamic_gap_x', 5.0)
    DYNAMIC_GAP_Y   = pv.get('dynamic_gap_y', 3.5)
    CORNER_RADIUS   = pv.get('corner_radius', 20.0)
    POINT_MARGIN    = pv.get('point_margin_factor', 0.20)

    # --- Colors ---
    PANEL_BG_COLOR  = colors.get('panel_body', '#C87533')
    QUADRANT_COLOR  = colors.get('quadrant_fill', '#F4B486')
    GRID_COLOR      = colors.get('grid_border', '#8B4513')
    BG_COLOR        = colors.get('background', '#2C3E50')

    # --- Figure settings ---
    FIG_WIDTH       = fig_cfg.get('width') or 800
    FIG_HEIGHT      = fig_cfg.get('height') or 800
    FIG_MARGIN      = fig_cfg.get('margin', 40)
    MARKER_SIZE     = fig_cfg.get('point_marker_size', 35)
    TEXT_SIZE       = fig_cfg.get('point_text_size', 14)

    # --- Layout Calculations ---
    effective_gap_x = GAP_X + 2 * DYNAMIC_GAP_X
    effective_gap_y = GAP_Y + 2 * DYNAMIC_GAP_Y

    p_width  = FRAME_WIDTH  - 2 * OFFSET_X - GAP_X  - 4 * DYNAMIC_GAP_X
    p_height = FRAME_HEIGHT - 2 * OFFSET_Y - GAP_Y  - 4 * DYNAMIC_GAP_Y

    quad_width  = p_width  / 2.0
    quad_height = p_height / 2.0

    total_off_x = OFFSET_X + DYNAMIC_GAP_X
    total_off_y = OFFSET_Y + DYNAMIC_GAP_Y

    origins = {
        'LL': (total_off_x, total_off_y),
        'LR': (total_off_x + quad_width + effective_gap_x, total_off_y),
        'UL': (total_off_x, total_off_y + quad_height + effective_gap_y),
        'UR': (total_off_x + quad_width + effective_gap_x, total_off_y + quad_height + effective_gap_y),
    }

    # --- Shapes ---
    shapes = []

    shapes.append(dict(
        type="path",
        path=get_rounded_rect_path(0, 0, FRAME_WIDTH, FRAME_HEIGHT, CORNER_RADIUS),
        fillcolor=PANEL_BG_COLOR,
        line=dict(color=GRID_COLOR, width=3),
        layer='below',
    ))

    for _name, (x_start, y_start) in origins.items():
        shapes.append(dict(
            type="rect",
            x0=x_start,
            y0=y_start,
            x1=x_start + quad_width,
            y1=y_start + quad_height,
            fillcolor=QUADRANT_COLOR,
            line=dict(color=GRID_COLOR, width=3),
            layer='below',
        ))

    # --- Hover lookup: grid_id → (named_location, vtp_array_key) ---
    grid_mapping = settings.get('GRID_MAPPING', {})
    positional_mapping = settings.get('POSITIONAL_MAPPING', [])
    # Reverse GRID_MAPPING: int(grid_id) → "LL_2"
    id_to_name = {int(v): k for k, v in grid_mapping.items()}
    # Reverse POSITIONAL_MAPPING: int(grid_id) → "[1,1][1,1]"
    id_to_vtp = {int(gid): _build_vtp_key(idx) for idx, gid in enumerate(positional_mapping)}

    # --- Grid Points ---
    point_x, point_y, point_text, point_hover = [], [], [], []
    margin_x = quad_width  * POINT_MARGIN
    margin_y = quad_height * POINT_MARGIN

    def add_points(prefix, x_start, y_start):
        coords = [
            (x_start + margin_x,              y_start + quad_height - margin_y),  # 1: Top-Left
            (x_start + margin_x,              y_start + margin_y),                 # 2: Bottom-Left
            (x_start + quad_width - margin_x, y_start + margin_y),                # 3: Bottom-Right
            (x_start + quad_width - margin_x, y_start + quad_height - margin_y),  # 4: Top-Right
        ]
        for i, (px, py) in enumerate(coords, start=1):
            gid = int(f"{prefix}{i}")
            point_x.append(px)
            point_y.append(py)
            point_text.append(str(gid))
            named = id_to_name.get(gid, "")
            vtp = id_to_vtp.get(gid, "")
            point_hover.append(f"<b>Grid ID:</b> {gid}<br><b>Location:</b> {named}<br><b>VtP Index:</b> {vtp}")

    # Counter-Clockwise factory mapping: 1=UL, 2=LL, 3=LR, 4=UR
    add_points('1', origins['UL'][0], origins['UL'][1])
    add_points('2', origins['LL'][0], origins['LL'][1])
    add_points('3', origins['LR'][0], origins['LR'][1])
    add_points('4', origins['UR'][0], origins['UR'][1])

    # --- Figure ---
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=point_x,
        y=point_y,
        mode='markers+text',
        text=point_text,
        textposition='middle center',
        marker=dict(size=MARKER_SIZE, color='white', line=dict(color=GRID_COLOR, width=2)),
        textfont=dict(size=TEXT_SIZE, color='black', family='Arial Black'),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=point_hover,
    ))

    fig.update_layout(
        shapes=shapes,
        paper_bgcolor=BG_COLOR,
        plot_bgcolor=BG_COLOR,
        width=FIG_WIDTH,
        height=FIG_HEIGHT,
        showlegend=False,
        xaxis=dict(range=[-10, FRAME_WIDTH + 10], constrain='domain', visible=False),
        yaxis=dict(range=[-10, FRAME_HEIGHT + 10], scaleanchor="x", scaleratio=1, visible=False),
        margin=dict(l=FIG_MARGIN, r=FIG_MARGIN, t=FIG_MARGIN, b=FIG_MARGIN),
    )

    return fig


def _load_settings() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), 'config', 'settings.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


if __name__ == "__main__":
    fig = create_four_quarters_view(_load_settings())
    fig.show(renderer="browser")