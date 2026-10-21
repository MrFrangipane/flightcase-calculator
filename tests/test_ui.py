"""Unit tests for PySide6 UI layer widgets."""

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_main_window_lifecycle(qapp):
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow()
    assert window.windowTitle().startswith("Flightcase Calculator")

    # Initial recalculation ran
    assert window._current_result is not None
    assert len(window._current_result.wood_cut_list) == 6
    assert window._current_result.total_lid_mating_profile_length_mm == 5200.0

    # Test preset change
    window.input_panel.combo_presets.setCurrentIndex(1)  # Large Production Case (1200x600x600)
    assert window.input_panel.spin_length.value() == 1200.0
    assert window._current_result.total_lid_mating_profile_length_mm == 7200.0  # 2 * 2 * (1200 + 600)

    # Test adding walls
    window.walls_widget.spin_count.setValue(2)
    window.walls_widget._on_generate_equispaced()
    assert len(window.walls_widget.get_walls()) == 2
    assert len(window._current_result.wood_cut_list) == 8  # 6 main panels + 2 walls

    window.close()


def test_schema_3d_canvas_rendering(qapp):
    from PySide6.QtGui import QOpenGLContext, QOffscreenSurface
    from flightcase.ui.widgets import Schema3DWidget
    from flightcase.domain import Dimensions3D, FlightCase, InsideWall, WallOrientation, Schema3DGeometryBuilder

    # Setup headless OpenGL context
    surface = QOffscreenSurface()
    surface.create()
    ctx = QOpenGLContext()
    ctx.create()
    ctx.makeCurrent(surface)

    widget = Schema3DWidget()
    case = FlightCase(Dimensions3D(800.0, 500.0, 400.0), lid_height=100.0, wood_thickness=9.0)
    case.add_wall(InsideWall(orientation=WallOrientation.WIDTH_WISE, position_mm=300.0, thickness_mm=10.0))
    mesh = Schema3DGeometryBuilder.build_geometry(case, lid_exploded_gap_mm=30.0)

    widget.set_mesh(mesh)
    assert widget.canvas.mesh is not None
    assert len(widget.canvas.mesh.faces) > 0

    # Test view resets
    widget.canvas.reset_view(45.0, 30.0)
    assert widget.canvas.azimuth_deg == 45.0
    assert widget.canvas.elevation_deg == 30.0

    # Test front, side, top views
    widget.canvas.reset_view(0.0, 0.0)
    widget.canvas.repaint()
    widget.canvas.reset_view(90.0, 0.0)
    widget.canvas.repaint()
    widget.canvas.reset_view(0.0, 89.0)
    widget.canvas.repaint()

    # Test toggles
    widget.chk_dims.setChecked(False)
    assert widget.canvas.show_dimensions is False
    widget.chk_walls.setChecked(False)
    assert widget.canvas.show_inside_walls is False

    # Test projection toggling
    assert widget.is_perspective is False
    assert widget.btn_proj_toggle.text() == "Parallel (Ortho)"
    
    # Toggle to perspective via button click
    widget.btn_proj_toggle.click()
    assert widget.is_perspective is True
    assert widget.btn_proj_toggle.text() == "Perspective"

    # Toggle back to parallel via canvas method
    widget.canvas.toggle_projection()
    assert widget.is_perspective is False
    assert widget.btn_proj_toggle.text() == "Parallel (Ortho)"

    # Render OpenGL pass in parallel mode
    widget.resize(600, 400)
    widget.canvas.initializeGL()
    widget.canvas.resizeGL(600, 400)
    widget.canvas.paintGL()

    # Switch to perspective and render OpenGL pass in perspective mode
    widget.set_perspective(True)
    widget.canvas.paintGL()

    # Trigger repaint
    widget.canvas.repaint()

    # Test 100% opaque fills across all face categories
    for face in mesh.faces:
        fill_color, edge_color, line_width = widget.canvas._get_face_styling(face, shade=1.0)
        assert fill_color.alpha() == 255, f"Fill color for {face.color_group} must be 100% opaque (alpha=255)"
        assert edge_color.isValid()
        assert line_width > 0

    widget.close()


