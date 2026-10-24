"""Unit tests for Flightcase Domain layer (Entities, Value Objects, Domain Services)."""

import pytest
from flightcase.domain import (
    Dimensions3D,
    FlightCase,
    InsideWall,
    WallOrientation,
    CutPieceCategory,
    FlightCaseDomainService,
    Schema3DGeometryBuilder,
    ComponentLayer,
    InvalidDimensionError,
    InvalidLidConfigurationError,
    WallOutOfBoundsError,
)


def test_dimensions_3d_validation():
    dims = Dimensions3D(800.0, 500.0, 400.0)
    assert dims.length_mm == 800.0
    assert dims.width_mm == 500.0
    assert dims.height_mm == 400.0
    assert pytest.approx(dims.volume_m3) == 0.16

    with pytest.raises(InvalidDimensionError):
        Dimensions3D(-100.0, 500.0, 400.0)

    with pytest.raises(InvalidDimensionError):
        Dimensions3D(800.0, 0.0, 400.0)


def test_flightcase_invariants_and_properties():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )

    assert case.inner_length == 800.0
    assert case.inner_width == 500.0
    assert case.inner_total_height == 400.0
    assert case.inner_lid_height == 100.0
    assert case.inner_base_height == 300.0
    assert case.outer_length == 818.0
    assert case.outer_width == 518.0
    assert case.total_height == 418.0
    assert case.outer_lid_height == 109.0
    assert case.base_height == 309.0
    assert case.total_wood_height == 390.0
    assert case.lid_wood_height == 95.0
    assert case.base_wood_height == 295.0


def test_flightcase_invalid_lid_height():
    with pytest.raises(InvalidLidConfigurationError):
        # Lid height >= total height
        FlightCase(
            dimensions=Dimensions3D(800.0, 500.0, 400.0),
            lid_height=400.0,
            wood_thickness=9.0,
        )

    with pytest.raises(InvalidLidConfigurationError):
        # Lid height too small for profile offset (e.g. lid 4mm + wood 0.5mm = 4.5mm <= half offset 5mm)
        FlightCase(
            dimensions=Dimensions3D(800.0, 500.0, 400.0),
            lid_height=4.0,
            wood_thickness=0.5,
            lid_alu_profile_offset=10.0,
        )


def test_wood_panels_cut_list_calculation():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )

    cuts = case.calculate_wood_cut_list()
    assert len(cuts) == 5

    top_bottom = next(p for p in cuts if p.name == "Top & Bottom Panels")
    assert top_bottom.length_mm == 818.0
    assert top_bottom.width_mm == 518.0
    assert top_bottom.thickness_mm == 9.0
    assert top_bottom.quantity == 2
    assert top_bottom.category == CutPieceCategory.WOOD_BASE

    base_long = next(p for p in cuts if "Base Long Sides" in p.name)
    assert base_long.length_mm == 818.0
    assert base_long.width_mm == 295.0
    assert base_long.quantity == 2

    base_short = next(p for p in cuts if "Base Short Sides" in p.name)
    assert base_short.length_mm == 500.0
    assert base_short.width_mm == 295.0
    assert base_short.quantity == 2


def test_lid_alu_profile_required_length():
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 500.0),
        lid_height=120.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=12.0,
    )

    single_perimeter = 2.0 * (1018.0 + 618.0)  # 3272 mm
    assert case.total_lid_alu_profile_length_mm == 6544.0  # Male + Female = 2 perimeters

    profiles = case.calculate_alu_profiles()
    mating_profiles = [p for p in profiles if p.category == CutPieceCategory.ALU_LID_MATING]
    assert len(mating_profiles) == 4
    total_mating_len = sum(p.length_mm * p.quantity for p in mating_profiles)
    assert total_mating_len == 6544.0


