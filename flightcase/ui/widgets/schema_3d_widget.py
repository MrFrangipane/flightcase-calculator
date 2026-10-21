"""Interactive 3D Axonometric / Isometric Schema Widget without Perspective."""

from __future__ import annotations
import math
from typing import Optional, List, Tuple
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPainterPath,
    QPolygonF,
    QMouseEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QCheckBox,
    QFrame,
    QToolTip,
)

from ...domain import (
    Point3D,
    Segment3D,
    DimensionCallout3D,
    WireframeMesh3D,
    ParallelProjector,
)
from ..theme import COLORS


class Schema3DCanvas(QWidget):
    """QPainter canvas rendering 3D wireframe mesh and dimensions without perspective."""

    view_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(400, 350)
        self.setMouseTracking(True)

        # Projection angles
        self.azimuth_deg: float = 45.0
        self.elevation_deg: float = 30.0
        self.zoom_factor: float = 1.0
        self.pan_offset_x: float = 0.0
        self.pan_offset_y: float = 0.0

        # Rendering options
        self.show_dimensions: bool = True
        self.show_inside_walls: bool = True
        self.show_axes: bool = True

        # Data
        self.mesh: Optional[WireframeMesh3D] = None

        # Mouse interaction state
        self._last_mouse_pos: Optional[QPoint] = None
        self._mouse_button_down: Optional[Qt.MouseButton] = None

    def set_mesh(self, mesh: WireframeMesh3D) -> None:
        self.mesh = mesh
        self.update()

    def reset_view(self, azimuth: float = 45.0, elevation: float = 30.0) -> None:
        self.azimuth_deg = azimuth
        self.elevation_deg = elevation
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.update()
        self.view_changed.emit()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = event.pos()
        self._mouse_button_down = event.button()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._last_mouse_pos is not None and self._mouse_button_down is not None:
            delta = event.pos() - self._last_mouse_pos
            self._last_mouse_pos = event.pos()

            if self._mouse_button_down == Qt.LeftButton:
                # Orbit rotation
                self.azimuth_deg = (self.azimuth_deg + delta.x() * 0.5) % 360.0
                self.elevation_deg = max(-89.0, min(89.0, self.elevation_deg - delta.y() * 0.5))
                self.update()
                self.view_changed.emit()
            elif self._mouse_button_down in (Qt.RightButton, Qt.MiddleButton):
                # Pan translation
                self.pan_offset_x += delta.x()
                self.pan_offset_y += delta.y()
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = None
        self._mouse_button_down = None

    def wheelEvent(self, event: QWheelEvent) -> None:
        num_degrees = event.angleDelta().y() / 8.0
        num_steps = num_degrees / 15.0
        scale = 1.15 ** num_steps
        self.zoom_factor = max(0.2, min(5.0, self.zoom_factor * scale))
        self.update()
        self.view_changed.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w, h = self.width(), self.height()

        # 1. Background
        painter.fillRect(self.rect(), QColor(COLORS["bg_schema"]))

        if not self.mesh:
            painter.setPen(QColor("#7a7a90"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No flightcase geometry to display")
            return

        # 2. Compute Auto-Fit Scale
        p_min, p_max = self.mesh.bounding_box
        diag_x = p_max.x - p_min.x
        diag_y = p_max.y - p_min.y
        diag_z = p_max.z - p_min.z
        max_dim = max(100.0, math.sqrt(diag_x**2 + diag_y**2 + diag_z**2))

        base_scale = (min(w, h) * 0.55) / max_dim
        scale = base_scale * self.zoom_factor

        # Center of bounding box in 3D
        center_3d = Point3D(
            (p_min.x + p_max.x) / 2.0,
            (p_min.y + p_max.y) / 2.0,
            (p_min.z + p_max.z) / 2.0,
        )

        origin_x = w / 2.0 + self.pan_offset_x
        origin_y = h / 2.0 + self.pan_offset_y

        projector = ParallelProjector(
            azimuth_deg=self.azimuth_deg,
            elevation_deg=self.elevation_deg,
            scale=scale,
            origin_screen_x=origin_x,
            origin_screen_y=origin_y,
        )

        # Center projection offset
        c_sx, c_sy, _ = projector.project_point(center_3d)
        dx_shift = origin_x - c_sx
        dy_shift = origin_y - c_sy

        projector.origin_screen_x += dx_shift
        projector.origin_screen_y += dy_shift

        # 3. Draw Background Grid / Center Ground Marker
        self._draw_ground_grid(painter, projector, p_max)

        # 4. Draw 3D Segments (Base, Lid, Profiles, Walls)
        for seg in self.mesh.segments:
            p1_sx, p1_sy, _ = projector.project_point(seg.p1)
            p2_sx, p2_sy, _ = projector.project_point(seg.p2)

            pen = self._get_pen_for_segment(seg)
            painter.setPen(pen)
            painter.drawLine(QPointF(p1_sx, p1_sy), QPointF(p2_sx, p2_sy))

        # 5. Draw Dimension Callouts & Leader Lines
        if self.show_dimensions:
            for dim in self.mesh.dimensions:
                self._draw_dimension_callout(painter, projector, dim)

        # 6. Draw 3D Coordinate Axis Indicator (Bottom Left)
        if self.show_axes:
            self._draw_axis_triad(painter)

        # 7. Draw HUD Overlay (Angles, Scale, Projection Label)
        self._draw_hud(painter)

    def _draw_ground_grid(self, painter: QPainter, projector: ParallelProjector, p_max: Point3D) -> None:
        grid_pen = QPen(QColor(COLORS["grid_line"]), 1, Qt.DotLine)
        painter.setPen(grid_pen)

        span_x = max(200.0, p_max.x * 1.3)
        span_y = max(200.0, p_max.y * 1.3)
        step = 100.0

        x_start = -50.0
        y_start = -50.0

        for x in range(int(x_start), int(span_x + step), int(step)):
            p1_x, p1_y, _ = projector.project_point(Point3D(x, y_start, 0))
            p2_x, p2_y, _ = projector.project_point(Point3D(x, span_y, 0))
            painter.drawLine(QPointF(p1_x, p1_y), QPointF(p2_x, p2_y))

        for y in range(int(y_start), int(span_y + step), int(step)):
            p1_x, p1_y, _ = projector.project_point(Point3D(x_start, y, 0))
            p2_x, p2_y, _ = projector.project_point(Point3D(span_x, y, 0))
            painter.drawLine(QPointF(p1_x, p1_y), QPointF(p2_x, p2_y))

    def _get_pen_for_segment(self, seg: Segment3D) -> QPen:
        color = QColor(COLORS["base_edge"])
        width = 2.0
        style = Qt.SolidLine

        if seg.color_group == "lid":
            color = QColor(COLORS["lid_edge"])
            width = 2.0
        elif seg.color_group == "profile":
            color = QColor(COLORS["profile_edge"])
            width = 3.0
        elif seg.color_group == "wall":
            color = QColor(COLORS["wall_edge"])
            width = 2.2
        elif seg.color_group == "inner":
            color = QColor(COLORS["inner_edge"])
            width = 1.2
            style = Qt.DashLine

        if seg.style == "dashed":
            style = Qt.DashLine

        pen = QPen(color, width, style)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        return pen

    def _draw_dimension_callout(
        self,
        painter: QPainter,
        projector: ParallelProjector,
        dim: DimensionCallout3D
    ) -> None:
        # 3D points
        p1 = dim.start
        p2 = dim.end
        ox, oy, oz = dim.offset_vector

        p1_off = Point3D(p1.x + ox, p1.y + oy, p1.z + oz)
        p2_off = Point3D(p2.x + ox, p2.y + oy, p2.z + oz)

        # 2D Projected points
        p1_s = QPointF(*projector.project_point(p1)[:2])
        p2_s = QPointF(*projector.project_point(p2)[:2])
        p1_off_s = QPointF(*projector.project_point(p1_off)[:2])
        p2_off_s = QPointF(*projector.project_point(p2_off)[:2])

        # Witness Extension Lines (thin)
        witness_pen = QPen(QColor("#64748b"), 1.0, Qt.DotLine)
        painter.setPen(witness_pen)
        painter.drawLine(p1_s, p1_off_s)
        painter.drawLine(p2_s, p2_off_s)

        # Main Dimension Line
        dim_pen = QPen(QColor(COLORS["dim_line"]), 1.5, Qt.SolidLine)
        painter.setPen(dim_pen)
        painter.drawLine(p1_off_s, p2_off_s)

        # Dimension End Ticks / Arrows
        self._draw_arrow_tick(painter, p1_off_s, p2_off_s)
        self._draw_arrow_tick(painter, p2_off_s, p1_off_s)

        # Dimension Text Label with pill background
        mid_s = QPointF((p1_off_s.x() + p2_off_s.x()) / 2.0, (p1_off_s.y() + p2_off_s.y()) / 2.0)
        
        font = QFont("Segoe UI", 10, QFont.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(dim.label)

        padding_x = 6
        padding_y = 3
        badge_w = text_rect.width() + padding_x * 2
        badge_h = text_rect.height() + padding_y * 2
        badge_rect = QRectF(
            mid_s.x() - badge_w / 2.0,
            mid_s.y() - badge_h / 2.0,
            badge_w,
            badge_h
        )

        painter.setPen(QPen(QColor("#454558"), 1))
        painter.setBrush(QBrush(QColor("#1e1e28")))
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(QColor(COLORS["dim_text"]))
        painter.drawText(badge_rect, Qt.AlignCenter, dim.label)

    def _draw_arrow_tick(self, painter: QPainter, tip: QPointF, other: QPointF) -> None:
        dx = other.x() - tip.x()
        dy = other.y() - tip.y()
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            return

        ux = dx / dist
        uy = dy / dist
        vx = -uy
        vy = ux

        arrow_len = 6.0
        arrow_w = 3.5

        p1 = tip + QPointF(ux * arrow_len + vx * arrow_w, uy * arrow_len + vy * arrow_w)
        p2 = tip + QPointF(ux * arrow_len - vx * arrow_w, uy * arrow_len - vy * arrow_w)

        poly = QPolygonF([tip, p1, p2])
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(COLORS["dim_line"])))
        painter.drawPolygon(poly)

    def _draw_axis_triad(self, painter: QPainter) -> None:
        margin_x = 45.0
        margin_y = self.height() - 45.0
        axis_len = 30.0

        projector = ParallelProjector(
            azimuth_deg=self.azimuth_deg,
            elevation_deg=self.elevation_deg,
            scale=1.0,
            origin_screen_x=margin_x,
            origin_screen_y=margin_y,
        )

        origin_s = QPointF(margin_x, margin_y)
        x_s = QPointF(*projector.project_point(Point3D(axis_len, 0, 0))[:2])
        y_s = QPointF(*projector.project_point(Point3D(0, axis_len, 0))[:2])
        z_s = QPointF(*projector.project_point(Point3D(0, 0, axis_len))[:2])

        # X Axis (Red / Length)
        painter.setPen(QPen(QColor("#ef4444"), 2))
        painter.drawLine(origin_s, x_s)
        painter.drawText(x_s + QPointF(4, 4), "X (L)")

        # Y Axis (Green / Width)
        painter.setPen(QPen(QColor("#22c55e"), 2))
        painter.drawLine(origin_s, y_s)
        painter.drawText(y_s + QPointF(4, 4), "Y (W)")

        # Z Axis (Blue / Height)
        painter.setPen(QPen(QColor("#3b82f6"), 2))
        painter.drawLine(origin_s, z_s)
        painter.drawText(z_s + QPointF(4, -4), "Z (H)")

    def _draw_hud(self, painter: QPainter) -> None:
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#9e9eb4"))
        info = f"Parallel Ortho 3D | Azimuth: {self.azimuth_deg:.0f}° | Elevation: {self.elevation_deg:.0f}° | Zoom: {self.zoom_factor:.2f}x"
        painter.drawText(12, 20, info)


class Schema3DWidget(QWidget):
    """Complete 3D Schema panel with interactive toolbar and canvas."""

    lid_exploded_changed = Signal(float)
    toggles_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.canvas = Schema3DCanvas(self)
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Toolbar Frame
        toolbar = QFrame(self)
        toolbar.setStyleSheet("background-color: #25252e; border-radius: 6px; padding: 4px;")
        t_layout = QHBoxLayout(toolbar)
        t_layout.setContentsMargins(8, 4, 8, 4)
        t_layout.setSpacing(10)

        # View Preset Buttons
        btn_iso = QPushButton("Isometric View", self)
        btn_iso.setObjectName("secondaryButton")
        btn_iso.clicked.connect(lambda: self.canvas.reset_view(45.0, 30.0))

        btn_front = QPushButton("Front", self)
        btn_front.setObjectName("secondaryButton")
        btn_front.clicked.connect(lambda: self.canvas.reset_view(0.0, 0.0))

        btn_side = QPushButton("Side", self)
        btn_side.setObjectName("secondaryButton")
        btn_side.clicked.connect(lambda: self.canvas.reset_view(90.0, 0.0))

        btn_top = QPushButton("Top", self)
        btn_top.setObjectName("secondaryButton")
        btn_top.clicked.connect(lambda: self.canvas.reset_view(0.0, 89.0))

        t_layout.addWidget(QLabel("<b>View Presets:</b>"))
        t_layout.addWidget(btn_iso)
        t_layout.addWidget(btn_front)
        t_layout.addWidget(btn_side)
        t_layout.addWidget(btn_top)

        t_layout.addSpacing(12)

        # Exploded Lid Slider
        t_layout.addWidget(QLabel("<b>Lid Split Gap:</b>"))
        self.slider_gap = QSlider(Qt.Horizontal, self)
        self.slider_gap.setRange(0, 200)
        self.slider_gap.setValue(0)
        self.slider_gap.setFixedWidth(120)
        self.slider_gap.setToolTip("Exploded lid view gap in mm")
        self.lbl_gap = QLabel("0 mm")
        self.slider_gap.valueChanged.connect(self._on_gap_changed)
        t_layout.addWidget(self.slider_gap)
        t_layout.addWidget(self.lbl_gap)

        t_layout.addSpacing(12)

        # Checkboxes
        self.chk_dims = QCheckBox("Dimensions", self)
        self.chk_dims.setChecked(True)
        self.chk_dims.toggled.connect(self._on_toggles_changed)

        self.chk_walls = QCheckBox("Inside Walls", self)
        self.chk_walls.setChecked(True)
        self.chk_walls.toggled.connect(self._on_toggles_changed)

        t_layout.addWidget(self.chk_dims)
        t_layout.addWidget(self.chk_walls)
        t_layout.addStretch()

        layout.addWidget(toolbar)
        layout.addWidget(self.canvas, 1)

    def _on_gap_changed(self, val: int) -> None:
        self.lbl_gap.setText(f"{val} mm")
        self.lid_exploded_changed.emit(float(val))

    def _on_toggles_changed(self) -> None:
        self.canvas.show_dimensions = self.chk_dims.isChecked()
        self.canvas.show_inside_walls = self.chk_walls.isChecked()
        self.toggles_changed.emit()
        self.canvas.update()

    def set_mesh(self, mesh: WireframeMesh3D) -> None:
        self.canvas.set_mesh(mesh)

    @property
    def exploded_gap_mm(self) -> float:
        return float(self.slider_gap.value())

    @property
    def show_dimensions(self) -> bool:
        return self.chk_dims.isChecked()

    @property
    def show_inside_walls(self) -> bool:
        return self.chk_walls.isChecked()
