"""Paquete de producción en un clic: hoja de montaje PDF, DXF por espesor, SVG y CSV."""

from __future__ import annotations

import os
import re
from typing import List, Optional

from ..i18n import tr
from .build_sheet import build_sheet_html, render_sheet_image, write_build_sheet_pdf
from .dxf import sheet_plan_to_dxf
from .quote import Quote


def _slug(text: str) -> str:
    text = re.sub(r"[^\w\-]+", "_", (text or "flightcase").strip(), flags=re.UNICODE)
    return text.strip("_") or "flightcase"


def full_report_csv(result, quote: Optional[Quote] = None) -> str:
    """Listado completo de materiales en CSV (madera, perfiles y, si hay presupuesto, herrajes y precio)."""
    rows: List[str] = ["=== INFORME DE CÁLCULO DEL FLIGHTCASE ===", ""]
    rows.append(f"Superficie total de madera (m2),{result.total_wood_area_m2:.4f}")
    rows.append(f"Peso estimado de la madera (kg),{result.total_wood_weight_kg:.2f}")
    if quote is not None:
        rows.append(f"Peso total estimado (kg),{quote.total_weight_kg:.2f}")
        rows.append(f"Placas necesarias (despiece real),{quote.total_sheets}")
    else:
        rows.append(f"Placas estándar (2440x1220),{result.standard_sheets_required:.2f}")
    rows.append(f"Largo necesario de perfil de cierre (mm),{result.total_lid_mating_profile_length_mm:.1f}")
    rows.append(f"Largo necesario de ángulos de borde (mm),{result.total_edge_angle_profile_length_mm:.1f}")
    rows.append("")
    rows.append("=== LISTA DE CORTES DE PANELES DE MADERA ===")
    rows.append("Panel,Categoría,Cant.,Largo_mm,Ancho_mm,Espesor_mm,SuperficieTotal_m2,Notas")
    for p in result.wood_cut_list:
        rows.append(f'"{tr(p.name)}","{tr(p.category)}",{p.quantity},{p.length_mm:.1f},{p.width_mm:.1f},'
                    f'{p.thickness_mm:.1f},{p.total_area_m2:.4f},"{tr(p.notes)}"')
    rows.append("")
    rows.append("=== LISTA DE CORTES DE PERFILES DE ALUMINIO ===")
    rows.append("Perfil,Categoría,Cant.,LargoCorte_mm,LargoTotal_m,Notas")
    for p in result.alu_profiles_list:
        rows.append(f'"{tr(p.name)}","{tr(p.category)}",{p.quantity},{p.length_mm:.1f},{p.total_length_m:.2f},"{tr(p.notes)}"')
    if quote is not None:
        rows.append("")
        rows.append("=== BARRAS DE PERFIL ===")
        rows.append("Perfil,Barras,LargoBarra_mm,MetrosUsados,Aprovechamiento_pct,Precio")
        for prof in quote.profiles:
            rows.append(f'"{prof.name}",{prof.bars},{prof.bar_length_mm:.0f},{prof.total_length_m:.2f},'
                        f'{prof.utilization_pct:.1f},{prof.price:.2f}')
        rows.append("")
        rows.append("=== HERRAJES ===")
        rows.append("Herraje,Categoría,Cant.,PrecioUnitario,Total,Ubicación")
        for h in quote.hardware:
            rows.append(f'"{h.name}","{h.category}",{h.quantity},{h.unit_price:.2f},{h.total_price:.2f},"{h.placement}"')
        rows.append("")
        rows.append("=== PRECIO ===")
        for line in quote.cost_lines:
            rows.append(f'"{line.concept}",{line.amount:.2f}')
    return "\n".join(rows) + "\n"


def write_production_pack(
    *,
    folder: str,
    title: str,
    inner_dims: tuple,
    outer_dims: tuple,
    wood_material: str,
    wood_pieces,
    result,
    quote: Quote,
    svg: str,
) -> List[str]:
    """Escribe todos los archivos de producción en ``folder`` y devuelve sus rutas."""
    base = _slug(title)
    os.makedirs(folder, exist_ok=True)
    written: List[str] = []

    # DXF por espesor
    dxf_dir = os.path.join(folder, "dxf")
    os.makedirs(dxf_dir, exist_ok=True)
    for plan in quote.sheet_plans:
        path = os.path.join(dxf_dir, f"{base}_{plan.thickness_mm:g}mm.dxf")
        with open(path, "w", encoding="utf-8") as f:
            f.write(sheet_plan_to_dxf(plan, title=title))
        written.append(path)

    # SVG y CSV
    svg_path = os.path.join(folder, f"{base}_paneles.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
    written.append(svg_path)
    csv_path = os.path.join(folder, f"{base}_listado_materiales.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(full_report_csv(result, quote))
    written.append(csv_path)

    # Hoja de montaje (taller, sin precios) y presupuesto (con precios)
    images = {}
    names: List[List[str]] = []
    for pi, plan in enumerate(quote.sheet_plans):
        names.append([])
        for si, sheet in enumerate(plan.sheets):
            name = f"placa_{pi}_{si}.png"
            images[name] = render_sheet_image(sheet)
            names[-1].append(name)
    for suffix, with_prices in (("hoja_montaje", False), ("presupuesto_interno", True)):
        html_text = build_sheet_html(
            title=title, inner_dims=inner_dims, outer_dims=outer_dims, wood_material=wood_material,
            wood_pieces=wood_pieces, quote=quote, include_prices=with_prices, sheet_image_names=names,
        )
        pdf_path = os.path.join(folder, f"{base}_{suffix}.pdf")
        write_build_sheet_pdf(pdf_path, html_text, images)
        written.append(pdf_path)
    return written
