"""UI styling, color palettes, and themes for Flightcase Calculator."""

DARK_THEME_QSS = """
QMainWindow, QDialog {
    background-color: #1e1e24;
    color: #f0f0f5;
    font-family: 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    background-color: #1e1e24;
    color: #e2e2ec;
    font-size: 13px;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #3a3a4c;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px;
    background-color: #25252e;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: #5e9eff;
}

QLabel {
    color: #cfcfe0;
}

QLineEdit, QDoubleSpinBox, QSpinBox, QComboBox {
    background-color: #2c2c38;
    border: 1px solid #454558;
    border-radius: 5px;
    padding: 6px 10px;
    color: #ffffff;
    selection-background-color: #3b82f6;
}

QLineEdit:focus, QDoubleSpinBox:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #5e9eff;
    background-color: #323240;
}

QPushButton {
    background-color: #3b82f6;
    color: #ffffff;
    font-weight: bold;
    border: none;
    border-radius: 6px;
    padding: 8px 16px;
}

QPushButton:hover {
    background-color: #2563eb;
}

QPushButton:pressed {
    background-color: #1d4ed8;
}

QPushButton:disabled {
    background-color: #3a3a4c;
    color: #7a7a90;
}

QPushButton#secondaryButton {
    background-color: #333342;
    color: #e2e2ec;
    border: 1px solid #4a4a5e;
}

QPushButton#secondaryButton:hover {
    background-color: #424254;
}

QTableWidget {
    background-color: #25252e;
    alternate-background-color: #2a2a35;
    gridline-color: #3a3a4c;
    border: 1px solid #3a3a4c;
    border-radius: 6px;
    color: #e2e2ec;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #2e2e3a;
    color: #5e9eff;
    font-weight: bold;
    padding: 6px;
    border: 1px solid #3a3a4c;
}

QTabWidget::pane {
    border: 1px solid #3a3a4c;
    background-color: #22222b;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #2a2a35;
    color: #9e9eb4;
    padding: 9px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    font-weight: bold;
}

QTabBar::tab:selected {
    background-color: #22222b;
    color: #5e9eff;
    border-bottom: 2px solid #5e9eff;
}

QTabBar::tab:hover:!selected {
    background-color: #333342;
    color: #ffffff;
}

QScrollBar:vertical {
    border: none;
    background: #1e1e24;
    width: 10px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #454558;
    min-height: 20px;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover {
    background: #5e9eff;
}

QSlider::groove:horizontal {
    border: 1px solid #3a3a4c;
    height: 6px;
    background: #2a2a35;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #3b82f6;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 1px solid #3b82f6;
    width: 14px;
    margin-top: -5px;
    margin-bottom: -5px;
    border-radius: 7px;
}

QCheckBox {
    spacing: 8px;
    color: #cfcfe0;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid #4a4a5e;
    background-color: #2a2a35;
}

QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
}

QStatusBar {
    background-color: #18181c;
    color: #9e9eb4;
    border-top: 1px solid #2e2e3a;
}
"""

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
    "grid_line": "#262633",
}
