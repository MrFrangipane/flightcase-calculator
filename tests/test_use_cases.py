"""Unit tests for Application Layer Use Cases and DTOs."""

import pytest
from flightcase.application import (
    CaseInputDTO,
    InsideWallDTO,
    UISettingsDTO,
    CalculateFlightCaseUseCase,
    GenerateSchema3DUseCase,
    SaveProjectUseCase,
    LoadProjectUseCase,
)


def test_calculate_flightcase_use_case():
    input_dto = CaseInputDTO(
        outer_length=800.0,
        outer_width=500.0,
        total_height=400.0,
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        walls=[
            InsideWallDTO(
                orientation="width_wise",
                position_mm=250.0,
                thickness_mm=9.0,
                label="Divider A"
            )
        ]
    )

    result = CalculateFlightCaseUseCase.execute(input_dto)

    # 1. Wood Panels Cut List
    assert len(result.wood_cut_list) == 7  # 6 main panels + 1 divider
    divider_item = next(p for p in result.wood_cut_list if "Divider A" in p.name)
    assert divider_item.length_mm == 482.0  # inner width
    assert divider_item.quantity == 1

    # 2. Lid Alu Profile Required Length
    assert result.total_lid_mating_profile_length_mm == 5200.0  # 2 * 2 * (800 + 500)

    # 3. Dimensions
    assert result.inner_length == 782.0
    assert result.inner_width == 482.0
    assert result.inner_base_height == 286.0

    # 4. Compartments
    assert len(result.compartments) == 2


def test_generate_schema_3d_use_case():
    input_dto = CaseInputDTO(
        outer_length=800.0,
        outer_width=500.0,
        total_height=400.0,
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        walls=[
            InsideWallDTO(
                orientation="width_wise",
                position_mm=300.0,
                thickness_mm=9.0,
                label="Wall 1"
            )
        ]
    )

    mesh = GenerateSchema3DUseCase.execute(
        input_dto=input_dto,
        lid_exploded_gap_mm=40.0,
        show_inside_walls=True,
        show_dimensions=True,
    )

    assert len(mesh.segments) > 20
    assert len(mesh.dimensions) >= 5


def test_self_cut_lid_use_cases():
    input_dto = CaseInputDTO(
        outer_length=800.0,
        outer_width=500.0,
        total_height=400.0,
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        self_cut_lid=True,
    )

    # Calculate use case produces 4 piece items (6 panels)
    result = CalculateFlightCaseUseCase.execute(input_dto)
    assert len(result.wood_cut_list) == 4
    assert sum(p.quantity for p in result.wood_cut_list) == 6

    # 3D Schema generation use case keeps the lid and base
    mesh = GenerateSchema3DUseCase.execute(input_dto=input_dto, lid_exploded_gap_mm=30.0)
    assert len(mesh.faces) > 0
    color_groups = {f.color_group for f in mesh.faces}
    assert "base" in color_groups
    assert "lid" in color_groups


