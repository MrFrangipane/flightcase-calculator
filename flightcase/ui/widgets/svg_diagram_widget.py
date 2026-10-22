"""Interactive SVG viewer and exporter widget for Flightcase wood panels."""

from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QByteArray, QSize, QPointF, Signal
from PySide6.QtGui import (
    QWheelEvent,
    QMouseEvent,
    QPainter,
    QCursor,
    QColor,
    QBrush,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QGraphicsView,
    QGraphicsScene,
    QFileDialog,
    QMessageBox,
    QApplication,
    QFrame,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtSvgWidgets import QGraphicsSvgItem


class SvgPanZoomView(QGraphicsView):
    """
    High-performance 2D vector viewport providing interactive click-and-drag panning,
    cursor-anchored mouse wheel zooming, fit-to-view, and smooth navigation.
    """

    zoom_changed = Signal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        self._svg_renderer = QSvgRenderer(self)
        self._svg_item = QGraphicsSvgItem()
        self._scene.addItem(self._svg_item)

        self._zoom_factor: float = 1.0
        self._is_middle_panning: bool = False
        self._last_mouse_pos: Optional[QPointF] = None

        # Viewport rendering properties
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setBackgroundBrush(QBrush(QColor(70, 70, 70)))

    def renderer(self) -> QSvgRenderer:
        """Returns the underlying QSvgRenderer."""
        return self._svg_renderer

    def set_svg_data(self, svg_str: str) -> None:
        """Loads SVG markup into renderer and updates scene bounds."""
        if not svg_str:
            self._svg_item.setVisible(False)
            return

        byte_arr = QByteArray(svg_str.encode("utf-8"))
        self._svg_renderer.load(byte_arr)
        if self._svg_renderer.isValid():
            self._svg_item.setSharedRenderer(self._svg_renderer)
            self._svg_item.setVisible(True)

            view_box = self._svg_renderer.viewBoxF()
            if not view_box.isEmpty() and view_box.width() > 0:
                self._scene.setSceneRect(view_box)
            else:
                default_sz = self._svg_renderer.defaultSize()
                self._scene.setSceneRect(0, 0, max(100.0, default_sz.width()), max(100.0, default_sz.height()))

    def wheelEvent(self, event: QWheelEvent) -> None:
        """Zooms smoothly in or out anchored at the mouse cursor position."""
        delta = event.angleDelta().y()
        if delta > 0:
            self.zoom_by(1.15)
        elif delta < 0:
            self.zoom_by(1.0 / 1.15)
        event.accept()

    def zoom_by(self, scale_multiplier: float) -> None:
        """Scales view by a relative multiplier within constrained limits."""
        new_factor = self._zoom_factor * scale_multiplier
        if 0.05 <= new_factor <= 20.0:
            self.scale(scale_multiplier, scale_multiplier)
            self._zoom_factor = new_factor
            self.zoom_changed.emit(self._zoom_factor)

    def set_zoom(self, target_factor: float) -> None:
        """Sets absolute zoom factor."""
        target_factor = max(0.05, min(20.0, target_factor))
        if self._zoom_factor <= 0.0:
            self._zoom_factor = 1.0
        multiplier = target_factor / self._zoom_factor
        self.scale(multiplier, multiplier)
        self._zoom_factor = target_factor
        self.zoom_changed.emit(self._zoom_factor)

    def reset_zoom(self) -> None:
        """Resets transform matrix to 1.0 (100% scale) and centers scene."""
        self.resetTransform()
        self._zoom_factor = 1.0
        self.zoom_changed.emit(self._zoom_factor)
        if not self._scene.sceneRect().isEmpty():
            self.centerOn(self._scene.sceneRect().center())

    def fit_to_view(self) -> None:
        """Scales and centers scene to fit within current viewport boundaries."""
        rect = self._scene.sceneRect()
        if not rect.isEmpty() and rect.width() > 0 and rect.height() > 0:
            # Margin padding around diagram
            padded_rect = rect.adjusted(-30, -30, 30, 30)
            self.fitInView(padded_rect, Qt.AspectRatioMode.KeepAspectRatio)
            t = self.transform()
            self._zoom_factor = round(t.m11(), 3)
            self.zoom_changed.emit(self._zoom_factor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handles middle mouse button panning initiation."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_middle_panning = True
            self._last_mouse_pos = event.position()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handles middle mouse button dragging for panning."""
        if self._is_middle_panning and self._last_mouse_pos is not None:
            delta = event.position() - self._last_mouse_pos
            self._last_mouse_pos = event.position()
            self.horizontalScrollBar().setValue(int(self.horizontalScrollBar().value() - delta.x()))
            self.verticalScrollBar().setValue(int(self.verticalScrollBar().value() - delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Ends middle mouse button panning."""
        if event.button() == Qt.MouseButton.MiddleButton:
            self._is_middle_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        """Double click resets view to fit entire diagram."""
        self.fit_to_view()
        event.accept()


class WoodPanelsSvgWidget(QWidget):
    """
    Dedicated view displaying a scalable 2D technical SVG diagram of all wood panels
    with their cut dimensions, quantities, and material specs, along with export options
    and 2D pan/zoom controls.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._svg_data: str = ""
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Top Action Toolbar
        toolbar = QFrame(self)
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

        # 2D Zoom Controls
        t_layout.addWidget(QLabel("<b>Zoom:</b>"))
        btn_zoom_out = QPushButton("−", self)
        btn_zoom_out.setFixedWidth(32)
        btn_zoom_out.setToolTip("Zoom Out (Wheel Down)")
        btn_zoom_out.clicked.connect(self._zoom_out)
        t_layout.addWidget(btn_zoom_out)

        self.lbl_zoom = QLabel("100%")
        self.lbl_zoom.setFixedWidth(50)
        self.lbl_zoom.setAlignment(Qt.AlignmentFlag.AlignCenter)
        t_layout.addWidget(self.lbl_zoom)

        btn_zoom_in = QPushButton("+", self)
        btn_zoom_in.setFixedWidth(32)
        btn_zoom_in.setToolTip("Zoom In (Wheel Up)")
        btn_zoom_in.clicked.connect(self._zoom_in)
        t_layout.addWidget(btn_zoom_in)

        btn_fit_view = QPushButton("Fit View", self)
        btn_fit_view.setObjectName("secondaryButton")
        btn_fit_view.setToolTip("Fit complete diagram into viewport (Double-Click)")
        btn_fit_view.clicked.connect(self.fit_to_view)
        t_layout.addWidget(btn_fit_view)

        btn_reset_zoom = QPushButton("Reset (100%)", self)
        btn_reset_zoom.setObjectName("secondaryButton")
        btn_reset_zoom.setToolTip("Reset zoom level to 100%")
        btn_reset_zoom.clicked.connect(self._reset_zoom)
        t_layout.addWidget(btn_reset_zoom)

        t_layout.addSpacing(16)
        hint_label = QLabel("Drag to Pan • Wheel to Zoom • Double-Click to Fit")
        t_layout.addWidget(hint_label)

        t_layout.addStretch()
        layout.addWidget(toolbar)

        # Interactive 2D Graphics Viewport
        self.svg_view = SvgPanZoomView(self)
        self.svg_view.zoom_changed.connect(self._on_zoom_changed)
        layout.addWidget(self.svg_view, 1)

    @property
    def _zoom_factor(self) -> float:
        """Current zoom factor."""
        return self.svg_view._zoom_factor

    @_zoom_factor.setter
    def _zoom_factor(self, value: float) -> None:
        self.svg_view.set_zoom(value)

    def set_svg(self, svg_str: str) -> None:
        """Loads and renders new SVG content in the viewport."""
        self._svg_data = svg_str
        self.svg_view.set_svg_data(svg_str)

    def get_svg_data(self) -> str:
        """Returns active SVG XML string."""
        return self._svg_data

    def _on_zoom_changed(self, factor: float) -> None:
        """Updates zoom percentage indicator label."""
        self.lbl_zoom.setText(f"{int(round(factor * 100))}%")

    def _zoom_in(self) -> None:
        """Zoom in by 20%."""
        self.svg_view.zoom_by(1.2)

    def _zoom_out(self) -> None:
        """Zoom out by 20%."""
        self.svg_view.zoom_by(1.0 / 1.2)

    def _reset_zoom(self) -> None:
        """Resets zoom to 100%."""
        self.svg_view.reset_zoom()

    def fit_to_view(self) -> None:
        """Fits diagram to current view."""
        self.svg_view.fit_to_view()

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
