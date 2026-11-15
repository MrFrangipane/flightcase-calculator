"""Optimización de corte: barras de aluminio (1D) y placas de madera (2D, guillotina)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Barras de aluminio (First Fit Decreasing)
# ---------------------------------------------------------------------------

@dataclass
class BarCut:
    label: str
    length_mm: float


@dataclass
class Bar:
    length_mm: float
    cuts: List[BarCut] = field(default_factory=list)
    kerf_mm: float = 3.0

    @property
    def used_mm(self) -> float:
        if not self.cuts:
            return 0.0
        return sum(c.length_mm for c in self.cuts) + self.kerf_mm * (len(self.cuts) - 1)

    @property
    def remaining_mm(self) -> float:
        return max(0.0, self.length_mm - self.used_mm)

    def fits(self, length_mm: float) -> bool:
        extra = self.kerf_mm if self.cuts else 0.0
        return self.used_mm + extra + length_mm <= self.length_mm + 1e-6


@dataclass
class BarPlan:
    bar_length_mm: float
    bars: List[Bar]
    oversize: List[BarCut] = field(default_factory=list)

    @property
    def bar_count(self) -> int:
        return len(self.bars)

    @property
    def waste_mm(self) -> float:
        return sum(b.remaining_mm for b in self.bars)

    @property
    def utilization_pct(self) -> float:
        total = self.bar_length_mm * len(self.bars)
        return 100.0 * (total - self.waste_mm) / total if total > 0 else 100.0


def optimize_bars(cuts: List[BarCut], bar_length_mm: float, kerf_mm: float = 3.0) -> BarPlan:
    """Reparte los cortes en barras de largo fijo con el método First Fit Decreasing.

    Un corte más largo que la barra se informa en ``oversize`` (hay que empalmar o pedir barra mayor).
    """
    bars: List[Bar] = []
    oversize: List[BarCut] = []
    for cut in sorted(cuts, key=lambda c: c.length_mm, reverse=True):
        if cut.length_mm <= 0:
            continue
        if cut.length_mm > bar_length_mm:
            oversize.append(cut)
            continue
        target = next((b for b in bars if b.fits(cut.length_mm)), None)
        if target is None:
            target = Bar(length_mm=bar_length_mm, kerf_mm=kerf_mm)
            bars.append(target)
        target.cuts.append(cut)
    return BarPlan(bar_length_mm=bar_length_mm, bars=bars, oversize=oversize)


# ---------------------------------------------------------------------------
# Placas de madera (guillotina con rectángulos libres, mejor ajuste por área)
# ---------------------------------------------------------------------------

@dataclass
class PanelPart:
    label: str
    length_mm: float
    width_mm: float


@dataclass
class Placement:
    label: str
    x_mm: float
    y_mm: float
    length_mm: float  # a lo largo del eje X de la placa
    width_mm: float   # a lo largo del eje Y de la placa
    rotated: bool = False


@dataclass
class Sheet:
    length_mm: float
    width_mm: float
    placements: List[Placement] = field(default_factory=list)
    _free: List[Tuple[float, float, float, float]] = field(default_factory=list, repr=False)

    @property
    def used_area_m2(self) -> float:
        return sum(p.length_mm * p.width_mm for p in self.placements) / 1_000_000.0

    @property
    def area_m2(self) -> float:
        return self.length_mm * self.width_mm / 1_000_000.0

    @property
    def utilization_pct(self) -> float:
        return 100.0 * self.used_area_m2 / self.area_m2 if self.area_m2 > 0 else 0.0


@dataclass
class SheetPlan:
    thickness_mm: float
    sheet_length_mm: float
    sheet_width_mm: float
    sheets: List[Sheet]
    oversize: List[PanelPart] = field(default_factory=list)

    @property
    def sheet_count(self) -> int:
        return len(self.sheets)

    @property
    def utilization_pct(self) -> float:
        total = sum(s.area_m2 for s in self.sheets)
        used = sum(s.used_area_m2 for s in self.sheets)
        return 100.0 * used / total if total > 0 else 0.0


def _try_place(sheet: Sheet, part: PanelPart, kerf: float, allow_rotation: bool):
    """Busca el rectángulo libre con mejor ajuste. Devuelve (índice, rotada) o None."""
    best = None
    best_score = None
    options = [(part.length_mm, part.width_mm, False)]
    if allow_rotation and part.length_mm != part.width_mm:
        options.append((part.width_mm, part.length_mm, True))
    for idx, (fx, fy, fw, fh) in enumerate(sheet._free):
        for pw, ph, rot in options:
            if pw <= fw + 1e-6 and ph <= fh + 1e-6:
                score = (fw * fh - pw * ph, min(fw - pw, fh - ph))
                if best_score is None or score < best_score:
                    best_score = score
                    best = (idx, pw, ph, rot)
    return best


def _place(sheet: Sheet, part: PanelPart, idx: int, pw: float, ph: float, rot: bool, kerf: float) -> None:
    fx, fy, fw, fh = sheet._free.pop(idx)
    sheet.placements.append(Placement(part.label, fx, fy, pw, ph, rot))
    # Corte de guillotina: se separa primero por el lado que deja el resto más grande.
    right_w = fw - pw - kerf
    top_h = fh - ph - kerf
    if right_w * fh >= fw * top_h:
        right = (fx + pw + kerf, fy, right_w, fh)
        top = (fx, fy + ph + kerf, pw, top_h)
    else:
        right = (fx + pw + kerf, fy, right_w, ph)
        top = (fx, fy + ph + kerf, fw, top_h)
    for r in (right, top):
        if r[2] > 1.0 and r[3] > 1.0:
            sheet._free.append(r)


def optimize_sheets(
    parts: List[PanelPart],
    thickness_mm: float,
    sheet_length_mm: float = 2440.0,
    sheet_width_mm: float = 1220.0,
    kerf_mm: float = 4.0,
    trim_mm: float = 10.0,
    allow_rotation: bool = True,
) -> SheetPlan:
    """Coloca los paneles en placas estándar con cortes de guillotina.

    ``trim_mm`` es el saneado del borde de la placa; ``kerf_mm`` el grosor de la sierra.
    """
    usable_l = sheet_length_mm - 2 * trim_mm
    usable_w = sheet_width_mm - 2 * trim_mm
    sheets: List[Sheet] = []
    oversize: List[PanelPart] = []

    ordered = sorted(parts, key=lambda p: (max(p.length_mm, p.width_mm), p.length_mm * p.width_mm), reverse=True)
    for part in ordered:
        if part.length_mm <= 0 or part.width_mm <= 0:
            continue
        fits_normal = part.length_mm <= usable_l and part.width_mm <= usable_w
        fits_rot = allow_rotation and part.width_mm <= usable_l and part.length_mm <= usable_w
        if not (fits_normal or fits_rot):
            oversize.append(part)
            continue
        placed = False
        for sheet in sheets:
            hit = _try_place(sheet, part, kerf_mm, allow_rotation)
            if hit:
                _place(sheet, part, *hit, kerf=kerf_mm)
                placed = True
                break
        if not placed:
            sheet = Sheet(sheet_length_mm, sheet_width_mm)
            sheet._free = [(trim_mm, trim_mm, usable_l, usable_w)]
            sheets.append(sheet)
            hit = _try_place(sheet, part, kerf_mm, allow_rotation)
            _place(sheet, part, *hit, kerf=kerf_mm)

    return SheetPlan(thickness_mm, sheet_length_mm, sheet_width_mm, sheets, oversize)


def expand_parts(pieces, name_fn=lambda s: s) -> Dict[float, List[PanelPart]]:
    """Convierte una lista de cortes (con cantidad) en piezas sueltas agrupadas por espesor."""
    groups: Dict[float, List[PanelPart]] = {}
    for p in pieces:
        for n in range(int(p.quantity)):
            name = name_fn(p.name)
            label = name if p.quantity == 1 else f"{name} ({n + 1}/{p.quantity})"
            groups.setdefault(round(float(p.thickness_mm), 2), []).append(
                PanelPart(label=label, length_mm=float(p.length_mm), width_mm=float(p.width_mm))
            )
    return groups
