"""Flightcase calculation engine for wood cut lists and aluminum profiles."""

from typing import List, Tuple, Optional
from .models import (
    CaseParameters,
    CalculationResult,
    CutPiece,
    Divider,
    DividerOrientation,
)


def calculate_flightcase(params: CaseParameters) -> CalculationResult:
    """
    Computes all wood panel dimensions, aluminum profile lengths,
    and material efficiency metrics for a given flightcase specification.
    """
    wood_cuts: List[CutPiece] = []
    alu_cuts: List[CutPiece] = []

    rebate = params.corner_extrusion_rebate
    t_wood = params.wood_thickness

    # Outer panel cutting dimensions (taking corner profile rebate into account)
    cut_outer_length = max(0.0, params.outer_length - (2.0 * rebate))
    cut_outer_width = max(0.0, params.outer_width - (2.0 * rebate))
    
    # Internal width for inset side panels
    cut_short_side_length = max(0.0, cut_outer_width - (2.0 * t_wood))

    # Base heights and Lid heights with aluminum profile offset subtracted
    h_base_wood = params.base_wood_height
    h_lid_wood = params.lid_wood_height
    h_total_wood = params.total_wood_height

    if params.self_cut_lid:
        # 6 Walls of uncut closed box to be sawn open by user
        wood_cuts.append(CutPiece(
            name="Bottom Panel",
            category="Wood Panel - Base",
            length_mm=cut_outer_length,
            width_mm=cut_outer_width,
            thickness_mm=t_wood,
            quantity=1,
            notes="Floor panel of 6-sided uncut box"
        ))
        wood_cuts.append(CutPiece(
            name="Top Panel",
            category="Wood Panel - Lid",
            length_mm=cut_outer_length,
            width_mm=cut_outer_width,
            thickness_mm=t_wood,
            quantity=1,
            notes="Roof panel of 6-sided uncut box"
        ))
        wood_cuts.append(CutPiece(
            name="Long Sides (Front & Back)",
            category="Wood Panel - Base",
            length_mm=cut_outer_length,
            width_mm=h_total_wood,
            thickness_mm=t_wood,
            quantity=2,
            notes=f"Full-height long sides to be cut open by user (height adjusted for lid profile: -{params.lid_alu_profile_offset:.1f}mm)"
        ))
        wood_cuts.append(CutPiece(
            name="Short Sides (Left & Right)",
            category="Wood Panel - Base",
            length_mm=cut_short_side_length,
            width_mm=h_total_wood,
            thickness_mm=t_wood,
            quantity=2,
            notes="Full-height short sides inset between front and back panels"
        ))
    else:
        # 1. Base Panels
        wood_cuts.append(CutPiece(
            name="Base Bottom Panel",
            category="Wood Panel - Base",
            length_mm=cut_outer_length,
            width_mm=cut_outer_width,
            thickness_mm=t_wood,
            quantity=1,
            notes="Main floor panel of the flightcase"
        ))

        wood_cuts.append(CutPiece(
            name="Base Long Sides (Front & Back)",
            category="Wood Panel - Base",
            length_mm=cut_outer_length,
            width_mm=h_base_wood,
            thickness_mm=t_wood,
            quantity=2,
            notes=f"Height adjusted for alu profile (-{params.lid_alu_profile_offset / 2:.1f}mm)"
        ))

        wood_cuts.append(CutPiece(
            name="Base Short Sides (Left & Right)",
            category="Wood Panel - Base",
            length_mm=cut_short_side_length,
            width_mm=h_base_wood,
            thickness_mm=t_wood,
            quantity=2,
            notes="Inset between front and back panels"
        ))

        # 2. Lid Panels
        wood_cuts.append(CutPiece(
            name="Lid Top Panel",
            category="Wood Panel - Lid",
            length_mm=cut_outer_length,
            width_mm=cut_outer_width,
            thickness_mm=t_wood,
            quantity=1,
            notes="Main roof panel of the flightcase"
        ))

        wood_cuts.append(CutPiece(
            name="Lid Long Sides (Front & Back)",
            category="Wood Panel - Lid",
            length_mm=cut_outer_length,
            width_mm=h_lid_wood,
            thickness_mm=t_wood,
            quantity=2,
            notes=f"Height adjusted for alu profile (-{params.lid_alu_profile_offset / 2:.1f}mm)"
        ))

        wood_cuts.append(CutPiece(
            name="Lid Short Sides (Left & Right)",
            category="Wood Panel - Lid",
            length_mm=cut_short_side_length,
            width_mm=h_lid_wood,
            thickness_mm=t_wood,
            quantity=2,
            notes="Inset between front and back lid panels"
        ))

    # 3. Inside Dividers / Partition Walls
    inner_w = params.inner_width
    inner_l = params.inner_length
    inner_total_h = params.inner_total_height

    for i, div in enumerate(params.dividers, start=1):
        lbl = div.label or f"Divider #{i}"
        div_thickness = div.thickness_mm if div.thickness_mm > 0 else t_wood
        div_height = div.height_mm if (div.height_mm is not None and div.height_mm > 0) else inner_total_h

        if div.orientation == DividerOrientation.WIDTH_WISE:
            wood_cuts.append(CutPiece(
                name=f"{lbl} (Across Width)",
                category="Wood Panel - Divider",
                length_mm=inner_w,
                width_mm=div_height,
                thickness_mm=div_thickness,
                quantity=1,
                notes=f"Width-wise partition at pos {div.position_mm:.1f}mm"
            ))
        else:
            wood_cuts.append(CutPiece(
                name=f"{lbl} (Across Length)",
                category="Wood Panel - Divider",
                length_mm=inner_l,
                width_mm=div_height,
                thickness_mm=div_thickness,
                quantity=1,
                notes=f"Length-wise partition at pos {div.position_mm:.1f}mm"
            ))

    # 4. Aluminum Profiles - Lid Hybrid Location Profiles (Male & Female mating extrusions)
    # Perimeter of the case for lid split
    perimeter_single = 2.0 * params.outer_length + 2.0 * params.outer_width

    # Male profile on Base rim
    alu_cuts.append(CutPiece(
        name="Lid Location Profile - Base Male (Long)",
        category="Alu Profile - Lid Mating",
        length_mm=params.outer_length,
        width_mm=params.edge_profile_width,
        thickness_mm=2.0,
        quantity=2,
        notes="Mounted along base top edge (front & back)"
    ))
    alu_cuts.append(CutPiece(
        name="Lid Location Profile - Base Male (Short)",
        category="Alu Profile - Lid Mating",
        length_mm=params.outer_width,
        width_mm=params.edge_profile_width,
        thickness_mm=2.0,
        quantity=2,
        notes="Mounted along base top edge (left & right)"
    ))

    # Female profile on Lid rim
    alu_cuts.append(CutPiece(
        name="Lid Location Profile - Lid Female (Long)",
        category="Alu Profile - Lid Mating",
        length_mm=params.outer_length,
        width_mm=params.edge_profile_width,
        thickness_mm=2.0,
        quantity=2,
        notes="Mounted along lid bottom edge (front & back)"
    ))
    alu_cuts.append(CutPiece(
        name="Lid Location Profile - Lid Female (Short)",
        category="Alu Profile - Lid Mating",
        length_mm=params.outer_width,
        width_mm=params.edge_profile_width,
        thickness_mm=2.0,
        quantity=2,
        notes="Mounted along lid bottom edge (left & right)"
    ))

    # 5. Aluminum Profiles - Edge Angle Profiles (e.g. 30x30 angle extrusion)
    alu_cuts.append(CutPiece(
        name="Angle Profile - Base Vertical Corners",
        category="Alu Profile - Edge Protection",
        length_mm=h_base_wood,
        width_mm=params.edge_profile_width,
        thickness_mm=1.5,
        quantity=4,
        notes="4 base vertical corner reinforcements"
    ))
    alu_cuts.append(CutPiece(
        name="Angle Profile - Lid Vertical Corners",
        category="Alu Profile - Edge Protection",
        length_mm=h_lid_wood,
        width_mm=params.edge_profile_width,
        thickness_mm=1.5,
        quantity=4,
        notes="4 lid vertical corner reinforcements"
    ))
    alu_cuts.append(CutPiece(
        name="Angle Profile - Horizontal Length Edges",
        category="Alu Profile - Edge Protection",
        length_mm=params.outer_length,
        width_mm=params.edge_profile_width,
        thickness_mm=1.5,
        quantity=4,
        notes="2 on base bottom, 2 on lid top"
    ))
    alu_cuts.append(CutPiece(
        name="Angle Profile - Horizontal Width Edges",
        category="Alu Profile - Edge Protection",
        length_mm=params.outer_width,
        width_mm=params.edge_profile_width,
        thickness_mm=1.5,
        quantity=4,
        notes="2 on base bottom, 2 on lid top"
    ))

    # Summary metrics
    total_wood_area = sum(p.area_m2 for p in wood_cuts)
    
    # Volumetric weight calculation based on wood density
    # Volume in m3 = Area (m2) * thickness (m)
    total_wood_volume = sum((p.area_m2 * (p.thickness_mm / 1000.0)) for p in wood_cuts)
    density = getattr(params, "wood_density", 700.0)
    wood_price = getattr(params, "wood_price", 18.50)
    wood_weight = total_wood_volume * density
    wood_cost = total_wood_area * wood_price

    # Standard plywood sheet 2440 x 1220 mm = 2.9768 m2
    sheet_area = (2440.0 * 1220.0) / 1_000_000.0
    sheets_req = total_wood_area / sheet_area if sheet_area > 0 else 0.0

    total_lid_mating_len = perimeter_single * 2.0  # Total of male + female profiles
    total_edge_angle_len = (
        (4.0 * h_base_wood) +
        (4.0 * h_lid_wood) +
        (4.0 * params.outer_length) +
        (4.0 * params.outer_width)
    )

    return CalculationResult(
        params=params,
        wood_cut_list=wood_cuts,
        alu_profiles_list=alu_cuts,
        total_wood_area_m2=total_wood_area,
        total_wood_weight_kg=wood_weight,
        total_wood_cost=wood_cost,
        standard_sheets_required=sheets_req,
        sheet_utilization_pct=(sheets_req / max(1, int(sheets_req + 0.999))) * 100.0 if sheets_req > 0 else 100.0,
        total_lid_mating_profile_length_mm=total_lid_mating_len,
        total_edge_angle_profile_length_mm=total_edge_angle_len,
    )


