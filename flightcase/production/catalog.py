"""Catálogos editables de herrajes y perfiles de aluminio (JSON en resources/)."""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..paths import editable_resource, user_resource

HARDWARE_NAME = "hardware.json"
ALU_PROFILES_NAME = "alu_profiles.json"

# Tipos de perfil que usa el cálculo de cortes (ver FlightCase.calculate_alu_profiles)
PROFILE_KIND_LID_MALE = "lid_male"
PROFILE_KIND_LID_FEMALE = "lid_female"
PROFILE_KIND_EDGE_ANGLE = "edge_angle"


@dataclass
class HardwareItem:
    """Herraje del catálogo (cierre, bisagra, asa, esquinero, rueda, remache...)."""
    id: str
    name: str
    category: str = "Varios"
    unit_price: float = 0.0
    weight_kg: float = 0.0
    rivets_per_unit: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HardwareItem":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", data.get("id", "Herraje"))),
            category=str(data.get("category", "Varios")),
            unit_price=float(data.get("unit_price", 0.0)),
            weight_kg=float(data.get("weight_kg", 0.0)),
            rivets_per_unit=int(data.get("rivets_per_unit", 0)),
        )


@dataclass
class AluProfileSpec:
    """Perfil de aluminio del catálogo, con precio y peso por metro y largo de barra."""
    id: str
    name: str
    kind: str
    price_per_m: float = 0.0
    weight_kg_per_m: float = 0.0
    bar_length_mm: float = 4000.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AluProfileSpec":
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", data.get("id", "Perfil"))),
            kind=str(data.get("kind", data.get("id", ""))),
            price_per_m=float(data.get("price_per_m", 0.0)),
            weight_kg_per_m=float(data.get("weight_kg_per_m", 0.0)),
            bar_length_mm=float(data.get("bar_length_mm", 4000.0)),
        )


def _load_list(path: Path) -> List[Dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [d for d in data if isinstance(d, dict)] if isinstance(data, list) else []


def load_hardware(path: Optional[Path] = None) -> List[HardwareItem]:
    return [HardwareItem.from_dict(d) for d in _load_list(path or editable_resource(HARDWARE_NAME))]


def save_hardware(items: List[HardwareItem], path: Optional[Path] = None) -> None:
    path = path or user_resource(HARDWARE_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load_alu_profiles(path: Optional[Path] = None) -> List[AluProfileSpec]:
    return [AluProfileSpec.from_dict(d) for d in _load_list(path or editable_resource(ALU_PROFILES_NAME))]


def save_alu_profiles(items: List[AluProfileSpec], path: Optional[Path] = None) -> None:
    path = path or user_resource(ALU_PROFILES_NAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([i.to_dict() for i in items], indent=2, ensure_ascii=False), encoding="utf-8"
    )


class Catalog:
    """Agrupa los catálogos y permite buscar por id o tipo."""

    def __init__(
        self,
        hardware: Optional[List[HardwareItem]] = None,
        profiles: Optional[List[AluProfileSpec]] = None,
    ) -> None:
        self.hardware: List[HardwareItem] = hardware if hardware is not None else load_hardware()
        self.profiles: List[AluProfileSpec] = profiles if profiles is not None else load_alu_profiles()

    def hardware_by_id(self, item_id: str) -> Optional[HardwareItem]:
        return next((h for h in self.hardware if h.id == item_id), None)

    def profile_by_kind(self, kind: str) -> Optional[AluProfileSpec]:
        return next((p for p in self.profiles if p.kind == kind), None)
