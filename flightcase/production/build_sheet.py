"""Hoja de montaje (HTML) y su conversión a PDF con Qt."""

from __future__ import annotations

import html
from datetime import date
from typing import List, Optional

from ..i18n import tr
from .quote import Quote


def _e(text) -> str:
    return html.escape(str(text))


def _eur(value: float) -> str:
    return f"{value:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def build_sheet_html(
    *,
    title: str,
    inner_dims: tuple,
    outer_dims: tuple,
    wood_material: str,
    wood_pieces,
    quote: Quote,
    include_prices: bool = True,
    sheet_image_names: Optional[List[List[str]]] = None,
) -> str:
    """HTML de la hoja de montaje: medidas, cortes, perfiles, herrajes, placas y precio."""
    il, iw, ih = inner_dims
    ol, ow, oh = outer_dims
    out: List[str] = []
    out.append("<html><head><meta charset='utf-8'><style>"
               "body{font-family:sans-serif;font-size:9pt;color:#111}"
               "h1{font-size:16pt;margin:0}h2{font-size:12pt;margin-top:14px;border-bottom:1px solid #999}"
               "table{border-collapse:collapse;width:100%}th,td{border:1px solid #bbb;padding:3px 5px}"
               "th{background:#e8e8e8;text-align:left}td.n{text-align:right}.warn{color:#a00}"
               "</style></head><body>")
    out.append(f"<h1>Hoja de montaje: {_e(title or 'Flightcase sin título')}</h1>")
    out.append(f"<p>Fecha: {date.today().strftime('%d/%m/%Y')} &nbsp;·&nbsp; Material: {_e(tr(wood_material))}</p>")
    out.append("<table><tr><th></th><th>Largo</th><th>Ancho</th><th>Alto</th></tr>"
               f"<tr><td>Interior (mm)</td><td class='n'>{il:.0f}</td><td class='n'>{iw:.0f}</td><td class='n'>{ih:.0f}</td></tr>"
               f"<tr><td>Exterior (mm)</td><td class='n'>{ol:.0f}</td><td class='n'>{ow:.0f}</td><td class='n'>{oh:.0f}</td></tr>"
               "</table>")
    out.append(f"<p>Peso estimado: <b>{quote.total_weight_kg:.1f} kg</b> "
               f"(madera {quote.weight_wood_kg:.1f}, perfiles {quote.weight_profiles_kg:.1f}, herrajes {quote.weight_hardware_kg:.1f}) "
               f"&nbsp;·&nbsp; Mano de obra estimada: {quote.labor_hours:.1f} h</p>")

    for w in quote.warnings:
        out.append(f"<p class='warn'>⚠ {_e(w)}</p>")

    out.append("<h2>1. Cortes de madera</h2><table><tr><th>Panel</th><th>Cant.</th><th>Largo (mm)</th>"
               "<th>Ancho (mm)</th><th>Espesor (mm)</th><th>Notas</th></tr>")
    for p in wood_pieces:
        out.append(f"<tr><td>{_e(tr(p.name))}</td><td class='n'>{p.quantity}</td><td class='n'>{p.length_mm:.1f}</td>"
                   f"<td class='n'>{p.width_mm:.1f}</td><td class='n'>{p.thickness_mm:g}</td><td>{_e(tr(p.notes))}</td></tr>")
    out.append("</table>")

    out.append("<h2>2. Despiece en placas</h2>")
    for pi, plan in enumerate(quote.sheet_plans):
        out.append(f"<p><b>Espesor {plan.thickness_mm:g} mm:</b> {plan.sheet_count} placa(s) de "
                   f"{plan.sheet_length_mm:.0f}×{plan.sheet_width_mm:.0f} mm, aprovechamiento {plan.utilization_pct:.0f} %</p>")
        for si, sheet in enumerate(plan.sheets):
            out.append(f"<p>Placa {si + 1}: " + ", ".join(
                f"<b>[{n}]</b> {_e(p.label)} {p.length_mm:.0f}×{p.width_mm:.0f}"
                for n, p in enumerate(sheet.placements, start=1)) + "</p>")
            if sheet_image_names and pi < len(sheet_image_names) and si < len(sheet_image_names[pi]):
                out.append(f"<p><img src='{sheet_image_names[pi][si]}' width='640'></p>")

    out.append("<h2>3. Perfiles de aluminio</h2>")
    for prof in quote.profiles:
        out.append(f"<p><b>{_e(prof.name)}:</b> {prof.total_length_m:.2f} m en {prof.bars} barra(s) de "
                   f"{prof.bar_length_mm / 1000:.1f} m (aprovechamiento {prof.utilization_pct:.0f} %)</p><table>"
                   "<tr><th>Barra</th><th>Cortes (mm)</th><th>Sobrante (mm)</th></tr>")
        for bi, bar in enumerate(prof.plan.bars):
            cuts = " + ".join(f"{c.length_mm:.1f}" for c in bar.cuts)
            out.append(f"<tr><td>{bi + 1}</td><td>{cuts}</td><td class='n'>{bar.remaining_mm:.0f}</td></tr>")
        out.append("</table>")

    out.append("<h2>4. Herrajes</h2><table><tr><th>Herraje</th><th>Cant.</th><th>Ubicación</th>")
    if include_prices:
        out.append("<th>Precio u.</th><th>Total</th>")
    out.append("</tr>")
    for h in quote.hardware:
        out.append(f"<tr><td>{_e(h.name)}</td><td class='n'>{h.quantity}</td><td>{_e(h.placement)}</td>")
        if include_prices:
            out.append(f"<td class='n'>{_eur(h.unit_price)}</td><td class='n'>{_eur(h.total_price)}</td>")
        out.append("</tr>")
    out.append("</table>")

    if include_prices:
        out.append("<h2>5. Precio</h2><table>")
        for line in quote.cost_lines:
            bold = line.concept in ("Coste total", "Precio sin IVA", "Precio final")
            c = f"<b>{_e(line.concept)}</b>" if bold else _e(line.concept)
            v = f"<b>{_eur(line.amount)}</b>" if bold else _eur(line.amount)
            out.append(f"<tr><td>{c}</td><td class='n'>{v}</td></tr>")
        out.append("</table>")

    out.append("</body></html>")
    return "".join(out)