def generate_equispaced_dividers(
    count: int,
    orientation: DividerOrientation,
    params: CaseParameters,
    thickness_mm: float = 9.0
) -> List[Divider]:
    """
    Generates evenly spaced dividers across length or width,
    equally distributing interior clearance while accounting for wood thickness.
    """
    if count <= 0:
        return []

    dividers = []
    span = params.inner_length if orientation == DividerOrientation.WIDTH_WISE else params.inner_width
    usable_clearance = max(0.0, span - (count * thickness_mm))
    compartment_clearance = usable_clearance / (count + 1)

    for i in range(1, count + 1):
        pos = (i * compartment_clearance) + ((i - 1) * thickness_mm) + (thickness_mm / 2.0)
        prefix = "Width" if orientation == DividerOrientation.WIDTH_WISE else "Length"
        dividers.append(Divider(
            orientation=orientation,
            position_mm=pos,
            thickness_mm=thickness_mm,
            label=f"{prefix} Divider #{i}"
        ))

    return dividers


def generate_dividers_from_compartment_spaces(
    clearances_mm: List[float],
    orientation: DividerOrientation,
    params: CaseParameters,
    thicknesses_mm: Optional[List[float]] = None,
) -> List[Divider]:
    """
    Generates partition dividers from a list of desired compartment available clearances,
    strictly accounting for divider wood thicknesses.
    """
    num_comps = len(clearances_mm)
    if num_comps <= 1:
        return []

    num_divs = num_comps - 1
    t_list = list(thicknesses_mm) if thicknesses_mm is not None else [params.wood_thickness] * num_divs
    if len(t_list) < num_divs:
        t_list.extend([params.wood_thickness] * (num_divs - len(t_list)))

    dividers: List[Divider] = []
    accum_pos = 0.0

    for i in range(num_divs):
        comp_c = max(0.0, clearances_mm[i])
        t_div = max(1.0, t_list[i])
        pos = accum_pos + comp_c + (t_div / 2.0)
        accum_pos = pos + (t_div / 2.0)

        prefix = "Width" if orientation == DividerOrientation.WIDTH_WISE else "Length"
        dividers.append(Divider(
            orientation=orientation,
            position_mm=pos,
            thickness_mm=t_div,
            label=f"{prefix} Divider #{i + 1}"
        ))

    return dividers


