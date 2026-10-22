"""UI styling, color palettes, and themes for Flightcase Calculator."""

from pathlib import Path

# Load central stylesheet from resources
_QSS_PATH = Path(__file__).resolve().parent.parent / "resources" / "dark-desktop.qss"
if _QSS_PATH.is_file():
    DARK_THEME_QSS = _QSS_PATH.read_text(encoding="utf-8")
else:
    DARK_THEME_QSS = ""

COLORS = {
    "bg_schema": "#18181f",
    "base_edge": "#3b82f6",       # Blue
    "base_fill": "#1e293b",       # Deep slate blue
    "lid_edge": "#06b6d4",        # Cyan
    "lid_fill": "#162e3b",        # Deep slate cyan
    "profile_edge": "#f59e0b",    # Amber/Gold
    "profile_fill": "#784d12",    # Warm bronze aluminum
    "wall_edge": "#ec4899",       # Pink/Magenta
    "wall_fill": "#3b1734",       # Deep magenta
    "endgrain_edge": "#60a5fa",   # Blue/slate edge highlight
    "endgrain_fill": "#334155",   # Wood panel thickness cross-section
    "highlight_edge": "#fde047",  # Bright glowing electric yellow/gold
    "highlight_fill": "#d97706",  # Rich glowing amber
    "highlight_endgrain_edge": "#fef08a",  # Brilliant yellow highlight
    "highlight_endgrain_fill": "#f59e0b",  # Radiant amber endgrain
    "inner_edge": "#64748b",      # Muted slate
    "dim_line": "#e2e8f0",        # Crisp white/silver
    "dim_text": "#fbbf24",        # Warm yellow
    "cut_line": "#f59e0b",        # Dashed cut line marking
    "grid_line": "#262633",
}
