"""Unit tests for Application Layer Use Cases and DTOs."""

import pytest
from flightcase.application import (
    CaseInputDTO,
    InsideWallDTO,
    CalculateFlightCaseUseCase,
    GenerateSchema3DUseCase,
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
