"""Conteo automático de herrajes, plan de barras/placas y presupuesto completo."""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from ..i18n import tr
from .catalog import (
    Catalog,
    PROFILE_KIND_EDGE_ANGLE,
    PROFILE_KIND_LID_FEMALE,
    PROFILE_KIND_LID_MALE,
)
from .optimizer import BarCut, BarPlan, SheetPlan, expand_parts, optimize_bars, optimize_sheets


@dataclass
class ProductionSettings:
    """Ajustes de fabricación y precio que se guardan con cada proyecto."""
    # Herrajes
    lid_hinged: bool = False          # tapa con bisagras (si no, tapa suelta con cierres alrededor)
    castors: bool = False             # base con 4 ruedas (2 con freno)
    stacking_cups: bool = False       # tazas de apilado en la tapa (requiere ruedas)
    extra_handles: bool = False       # 2 asas más en los laterales largos
    # Corte
    sheet_length_mm: float = 2440.0
    sheet_width_mm: float = 1220.0
    saw_kerf_mm: float = 4.0
    sheet_trim_mm: float = 10.0
    allow_rotation: bool = True       # desactivar si la veta debe ir en un sentido
    profile_kerf_mm: float = 3.0
    charge_full_sheets: bool = False  # cobrar placas enteras en lugar de m² usados
    charge_full_bars: bool = True     # cobrar barras enteras en lugar de metros usados
    # Precio
    wood_waste_pct: float = 10.0      # solo si se cobran m²
    consumables: float = 4.0          # cola, tornillos, lija... por caja
    labor_hours_base: float = 1.5     # horas fijas por caja
    labor_hours_per_m2: float = 0.6   # horas extra por m² de superficie exterior
    labor_rate: float = 25.0          # € por hora
    margin_pct: float = 30.0
    vat_pct: float = 21.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ProductionSettings":
        s = cls()
        if not isinstance(data, dict):
            return s
        for key, default in asdict(s).items():
            if key in data:
                try:
                    setattr(s, key, type(default)(data[key]))
                except (TypeError, ValueError):
                    pass
        return s


@dataclass
class HardwareLine:
    item_id: str
    name: str
    category: str
    quantity: int
    unit_price: float
    weight_kg: float
    placement: str = ""

    @property
    def total_price(self) -> float:
        return self.quantity * self.unit_price

    @property
    def total_weight_kg(self) -> float:
        return self.quantity * self.weight_kg


@dataclass
class ProfileLine:
    kind: str
    name: str
    total_length_m: float
    bars: int
    bar_length_mm: float
    utilization_pct: float
    price: float
    weight_kg: float
    plan: BarPlan


@dataclass
class CostLine:
    concept: str
    amount: float


@dataclass
class Quote:
    hardware: List[HardwareLine]
    profiles: List[ProfileLine]
    sheet_plans: List[SheetPlan]
    cost_lines: List[CostLine]
    labor_hours: float
    materials_cost: float
    labor_cost: float
    subtotal: float
    margin: float
    net_price: float
    vat: float
    total_price: float
    weight_wood_kg: float
    weight_profiles_kg: float
    weight_hardware_kg: float
    warnings: List[str] = field(default_factory=list)

    @property
    def total_weight_kg(self) -> float:
        return self.weight_wood_kg + self.weight_profiles_kg + self.weight_hardware_kg

    @property
    def total_sheets(self) -> int:
        return sum(p.sheet_count for p in self.sheet_plans)


def _latches_per_side(length_mm: float) -> int:
    if length_mm < 400:
        return 1
    if length_mm <= 900:
        return 2
    return 3


