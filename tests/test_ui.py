"""Unit tests for PySide6 UI layer widgets."""

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox


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
    t_wood = window.input_panel.spin_wood_thickness.value()
    expected_lid_profile = 2 * 2 * ((800.0 + 2 * t_wood) + (500.0 + 2 * t_wood))
    assert window._current_result.total_lid_mating_profile_length_mm == expected_lid_profile

    # Test dimension change
    window.input_panel.spin_length.setValue(1200.0)
    window.input_panel.spin_width.setValue(600.0)
    window.input_panel.spin_total_height.setValue(600.0)
    assert window.input_panel.spin_length.value() == 1200.0
    expected_new_profile = 2 * 2 * ((1200.0 + 2 * t_wood) + (600.0 + 2 * t_wood))
    assert window._current_result.total_lid_mating_profile_length_mm == expected_new_profile

    # Test adding walls
    window.walls_widget._on_comp_tab_add()
    window.walls_widget._on_comp_tab_add()
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

    # 1. Verify layout: Splitter with Left output tabs & Center 3D view | Right fixed config panel
    central = window.centralWidget()
    splitter = central.findChild(QSplitter)
    assert splitter is not None
    assert splitter.count() == 2

    # Left child must be QTabWidget with output cut lists & profiles tables
    left_tabs = splitter.widget(0)
    assert isinstance(left_tabs, QTabWidget)
    assert left_tabs == window.tabs
    assert left_tabs.count() == 3
    assert left_tabs.tabText(0).endswith("Wood Cut List")
    assert left_tabs.tabText(1).endswith("Alu Profiles")
    assert left_tabs.tabText(2).endswith("Wood Types")

    # Center child must be QTabWidget containing 3D schema and 2D wood panels SVG
    center_tabs = splitter.widget(1)
    assert isinstance(center_tabs, QTabWidget)
    assert center_tabs == window.center_tabs
    assert center_tabs.count() == 2
    assert center_tabs.widget(0) == window.schema_widget
    assert center_tabs.widget(1) == window.svg_widget
    assert window.schema_widget.isVisibleTo(window)

    # Right panel must be permanent configuration panel (with dimensions and walls) directly in central layout
    assert window.config_container.parent() == central
    assert window.input_panel.isVisibleTo(window)
    assert window.walls_widget.isVisibleTo(window)

    # 2. Add inside walls and verify wall selection highlighting
    window.walls_widget._on_add_wall()
    window.walls_widget._on_add_wall()

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

    # Configure lid distance, checkboxes, tabs, and inside walls orientation & auto equalize
    window1.schema_widget.slider_gap.setValue(65)
    window1.schema_widget.chk_dims.setChecked(False)
    window1.schema_widget.chk_walls.setChecked(True)
    window1.tabs.setCurrentIndex(1)
    window1.walls_widget.set_walls([
        InsideWallDTO(orientation="length_wise", position_mm=150.0, thickness_mm=10.0),
        InsideWallDTO(orientation="length_wise", position_mm=300.0, thickness_mm=10.0),
    ])
    window1.walls_widget.set_compartment_orientation("length_wise")
    assert window1.walls_widget.get_compartment_orientation() == "length_wise"
    window1.walls_widget.set_auto_equalize_flags([False, True, True])
    assert window1.walls_widget.get_auto_equalize_flags() == [False, True, True]

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

    # Verify active tab, compartment orientation, and auto equalize flags
    assert window2.tabs.currentIndex() == 1
    assert window2.walls_widget.get_compartment_orientation() == "length_wise"
    assert window2.walls_widget.get_auto_equalize_flags() == [False, True, True]
    assert window2.walls_widget._get_comp_tab_space_spinbox(0).isEnabled() is True
    assert window2.walls_widget._get_comp_tab_space_spinbox(1).isEnabled() is False
    assert window2.walls_widget._get_comp_tab_space_spinbox(2).isEnabled() is False

    window2.close()


