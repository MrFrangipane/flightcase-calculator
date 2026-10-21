"""Data models for flightcase dimensions, partitions, and cut pieces."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class DividerOrientation(Enum):
    """Orientation of an inside partition wall."""
    WIDTH_WISE = "Width-wise (divides Length, parallel to Width)"
    LENGTH_WISE = "Length-wise (divides Width, parallel to Length)"


@dataclass
class Divider:
    """Inside divider wall specification."""
    orientation: DividerOrientation
    position_mm: float  # Distance from left (for width-wise) or front (for length-wise)
    thickness_mm: float = 9.0
    height_mm: Optional[float] = None  # None for full inner base height
    label: str = ""


@dataclass
class CutPiece:
    """Individual cut piece for wood panel or aluminum profile."""
    name: str
    category: str  # e.g., "Wood Panel - Base", "Wood Panel - Lid", "Wood Panel - Divider", "Alu Profile - Lid Hybrid"
    length_mm: float
    width_mm: float  # For 1D profiles, width_mm is profile width or 0
    thickness_mm: float
    quantity: int
    notes: str = ""

    @property
    def area_m2(self) -> float:
        """Area in square meters for all units of this piece."""
        return (self.length_mm * self.width_mm * self.quantity) / 1_000_000.0

    @property
    def single_area_m2(self) -> float:
        """Area in square meters for a single piece."""
        return (self.length_mm * self.width_mm) / 1_000_000.0

    @property
    def total_length_m(self) -> float:
        """Total linear meters (primarily for profiles or sum of lengths)."""
        return (self.length_mm * self.quantity) / 1_000.0


@dataclass
class CaseParameters:
    """Input dimensions and configuration of the flightcase."""
    # Inner dimensions (mm)
    inner_length: float = 800.0
    inner_width: float = 500.0
    inner_total_height: float = 400.0
    inner_lid_height: float = 100.0

    # Wood panel specifications (mm)
    wood_thickness: float = 9.0

    # Aluminum profile added dimension (mm) - subtracted from height
    lid_alu_profile_offset: float = 10.0

    # Aluminum corner rebate / extrusion offset (mm) - 0 for standard flush butt / corner angle
    corner_extrusion_rebate: float = 0.0

    # Aluminum angle profile width (mm) for edge calculations (e.g. 30mm x 30mm)
    edge_profile_width: float = 30.0

    # User self-cuts the lid from an uncut 6-wall closed box
    self_cut_lid: bool = False

    # Internal dividers
    dividers: List[Divider] = field(default_factory=list)

    # Legacy/compatibility aliases for inputs
    def __init__(
        self,
        inner_length: Optional[float] = None,
        inner_width: Optional[float] = None,
        inner_total_height: Optional[float] = None,
        inner_lid_height: Optional[float] = None,
        wood_thickness: float = 9.0,
        lid_alu_profile_offset: float = 10.0,
        corner_extrusion_rebate: float = 0.0,
        edge_profile_width: float = 30.0,
        self_cut_lid: bool = False,
        dividers: Optional[List[Divider]] = None,
        outer_length: Optional[float] = None,
        outer_width: Optional[float] = None,
        total_height: Optional[float] = None,
        lid_height: Optional[float] = None,
    ):
        self.wood_thickness = wood_thickness
        self.lid_alu_profile_offset = lid_alu_profile_offset
        self.corner_extrusion_rebate = corner_extrusion_rebate
        self.edge_profile_width = edge_profile_width
        self.self_cut_lid = self_cut_lid
        self.dividers = list(dividers) if dividers is not None else []

        if inner_length is not None:
            self.inner_length = inner_length
        elif outer_length is not None:
            self.inner_length = max(0.0, outer_length - (2.0 * wood_thickness))
        else:
            self.inner_length = 800.0

        if inner_width is not None:
            self.inner_width = inner_width
        elif outer_width is not None:
            self.inner_width = max(0.0, outer_width - (2.0 * wood_thickness))
        else:
            self.inner_width = 500.0

        if inner_total_height is not None:
            self.inner_total_height = inner_total_height
        elif total_height is not None:
            self.inner_total_height = max(0.0, total_height - (2.0 * wood_thickness))
        else:
            self.inner_total_height = 400.0

        if inner_lid_height is not None:
            self.inner_lid_height = inner_lid_height
        elif lid_height is not None:
            self.inner_lid_height = max(0.0, lid_height - wood_thickness)
        else:
            self.inner_lid_height = 100.0

    @property
    def outer_length(self) -> float:
        """Nominal outer length including wood thickness."""
        return self.inner_length + (2.0 * self.wood_thickness)

    @property
    def outer_width(self) -> float:
        """Nominal outer width including wood thickness."""
        return self.inner_width + (2.0 * self.wood_thickness)

    @property
    def total_height(self) -> float:
        """Nominal outer total height."""
        return self.inner_total_height + (2.0 * self.wood_thickness)

    @property
    def lid_height(self) -> float:
        """Nominal outer lid height."""
        return self.inner_lid_height + self.wood_thickness

    @property
    def inner_base_height(self) -> float:
        """Interior usable height inside base box."""
        return max(0.0, self.inner_total_height - self.inner_lid_height)

    @property
    def base_height(self) -> float:
        """Outer height of the base part."""
        return max(0.0, self.total_height - self.lid_height)

    @property
    def total_wood_height(self) -> float:
        """Total height of wood panels combined, subtracting aluminum lid profile offset."""
        return max(0.0, self.total_height - self.lid_alu_profile_offset)

    @property
    def lid_wood_height(self) -> float:
        """Wood panel height for lid sides (accounting for half profile offset)."""
        half_offset = self.lid_alu_profile_offset / 2.0
        return max(0.0, self.lid_height - half_offset)

    @property
    def base_wood_height(self) -> float:
        """Wood panel height for base sides (accounting for half profile offset)."""
        half_offset = self.lid_alu_profile_offset / 2.0
        return max(0.0, self.base_height - half_offset)


@dataclass
class CalculationResult:
    """Comprehensive calculation outputs."""
    params: CaseParameters
    wood_cut_list: List[CutPiece] = field(default_factory=list)
    alu_profiles_list: List[CutPiece] = field(default_factory=list)
    
    # Summary metrics
    total_wood_area_m2: float = 0.0
    total_wood_weight_kg: float = 0.0  # Approx birch plywood 700 kg/m3
    standard_sheets_required: float = 0.0  # standard 2440 x 1220 mm sheet
    sheet_utilization_pct: float = 0.0
    
    total_lid_mating_profile_length_mm: float = 0.0
    total_edge_angle_profile_length_mm: float = 0.0
