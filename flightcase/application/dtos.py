"""Data Transfer Objects (DTOs) for Application Layer."""

from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class InsideWallDTO:
    """DTO for an interior partition wall input/output."""
    orientation: str  # "width_wise" or "length_wise"
    position_mm: float
    thickness_mm: float = 9.0
    height_mm: Optional[float] = None
    label: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "orientation": self.orientation,
            "position_mm": self.position_mm,
            "thickness_mm": self.thickness_mm,
            "height_mm": self.height_mm,
            "label": self.label,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> InsideWallDTO:
        return cls(
            orientation=str(data.get("orientation", "width_wise")),
            position_mm=float(data.get("position_mm", 100.0)),
            thickness_mm=float(data.get("thickness_mm", 9.0)),
            height_mm=float(data["height_mm"]) if data.get("height_mm") is not None else None,
            label=str(data.get("label", "")),
        )


@dataclass
class UISettingsDTO:
    """DTO representing UI display, viewport, and interaction settings stored with project."""
    # 3D Viewport Transform & Camera
    camera_azimuth_deg: float = 45.0
    camera_elevation_deg: float = 30.0
    camera_zoom: float = 1.0
    camera_pan_x: float = 0.0
    camera_pan_y: float = 0.0
    is_perspective: bool = False

    # 3D Schema Toggles & Lid Distance
    lid_exploded_gap_mm: float = 0.0
    show_dimensions: bool = True
    show_inside_walls: bool = True
    show_axes: bool = True

    # Active Tab & Inside Walls UI
    active_tab_index: int = 0
    compartment_orientation: str = "width_wise"
    auto_equalize_flags: List[bool] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_azimuth_deg": self.camera_azimuth_deg,
            "camera_elevation_deg": self.camera_elevation_deg,
            "camera_zoom": self.camera_zoom,
            "camera_pan_x": self.camera_pan_x,
            "camera_pan_y": self.camera_pan_y,
            "is_perspective": self.is_perspective,
            "lid_exploded_gap_mm": self.lid_exploded_gap_mm,
            "show_dimensions": self.show_dimensions,
            "show_inside_walls": self.show_inside_walls,
            "show_axes": self.show_axes,
            "active_tab_index": self.active_tab_index,
            "compartment_orientation": self.compartment_orientation,
            "auto_equalize_flags": list(self.auto_equalize_flags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> UISettingsDTO:
        if not data or not isinstance(data, dict):
            return cls()

        raw_auto_flags = data.get("auto_equalize_flags", data.get("compartment_auto_equalize", data.get("auto_equalize", [])))
        if isinstance(raw_auto_flags, list):
            auto_equalize_flags = [bool(f) for f in raw_auto_flags]
        else:
            auto_equalize_flags = []

        return cls(
            camera_azimuth_deg=float(data.get("camera_azimuth_deg", 45.0)),
            camera_elevation_deg=float(data.get("camera_elevation_deg", 30.0)),
            camera_zoom=float(data.get("camera_zoom", 1.0)),
            camera_pan_x=float(data.get("camera_pan_x", 0.0)),
            camera_pan_y=float(data.get("camera_pan_y", 0.0)),
            is_perspective=bool(data.get("is_perspective", False)),
            lid_exploded_gap_mm=float(data.get("lid_exploded_gap_mm", 0.0)),
            show_dimensions=bool(data.get("show_dimensions", True)),
            show_inside_walls=bool(data.get("show_inside_walls", True)),
            show_axes=bool(data.get("show_axes", True)),
            active_tab_index=int(data.get("active_tab_index", 0)),
            compartment_orientation=str(data.get("compartment_orientation", data.get("equispaced_walls_orientation", "width_wise"))),
            auto_equalize_flags=auto_equalize_flags,
        )


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
    self_cut_lid: bool = False
    walls: List[InsideWallDTO] = field(default_factory=list)
    ui_settings: UISettingsDTO = field(default_factory=UISettingsDTO)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": "1.0",
            "outer_length": self.outer_length,
            "outer_width": self.outer_width,
            "total_height": self.total_height,
            "lid_height": self.lid_height,
            "wood_thickness": self.wood_thickness,
            "lid_alu_profile_offset": self.lid_alu_profile_offset,
            "corner_extrusion_rebate": self.corner_extrusion_rebate,
            "edge_profile_width": self.edge_profile_width,
            "self_cut_lid": self.self_cut_lid,
            "walls": [w.to_dict() for w in self.walls],
            "ui_settings": self.ui_settings.to_dict() if self.ui_settings else UISettingsDTO().to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CaseInputDTO:
        raw_walls = data.get("walls", [])
        walls = [InsideWallDTO.from_dict(w) for w in raw_walls if isinstance(w, dict)]
        raw_ui = data.get("ui_settings")
        ui_settings = UISettingsDTO.from_dict(raw_ui) if isinstance(raw_ui, dict) else UISettingsDTO()
        return cls(
            outer_length=float(data.get("outer_length", 800.0)),
            outer_width=float(data.get("outer_width", 500.0)),
            total_height=float(data.get("total_height", 400.0)),
            lid_height=float(data.get("lid_height", 100.0)),
            wood_thickness=float(data.get("wood_thickness", 9.0)),
            lid_alu_profile_offset=float(data.get("lid_alu_profile_offset", 10.0)),
            corner_extrusion_rebate=float(data.get("corner_extrusion_rebate", 0.0)),
            edge_profile_width=float(data.get("edge_profile_width", 30.0)),
            self_cut_lid=bool(data.get("self_cut_lid", False)),
            walls=walls,
            ui_settings=ui_settings,
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> CaseInputDTO:
        data = json.loads(json_str)
        return cls.from_dict(data)


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
    inner_total_height: float
    base_wood_height: float
    lid_wood_height: float
    total_wood_height: float

    # Cut lists & Compartments
    wood_cut_list: List[CutPieceDTO] = field(default_factory=list)
    alu_profiles_list: List[CutPieceDTO] = field(default_factory=list)
    compartments: List[CaseCompartmentDTO] = field(default_factory=list)