def test_inside_walls_compartment_spaces_ui(qapp):
    from flightcase.ui import FlightCaseMainWindow
    from PySide6.QtWidgets import QDoubleSpinBox, QCheckBox

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    # Set inner dimensions: L = 1000mm, W = 600mm, Wood = 10mm -> inner_length = 1000mm, inner_width = 600mm
    window.input_panel.spin_length.setValue(1000.0)
    window.input_panel.spin_width.setValue(600.0)
    window.input_panel.spin_wood_thickness.setValue(10.0)
    window.recalculate()

    # Verify InsideWallsWidget has received context
    assert window.walls_widget.inner_length == 1000.0
    assert window.walls_widget.inner_width == 600.0
    assert window.walls_widget.wood_thickness == 10.0

    # 1. Test adding compartments and configuring clearances directly in InsideWallsWidget
    window.walls_widget.set_walls([])
    assert window.walls_widget.table_comps.rowCount() == 1  # 1 full span compartment by default

    # Add 2 more compartments (total 3 compartments, 2 walls)
    window.walls_widget._on_comp_tab_add()
    window.walls_widget._on_comp_tab_add()
    assert window.walls_widget.table_comps.rowCount() == 3

    # Enable auto-equalize on row 2
    chk_comp2 = window.walls_widget._get_comp_tab_auto_checkbox(2)
    assert isinstance(chk_comp2, QCheckBox)
    chk_comp2.setChecked(True)
    spin_tab_comp2 = window.walls_widget._get_comp_tab_space_spinbox(2)
    assert spin_tab_comp2.isEnabled() is False

    # Edit compartment 0 available space to 300.0 mm
    spin_comp0 = window.walls_widget._get_comp_tab_space_spinbox(0)
    assert isinstance(spin_comp0, QDoubleSpinBox)
    spin_comp0.setValue(300.0)

    # Edit compartment 1 available space to 200.0 mm
    spin_comp1 = window.walls_widget._get_comp_tab_space_spinbox(1)
    spin_comp1.setValue(200.0)

    # Verify auto-equalized compartment 2 space = 1000 - 20 (walls) - 300 - 200 = 480 mm
    clearances = window.walls_widget._get_comp_tab_clearances()
    assert pytest.approx(clearances[2]) == 480.0

    # Verify that walls are updated dynamically
    updated_walls = window.walls_widget.get_walls()
    assert len(updated_walls) == 2
    # Wall 1 center: 300 + 5 = 305.0 mm
    assert pytest.approx(updated_walls[0].position_mm) == 305.0
    # Wall 2 center: 300 + 10 + 200 + 5 = 515.0 mm
    assert pytest.approx(updated_walls[1].position_mm) == 515.0

    # Test "- Remove Compartment" button
    prev_count = window.walls_widget.table_comps.rowCount()
    window.walls_widget._on_comp_tab_remove()
    assert window.walls_widget.table_comps.rowCount() == prev_count - 1

    window.close()


def test_compartment_auto_equalize_comprehensive(qapp):
    """Tests all aspects of the Auto-Equalize column and reactive space redistribution."""
    from flightcase.ui.widgets.walls_widget import InsideWallsWidget
    from PySide6.QtWidgets import QDoubleSpinBox, QCheckBox

    widget = InsideWallsWidget()
    widget.set_case_dimensions(inner_length=1000.0, inner_width=500.0, wood_thickness=10.0)

    # Add compartments so we have 4 compartments (3 partition walls of 10mm -> 30mm total walls, 970mm usable clearance)
    while widget.table_comps.rowCount() < 4:
        widget._on_comp_tab_add()

    assert widget.table_comps.rowCount() == 4

    # Set initial clearances on unchecked rows: row 0 = 200, row 1 = 200, row 2 and 3 checked
    widget._get_comp_tab_auto_checkbox(0).setChecked(False)
    widget._get_comp_tab_auto_checkbox(1).setChecked(False)
    widget._get_comp_tab_auto_checkbox(2).setChecked(True)
    widget._get_comp_tab_auto_checkbox(3).setChecked(True)

    widget._get_comp_tab_space_spinbox(0).setValue(200.0)
    widget._get_comp_tab_space_spinbox(1).setValue(200.0)

    # Rows 2 and 3 should be disabled for manual editing
    assert widget._get_comp_tab_space_spinbox(0).isEnabled() is True
    assert widget._get_comp_tab_space_spinbox(1).isEnabled() is True
    assert widget._get_comp_tab_space_spinbox(2).isEnabled() is False
    assert widget._get_comp_tab_space_spinbox(3).isEnabled() is False

    # Remaining space for rows 2 and 3 = 1000 - 30 - (200 + 200) = 570mm -> 285mm each
    clearances = widget._get_comp_tab_clearances()
    assert pytest.approx(clearances[2]) == 285.0
    assert pytest.approx(clearances[3]) == 285.0

    # Edit unchecked row 0 to 100.0 mm -> Remaining space = 1000 - 30 - (100 + 200) = 670mm -> 335mm each
    widget._get_comp_tab_space_spinbox(0).setValue(100.0)
    clearances = widget._get_comp_tab_clearances()
    assert pytest.approx(clearances[0]) == 100.0
    assert pytest.approx(clearances[2]) == 335.0
    assert pytest.approx(clearances[3]) == 335.0

    # Change material specification wood thickness from 10mm to 15mm -> total walls (3 * 15mm = 45mm)
    widget.set_case_dimensions(inner_length=1000.0, inner_width=500.0, wood_thickness=15.0)
    clearances = widget._get_comp_tab_clearances()
    assert pytest.approx(clearances[2], 0.1) == 331.2
    assert pytest.approx(clearances[3], 0.1) == 331.2

    # Toggle row 1 to auto-equalize as well (rows 1, 2, 3 now checked)
    chk1 = widget._get_comp_tab_auto_checkbox(1)
    chk1.setChecked(True)
    assert widget._get_comp_tab_space_spinbox(1).isEnabled() is False
    # Remaining space = 1000 - 45 - 97.5 = 857.5mm -> 857.5 / 3 = 285.8mm each
    clearances = widget._get_comp_tab_clearances()
    assert pytest.approx(clearances[1], 0.1) == 285.8
    assert pytest.approx(clearances[2], 0.1) == 285.8
    assert pytest.approx(clearances[3], 0.1) == 285.8

    # Toggle row 1 back to unchecked -> should become editable again
    chk1.setChecked(False)
    assert widget._get_comp_tab_space_spinbox(1).isEnabled() is True


