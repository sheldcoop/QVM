"""Helper to locate the panel background image asset."""

import os


def get_panel_image_path() -> str:
    """Return the absolute path to the panel background image.

    ``__file__`` lives at ``qvm_dashboard/src/visuals/panel_image.py``; three
    ``dirname`` hops reach the ``qvm_dashboard`` package root.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base_dir, 'assets', 'panel_background.png')
