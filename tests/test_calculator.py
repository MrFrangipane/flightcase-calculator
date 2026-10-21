"""Unit tests for flightcase calculator and data models."""

import pytest
from flightcase.models import CaseParameters, Divider, DividerOrientation
from flightcase.calculator import (
    calculate_flightcase,
    generate_equispaced_dividers,
    compute_compartment_dimensions,
)


def test_standard_case_dimensions():
    params = CaseParameters(
        outer_length=800.0,
        outer_width=500.0,
        total_height=400.0,
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        corner_extrusion_rebate=0.0
    )

    assert params.base_height == 300.0
    assert params.total_wood_height == 390.0  # 400 - 10
    assert params.lid_wood_height == 95.0    # 100 - 5
    assert params.base_wood_height == 295.0  # 300 - 5
    assert params.lid_wood_height + params.base_wood_height == 390.0

    assert params.inner_length == 800.0 - 18.0  # 782.0
    assert params.inner_width == 500.0 - 18.0   # 482.0
    assert params.inner_base_height == 295.0 - 9.0  # 286.0
    assert params.inner_total_height == 400.0 - 18.0  # 382.0

    res = calculate_flightcase(params)
    assert len(res.wood_cut_list) == 6  # 2 top/bottom + 2 long base + 2 short base + 2 long lid + 2 short lid = 6 items (each with qty)

    # Base Bottom
    bottom = next(p for p in res.wood_cut_list if p.name == "Base Bottom Panel")
    assert bottom.length_mm == 800.0
    assert bottom.width_mm == 500.0
    assert bottom.quantity == 1

    # Base Long Sides
    base_long = next(p for p in res.wood_cut_list if p.name == "Base Long Sides (Front & Back)")
    assert base_long.length_mm == 800.0
    assert base_long.width_mm == 295.0
    assert base_long.quantity == 2

    # Base Short Sides (inset between front & back)
    base_short = next(p for p in res.wood_cut_list if p.name == "Base Short Sides (Left & Right)")
    assert base_short.length_mm == 500.0 - 18.0  # 482.0
    assert base_short.width_mm == 295.0
    assert base_short.quantity == 2

    # Lid Long Sides
    lid_long = next(p for p in res.wood_cut_list if p.name == "Lid Long Sides (Front & Back)")
    assert lid_long.length_mm == 800.0
    assert lid_long.width_mm == 95.0
    assert lid_long.quantity == 2

    # Lid Short Sides
    lid_short = next(p for p in res.wood_cut_list if p.name == "Lid Short Sides (Left & Right)")
    assert lid_short.length_mm == 482.0
    assert lid_short.width_mm == 95.0
    assert lid_short.quantity == 2


def test_lid_alu_profile_calculation():
    params = CaseParameters(
        outer_length=1000.0,
        outer_width=600.0,
        total_height=500.0,
        lid_height=120.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=12.0
    )

    res = calculate_flightcase(params)
    single_perimeter = 2 * (1000.0 + 600.0)  # 3200.0 mm
    assert res.total_lid_mating_profile_length_mm == 6400.0  # Male + Female = 2 perimeters

    # Check mating profile items in list
    male_long = next(p for p in res.alu_profiles_list if "Base Male (Long)" in p.name)
    assert male_long.length_mm == 1000.0
    assert male_long.quantity == 2

    female_short = next(p for p in res.alu_profiles_list if "Lid Female (Short)" in p.name)
    assert female_short.length_mm == 600.0
    assert female_short.quantity == 2


def test_dividers_cut_list():
    params = CaseParameters(
        outer_length=800.0,
        outer_width=500.0,
        total_height=400.0,
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        dividers=[
            Divider(orientation=DividerOrientation.WIDTH_WISE, position_mm=250.0, label="Compartment 1 Wall"),
            Divider(orientation=DividerOrientation.WIDTH_WISE, position_mm=500.0, label="Compartment 2 Wall"),
            Divider(orientation=DividerOrientation.LENGTH_WISE, position_mm=240.0, label="Longitudinal Wall"),
        ]
    )

    res = calculate_flightcase(params)
    divider_cuts = [p for p in res.wood_cut_list if p.category == "Wood Panel - Divider"]
    assert len(divider_cuts) == 3

    # Width-wise divider length is inner width = 500 - 18 = 482.0
    w_cut = next(p for p in divider_cuts if "Compartment 1 Wall" in p.name)
    assert w_cut.length_mm == 482.0
    assert w_cut.width_mm == 382.0  # inner total height up to lid roof: 400 - 18 = 382.0

    # Length-wise divider length is inner length = 800 - 18 = 782.0
    l_cut = next(p for p in divider_cuts if "Longitudinal Wall" in p.name)
    assert l_cut.length_mm == 782.0
    assert l_cut.width_mm == 382.0


def test_equispaced_divider_generator():
    params = CaseParameters(outer_length=1000.0, outer_width=600.0, wood_thickness=10.0)
    # inner_length = 980, 1 divider should be at 490
    divs = generate_equispaced_dividers(1, DividerOrientation.WIDTH_WISE, params)
    assert len(divs) == 1
    assert pytest.approx(divs[0].position_mm) == 490.0

    # 2 dividers along length should be at 980/3 = 326.67 and 653.33
    divs2 = generate_equispaced_dividers(2, DividerOrientation.WIDTH_WISE, params)
    assert len(divs2) == 2
    assert pytest.approx(divs2[0].position_mm, rel=1e-3) == 980.0 / 3.0
    assert pytest.approx(divs2[1].position_mm, rel=1e-3) == (980.0 / 3.0) * 2.0


def test_compartments_calculation():
    params = CaseParameters(
        outer_length=800.0,
        outer_width=500.0,
        wood_thickness=9.0,
        dividers=[
            Divider(orientation=DividerOrientation.WIDTH_WISE, position_mm=300.0),
        ]
    )
    comps = compute_compartment_dimensions(params)
    assert len(comps) == 2  # 1 width divider splits length into 2 compartments
    assert pytest.approx(comps[0][1]) == 300.0
    assert pytest.approx(comps[1][1]) == (800.0 - 18.0) - 300.0


def test_self_cut_lid_calculation():
    params = CaseParameters(
        outer_length=800.0,
        outer_width=500.0,
        total_height=400.0,
        lid_height=100.0,
        wood_thickness=9.0,
        lid_alu_profile_offset=10.0,
        self_cut_lid=True,
    )

    res = calculate_flightcase(params)
    # When self_cut_lid=True, wood_cut_list should contain exactly 4 entries (6 outer panels: 1 bottom, 1 top, 2 long, 2 short)
    assert len(res.wood_cut_list) == 4
    total_panels = sum(p.quantity for p in res.wood_cut_list)
    assert total_panels == 6

    bottom = next(p for p in res.wood_cut_list if p.name == "Bottom Panel")
    assert bottom.length_mm == 800.0
    assert bottom.width_mm == 500.0
    assert bottom.quantity == 1

    top = next(p for p in res.wood_cut_list if p.name == "Top Panel")
    assert top.length_mm == 800.0
    assert top.width_mm == 500.0
    assert top.quantity == 1

    long_sides = next(p for p in res.wood_cut_list if p.name == "Long Sides (Front & Back)")
    assert long_sides.length_mm == 800.0
    assert long_sides.width_mm == 390.0  # 400 - 10
    assert long_sides.quantity == 2

    short_sides = next(p for p in res.wood_cut_list if p.name == "Short Sides (Left & Right)")
    assert short_sides.length_mm == 500.0 - 18.0  # 482.0
    assert short_sides.width_mm == 390.0  # 400 - 10
    assert short_sides.quantity == 2