def test_schema_3d_canvas_antialiasing(qapp):
    """Validates that Schema3DCanvas configures hardware multisample antialiasing (MSAA)."""
    from flightcase.ui.widgets.schema_3d_widget import Schema3DCanvas
    from flightcase.domain import FlightCase, Dimensions3D, Schema3DGeometryBuilder

    canvas = Schema3DCanvas()
    canvas.resize(600, 400)
    assert canvas.format().samples() >= 4

    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 300.0),
        lid_height=80.0,
        wood_thickness=10.0,
    )
    mesh = Schema3DGeometryBuilder.build_geometry(case)
    canvas.set_mesh(mesh)
    canvas.show()
    canvas.repaint()
    canvas.close()


def test_open_recent_menu_section(qapp, tmp_path):
    """Validates that the File menu contains an Open Recent section with max 5 files directly in the menu (no submenu)."""
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.application import CaseInputDTO, SaveProjectUseCase

    # Clean up settings for test isolation
    from PySide6.QtCore import QSettings
    settings = QSettings("FlightcaseCalculator", "FlightcaseCalculator")
    settings.remove("recentProjects")

    # Create 6 distinct project files on disk
    project_paths = []
    for i in range(6):
        path = str(tmp_path / f"test_project_{i + 1}.fcproj")
        dto = CaseInputDTO(outer_length=800.0 + i * 50.0, outer_width=500.0, total_height=300.0)
        SaveProjectUseCase.execute(dto, path)
        project_paths.append(path)

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Verify File menu structure
    assert hasattr(window, "recent_section_action")
    assert hasattr(window, "recent_file_actions")
    assert len(window.recent_file_actions) == 5

    # Initially empty
    assert window._get_recent_files() == []
    assert window.recent_section_action.isVisible() is False

    # 2. Open 6 project files sequentially
    for path in project_paths:
        window._load_project_file(path)

    # 3. Verify exactly 5 most recent files are kept in MRU order (newest first)
    recent = window._get_recent_files()
    assert len(recent) == 5
    assert recent[0] == project_paths[5]  # project 6
    assert recent[1] == project_paths[4]  # project 5
    assert recent[2] == project_paths[3]  # project 4
    assert recent[3] == project_paths[2]  # project 3
    assert recent[4] == project_paths[1]  # project 2
    assert project_paths[0] not in recent  # project 1 fell off (limit 5)

    # 4. Verify menu actions are visible directly in the File menu
    assert window.recent_section_action.isVisible() is True
    for i in range(5):
        act = window.recent_file_actions[i]
        assert act.isVisible() is True
        assert act.isEnabled() is True
        assert f"&{i + 1} test_project_" in act.text()
        assert act.statusTip() == recent[i]

    # 5. Trigger recent file action 2 (project 4) and verify it loads and moves to top
    act_proj4 = window.recent_file_actions[2]
    assert "test_project_4" in act_proj4.text()
    act_proj4.trigger()

    assert window._current_project_path == project_paths[3]
    assert window.input_panel.spin_length.value() == 950.0  # 800 + 3*50
    assert window._get_recent_files()[0] == project_paths[3]

    # 6. Save a new project and verify it adds to recent files
    new_saved_path = str(tmp_path / "brand_new_case.fcproj")
    window._save_project_file(new_saved_path)
    assert window._get_recent_files()[0] == new_saved_path
    assert window.recent_file_actions[0].text() == "&1 brand_new_case.fcproj"

    window.close()
    settings.remove("recentProjects")