def test_inside_walls_addition_and_validation():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
    )

    # Valid width-wise wall (inner_length is 800)
    wall1 = InsideWall(
        orientation=WallOrientation.WIDTH_WISE,
        position_mm=250.0,
        thickness_mm=9.0,
        label="Compartment Wall 1"
    )
    case.add_wall(wall1)
    assert len(case.walls) == 1

    # Out of bounds wall (position >= 800)
    with pytest.raises(WallOutOfBoundsError):
        case.add_wall(InsideWall(
            orientation=WallOrientation.WIDTH_WISE,
            position_mm=850.0
        ))

    # Out of bounds wall for width (inner_width is 500)
    with pytest.raises(WallOutOfBoundsError):
        case.add_wall(InsideWall(
            orientation=WallOrientation.LENGTH_WISE,
            position_mm=550.0
        ))


def test_inside_wall_full_height_to_lid_roof():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )
    # Default full height wall (height_mm is None)
    case.add_wall(InsideWall(
        orientation=WallOrientation.WIDTH_WISE,
        position_mm=250.0,
        thickness_mm=9.0,
        label="Full Height Wall",
    ))
    # Custom partial height wall
    case.add_wall(InsideWall(
        orientation=WallOrientation.LENGTH_WISE,
        position_mm=150.0,
        thickness_mm=9.0,
        height_mm=120.0,
        label="Tray Divider",
    ))

    cuts = case.calculate_wood_cut_list()
    full_wall_cut = next(p for p in cuts if "Full Height Wall" in p.name)
    assert full_wall_cut.length_mm == 500.0  # inner width
    assert full_wall_cut.width_mm == 400.0  # inner total height

    tray_cut = next(p for p in cuts if "Tray Divider" in p.name)
    assert tray_cut.length_mm == 800.0  # inner length
    assert tray_cut.width_mm == 120.0

    comps = case.calculate_compartments()
    for c in comps:
        assert c.height_mm == 400.0


def test_equispaced_walls_and_compartments():
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 400.0),
        lid_height=100.0,
        wood_thickness=10.0,
    )

    # inner_length = 1000, 2 walls (10mm thick each): total wall thickness = 20mm -> usable clearance = 980mm -> 326.67mm each
    case.set_equispaced_walls(count=2, orientation=WallOrientation.WIDTH_WISE)
    assert len(case.walls) == 2
    assert pytest.approx(case.walls[0].position_mm, rel=1e-3) == 331.67
    assert pytest.approx(case.walls[1].position_mm, rel=1e-3) == 668.33

    comps = case.calculate_compartments()
    assert len(comps) == 3
    assert pytest.approx(comps[0].length_mm, rel=1e-3) == 326.67
    assert pytest.approx(comps[1].length_mm, rel=1e-3) == 326.67
    assert pytest.approx(comps[2].length_mm, rel=1e-3) == 326.67
    assert pytest.approx(comps[0].width_mm) == 600.0


def test_custom_compartment_spaces_configuration():
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 400.0),
        lid_height=100.0,
        wood_thickness=10.0,
    )
    # Inner length = 1000mm, inner width = 600mm
    # We want 3 compartments along length with clearances: 250mm, 350mm, 380mm (sum = 980mm + 2*10mm walls = 1000mm)
    case.set_walls_from_compartment_spaces(
        clearances_mm=[250.0, 350.0, 380.0],
        orientation=WallOrientation.WIDTH_WISE,
        thicknesses_mm=[10.0, 10.0],
    )
    assert len(case.walls) == 2
    # Wall 1: center = 250 + 5 = 255mm
    # Wall 2: center = 250 + 10 + 350 + 5 = 615mm
    assert pytest.approx(case.walls[0].position_mm) == 255.0
    assert pytest.approx(case.walls[1].position_mm) == 615.0

    clearances = case.get_compartment_clearances(WallOrientation.WIDTH_WISE)
    assert len(clearances) == 3
    assert pytest.approx(clearances[0]) == 250.0
    assert pytest.approx(clearances[1]) == 350.0
    assert pytest.approx(clearances[2]) == 380.0

    comps = case.calculate_compartments()
    assert len(comps) == 3
    assert pytest.approx(comps[0].length_mm) == 250.0
    assert pytest.approx(comps[1].length_mm) == 350.0
    assert pytest.approx(comps[2].length_mm) == 380.0


