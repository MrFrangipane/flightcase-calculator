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

    assert case.outer_length == 800.0
    assert case.outer_width == 500.0
    assert case.total_height == 400.0
    assert case.base_height == 300.0
    assert case.total_wood_height == 390.0
    assert case.lid_wood_height == 95.0
    assert case.base_wood_height == 295.0
    assert case.inner_length == 782.0
    assert case.inner_width == 482.0
    assert case.inner_base_height == 286.0
    assert case.inner_lid_height == 86.0
    assert case.inner_total_height == 382.0


def test_flightcase_invalid_lid_height():
    with pytest.raises(InvalidLidConfigurationError):
        # Lid height >= total height
        FlightCase(
            dimensions=Dimensions3D(800.0, 500.0, 400.0),
            lid_height=400.0,
            wood_thickness=9.0,
        )

    with pytest.raises(InvalidLidConfigurationError):
        # Lid height too small for profile offset (e.g. lid 4mm, offset 10mm -> half offset 5mm > lid)
        FlightCase(
            dimensions=Dimensions3D(800.0, 500.0, 400.0),
            lid_height=4.0,
            wood_thickness=9.0,
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
    assert len(cuts) == 6

    bottom = next(p for p in cuts if p.name == "Base Bottom Panel")
    assert bottom.length_mm == 800.0
    assert bottom.width_mm == 500.0
    assert bottom.thickness_mm == 9.0
    assert bottom.quantity == 1
    assert bottom.category == CutPieceCategory.WOOD_BASE

    base_long = next(p for p in cuts if "Base Long Sides" in p.name)
    assert base_long.length_mm == 800.0
    assert base_long.width_mm == 295.0
    assert base_long.quantity == 2

    base_short = next(p for p in cuts if "Base Short Sides" in p.name)
    assert base_short.length_mm == 482.0
    assert base_short.width_mm == 295.0
    assert base_short.quantity == 2


def test_lid_alu_profile_required_length():
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 500.0),
        lid_height=120.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=12.0,
    )

    single_perimeter = 2.0 * (1000.0 + 600.0)  # 3200 mm
    assert case.total_lid_alu_profile_length_mm == 6400.0  # Male + Female = 2 perimeters

    profiles = case.calculate_alu_profiles()
    mating_profiles = [p for p in profiles if p.category == CutPieceCategory.ALU_LID_MATING]
    assert len(mating_profiles) == 4
    total_mating_len = sum(p.length_mm * p.quantity for p in mating_profiles)
    assert total_mating_len == 6400.0


def test_inside_walls_addition_and_validation():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
    )

    # Valid width-wise wall (inner_length is 782)
    wall1 = InsideWall(
        orientation=WallOrientation.WIDTH_WISE,
        position_mm=250.0,
        thickness_mm=9.0,
        label="Compartment Wall 1"
    )
    case.add_wall(wall1)
    assert len(case.walls) == 1

    # Out of bounds wall (position >= 782)
    with pytest.raises(WallOutOfBoundsError):
        case.add_wall(InsideWall(
            orientation=WallOrientation.WIDTH_WISE,
            position_mm=800.0
        ))

    # Out of bounds wall for width (inner_width is 482)
    with pytest.raises(WallOutOfBoundsError):
        case.add_wall(InsideWall(
            orientation=WallOrientation.LENGTH_WISE,
            position_mm=500.0
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
    assert full_wall_cut.length_mm == 482.0
    assert full_wall_cut.width_mm == 382.0  # inner total height = 400 - 2*9 = 382.0

    tray_cut = next(p for p in cuts if "Tray Divider" in p.name)
    assert tray_cut.length_mm == 782.0
    assert tray_cut.width_mm == 120.0

    comps = case.calculate_compartments()
    for c in comps:
        assert c.height_mm == 382.0


def test_equispaced_walls_and_compartments():
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 400.0),
        lid_height=100.0,
        wood_thickness=10.0,
    )

    # inner_length = 980, 2 walls (10mm thick each): total wall thickness = 20mm -> usable clearance = 960mm -> 320mm each
    case.set_equispaced_walls(count=2, orientation=WallOrientation.WIDTH_WISE)
    assert len(case.walls) == 2
    assert pytest.approx(case.walls[0].position_mm) == 325.0
    assert pytest.approx(case.walls[1].position_mm) == 655.0

    comps = case.calculate_compartments()
    assert len(comps) == 3
    assert pytest.approx(comps[0].length_mm) == 320.0
    assert pytest.approx(comps[1].length_mm) == 320.0
    assert pytest.approx(comps[2].length_mm) == 320.0
    assert pytest.approx(comps[0].width_mm) == 580.0


def test_custom_compartment_spaces_configuration():
    case = FlightCase(
        dimensions=Dimensions3D(1000.0, 600.0, 400.0),
        lid_height=100.0,
        wood_thickness=10.0,
    )
    # Usable inner_length = 980mm, inner_width = 580mm
    # We want 3 compartments along length with clearances: 250mm, 350mm, 360mm (sum = 960mm + 2*10mm walls = 980mm)
    case.set_walls_from_compartment_spaces(
        clearances_mm=[250.0, 350.0, 360.0],
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
    assert pytest.approx(clearances[2]) == 360.0

    comps = case.calculate_compartments()
    assert len(comps) == 3
    assert pytest.approx(comps[0].length_mm) == 250.0
    assert pytest.approx(comps[1].length_mm) == 350.0
    assert pytest.approx(comps[2].length_mm) == 360.0


def test_domain_calculation_report():
    case = FlightCase(
        dimensions=Dimensions3D(800.0, 500.0, 400.0),
        lid_height=100.0,
        wood_thickness=9.0,
    )

    report = FlightCaseDomainService.calculate(case)
    assert report.total_wood_area_m2 > 0.0
    assert report.total_wood_weight_kg > 0.0
    assert report.total_lid_mating_profile_length_mm == 5200.0
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

    # Verify length and width callouts exist
    dim_labels = [d.label for d in mesh.dimensions]
    assert any("L = 800" in lbl for lbl in dim_labels)
    assert any("W = 500" in lbl for lbl in dim_labels)
    assert any("H = 400" in lbl for lbl in dim_labels)


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

    # 1. Wood cut list has 4 entries representing 6 outer walls
    cuts = case.calculate_wood_cut_list()
    assert len(cuts) == 4
    assert sum(c.quantity for c in cuts) == 6

    bottom = next(c for c in cuts if c.name == "Bottom Panel")
    assert bottom.length_mm == 800.0
    assert bottom.width_mm == 500.0
    assert bottom.quantity == 1

    top = next(c for c in cuts if c.name == "Top Panel")
    assert top.length_mm == 800.0
    assert top.width_mm == 500.0
    assert top.quantity == 1

    long_s = next(c for c in cuts if c.name == "Long Sides (Front & Back)")
    assert long_s.length_mm == 800.0
    assert long_s.width_mm == 390.0
    assert long_s.quantity == 2

    short_s = next(c for c in cuts if c.name == "Short Sides (Left & Right)")
    assert short_s.length_mm == 482.0
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