def test_top_and_bottom_panel_selection_does_not_highlight_lid_profile(qapp):
    """
    Validates that selecting top or bottom wood panels (both in standard and self-cut lid mode)
    highlights only the corresponding wood panels and does NOT highlight lid/base aluminum profiles.
    """
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Standard mode: Select "Base Bottom Panel"
    window.tabs.setCurrentIndex(0)
    bottom_row = -1
    top_row = -1
    for r, item in enumerate(window._current_result.wood_cut_list):
        if item.name == "Base Bottom Panel":
            bottom_row = r
        elif item.name == "Lid Top Panel":
            top_row = r

    assert bottom_row >= 0
    assert top_row >= 0

    # Select Base Bottom Panel
    window.cutlist_widget.table.selectRow(bottom_row)
    highlighted_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_faces) > 0
    # Must only highlight wood base bottom panel faces
    for f in highlighted_faces:
        assert f.color_group in ("base", "endgrain")
        assert "profile" not in f.label.lower()
        assert f.color_group != "profile"
        assert "lid" not in f.label.lower()

    # Select Lid Top Panel
    window.cutlist_widget.table.selectRow(top_row)
    highlighted_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_faces) > 0
    # Must only highlight wood lid top panel faces
    for f in highlighted_faces:
        assert f.color_group in ("lid", "endgrain")
        assert "profile" not in f.label.lower()
        assert f.color_group != "profile"
        assert "base" not in f.label.lower()

    # 2. Self-cut lid mode: Select "Bottom Panel" and "Top Panel"
    window.input_panel.set_self_cut_lid(True)
    sc_bottom_row = -1
    sc_top_row = -1
    for r, item in enumerate(window._current_result.wood_cut_list):
        if item.name == "Bottom Panel":
            sc_bottom_row = r
        elif item.name == "Top Panel":
            sc_top_row = r

    assert sc_bottom_row >= 0
    assert sc_top_row >= 0

    # Select Bottom Panel in self-cut mode
    window.cutlist_widget.table.selectRow(sc_bottom_row)
    highlighted_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_faces) > 0
    for f in highlighted_faces:
        assert f.color_group in ("base", "endgrain")
        assert "profile" not in f.label.lower()
        assert f.color_group != "profile"
        assert "lid" not in f.label.lower()

    # Select Top Panel in self-cut mode
    window.cutlist_widget.table.selectRow(sc_top_row)
    highlighted_faces = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_faces) > 0
    for f in highlighted_faces:
        assert f.color_group in ("lid", "endgrain")
        assert "profile" not in f.label.lower()
        assert f.color_group != "profile"
        assert "base" not in f.label.lower()

    # 3. Alu Profiles selection: selecting a profile should highlight only profiles, NOT wood panels
    window.tabs.setCurrentIndex(1)
    window.alu_widget.table_profiles.selectRow(0)  # Lid Hybrid Profile - Base Male (Long / Front-Back)
    highlighted_alu = [f for f in window.schema_widget.canvas.mesh.faces if window.schema_widget.canvas.is_face_highlighted(f)]
    assert len(highlighted_alu) > 0
    for f in highlighted_alu:
        assert f.color_group == "profile"
        assert "profile" in f.label.lower()

    window.close()


def test_schema_3d_widget_lid_rotation_ui_and_settings(qapp):
    """Validates that Schema3DWidget slider and hinge side combo manipulate lid rotation and serialize settings."""
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.ui.widgets import Schema3DWidget
    from flightcase.domain import FlightCase, Dimensions3D, Schema3DGeometryBuilder, ComponentLayer

    # 1. Test standalone Schema3DWidget controls
    widget = Schema3DWidget()
    assert widget.rotation_angle_deg == 0.0
    assert widget.hinge_side == "Back"

    # Manipulate slider
    widget.slider_angle.setValue(90)
    assert widget.rotation_angle_deg == 90.0
    assert widget.lbl_angle.text() == "90°"

    # Manipulate hinge side combo
    widget.combo_hinge.setCurrentText("Left")
    assert widget.hinge_side == "Left"

    # Helper method set_lid_rotation
    widget.set_lid_rotation(120.0, "Right")
    assert widget.rotation_angle_deg == 120.0
    assert widget.hinge_side == "Right"
    assert widget.lbl_angle.text() == "120°"

    # Get & Set UI settings
    ui_settings = widget.get_ui_settings()
    assert ui_settings.lid_rotation_angle_deg == 120.0
    assert ui_settings.lid_hinge_side == "Right"

    ui_settings.lid_rotation_angle_deg = 45.0
    ui_settings.lid_hinge_side = "Front"
    widget.set_ui_settings(ui_settings)
    assert widget.rotation_angle_deg == 45.0
    assert widget.hinge_side == "Front"
    assert widget.lbl_angle.text() == "45°"

    # 2. Test in MainWindow live update
    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    assert window.schema_widget.rotation_angle_deg == 0.0

    # Changing angle updates the canvas mesh
    window.schema_widget.slider_angle.setValue(90)
    lid_roof = [f for f in window.schema_widget.canvas.mesh.faces if f.layer_order == ComponentLayer.LID_ROOF]
    y_coords = [v.y for f in lid_roof for v in f.vertices]
    # Default Back hinge rotates lid backwards: max Y exceeds outer width (518)
    assert max(y_coords) > window._current_result.inner_width

    # Changing hinge side to Front rotates lid forwards: min Y becomes negative
    window.schema_widget.combo_hinge.setCurrentText("Front")
    lid_roof_front = [f for f in window.schema_widget.canvas.mesh.faces if f.layer_order == ComponentLayer.LID_ROOF]
    y_coords_front = [v.y for f in lid_roof_front for v in f.vertices]
    assert min(y_coords_front) < 0.0

    window.close()