def compute_compartment_dimensions(params: CaseParameters) -> List[Tuple[str, float, float, float]]:
    """
    Computes interior compartment sizes (Name, Length mm, Width mm, Height mm)
    derived from current divider positions, strictly accounting for wood thickness.
    """
    w_divs = sorted(
        [d for d in params.dividers if d.orientation == DividerOrientation.WIDTH_WISE],
        key=lambda d: d.position_mm
    )
    l_divs = sorted(
        [d for d in params.dividers if d.orientation == DividerOrientation.LENGTH_WISE],
        key=lambda d: d.position_mm
    )

    inner_l = params.inner_length
    inner_w = params.inner_width
    inner_h = params.inner_total_height

    # Calculate usable clearances along Length (divided by width-wise dividers)
    x_clearances: List[float] = []
    if not w_divs:
        x_clearances.append(inner_l)
    else:
        # First
        t0 = w_divs[0].thickness_mm if w_divs[0].thickness_mm > 0 else params.wood_thickness
        x_clearances.append(max(0.0, w_divs[0].position_mm - (t0 / 2.0)))
        # Intermediates
        for i in range(1, len(w_divs)):
            t_prev = w_divs[i-1].thickness_mm if w_divs[i-1].thickness_mm > 0 else params.wood_thickness
            t_curr = w_divs[i].thickness_mm if w_divs[i].thickness_mm > 0 else params.wood_thickness
            gap = max(0.0, (w_divs[i].position_mm - t_curr / 2.0) - (w_divs[i-1].position_mm + t_prev / 2.0))
            x_clearances.append(gap)
        # Last
        t_last = w_divs[-1].thickness_mm if w_divs[-1].thickness_mm > 0 else params.wood_thickness
        x_clearances.append(max(0.0, inner_l - (w_divs[-1].position_mm + t_last / 2.0)))

    # Calculate usable clearances along Width (divided by length-wise dividers)
    y_clearances: List[float] = []
    if not l_divs:
        y_clearances.append(inner_w)
    else:
        # First
        t0 = l_divs[0].thickness_mm if l_divs[0].thickness_mm > 0 else params.wood_thickness
        y_clearances.append(max(0.0, l_divs[0].position_mm - (t0 / 2.0)))
        # Intermediates
        for j in range(1, len(l_divs)):
            t_prev = l_divs[j-1].thickness_mm if l_divs[j-1].thickness_mm > 0 else params.wood_thickness
            t_curr = l_divs[j].thickness_mm if l_divs[j].thickness_mm > 0 else params.wood_thickness
            gap = max(0.0, (l_divs[j].position_mm - t_curr / 2.0) - (l_divs[j-1].position_mm + t_prev / 2.0))
            y_clearances.append(gap)
        # Last
        t_last = l_divs[-1].thickness_mm if l_divs[-1].thickness_mm > 0 else params.wood_thickness
        y_clearances.append(max(0.0, inner_w - (l_divs[-1].position_mm + t_last / 2.0)))

    compartments = []
    comp_idx = 1
    for r, c_width in enumerate(y_clearances):
        for c, c_length in enumerate(x_clearances):
            name = f"Compartment {comp_idx} (Col {c+1}, Row {r+1})"
            compartments.append((name, max(0.0, c_length), max(0.0, c_width), inner_h))
            comp_idx += 1

    return compartments
