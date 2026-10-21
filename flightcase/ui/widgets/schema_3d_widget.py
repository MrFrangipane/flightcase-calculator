"""Interactive 3D Hardware-Accelerated OpenGL Schema Widget with Projection Toggle."""

from __future__ import annotations
import math
from typing import Optional, Tuple
from PySide6.QtCore import Qt, QPoint, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QPainter,
    QPen,
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QPolygonF,
    QMouseEvent,
    QWheelEvent,
    QSurfaceFormat,
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
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL import GL, GLU

from ...domain import (
    Point3D,
    PolygonFace3D,
    DimensionCallout3D,
    WireframeMesh3D,
)
from ...application import UISettingsDTO
from ..theme import COLORS


class Schema3DCanvas(QOpenGLWidget):
    """
    Hardware-accelerated OpenGL viewport rendering flightcase 3D geometry with genuine
    Z-buffer depth testing, eliminating sorting artifacts and hidden lines.
    Supports real-time switching between Parallel (Orthographic) and Perspective projections.
    """

    view_changed = Signal()
    projection_changed = Signal(bool)  # True = Perspective, False = Parallel

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMinimumSize(400, 350)
        self.setMouseTracking(True)

        # Configure OpenGL surface format for hardware antialiasing (4x MSAA)
        gl_format = QSurfaceFormat()
        gl_format.setSamples(4)
        gl_format.setDepthBufferSize(24)
        self.setFormat(gl_format)

        # Camera & Projection state
        self.azimuth_deg: float = 45.0
        self.elevation_deg: float = 30.0
        self.zoom_factor: float = 1.0
        self.pan_offset_x: float = 0.0
        self.pan_offset_y: float = 0.0
        self.is_perspective: bool = False  # False = Parallel (Ortho), True = Perspective

        # Rendering options
        self.show_dimensions: bool = True
        self.show_inside_walls: bool = True
        self.show_axes: bool = True

        # Geometry Data
        self.mesh: Optional[WireframeMesh3D] = None

        # Highlight state for selected elements
        self.highlighted_wall_indices: set[int] = set()
        self.highlighted_labels: set[str] = set()

        # Mouse interaction state
        self._last_mouse_pos: Optional[QPoint] = None
        self._mouse_button_down: Optional[Qt.MouseButton] = None

    def set_mesh(self, mesh: WireframeMesh3D) -> None:
        """Sets flightcase 3D mesh and triggers a redraw."""
        self.mesh = mesh
        self.update()

    def set_perspective(self, is_perspective: bool) -> None:
        """Sets projection mode: True for Perspective, False for Parallel (Orthographic)."""
        if self.is_perspective != is_perspective:
            self.is_perspective = is_perspective
            self.update()
            self.projection_changed.emit(self.is_perspective)
            self.view_changed.emit()

    def toggle_projection(self) -> None:
        """Toggles between Parallel (Orthographic) and Perspective rendering."""
        self.set_perspective(not self.is_perspective)

    def reset_view(self, azimuth: float = 45.0, elevation: float = 30.0) -> None:
        """Resets camera orientation to specified angles and re-centers the view."""
        self.azimuth_deg = azimuth
        self.elevation_deg = elevation
        self.zoom_factor = 1.0
        self.pan_offset_x = 0.0
        self.pan_offset_y = 0.0
        self.update()
        self.view_changed.emit()

    def set_view_state(
        self,
        azimuth_deg: float = 45.0,
        elevation_deg: float = 30.0,
        zoom_factor: float = 1.0,
        pan_offset_x: float = 0.0,
        pan_offset_y: float = 0.0,
        is_perspective: bool = False,
        show_dimensions: bool = True,
        show_inside_walls: bool = True,
        show_axes: bool = True,
    ) -> None:
        """Sets full camera transform and visibility states."""
        self.azimuth_deg = float(azimuth_deg)
        self.elevation_deg = float(elevation_deg)
        self.zoom_factor = float(zoom_factor)
        self.pan_offset_x = float(pan_offset_x)
        self.pan_offset_y = float(pan_offset_y)
        self.show_dimensions = bool(show_dimensions)
        self.show_inside_walls = bool(show_inside_walls)
        self.show_axes = bool(show_axes)
        self.set_perspective(bool(is_perspective))
        self.update()
        self.view_changed.emit()

    def set_highlights(
        self,
        wall_indices: Optional[List[int]] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Sets active highlighted wall indices and/or element labels and redraws."""
        self.highlighted_wall_indices = set(wall_indices or [])
        self.highlighted_labels = set(labels or [])
        self.update()
        self.view_changed.emit()

    def clear_highlights(self) -> None:
        """Clears all active highlights."""
        if self.highlighted_wall_indices or self.highlighted_labels:
            self.highlighted_wall_indices.clear()
            self.highlighted_labels.clear()
            self.update()
            self.view_changed.emit()

    def is_face_highlighted(self, face: PolygonFace3D) -> bool:
        """Determines whether a given 3D polygon face is currently selected/highlighted."""
        if not self.highlighted_wall_indices and not self.highlighted_labels:
            return False

        if face.wall_index is not None and face.wall_index in self.highlighted_wall_indices:
            return True

        if face.label:
            if face.label in self.highlighted_labels:
                return True
            lbl_lower = face.label.lower()
            for hl in self.highlighted_labels:
                if not hl:
                    continue
                hl_lower = hl.lower()
                if lbl_lower in hl_lower or hl_lower in lbl_lower:
                    return True
                # Keyword matches for composite panel descriptions
                if "front" in lbl_lower and "front" in hl_lower:
                    return True
                if "back" in lbl_lower and "back" in hl_lower:
                    return True
                if "left" in lbl_lower and "left" in hl_lower:
                    return True
                if "right" in lbl_lower and "right" in hl_lower:
                    return True
                if "bottom" in lbl_lower and "bottom" in hl_lower:
                    return True
                if "top" in lbl_lower and "top" in hl_lower:
                    return True
                if "profile" in lbl_lower and "profile" in hl_lower:
                    if "lid" in lbl_lower and "lid" in hl_lower:
                        return True
                    if "base" in lbl_lower and "base" in hl_lower:
                        return True

        return False

    # --- Mouse Event Handlers ---

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._last_mouse_pos = event.position().toPoint()
        self._mouse_button_down = event.button()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        curr_pos = event.position().toPoint()
        if self._last_mouse_pos is not None and self._mouse_button_down is not None:
            delta = curr_pos - self._last_mouse_pos
            self._last_mouse_pos = curr_pos

            if self._mouse_button_down == Qt.MouseButton.LeftButton:
                # Orbit rotation
                self.azimuth_deg = (self.azimuth_deg - delta.x() * 0.5) % 360.0
                self.elevation_deg = max(-89.0, min(89.0, self.elevation_deg + delta.y() * 0.5))
                self.update()
                self.view_changed.emit()
            elif self._mouse_button_down in (Qt.MouseButton.RightButton, Qt.MouseButton.MiddleButton):
                # Pan translation
                self.pan_offset_x += delta.x()
                self.pan_offset_y += delta.y()
                self.update()
                self.view_changed.emit()

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

    # --- OpenGL Pipeline Implementation ---

    def initializeGL(self) -> None:
        """Configures initial OpenGL rendering state."""
        GL.glEnable(GL.GL_DEPTH_TEST)
        GL.glDepthFunc(GL.GL_LEQUAL)
        GL.glEnable(GL.GL_BLEND)
        GL.glBlendFunc(GL.GL_SRC_ALPHA, GL.GL_ONE_MINUS_SRC_ALPHA)
        GL.glEnable(GL.GL_MULTISAMPLE)
        GL.glEnable(GL.GL_LINE_SMOOTH)
        GL.glHint(GL.GL_LINE_SMOOTH_HINT, GL.GL_NICEST)
        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(1.2, 1.2)

        bg = QColor(COLORS.get("bg_schema", "#141419"))
        GL.glClearColor(bg.redF(), bg.greenF(), bg.blueF(), 1.0)

    def resizeGL(self, w: int, h: int) -> None:
        """Updates OpenGL viewport when widget is resized."""
        GL.glViewport(0, 0, max(1, w), max(1, h))

    def paintGL(self) -> None:
        """Executes full 3D OpenGL pass with depth testing and 2D QPainter overlay."""
        w, h = max(1, self.width()), max(1, self.height())
        aspect = w / h

        # 1. Clear color and depth buffers
        bg = QColor(COLORS.get("bg_schema", "#141419"))
        GL.glClearColor(bg.redF(), bg.greenF(), bg.blueF(), 1.0)
        GL.glViewport(0, 0, w, h)
        GL.glClear(GL.GL_COLOR_BUFFER_BIT | GL.GL_DEPTH_BUFFER_BIT)

        if not self.mesh:
            painter = QPainter(self)
            painter.setPen(QColor("#7a7a90"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No flightcase geometry to display")
            painter.end()
            return

        # 2. Compute 3D bounding box & center
        p_min, p_max = self.mesh.bounding_box
        center = Point3D(
            (p_min.x + p_max.x) / 2.0,
            (p_min.y + p_max.y) / 2.0,
            (p_min.z + p_max.z) / 2.0,
        )
        diag = math.sqrt((p_max.x - p_min.x)**2 + (p_max.y - p_min.y)**2 + (p_max.z - p_min.z)**2)
        max_dim = max(100.0, diag)

        # 3. Setup Projection Matrix
        GL.glMatrixMode(GL.GL_PROJECTION)
        GL.glLoadIdentity()
        fov_y = 38.0

        ortho_half_h = (max_dim * 0.72) / self.zoom_factor
        ortho_half_w = ortho_half_h * aspect
        if aspect < 1.0:
            ortho_half_w = (max_dim * 0.72) / self.zoom_factor
            ortho_half_h = ortho_half_w / aspect

        if self.is_perspective:
            z_near = max(1.0, max_dim * 0.02)
            z_far = max_dim * 25.0
            GLU.gluPerspective(fov_y, aspect, z_near, z_far)
        else:
            GL.glOrtho(-ortho_half_w, ortho_half_w, -ortho_half_h, ortho_half_h, -max_dim * 10.0, max_dim * 10.0)

        # 4. Setup ModelView Matrix
        GL.glMatrixMode(GL.GL_MODELVIEW)
        GL.glLoadIdentity()

        if self.is_perspective:
            cam_dist = (max_dim * 1.7) / self.zoom_factor
            pan_scale = (cam_dist * math.tan(math.radians(fov_y / 2.0))) / (h / 2.0)
            GL.glTranslatef(self.pan_offset_x * pan_scale, -self.pan_offset_y * pan_scale, -cam_dist)
        else:
            pan_scale = (2.0 * ortho_half_h) / h
            GL.glTranslatef(self.pan_offset_x * pan_scale, -self.pan_offset_y * pan_scale, 0.0)

        # Camera rotation (Elevation around X, Azimuth around Z)
        GL.glRotatef(self.elevation_deg - 90.0, 1.0, 0.0, 0.0)
        GL.glRotatef(-self.azimuth_deg, 0.0, 0.0, 1.0)
        # Center flightcase at origin
        GL.glTranslatef(-center.x, -center.y, -center.z)

        # 5. Render 3D Scene into Hardware Z-Buffer
        GL.glEnable(GL.GL_DEPTH_TEST)

        # 5a. Ground Reference Grid
        self._draw_gl_ground_grid(p_max)

        # 5b. Solid Panel Polygons with Directional Lighting & Offset
        if self.mesh.faces:
            self._draw_gl_solid_faces()
            self._draw_gl_face_outlines()
        else:
            self._draw_gl_fallback_segments()

        # 6. Capture GL Transformation Matrices for 2D Coordinate Unprojecting
        mv_matrix = GL.glGetDoublev(GL.GL_MODELVIEW_MATRIX)
        proj_matrix = GL.glGetDoublev(GL.GL_PROJECTION_MATRIX)
        viewport = GL.glGetIntegerv(GL.GL_VIEWPORT)

        def project_3d_to_screen(p: Point3D) -> QPointF:
            wx, wy, wz = GLU.gluProject(p.x, p.y, p.z, mv_matrix, proj_matrix, viewport)
            return QPointF(wx, h - wy)

        # 7. Render 2D Overlays (Crisp High-DPI Dimensions, Coordinate Axes & HUD)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        # 7a. Dimension Callouts
        if self.show_dimensions:
            for dim in self.mesh.dimensions:
                self._draw_2d_dimension_callout(painter, dim, project_3d_to_screen)

        # 7b. 3D Coordinate Axis Triad (Bottom-Left)
        if self.show_axes:
            self._draw_axis_triad(painter)

        # 7c. HUD Status & Info (Top-Left)
        self._draw_hud(painter)

        painter.end()

    # --- 3D OpenGL Rendering Helpers ---

    def _draw_gl_ground_grid(self, p_max: Point3D) -> None:
        """Renders ground reference grid in the Z = 0 ground plane."""
        span_x = max(200.0, p_max.x * 1.3)
        span_y = max(200.0, p_max.y * 1.3)
        step = 100.0

        grid_c = QColor(COLORS.get("grid_line", "#23232f"))
        GL.glColor4f(grid_c.redF(), grid_c.greenF(), grid_c.blueF(), 0.5)
        GL.glLineWidth(1.0)
        GL.glBegin(GL.GL_LINES)

        x = -50.0
        while x <= span_x + step:
            GL.glVertex3f(x, -50.0, 0.0)
            GL.glVertex3f(x, span_y, 0.0)
            x += step

        y = -50.0
        while y <= span_y + step:
            GL.glVertex3f(-50.0, y, 0.0)
            GL.glVertex3f(span_x, y, 0.0)
            y += step

        GL.glEnd()

    def _draw_gl_solid_faces(self) -> None:
        """Renders filled 3D panel faces into OpenGL Z-buffer with directional lighting."""
        if not self.mesh or not self.mesh.faces:
            return

        GL.glEnable(GL.GL_POLYGON_OFFSET_FILL)
        GL.glPolygonOffset(1.2, 1.2)

        # Key directional light in world space
        lx, ly, lz = 0.55, -0.45, 0.70
        l_len = math.sqrt(lx*lx + ly*ly + lz*lz)
        lx, ly, lz = lx / l_len, ly / l_len, lz / l_len

        for face in self.mesh.faces:
            if face.color_group == "wall" and not self.show_inside_walls:
                continue

            nx, ny, nz = face.normal
            diff = max(0.0, nx * lx + ny * ly + nz * lz)
            shade = 0.50 + diff * 0.50

            fill_color, _, _ = self._get_face_styling(face, shade)
            GL.glColor4f(fill_color.redF(), fill_color.greenF(), fill_color.blueF(), 1.0)

            GL.glBegin(GL.GL_POLYGON)
            for v in face.vertices:
                GL.glVertex3f(v.x, v.y, v.z)
            GL.glEnd()

    def _draw_gl_face_outlines(self) -> None:
        """Renders crisp boundary outlines on solid panel faces with depth testing."""
        if not self.mesh or not self.mesh.faces:
            return

        GL.glDisable(GL.GL_POLYGON_OFFSET_FILL)

        for face in self.mesh.faces:
            if face.color_group == "wall" and not self.show_inside_walls:
                continue

            _, edge_color, line_width = self._get_face_styling(face, 1.0)
            GL.glLineWidth(float(line_width))
            GL.glColor4f(edge_color.redF(), edge_color.greenF(), edge_color.blueF(), 1.0)

            GL.glBegin(GL.GL_LINE_LOOP)
            for v in face.vertices:
                GL.glVertex3f(v.x, v.y, v.z)
            GL.glEnd()

    def _draw_gl_fallback_segments(self) -> None:
        """Fallback line renderer if no solid faces exist."""
        if not self.mesh or not self.mesh.segments:
            return

        for seg in self.mesh.segments:
            if seg.color_group == "wall" and not self.show_inside_walls:
                continue

            edge_color = QColor(COLORS.get(f"{seg.color_group}_edge", COLORS["base_edge"]))
            GL.glLineWidth(2.0)
            GL.glColor4f(edge_color.redF(), edge_color.greenF(), edge_color.blueF(), 1.0)

            GL.glBegin(GL.GL_LINES)
            GL.glVertex3f(seg.p1.x, seg.p1.y, seg.p1.z)
            GL.glVertex3f(seg.p2.x, seg.p2.y, seg.p2.z)
            GL.glEnd()

    def _get_face_styling(self, face: PolygonFace3D, shade: float = 1.0) -> Tuple[QColor, QColor, float]:
        """Calculates shaded 100% opaque fill color, edge color, and line width for a 3D panel face."""
        is_highlighted = self.is_face_highlighted(face)

        if is_highlighted:
            if face.is_endgrain:
                base_fill_hex = COLORS.get("highlight_endgrain_fill", "#f59e0b")
                base_edge_hex = COLORS.get("highlight_endgrain_edge", "#fef08a")
                line_width = 3.2
            else:
                base_fill_hex = COLORS.get("highlight_fill", "#d97706")
                base_edge_hex = COLORS.get("highlight_edge", "#fde047")
                line_width = 3.0

            raw_color = QColor(base_fill_hex)
            lit_shade = 0.65 + shade * 0.35
            r = max(0, min(255, int(raw_color.red() * lit_shade)))
            g = max(0, min(255, int(raw_color.green() * lit_shade)))
            b = max(0, min(255, int(raw_color.blue() * lit_shade)))
            fill_color = QColor(r, g, b, 255)
            edge_color = QColor(base_edge_hex)
            return fill_color, edge_color, line_width

        base_fill_hex = COLORS.get(f"{face.color_group}_fill", COLORS["base_fill"])
        base_edge_hex = COLORS.get(f"{face.color_group}_edge", COLORS["base_edge"])
        line_width = 1.6

        if face.is_endgrain:
            base_fill_hex = COLORS.get("endgrain_fill", "#334155")
            base_edge_hex = COLORS.get("endgrain_edge", "#60a5fa")
            line_width = 2.0
        elif face.color_group == "profile":
            line_width = 2.0
        elif face.color_group == "wall":
            line_width = 1.8

        raw_color = QColor(base_fill_hex)
        r = max(0, min(255, int(raw_color.red() * shade)))
        g = max(0, min(255, int(raw_color.green() * shade)))
        b = max(0, min(255, int(raw_color.blue() * shade)))
        fill_color = QColor(r, g, b, 255)  # 100% opaque solid color

        edge_color = QColor(base_edge_hex)
        return fill_color, edge_color, line_width

    # --- 2D Vector Overlay Helpers ---

    def _draw_2d_dimension_callout(
        self,
        painter: QPainter,
        dim: DimensionCallout3D,
        project_func,
    ) -> None:
        """Renders crisp vector dimension line, witness extension lines, ticks, and text badge."""
        p1 = dim.start
        p2 = dim.end
        ox, oy, oz = dim.offset_vector

        p1_off = Point3D(p1.x + ox, p1.y + oy, p1.z + oz)
        p2_off = Point3D(p2.x + ox, p2.y + oy, p2.z + oz)

        p1_s = project_func(p1)
        p2_s = project_func(p2)
        p1_off_s = project_func(p1_off)
        p2_off_s = project_func(p2_off)

        # Witness Extension Lines
        witness_pen = QPen(QColor("#64748b"), 1.0, Qt.PenStyle.DotLine)
        painter.setPen(witness_pen)
        painter.drawLine(p1_s, p1_off_s)
        painter.drawLine(p2_s, p2_off_s)

        # Dimension Line
        dim_pen = QPen(QColor(COLORS.get("dim_line", "#f59e0b")), 1.5, Qt.PenStyle.SolidLine)
        painter.setPen(dim_pen)
        painter.drawLine(p1_off_s, p2_off_s)

        # End Ticks / Arrows
        self._draw_arrow_tick(painter, p1_off_s, p2_off_s)
        self._draw_arrow_tick(painter, p2_off_s, p1_off_s)

        # Text Label Badge
        mid_s = QPointF((p1_off_s.x() + p2_off_s.x()) / 2.0, (p1_off_s.y() + p2_off_s.y()) / 2.0)
        font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font)
        fm = QFontMetrics(font)
        text_rect = fm.boundingRect(dim.label)

        padding_x = 6
        padding_y = 3
        badge_w = text_rect.width() + padding_x * 2
        badge_h = text_rect.height() + padding_y * 2
        badge_rect = QRectF(mid_s.x() - badge_w / 2.0, mid_s.y() - badge_h / 2.0, badge_w, badge_h)

        # Badge pill background
        painter.setBrush(QBrush(QColor(24, 24, 32, 230)))
        painter.setPen(QPen(QColor(COLORS.get("dim_line", "#f59e0b")), 1.2))
        painter.drawRoundedRect(badge_rect, 4, 4)

        # Text string
        painter.setPen(QColor(COLORS.get("dim_text", "#fbbf24")))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, dim.label)

    def _draw_arrow_tick(self, painter: QPainter, pt: QPointF, towards_pt: QPointF) -> None:
        """Draws small dimension arrow or tick marker at terminal point."""
        dx = towards_pt.x() - pt.x()
        dy = towards_pt.y() - pt.y()
        length = math.sqrt(dx * dx + dy * dy)
        if length < 1e-4:
            return

        ux, uy = dx / length, dy / length
        arrow_size = 7.0
        angle = math.radians(25.0)

        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        v1_x = (ux * cos_a - uy * sin_a) * arrow_size
        v1_y = (ux * sin_a + uy * cos_a) * arrow_size
        v2_x = (ux * cos_a + uy * sin_a) * arrow_size
        v2_y = (-ux * sin_a + uy * cos_a) * arrow_size

        arrow_p1 = QPointF(pt.x() + v1_x, pt.y() + v1_y)
        arrow_p2 = QPointF(pt.x() + v2_x, pt.y() + v2_y)

        poly = QPolygonF([pt, arrow_p1, arrow_p2])
        painter.setBrush(QBrush(QColor(COLORS.get("dim_line", "#f59e0b"))))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)

    def _draw_axis_triad(self, painter: QPainter) -> None:
        """Draws rotating 3D coordinate axis indicator in the bottom-left corner."""
        origin_s = QPointF(50.0, self.height() - 50.0)
        axis_len = 32.0

        rad_az = math.radians(self.azimuth_deg)
        rad_el = math.radians(self.elevation_deg)
        sin_az, cos_az = math.sin(rad_az), math.cos(rad_az)
        sin_el, cos_el = math.sin(rad_el), math.cos(rad_el)

        def proj_dir(x: float, y: float, z: float) -> QPointF:
            xr = x * cos_az - y * sin_az
            yr = x * sin_az + y * cos_az
            sx = -xr
            sy = -yr * sin_el - z * cos_el
            return QPointF(origin_s.x() + sx * axis_len, origin_s.y() + sy * axis_len)

        x_s = proj_dir(1, 0, 0)
        y_s = proj_dir(0, 1, 0)
        z_s = proj_dir(0, 0, 1)

        font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(font)

        # X Axis (Red / Length)
        painter.setPen(QPen(QColor("#ef4444"), 2.0))
        painter.drawLine(origin_s, x_s)
        painter.drawText(x_s + QPointF(4, 4), "X (L)")

        # Y Axis (Green / Width)
        painter.setPen(QPen(QColor("#22c55e"), 2.0))
        painter.drawLine(origin_s, y_s)
        painter.drawText(y_s + QPointF(4, 4), "Y (W)")

        # Z Axis (Blue / Height)
        painter.setPen(QPen(QColor("#3b82f6"), 2.0))
        painter.drawLine(origin_s, z_s)
        painter.drawText(z_s + QPointF(4, -4), "Z (H)")

    def _draw_hud(self, painter: QPainter) -> None:
        """Draws HUD viewport status overlay in top-left."""
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#9e9eb4"))
        proj_name = "Perspective" if self.is_perspective else "Parallel (Ortho)"
        info = f"OpenGL {proj_name} | Azimuth: {self.azimuth_deg:.0f}° | Elevation: {self.elevation_deg:.0f}° | Zoom: {self.zoom_factor:.2f}x"
        painter.drawText(12, 20, info)

        if self.highlighted_labels or self.highlighted_wall_indices:
            sel_text = ", ".join(sorted(self.highlighted_labels)) if self.highlighted_labels else f"Wall #{list(self.highlighted_wall_indices)[0] + 1}"
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            painter.setPen(QColor(COLORS.get("highlight_edge", "#fde047")))
            painter.drawText(12, 38, f"★ Highlighted: {sel_text}")


class Schema3DWidget(QWidget):
    """Complete 3D Schema panel with interactive toolbar and hardware-accelerated OpenGL canvas."""

    lid_exploded_changed = Signal(float)
    toggles_changed = Signal()
    projection_changed = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.canvas = Schema3DCanvas(self)
        self.canvas.projection_changed.connect(self._on_canvas_projection_changed)
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

        # Projection Mode Toggle Button
        t_layout.addWidget(QLabel("<b>Projection:</b>"))
        self.btn_proj_toggle = QPushButton("Parallel (Ortho)", self)
        self.btn_proj_toggle.setObjectName("secondaryButton")
        self.btn_proj_toggle.setCheckable(True)
        self.btn_proj_toggle.setChecked(False)
        self.btn_proj_toggle.setToolTip("Toggle between Parallel (Orthographic) and Perspective 3D rendering")
        self.btn_proj_toggle.clicked.connect(self._on_toggle_projection_clicked)
        t_layout.addWidget(self.btn_proj_toggle)

        t_layout.addSpacing(12)

        # Exploded Lid Slider
        t_layout.addWidget(QLabel("<b>Lid Split Gap:</b>"))
        self.slider_gap = QSlider(Qt.Orientation.Horizontal, self)
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

    def _on_toggle_projection_clicked(self) -> None:
        is_perspective = self.btn_proj_toggle.isChecked()
        self.canvas.set_perspective(is_perspective)

    def _on_canvas_projection_changed(self, is_perspective: bool) -> None:
        self.btn_proj_toggle.setChecked(is_perspective)
        if is_perspective:
            self.btn_proj_toggle.setText("Perspective")
            self.btn_proj_toggle.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold;")
        else:
            self.btn_proj_toggle.setText("Parallel (Ortho)")
            self.btn_proj_toggle.setStyleSheet("")
        self.projection_changed.emit(is_perspective)

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

    def set_perspective(self, is_perspective: bool) -> None:
        self.canvas.set_perspective(is_perspective)

    @property
    def is_perspective(self) -> bool:
        return self.canvas.is_perspective

    @property
    def exploded_gap_mm(self) -> float:
        return float(self.slider_gap.value())

    @property
    def show_dimensions(self) -> bool:
        return self.chk_dims.isChecked()

    @property
    def show_inside_walls(self) -> bool:
        return self.chk_walls.isChecked()

    def set_highlights(
        self,
        wall_indices: Optional[List[int]] = None,
        labels: Optional[List[str]] = None,
    ) -> None:
        """Forward highlight selection to OpenGL canvas."""
        self.canvas.set_highlights(wall_indices=wall_indices, labels=labels)

    def clear_highlights(self) -> None:
        """Clears all element highlights on OpenGL canvas."""
        self.canvas.clear_highlights()

    def get_ui_settings(self) -> UISettingsDTO:
        """Collects current 3D viewport, camera, explosion gap, and toggle states."""
        return UISettingsDTO(
            camera_azimuth_deg=self.canvas.azimuth_deg,
            camera_elevation_deg=self.canvas.elevation_deg,
            camera_zoom=self.canvas.zoom_factor,
            camera_pan_x=self.canvas.pan_offset_x,
            camera_pan_y=self.canvas.pan_offset_y,
            is_perspective=self.canvas.is_perspective,
            lid_exploded_gap_mm=float(self.slider_gap.value()),
            show_dimensions=self.chk_dims.isChecked(),
            show_inside_walls=self.chk_walls.isChecked(),
            show_axes=self.canvas.show_axes,
        )

    def set_ui_settings(self, settings: UISettingsDTO) -> None:
        """Restores 3D viewport transform, camera, explosion gap, and toggle states."""
        gap_val = int(round(settings.lid_exploded_gap_mm))
        self.slider_gap.blockSignals(True)
        self.slider_gap.setValue(gap_val)
        self.slider_gap.blockSignals(False)
        self.lbl_gap.setText(f"{gap_val} mm")

        self.chk_dims.blockSignals(True)
        self.chk_dims.setChecked(settings.show_dimensions)
        self.chk_dims.blockSignals(False)

        self.chk_walls.blockSignals(True)
        self.chk_walls.setChecked(settings.show_inside_walls)
        self.chk_walls.blockSignals(False)

        self.btn_proj_toggle.setChecked(settings.is_perspective)
        if settings.is_perspective:
            self.btn_proj_toggle.setText("Perspective")
            self.btn_proj_toggle.setStyleSheet("background-color: #3b82f6; color: white; font-weight: bold;")
        else:
            self.btn_proj_toggle.setText("Parallel (Ortho)")
            self.btn_proj_toggle.setStyleSheet("")

        self.canvas.set_view_state(
            azimuth_deg=settings.camera_azimuth_deg,
            elevation_deg=settings.camera_elevation_deg,
            zoom_factor=settings.camera_zoom,
            pan_offset_x=settings.camera_pan_x,
            pan_offset_y=settings.camera_pan_y,
            is_perspective=settings.is_perspective,
            show_dimensions=settings.show_dimensions,
            show_inside_walls=settings.show_inside_walls,
            show_axes=settings.show_axes,
        )
