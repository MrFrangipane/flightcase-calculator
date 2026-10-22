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
        lid_rotation_angle_deg: float = 0.0,
        lid_hinge_side: str = "Back",
        show_inside_walls: bool = True,
        show_dimensions: bool = True
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
        ) -> None:
            x0, y0, z0 = p_min.x, p_min.y, p_min.z
            x1, y1, z1 = p_max.x, p_max.y, p_max.z

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

        # --- 1. Base Box Volumetric Panels with Panel Thickness ---
        # Base Bottom Floor Panel: spans [0, L] x [0, W] x [0, t_wood]
        add_solid_box(
            Point3D(0, 0, z_base_bot),
            Point3D(L, W, z_base_bot + t_wood),
            color_group="base",
            label="Base Bottom Panel",
            layer_order=ComponentLayer.BASE_FLOOR,
        )

        # Base Long Sides (Front & Back Panels):
        # Front panel: [0, L] x [0, t_wood] x [t_wood, z_base_top - profile_h]
        add_solid_box(
            Point3D(0, 0, z_base_bot + t_wood),
            Point3D(L, t_wood, z_base_top - profile_h),
            color_group="base",
            label="Base Front Panel",
            highlight_top_endgrain=(profile_h == 0.0),
            layer_order=ComponentLayer.OUTER_BASE_WALLS,
        )
        # Back panel: [0, L] x [W - t_wood, W] x [t_wood, z_base_top - profile_h]
        add_solid_box(
            Point3D(0, W - t_wood, z_base_bot + t_wood),
            Point3D(L, W, z_base_top - profile_h),
            color_group="base",
            label="Base Back Panel",
            highlight_top_endgrain=(profile_h == 0.0),
            layer_order=ComponentLayer.OUTER_BASE_WALLS,
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
        )
        # Right panel: [L - t_wood, L] x [t_wood, W - t_wood] x [t_wood, z_base_top - profile_h]
        add_solid_box(
            Point3D(L - t_wood, t_wood, z_base_bot + t_wood),
            Point3D(L, W - t_wood, z_base_top - profile_h),
            color_group="base",
            label="Base Right Panel",
            highlight_top_endgrain=(profile_h == 0.0),
            layer_order=ComponentLayer.OUTER_BASE_WALLS,
        )

        # --- 2. Lid Box Volumetric Panels with Panel Thickness ---
        # Lid Top Roof Panel: spans [0, L] x [0, W] x [z_lid_top - t_wood, z_lid_top]
        add_solid_box(
            Point3D(0, 0, z_lid_top - t_wood),
            Point3D(L, W, z_lid_top),
            color_group="lid",
            label="Lid Top Panel",
            layer_order=ComponentLayer.LID_ROOF,
            is_lid=True,
        )

        # Lid Long Sides (Front & Back Panels):
        # Front panel: [0, L] x [0, t_wood] x [z_lid_bot + profile_h, z_lid_top - t_wood]
        add_solid_box(
            Point3D(0, 0, z_lid_bot + profile_h),
            Point3D(L, t_wood, z_lid_top - t_wood),
            color_group="lid",
            label="Lid Front Panel",
            layer_order=ComponentLayer.LID_WALLS,
            is_lid=True,
        )
        # Back panel: [0, L] x [W - t_wood, W] x [z_lid_bot + profile_h, z_lid_top - t_wood]
        add_solid_box(
            Point3D(0, W - t_wood, z_lid_bot + profile_h),
            Point3D(L, W, z_lid_top - t_wood),
            color_group="lid",
            label="Lid Back Panel",
            layer_order=ComponentLayer.LID_WALLS,
            is_lid=True,
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
        )
        # Right panel: [L - t_wood, L] x [t_wood, W - t_wood] x [z_lid_bot + profile_h, z_lid_top - t_wood]
        add_solid_box(
            Point3D(L - t_wood, t_wood, z_lid_bot + profile_h),
            Point3D(L, W - t_wood, z_lid_top - t_wood),
            color_group="lid",
            label="Lid Right Panel",
            layer_order=ComponentLayer.LID_WALLS,
            is_lid=True,
        )

        # --- 3. Aluminum Location Profile Mating Extrusions ---
        if profile_h > 0.0:
            # Rim along Base top edge
            add_solid_box(
                Point3D(0, 0, z_base_top - profile_h),
                Point3D(L, t_wood, z_base_top),
                color_group="profile",
                label="Base Top Profile (Front)",
                layer_order=ComponentLayer.BASE_ALU,
            )
            add_solid_box(
                Point3D(0, W - t_wood, z_base_top - profile_h),
                Point3D(L, W, z_base_top),
                color_group="profile",
                label="Base Top Profile (Back)",
                layer_order=ComponentLayer.BASE_ALU,
            )
            add_solid_box(
                Point3D(0, t_wood, z_base_top - profile_h),
                Point3D(t_wood, W - t_wood, z_base_top),
                color_group="profile",
                label="Base Top Profile (Left)",
                layer_order=ComponentLayer.BASE_ALU,
            )
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_base_top - profile_h),
                Point3D(L, W - t_wood, z_base_top),
                color_group="profile",
                label="Base Top Profile (Right)",
                layer_order=ComponentLayer.BASE_ALU,
            )

            # Rim along Lid bottom edge
            add_solid_box(
                Point3D(0, 0, z_lid_bot),
                Point3D(L, t_wood, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Front)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
            )
            add_solid_box(
                Point3D(0, W - t_wood, z_lid_bot),
                Point3D(L, W, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Back)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
            )
            add_solid_box(
                Point3D(0, t_wood, z_lid_bot),
                Point3D(t_wood, W - t_wood, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Left)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
            )
            add_solid_box(
                Point3D(L - t_wood, t_wood, z_lid_bot),
                Point3D(L, W - t_wood, z_lid_bot + profile_h),
                color_group="profile",
                label="Lid Bottom Profile (Right)",
                layer_order=ComponentLayer.LID_WALLS,
                is_lid=True,
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

            # Dimension: Base Height & Lid Height
            dimensions.append(DimensionCallout3D(
                start=Point3D(0, W, 0),
                end=Point3D(0, W, H_base),
                label=f"Base = {H_base:.0f} mm",
                value_mm=H_base,
                offset_vector=(-60, 0, 0),
                dimension_type="base_height"
            ))

            dimensions.append(DimensionCallout3D(
                start=transform_lid_point(Point3D(0, W, z_lid_bot)),
                end=transform_lid_point(Point3D(0, W, z_lid_top)),
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

        all_points = []
        for f in faces:
            all_points.extend(f.vertices)
        for s in segments:
            all_points.append(s.p1)
            all_points.append(s.p2)

        if all_points:
            min_x = min(min(p.x for p in all_points), 0.0)
            min_y = min(min(p.y for p in all_points), 0.0)
            min_z = min(min(p.z for p in all_points), 0.0)
            max_x = max(max(p.x for p in all_points), L)
            max_y = max(max(p.y for p in all_points), W)
            max_z = max(max(p.z for p in all_points), H)
        else:
            min_x, min_y, min_z = 0.0, 0.0, 0.0
            max_x, max_y, max_z = L, W, H + gap

        return WireframeMesh3D(
            faces=faces,
            segments=segments,
            dimensions=dimensions,
            bounding_box=(Point3D(min_x, min_y, min_z), Point3D(max_x, max_y, max_z))
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