def test_schema_3d_widget_explode_view_ui(qapp):
    """Validates that Schema3DWidget explode view slider controls exploded gap and generates panel dimensions."""
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.ui.widgets import Schema3DWidget

    # 1. Standalone Schema3DWidget controls
    widget = Schema3DWidget()
    assert widget.explode_gap_mm == 0.0
    assert widget.lbl_explode.text() == "0 mm"

    # Manipulate slider
    widget.slider_explode.setValue(80)
    assert widget.explode_gap_mm == 80.0
    assert widget.lbl_explode.text() == "80 mm"

    # Helper method set_explode_gap
    widget.set_explode_gap(120.0)
    assert widget.explode_gap_mm == 120.0
    assert widget.lbl_explode.text() == "120 mm"

    # Get & Set UI settings
    ui_settings = widget.get_ui_settings()
    assert ui_settings.explode_gap_mm == 120.0

    ui_settings.explode_gap_mm = 50.0
    widget.set_ui_settings(ui_settings)
    assert widget.explode_gap_mm == 50.0
    assert widget.lbl_explode.text() == "50 mm"

    # 2. Main Window integration
    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    assert window.schema_widget.explode_gap_mm == 0.0
    mesh_unexploded = window.schema_widget.canvas.mesh
    assert mesh_unexploded is not None
    assert len([d for d in mesh_unexploded.dimensions if d.dimension_type == "panel_dim"]) == 0

    # Moving explode slider updates 3D mesh with all panel dimensions
    window.schema_widget.slider_explode.setValue(75)
    assert window.schema_widget.explode_gap_mm == 75.0
    mesh = window.schema_widget.canvas.mesh
    assert mesh is not None
    panel_dims = [d for d in mesh.dimensions if d.dimension_type == "panel_dim"]
    assert len(panel_dims) >= 10
    assert any("Bottom Panel" in d.label for d in panel_dims)

    # Toggling self-cut lid ensures side panels are not split, marked with dashed cut line, and single height dimension
    window.input_panel.chk_self_cut_lid.setChecked(True)
    mesh_self_cut = window.schema_widget.canvas.mesh
    assert mesh_self_cut is not None
    # 6 solid panels (36 faces) instead of split panels
    assert len(mesh_self_cut.faces) == 36
    # Dashed cut segments present
    dashed_segs = [s for s in mesh_self_cut.segments if s.style == "dashed"]
    assert len(dashed_segs) == 16
    # Single height dimension per side wall (390 mm for default case)
    self_cut_panel_dims = [d for d in mesh_self_cut.dimensions if d.dimension_type == "panel_dim"]
    self_cut_labels = [d.label for d in self_cut_panel_dims]
    assert any("390 mm" in l for l in self_cut_labels)
    assert not any("295 mm" in l for l in self_cut_labels)
    assert not any("95 mm" in l for l in self_cut_labels)

    window.close()


