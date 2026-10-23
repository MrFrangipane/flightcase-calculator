"""Tests for wood materials loading, selection, and UI interactions."""

import pytest
import json
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from flightcase.domain.materials import (
    WoodMaterial,
    load_wood_materials,
    save_wood_materials,
    find_wood_material,
)
from flightcase.domain import (
    FlightCase,
    Dimensions3D,
    FlightCaseDomainService,
)
from flightcase.application import (
    CaseInputDTO,
    CalculateFlightCaseUseCase,
)
from flightcase.ui.widgets.input_panel import CaseInputPanel
from flightcase.ui.widgets.wood_types_widget import WoodTypesWidget


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_load_wood_materials_from_json():
    materials = load_wood_materials()
    assert len(materials) >= 6

    # Verify Bolivar plywood 10mm from wood_types.json
    bolivar_10 = find_wood_material("Bolivar plywood 10mm", materials=materials)
    assert bolivar_10 is not None
    assert bolivar_10.thickness_mm == 10.0
    assert bolivar_10.density_kg_m3 == 500.0
    assert bolivar_10.price_per_m2 == 32.90
    assert bolivar_10.weight == 500.0
    assert bolivar_10.price == 32.90

    # Verify other materials
    bolivar_12 = find_wood_material(thickness=12.0, materials=materials)
    assert bolivar_12 is not None
    assert bolivar_12.thickness_mm == 12.0


def test_save_and_load_wood_materials(tmp_path: Path):
    temp_file = tmp_path / "custom_wood_types.json"
    custom_mats = [
        WoodMaterial(name="Test Birch 9mm", thickness_mm=9.0, density_kg_m3=700.0, price_per_m2=21.50, id="test_birch_9"),
        WoodMaterial(name="Test Oak 15mm", thickness_mm=15.0, density_kg_m3=800.0, price_per_m2=45.00, id="test_oak_15"),
    ]

    save_wood_materials(custom_mats, file_path=temp_file)
    assert temp_file.is_file()

    loaded = load_wood_materials(file_path=temp_file)
    assert len(loaded) == 2
    assert loaded[0].name == "Test Birch 9mm"
    assert loaded[0].thickness_mm == 9.0
    assert loaded[1].name == "Test Oak 15mm"
    assert loaded[1].price_per_m2 == 45.00


def test_wood_types_widget_lifecycle_and_editing(qapp, tmp_path: Path):
    widget = WoodTypesWidget()
    initial_count = widget.table.rowCount()
    assert initial_count >= 6

    # 1. Test adding a material
    received_materials = []
    widget.materials_changed.connect(lambda mats: received_materials.append(mats))

    widget._on_add_material()
    assert widget.table.rowCount() == initial_count + 1
    assert len(received_materials) == 1
    new_mats = widget.get_materials()
    assert new_mats[-1].name.startswith("Custom Wood")
    assert new_mats[-1].thickness_mm == 9.0

    # 2. Test editing in-table cell
    row_idx = initial_count
    name_item = widget.table.item(row_idx, 1)
    name_item.setText("Super Plywood 14mm")
    thick_item = widget.table.item(row_idx, 2)
    thick_item.setText("14.0")
    density_item = widget.table.item(row_idx, 3)
    density_item.setText("620.0")
    price_item = widget.table.item(row_idx, 4)
    price_item.setText("38.50")

    updated_mats = widget.get_materials()
    assert updated_mats[-1].name == "Super Plywood 14mm"
    assert updated_mats[-1].thickness_mm == 14.0
    assert updated_mats[-1].density_kg_m3 == 620.0
    assert updated_mats[-1].price_per_m2 == 38.50

    # 3. Test move up and move down
    widget.table.selectRow(row_idx)
    widget._on_move_up()
    mats_after_up = widget.get_materials()
    assert mats_after_up[row_idx - 1].name == "Super Plywood 14mm"

    widget._on_move_down()
    mats_after_down = widget.get_materials()
    assert mats_after_down[row_idx].name == "Super Plywood 14mm"

    # 4. Test delete material
    widget.table.selectRow(row_idx)
    widget._on_delete_material()
    assert widget.table.rowCount() == initial_count

    # 5. Test copy to clipboard
    widget._copy_to_clipboard()
    cb = QApplication.clipboard()
    if cb is not None:
        assert "Thickness" in cb.text()

    widget.close()


