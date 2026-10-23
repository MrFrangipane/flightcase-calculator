"""Tests for wood materials loading, selection, and UI interactions."""

import pytest
from PySide6.QtWidgets import QApplication
from flightcase.domain.materials import (
    WoodMaterial,
    load_wood_materials,
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


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_load_wood_materials_from_json():
    materials = load_wood_materials()
    assert len(materials) >= 6
    
    # Verify Birch plywood 9mm default
    birch_9 = find_wood_material("Birch plywood 9mm", materials=materials)
    assert birch_9 is not None
    assert birch_9.thickness_mm == 9.0
    assert birch_9.density_kg_m3 == 700.0
    assert birch_9.price_per_m2 == 18.50
    assert birch_9.weight == 700.0
    assert birch_9.price == 18.50

    # Verify other materials (e.g. Poplar, Astroboard, Hexa)
    birch_65 = find_wood_material(thickness=6.5, materials=materials)
    assert birch_65 is not None
    assert birch_65.thickness_mm == 6.5


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
        wood_material="Birch plywood 12mm",
        wood_density=700.0,
        wood_price=24.00,
    )
    data = dto.to_dict()
    assert data["wood_material"] == "Birch plywood 12mm"
    assert data["wood_density"] == 700.0
    assert data["wood_price"] == 24.00

    loaded = CaseInputDTO.from_dict(data)
    assert loaded.wood_material == "Birch plywood 12mm"
    assert loaded.wood_thickness == 12.0
    assert loaded.wood_density == 700.0
    assert loaded.wood_price == 24.00


def test_case_input_panel_ui_wood_material_selection(qapp):
    panel = CaseInputPanel()

    # Default should be Birch plywood 9mm, read-only spinners
    assert panel.combo_wood_material.currentText() == "Birch plywood 9mm"
    assert panel.spin_wood_thickness.value() == 9.0
    assert panel.spin_wood_density.value() == 700.0
    assert panel.spin_wood_price.value() == 18.50
    assert panel.spin_wood_thickness.isReadOnly() is True
    assert panel.spin_wood_density.isReadOnly() is True
    assert panel.spin_wood_price.isReadOnly() is True

    # Select another preset
    idx_65 = panel.combo_wood_material.findText("Birch plywood 6.5mm")
    assert idx_65 >= 0
    panel.combo_wood_material.setCurrentIndex(idx_65)
    assert panel.spin_wood_thickness.value() == 6.5
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
        wood_material="Birch plywood 15mm",
        wood_thickness=15.0,
        wood_density=700.0,
        wood_price=29.50,
    )
    panel.set_input_dto(dto_std)
    assert panel.combo_wood_material.currentText() == "Birch plywood 15mm"
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