def test_domain_calculation_report():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
    )

    report = FlightCaseDomainService.calculate(case)
    assert report.total_wood_area_m2 > 0.0
    assert report.total_wood_weight_kg > 0.0
    assert report.total_lid_mating_profile_length_mm == 5344.0
    assert report.standard_sheets_required > 0.0


def test_schema_3d_geometry_generation():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
    )
    case.add_wall(InsideWall(orientation=WallOrientation.WIDTH_WISE, position_mm=300.0, thickness_mm=12.0))

    mesh = Schema3DGeometryBuilder.build_geometry(case, lid_exploded_gap_mm=50.0)
    assert len(mesh.faces) > 0
    assert len(mesh.segments) > 0
    assert len(mesh.dimensions) > 0

    # Verify panel faces with thickness exist (base, lid, endgrain, profile, wall)
    color_groups = {f.color_group for f in mesh.faces}
    assert "base" in color_groups
    assert "lid" in color_groups
    assert "profile" in color_groups
    assert "wall" in color_groups
    assert "endgrain" in color_groups

    # Verify end-grain thickness faces
    endgrain_faces = [f for f in mesh.faces if f.is_endgrain]
    assert len(endgrain_faces) > 0

    # Verify structural hierarchy layer orders
    assert ComponentLayer.BASE_FLOOR < ComponentLayer.INTERNAL_DIVIDERS < ComponentLayer.OUTER_BASE_WALLS < ComponentLayer.BASE_ALU < ComponentLayer.LID_WALLS < ComponentLayer.LID_ROOF
    base_floor_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.BASE_FLOOR]
    divider_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.INTERNAL_DIVIDERS]
    base_wall_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.OUTER_BASE_WALLS]
    base_alu_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.BASE_ALU]
    lid_wall_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.LID_WALLS]
    lid_roof_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.LID_ROOF]

    assert len(base_floor_faces) == 6
    assert len(divider_faces) == 6
    assert len(base_wall_faces) == 24  # 4 base walls * 6 faces
    assert len(base_alu_faces) == 24   # 4 base profiles * 6 faces
    assert len(lid_wall_faces) == 48   # 4 lid walls * 6 faces + 4 lid profiles * 6 faces
    assert len(lid_roof_faces) == 6    # 1 roof panel * 6 faces

    # Verify length and width callouts exist (outer nominal dimensions)
    dim_labels = [d.label for d in mesh.dimensions]
    assert any("L = 818" in lbl for lbl in dim_labels)
    assert any("W = 518" in lbl for lbl in dim_labels)
    assert any("H = 418" in lbl for lbl in dim_labels)


def test_parallel_projector_face_visibility_and_shading():
    from flightcase.domain import ParallelProjector

    projector = ParallelProjector(azimuth_deg=45.0, elevation_deg=30.0)

    # Top face normal (0, 0, 1) is visible from above (elevation=30°)
    assert projector.is_face_facing_camera((0.0, 0.0, 1.0)) is True

    # Bottom face normal (0, 0, -1) is culled when looking from above
    assert projector.is_face_facing_camera((0.0, 0.0, -1.0)) is False

    # Shading produces valid brightness factor
    shade_top = projector.compute_face_shade((0.0, 0.0, 1.0))
    shade_bottom = projector.compute_face_shade((0.0, 0.0, -1.0))
    assert shade_top > shade_bottom