def test_wood_panels_svg_widget_ui_and_export(qapp, tmp_path, monkeypatch):
    """Validates WoodPanelsSvgWidget rendering, zoom, export, and main window integration."""
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.ui.widgets import WoodPanelsSvgWidget
    from PySide6.QtWidgets import QFileDialog, QMessageBox, QApplication

    # 1. Standalone WoodPanelsSvgWidget
    svg_widget = WoodPanelsSvgWidget()
    sample_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 600" width="1000" height="600">'
        '<rect width="100%" height="100%" fill="#0f172a"/>'
        '<text x="50" y="50" fill="#ffffff">Sample Test SVG</text>'
        '</svg>'
    )
    svg_widget.set_svg(sample_svg)
    assert svg_widget.get_svg_data() == sample_svg

    # 2D Zoom & Pan controls
    assert svg_widget.lbl_zoom.text() == "100%"
    svg_widget._zoom_in()
    assert svg_widget._zoom_factor > 1.0
    svg_widget._zoom_out()
    svg_widget._reset_zoom()
    assert svg_widget._zoom_factor == 1.0
    assert svg_widget.lbl_zoom.text() == "100%"

    # Fit to view
    svg_widget.fit_to_view()
    assert svg_widget._zoom_factor > 0.0
    assert svg_widget.svg_view.backgroundBrush().color().name().lower() == "#ffffff"

    # 2D Viewport mouse interactions (wheel & drag pan simulation)
    from PySide6.QtGui import QWheelEvent, QMouseEvent
    from PySide6.QtCore import QPointF, QPoint

    # Wheel event
    wheel_ev = QWheelEvent(
        QPointF(100.0, 100.0),
        QPointF(100.0, 100.0),
        QPoint(0, 120),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    svg_widget.svg_view.wheelEvent(wheel_ev)
    assert svg_widget._zoom_factor > 0.0

    # Middle click pan simulation
    press_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(50.0, 50.0),
        QPointF(50.0, 50.0),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    svg_widget.svg_view.mousePressEvent(press_ev)
    assert svg_widget.svg_view._is_middle_panning is True

    move_ev = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPointF(80.0, 90.0),
        QPointF(80.0, 90.0),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    svg_widget.svg_view.mouseMoveEvent(move_ev)

    release_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonRelease,
        QPointF(80.0, 90.0),
        QPointF(80.0, 90.0),
        Qt.MouseButton.MiddleButton,
        Qt.MouseButton.MiddleButton,
        Qt.KeyboardModifier.NoModifier,
    )
    svg_widget.svg_view.mouseReleaseEvent(release_ev)
    assert svg_widget.svg_view._is_middle_panning is False

    # Double click fit simulation
    dbl_click_ev = QMouseEvent(
        QMouseEvent.Type.MouseButtonDblClick,
        QPointF(100.0, 100.0),
        QPointF(100.0, 100.0),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    svg_widget.svg_view.mouseDoubleClickEvent(dbl_click_ev)

    # Copy to clipboard
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args, **kwargs: None)
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    svg_widget._copy_svg_to_clipboard()
    assert "Sample Test SVG" in QApplication.clipboard().text()

    # Export SVG dialog simulation
    export_file = tmp_path / "exported_diagram.svg"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(export_file), "SVG Files (*.svg)")
    )

    svg_widget.export_svg()
    assert export_file.is_file()
    assert "Sample Test SVG" in export_file.read_text(encoding="utf-8")

    # 2. Main Window central tab integration
    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    assert window.svg_widget is not None
    assert window.tabs.count() == 3
    assert window.center_tabs.count() == 2
    assert window.center_tabs.widget(0) == window.schema_widget
    assert window.center_tabs.widget(1) == window.svg_widget

    # Recalculate populates SVG data
    assert "<svg" in window.svg_widget.get_svg_data()
    assert "FLIGHTCASE WOOD PANELS CUT DIAGRAM" in window.svg_widget.get_svg_data()

    # Menu view switching
    window._fit_svg_view()
    assert window.center_tabs.currentWidget() == window.svg_widget
    window._reset_3d_view()
    assert window.center_tabs.currentWidget() == window.schema_widget

    # Trigger export through cut list button and main window
    export_main_file = tmp_path / "from_mainwindow.svg"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda *args, **kwargs: (str(export_main_file), "SVG Files (*.svg)")
    )
    window._export_wood_panels_svg()
    assert export_main_file.is_file()
    assert "FLIGHTCASE WOOD PANELS CUT DIAGRAM" in export_main_file.read_text(encoding="utf-8")

    window.close()


def test_dark_desktop_theme_applied(qapp):
    from flightcase.ui.theme import DARK_THEME_QSS
    from flightcase.ui import FlightCaseMainWindow

    assert len(DARK_THEME_QSS) > 0
    assert "Section: Main" in DARK_THEME_QSS
    assert "Section: Buttons/Inputs" in DARK_THEME_QSS
    assert "Section: Views" in DARK_THEME_QSS

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    # Ensure individual widgets don't have hardcoded inline stylesheets overriding theme
    assert window.alu_widget.lbl_lid_profile_len.styleSheet() == ""
    assert window.alu_widget.lbl_edge_profile_len.styleSheet() == ""
    assert window.cutlist_widget.lbl_total_area.styleSheet() == ""
    assert window.cutlist_widget.lbl_weight.styleSheet() == ""
    assert window.cutlist_widget.lbl_sheets.styleSheet() == ""
    assert window.cutlist_widget.lbl_utilization.styleSheet() == ""
    assert window.walls_widget.lbl_comp_summary.styleSheet() == ""
    assert window.schema_widget.btn_proj_toggle.styleSheet() == ""
    window.close()


