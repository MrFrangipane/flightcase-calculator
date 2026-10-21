"""Value Objects for the Flightcase domain."""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
from .exceptions import InvalidDimensionError


@dataclass(frozen=True)
class Dimensions3D:
    """Outer 3D dimensions of a box or case in millimeters."""
    length_mm: float
    width_mm: float
    height_mm: float

    def __post_init__(self) -> None:
        if self.length_mm <= 0.0 or self.width_mm <= 0.0 or self.height_mm <= 0.0:
            raise InvalidDimensionError(
                f"Dimensions must be positive: L={self.length_mm}, W={self.width_mm}, H={self.height_mm}"
            )

    @property
    def volume_m3(self) -> float:
        return (self.length_mm * self.width_mm * self.height_mm) / 1_000_000_000.0


class WallOrientation(str, Enum):
    """Orientation of an interior partition wall."""
    WIDTH_WISE = "width_wise"    # Transverse: divides along Length axis, parallel to Width (Y)
    LENGTH_WISE = "length_wise"  # Longitudinal: divides along Width axis, parallel to Length (X)

    @property
    def display_name(self) -> str:
        if self == WallOrientation.WIDTH_WISE:
            return "Width-wise (Transverse, ⟂ Length)"
        return "Length-wise (Longitudinal, ⟂ Width)"


@dataclass(frozen=True)
class InsideWall:
    """Specification of an inside divider wall."""
    orientation: WallOrientation
    position_mm: float
    thickness_mm: float = 9.0
    height_mm: Optional[float] = None  # None for full internal base height
    label: str = ""

    def __post_init__(self) -> None:
        if self.position_mm <= 0.0:
            raise InvalidDimensionError(f"Wall position must be strictly positive: {self.position_mm}")
        if self.thickness_mm <= 0.0:
            raise InvalidDimensionError(f"Wall thickness must be strictly positive: {self.thickness_mm}")
        if self.height_mm is not None and self.height_mm <= 0.0:
            raise InvalidDimensionError(f"Wall height must be strictly positive: {self.height_mm}")


class CutPieceCategory(str, Enum):
    """Category classification for material cut lists."""
    WOOD_BASE = "Wood Panel - Base"
    WOOD_LID = "Wood Panel - Lid"
    WOOD_DIVIDER = "Wood Panel - Inside Wall"
    ALU_LID_MATING = "Alu Profile - Lid Mating"
    ALU_EDGE_ANGLE = "Alu Profile - Edge Protection"


@dataclass(frozen=True)
class CutPiece:
    """An immutable individual cut piece for wood panels or aluminum extrusions."""
    name: str
    category: CutPieceCategory
    length_mm: float
    width_mm: float  # For 1D profiles, width_mm is profile width or flange size
    thickness_mm: float
    quantity: int
    notes: str = ""

    def __post_init__(self) -> None:
        if self.length_mm < 0.0 or self.width_mm < 0.0 or self.thickness_mm < 0.0:
            raise InvalidDimensionError("Cut piece dimensions cannot be negative")
        if self.quantity <= 0:
            raise InvalidDimensionError(f"Quantity must be at least 1, got {self.quantity}")

    @property
    def single_area_m2(self) -> float:
        """Area of a single cut piece in m²."""
        return (self.length_mm * self.width_mm) / 1_000_000.0

    @property
    def total_area_m2(self) -> float:
        """Combined area of all units in m²."""
        return self.single_area_m2 * self.quantity

    @property
    def single_length_m(self) -> float:
        """Length of a single piece in meters."""
        return self.length_mm / 1_000.0

    @property
    def total_length_m(self) -> float:
        """Total linear meters of this item."""
        return (self.length_mm * self.quantity) / 1_000.0


@dataclass(frozen=True)
class Point3D:
    """3D point coordinate in millimeters."""
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Segment3D:
    """3D line segment with styling tags."""
    p1: Point3D
    p2: Point3D
    style: str = "solid"  # "solid", "dashed", "axis", "profile", "wall"
    color_group: str = "case"  # "case", "lid", "profile", "wall", "dimension"


@dataclass(frozen=True)
class DimensionCallout3D:
    """Dimension annotation in 3D space with text label and offset direction."""
    start: Point3D
    end: Point3D
    label: str
    value_mm: float
    offset_vector: Tuple[float, float, float]
    dimension_type: str = "linear"  # "length", "width", "height", "lid_height", "wall_pos"