def test_self_cut_lid_domain_and_geometry():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        self_cut_lid=True,
    )

    # 1. Wood cut list has 3 entries representing 6 outer walls (Top & Bottom qty 2, Long qty 2, Short qty 2)
    cuts = case.calculate_wood_cut_list()
    assert len(cuts) == 3
    assert sum(c.quantity for c in cuts) == 6

    top_bottom = next(c for c in cuts if c.name == "Top & Bottom Panels")
    assert top_bottom.length_mm == 818.0
    assert top_bottom.width_mm == 518.0
    assert top_bottom.quantity == 2

    long_s = next(c for c in cuts if c.name == "Long Sides (Front & Back)")
    assert long_s.length_mm == 818.0
    assert long_s.width_mm == 390.0
    assert long_s.quantity == 2

    short_s = next(c for c in cuts if c.name == "Short Sides (Left & Right)")
    assert short_s.length_mm == 500.0
    assert short_s.width_mm == 390.0
    assert short_s.quantity == 2

    # 2. 3D Schema Geometry is kept with the lid, base, and aluminum mating profiles
    mesh = Schema3DGeometryBuilder.build_geometry(case, lid_exploded_gap_mm=20.0)
    color_groups = {f.color_group for f in mesh.faces}
    assert "base" in color_groups
    assert "lid" in color_groups
    assert "profile" in color_groups
    # Ensure lid roof and base floor faces exist
    assert any(f.layer_order == ComponentLayer.LID_ROOF for f in mesh.faces)
    assert any(f.layer_order == ComponentLayer.BASE_FLOOR for f in mesh.faces)
    assert any(f.layer_order == ComponentLayer.LID_WALLS for f in mesh.faces)
    assert any(f.layer_order == ComponentLayer.OUTER_BASE_WALLS for f in mesh.faces)


def test_schema_3d_lid_alu_profile_offset_dimensions():
    # Case with 20mm total profile offset (10mm base profile, 10mm lid profile)
    case = FlightCase(
        dimensions=Dimensions3D(970.0, 570.0, 270.0),
        lid_height=70.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=20.0,
    )
    H_base = case.base_height  # 209.0
    half_offset = 10.0
    gap = 40.0

    mesh = Schema3DGeometryBuilder.build_geometry(case, lid_exploded_gap_mm=gap)

    # 1. Base profile faces span z in [H_base - half_offset, H_base] = [199.0, 209.0]
    base_alu_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.BASE_ALU]
    assert len(base_alu_faces) == 24
    base_alu_z_coords = [v.z for f in base_alu_faces for v in f.vertices]
    assert min(base_alu_z_coords) == pytest.approx(199.0)
    assert max(base_alu_z_coords) == pytest.approx(209.0)

    # 2. Base wood walls span z in [wood_thickness, H_base - half_offset] = [9.0, 199.0]
    base_wood_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.OUTER_BASE_WALLS]
    base_wood_z_coords = [v.z for f in base_wood_faces for v in f.vertices]
    assert min(base_wood_z_coords) == pytest.approx(9.0)
    assert max(base_wood_z_coords) == pytest.approx(199.0)

    # 3. Lid profile faces span z in [H_base + gap, H_base + gap + half_offset] = [249.0, 259.0]
    lid_alu_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.LID_WALLS and f.color_group == "profile"]
    assert len(lid_alu_faces) == 24
    lid_alu_z_coords = [v.z for f in lid_alu_faces for v in f.vertices]
    assert min(lid_alu_z_coords) == pytest.approx(249.0)
    assert max(lid_alu_z_coords) == pytest.approx(259.0)

    # 4. Lid wood walls span z in [259.0, (209 + 40 + 79) - 9 = 319.0]
    lid_wood_faces = [f for f in mesh.faces if f.layer_order == ComponentLayer.LID_WALLS and f.color_group == "lid"]
    assert len(lid_wood_faces) == 24
    lid_wood_z_coords = [v.z for f in lid_wood_faces for v in f.vertices]
    assert min(lid_wood_z_coords) == pytest.approx(259.0)
    assert max(lid_wood_z_coords) == pytest.approx(319.0)

    # 5. Case with 0mm profile offset has no profile faces and wood walls extend completely
    case_no_profile = FlightCase(
        dimensions=Dimensions3D(970.0, 570.0, 270.0),
        lid_height=70.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=0.0,
    )
    mesh_no_profile = Schema3DGeometryBuilder.build_geometry(case_no_profile, lid_exploded_gap_mm=gap)
    assert not any(f.layer_order == ComponentLayer.BASE_ALU for f in mesh_no_profile.faces)
    assert not any(f.color_group == "profile" for f in mesh_no_profile.faces)


