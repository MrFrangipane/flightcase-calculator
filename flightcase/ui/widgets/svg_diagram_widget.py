"""Interactive SVG viewer and exporter widget for Flightcase wood panels."""

from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QByteArray, QSize
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QScrollArea,
    QFileDialog,
    QMessageBox,
    QApplication,
    QFrame,
)
from PySide6.QtSvgWidgets import QSvgWidget


class WoodPanelsSvgWidget(QWidget):
    """
    Dedicated view displaying a scalable 2D technical SVG diagram of all wood panels
    with their cut dimensions, quantities, and material specs, along with export options.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._svg_data: str = ""
        self._zoom_factor: float = 1.0
        self._base_size: QSize = QSize(1048, 800)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top Action Toolbar
        toolbar = QFrame(self)
        toolbar.setStyleSheet("background-color: #25252e; border-radius: 6px; padding: 4px;")
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(8, 6, 8, 6)
        t_layout.setSpacing(10)

        # Export & Copy Buttons
        btn_export = QPushButton("Export SVG...", self)
        btn_export.setObjectName("primaryButton")
        btn_export.setToolTip("Save the wood panels diagram as a scalable SVG file")
        btn_export.clicked.connect(self.export_svg)
        t_layout.addWidget(btn_export)

        btn_copy = QPushButton("Copy SVG Code", self)
        btn_copy.setObjectName("secondaryButton")
        btn_copy.setToolTip("Copy raw SVG XML markup to clipboard")
        btn_copy.clicked.connect(self._copy_svg_to_clipboard)
        t_layout.addWidget(btn_copy)

        t_layout.addSpacing(16)

        # Zoom Controls
        t_layout.addWidget(QLabel("<b>Zoom:</b>"))
        btn_zoom_out = QPushButton("−", self)
        btn_zoom_out.setFixedWidth(32)
        btn_zoom_out.setToolTip("Zoom Out")
        btn_zoom_out.clicked.connect(self._zoom_out)
        t_layout.addWidget(btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(45)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_layout.addWidget(self.lbl_zoom)

        btn_zoom_in = QPushButton("+", self)
        btn_zoom_in.setFixedWidth(32)
        btn_zoom_in.setToolTip("Zoom In")
        btn_zoom_in.clicked.connect(self._zoom_in)
        t_layout.addWidget(btn_zoom_in)

        btn_reset_zoom = QPushButton("Reset (100%)", self)
        btn_reset_zoom.setObjectName("secondaryButton")
        btn_reset_zoom.clicked.connect(self._reset_zoom)
        t_layout.addWidget(btn_reset_zoom)

        t_layout.addStretch()
        layout.addWidget(toolbar)

        # Scroll Area containing the SVG Canvas
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setStyleSheet("background-color: #1e1e24; border: 1px solid #334155; border-radius: 6px;")

        self.svg_view = QSvgWidget(self.scroll_area)
        self.svg_view.setStyleSheet("background-color: transparent;")
        self.scroll_area.setWidget(self.svg_view)

        layout.addWidget(self.scroll_area, 1)

    def set_svg(self, svg_str: str) -> None:
        """Loads and renders new SVG content in the viewport."""
        self._svg_data = svg_str
        if not svg_str:
            return

        byte_arr = QByteArray(svg_str.encode("utf-8"))
        self.svg_view.load(byte_arr)

        renderer = self.svg_view.renderer()
        if renderer and renderer.isValid():
            view_box = renderer.viewBox()
            if view_box.isValid() and view_box.width() > 0 and view_box.height() > 0:
                self._base_size = QSize(view_box.width(), view_box.height())

        self._update_svg_size()

    def get_svg_data(self) -> str:
        """Returns active SVG XML string."""
        return self._svg_data

    def _update_svg_size(self) -> None:
        target_w = int(self._base_size.width() * self._zoom_factor)
        target_h = int(self._base_size.height() * self._zoom_factor)
        self.svg_view.setFixedSize(target_w, target_h)
        self.lbl_zoom.setText(f"{int(self._zoom_factor * 100)}%")

    def _zoom_in(self) -> None:
        if self._zoom_factor < 3.0:
            self._zoom_factor = min(3.0, round(self._zoom_factor + 0.15, 2))
            self._update_svg_size()

    def _zoom_out(self) -> None:
        if self._zoom_factor > 0.3:
            self._zoom_factor = max(0.3, round(self._zoom_factor - 0.15, 2))
            self._update_svg_size()

    def _reset_zoom(self) -> None:
        self._zoom_factor = 1.0
        self._update_svg_size()

    def _copy_svg_to_clipboard(self) -> None:
        if not self._svg_data:
            return
        QApplication.clipboard().setText(self._svg_data)
        QMessageBox.information(self, "Clipboard", "Wood panels SVG code copied to clipboard successfully.")

    def export_svg(self) -> None:
        """Opens file dialog and exports current wood panels SVG to disk."""
        if not self._svg_data:
            QMessageBox.warning(self, "Export SVG", "No wood panels data available to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Wood Panels SVG Diagram",
            "flightcase_wood_panels_diagram.svg",
            "SVG Files (*.svg);;All Files (*)",
        )
        if not file_path:
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self._svg_data)
            QMessageBox.information(
                self,
                "Export Successful",
                f"Wood panels SVG diagram saved successfully to:\n{file_path}"
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to export SVG file:\n{str(e)}"
            )
