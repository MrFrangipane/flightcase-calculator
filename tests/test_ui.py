"""Unit tests for PySide6 UI layer widgets."""

import os
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Run Qt headless in offscreen mode
os.environ["QT_QPA_PLATFORM"] = "offscreen"


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
    from flightcase.ui.widgets import Schema3DWidget
    from flightcase.domain import Dimensions3D, FlightCase, InsideWall, WallOrientation, Schema3DGeometryBuilder

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

    # Trigger repaint
    widget.canvas.repaint()
    widget.close()