def test_schema_3d_lid_rotation_all_sides():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=10.0,
        lid_alu_profile_offset=0.0,
    )
    L, W, H = case.outer_length, case.outer_width, case.total_height
    H_base = case.base_height
    H_lid = case.outer_lid_height

    # 1. Closed lid (0 deg)
    mesh_closed = Schema3DGeometryBuilder.build_geometry(case, lid_rotation_angle_deg=0.0)
    lid_roof_closed = [f for f in mesh_closed.faces if f.layer_order == ComponentLayer.LID_ROOF]
    z_roof_closed = [v.z for f in lid_roof_closed for v in f.vertices]
    assert max(z_roof_closed) == pytest.approx(H)

    # 2. Back hinge side (90 deg)
    mesh_back_90 = Schema3DGeometryBuilder.build_geometry(
        case, lid_rotation_angle_deg=90.0, lid_hinge_side="Back"
    )
    lid_roof_back = [f for f in mesh_back_90.faces if f.layer_order == ComponentLayer.LID_ROOF]
    y_roof_back = [v.y for f in lid_roof_back for v in f.vertices]
    z_roof_back = [v.z for f in lid_roof_back for v in f.vertices]
    # Roof swings back: Y exceeds W (520)
    assert max(y_roof_back) > W
    assert min(z_roof_back) == pytest.approx(H_base)

    # 3. Back hinge side (180 deg - fully open flat)
    mesh_back_180 = Schema3DGeometryBuilder.build_geometry(
        case, lid_rotation_angle_deg=180.0, lid_hinge_side="Back"
    )
    lid_roof_180 = [f for f in mesh_back_180.faces if f.layer_order == ComponentLayer.LID_ROOF]
    z_roof_180 = [v.z for f in lid_roof_180 for v in f.vertices]
    assert max(z_roof_180) == pytest.approx(H_base - (H_lid - case.wood_thickness))

    # 4. Front hinge side (90 deg)
    mesh_front_90 = Schema3DGeometryBuilder.build_geometry(
        case, lid_rotation_angle_deg=90.0, lid_hinge_side="Front"
    )
    lid_roof_front = [f for f in mesh_front_90.faces if f.layer_order == ComponentLayer.LID_ROOF]
    y_roof_front = [v.y for f in lid_roof_front for v in f.vertices]
    assert min(y_roof_front) < 0.0

    # 5. Left hinge side (90 deg)
    mesh_left_90 = Schema3DGeometryBuilder.build_geometry(
        case, lid_rotation_angle_deg=90.0, lid_hinge_side="Left"
    )
    lid_roof_left = [f for f in mesh_left_90.faces if f.layer_order == ComponentLayer.LID_ROOF]
    x_roof_left = [v.x for f in lid_roof_left for v in f.vertices]
    assert min(x_roof_left) < 0.0

    # 6. Right hinge side (90 deg)
    mesh_right_90 = Schema3DGeometryBuilder.build_geometry(
        case, lid_rotation_angle_deg=90.0, lid_hinge_side="Right"
    )
    lid_roof_right = [f for f in mesh_right_90.faces if f.layer_order == ComponentLayer.LID_ROOF]
    x_roof_right = [v.x for f in lid_roof_right for v in f.vertices]
    assert max(x_roof_right) > L


