"""Unit tests for PySide6 UI layer widgets."""

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication


@pytest.fixture(autouse=True)
def clean_settings():
    """Ensure clean QSettings for every test."""
    settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
    settings.clear()
    settings.sync()
    yield
    settings.clear()
    settings.sync()


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
    assert widget.canvas.elevation_deg == initial_el + 10 * 0.5

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


def test_main_window_permanent_3d_view_and_highlighting(qapp):
    from flightcase.ui import FlightCaseMainWindow
    from PySide6.QtWidgets import QSplitter, QTabWidget, QScrollArea

    window = FlightCaseMainWindow()

    # 1. Verify 3-pane layout in splitter: Left output tabs | Center 3D view | Right config panel
    central = window.centralWidget()
    splitter = central.findChild(QSplitter)
    assert splitter is not None
    assert splitter.count() == 3

    # Left child must be QTabWidget with output cut lists & profiles tables
    left_tabs = splitter.widget(0)
    assert isinstance(left_tabs, QTabWidget)
    assert left_tabs == window.tabs
    assert left_tabs.count() == 2
    assert left_tabs.tabText(0).endswith("Wood Cut List")
    assert left_tabs.tabText(1).endswith("Alu Profiles")

    # Center child must be Schema3DWidget directly
    center_widget = splitter.widget(1)
    assert center_widget == window.schema_widget
    assert window.schema_widget.isVisibleTo(window)

    # Right child must be permanent configuration panel (scroll area with dimensions and walls)
    right_widget = splitter.widget(2)
    assert isinstance(right_widget, QScrollArea)
    assert window.input_panel.isVisibleTo(window)
    assert window.walls_widget.isVisibleTo(window)

    # 2. Add inside walls and verify wall selection highlighting
    window.walls_widget.spin_count.setValue(2)
    window.walls_widget._on_generate_equispaced()

    # Select the first wall in InsideWallsWidget table
    window.walls_widget.table.selectRow(0)
    assert 0 in window.schema_widget.canvas.highlighted_wall_indices

    # Check that wall faces are highlighted in 3D canvas
    highlighted_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_faces) > 0
    for hf in highlighted_faces:
        assert hf.wall_index == 0
        fill_color, edge_color, line_width = window.schema_widget.canvas._get_face_styling(hf)
        assert fill_color.alpha() == 255
        assert line_width >= 3.0

    # 3. Test Wood Cut List table selection highlighting
    window.tabs.setCurrentIndex(0)
    # Select first row in cut list table ("Base Bottom Panel")
    window.cutlist_widget.table.selectRow(0)
    assert len(window.schema_widget.canvas.highlighted_labels) > 0
    assert "Base Bottom Panel" in window.schema_widget.canvas.highlighted_labels

    highlighted_wood_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_wood_faces) > 0
    assert any("bottom" in f.label.lower() for f in highlighted_wood_faces)

    # 4. Test selecting an Inside Wall inside the Wood Cut List table
    wall_cut_row = -1
    for r, item in enumerate(window._current_result.wood_cut_list):
        if "wall" in item.name.lower() or "wall" in item.category.lower():
            wall_cut_row = r
            break
    if wall_cut_row >= 0:
        window.cutlist_widget.table.selectRow(wall_cut_row)
        assert len(window.schema_widget.canvas.highlighted_labels) > 0
        highlighted_wall_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
        assert len(highlighted_wall_faces) > 0
        assert any(f.color_group == "wall" for f in highlighted_wall_faces)

    # 5. Test Alu Profiles table selection highlighting
    window.tabs.setCurrentIndex(1)
    window.alu_widget.table_profiles.selectRow(0)
    assert len(window.schema_widget.canvas.highlighted_labels) > 0

    highlighted_alu_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_alu_faces) > 0
    assert any(f.color_group == "profile" for f in highlighted_alu_faces)

    window.close()


def test_self_cut_lid_ui_interaction(qapp):
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow()

    # Default is False (split lid wood cut list with 6 rows)
    assert window.input_panel.chk_self_cut_lid.isChecked() is False
    assert len(window._current_result.wood_cut_list) == 6
    assert window.cutlist_widget.table.rowCount() == 6

    # Toggle to self-cut lid (6-wall uncut box)
    window.input_panel.set_self_cut_lid(True)
    assert window.input_panel.chk_self_cut_lid.isChecked() is True
    assert len(window._current_result.wood_cut_list) == 4  # 4 rows representing 6 outer walls
    assert window.cutlist_widget.table.rowCount() == 4

    # Verify 3D model maintains base and lid components
    assert window.schema_widget.canvas.mesh is not None
    color_groups = {f.color_group for f in window.schema_widget.canvas.mesh.faces}
    assert "base" in color_groups
    assert "lid" in color_groups
    assert "profile" in color_groups

    # Select "Bottom Panel" row and verify highlighting
    window.tabs.setCurrentIndex(0)
    window.cutlist_widget.table.selectRow(0)
    highlighted_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_faces) > 0
    assert any("bottom" in f.label.lower() for f in highlighted_faces)

    # Select "Top Panel" row and verify highlighting
    window.cutlist_widget.table.selectRow(1)
    highlighted_top_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_top_faces) > 0
    assert any("top" in f.label.lower() for f in highlighted_top_faces)

    # Toggle back to standard mode
    window.input_panel.set_self_cut_lid(False)
    assert len(window._current_result.wood_cut_list) == 6
    assert window.cutlist_widget.table.rowCount() == 6

    window.close()


