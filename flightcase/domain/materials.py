"""Wood materials and specifications domain models and resource loader."""

from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

_DEFAULT_WOOD_TYPES_FILE = Path(__file__).resolve().parent.parent / "resources" / "wood_types.json"


@dataclass
class WoodMaterial:
    """Represents a wood material type with thickness, density/weight, and price."""
    name: str
    thickness_mm: float = 9.0
    density_kg_m3: float = 700.0
    price_per_m2: float = 18.50
    id: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            self.id = self.name.lower().replace(" ", "_").replace("/", "_").replace("-", "_")

    @property
    def thickness(self) -> float:
        """Alias for thickness_mm."""
        return self.thickness_mm

    @property
    def density(self) -> float:
        """Alias for density_kg_m3."""
        return self.density_kg_m3

    @property
    def weight(self) -> float:
        """Alias for density_kg_m3 (volumetric weight)."""
        return self.density_kg_m3

    @property
    def price(self) -> float:
        """Alias for price_per_m2."""
        return self.price_per_m2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "thickness_mm": self.thickness_mm,
            "density_kg_m3": self.density_kg_m3,
            "price_per_m2": self.price_per_m2,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> WoodMaterial:
        name = str(data.get("name", "Custom"))
        thickness = float(data.get("thickness_mm", data.get("thickness", 9.0)))
        density = float(data.get("density_kg_m3", data.get("density", data.get("weight", 700.0))))
        price = float(data.get("price_per_m2", data.get("price", 18.50)))
        mat_id = str(data.get("id", ""))
        return cls(
            name=name,
            thickness_mm=thickness,
            density_kg_m3=density,
            price_per_m2=price,
            id=mat_id,
        )


def load_wood_materials(file_path: Optional[Path] = None) -> List[WoodMaterial]:
    """Loads wood material specifications from the JSON resource file."""
    path = file_path if file_path is not None else _DEFAULT_WOOD_TYPES_FILE
    if path.is_file():
        try:
            content = path.read_text(encoding="utf-8")
            data = json.loads(content)
            if isinstance(data, list):
                return [WoodMaterial.from_dict(item) for item in data if isinstance(item, dict)]
        except Exception:
            pass

    # Built-in fallback presets if file cannot be read
    return [
        WoodMaterial(name="Generic 7mm", thickness_mm=7.0, density_kg_m3=0.0, price_per_m2=0.0, id="generic_7mm"),
        WoodMaterial(name="Generic 9mm", thickness_mm=9.0, density_kg_m3=0.0, price_per_m2=0.0, id="generic_9mm"),
        WoodMaterial(name="Generic 10mm", thickness_mm=10.0, density_kg_m3=0.0, price_per_m2=0.0, id="generic_10mm"),
        WoodMaterial(name="Bolivar plywood 3mm", thickness_mm=3.0, density_kg_m3=500.0, price_per_m2=16.56, id="bolivar_cp_3mm"),
        WoodMaterial(name="Bolivar plywood 5mm", thickness_mm=5.0, density_kg_m3=500.0, price_per_m2=19.89, id="bolivar_cp_5mm"),
        WoodMaterial(name="Bolivar plywood 10mm", thickness_mm=10.0, density_kg_m3=500.0, price_per_m2=32.90, id="bolivar_cp_10mm"),
        WoodMaterial(name="Bolivar plywood 12mm", thickness_mm=12.0, density_kg_m3=500.0, price_per_m2=39.91, id="bolivar_cp_12mm"),
        WoodMaterial(name="Bolivar plywood 15mm", thickness_mm=15.0, density_kg_m3=500.0, price_per_m2=44.89, id="bolivar_cp_15mm"),
        WoodMaterial(name="Bolivar plywood 18mm", thickness_mm=18.0, density_kg_m3=500.0, price_per_m2=59.89, id="bolivar_cp_18mm"),
        WoodMaterial(name="Vexi.fr plywood pvc 7mm", thickness_mm=7.0, density_kg_m3=500.0, price_per_m2=39.84, id="vexi_cp_pvc_7mm"),
    ]


def save_wood_materials(materials: List[WoodMaterial], file_path: Optional[Path] = None) -> None:
    """Saves wood material specifications to the JSON resource file."""
    path = file_path if file_path is not None else _DEFAULT_WOOD_TYPES_FILE
    data = [mat.to_dict() for mat in materials]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_wood_material(
    name: Optional[str] = None,
    thickness: Optional[float] = None,
    materials: Optional[List[WoodMaterial]] = None,
) -> Optional[WoodMaterial]:
    """Finds a matching wood material by name or thickness."""
    mats = materials if materials is not None else load_wood_materials()
    if name:
        target = name.strip().lower()
        for m in mats:
            if m.name.lower() == target or m.id.lower() == target:
                return m
    if thickness is not None:
        for m in mats:
            if abs(m.thickness_mm - thickness) < 1e-3:
                return m
    return None