def test_wood_types_widget_save_and_reload(qapp, monkeypatch, tmp_path: Path):
    temp_json = tmp_path / "wood_types.json"
    initial_mats = [
        WoodMaterial(name="Wood A", thickness_mm=6.0, density_kg_m3=400.0, price_per_m2=12.0, id="wood_a"),
        WoodMaterial(name="Wood B", thickness_mm=12.0, density_kg_m3=600.0, price_per_m2=24.0, id="wood_b"),
    ]
    save_wood_materials(initial_mats, file_path=temp_json)

    widget = WoodTypesWidget()
    widget.load_materials(initial_mats)
    assert widget.table.rowCount() == 2

    # Add a row and test reload
    widget._on_add_material()
    assert widget.table.rowCount() == 3

    # Reload from initial_mats
    widget.load_materials(initial_mats)
    assert widget.table.rowCount() == 2


def test_flightcase_wood_cost_and_weight_calculation():
    dims = Dimensions3D(length_mm=800.0, width_mm=500.0, height_mm=400.0)
    case_standard = FlightCase(
        dimensions=dims,
        lid_height=100.0,
        wood_thickness=9.0,
        wood_density=700.0,
        wood_price=18.50,
    )
    report_std = FlightCaseDomainService.calculate(case_standard)
    assert report_std.total_wood_cost > 0.0
    expected_cost = report_std.total_wood_area_m2 * 18.50
    assert pytest.approx(report_std.total_wood_cost, rel=1e-3) == expected_cost

    # Poplar lighter wood
    case_poplar = FlightCase(
        dimensions=dims,
        lid_height=100.0,
        wood_thickness=9.0,
        wood_density=450.0,
        wood_price=16.00,
    )
    report_poplar = FlightCaseDomainService.calculate(case_poplar)
    assert report_poplar.total_wood_weight_kg < report_std.total_wood_weight_kg
    assert report_poplar.total_wood_cost < report_std.total_wood_cost


def test_case_input_dto_serialization_with_wood_material():
    dto = CaseInputDTO(
        inner_length=800.0,
        inner_width=500.0,
        inner_total_height=400.0,
        inner_lid_height=100.0,
        wood_thickness=12.0,
        wood_material="Bolivar plywood 12mm",
        wood_density=500.0,
        wood_price=39.91,
    )
    data = dto.to_dict()
    assert data["wood_material"] == "Bolivar plywood 12mm"
    assert data["wood_density"] == 500.0
    assert data["wood_price"] == 39.91

    loaded = CaseInputDTO.from_dict(data)
    assert loaded.wood_material == "Bolivar plywood 12mm"
    assert loaded.wood_thickness == 12.0
    assert loaded.wood_density == 500.0
    assert loaded.wood_price == 39.91