def test_project_serialization_roundtrip(tmp_path):
    dto = CaseInputDTO(
        outer_length=1200.0,
        outer_width=600.0,
        total_height=500.0,
        lid_height=120.0,
        wood_thickness=12.0,
        lid_alu_profile_offset=15.0,
        corner_extrusion_rebate=2.0,
        edge_profile_width=35.0,
        self_cut_lid=True,
        walls=[
            InsideWallDTO(
                orientation="length_wise",
                position_mm=200.0,
                thickness_mm=12.0,
                height_mm=250.0,
                label="Long Divider 1",
            ),
            InsideWallDTO(
                orientation="width_wise",
                position_mm=400.0,
                thickness_mm=9.0,
                height_mm=None,
                label="Cross Divider 2",
            ),
        ],
    )

    # 1. Test JSON string conversion
    json_str = dto.to_json()
    loaded_dto = CaseInputDTO.from_json(json_str)

    assert loaded_dto.outer_length == 1200.0
    assert loaded_dto.outer_width == 600.0
    assert loaded_dto.total_height == 500.0
    assert loaded_dto.lid_height == 120.0
    assert loaded_dto.wood_thickness == 12.0
    assert loaded_dto.lid_alu_profile_offset == 15.0
    assert loaded_dto.corner_extrusion_rebate == 2.0
    assert loaded_dto.edge_profile_width == 35.0
    assert loaded_dto.self_cut_lid is True
    assert len(loaded_dto.walls) == 2
    assert loaded_dto.walls[0].label == "Long Divider 1"
    assert loaded_dto.walls[0].orientation == "length_wise"
    assert loaded_dto.walls[0].height_mm == 250.0
    assert loaded_dto.walls[1].label == "Cross Divider 2"
    assert loaded_dto.walls[1].height_mm is None

    # 2. Test File Save and Load Use Cases
    file_path = str(tmp_path / "test_project.fcproj")
    SaveProjectUseCase.execute(dto, file_path)

    loaded_from_file = LoadProjectUseCase.execute(file_path)
    assert loaded_from_file.outer_length == 1200.0
    assert loaded_from_file.self_cut_lid is True
    assert len(loaded_from_file.walls) == 2
    assert loaded_from_file.walls[0].label == "Long Divider 1"


def test_ui_settings_dto_serialization_and_backward_compatibility(tmp_path):
    ui_dto = UISettingsDTO(
        camera_azimuth_deg=135.0,
        camera_elevation_deg=45.0,
        camera_zoom=2.5,
        camera_pan_x=50.0,
        camera_pan_y=-30.0,
        is_perspective=True,
        lid_exploded_gap_mm=75.0,
        show_dimensions=False,
        show_inside_walls=True,
        show_axes=False,
        active_tab_index=2,
        compartment_orientation="length_wise",
        auto_equalize_flags=[True, False, True],
    )

    case_dto = CaseInputDTO(
        outer_length=900.0,
        outer_width=450.0,
        total_height=350.0,
        ui_settings=ui_dto,
    )

    # 1. Roundtrip JSON
    json_str = case_dto.to_json()
    loaded = CaseInputDTO.from_json(json_str)

    assert loaded.ui_settings.camera_azimuth_deg == 135.0
    assert loaded.ui_settings.camera_elevation_deg == 45.0
    assert loaded.ui_settings.camera_zoom == 2.5
    assert loaded.ui_settings.camera_pan_x == 50.0
    assert loaded.ui_settings.camera_pan_y == -30.0
    assert loaded.ui_settings.is_perspective is True
    assert loaded.ui_settings.lid_exploded_gap_mm == 75.0
    assert loaded.ui_settings.show_dimensions is False
    assert loaded.ui_settings.show_inside_walls is True
    assert loaded.ui_settings.show_axes is False
    assert loaded.ui_settings.active_tab_index == 2
    assert loaded.ui_settings.compartment_orientation == "length_wise"
    assert loaded.ui_settings.auto_equalize_flags == [True, False, True]

    # 2. Backward compatibility with project JSON that has no "ui_settings" key
    legacy_json = '{"version": "1.0", "outer_length": 800.0, "walls": []}'
    legacy_loaded = CaseInputDTO.from_json(legacy_json)
    assert legacy_loaded.ui_settings is not None
    assert legacy_loaded.ui_settings.camera_azimuth_deg == 45.0
    assert legacy_loaded.ui_settings.show_dimensions is True
    assert legacy_loaded.ui_settings.is_perspective is False
    assert legacy_loaded.ui_settings.compartment_orientation == "width_wise"
    assert legacy_loaded.ui_settings.auto_equalize_flags == []

    # 3. Backward compatibility with legacy "equispaced_walls_orientation"
    legacy_gen_json = '{"version": "1.0", "outer_length": 800.0, "ui_settings": {"equispaced_walls_orientation": "length_wise"}}'
    legacy_gen_loaded = CaseInputDTO.from_json(legacy_gen_json)
    assert legacy_gen_loaded.ui_settings.compartment_orientation == "length_wise"
