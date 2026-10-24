"""Domain entities and Aggregate Root for Flightcase."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional
from .exceptions import (
    InvalidDimensionError,
    InvalidLidConfigurationError,
    WallOutOfBoundsError,
)
from .value_objects import (
    Dimensions3D,
    InsideWall,
    WallOrientation,
    CutPiece,
    CutPieceCategory,
)


@dataclass
class CaseCompartment:
    """Calculated internal compartment volume and boundary."""
    name: str
    length_mm: float
    width_mm: float
    height_mm: float

    @property
    def volume_liters(self) -> float:
        return (self.length_mm * self.width_mm * self.height_mm) / 1_000_000.0


@dataclass
class FlightCase:
    """
    Aggregate Root representing the entire Flightcase specification.
    Enforces all domain invariants, material calculations, and interior partitions.
    Input dimensions represent the internal usable cavity (inner case dimensions).
    """
    dimensions: Dimensions3D  # Represents inner length, inner width, and inner total height
    lid_height: float         # Represents inner lid height (clearance inside lid)
    wood_thickness: float
    lid_alu_profile_offset: float = 10.0  # Added dimension subtracted from wood height
    corner_extrusion_rebate: float = 0.0
    edge_profile_width: float = 30.0
    self_cut_lid: bool = False
    _walls: List[InsideWall] = field(default_factory=list)
    wood_material: str = "Birch plywood 9mm"
    wood_density: float = 700.0
    wood_price: float = 18.50

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Enforces all domain invariants."""
        if self.lid_height <= 0.0:
            raise InvalidDimensionError(f"Inner lid height must be positive, got {self.lid_height}mm")

        if self.lid_height >= self.dimensions.height_mm:
            raise InvalidLidConfigurationError(
                f"Inner lid height ({self.lid_height}mm) must be strictly less than inner total height ({self.dimensions.height_mm}mm)"
            )

        if self.lid_alu_profile_offset < 0.0:
            raise InvalidDimensionError(
                f"Lid profile offset cannot be negative, got {self.lid_alu_profile_offset}mm"
            )

        if self.wood_thickness <= 0.0:
            raise InvalidDimensionError(f"Wood thickness must be positive, got {self.wood_thickness}mm")

        if self.dimensions.length_mm <= 0.0 or self.dimensions.width_mm <= 0.0:
            raise InvalidDimensionError(
                f"Inner dimensions must be positive (L={self.dimensions.length_mm}mm, W={self.dimensions.width_mm}mm)"
            )

        half_offset = self.lid_alu_profile_offset / 2.0
        if (self.lid_height + self.wood_thickness) <= half_offset:
            raise InvalidLidConfigurationError(
                f"Lid height ({self.lid_height}mm) is too small for profile offset ({self.lid_alu_profile_offset}mm)"
            )

        base_nominal_h = (self.dimensions.height_mm - self.lid_height) + self.wood_thickness
        if base_nominal_h <= half_offset:
            raise InvalidLidConfigurationError(
                f"Base height ({base_nominal_h}mm) is too small for profile offset ({self.lid_alu_profile_offset}mm)"
            )

        for wall in self._walls:
            self._validate_wall_bounds(wall)

    def _validate_wall_bounds(self, wall: InsideWall) -> None:
        """Validates that a wall is placed strictly inside the interior space."""
        if wall.orientation == WallOrientation.WIDTH_WISE:
            if wall.position_mm <= 0.0 or wall.position_mm >= self.inner_length:
                raise WallOutOfBoundsError(
                    f"Width-wise wall position {wall.position_mm}mm is outside usable inner length (0 to {self.inner_length:.1f}mm)"
                )
        else:
            if wall.position_mm <= 0.0 or wall.position_mm >= self.inner_width:
                raise WallOutOfBoundsError(
                    f"Length-wise wall position {wall.position_mm}mm is outside usable inner width (0 to {self.inner_width:.1f}mm)"
                )

    # --- Dimension Properties ---

    @property
    def inner_length(self) -> float:
        """Usable internal length inside the flightcase."""
        return self.dimensions.length_mm

    @property
    def inner_width(self) -> float:
        """Usable internal width inside the flightcase."""
        return self.dimensions.width_mm

    @property
    def inner_total_height(self) -> float:
        """Usable internal total height inside the closed flightcase (floor to lid roof ceiling)."""
        return self.dimensions.height_mm

    @property
    def inner_lid_height(self) -> float:
        """Usable internal height inside the lid box."""
        return self.lid_height

    @property
    def inner_base_height(self) -> float:
        """Usable internal height inside the base box."""
        return max(0.0, self.inner_total_height - self.inner_lid_height)

    @property
    def outer_length(self) -> float:
        """External nominal length including wood panel thickness."""
        return self.inner_length + (2.0 * self.wood_thickness)

    @property
    def outer_width(self) -> float:
        """External nominal width including wood panel thickness."""
        return self.inner_width + (2.0 * self.wood_thickness)

    @property
    def total_height(self) -> float:
        """External nominal total height of the closed flightcase."""
        return self.inner_total_height + (2.0 * self.wood_thickness)

    @property
    def outer_lid_height(self) -> float:
        """Nominal outer height of the lid box."""
        return self.inner_lid_height + self.wood_thickness

    @property
    def base_height(self) -> float:
        """Nominal outer height of the base box."""
        return self.total_height - self.outer_lid_height

    @property
    def total_wood_height(self) -> float:
        """Total combined height of wood panels, subtracting aluminum profile offset."""
        return max(0.0, self.inner_total_height - self.lid_alu_profile_offset)

    @property
    def lid_wood_height(self) -> float:
        """Wood panel height for lid box sides."""
        half_offset = self.lid_alu_profile_offset / 2.0
        return max(0.0, self.inner_lid_height - half_offset)

    @property
    def base_wood_height(self) -> float:
        """Wood panel height for base box sides."""
        half_offset = self.lid_alu_profile_offset / 2.0
        return max(0.0, self.inner_base_height - half_offset)

    @property
    def walls(self) -> List[InsideWall]:
        """List of interior partition walls."""
        return list(self._walls)

    # --- Wall Manipulation ---

    def add_wall(self, wall: InsideWall) -> None:
        """Adds a partition wall after boundary validation."""
        self._validate_wall_bounds(wall)
        self._walls.append(wall)

    def remove_wall(self, index: int) -> None:
        """Removes a partition wall by index."""
        if 0 <= index < len(self._walls):
            self._walls.pop(index)

    def clear_walls(self) -> None:
        """Clears all partition walls."""
        self._walls.clear()

    def set_walls(self, walls: List[InsideWall]) -> None:
        """Replaces all partition walls with validation."""
        for w in walls:
            self._validate_wall_bounds(w)
        self._walls = list(walls)

    def set_equispaced_walls(
        self,
        count: int,
        orientation: WallOrientation,
        thickness_mm: Optional[float] = None
    ) -> None:
        """
        Configures N evenly spaced dividers along the given orientation,
        distributing available interior clearance equally while accounting for wall thickness.
        """
        t_wall = thickness_mm if thickness_mm is not None else self.wood_thickness
        new_walls: List[InsideWall] = []
        if count > 0:
            span = self.inner_length if orientation == WallOrientation.WIDTH_WISE else self.inner_width
            total_wall_thickness = count * t_wall
            usable_clearance = max(0.0, span - total_wall_thickness)
            compartment_clearance = usable_clearance / (count + 1)

            for i in range(1, count + 1):
                # Center of wall i: (i compartments clearance) + (i-1 full walls) + half of current wall
                pos = (i * compartment_clearance) + ((i - 1) * t_wall) + (t_wall / 2.0)
                label = f"{'Width' if orientation == WallOrientation.WIDTH_WISE else 'Length'} Wall #{i}"
                new_walls.append(InsideWall(
                    orientation=orientation,
                    position_mm=pos,
                    thickness_mm=t_wall,
                    label=label
                ))
        self.set_walls(new_walls)

    def set_walls_from_compartment_spaces(
        self,
        clearances_mm: List[float],
        orientation: WallOrientation,
        thicknesses_mm: Optional[List[float]] = None,
        labels: Optional[List[str]] = None,
        heights_mm: Optional[List[Optional[float]]] = None,
    ) -> None:
        """
        Creates and positions partition walls from a list of desired compartment available clearances (spaces),
        strictly taking each partition wall's wood thickness into account.
        
        For N compartments (len(clearances_mm)), N-1 partition walls are created.
        """
        num_comps = len(clearances_mm)
        if num_comps <= 1:
            # 1 or 0 compartments means no partition walls in this orientation
            # Keep walls in the other orientation
            other_walls = [w for w in self._walls if w.orientation != orientation]
            self.set_walls(other_walls)
            return

        num_walls = num_comps - 1
        t_default = self.wood_thickness
        span = self.inner_length if orientation == WallOrientation.WIDTH_WISE else self.inner_width

        # Default wall thicknesses
        t_list = list(thicknesses_mm) if thicknesses_mm is not None else [t_default] * num_walls
        if len(t_list) < num_walls:
            t_list.extend([t_default] * (num_walls - len(t_list)))

        # Default labels
        lbl_list = list(labels) if labels is not None else []
        for i in range(len(lbl_list), num_walls):
            prefix = "Width" if orientation == WallOrientation.WIDTH_WISE else "Length"
            lbl_list.append(f"{prefix} Wall #{i + 1}")

        # Default heights
        h_list = list(heights_mm) if heights_mm is not None else [None] * num_walls
        if len(h_list) < num_walls:
            h_list.extend([None] * (num_walls - len(h_list)))

        new_orientation_walls: List[InsideWall] = []
        accum_pos = 0.0

        for i in range(num_walls):
            comp_clearance = max(0.0, clearances_mm[i])
            wall_thick = max(1.0, t_list[i])
            # Wall center position:
            # start of compartment + compartment clearance + half wall thickness
            wall_pos = accum_pos + comp_clearance + (wall_thick / 2.0)
            accum_pos = wall_pos + (wall_thick / 2.0)

            new_orientation_walls.append(InsideWall(
                orientation=orientation,
                position_mm=wall_pos,
                thickness_mm=wall_thick,
                height_mm=h_list[i],
                label=lbl_list[i]
            ))

        # Preserve walls of the other orientation
        other_walls = [w for w in self._walls if w.orientation != orientation]
        self.set_walls(other_walls + new_orientation_walls)

    def get_compartment_clearances(self, orientation: WallOrientation) -> List[float]:
        """
        Calculates the actual available clearance (usable space) in each compartment along the given orientation,
        taking partition wall wood thicknesses into account.
        """
        walls = sorted(
            [w for w in self._walls if w.orientation == orientation],
            key=lambda w: w.position_mm
        )
        span = self.inner_length if orientation == WallOrientation.WIDTH_WISE else self.inner_width
        if not walls:
            return [span]

        clearances: List[float] = []
        # First compartment: 0 to left face of first wall
        first_thick = walls[0].thickness_mm if walls[0].thickness_mm > 0 else self.wood_thickness
        c0 = max(0.0, walls[0].position_mm - (first_thick / 2.0))
        clearances.append(c0)

        # Intermediate compartments: between right face of wall i-1 and left face of wall i
        for i in range(1, len(walls)):
            prev_thick = walls[i-1].thickness_mm if walls[i-1].thickness_mm > 0 else self.wood_thickness
            curr_thick = walls[i].thickness_mm if walls[i].thickness_mm > 0 else self.wood_thickness
            c_i = max(0.0, (walls[i].position_mm - curr_thick / 2.0) - (walls[i-1].position_mm + prev_thick / 2.0))
            clearances.append(c_i)

        # Last compartment: right face of last wall to inner span end
        last_thick = walls[-1].thickness_mm if walls[-1].thickness_mm > 0 else self.wood_thickness
        c_last = max(0.0, span - (walls[-1].position_mm + (last_thick / 2.0)))
        clearances.append(c_last)

        return clearances

    # --- Calculations ---

    def calculate_wood_cut_list(self) -> List[CutPiece]:
        """Calculates exact cut dimensions for all wood panels."""
        cuts: List[CutPiece] = []
        rebate = self.corner_extrusion_rebate
        t_wood = self.wood_thickness

        cut_l = max(0.0, self.outer_length - (2.0 * rebate))
        cut_w = max(0.0, self.outer_width - (2.0 * rebate))
        cut_inset_w = max(0.0, cut_w - (2.0 * t_wood))

        h_base = self.base_wood_height
        h_lid = self.lid_wood_height
        h_total_wood = self.total_wood_height

        if self.self_cut_lid:
            # 6 Walls of uncut closed box to be sawn open by user
            cuts.append(CutPiece(
                name="Bottom Panel",
                category=CutPieceCategory.WOOD_BASE,
                length_mm=cut_l,
                width_mm=cut_w,
                thickness_mm=t_wood,
                quantity=1,
                notes="Floor panel of 6-sided uncut box"
            ))
            cuts.append(CutPiece(
                name="Top Panel",
                category=CutPieceCategory.WOOD_LID,
                length_mm=cut_l,
                width_mm=cut_w,
                thickness_mm=t_wood,
                quantity=1,
                notes="Roof panel of 6-sided uncut box"
            ))
            cuts.append(CutPiece(
                name="Long Sides (Front & Back)",
                category=CutPieceCategory.WOOD_BASE,
                length_mm=cut_l,
                width_mm=h_total_wood,
                thickness_mm=t_wood,
                quantity=2,
                notes=f"Full-height long sides to be cut open by user (height adjusted for lid profile: -{self.lid_alu_profile_offset:.1f}mm)"
            ))
            cuts.append(CutPiece(
                name="Short Sides (Left & Right)",
                category=CutPieceCategory.WOOD_BASE,
                length_mm=cut_inset_w,
                width_mm=h_total_wood,
                thickness_mm=t_wood,
                quantity=2,
                notes="Full-height short sides inset between front and back panels"
            ))
        else:
            # Base panels
            cuts.append(CutPiece(
                name="Base Bottom Panel",
                category=CutPieceCategory.WOOD_BASE,
                length_mm=cut_l,
                width_mm=cut_w,
                thickness_mm=t_wood,
                quantity=1,
                notes="Main bottom panel of base box"
            ))
            cuts.append(CutPiece(
                name="Base Long Sides (Front & Back)",
                category=CutPieceCategory.WOOD_BASE,
                length_mm=cut_l,
                width_mm=h_base,
                thickness_mm=t_wood,
                quantity=2,
                notes=f"Height adjusted for lid profile (-{self.lid_alu_profile_offset/2.0:.1f}mm)"
            ))
            cuts.append(CutPiece(
                name="Base Short Sides (Left & Right)",
                category=CutPieceCategory.WOOD_BASE,
                length_mm=cut_inset_w,
                width_mm=h_base,
                thickness_mm=t_wood,
                quantity=2,
                notes="Inset between front and back panels"
            ))

            # Lid panels
            cuts.append(CutPiece(
                name="Lid Top Panel",
                category=CutPieceCategory.WOOD_LID,
                length_mm=cut_l,
                width_mm=cut_w,
                thickness_mm=t_wood,
                quantity=1,
                notes="Main top panel of lid box"
            ))
            cuts.append(CutPiece(
                name="Lid Long Sides (Front & Back)",
                category=CutPieceCategory.WOOD_LID,
                length_mm=cut_l,
                width_mm=h_lid,
                thickness_mm=t_wood,
                quantity=2,
                notes=f"Height adjusted for lid profile (-{self.lid_alu_profile_offset/2.0:.1f}mm)"
            ))
            cuts.append(CutPiece(
                name="Lid Short Sides (Left & Right)",
                category=CutPieceCategory.WOOD_LID,
                length_mm=cut_inset_w,
                width_mm=h_lid,
                thickness_mm=t_wood,
                quantity=2,
                notes="Inset between front and back lid panels"
            ))

        # Inside divider walls
        inner_w = self.inner_width
        inner_l = self.inner_length
        inner_total_h = self.inner_total_height

        for i, wall in enumerate(self._walls, start=1):
            lbl = wall.label or f"Inside Wall #{i}"
            w_thick = wall.thickness_mm if wall.thickness_mm > 0 else t_wood
            w_height = wall.height_mm if (wall.height_mm is not None and wall.height_mm > 0) else inner_total_h

            if wall.orientation == WallOrientation.WIDTH_WISE:
                cuts.append(CutPiece(
                    name=f"{lbl} (Width-wise)",
                    category=CutPieceCategory.WOOD_DIVIDER,
                    length_mm=inner_w,
                    width_mm=w_height,
                    thickness_mm=w_thick,
                    quantity=1,
                    notes=f"Positioned along length at {wall.position_mm:.1f}mm"
                ))
            else:
                cuts.append(CutPiece(
                    name=f"{lbl} (Length-wise)",
                    category=CutPieceCategory.WOOD_DIVIDER,
                    length_mm=inner_l,
                    width_mm=w_height,
                    thickness_mm=w_thick,
                    quantity=1,
                    notes=f"Positioned along width at {wall.position_mm:.1f}mm"
                ))

        return self._group_wood_cut_pieces(cuts)

    @staticmethod
    def _group_wood_cut_pieces(pieces: List[CutPiece]) -> List[CutPiece]:
        """
        Groups panels that have the same cut length, width, and thickness.
        Combines quantities, updates panel names to reflect the combined set,
        and consolidates relevant notes.
        """
        if not pieces:
            return []

        grouped: dict[tuple[float, float, float], list[CutPiece]] = {}
        for p in pieces:
            dim_key = (
                round(min(p.length_mm, p.width_mm), 2),
                round(max(p.length_mm, p.width_mm), 2),
                round(p.thickness_mm, 2),
            )
            grouped.setdefault(dim_key, []).append(p)

        result: List[CutPiece] = []
        for group in grouped.values():
            if len(group) == 1:
                result.append(group[0])
                continue

            total_qty = sum(p.quantity for p in group)
            primary = group[0]
            length_mm = primary.length_mm
            width_mm = primary.width_mm
            thickness_mm = primary.thickness_mm

            names_lower = [p.name.lower() for p in group]

            # 1. Top and Bottom panels
            has_bottom = any("bottom" in n for n in names_lower)
            has_top = any("top" in n for n in names_lower)
            if has_bottom and has_top:
                name = "Top & Bottom Panels"
                notes = "Floor and roof panels"
                category = primary.category
            # 2. Long sides (Front & Back) - e.g. base and lid with equal heights
            elif any("long side" in n or ("front" in n and "back" in n) for n in names_lower) and not any("short" in n for n in names_lower):
                name = "Long Sides (Front & Back)"
                notes = "Front and back side panels"
                category = primary.category
            # 3. Short sides (Left & Right) - e.g. base and lid with equal heights
            elif any("short side" in n or ("left" in n and "right" in n) for n in names_lower) and not any("long" in n for n in names_lower):
                name = "Short Sides (Left & Right)"
                notes = "Left and right short side panels"
                category = primary.category
            # 4. Inside divider walls
            elif all(
                ("divider" in p.category.name.lower() if hasattr(p.category, "name") else "divider" in str(p.category).lower())
                or "wall" in p.name.lower()
                for p in group
            ):
                if all("width" in n for n in names_lower):
                    name = f"Inside Walls ({total_qty} pcs, Width-wise)" if total_qty > 2 else "Inside Walls (Width-wise)"
                elif all("length" in n for n in names_lower):
                    name = f"Inside Walls ({total_qty} pcs, Length-wise)" if total_qty > 2 else "Inside Walls (Length-wise)"
                else:
                    name = f"Inside Walls ({total_qty} pcs)"
                notes_list = [p.notes for p in group if p.notes]
                notes = " • ".join(dict.fromkeys(notes_list))
                category = primary.category
            # 5. General fallback
            else:
                distinct_names = list(dict.fromkeys(p.name for p in group))
                if len(distinct_names) == 1:
                    name = distinct_names[0]
                else:
                    name = " / ".join(distinct_names)
                notes_list = [p.notes for p in group if p.notes]
                notes = " • ".join(dict.fromkeys(notes_list))
                category = primary.category

            result.append(CutPiece(
                name=name,
                category=category,
                length_mm=length_mm,
                width_mm=width_mm,
                thickness_mm=thickness_mm,
                quantity=total_qty,
                notes=notes,
            ))

        return result

    def calculate_alu_profiles(self) -> List[CutPiece]:
        """Calculates exact cut lengths for lid aluminum mating extrusions and edge angles."""
        profiles: List[CutPiece] = []
        l = self.outer_length
        w = self.outer_width
        h_base = self.base_wood_height
        h_lid = self.lid_wood_height
        pw = self.edge_profile_width

        # 1. Lid Hybrid Location Profile (Male on Base rim, Female on Lid rim)
        profiles.append(CutPiece(
            name="Lid Hybrid Profile - Base Male (Long / Front-Back)",
            category=CutPieceCategory.ALU_LID_MATING,
            length_mm=l,
            width_mm=pw,
            thickness_mm=2.0,
            quantity=2,
            notes="Mounted on base rim (front and back)"
        ))
        profiles.append(CutPiece(
            name="Lid Hybrid Profile - Base Male (Short / Left-Right)",
            category=CutPieceCategory.ALU_LID_MATING,
            length_mm=w,
            width_mm=pw,
            thickness_mm=2.0,
            quantity=2,
            notes="Mounted on base rim (left and right)"
        ))
        profiles.append(CutPiece(
            name="Lid Hybrid Profile - Lid Female (Long / Front-Back)",
            category=CutPieceCategory.ALU_LID_MATING,
            length_mm=l,
            width_mm=pw,
            thickness_mm=2.0,
            quantity=2,
            notes="Mounted on lid rim (front and back)"
        ))
        profiles.append(CutPiece(
            name="Lid Hybrid Profile - Lid Female (Short / Left-Right)",
            category=CutPieceCategory.ALU_LID_MATING,
            length_mm=w,
            width_mm=pw,
            thickness_mm=2.0,
            quantity=2,
            notes="Mounted on lid rim (left and right)"
        ))

        # 2. Aluminum Edge Protection Angle Extrusions (e.g. 30x30mm)
        profiles.append(CutPiece(
            name="Corner Angle - Base Vertical Corners",
            category=CutPieceCategory.ALU_EDGE_ANGLE,
            length_mm=h_base,
            width_mm=pw,
            thickness_mm=1.5,
            quantity=4,
            notes="4 base vertical corner reinforcements"
        ))
        profiles.append(CutPiece(
            name="Corner Angle - Lid Vertical Corners",
            category=CutPieceCategory.ALU_EDGE_ANGLE,
            length_mm=h_lid,
            width_mm=pw,
            thickness_mm=1.5,
            quantity=4,
            notes="4 lid vertical corner reinforcements"
        ))
        profiles.append(CutPiece(
            name="Edge Angle - Horizontal Length (Base Bottom & Lid Top)",
            category=CutPieceCategory.ALU_EDGE_ANGLE,
            length_mm=l,
            width_mm=pw,
            thickness_mm=1.5,
            quantity=4,
            notes="2 on base bottom, 2 on lid top"
        ))
        profiles.append(CutPiece(
            name="Edge Angle - Horizontal Width (Base Bottom & Lid Top)",
            category=CutPieceCategory.ALU_EDGE_ANGLE,
            length_mm=w,
            width_mm=pw,
            thickness_mm=1.5,
            quantity=4,
            notes="2 on base bottom, 2 on lid top"
        ))

        return profiles

    @property
    def total_lid_alu_profile_length_mm(self) -> float:
        """Total required linear length of lid mating profile (Male + Female = 2 full perimeters)."""
        single_perimeter = 2.0 * (self.outer_length + self.outer_width)
        return single_perimeter * 2.0

    @property
    def total_edge_angle_profile_length_mm(self) -> float:
        """Total required linear length of edge protection angle profiles."""
        return (
            (4.0 * self.base_wood_height) +
            (4.0 * self.lid_wood_height) +
            (4.0 * self.outer_length) +
            (4.0 * self.outer_width)
        )

    def calculate_compartments(self) -> List[CaseCompartment]:
        """
        Calculates usable compartment dimensions from inside partition walls,
        strictly accounting for wood thickness of outer and partition walls.
        """
        x_clearances = self.get_compartment_clearances(WallOrientation.WIDTH_WISE)
        y_clearances = self.get_compartment_clearances(WallOrientation.LENGTH_WISE)

        compartments: List[CaseCompartment] = []
        c_idx = 1
        for i, dx in enumerate(x_clearances):
            for j, dy in enumerate(y_clearances):
                compartments.append(CaseCompartment(
                    name=f"Compartment {c_idx} (Sec {i+1},{j+1})",
                    length_mm=dx,
                    width_mm=dy,
                    height_mm=self.inner_total_height
                ))
                c_idx += 1

        return compartments