def test_schema_3d_explode_view_geometry_and_panel_dimensions():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )
    L, W, H = case.outer_length, case.outer_width, case.total_height

    # 1. Without explode view (explode_gap_mm = 0)
    mesh_normal = Schema3DGeometryBuilder.build_geometry(case, explode_gap_mm=0.0)
    normal_panel_dims = [d for d in mesh_normal.dimensions if d.dimension_type == "panel_dim"]
    # Individual panel dimensions are hidden when unexploded to avoid clutter
    assert len(normal_panel_dims) == 0
    # Outer dimensions exist
    dim_types = [d.dimension_type for d in mesh_normal.dimensions]
    assert "length" in dim_types
    assert "width" in dim_types
    assert "height" in dim_types

    # 2. With explode view (explode_gap_mm = 60.0)
    explode_dist = 60.0
    mesh_exploded = Schema3DGeometryBuilder.build_geometry(
        case,
        explode_gap_mm=explode_dist,
        show_dimensions=True,
        show_all_panel_dimensions=True,
    )

    # Panel dimensions must be present
    exploded_panel_dims = [d for d in mesh_exploded.dimensions if d.dimension_type == "panel_dim"]
    assert len(exploded_panel_dims) >= 10

    labels = [d.label for d in exploded_panel_dims]
    assert any("Bottom Panel" in l for l in labels)
    assert any("Base Front" in l for l in labels)
    assert any("Base Back" in l for l in labels)
    assert any("Base Left" in l for l in labels)
    assert any("Base Right" in l for l in labels)
    assert any("Lid Top" in l for l in labels)
    assert any("Lid Front" in l for l in labels)
    assert any("Lid Back" in l for l in labels)
    assert any("Lid Left" in l for l in labels)
    assert any("Lid Right" in l for l in labels)

    # Bounding box should stay fixed to base case dimensions (does not adapt camera view)
    min_pt, max_pt = mesh_exploded.bounding_box
    assert min_pt.x == pytest.approx(0.0)
    assert min_pt.y == pytest.approx(0.0)
    assert min_pt.z == pytest.approx(0.0)
    assert max_pt.x == pytest.approx(L)
    assert max_pt.y == pytest.approx(W)
    assert max_pt.z == pytest.approx(H)


def test_schema_3d_bounding_box_invariant_across_transforms():
    """Verify 3D bounding box remains constant across explode gap, lid rotation, and lid split gap."""
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )
    L, W, H = case.outer_length, case.outer_width, case.total_height

    for explode in [0.0, 50.0, 150.0]:
        for angle in [0.0, 45.0, 120.0]:
            for split_gap in [0.0, 30.0, 100.0]:
                mesh = Schema3DGeometryBuilder.build_geometry(
                    case,
                    lid_exploded_gap_mm=split_gap,
                    explode_gap_mm=explode,
                    lid_rotation_angle_deg=angle,
                    lid_hinge_side="Back",
                )
                p_min, p_max = mesh.bounding_box
                assert (p_min.x, p_min.y, p_min.z) == (0.0, 0.0, 0.0)
                assert (p_max.x, p_max.y, p_max.z) == (pytest.approx(L), pytest.approx(W), pytest.approx(H))


def test_schema_3d_explode_view_self_cut_lid():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        self_cut_lid=True,
    )
    mesh = Schema3DGeometryBuilder.build_geometry(
        case,
        explode_gap_mm=50.0,
        show_dimensions=True,
        show_all_panel_dimensions=True,
    )

    # 1. Verify 6 uncut panels (36 solid faces total: 1 bottom, 1 top, 4 side walls)
    # Side panels are NOT split into separate base and lid panels
    assert len(mesh.faces) == 36
    labels = {f.label for f in mesh.faces}
    assert "Bottom Panel" in labels
    assert "Top Panel" in labels
    assert "Long Sides (Front & Back)" in labels
    assert "Short Sides (Left & Right)" in labels
    assert not any("Lid Front" in l for l in labels)
    assert not any("Base Front" in l for l in labels)

    # 2. Verify dashed cut line segments marking where lid is to be cut
    dashed_segs = [s for s in mesh.segments if s.style == "dashed"]
    assert len(dashed_segs) == 16  # 4 segments per side wall * 4 walls
    # Cut height is at z_cut = t_wood + base_wood_height = 9.0 + 295.0 = 304.0 mm
    z_cut_expected = case.wood_thickness + case.base_wood_height
    for s in dashed_segs:
        assert s.p1.z == pytest.approx(z_cut_expected)
        assert s.p2.z == pytest.approx(z_cut_expected)
        assert s.label == "Lid Cut Line"

    # 3. Verify single height dimension for side panels (total wood height = 390 mm)
    exploded_panel_dims = [d for d in mesh.dimensions if d.dimension_type == "panel_dim"]
    dim_labels = [d.label for d in exploded_panel_dims]
    assert any("390 mm" in l for l in dim_labels)
    assert not any("295 mm" in l for l in dim_labels)
    assert not any("95 mm" in l for l in dim_labels)


