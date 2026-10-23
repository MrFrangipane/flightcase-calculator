"""Application Use Cases orchestrating Domain Services and Entities."""

from __future__ import annotations
from typing import List, Tuple
from ..domain import (
    Dimensions3D,
    FlightCase,
    InsideWall,
    WallOrientation,
    FlightCaseDomainService,
    Schema3DGeometryBuilder,
    WoodPanelsSvgGenerator,
    WireframeMesh3D,
)
from .dtos import (
    CaseInputDTO,
    InsideWallDTO,
    CalculationResultDTO,
    CutPieceDTO,
    CaseCompartmentDTO,
)


class CalculateFlightCaseUseCase:
    """Use case to perform complete flightcase calculation from user input parameters."""

    @staticmethod
    def execute(input_dto: CaseInputDTO) -> CalculationResultDTO:
        # 1. Map input DTO to Domain Aggregate Root (Input dimensions are inner case dimensions)
        dimensions = Dimensions3D(
            length_mm=input_dto.inner_length,
            width_mm=input_dto.inner_width,
            height_mm=input_dto.inner_total_height,
        )

        domain_walls: List[InsideWall] = []
        for w_dto in input_dto.walls:
            orientation = (
                WallOrientation.WIDTH_WISE
                if w_dto.orientation.lower().startswith("width")
                else WallOrientation.LENGTH_WISE
            )
            domain_walls.append(InsideWall(
                orientation=orientation,
                position_mm=w_dto.position_mm,
                thickness_mm=w_dto.thickness_mm,
                height_mm=w_dto.height_mm,
                label=w_dto.label,
            ))

        flight_case = FlightCase(
            dimensions=dimensions,
            lid_height=input_dto.inner_lid_height,
            wood_thickness=input_dto.wood_thickness,
            lid_alu_profile_offset=input_dto.lid_alu_profile_offset,
            corner_extrusion_rebate=input_dto.corner_extrusion_rebate,
            edge_profile_width=input_dto.edge_profile_width,
            self_cut_lid=input_dto.self_cut_lid,
            _walls=domain_walls,
            wood_material=input_dto.wood_material,
            wood_density=input_dto.wood_density,
            wood_price=input_dto.wood_price,
        )

        # 2. Execute Domain Service
        report = FlightCaseDomainService.calculate(flight_case)

        # 3. Map Domain Entities/Value Objects to Output DTO
        wood_dtos = [
            CutPieceDTO(
                name=p.name,
                category=p.category.value,
                length_mm=p.length_mm,
                width_mm=p.width_mm,
                thickness_mm=p.thickness_mm,
                quantity=p.quantity,
                single_area_m2=p.single_area_m2,
                total_area_m2=p.total_area_m2,
                single_length_m=p.single_length_m,
                total_length_m=p.total_length_m,
                notes=p.notes,
            )
            for p in report.wood_cut_list
        ]

        alu_dtos = [
            CutPieceDTO(
                name=p.name,
                category=p.category.value,
                length_mm=p.length_mm,
                width_mm=p.width_mm,
                thickness_mm=p.thickness_mm,
                quantity=p.quantity,
                single_area_m2=p.single_area_m2,
                total_area_m2=p.total_area_m2,
                single_length_m=p.single_length_m,
                total_length_m=p.total_length_m,
                notes=p.notes,
            )
            for p in report.alu_profiles_list
        ]

        comp_dtos = [
            CaseCompartmentDTO(
                name=c.name,
                length_mm=c.length_mm,
                width_mm=c.width_mm,
                height_mm=c.height_mm,
                volume_liters=c.volume_liters,
            )
            for c in report.compartments
        ]

        return CalculationResultDTO(
            total_wood_area_m2=report.total_wood_area_m2,
            total_wood_weight_kg=report.total_wood_weight_kg,
            total_wood_cost=report.total_wood_cost,
            standard_sheets_required=report.standard_sheets_required,
            sheet_utilization_pct=report.sheet_utilization_pct,
            total_lid_mating_profile_length_mm=report.total_lid_mating_profile_length_mm,
            total_edge_angle_profile_length_mm=report.total_edge_angle_profile_length_mm,
            inner_length=flight_case.inner_length,
            inner_width=flight_case.inner_width,
            inner_base_height=flight_case.inner_base_height,
            inner_lid_height=flight_case.inner_lid_height,
            inner_total_height=flight_case.inner_total_height,
            base_wood_height=flight_case.base_wood_height,
            lid_wood_height=flight_case.lid_wood_height,
            total_wood_height=flight_case.total_wood_height,
            wood_cut_list=wood_dtos,
            alu_profiles_list=alu_dtos,
            compartments=comp_dtos,
        )