def render_sheet_image(sheet, width_px: int = 1280):
    """Dibuja una placa con sus paneles en un QImage (requiere QGuiApplication)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen

    scale = width_px / sheet.length_mm
    height_px = int(sheet.width_mm * scale) + 2
    img = QImage(width_px + 2, height_px, QImage.Format_RGB32)
    img.fill(QColor("white"))
    painter = QPainter(img)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(QPen(QColor("#555"), 2))
    painter.setBrush(QColor("#f1e3c8"))
    painter.drawRect(QRectF(1, 1, sheet.length_mm * scale, sheet.width_mm * scale))
    font = QFont("Sans")
    for n, p in enumerate(sheet.placements, start=1):
        r = QRectF(1 + p.x_mm * scale, 1 + p.y_mm * scale, p.length_mm * scale, p.width_mm * scale)
        painter.setPen(QPen(QColor("#1d4ed8"), 2))
        painter.setBrush(QColor("#dbeafe"))
        painter.drawRect(r)
        font.setPixelSize(max(10, min(22, int(min(r.height(), r.width()) / 3))))
        painter.setFont(font)
        painter.setPen(QColor("#111"))
        text = f"[{n}]\n{p.length_mm:.0f} × {p.width_mm:.0f}" if min(r.width(), r.height()) > 60 else str(n)
        painter.drawText(r.adjusted(2, 2, -2, -2), Qt.AlignCenter | Qt.TextWordWrap, text)
    painter.end()
    return img


def write_build_sheet_pdf(file_path: str, html_text: str, sheet_images=None) -> None:
    """Convierte el HTML de la hoja de montaje en PDF A4 con QTextDocument."""
    from PySide6.QtCore import QMarginsF, QUrl
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    writer = QPdfWriter(file_path)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(12, 12, 12, 12), QPageLayout.Millimeter))
    writer.setResolution(150)
    doc = QTextDocument()
    for name, image in (sheet_images or {}).items():
        doc.addResource(QTextDocument.ImageResource, QUrl(name), image)
    doc.setHtml(html_text)
    doc.setPageSize(writer.pageLayout().paintRectPixels(writer.resolution()).size())
    doc.print_(writer)