def test_table_horizontal_scrollbars(qapp):
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Wood Cut List Table horizontal scrollbar policy
    assert window.cutlist_widget.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.cutlist_widget.table.horizontalHeader().minimumSectionSize() == 60

    # 2. Aluminum Extrusion Cut List Table horizontal scrollbar policy
    assert window.alu_widget.table_profiles.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.alu_widget.table_profiles.horizontalHeader().minimumSectionSize() == 60

    # 3. Compartments Analysis Table horizontal scrollbar policy
    assert window.alu_widget.table_comps.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.alu_widget.table_comps.horizontalHeader().minimumSectionSize() == 60

    # 4. Partition Walls Table horizontal scrollbar policy
    assert window.walls_widget.table.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAsNeeded
    assert window.walls_widget.table.horizontalHeader().minimumSectionSize() == 60

    window.close()


def test_project_save_load_file_and_qsettings(tmp_path, qapp):
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.application import InsideWallDTO

    # Step 1: Open window, configure parameters and walls
    window1 = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    window1.input_panel.spin_length.setValue(1100.0)
    window1.input_panel.spin_width.setValue(550.0)
    window1.input_panel.spin_total_height.setValue(450.0)
    window1.input_panel.spin_lid_height.setValue(110.0)
    window1.input_panel.set_self_cut_lid(True)

    # Add a custom partition wall
    window1.walls_widget.set_walls([
        InsideWallDTO(
            orientation="width_wise",
            position_mm=350.0,
            thickness_mm=9.0,
            height_mm=200.0,
            label="Custom Test Wall",
        )
    ])
    window1.recalculate()

    # Save project to file
    proj_file = str(tmp_path / "custom_flightcase.fcproj")
    window1._save_project_file(proj_file)
    assert window1._current_project_path == proj_file
    assert "custom_flightcase.fcproj" in window1.windowTitle()

    # Close window (this triggers _save_settings to QSettings)
    window1.close()

    # Step 2: Open a new window with restore_settings=True and load_last_project=True
    window2 = FlightCaseMainWindow(restore_settings=True, load_last_project=True)

    # Verify that the last project was automatically loaded at startup
    assert window2._current_project_path == proj_file
    assert window2.input_panel.spin_length.value() == 1100.0
    assert window2.input_panel.spin_width.value() == 550.0
    assert window2.input_panel.spin_total_height.value() == 450.0
    assert window2.input_panel.spin_lid_height.value() == 110.0
    assert window2.input_panel.chk_self_cut_lid.isChecked() is True

    walls = window2.walls_widget.get_walls()
    assert len(walls) == 1
    assert walls[0].label == "Custom Test Wall"
    assert walls[0].position_mm == 350.0
    assert walls[0].height_mm == 200.0

    # Step 3: Test New Project reset
    window2._new_project()
    assert window2._current_project_path is None
    assert "Untitled" in window2.windowTitle()
    assert window2.input_panel.spin_length.value() == 800.0
    assert len(window2.walls_widget.get_walls()) == 0

    # Step 4: Test loading back from file
    window2._load_project_file(proj_file)
    assert window2._current_project_path == proj_file
    assert window2.input_panel.spin_length.value() == 1100.0
    assert len(window2.walls_widget.get_walls()) == 1

    window2.close()


def test_project_ui_settings_storage_and_restoration(tmp_path, qapp):
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.application import InsideWallDTO

    # Step 1: Initialize main window
    window1 = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    window1.input_panel.spin_length.setValue(950.0)
    window1.input_panel.spin_width.setValue(480.0)

    # Configure 3D camera transform and perspective
    window1.schema_widget.canvas.azimuth_deg = 120.0
    window1.schema_widget.canvas.elevation_deg = 40.0
    window1.schema_widget.canvas.zoom_factor = 1.8
    window1.schema_widget.canvas.pan_offset_x = 15.0
    window1.schema_widget.canvas.pan_offset_y = -25.0
    window1.schema_widget.btn_proj_toggle.setChecked(True)
    window1.schema_widget._on_toggle_projection_clicked()
    assert window1.schema_widget.is_perspective is True

    # Configure lid distance, checkboxes, and tabs
    window1.schema_widget.slider_gap.setValue(65)
    window1.schema_widget.chk_dims.setChecked(False)
    window1.schema_widget.chk_walls.setChecked(True)
    window1.tabs.setCurrentIndex(1)

    # Configure wall generator inputs
    window1.walls_widget.set_generator_settings(3, "length_wise")

    # Save to project file
    project_path = str(tmp_path / "ui_customized_case.fcproj")
    window1._save_project_file(project_path)
    window1.close()

    # Step 2: Open fresh window and load the saved project
    window2 = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    window2._load_project_file(project_path)

    # Verify 3D Camera transform
    assert window2.schema_widget.canvas.azimuth_deg == 120.0
    assert window2.schema_widget.canvas.elevation_deg == 40.0
    assert window2.schema_widget.canvas.zoom_factor == 1.8
    assert window2.schema_widget.canvas.pan_offset_x == 15.0
    assert window2.schema_widget.canvas.pan_offset_y == -25.0
    assert window2.schema_widget.is_perspective is True
    assert window2.schema_widget.btn_proj_toggle.isChecked() is True
    assert window2.schema_widget.btn_proj_toggle.text() == "Perspective"

    # Verify lid split gap slider and label
    assert window2.schema_widget.slider_gap.value() == 65
    assert window2.schema_widget.lbl_gap.text() == "65 mm"
    assert window2.schema_widget.exploded_gap_mm == 65.0

    # Verify checkboxes
    assert window2.schema_widget.chk_dims.isChecked() is False
    assert window2.schema_widget.canvas.show_dimensions is False
    assert window2.schema_widget.chk_walls.isChecked() is True
    assert window2.schema_widget.canvas.show_inside_walls is True

    # Verify active tab
    assert window2.tabs.currentIndex() == 1

    # Verify generator settings
    count, orient = window2.walls_widget.get_generator_settings()
    assert count == 3
    assert orient == "length_wise"

    window2.close()