def test_opengl_interaction_and_projection_signals(qapp):
    from PySide6.QtCore import Qt, QPoint, QPointF
    from PySide6.QtGui import QMouseEvent, QWheelEvent, QOpenGLContext, QOffscreenSurface
    from flightcase.ui.widgets import Schema3DWidget
    from flightcase.domain import Dimensions3D, FlightCase, Schema3DGeometryBuilder

    surface = QOffscreenSurface()
    surface.create()
    ctx = QOpenGLContext()
    ctx.create()
    ctx.makeCurrent(surface)

    widget = Schema3DWidget()
    case = FlightCase(Dimensions3D(600.0, 400.0, 300.0), lid_height=80.0, wood_thickness=9.0)
    mesh = Schema3DGeometryBuilder.build_geometry(case, lid_exploded_gap_mm=50.0)
    widget.set_mesh(mesh)
    widget.resize(500, 400)
    widget.canvas.initializeGL()

    # Track projection change signals
    signals_received = []
    widget.projection_changed.connect(lambda mode: signals_received.append(mode))

    # Toggle projection via API
    widget.set_perspective(True)
    assert widget.is_perspective is True
    assert signals_received == [True]

    widget.set_perspective(False)
    assert widget.is_perspective is False
    assert signals_received == [True, False]

    # Test mouse orbit (Left Button Drag)
    initial_az = widget.canvas.azimuth_deg
    initial_el = widget.canvas.elevation_deg
    
    press_event = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(100, 100), QPointF(100, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.canvas.mousePressEvent(press_event)
    move_event = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(120, 110), QPointF(120, 110), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.canvas.mouseMoveEvent(move_event)
    release_event = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(120, 110), QPointF(120, 110), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    widget.canvas.mouseReleaseEvent(release_event)

    assert widget.canvas.azimuth_deg == (initial_az - 20 * 0.5) % 360.0
    assert widget.canvas.elevation_deg == initial_el - 10 * 0.5

    # Test mouse pan (Right Button Drag)
    initial_px = widget.canvas.pan_offset_x
    initial_py = widget.canvas.pan_offset_y
    press_r = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPointF(100, 100), QPointF(100, 100), Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    widget.canvas.mousePressEvent(press_r)
    move_r = QMouseEvent(QMouseEvent.Type.MouseMove, QPointF(130, 140), QPointF(130, 140), Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    widget.canvas.mouseMoveEvent(move_r)
    release_r = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPointF(130, 140), QPointF(130, 140), Qt.MouseButton.RightButton, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier)
    widget.canvas.mouseReleaseEvent(release_r)

    assert widget.canvas.pan_offset_x == initial_px + 30
    assert widget.canvas.pan_offset_y == initial_py + 40

    # Test wheel zoom
    initial_zoom = widget.canvas.zoom_factor
    wheel_event = QWheelEvent(QPointF(200, 200), QPointF(200, 200), QPoint(0, 120), QPoint(0, 120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
    widget.canvas.wheelEvent(wheel_event)
    assert widget.canvas.zoom_factor > initial_zoom

    # Test exploded gap slider
    widget.slider_gap.setValue(80)
    assert widget.exploded_gap_mm == 80.0
    assert widget.lbl_gap.text() == "80 mm"

    widget.close()


def test_topological_face_sorting_and_culling(qapp):
    from flightcase.ui.widgets import Schema3DCanvas
    from flightcase.domain import (
        Dimensions3D,
        FlightCase,
        InsideWall,
        WallOrientation,
        Schema3DGeometryBuilder,
        ParallelProjector,
        ComponentLayer,
    )

    case = FlightCase(Dimensions3D(800.0, 500.0, 400.0), lid_height=100.0, wood_thickness=9.0)
    case.add_wall(InsideWall(orientation=WallOrientation.WIDTH_WISE, position_mm=300.0, thickness_mm=10.0))
    mesh = Schema3DGeometryBuilder.build_geometry(case, lid_exploded_gap_mm=20.0)

    canvas = Schema3DCanvas()
    canvas.set_mesh(mesh)
    projector = ParallelProjector(azimuth_deg=45.0, elevation_deg=30.0)

    # Collect visible faces and simulate layer sorting
    visible_faces = []
    for face in mesh.faces:
        if not projector.is_face_facing_camera(face.normal):
            continue
        _, _, depth_z = projector.project_point(face.centroid)
        visible_faces.append((depth_z, face))

    visible_faces.sort(key=lambda item: (item[1].layer_order, -item[0]))

    # Verify that layers appear in strict monotonically non-decreasing hierarchy
    layer_orders = [f.layer_order for _, f in visible_faces]
    assert layer_orders == sorted(layer_orders)

    # Check presence of distinct layers in visible draw list
    distinct_layers = sorted(list(set(layer_orders)))
    assert ComponentLayer.BASE_FLOOR in distinct_layers
    assert ComponentLayer.OUTER_BASE_WALLS in distinct_layers
    assert ComponentLayer.LID_ROOF in distinct_layers