def count_hardware(
    outer_length: float,
    outer_width: float,
    case_weight_kg: float,
    settings: ProductionSettings,
) -> List[tuple]:
    """Devuelve [(item_id, cantidad, ubicación)] según tamaño y opciones de la caja."""
    lines: List[tuple] = [("ball_corner", 8, "4 en el cuerpo y 4 en la tapa")]

    long_latches = _latches_per_side(outer_length)
    short_latches = 1 if outer_width >= 450 else 0
    if settings.lid_hinged:
        hinges = 2 if outer_length <= 800 else 3
        lines.append(("hinge", hinges, "Lateral trasero"))
        lines.append(("lid_stay", 1 if outer_length <= 800 else 2, "Interior, entre cuerpo y tapa"))
        latches = long_latches + 2 * short_latches
        lines.append(("butterfly_latch", latches, f"{long_latches} delante" + (", 1 en cada lateral corto" if short_latches else "")))
    else:
        latches = 2 * long_latches + 2 * short_latches
        lines.append(("butterfly_latch", latches, f"{long_latches} delante, {long_latches} detrás" + (", 1 en cada lateral corto" if short_latches else "")))

    handles = 2
    where = "1 en cada lateral corto"
    if settings.extra_handles or outer_length > 1000 or case_weight_kg > 40:
        handles = 4
        where += ", 1 en cada lateral largo"
    lines.append(("recessed_handle", handles, where))

    if settings.castors:
        lines.append(("castor_100", 2, "Base, lado izquierdo"))
        lines.append(("castor_100_brake", 2, "Base, lado derecho"))
        lines.append(("castor_bolt", 16, "4 por rueda"))
        if settings.stacking_cups:
            lines.append(("stacking_cup", 4, "Tapa, alineadas con las ruedas"))
    return lines


def _profile_cuts(alu_pieces) -> Dict[str, List[BarCut]]:
    cuts: Dict[str, List[BarCut]] = {}
    for p in alu_pieces:
        name = p.name.lower()
        if "female" in name:
            kind = PROFILE_KIND_LID_FEMALE
        elif "male" in name:
            kind = PROFILE_KIND_LID_MALE
        else:
            kind = PROFILE_KIND_EDGE_ANGLE
        for _ in range(int(p.quantity)):
            cuts.setdefault(kind, []).append(BarCut(tr(p.name), float(p.length_mm)))
    return cuts