class GenerateSchema3DUseCase:
    """Use case to construct wireframe schema geometry for the 3D no-perspective display."""

    @staticmethod
    def execute(
        input_dto: CaseInputDTO,
        lid_exploded_gap_mm: float = 0.0,
        explode_gap_mm: float = 0.0,
        lid_rotation_angle_deg: float = 0.0,
        lid_hinge_side: str = "Back",
        show_inside_walls: bool = True,
        show_dimensions: bool = True,
        show_all_panel_dimensions: bool = True,
    ) -> WireframeMesh3D:
        dimensions = Dimensions3D(
            length_mm=input_dto.inner_length,
            width_mm=input_dto.inner_width,
            height_mm=input_dto.inner_total_height,
        )

        domain_walls: List[InsideWall] = []
        for w_dto in input_dto.walls:
            orientation = (
                WallOrientation.WIDTH_WISE
                if w_dto.orientation.lower().startswith("width")
                else WallOrientation.LENGTH_WISE
            )
            domain_walls.append(InsideWall(
                orientation=orientation,
                position_mm=w_dto.position_mm,
                thickness_mm=w_dto.thickness_mm,
                height_mm=w_dto.height_mm,
                label=w_dto.label,
            ))

        flight_case = FlightCase(
            dimensions=dimensions,
            lid_height=input_dto.inner_lid_height,
            wood_thickness=input_dto.wood_thickness,
            lid_alu_profile_offset=input_dto.lid_alu_profile_offset,
            corner_extrusion_rebate=input_dto.corner_extrusion_rebate,
            edge_profile_width=input_dto.edge_profile_width,
            self_cut_lid=input_dto.self_cut_lid,
            _walls=domain_walls,
            wood_material=input_dto.wood_material,
            wood_density=input_dto.wood_density,
            wood_price=input_dto.wood_price,
        )

        return Schema3DGeometryBuilder.build_geometry(
            case=flight_case,
            lid_exploded_gap_mm=lid_exploded_gap_mm,
            explode_gap_mm=explode_gap_mm,
            lid_rotation_angle_deg=lid_rotation_angle_deg,
            lid_hinge_side=lid_hinge_side,
            show_inside_walls=show_inside_walls,
            show_dimensions=show_dimensions,
            show_all_panel_dimensions=show_all_panel_dimensions,
        )


class GenerateWoodPanelsSvgUseCase:
    """Use case to generate vector SVG diagram of all wood panels with cut dimensions."""

    @staticmethod
    def execute(input_dto: CaseInputDTO) -> str:
        dimensions = Dimensions3D(
            length_mm=input_dto.inner_length,
            width_mm=input_dto.inner_width,
            height_mm=input_dto.inner_total_height,
        )

        domain_walls: List[InsideWall] = []
        for w_dto in input_dto.walls:
            orientation = (
                WallOrientation.WIDTH_WISE
                if w_dto.orientation.lower().startswith("width")
                else WallOrientation.LENGTH_WISE
            )
            domain_walls.append(InsideWall(
                orientation=orientation,
                position_mm=w_dto.position_mm,
                thickness_mm=w_dto.thickness_mm,
                height_mm=w_dto.height_mm,
                label=w_dto.label,
            ))

        flight_case = FlightCase(
            dimensions=dimensions,
            lid_height=input_dto.inner_lid_height,
            wood_thickness=input_dto.wood_thickness,
            lid_alu_profile_offset=input_dto.lid_alu_profile_offset,
            corner_extrusion_rebate=input_dto.corner_extrusion_rebate,
            edge_profile_width=input_dto.edge_profile_width,
            self_cut_lid=input_dto.self_cut_lid,
            _walls=domain_walls,
            wood_material=input_dto.wood_material,
            wood_density=input_dto.wood_density,
            wood_price=input_dto.wood_price,
        )

        return WoodPanelsSvgGenerator.generate_wood_panels_svg(flight_case, title=input_dto.title)


class SaveProjectUseCase:
    """Use case to serialize and save flightcase project configuration to a file."""

    @staticmethod
    def execute(input_dto: CaseInputDTO, file_path: str) -> None:
        json_content = input_dto.to_json(indent=2)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(json_content)


class LoadProjectUseCase:
    """Use case to load and deserialize flightcase project configuration from a file."""

    @staticmethod
    def execute(file_path: str) -> CaseInputDTO:
        with open(file_path, "r", encoding="utf-8") as f:
            json_content = f.read()
        return CaseInputDTO.from_json(json_content)
