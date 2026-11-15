"""Exportación DXF (formato R12 ASCII, sin dependencias) de los despieces de placas.

Capas:
- PLACA: contorno de cada placa.
- CORTE: contorno de cada panel (para la CNC o la sierra).
- ETIQUETAS: nombre y medidas de cada panel.
Unidades: milímetros. Las placas se dibujan una al lado de la otra con 100 mm de separación.
"""

from __future__ import annotations

from typing import List

from .optimizer import SheetPlan

SHEET_GAP_MM = 100.0


def _sanitize(text: str) -> str:
    return text.replace("\n", " ").replace("\r", " ")


class _DxfWriter:
    def __init__(self) -> None:
        self.lines: List[str] = []

    def _w(self, code: int, value) -> None:
        self.lines.append(str(code))
        self.lines.append(str(value))

    def header(self, layers: List[tuple]) -> None:
        self._w(0, "SECTION"); self._w(2, "HEADER")
        self._w(9, "$ACADVER"); self._w(1, "AC1009")
        self._w(9, "$INSUNITS"); self._w(70, 4)
        self._w(0, "ENDSEC")
        self._w(0, "SECTION"); self._w(2, "TABLES")
        self._w(0, "TABLE"); self._w(2, "LAYER"); self._w(70, len(layers))
        for name, color in layers:
            self._w(0, "LAYER"); self._w(2, name); self._w(70, 0); self._w(62, color); self._w(6, "CONTINUOUS")
        self._w(0, "ENDTAB")
        self._w(0, "ENDSEC")
        self._w(0, "SECTION"); self._w(2, "ENTITIES")

    def line(self, layer: str, x1: float, y1: float, x2: float, y2: float) -> None:
        self._w(0, "LINE"); self._w(8, layer)
        self._w(10, f"{x1:.3f}"); self._w(20, f"{y1:.3f}"); self._w(30, "0.0")
        self._w(11, f"{x2:.3f}"); self._w(21, f"{y2:.3f}"); self._w(31, "0.0")

    def rect(self, layer: str, x: float, y: float, w: float, h: float) -> None:
        self.line(layer, x, y, x + w, y)
        self.line(layer, x + w, y, x + w, y + h)
        self.line(layer, x + w, y + h, x, y + h)
        self.line(layer, x, y + h, x, y)

    def text(self, layer: str, x: float, y: float, height: float, value: str) -> None:
        self._w(0, "TEXT"); self._w(8, layer)
        self._w(10, f"{x:.3f}"); self._w(20, f"{y:.3f}"); self._w(30, "0.0")
        self._w(40, f"{height:.3f}"); self._w(1, _sanitize(value))

    def finish(self) -> str:
        self._w(0, "ENDSEC")
        self._w(0, "EOF")
        return "\n".join(self.lines) + "\n"


def sheet_plan_to_dxf(plan: SheetPlan, title: str = "") -> str:
    """Genera un DXF con todas las placas de un espesor y los paneles colocados."""
    dxf = _DxfWriter()
    dxf.header([("PLACA", 8), ("CORTE", 1), ("ETIQUETAS", 3)])
    for i, sheet in enumerate(plan.sheets):
        ox = i * (sheet.length_mm + SHEET_GAP_MM)
        dxf.rect("PLACA", ox, 0.0, sheet.length_mm, sheet.width_mm)
        caption = f"{title} - Placa {i + 1}/{plan.sheet_count} - {plan.thickness_mm:g} mm - {sheet.utilization_pct:.0f} %"
        dxf.text("ETIQUETAS", ox, sheet.width_mm + 20.0, 30.0, caption.strip(" -"))
        for p in sheet.placements:
            dxf.rect("CORTE", ox + p.x_mm, p.y_mm, p.length_mm, p.width_mm)
            h = max(8.0, min(25.0, p.width_mm / 6.0, p.length_mm / 20.0))
            dxf.text("ETIQUETAS", ox + p.x_mm + 10.0, p.y_mm + p.width_mm / 2.0 + h * 0.2, h, p.label)
            dxf.text("ETIQUETAS", ox + p.x_mm + 10.0, p.y_mm + p.width_mm / 2.0 - h * 1.4, h * 0.8,
                     f"{p.length_mm:.1f} x {p.width_mm:.1f}" + (" (girado)" if p.rotated else ""))
    return dxf.finish()