def test_wood_panels_svg_generator():
    from flightcase.domain import WoodPanelsSvgGenerator

    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )

    svg_content = WoodPanelsSvgGenerator.generate_wood_panels_svg(case)

    assert isinstance(svg_content, str)
    assert svg_content.startswith("<svg")
    assert svg_content.endswith("</svg>")
    assert "xmlns=\"http://www.w3.org/2000/svg\"" in svg_content
    assert "fill=\"#ffffff\"" in svg_content  # Printer-friendly white background
    assert "FLIGHTCASE WOOD PANELS CUT DIAGRAM" in svg_content
    assert "Top &amp; Bottom Panels" in svg_content or "Top & Bottom Panels" in svg_content
    assert "QTY: 2" in svg_content
    assert "818.0 mm" in svg_content  # 800 + 18 outer length
    assert "518.0 mm" in svg_content  # 500 + 18 outer width
    assert "<line" in svg_content
    assert "<marker" in svg_content

    # With custom project title
    svg_with_title = WoodPanelsSvgGenerator.generate_wood_panels_svg(case, title="Laser Tour Trunk")
    assert "Laser Tour Trunk — Wood Panels Cut Diagram" in svg_with_title
    assert "<title>Laser Tour Trunk — Wood Panels Cut Diagram</title>" in svg_with_title


def test_panel_grouping_same_size_and_width():
    """Verifies that panels with identical dimensions (cut length, width, thickness) are grouped together in cut list and 2D view."""
    # Case with 3 identical width-wise divider walls
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
    )
    case.add_wall(InsideWall(orientation=WallOrientation.WIDTH_WISE, position_mm=200.0, label="Wall 1"))
    case.add_wall(InsideWall(orientation=WallOrientation.WIDTH_WISE, position_mm=400.0, label="Wall 2"))
    case.add_wall(InsideWall(orientation=WallOrientation.WIDTH_WISE, position_mm=600.0, label="Wall 3"))

    cuts = case.calculate_wood_cut_list()
    # Top & Bottom grouped (qty 2), Base Long (qty 2), Base Short (qty 2), Lid Long (qty 2), Lid Short (qty 2), Walls (qty 3) = 6 cut items (total 13 pieces)
    assert len(cuts) == 6
    assert sum(c.quantity for c in cuts) == 13

    # Inside walls should be grouped into a single entry with quantity 3
    wall_cuts = [c for c in cuts if "Wall" in c.name or "Divider" in c.name or c.category == CutPieceCategory.WOOD_DIVIDER]
    assert len(wall_cuts) == 1
    assert wall_cuts[0].quantity == 3
    assert wall_cuts[0].length_mm == 600.0
    assert wall_cuts[0].width_mm == 400.0

    # 2D SVG Diagram should also reflect the grouped panel with QTY: 3
    from flightcase.domain import WoodPanelsSvgGenerator
    svg = WoodPanelsSvgGenerator.generate_wood_panels_svg(case)
    assert "QTY: 3" in svg
    assert "Inside Walls (3 pcs, Width-wise)" in svg or "Inside Walls" in svg
