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
    """
    dimensions: Dimensions3D
    lid_height: float
    wood_thickness: float
    lid_alu_profile_offset: float = 10.0  # Added dimension subtracted from height
    corner_extrusion_rebate: float = 0.0
    edge_profile_width: float = 30.0
    _walls: List[InsideWall] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        """Enforces all domain invariants."""
        if self.lid_height <= 0.0:
            raise InvalidDimensionError(f"Lid height must be positive, got {self.lid_height}mm")

        if self.lid_height >= self.dimensions.height_mm:
            raise InvalidLidConfigurationError(
                f"Lid height ({self.lid_height}mm) must be strictly less than total height ({self.dimensions.height_mm}mm)"
            )

        if self.lid_alu_profile_offset < 0.0:
            raise InvalidDimensionError(
                f"Lid profile offset cannot be negative, got {self.lid_alu_profile_offset}mm"
            )

        half_offset = self.lid_alu_profile_offset / 2.0
        if self.lid_height <= half_offset:
            raise InvalidLidConfigurationError(
                f"Lid height ({self.lid_height}mm) is too small for profile offset ({self.lid_alu_profile_offset}mm)"
            )

        base_h = self.dimensions.height_mm - self.lid_height
        if base_h <= half_offset:
            raise InvalidLidConfigurationError(
                f"Base height ({base_h}mm) is too small for profile offset ({self.lid_alu_profile_offset}mm)"
            )

        if self.wood_thickness <= 0.0:
            raise InvalidDimensionError(f"Wood thickness must be positive, got {self.wood_thickness}mm")

        if self.inner_length <= 0.0 or self.inner_width <= 0.0:
            raise InvalidDimensionError(
                f"Wood thickness ({self.wood_thickness}mm) exceeds case dimensions "
                f"(L={self.dimensions.length_mm}mm, W={self.dimensions.width_mm}mm)"
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
    def outer_length(self) -> float:
        return self.dimensions.length_mm

    @property
    def outer_width(self) -> float:
        return self.dimensions.width_mm

    @property
    def total_height(self) -> float:
        return self.dimensions.height_mm

    @property
    def base_height(self) -> float:
        """Nominal outer height of the base box."""
        return max(0.0, self.total_height - self.lid_height)

    @property
    def total_wood_height(self) -> float:
        """Total combined height of wood panels, subtracting aluminum profile offset."""
        return max(0.0, self.total_height - self.lid_alu_profile_offset)

    @property
    def lid_wood_height(self) -> float:
        """Wood panel height for lid box sides."""
        half_offset = self.lid_alu_profile_offset / 2.0
        return max(0.0, self.lid_height - half_offset)

    @property
    def base_wood_height(self) -> float:
        """Wood panel height for base box sides."""
        half_offset = self.lid_alu_profile_offset / 2.0
        return max(0.0, self.base_height - half_offset)

    @property
    def inner_length(self) -> float:
        """Usable internal length inside the flightcase."""
        return max(0.0, self.outer_length - (2.0 * self.wood_thickness))

    @property
    def inner_width(self) -> float:
        """Usable internal width inside the flightcase."""
        return max(0.0, self.outer_width - (2.0 * self.wood_thickness))

    @property
    def inner_base_height(self) -> float:
        """Usable internal height inside the base box."""
        return max(0.0, self.base_wood_height - self.wood_thickness)

    @property
    def inner_lid_height(self) -> float:
        """Usable internal height inside the lid box."""
        return max(0.0, self.lid_wood_height - self.wood_thickness)

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
        """Configures N evenly spaced dividers along the given orientation."""
        t_wall = thickness_mm if thickness_mm is not None else self.wood_thickness
        new_walls: List[InsideWall] = []
        if count > 0:
            span = self.inner_length if orientation == WallOrientation.WIDTH_WISE else self.inner_width
            step = span / (count + 1)
            for i in range(1, count + 1):
                pos = step * i
                label = f"{'Width' if orientation == WallOrientation.WIDTH_WISE else 'Length'} Wall #{i}"
                new_walls.append(InsideWall(
                    orientation=orientation,
                    position_mm=pos,
                    thickness_mm=t_wall,
                    label=label
                ))
        self.set_walls(new_walls)

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
        inner_base_h = self.inner_base_height

        for i, wall in enumerate(self._walls, start=1):
            lbl = wall.label or f"Inside Wall #{i}"
            w_thick = wall.thickness_mm if wall.thickness_mm > 0 else t_wood
            w_height = wall.height_mm if (wall.height_mm is not None and wall.height_mm > 0) else inner_base_h

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

        return cuts

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
        """Calculates usable compartment dimensions from inside partition walls."""
        w_walls = sorted(
            [w for w in self._walls if w.orientation == WallOrientation.WIDTH_WISE],
            key=lambda w: w.position_mm
        )
        l_walls = sorted(
            [w for w in self._walls if w.orientation == WallOrientation.LENGTH_WISE],
            key=lambda w: w.position_mm
        )

        x_coords = [0.0] + [w.position_mm for w in w_walls] + [self.inner_length]
        y_coords = [0.0] + [w.position_mm for w in l_walls] + [self.inner_width]

        compartments: List[CaseCompartment] = []
        c_idx = 1
        for i in range(len(x_coords) - 1):
            dx = max(0.0, x_coords[i+1] - x_coords[i])
            for j in range(len(y_coords) - 1):
                dy = max(0.0, y_coords[j+1] - y_coords[j])
                compartments.append(CaseCompartment(
                    name=f"Compartment {c_idx} (Sec {i+1},{j+1})",
                    length_mm=dx,
                    width_mm=dy,
                    height_mm=self.inner_base_height
                ))
                c_idx += 1

        return compartments
