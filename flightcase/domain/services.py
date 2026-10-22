"""Domain services for flightcase calculations and 3D wireframe schema generation."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Tuple
from .entities import FlightCase, CaseCompartment
from .value_objects import (
    Point3D,
    Segment3D,
    PolygonFace3D,
    DimensionCallout3D,
    CutPiece,
    WallOrientation,
    ComponentLayer,
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
    """Calculated 3D mesh elements, solid faces, and dimension callouts for schema rendering."""
    faces: List[PolygonFace3D] = field(default_factory=list)
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
    with solid volumetric panels showing exact panel thicknesses, partition walls,
    lid separation, and callouts without perspective distortion or hidden lines.
    """

    @staticmethod
    def build_geometry(
        case: FlightCase,
        lid_exploded_gap_mm: float = 0.0,
        explode_gap_mm: float = 0.0,
        lid_rotation_angle_deg: float = 0.0,
        lid_hinge_side: str = "Back",
        show_inside_walls: bool = True,
        show_dimensions: bool = True,
        show_all_panel_dimensions: bool = True,
    ) -> WireframeMesh3D:
        faces: List[PolygonFace3D] = []
        segments: List[Segment3D] = []
        dimensions: List[DimensionCallout3D] = []

        L = case.outer_length
        W = case.outer_width
        H = case.total_height
        H_base = case.base_height
        H_lid = case.outer_lid_height
        t_wood = case.wood_thickness
        gap = lid_exploded_gap_mm
        ex = max(0.0, explode_gap_mm)

        # Z coordinates
        z_base_bot = 0.0
        z_base_top = H_base
        z_lid_bot = H_base + gap
        z_lid_top = H_base + gap + H_lid

        theta = math.radians(lid_rotation_angle_deg)
        side_norm = (lid_hinge_side or "Back").strip().capitalize()
        z_hinge = z_lid_bot

        def transform_lid_point(p: Point3D) -> Point3D:
            if theta == 0.0:
                return p
            cos_a = math.cos(theta)
            sin_a = math.sin(theta)

            if side_norm == "Front":
                # Hinge at Y = 0, Z = z_hinge
                dy = p.y
                dz = p.z - z_hinge
                dy_rot = dy * cos_a - dz * sin_a
                dz_rot = dy * sin_a + dz * cos_a
                return Point3D(p.x, dy_rot, z_hinge + dz_rot)
            elif side_norm == "Left":
                # Hinge at X = 0, Z = z_hinge
                dx = p.x
                dz = p.z - z_hinge
                dx_rot = dx * cos_a - dz * sin_a
                dz_rot = dx * sin_a + dz * cos_a
                return Point3D(dx_rot, p.y, z_hinge + dz_rot)
            elif side_norm == "Right":
                # Hinge at X = L, Z = z_hinge
                dx = p.x - L
                dz = p.z - z_hinge
                dx_rot = dx * cos_a + dz * sin_a
                dz_rot = -dx * sin_a + dz * cos_a
                return Point3D(L + dx_rot, p.y, z_hinge + dz_rot)
            else:  # "Back" (default)
                # Hinge at Y = W, Z = z_hinge
                dy = p.y - W
                dz = p.z - z_hinge
                dy_rot = dy * cos_a + dz * sin_a
                dz_rot = -dy * sin_a + dz * cos_a
                return Point3D(p.x, W + dy_rot, z_hinge + dz_rot)

        def transform_lid_normal(n: Tuple[float, float, float]) -> Tuple[float, float, float]:
            if theta == 0.0:
                return n
            cos_a = math.cos(theta)
            sin_a = math.sin(theta)
            nx, ny, nz = n

            if side_norm == "Front":
                ny_rot = ny * cos_a - nz * sin_a
                nz_rot = ny * sin_a + nz * cos_a
                return (nx, ny_rot, nz_rot)
            elif side_norm == "Left":
                nx_rot = nx * cos_a - nz * sin_a
                nz_rot = nx * sin_a + nz * cos_a
                return (nx_rot, ny, nz_rot)
            elif side_norm == "Right":
                nx_rot = nx * cos_a + nz * sin_a
                nz_rot = -nx * sin_a + nz * cos_a
                return (nx_rot, ny, nz_rot)
            else:  # "Back"
                ny_rot = ny * cos_a + nz * sin_a
                nz_rot = -ny * sin_a + nz * cos_a
                return (nx, ny_rot, nz_rot)

        # Helper to add a solid volumetric cuboid box with 6 outward-facing polygonal faces and wireframe segments
        def add_solid_box(
            p_min: Point3D,
            p_max: Point3D,
            color_group: str,
            label: str = "",
            highlight_top_endgrain: bool = False,
            layer_order: int = ComponentLayer.BASE_FLOOR,
            wall_index: Optional[int] = None,
            is_lid: bool = False,
            offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
        ) -> None:
            ox, oy, oz = offset
            x0, y0, z0 = p_min.x + ox, p_min.y + oy, p_min.z + oz
            x1, y1, z1 = p_max.x + ox, p_max.y + oy, p_max.z + oz

            # Avoid degenerate zero-volume boxes
            if x1 <= x0 or y1 <= y0 or z1 <= z0:
                return

            def pt(x: float, y: float, z: float) -> Point3D:
                p = Point3D(x, y, z)
                return transform_lid_point(p) if (is_lid and theta != 0.0) else p

            def norm(nx: float, ny: float, nz: float) -> Tuple[float, float, float]:
                return transform_lid_normal((nx, ny, nz)) if (is_lid and theta != 0.0) else (nx, ny, nz)

            # 1. Bottom (-Z)
            faces.append(PolygonFace3D(
                vertices=(pt(x0, y0, z0), pt(x0, y1, z0), pt(x1, y1, z0), pt(x1, y0, z0)),
                normal=norm(0.0, 0.0, -1.0),
                color_group=color_group,
                label=label,
                is_endgrain=False,
                layer_order=layer_order,
                wall_index=wall_index,
            ))

            # 2. Top (+Z)
            faces.append(PolygonFace3D(
                vertices=(pt(x0, y0, z1), pt(x1, y0, z1), pt(x1, y1, z1), pt(x0, y1, z1)),
                normal=norm(0.0, 0.0, 1.0),
                color_group="endgrain" if highlight_top_endgrain else color_group,
                label=label,
                is_endgrain=highlight_top_endgrain,
                layer_order=layer_order,
                wall_index=wall_index,
            ))

            # 3. Front (-Y)
            faces.append(PolygonFace3D(
                vertices=(pt(x0, y0, z0), pt(x1, y0, z0), pt(x1, y0, z1), pt(x0, y0, z1)),
                normal=norm(0.0, -1.0, 0.0),
                color_group=color_group,
                label=label,
                is_endgrain=False,
                layer_order=layer_order,
                wall_index=wall_index,
            ))

            # 4. Back (+Y)
            faces.append(PolygonFace3D(
                vertices=(pt(x1, y1, z0), pt(x0, y1, z0), pt(x0, y1, z1), pt(x1, y1, z1)),
                normal=norm(0.0, 1.0, 0.0),
                color_group=color_group,
                label=label,
                is_endgrain=False,
                layer_order=layer_order,
                wall_index=wall_index,
            ))

            # 5. Left (-X)
            faces.append(PolygonFace3D(
                vertices=(pt(x0, y1, z0), pt(x0, y0, z0), pt(x0, y0, z1), pt(x0, y1, z1)),
                normal=norm(-1.0, 0.0, 0.0),
                color_group=color_group,
                label=label,
                is_endgrain=False,
                layer_order=layer_order,
                wall_index=wall_index,
            ))

            # 6. Right (+X)
            faces.append(PolygonFace3D(
                vertices=(pt(x1, y0, z0), pt(x1, y1, z0), pt(x1, y1, z1), pt(x1, y0, z1)),
                normal=norm(1.0, 0.0, 0.0),
                color_group=color_group,
                label=label,
                is_endgrain=False,
                layer_order=layer_order,
                wall_index=wall_index,
            ))

            # Wireframe bounding segments (for wireframe modes / fallback)
            # Bottom
            segments.append(Segment3D(pt(x0, y0, z0), pt(x1, y0, z0), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x1, y0, z0), pt(x1, y1, z0), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x1, y1, z0), pt(x0, y1, z0), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x0, y1, z0), pt(x0, y0, z0), "solid", color_group, label=label, wall_index=wall_index))
            # Top
            segments.append(Segment3D(pt(x0, y0, z1), pt(x1, y0, z1), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x1, y0, z1), pt(x1, y1, z1), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x1, y1, z1), pt(x0, y1, z1), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x0, y1, z1), pt(x0, y0, z1), "solid", color_group, label=label, wall_index=wall_index))
            # Verticals
            segments.append(Segment3D(pt(x0, y0, z0), pt(x0, y0, z1), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x1, y0, z0), pt(x1, y0, z1), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x1, y1, z0), pt(x1, y1, z1), "solid", color_group, label=label, wall_index=wall_index))
            segments.append(Segment3D(pt(x0, y1, z0), pt(x0, y1, z1), "solid", color_group, label=label, wall_index=wall_index))

        # Aluminum profile offset: height induced by profile on each half (base & lid)
        profile_h = max(0.0, case.lid_alu_profile_offset / 2.0)
        is_exploded_self_cut = (case.self_cut_lid and ex > 0)
        h_total_wood = case.total_wood_height
        z_side_top = z_base_bot + t_wood + h_total_wood
        z_cut = z_base_bot + t_wood + case.base_wood_height

        # --- 1. Base Box / Uncut Solid Panels with Panel Thickness ---
        # Base Bottom Floor Panel: spans [0, L] x [0, W] x [0, t_wood]
        add_solid_box(
            Point3D(0, 0, z_base_bot),
            Point3D(L, W, z_base_bot + t_wood),
            color_group="base",
            label="Bottom Panel" if case.self_cut_lid else "Base Bottom Panel",
            layer_order=ComponentLayer.BASE_FLOOR,
            offset=(0.0, 0.0, -ex),
        )

        if is_exploded_self_cut:
            # Full-height uncut side panels (not split for lid) with dashed cut lines
            # Front Long Side
            add_solid_box(
                Point3D(0, 0, z_base_bot + t_wood),
                Point3D(L, t_wood, z_side_top),
                color_group="base",
                label="Long Sides (Front & Back)",
                highlight_top_endgrain=True,
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(0.0, -ex, 0.0),
            )
            # Dashed lid cut lines around front panel at z_cut
            segments.append(Segment3D(Point3D(0, -ex, z_cut), Point3D(L, -ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(0, t_wood - ex, z_cut), Point3D(L, t_wood - ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(0, -ex, z_cut), Point3D(0, t_wood - ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(L, -ex, z_cut), Point3D(L, t_wood - ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))

            # Back Long Side
            add_solid_box(
                Point3D(0, W - t_wood, z_base_bot + t_wood),
                Point3D(L, W, z_side_top),
                color_group="base",
                label="Long Sides (Front & Back)",
                highlight_top_endgrain=True,
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(0.0, ex, 0.0),
            )
            # Dashed lid cut lines around back panel at z_cut
            segments.append(Segment3D(Point3D(0, W + ex, z_cut), Point3D(L, W + ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(0, W - t_wood + ex, z_cut), Point3D(L, W - t_wood + ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(0, W - t_wood + ex, z_cut), Point3D(0, W + ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(L, W - t_wood + ex, z_cut), Point3D(L, W + ex, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))

            # Left Short Side
            add_solid_box(
                Point3D(0, t_wood, z_base_bot + t_wood),
                Point3D(t_wood, W - t_wood, z_side_top),
                color_group="base",
                label="Short Sides (Left & Right)",
                highlight_top_endgrain=True,
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(-ex, 0.0, 0.0),
            )
            # Dashed lid cut lines around left panel at z_cut
            segments.append(Segment3D(Point3D(-ex, t_wood, z_cut), Point3D(-ex, W - t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(t_wood - ex, t_wood, z_cut), Point3D(t_wood - ex, W - t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(-ex, t_wood, z_cut), Point3D(t_wood - ex, t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(-ex, W - t_wood, z_cut), Point3D(t_wood - ex, W - t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))

            # Right Short Side
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_base_bot + t_wood),
                Point3D(L, W - t_wood, z_side_top),
                color_group="base",
                label="Short Sides (Left & Right)",
                highlight_top_endgrain=True,
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(ex, 0.0, 0.0),
            )
            # Dashed lid cut lines around right panel at z_cut
            segments.append(Segment3D(Point3D(L + ex, t_wood, z_cut), Point3D(L + ex, W - t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(L - t_wood + ex, t_wood, z_cut), Point3D(L - t_wood + ex, W - t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(L - t_wood + ex, t_wood, z_cut), Point3D(L + ex, t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))
            segments.append(Segment3D(Point3D(L - t_wood + ex, W - t_wood, z_cut), Point3D(L + ex, W - t_wood, z_cut), style="dashed", color_group="profile", label="Lid Cut Line"))

        else:
            # Base Long Sides (Front & Back Panels):
            # Front panel: [0, L] x [0, t_wood] x [t_wood, z_base_top - profile_h]
            add_solid_box(
                Point3D(0, 0, z_base_bot + t_wood),
                Point3D(L, t_wood, z_base_top - profile_h),
                color_group="base",
                label="Base Front Panel",
                highlight_top_endgrain=(profile_h == 0.0),
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(0.0, -ex, 0.0),
            )
            # Back panel: [0, L] x [W - t_wood, W] x [t_wood, z_base_top - profile_h]
            add_solid_box(
                Point3D(0, W - t_wood, z_base_bot + t_wood),
                Point3D(L, W, z_base_top - profile_h),
                color_group="base",
                label="Base Back Panel",
                highlight_top_endgrain=(profile_h == 0.0),
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(0.0, ex, 0.0),
            )

            # Base Short Sides (Left & Right Panels, inset between front and back):
            # Left panel: [0, t_wood] x [t_wood, W - t_wood] x [t_wood, z_base_top - profile_h]
            add_solid_box(
                Point3D(0, t_wood, z_base_bot + t_wood),
                Point3D(t_wood, W - t_wood, z_base_top - profile_h),
                color_group="base",
                label="Base Left Panel",
                highlight_top_endgrain=(profile_h == 0.0),
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(-ex, 0.0, 0.0),
            )
            # Right panel: [L - t_wood, L] x [t_wood, W - t_wood] x [t_wood, z_base_top - profile_h]
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_base_bot + t_wood),
                Point3D(L, W - t_wood, z_base_top - profile_h),
                color_group="base",
                label="Base Right Panel",
                highlight_top_endgrain=(profile_h == 0.0),
                layer_order=ComponentLayer.OUTER_BASE_WALLS,
                offset=(ex, 0.0, 0.0),
            )

        # --- 2. Lid Box Volumetric Panels with Panel Thickness ---
        # Lid Top Roof Panel: spans [0, L] x [0, W] x [z_lid_top - t_wood, z_lid_top]
        add_solid_box(
            Point3D(0, 0, z_lid_top - t_wood),
            Point3D(L, W, z_lid_top),
            color_group="lid",
            label="Top Panel" if case.self_cut_lid else "Lid Top Panel",
            layer_order=ComponentLayer.LID_ROOF,
            is_lid=True,
            offset=(0.0, 0.0, ex),
        )

        if not is_exploded_self_cut:
            # Lid Long Sides (Front & Back Panels):
            # Front panel: [0, L] x [0, t_wood] x [z_lid_bot + profile_h, z_lid_top - t_wood]
            add_solid_box(
                Point3D(0, 0, z_lid_bot + profile_h),
                Point3D(L, t_wood, z_lid_top - t_wood),
                color_group="lid",
                label="Lid Front Panel",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(0.0, -ex, 0.0),
            )
            # Back panel: [0, L] x [W - t_wood, W] x [z_lid_bot + profile_h, z_lid_top - t_wood]
            add_solid_box(
                Point3D(0, W - t_wood, z_lid_bot + profile_h),
                Point3D(L, W, z_lid_top - t_wood),
                color_group="lid",
                label="Lid Back Panel",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(0.0, ex, 0.0),
            )

            # Lid Short Sides (Left & Right Panels):
            # Left panel: [0, t_wood] x [t_wood, W - t_wood] x [z_lid_bot + profile_h, z_lid_top - t_wood]
            add_solid_box(
                Point3D(0, t_wood, z_lid_bot + profile_h),
                Point3D(t_wood, W - t_wood, z_lid_top - t_wood),
                color_group="lid",
                label="Lid Left Panel",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(-ex, 0.0, 0.0),
            )
            # Right panel: [L - t_wood, L] x [t_wood, W - t_wood] x [z_lid_bot + profile_h, z_lid_top - t_wood]
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_lid_bot + profile_h),
                Point3D(L, W - t_wood, z_lid_top - t_wood),
                color_group="lid",
                label="Lid Right Panel",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(ex, 0.0, 0.0),
            )

        # --- 3. Aluminum Location Profile Mating Extrusions ---
        if profile_h > 0.0 and not is_exploded_self_cut:
            # Rim along Base top edge
            add_solid_box(
                Point3D(0, 0, z_base_top - profile_h),
                Point3D(L, t_wood, z_base_top),
                color_group="profile",
                label="Base Top Profile (Front)",
                layer_order=ComponentLayer.BASE_ALU,
                offset=(0.0, -ex, 0.0),
            )
            add_solid_box(
                Point3D(0, W - t_wood, z_base_top - profile_h),
                Point3D(L, W, z_base_top),
                color_group="profile",
                label="Base Top Profile (Back)",
                layer_order=ComponentLayer.BASE_ALU,
                offset=(0.0, ex, 0.0),
            )
            add_solid_box(
                Point3D(0, t_wood, z_base_top - profile_h),
                Point3D(t_wood, W - t_wood, z_base_top),
                color_group="profile",
                label="Base Top Profile (Left)",
                layer_order=ComponentLayer.BASE_ALU,
                offset=(-ex, 0.0, 0.0),
            )
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_base_top - profile_h),
                Point3D(L, W - t_wood, z_base_top),
                color_group="profile",
                label="Base Top Profile (Right)",
                layer_order=ComponentLayer.BASE_ALU,
                offset=(ex, 0.0, 0.0),
            )

            # Rim along Lid bottom edge
            add_solid_box(
                Point3D(0, 0, z_lid_bot),
                Point3D(L, t_wood, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Front)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(0.0, -ex, 0.0),
            )
            add_solid_box(
                Point3D(0, W - t_wood, z_lid_bot),
                Point3D(L, W, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Back)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(0.0, ex, 0.0),
            )
            add_solid_box(
                Point3D(0, t_wood, z_lid_bot),
                Point3D(t_wood, W - t_wood, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Left)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(-ex, 0.0, 0.0),
            )
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_lid_bot),
                Point3D(L, W - t_wood, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Right)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
                offset=(ex, 0.0, 0.0),
            )

        # --- 4. Inside Partition Walls (Volumetric Panels with Thickness) ---
        inner_x0 = t_wood
        inner_x1 = L - t_wood
        inner_y0 = t_wood
        inner_y1 = W - t_wood
        inner_z0 = t_wood  # resting on top of base bottom floor panel

        if show_inside_walls:
            for i, wall in enumerate(case.walls, start=1):
                w_thick = wall.thickness_mm if wall.thickness_mm > 0 else t_wood
                w_height = wall.height_mm if (wall.height_mm is not None and wall.height_mm > 0) else case.inner_total_height
                z_wall_top = inner_z0 + min(w_height, case.inner_total_height)
                lbl = wall.label or f"Wall #{i}"

                if wall.orientation == WallOrientation.WIDTH_WISE:
                    x_center = inner_x0 + wall.position_mm
                    x_a = max(inner_x0, x_center - (w_thick / 2.0))
                    x_b = min(inner_x1, x_center + (w_thick / 2.0))

                    add_solid_box(
                        Point3D(x_a, inner_y0, inner_z0),
                        Point3D(x_b, inner_y1, z_wall_top),
                        color_group="wall",
                        label=lbl,
                        highlight_top_endgrain=True,
                        layer_order=ComponentLayer.INTERNAL_DIVIDERS,
                        wall_index=i-1,
                    )
                else:
                    y_center = inner_y0 + wall.position_mm
                    y_a = max(inner_y0, y_center - (w_thick / 2.0))
                    y_b = min(inner_y1, y_center + (w_thick / 2.0))

                    add_solid_box(
                        Point3D(inner_x0, y_a, inner_z0),
                        Point3D(inner_x1, y_b, z_wall_top),
                        color_group="wall",
                        label=lbl,
                        highlight_top_endgrain=True,
                        layer_order=ComponentLayer.INTERNAL_DIVIDERS,
                        wall_index=i-1,
                    )

        # --- 5. Dimensions Callouts ---
        cut_l = max(0.0, L - (2.0 * case.corner_extrusion_rebate))
        cut_w = max(0.0, W - (2.0 * case.corner_extrusion_rebate))
        cut_inset_w = max(0.0, cut_w - (2.0 * t_wood))
        h_base_wood = case.base_wood_height
        h_lid_wood = case.lid_wood_height

        if show_dimensions:
            # Dimension: Length (front edge along X)
            dimensions.append(DimensionCallout3D(
                start=Point3D(0, -ex, -ex if ex > 0 else 0),
                end=Point3D(L, -ex, -ex if ex > 0 else 0),
                label=f"L = {L:.0f} mm",
                value_mm=L,
                offset_vector=(0, -80, 0),
                dimension_type="length"
            ))

            # Dimension: Width (right edge along Y)
            dimensions.append(DimensionCallout3D(
                start=Point3D(L + ex, 0, -ex if ex > 0 else 0),
                end=Point3D(L + ex, W, -ex if ex > 0 else 0),
                label=f"W = {W:.0f} mm",
                value_mm=W,
                offset_vector=(80, 0, 0),
                dimension_type="width"
            ))

            # Dimension: Total Height (front-left corner along Z)
            dimensions.append(DimensionCallout3D(
                start=Point3D(-ex, -ex, -ex if ex > 0 else 0),
                end=Point3D(-ex, -ex, (H if gap == 0 else (H + gap)) + (ex if ex > 0 else 0)),
                label=f"H = {H:.0f} mm",
                value_mm=H,
                offset_vector=(-80, 0, 0),
                dimension_type="height"
            ))

            # Dimension: Base Height & Lid Height
            dimensions.append(DimensionCallout3D(
                start=Point3D(-ex, W + ex, -ex if ex > 0 else 0),
                end=Point3D(-ex, W + ex, H_base),
                label=f"Base = {H_base:.0f} mm",
                value_mm=H_base,
                offset_vector=(-60, 0, 0),
                dimension_type="base_height"
            ))

            dimensions.append(DimensionCallout3D(
                start=transform_lid_point(Point3D(-ex, W + ex, z_lid_bot)),
                end=transform_lid_point(Point3D(-ex, W + ex, z_lid_top + (ex if ex > 0 else 0))),
                label=f"Lid = {H_lid:.0f} mm",
                value_mm=H_lid,
                offset_vector=(-60, 0, 0),
                dimension_type="lid_height"
            ))

            # Individual Panel Dimensions (only when exploding)
            if ex > 0 and show_all_panel_dimensions:
                if is_exploded_self_cut:
                    # --- Exploded Self-Cut Lid Panels (Uncut 6-Wall Box) ---
                    # 1. Bottom Panel
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, 0, z_base_bot - ex),
                        end=Point3D(L, 0, z_base_bot - ex),
                        label=f"Bottom Panel: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -40, 0),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L, 0, z_base_bot - ex),
                        end=Point3D(L, W, z_base_bot - ex),
                        label=f"{cut_w:.0f} mm",
                        value_mm=cut_w,
                        offset_vector=(40, 0, 0),
                        dimension_type="panel_dim"
                    ))

                    # 2. Long Side (Front)
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, -ex, z_side_top),
                        end=Point3D(L, -ex, z_side_top),
                        label=f"Long Side (Front): {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -30, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, -ex, t_wood),
                        end=Point3D(0, -ex, z_side_top),
                        label=f"{h_total_wood:.0f} mm",
                        value_mm=h_total_wood,
                        offset_vector=(-30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 3. Long Side (Back)
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, W + ex, z_side_top),
                        end=Point3D(L, W + ex, z_side_top),
                        label=f"Long Side (Back): {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, 30, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L, W + ex, t_wood),
                        end=Point3D(L, W + ex, z_side_top),
                        label=f"{h_total_wood:.0f} mm",
                        value_mm=h_total_wood,
                        offset_vector=(30, 30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 4. Short Side (Left)
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(-ex, t_wood, t_wood),
                        end=Point3D(-ex, W - t_wood, t_wood),
                        label=f"Short Side (Left): {cut_inset_w:.0f} mm",
                        value_mm=cut_inset_w,
                        offset_vector=(-30, 0, -20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(-ex, t_wood, t_wood),
                        end=Point3D(-ex, t_wood, z_side_top),
                        label=f"{h_total_wood:.0f} mm",
                        value_mm=h_total_wood,
                        offset_vector=(-30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 5. Short Side (Right)
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L + ex, t_wood, t_wood),
                        end=Point3D(L + ex, W - t_wood, t_wood),
                        label=f"Short Side (Right): {cut_inset_w:.0f} mm",
                        value_mm=cut_inset_w,
                        offset_vector=(30, 0, -20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L + ex, t_wood, t_wood),
                        end=Point3D(L + ex, t_wood, z_side_top),
                        label=f"{h_total_wood:.0f} mm",
                        value_mm=h_total_wood,
                        offset_vector=(30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 6. Top Panel
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(0, 0, z_lid_top + ex)),
                        end=transform_lid_point(Point3D(L, 0, z_lid_top + ex)),
                        label=f"Top Panel: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -35, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(L, 0, z_lid_top + ex)),
                        end=transform_lid_point(Point3D(L, W, z_lid_top + ex)),
                        label=f"{cut_w:.0f} mm",
                        value_mm=cut_w,
                        offset_vector=(35, 0, 20),
                        dimension_type="panel_dim"
                    ))

                else:
                    # --- Standard Separate Base & Lid Panels ---
                    # 1. Base Bottom Panel
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, 0, z_base_bot - ex),
                        end=Point3D(L, 0, z_base_bot - ex),
                        label=f"Bottom Panel: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -40, 0),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L, 0, z_base_bot - ex),
                        end=Point3D(L, W, z_base_bot - ex),
                        label=f"{cut_w:.0f} mm",
                        value_mm=cut_w,
                        offset_vector=(40, 0, 0),
                        dimension_type="panel_dim"
                    ))

                    # 2. Base Front Panel
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, -ex, z_base_top - profile_h),
                        end=Point3D(L, -ex, z_base_top - profile_h),
                        label=f"Base Front: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -30, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, -ex, t_wood),
                        end=Point3D(0, -ex, z_base_top - profile_h),
                        label=f"{h_base_wood:.0f} mm",
                        value_mm=h_base_wood,
                        offset_vector=(-30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 3. Base Back Panel
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(0, W + ex, z_base_top - profile_h),
                        end=Point3D(L, W + ex, z_base_top - profile_h),
                        label=f"Base Back: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, 30, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L, W + ex, t_wood),
                        end=Point3D(L, W + ex, z_base_top - profile_h),
                        label=f"{h_base_wood:.0f} mm",
                        value_mm=h_base_wood,
                        offset_vector=(30, 30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 4. Base Left Panel
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(-ex, t_wood, t_wood),
                        end=Point3D(-ex, W - t_wood, t_wood),
                        label=f"Base Left: {cut_inset_w:.0f} mm",
                        value_mm=cut_inset_w,
                        offset_vector=(-30, 0, -20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(-ex, t_wood, t_wood),
                        end=Point3D(-ex, t_wood, z_base_top - profile_h),
                        label=f"{h_base_wood:.0f} mm",
                        value_mm=h_base_wood,
                        offset_vector=(-30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 5. Base Right Panel
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L + ex, t_wood, t_wood),
                        end=Point3D(L + ex, W - t_wood, t_wood),
                        label=f"Base Right: {cut_inset_w:.0f} mm",
                        value_mm=cut_inset_w,
                        offset_vector=(30, 0, -20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=Point3D(L + ex, t_wood, t_wood),
                        end=Point3D(L + ex, t_wood, z_base_top - profile_h),
                        label=f"{h_base_wood:.0f} mm",
                        value_mm=h_base_wood,
                        offset_vector=(30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 6. Lid Top Panel
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(0, 0, z_lid_top + ex)),
                        end=transform_lid_point(Point3D(L, 0, z_lid_top + ex)),
                        label=f"Lid Top: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -35, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(L, 0, z_lid_top + ex)),
                        end=transform_lid_point(Point3D(L, W, z_lid_top + ex)),
                        label=f"{cut_w:.0f} mm",
                        value_mm=cut_w,
                        offset_vector=(35, 0, 20),
                        dimension_type="panel_dim"
                    ))

                    # 7. Lid Front Panel
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(0, -ex, z_lid_top - t_wood)),
                        end=transform_lid_point(Point3D(L, -ex, z_lid_top - t_wood)),
                        label=f"Lid Front: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, -30, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(0, -ex, z_lid_bot + profile_h)),
                        end=transform_lid_point(Point3D(0, -ex, z_lid_top - t_wood)),
                        label=f"{h_lid_wood:.0f} mm",
                        value_mm=h_lid_wood,
                        offset_vector=(-30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 8. Lid Back Panel
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(0, W + ex, z_lid_top - t_wood)),
                        end=transform_lid_point(Point3D(L, W + ex, z_lid_top - t_wood)),
                        label=f"Lid Back: {cut_l:.0f} mm",
                        value_mm=cut_l,
                        offset_vector=(0, 30, 20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(L, W + ex, z_lid_bot + profile_h)),
                        end=transform_lid_point(Point3D(L, W + ex, z_lid_top - t_wood)),
                        label=f"{h_lid_wood:.0f} mm",
                        value_mm=h_lid_wood,
                        offset_vector=(30, 30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 9. Lid Left Panel
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(-ex, t_wood, z_lid_bot + profile_h)),
                        end=transform_lid_point(Point3D(-ex, W - t_wood, z_lid_bot + profile_h)),
                        label=f"Lid Left: {cut_inset_w:.0f} mm",
                        value_mm=cut_inset_w,
                        offset_vector=(-30, 0, -20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(-ex, t_wood, z_lid_bot + profile_h)),
                        end=transform_lid_point(Point3D(-ex, t_wood, z_lid_top - t_wood)),
                        label=f"{h_lid_wood:.0f} mm",
                        value_mm=h_lid_wood,
                        offset_vector=(-30, -30, 0),
                        dimension_type="panel_dim"
                    ))

                    # 10. Lid Right Panel
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(L + ex, t_wood, z_lid_bot + profile_h)),
                        end=transform_lid_point(Point3D(L + ex, W - t_wood, z_lid_bot + profile_h)),
                        label=f"Lid Right: {cut_inset_w:.0f} mm",
                        value_mm=cut_inset_w,
                        offset_vector=(30, 0, -20),
                        dimension_type="panel_dim"
                    ))
                    dimensions.append(DimensionCallout3D(
                        start=transform_lid_point(Point3D(L + ex, t_wood, z_lid_bot + profile_h)),
                        end=transform_lid_point(Point3D(L + ex, t_wood, z_lid_top - t_wood)),
                        label=f"{h_lid_wood:.0f} mm",
                        value_mm=h_lid_wood,
                        offset_vector=(30, -30, 0),
                        dimension_type="panel_dim"
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
                        offset_vector=(0, -40 - ex, 0),
                        dimension_type="wall_pos"
                    ))

        # Fixed base case bounding box so 3D viewport camera does not adapt on explode, lid angle, or split gap
        return WireframeMesh3D(
            faces=faces,
            segments=segments,
            dimensions=dimensions,
            bounding_box=(Point3D(0.0, 0.0, 0.0), Point3D(L, W, H))
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

    def is_face_facing_camera(self, normal: Tuple[float, float, float]) -> bool:
        """Determines if a 3D surface normal is facing towards the parallel projection camera."""
        nx, ny, nz = normal
        theta = math.radians(self.azimuth_deg)
        phi = math.radians(self.elevation_deg)

        cos_t, sin_t = math.cos(theta), math.sin(theta)
        cos_p, sin_p = math.cos(phi), math.sin(phi)

        n_rot_y = nx * sin_t + ny * cos_t
        n_cam_z = n_rot_y * cos_p - nz * sin_p
        # Faces pointing towards camera have negative camera Z normal component
        return n_cam_z < -1e-6

    def compute_face_shade(
        self,
        normal: Tuple[float, float, float],
        light_dir: Tuple[float, float, float] = (0.5, -0.6, 0.7)
    ) -> float:
        """Computes directional lighting intensity factor for a face normal."""
        nx, ny, nz = normal
        lx, ly, lz = light_dir
        l_len = math.sqrt(lx**2 + ly**2 + lz**2)
        if l_len > 0:
            lx, ly, lz = lx / l_len, ly / l_len, lz / l_len

        dot = nx * lx + ny * ly + nz * lz
        factor = 0.75 + 0.25 * max(0.0, dot)
        if nz > 0.8:
            factor = min(1.2, factor + 0.15)
        elif nz < -0.8:
            factor = max(0.55, factor - 0.15)
        return factor


class WoodPanelsSvgGenerator:
    """
    Generates a clean, vector-based SVG technical drawing of all wood panels
    and their exact dimensions, quantities, and material specs.
    """

    @staticmethod
    def generate_wood_panels_svg(
        case: FlightCase,
        cut_list: Optional[List[CutPiece]] = None,
        title: str = ""
    ) -> str:
        """
        Renders all wood panels as a high-contrast, scalable SVG technical drawing.
        Each panel is rendered to scale with dimension extension lines, witness ticks,
        dimension badges, quantity indicators, and material details.
        """
        import html

        clean_title = title.strip() if title else ""
        if clean_title:
            main_title_text = f"{html.escape(clean_title)} — Wood Panels Cut Diagram"
            svg_doc_title = f"{html.escape(clean_title)} — Wood Panels Cut Diagram"
        else:
            main_title_text = "FLIGHTCASE WOOD PANELS CUT DIAGRAM"
            svg_doc_title = "Flightcase Wood Panels Cut Diagram"

        if cut_list is None:
            raw_cuts = case.calculate_wood_cut_list()
        else:
            raw_cuts = cut_list

        # Filter wood pieces only
        wood_cuts = [
            p for p in raw_cuts
            if "WOOD" in p.category.name or "Wood" in p.category.value
        ]

        if not wood_cuts:
            # Fallback for empty cut list
            return (
                '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="800" height="400">'
                f'<title>{svg_doc_title}</title>'
                '<rect width="100%" height="100%" fill="#ffffff"/>'
                '<text x="400" y="200" text-anchor="middle" fill="#64748b" font-size="18" '
                'font-family="system-ui, -apple-system, sans-serif">No wood panels to display.</text>'
                '</svg>'
            )

        card_w = 480
        card_h = 280
        spacing = 24
        cols = 2
        margin_x = 32
        margin_top = 110
        margin_bot = 32

        num_cards = len(wood_cuts)
        num_rows = math.ceil(num_cards / cols)

        svg_w = margin_x * 2 + cols * card_w + (cols - 1) * spacing
        svg_h = margin_top + num_rows * card_h + max(0, num_rows - 1) * spacing + margin_bot

        total_pieces = sum(p.quantity for p in wood_cuts)
        total_area = sum(p.total_area_m2 for p in wood_cuts)

        lines: List[str] = [
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}">',
            f'  <title>{svg_doc_title}</title>',
            '  <defs>',
            '    <pattern id="gridPattern" width="20" height="20" patternUnits="userSpaceOnUse">',
            '      <path d="M 20 0 L 0 0 0 20" fill="none" stroke="#f1f5f9" stroke-width="0.7"/>',
            '    </pattern>',
            '    <marker id="arrowHead" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto">',
            '      <polygon points="0 1, 6 3, 0 5" fill="#d97706"/>',
            '    </marker>',
            '    <marker id="arrowHeadStart" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto-start-reverse">',
            '      <polygon points="0 1, 6 3, 0 5" fill="#d97706"/>',
            '    </marker>',
            '  </defs>',
            f'  <rect width="100%" height="100%" fill="#ffffff"/>',
            f'  <rect width="100%" height="100%" fill="url(#gridPattern)"/>',
            '',
            '  <!-- Header Banner -->',
            f'  <g id="headerBanner" transform="translate({margin_x}, 20)">',
            f'    <rect width="{svg_w - 2 * margin_x}" height="70" rx="8" fill="#f8fafc" stroke="#cbd5e1" stroke-width="1.5"/>',
            f'    <text x="24" y="30" fill="#0f172a" font-size="18" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">{main_title_text}</text>',
            f'    <text x="24" y="52" fill="#475569" font-size="13" font-family="system-ui, -apple-system, sans-serif">Outer: {case.outer_length:.0f}×{case.outer_width:.0f}×{case.total_height:.0f} mm  |  Thickness: {case.wood_thickness:.1f} mm  |  Total Panels: {total_pieces} pcs  |  Total Area: {total_area:.2f} m²</text>',
            '  </g>',
            '',
        ]

        # Render panel cards
        for idx, piece in enumerate(wood_cuts):
            row = idx // cols
            col = idx % cols

            cx = margin_x + col * (card_w + spacing)
            cy = margin_top + row * (card_h + spacing)

            name_esc = html.escape(piece.name)
            notes_esc = html.escape(piece.notes or "")
            cat_esc = html.escape(piece.category.value)

            # Available panel drawing box inside the card
            # Card has header (top 45px) and footer (bottom 35px)
            draw_max_w = 340.0
            draw_max_h = 130.0

            w_mm = max(1.0, piece.length_mm)
            h_mm = max(1.0, piece.width_mm)

            scale = min(draw_max_w / w_mm, draw_max_h / h_mm)
            pw = max(30.0, w_mm * scale)
            ph = max(20.0, h_mm * scale)

            px = cx + 50.0 + (draw_max_w - pw) / 2.0
            py = cy + 65.0 + (draw_max_h - ph) / 2.0

            lines.append(f'  <!-- Panel Card {idx+1}: {name_esc} -->')
            lines.append(f'  <g id="panelCard_{idx+1}">')
            lines.append(f'    <rect x="{cx}" y="{cy}" width="{card_w}" height="{card_h}" rx="8" fill="#ffffff" stroke="#cbd5e1" stroke-width="1.5"/>')
            
            # Card Header: Panel Name
            lines.append(f'    <text x="{cx + 18}" y="{cy + 28}" fill="#0f172a" font-size="14" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">{name_esc}</text>')
            
            # Quantity Badge
            badge_x = cx + card_w - 85
            lines.append(f'    <rect x="{badge_x}" y="{cy + 12}" width="70" height="22" rx="4" fill="#ecfdf5" stroke="#10b981" stroke-width="1"/>')
            lines.append(f'    <text x="{badge_x + 35}" y="{cy + 27}" text-anchor="middle" fill="#047857" font-size="11" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">QTY: {piece.quantity}</text>')

            # Scaled 2D Wood Panel Rectangle
            lines.append(f'    <rect x="{px:.1f}" y="{py:.1f}" width="{pw:.1f}" height="{ph:.1f}" rx="3" fill="#eff6ff" fill-opacity="0.85" stroke="#2563eb" stroke-width="1.6"/>')

            # Top Dimension Line (Length)
            # Extension witness lines
            dim_y = py - 12.0
            lines.append(f'    <line x1="{px:.1f}" y1="{py - 2:.1f}" x2="{px:.1f}" y2="{py - 18:.1f}" stroke="#94a3b8" stroke-width="0.8"/>')
            lines.append(f'    <line x1="{px + pw:.1f}" y1="{py - 2:.1f}" x2="{px + pw:.1f}" y2="{py - 18:.1f}" stroke="#94a3b8" stroke-width="0.8"/>')
            lines.append(f'    <line x1="{px + 3:.1f}" y1="{dim_y:.1f}" x2="{px + pw - 3:.1f}" y2="{dim_y:.1f}" stroke="#d97706" stroke-width="1.2" marker-start="url(#arrowHeadStart)" marker-end="url(#arrowHead)"/>')
            lines.append(f'    <text x="{px + pw / 2.0:.1f}" y="{dim_y - 4.0:.1f}" text-anchor="middle" fill="#b45309" font-size="11" font-weight="600" font-family="system-ui, -apple-system, sans-serif">{piece.length_mm:.1f} mm</text>')

            # Right Dimension Line (Width / Height)
            # Extension witness lines
            dim_x = px + pw + 12.0
            lines.append(f'    <line x1="{px + pw + 2:.1f}" y1="{py:.1f}" x2="{px + pw + 18:.1f}" y2="{py:.1f}" stroke="#94a3b8" stroke-width="0.8"/>')
            lines.append(f'    <line x1="{px + pw + 2:.1f}" y1="{py + ph:.1f}" x2="{px + pw + 18:.1f}" y2="{py + ph:.1f}" stroke="#94a3b8" stroke-width="0.8"/>')
            lines.append(f'    <line x1="{dim_x:.1f}" y1="{py + 3:.1f}" x2="{dim_x:.1f}" y2="{py + ph - 3:.1f}" stroke="#d97706" stroke-width="1.2" marker-start="url(#arrowHeadStart)" marker-end="url(#arrowHead)"/>')
            lines.append(f'    <text x="{dim_x + 6.0:.1f}" y="{py + ph / 2.0 + 4.0:.1f}" fill="#b45309" font-size="11" font-weight="600" font-family="system-ui, -apple-system, sans-serif">{piece.width_mm:.1f} mm</text>')

            # Center text on panel
            lines.append(f'    <text x="{px + pw / 2.0:.1f}" y="{py + ph / 2.0 - 2.0:.1f}" text-anchor="middle" fill="#0f172a" font-size="12" font-weight="bold" font-family="system-ui, -apple-system, sans-serif">{piece.length_mm:.1f} × {piece.width_mm:.1f} mm</text>')
            lines.append(f'    <text x="{px + pw / 2.0:.1f}" y="{py + ph / 2.0 + 14.0:.1f}" text-anchor="middle" fill="#2563eb" font-size="10" font-family="system-ui, -apple-system, sans-serif">Thick: {piece.thickness_mm:.1f} mm</text>')

            # Card Footer: Area & Notes
            footer_text = f"Area: {piece.total_area_m2:.3f} m²"
            if notes_esc:
                footer_text += f"  •  {notes_esc}"
            lines.append(f'    <text x="{cx + 18}" y="{cy + card_h - 16}" fill="#64748b" font-size="11" font-family="system-ui, -apple-system, sans-serif">{footer_text}</text>')
            lines.append('  </g>')
            lines.append('')

        lines.append('</svg>')
        return "\n".join(lines)