def test_project_title_and_svg_export_integration(qapp, monkeypatch, tmp_path):
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # Initial state
    assert window.input_panel.edit_title.text() == ""
    assert "Untitled" in window.windowTitle()
    assert "FLIGHTCASE WOOD PANELS CUT DIAGRAM" in window.svg_widget.get_svg_data()

    # Change title
    window.input_panel.edit_title.setText("Amp Rack Case")
    assert "Amp Rack Case" in window.windowTitle()
    assert "Amp Rack Case — Wood Panels Cut Diagram" in window.svg_widget.get_svg_data()

    # Test SVG export default filename uses project title
    saved_paths = []

    def mock_save_file_name(parent, caption, dir_or_file, filter_str):
        saved_paths.append(dir_or_file)
        out_file = tmp_path / "amp_rack_case_wood_panels_diagram.svg"
        return str(out_file), filter_str

    monkeypatch.setattr(QFileDialog, "getSaveFileName", mock_save_file_name)
    monkeypatch.setattr(QMessageBox, "information", lambda *args, **kwargs: None)

    window.svg_widget.export_svg()
    assert len(saved_paths) > 0
    assert "amp_rack_case_wood_panels_diagram.svg" in saved_paths[-1]

    # Save Project As suggests title as filename
    proj_dialog_defaults = []

    def mock_proj_save_file_name(parent, caption, dir_or_file, filter_str):
        proj_dialog_defaults.append(dir_or_file)
        return str(tmp_path / "amp_rack_case.fcproj"), filter_str

    monkeypatch.setattr(QFileDialog, "getSaveFileName", mock_proj_save_file_name)
    window._save_project_as()
    assert len(proj_dialog_defaults) > 0
    assert "amp_rack_case.fcproj" in proj_dialog_defaults[-1]

    window.close()


def test_3d_schema_view_bounding_box_stability(qapp):
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)
    mesh_init = window.schema_widget.canvas.mesh
    assert mesh_init is not None
    init_bb = mesh_init.bounding_box

    # Change explode gap
    window.schema_widget.set_explode_gap(100.0)
    window.recalculate()
    mesh_exploded = window.schema_widget.canvas.mesh
    assert mesh_exploded.bounding_box == init_bb

    # Change lid rotation angle
    window.schema_widget.set_lid_rotation(90.0, "Left")
    window.recalculate()
    mesh_rotated = window.schema_widget.canvas.mesh
    assert mesh_rotated.bounding_box == init_bb

    # Change lid split gap
    window.schema_widget.slider_gap.setValue(50)
    window.recalculate()
    mesh_gapped = window.schema_widget.canvas.mesh
    assert mesh_gapped.bounding_box == init_bb

    window.close()


def test_vertical_toolbars_layout_and_resizability(qapp):
    from flightcase.ui import FlightCaseMainWindow
    from PySide6.QtWidgets import QHBoxLayout, QScrollArea

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Verify 3D Schema Widget layout is horizontal with toolbar on the left
    schema_layout = window.schema_widget.layout()
    assert isinstance(schema_layout, QHBoxLayout)
    assert schema_layout.count() >= 2
    left_widget = schema_layout.itemAt(0).widget()
    assert isinstance(left_widget, QScrollArea)
    right_widget = schema_layout.itemAt(1).widget()
    assert right_widget == window.schema_widget.canvas

    # 2. Verify 2D Wood Panels SVG Widget layout is horizontal with toolbar on the left
    svg_layout = window.svg_widget.layout()
    assert isinstance(svg_layout, QHBoxLayout)
    assert svg_layout.count() >= 2
    left_svg_widget = svg_layout.itemAt(0).widget()
    assert isinstance(left_svg_widget, QScrollArea)
    right_svg_widget = svg_layout.itemAt(1).widget()
    assert right_svg_widget == window.svg_widget.svg_view

    # 3. Verify window can be resized down freely without toolbar horizontal overflow
    window.resize(800, 600)
    assert window.width() <= 800

    window.close()


