"""Domain services for flightcase calculations and 3D wireframe schema generation."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .entities import FlightCase, CaseCompartment
from .value_objects import (
    Point3D,
    Segment3D,
    DimensionCallout3D,
    CutPiece,
    WallOrientation,
)


@dataclass
class FlightCaseCalculationReport:
    """Consolidated domain calculation output."""
    flight_case: FlightCase
    wood_cut_list: List[CutPiece]
    alu_profiles_list: List[CutPiece]
    compartments: List[CaseCompartment]
    
    # Material totals
    total_wood_area_m2: float
    total_wood_weight_kg: float
    standard_sheets_required: float
    sheet_utilization_pct: float
    
    total_lid_mating_profile_length_mm: float
    total_edge_angle_profile_length_mm: float


@dataclass
class WireframeMesh3D:
    """Calculated 3D wireframe elements and dimension callouts for no-perspective schema."""
    segments: List[Segment3D] = field(default_factory=list)
    dimensions: List[DimensionCallout3D] = field(default_factory=list)
    bounding_box: Tuple[Point3D, Point3D] = (Point3D(0, 0, 0), Point3D(0, 0, 0))


class FlightCaseDomainService:
    """Service to execute full domain calculations on a FlightCase entity."""

    @staticmethod
    def calculate(case: FlightCase) -> FlightCaseCalculationReport:
        wood_cuts = case.calculate_wood_cut_list()
        alu_cuts = case.calculate_alu_profiles()
        compartments = case.calculate_compartments()

        total_wood_area = sum(p.total_area_m2 for p in wood_cuts)
        # Volume in m³ = Area (m²) * thickness (m)
        total_wood_vol = sum((p.total_area_m2 * (p.thickness_mm / 1000.0)) for p in wood_cuts)
        wood_weight = total_wood_vol * 700.0  # Approx birch plywood 700 kg/m³

        # Standard plywood sheet 2440 x 1220 mm = 2.9768 m²
        sheet_area = (2440.0 * 1220.0) / 1_000_000.0
        sheets_req = total_wood_area / sheet_area if sheet_area > 0 else 0.0

        total_lid_mating_len = case.total_lid_alu_profile_length_mm
        total_edge_angle_len = case.total_edge_angle_profile_length_mm

        return FlightCaseCalculationReport(
            flight_case=case,
            wood_cut_list=wood_cuts,
            alu_profiles_list=alu_cuts,
            compartments=compartments,
            total_wood_area_m2=total_wood_area,
            total_wood_weight_kg=wood_weight,
            standard_sheets_required=sheets_req,
            sheet_utilization_pct=(sheets_req / max(1, math.ceil(sheets_req))) * 100.0 if sheets_req > 0 else 100.0,
            total_lid_mating_profile_length_mm=total_lid_mating_len,
            total_edge_angle_profile_length_mm=total_edge_angle_len,
        )


class Schema3DGeometryBuilder:
    """
    Constructs an axonometric / isometric parallel-projection 3D schema
    with exact dimensions, inside walls, lid separation, and callouts (without perspective distortion).
    """

    @staticmethod
    def build_geometry(
        case: FlightCase,
        lid_exploded_gap_mm: float = 0.0,
        show_inside_walls: bool = True,
        show_dimensions: bool = True
    ) -> WireframeMesh3D:
        segments: List[Segment3D] = []
        dimensions: List[DimensionCallout3D] = []

        L = case.outer_length
        W = case.outer_width
        H = case.total_height
        H_base = case.base_height
        H_lid = case.lid_height
        t_wood = case.wood_thickness
        gap = lid_exploded_gap_mm

        # Z coordinates
        z_base_bot = 0.0
        z_base_top = H_base
        z_lid_bot = H_base + gap
        z_lid_top = H_base + gap + H_lid

        # Helper to add a 3D box wireframe
        def add_box_wireframe(p_min: Point3D, p_max: Point3D, color_group: str, style: str = "solid"):
            x0, y0, z0 = p_min.x, p_min.y, p_min.z
            x1, y1, z1 = p_max.x, p_max.y, p_max.z

            # Bottom rectangle
            segments.append(Segment3D(Point3D(x0, y0, z0), Point3D(x1, y0, z0), style, color_group))
            segments.append(Segment3D(Point3D(x1, y0, z0), Point3D(x1, y1, z0), style, color_group))
            segments.append(Segment3D(Point3D(x1, y1, z0), Point3D(x0, y1, z0), style, color_group))
            segments.append(Segment3D(Point3D(x0, y1, z0), Point3D(x0, y0, z0), style, color_group))

            # Top rectangle
            segments.append(Segment3D(Point3D(x0, y0, z1), Point3D(x1, y0, z1), style, color_group))
            segments.append(Segment3D(Point3D(x1, y0, z1), Point3D(x1, y1, z1), style, color_group))
            segments.append(Segment3D(Point3D(x1, y1, z1), Point3D(x0, y1, z1), style, color_group))
            segments.append(Segment3D(Point3D(x0, y1, z1), Point3D(x0, y0, z1), style, color_group))

            # 4 Vertical pillars
            segments.append(Segment3D(Point3D(x0, y0, z0), Point3D(x0, y0, z1), style, color_group))
            segments.append(Segment3D(Point3D(x1, y0, z0), Point3D(x1, y0, z1), style, color_group))
            segments.append(Segment3D(Point3D(x1, y1, z0), Point3D(x1, y1, z1), style, color_group))
            segments.append(Segment3D(Point3D(x0, y1, z0), Point3D(x0, y1, z1), style, color_group))

        # 1. Base Box Outer Frame
        add_box_wireframe(
            Point3D(0, 0, z_base_bot),
            Point3D(L, W, z_base_top),
            color_group="base",
            style="solid"
        )

        # 2. Lid Box Outer Frame
        add_box_wireframe(
            Point3D(0, 0, z_lid_bot),
            Point3D(L, W, z_lid_top),
            color_group="lid",
            style="solid"
        )

        # 3. Alu Profile Band (Mating Extrusion indicator at split)
        # Rim along Base top
        segments.append(Segment3D(Point3D(0, 0, z_base_top), Point3D(L, 0, z_base_top), "profile", "profile"))
        segments.append(Segment3D(Point3D(L, 0, z_base_top), Point3D(L, W, z_base_top), "profile", "profile"))
        segments.append(Segment3D(Point3D(L, W, z_base_top), Point3D(0, W, z_base_top), "profile", "profile"))
        segments.append(Segment3D(Point3D(0, W, z_base_top), Point3D(0, 0, z_base_top), "profile", "profile"))

        # Rim along Lid bottom
        segments.append(Segment3D(Point3D(0, 0, z_lid_bot), Point3D(L, 0, z_lid_bot), "profile", "profile"))
        segments.append(Segment3D(Point3D(L, 0, z_lid_bot), Point3D(L, W, z_lid_bot), "profile", "profile"))
        segments.append(Segment3D(Point3D(L, W, z_lid_bot), Point3D(0, W, z_lid_bot), "profile", "profile"))
        segments.append(Segment3D(Point3D(0, W, z_lid_bot), Point3D(0, 0, z_lid_bot), "profile", "profile"))

        # 4. Interior Cavity Cavity Boundary (dashed inner wood boundaries)
        inner_x0 = t_wood
        inner_x1 = L - t_wood
        inner_y0 = t_wood
        inner_y1 = W - t_wood
        inner_z0 = t_wood

        # Inner floor outline
        segments.append(Segment3D(Point3D(inner_x0, inner_y0, inner_z0), Point3D(inner_x1, inner_y0, inner_z0), "dashed", "inner"))
        segments.append(Segment3D(Point3D(inner_x1, inner_y0, inner_z0), Point3D(inner_x1, inner_y1, inner_z0), "dashed", "inner"))
        segments.append(Segment3D(Point3D(inner_x1, inner_y1, inner_z0), Point3D(inner_x0, inner_y1, inner_z0), "dashed", "inner"))
        segments.append(Segment3D(Point3D(inner_x0, inner_y1, inner_z0), Point3D(inner_x0, inner_y0, inner_z0), "dashed", "inner"))

        # 5. Inside Partition Walls
        if show_inside_walls:
            for wall in case.walls:
                w_thick = wall.thickness_mm if wall.thickness_mm > 0 else t_wood
                w_height = wall.height_mm if (wall.height_mm is not None and wall.height_mm > 0) else case.inner_base_height
                z_top = inner_z0 + w_height

                if wall.orientation == WallOrientation.WIDTH_WISE:
                    # Wall placed at position_mm along inner length
                    x_center = inner_x0 + wall.position_mm
                    x_a = max(inner_x0, x_center - (w_thick / 2.0))
                    x_b = min(inner_x1, x_center + (w_thick / 2.0))

                    add_box_wireframe(
                        Point3D(x_a, inner_y0, inner_z0),
                        Point3D(x_b, inner_y1, z_top),
                        color_group="wall",
                        style="wall"
                    )
                else:
                    # Wall placed at position_mm along inner width
                    y_center = inner_y0 + wall.position_mm
                    y_a = max(inner_y0, y_center - (w_thick / 2.0))
                    y_b = min(inner_y1, y_center + (w_thick / 2.0))

                    add_box_wireframe(
                        Point3D(inner_x0, y_a, inner_z0),
                        Point3D(inner_x1, y_b, z_top),
                        color_group="wall",
                        style="wall"
                    )

        # 6. Dimensions Callouts
        if show_dimensions:
            # Dimension: Length (front edge along X)
            dimensions.append(DimensionCallout3D(
                start=Point3D(0, 0, 0),
                end=Point3D(L, 0, 0),
                label=f"L = {L:.0f} mm",
                value_mm=L,
                offset_vector=(0, -80, 0),
                dimension_type="length"
            ))

            # Dimension: Width (right edge along Y)
            dimensions.append(DimensionCallout3D(
                start=Point3D(L, 0, 0),
                end=Point3D(L, W, 0),
                label=f"W = {W:.0f} mm",
                value_mm=W,
                offset_vector=(80, 0, 0),
                dimension_type="width"
            ))

            # Dimension: Total Height (front-left corner along Z)
            dimensions.append(DimensionCallout3D(
                start=Point3D(0, 0, 0),
                end=Point3D(0, 0, H if gap == 0 else (H + gap)),
                label=f"H = {H:.0f} mm",
                value_mm=H,
                offset_vector=(-80, 0, 0),
                dimension_type="height"
            ))

            # Dimension: Base Height & Lid Height (back-left or front-left)
            dimensions.append(DimensionCallout3D(
                start=Point3D(0, W, 0),
                end=Point3D(0, W, H_base),
                label=f"Base = {H_base:.0f} mm",
                value_mm=H_base,
                offset_vector=(-60, 0, 0),
                dimension_type="base_height"
            ))

            dimensions.append(DimensionCallout3D(
                start=Point3D(0, W, z_lid_bot),
                end=Point3D(0, W, z_lid_top),
                label=f"Lid = {H_lid:.0f} mm",
                value_mm=H_lid,
                offset_vector=(-60, 0, 0),
                dimension_type="lid_height"
            ))

            # Divider Wall Positions
            for i, wall in enumerate(case.walls, start=1):
                if wall.orientation == WallOrientation.WIDTH_WISE:
                    x_pos = inner_x0 + wall.position_mm
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(inner_x0, 0, 0),
                        end=Point3D(x_pos, 0, 0),
                        label=f"Wall {i} = {wall.position_mm:.0f} mm",
                        value_mm=wall.position_mm,
                        offset_vector=(0, -40, 0),
                        dimension_type="wall_pos"
                    ))

        return WireframeMesh3D(
            segments=segments,
            dimensions=dimensions,
            bounding_box=(Point3D(0, 0, 0), Point3D(L, W, H + gap))
        )


class ParallelProjector:
    """
    Projects 3D coordinates onto a 2D screen coordinate plane without perspective distortion (isometric/axonometric).
    """

    def __init__(
        self,
        azimuth_deg: float = 45.0,
        elevation_deg: float = 30.0,
        scale: float = 1.0,
        origin_screen_x: float = 0.0,
        origin_screen_y: float = 0.0
    ):
        self.azimuth_deg = azimuth_deg
        self.elevation_deg = elevation_deg
        self.scale = scale
        self.origin_screen_x = origin_screen_x
        self.origin_screen_y = origin_screen_y

    def project_point(self, p: Point3D) -> Tuple[float, float, float]:
        """
        Projects (x, y, z) in mm to (screen_x, screen_y, depth_z).
        Using orthographic rotation angles without perspective division.
        """
        theta = math.radians(self.azimuth_deg)
        phi = math.radians(self.elevation_deg)

        cos_t, sin_t = math.cos(theta), math.sin(theta)
        cos_p, sin_p = math.cos(phi), math.sin(phi)

        # 1. Rotate around Z axis by azimuth
        x_rot = p.x * cos_t - p.y * sin_t
        y_rot = p.x * sin_t + p.y * cos_t
        z_rot = p.z

        # 2. Tilt by elevation angle
        # screen_x is horizontal axis
        # screen_y is vertical axis (inverted for Qt coordinate system where Y goes downward)
        screen_x = self.origin_screen_x + (x_rot * self.scale)
        screen_y = self.origin_screen_y - ((y_rot * sin_p + z_rot * cos_p) * self.scale)
        depth_z = y_rot * cos_p - z_rot * sin_p

        return screen_x, screen_y, depth_z
