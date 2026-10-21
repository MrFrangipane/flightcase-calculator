"""Data Transfer Objects (DTOs) for Application Layer."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InsideWallDTO:
    """DTO for an interior partition wall input/output."""
    orientation: str  # "width_wise" or "length_wise"
    position_mm: float
    thickness_mm: float = 9.0
    height_mm: Optional[float] = None
    label: str = ""


@dataclass
class CaseInputDTO:
    """DTO representing the complete flightcase specification input."""
    outer_length: float = 800.0
    outer_width: float = 500.0
    total_height: float = 400.0
    lid_height: float = 100.0
    wood_thickness: float = 9.0
    lid_alu_profile_offset: float = 10.0  # Added dimension to subtract from height
    corner_extrusion_rebate: float = 0.0
    edge_profile_width: float = 30.0
    walls: List[InsideWallDTO] = field(default_factory=list)


@dataclass
class CutPieceDTO:
    """DTO for a single wood panel or aluminum cut piece."""
    name: str
    category: str
    length_mm: float
    width_mm: float
    thickness_mm: float
    quantity: int
    single_area_m2: float
    total_area_m2: float
    single_length_m: float
    total_length_m: float
    notes: str = ""


@dataclass
class CaseCompartmentDTO:
    """DTO for calculated interior compartment dimensions."""
    name: str
    length_mm: float
    width_mm: float
    height_mm: float
    volume_liters: float


@dataclass
class CalculationResultDTO:
    """DTO containing the comprehensive flightcase calculation result."""
    # Summary & Metrics
    total_wood_area_m2: float
    total_wood_weight_kg: float
    standard_sheets_required: float
    sheet_utilization_pct: float
    
    # Required Alu Profile Lengths
    total_lid_mating_profile_length_mm: float
    total_edge_angle_profile_length_mm: float

    # Dimensions breakdown
    inner_length: float
    inner_width: float
    inner_base_height: float
    inner_lid_height: float
    base_wood_height: float
    lid_wood_height: float
    total_wood_height: float

    # Cut lists & Compartments
    wood_cut_list: List[CutPieceDTO] = field(default_factory=list)
    alu_profiles_list: List[CutPieceDTO] = field(default_factory=list)
    compartments: List[CaseCompartmentDTO] = field(default_factory=list)