def test_inside_walls_widget_uses_material_specifications_wood_type(qapp):
    """Verifies that InsideWallsWidget has no 'wall positions' tab and uses material specification wood type."""
    from flightcase.ui import FlightCaseMainWindow
    from PySide6.QtWidgets import QTabWidget

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Verify InsideWallsWidget does not contain a QTabWidget / "Wall Positions" tab
    assert not hasattr(window.walls_widget, "tabs_config")
    child_tabs = window.walls_widget.findChildren(QTabWidget)
    assert len(child_tabs) == 0

    # 2. Verify Compartments table has exactly 3 columns (Compartment, Auto-Equalize, Available Space)
    table = window.walls_widget.table_comps
    assert table.columnCount() == 3
    headers = [table.horizontalHeaderItem(c).text() for c in range(3)]
    assert headers == ["Compartment", "Auto-Equalize", "Available Space (mm)"]

    # 3. Select wood material "Bolivar plywood 12mm"
    idx_12 = window.input_panel.combo_wood_material.findText("Bolivar plywood 12mm")
    assert idx_12 >= 0
    window.input_panel.combo_wood_material.setCurrentIndex(idx_12)
    assert window.input_panel.spin_wood_thickness.value() == 12.0

    # Add compartments (2 walls)
    window.walls_widget._on_comp_tab_add()
    window.walls_widget._on_comp_tab_add()
    walls = window.walls_widget.get_walls()
    assert len(walls) == 2
    for w in walls:
        assert w.thickness_mm == 12.0

    # Verify cut list contains divider panels with 12.0 mm thickness
    window.recalculate()
    divider_cuts = [p for p in window._current_result.wood_cut_list if "divider" in p.category.lower() or "wall" in p.name.lower()]
    assert len(divider_cuts) == 2
    for dc in divider_cuts:
        assert dc.thickness_mm == 12.0

    # Switch to "Bolivar plywood 18mm"
    idx_18 = window.input_panel.combo_wood_material.findText("Bolivar plywood 18mm")
    assert idx_18 >= 0
    window.input_panel.combo_wood_material.setCurrentIndex(idx_18)
    window.recalculate()

    walls_18 = window.walls_widget.get_walls()
    for w in walls_18:
        assert w.thickness_mm == 18.0

    divider_cuts_18 = [p for p in window._current_result.wood_cut_list if "divider" in p.category.lower() or "wall" in p.name.lower()]
    for dc in divider_cuts_18:
        assert dc.thickness_mm == 18.0

    window.close()


def test_tables_scroll_per_pixel(qapp):
    """Verifies that all table widgets in the UI are configured to scroll per pixel."""
    from flightcase.ui import FlightCaseMainWindow
    from PySide6.QtWidgets import QAbstractItemView

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    tables = [
        window.cutlist_widget.table,
        window.alu_widget.table_profiles,
        window.alu_widget.table_comps,
        window.walls_widget.table_comps,
        window.wood_types_widget.table,
    ]

    for table in tables:
        assert table.verticalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel
        assert table.horizontalScrollMode() == QAbstractItemView.ScrollMode.ScrollPerPixel

    window.close()


def test_main_window_wood_types_tab(qapp):
    """Verifies that the Wood Types tab is present, editable, and synchronizes with input panel."""
    from flightcase.ui import FlightCaseMainWindow
    from flightcase.ui.widgets import WoodTypesWidget

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Verify tab presence
    assert hasattr(window, "wood_types_widget")
    assert isinstance(window.wood_types_widget, WoodTypesWidget)
    assert window.tabs.indexOf(window.wood_types_widget) >= 0
    assert window.tabs.tabText(window.tabs.indexOf(window.wood_types_widget)) == "Wood Types"

    # 2. Add a new wood type in the tab
    initial_rows = window.wood_types_widget.table.rowCount()
    window.wood_types_widget._on_add_material()
    assert window.wood_types_widget.table.rowCount() == initial_rows + 1

    # Verify input_panel combo includes the new material
    last_row = initial_rows
    new_mat_name = window.wood_types_widget.table.item(last_row, 1).text()
    idx = window.input_panel.combo_wood_material.findText(new_mat_name)
    assert idx >= 0

    # Select the new material in input panel and check thickness
    window.input_panel.combo_wood_material.setCurrentIndex(idx)
    assert window.input_panel.spin_wood_thickness.value() == 9.0

    # 3. Edit thickness in wood_types_widget and check that input_panel updates live
    thick_item = window.wood_types_widget.table.item(last_row, 2)
    thick_item.setText("13.5")
    assert window.input_panel.spin_wood_thickness.value() == 13.5

    window.close()


def test_about_menu_and_dialog_removed(qapp):
    """Verifies that the Help menu and About dialog action/method are removed."""
    from flightcase.ui import FlightCaseMainWindow

    window = FlightCaseMainWindow(restore_settings=False, load_last_project=False)

    # 1. Verify menu bar has no Help menu or About actions
    menu_bar = window.menuBar()
    menu_titles = [action.text().replace("&", "") for action in menu_bar.actions()]
    assert "Help" not in menu_titles
    assert "About" not in menu_titles

    # 2. Verify all actions in the window menu bar
    for menu_action in menu_bar.actions():
        menu = menu_action.menu()
        if menu:
            action_texts = [act.text().lower() for act in menu.actions()]
            assert not any("about" in t for t in action_texts)

    # 3. Verify _show_about method is removed
    assert not hasattr(window, "_show_about")

    window.close()