def build_quote(
    *,
    wood_pieces,
    alu_pieces,
    outer_length: float,
    outer_width: float,
    outer_height: float,
    wood_density: float,
    wood_price_m2: float,
    settings: ProductionSettings,
    catalog: Optional[Catalog] = None,
) -> Quote:
    """Calcula herrajes, barras, placas, peso y precio final de una caja."""
    catalog = catalog or Catalog()
    warnings: List[str] = []

    # Madera: despiece en placas por espesor
    sheet_plans: List[SheetPlan] = []
    for thickness, parts in sorted(expand_parts(wood_pieces, tr).items()):
        plan = optimize_sheets(
            parts, thickness,
            settings.sheet_length_mm, settings.sheet_width_mm,
            settings.saw_kerf_mm, settings.sheet_trim_mm, settings.allow_rotation,
        )
        sheet_plans.append(plan)
        for o in plan.oversize:
            warnings.append(f"El panel «{o.label}» ({o.length_mm:.0f}×{o.width_mm:.0f} mm) no entra en una placa.")

    if wood_price_m2 <= 0 or wood_density <= 0:
        warnings.append("La madera elegida no tiene precio o densidad; cárgalos en «Tipos de madera».")
    wood_area = sum(p.length_mm * p.width_mm * p.quantity for p in wood_pieces) / 1_000_000.0
    wood_volume = sum(p.length_mm * p.width_mm * p.quantity * p.thickness_mm for p in wood_pieces) / 1e9
    weight_wood = wood_volume * wood_density
    if settings.charge_full_sheets:
        sheet_area = settings.sheet_length_mm * settings.sheet_width_mm / 1_000_000.0
        wood_cost = sum(p.sheet_count for p in sheet_plans) * sheet_area * wood_price_m2
    else:
        wood_cost = wood_area * (1 + settings.wood_waste_pct / 100.0) * wood_price_m2

    # Perfiles: plan de barras por tipo
    profiles: List[ProfileLine] = []
    total_profile_m = 0.0
    for kind, cuts in _profile_cuts(alu_pieces).items():
        spec = catalog.profile_by_kind(kind)
        if spec is None:
            warnings.append(f"No hay perfil del tipo «{kind}» en el catálogo; no se cobra.")
            continue
        plan = optimize_bars(cuts, spec.bar_length_mm, settings.profile_kerf_mm)
        length_m = sum(c.length_mm for c in cuts) / 1000.0
        total_profile_m += length_m
        billed_m = plan.bar_count * spec.bar_length_mm / 1000.0 if settings.charge_full_bars else length_m
        for o in plan.oversize:
            warnings.append(f"El corte «{o.label}» ({o.length_mm:.0f} mm) es más largo que la barra de {spec.name}.")
        profiles.append(ProfileLine(
            kind=kind, name=spec.name, total_length_m=length_m, bars=plan.bar_count,
            bar_length_mm=spec.bar_length_mm, utilization_pct=plan.utilization_pct,
            price=billed_m * spec.price_per_m, weight_kg=length_m * spec.weight_kg_per_m, plan=plan,
        ))
    weight_profiles = sum(p.weight_kg for p in profiles)

    # Herrajes
    hardware: List[HardwareLine] = []
    rivets = 0
    for item_id, qty, where in count_hardware(outer_length, outer_width, weight_wood + weight_profiles, settings):
        item = catalog.hardware_by_id(item_id)
        if item is None:
            warnings.append(f"El herraje «{item_id}» no está en el catálogo; no se cobra.")
            continue
        rivets += qty * item.rivets_per_unit
        hardware.append(HardwareLine(item.id, item.name, item.category, qty, item.unit_price, item.weight_kg, where))
    rivets += math.ceil(total_profile_m * 1000.0 / 100.0)  # 1 remache cada 100 mm de perfil
    rivet = catalog.hardware_by_id("rivet")
    if rivet and rivets:
        hardware.append(HardwareLine(rivet.id, rivet.name, rivet.category, rivets, rivet.unit_price, rivet.weight_kg, "Perfiles y herrajes"))
    weight_hw = sum(h.total_weight_kg for h in hardware)

    # Mano de obra y totales
    outer_surface = 2 * (outer_length * outer_width + outer_length * outer_height + outer_width * outer_height) / 1_000_000.0
    labor_hours = settings.labor_hours_base + settings.labor_hours_per_m2 * outer_surface
    labor_cost = labor_hours * settings.labor_rate

    hw_cost = sum(h.total_price for h in hardware)
    prof_cost = sum(p.price for p in profiles)
    materials = wood_cost + prof_cost + hw_cost + settings.consumables
    subtotal = materials + labor_cost
    margin = subtotal * settings.margin_pct / 100.0
    net = subtotal + margin
    vat = net * settings.vat_pct / 100.0

    cost_lines = [
        CostLine("Madera", wood_cost),
        CostLine("Perfiles de aluminio", prof_cost),
        CostLine("Herrajes", hw_cost),
        CostLine("Consumibles", settings.consumables),
        CostLine(f"Mano de obra ({labor_hours:.1f} h × {settings.labor_rate:.2f} €)", labor_cost),
        CostLine("Coste total", subtotal),
        CostLine(f"Margen ({settings.margin_pct:.0f} %)", margin),
        CostLine("Precio sin IVA", net),
        CostLine(f"IVA ({settings.vat_pct:.0f} %)", vat),
        CostLine("Precio final", net + vat),
    ]

    return Quote(
        hardware=hardware, profiles=profiles, sheet_plans=sheet_plans, cost_lines=cost_lines,
        labor_hours=labor_hours, materials_cost=materials, labor_cost=labor_cost, subtotal=subtotal,
        margin=margin, net_price=net, vat=vat, total_price=net + vat,
        weight_wood_kg=weight_wood, weight_profiles_kg=weight_profiles, weight_hardware_kg=weight_hw,
        warnings=warnings,
    )