def test_case_input_panel_ui_wood_material_selection(qapp):
    panel = CaseInputPanel()

    # Default matches first material in wood_types.json
    first_mat = panel._wood_materials[0]
    assert panel.combo_wood_material.currentText() == first_mat.name
    assert panel.spin_wood_thickness.value() == first_mat.thickness_mm
    assert panel.spin_wood_density.value() == first_mat.density_kg_m3
    assert panel.spin_wood_price.value() == first_mat.price_per_m2
    assert panel.spin_wood_thickness.isReadOnly() is True
    assert panel.spin_wood_density.isReadOnly() is True
    assert panel.spin_wood_price.isReadOnly() is True

    # Select another preset
    idx_target = panel.combo_wood_material.findText("Bolivar plywood 10mm")
    if idx_target >= 0:
        panel.combo_wood_material.setCurrentIndex(idx_target)
        assert panel.spin_wood_thickness.value() == 10.0
        assert panel.spin_wood_thickness.isReadOnly() is True
        assert panel.spin_wood_density.isReadOnly() is True
        assert panel.spin_wood_price.isReadOnly() is True

    # Select Custom
    idx_custom = panel.combo_wood_material.findText("Custom")
    assert idx_custom >= 0
    panel.combo_wood_material.setCurrentIndex(idx_custom)
    assert panel.spin_wood_thickness.isReadOnly() is False
    assert panel.spin_wood_density.isReadOnly() is False
    assert panel.spin_wood_price.isReadOnly() is False

    # Edit custom values
    panel.spin_wood_thickness.setValue(10.5)
    panel.spin_wood_density.setValue(550.0)
    panel.spin_wood_price.setValue(22.00)

    dto = panel.get_input_dto()
    assert dto.wood_material == "Custom"
    assert dto.wood_thickness == 10.5
    assert dto.wood_density == 550.0
    assert dto.wood_price == 22.00


def test_case_input_panel_set_input_dto(qapp):
    panel = CaseInputPanel()

    # Setting standard preset DTO
    dto_std = CaseInputDTO(
        inner_length=1000.0,
        inner_width=600.0,
        inner_total_height=500.0,
        inner_lid_height=120.0,
        wood_material="Bolivar plywood 15mm",
        wood_thickness=15.0,
        wood_density=500.0,
        wood_price=44.89,
    )
    panel.set_input_dto(dto_std)
    assert panel.combo_wood_material.currentText() == "Bolivar plywood 15mm"
    assert panel.spin_wood_thickness.value() == 15.0
    assert panel.spin_wood_thickness.isReadOnly() is True
    assert panel.spin_wood_density.isReadOnly() is True
    assert panel.spin_wood_price.isReadOnly() is True

    # Setting custom DTO
    dto_custom = CaseInputDTO(
        inner_length=800.0,
        inner_width=500.0,
        inner_total_height=400.0,
        inner_lid_height=100.0,
        wood_material="Custom",
        wood_thickness=8.0,
        wood_density=620.0,
        wood_price=19.99,
    )
    panel.set_input_dto(dto_custom)
    assert panel.combo_wood_material.currentText() == "Custom"
    assert panel.spin_wood_thickness.value() == 8.0
    assert panel.spin_wood_density.value() == 620.0
    assert panel.spin_wood_price.value() == 19.99
    assert panel.spin_wood_thickness.isReadOnly() is False
    assert panel.spin_wood_density.isReadOnly() is False
    assert panel.spin_wood_price.isReadOnly() is False


def test_case_input_panel_set_wood_materials_dynamic(qapp):
    panel = CaseInputPanel()
    new_mats = [
        WoodMaterial(name="Custom Plywood 8mm", thickness_mm=8.0, density_kg_m3=480.0, price_per_m2=15.0, id="cp_8"),
        WoodMaterial(name="Custom Plywood 16mm", thickness_mm=16.0, density_kg_m3=520.0, price_per_m2=35.0, id="cp_16"),
    ]
    panel.set_wood_materials(new_mats)

    assert panel.combo_wood_material.count() == 3  # 2 mats + Custom
    assert panel.combo_wood_material.itemText(0) == "Custom Plywood 8mm"
    assert panel.combo_wood_material.itemText(1) == "Custom Plywood 16mm"
    assert panel.combo_wood_material.itemText(2) == "Custom"

    panel.combo_wood_material.setCurrentIndex(1)
    assert panel.spin_wood_thickness.value() == 16.0
    assert panel.spin_wood_density.value() == 520.0
    assert panel.spin_wood_price.value() == 35.0
