"""Traducción al español de los textos generados por el dominio.

El dominio genera nombres de piezas, notas, categorías y etiquetas 3D en inglés,
y esos textos se usan internamente (agrupación de piezas, resaltado 3D, archivos
de proyecto). Para no romper esa lógica, la traducción se aplica sólo al mostrar
o exportar los textos, mediante ``tr()``.
"""

from __future__ import annotations

import re
from typing import Callable, List, Tuple

# Lado de bisagra: valor interno (se guarda en el proyecto) -> texto visible
HINGE_SIDES: List[Tuple[str, str]] = [
    ("Back", "Trasero"),
    ("Front", "Delantero"),
    ("Left", "Izquierdo"),
    ("Right", "Derecho"),
]

_EXACT = {
    # --- Paneles de madera (lista de cortes) ---
    "Bottom Panel": "Piso",
    "Top Panel": "Techo",
    "Long Sides (Front & Back)": "Laterales largos (delantero y trasero)",
    "Short Sides (Left & Right)": "Laterales cortos (izquierdo y derecho)",
    "Base Bottom Panel": "Piso del cuerpo",
    "Base Long Sides (Front & Back)": "Laterales largos del cuerpo (delantero y trasero)",
    "Base Short Sides (Left & Right)": "Laterales cortos del cuerpo (izquierdo y derecho)",
    "Lid Top Panel": "Techo de la tapa",
    "Lid Long Sides (Front & Back)": "Laterales largos de la tapa (delantero y trasero)",
    "Lid Short Sides (Left & Right)": "Laterales cortos de la tapa (izquierdo y derecho)",
    "Top & Bottom Panels": "Piso y techo",
    "Inside Walls (Width-wise)": "Divisores (transversales)",
    "Inside Walls (Length-wise)": "Divisores (longitudinales)",
    "Inside Walls (Across Width)": "Divisores (transversales)",
    "Inside Walls (Across Length)": "Divisores (longitudinales)",
    # --- Perfiles de aluminio ---
    "Lid Hybrid Profile - Base Male (Long / Front-Back)": "Perfil de cierre - Macho del cuerpo (largo / delantero-trasero)",
    "Lid Hybrid Profile - Base Male (Short / Left-Right)": "Perfil de cierre - Macho del cuerpo (corto / izquierdo-derecho)",
    "Lid Hybrid Profile - Lid Female (Long / Front-Back)": "Perfil de cierre - Hembra de la tapa (largo / delantero-trasero)",
    "Lid Hybrid Profile - Lid Female (Short / Left-Right)": "Perfil de cierre - Hembra de la tapa (corto / izquierdo-derecho)",
    "Corner Angle - Base Vertical Corners": "Ángulo esquinero - Esquinas verticales del cuerpo",
    "Corner Angle - Lid Vertical Corners": "Ángulo esquinero - Esquinas verticales de la tapa",
    "Edge Angle - Horizontal Length (Base Bottom & Lid Top)": "Ángulo de borde - Largo horizontal (piso del cuerpo y techo de la tapa)",
    "Edge Angle - Horizontal Width (Base Bottom & Lid Top)": "Ángulo de borde - Ancho horizontal (piso del cuerpo y techo de la tapa)",
    # --- Notas ---
    "Floor panel of 6-sided uncut box": "Piso de la caja cerrada de 6 caras",
    "Roof panel of 6-sided uncut box": "Techo de la caja cerrada de 6 caras",
    "Full-height short sides inset between front and back panels": "Laterales cortos de altura completa, entre los paneles delantero y trasero",
    "Main bottom panel of base box": "Piso principal del cuerpo",
    "Inset between front and back panels": "Va entre los paneles delantero y trasero",
    "Main top panel of lid box": "Techo principal de la tapa",
    "Inset between front and back lid panels": "Va entre los paneles delantero y trasero de la tapa",
    "Floor and roof panels": "Paneles de piso y techo",
    "Front and back side panels": "Laterales delantero y trasero",
    "Left and right short side panels": "Laterales cortos izquierdo y derecho",
    "Mounted on base rim (front and back)": "Va en el borde del cuerpo (delantero y trasero)",
    "Mounted on base rim (left and right)": "Va en el borde del cuerpo (izquierdo y derecho)",
    "Mounted on lid rim (front and back)": "Va en el borde de la tapa (delantero y trasero)",
    "Mounted on lid rim (left and right)": "Va en el borde de la tapa (izquierdo y derecho)",
    "4 base vertical corner reinforcements": "4 refuerzos en las esquinas verticales del cuerpo",
    "4 lid vertical corner reinforcements": "4 refuerzos en las esquinas verticales de la tapa",
    "2 on base bottom, 2 on lid top": "2 en el piso del cuerpo, 2 en el techo de la tapa",
    # --- Categorías ---
    "Wood Panel - Base": "Madera - Cuerpo",
    "Wood Panel - Lid": "Madera - Tapa",
    "Wood Panel - Inside Wall": "Madera - Divisor",
    "Wood Panel - Divider": "Madera - Divisor",
    "Alu Profile - Lid Mating": "Aluminio - Cierre de tapa",
    "Alu Profile - Edge Protection": "Aluminio - Protección de cantos",
    # --- Etiquetas de la vista 3D ---
    "Base Front Panel": "Panel delantero del cuerpo",
    "Base Back Panel": "Panel trasero del cuerpo",
    "Base Left Panel": "Panel izquierdo del cuerpo",
    "Base Right Panel": "Panel derecho del cuerpo",
    "Lid Front Panel": "Panel delantero de la tapa",
    "Lid Back Panel": "Panel trasero de la tapa",
    "Lid Left Panel": "Panel izquierdo de la tapa",
    "Lid Right Panel": "Panel derecho de la tapa",
    "Base Top Profile (Front)": "Perfil superior del cuerpo (delantero)",
    "Base Top Profile (Back)": "Perfil superior del cuerpo (trasero)",
    "Base Top Profile (Left)": "Perfil superior del cuerpo (izquierdo)",
    "Base Top Profile (Right)": "Perfil superior del cuerpo (derecho)",
    "Lid Bottom Profile (Front)": "Perfil inferior de la tapa (delantero)",
    "Lid Bottom Profile (Back)": "Perfil inferior de la tapa (trasero)",
    "Lid Bottom Profile (Left)": "Perfil inferior de la tapa (izquierdo)",
    "Lid Bottom Profile (Right)": "Perfil inferior de la tapa (derecho)",
    "Lid Cut Line": "Línea de corte de la tapa",
    # --- Prefijos de cotas 3D ("<prefijo>: 123 mm" / "<prefijo> = 123 mm") ---
    "Base": "Cuerpo",
    "Lid": "Tapa",
    "Long Side (Front)": "Lateral largo (delantero)",
    "Long Side (Back)": "Lateral largo (trasero)",
    "Short Side (Left)": "Lateral corto (izquierdo)",
    "Short Side (Right)": "Lateral corto (derecho)",
    "Base Front": "Lateral delantero del cuerpo",
    "Base Back": "Lateral trasero del cuerpo",
    "Base Left": "Lateral izquierdo del cuerpo",
    "Base Right": "Lateral derecho del cuerpo",
    "Lid Top": "Techo de la tapa",
    "Lid Front": "Lateral delantero de la tapa",
    "Lid Back": "Lateral trasero de la tapa",
    "Lid Left": "Lateral izquierdo de la tapa",
    "Lid Right": "Lateral derecho de la tapa",
    # --- Lado de bisagra ---
    **dict(HINGE_SIDES),
}

_NUM = r"(-?[\d.,]+)"

_PATTERNS: List[Tuple[re.Pattern, Callable[[re.Match], str]]] = [
    (re.compile(r"^Inside Walls \((\d+) pcs, (?:Width-wise|Across Width)\)$"),
     lambda m: f"Divisores ({m[1]} u., transversales)"),
    (re.compile(r"^Inside Walls \((\d+) pcs, (?:Length-wise|Across Length)\)$"),
     lambda m: f"Divisores ({m[1]} u., longitudinales)"),
    (re.compile(r"^Inside Walls \((\d+) pcs\)$"),
     lambda m: f"Divisores ({m[1]} u.)"),
    (re.compile(r"^Width Wall #(\d+)$"), lambda m: f"Divisor transversal #{m[1]}"),
    (re.compile(r"^Length Wall #(\d+)$"), lambda m: f"Divisor longitudinal #{m[1]}"),
    (re.compile(r"^(?:Inside Wall|Wall|Divider) #(\d+)$"), lambda m: f"Divisor #{m[1]}"),
    (re.compile(r"^Wall (\d+)$"), lambda m: f"Divisor {m[1]}"),
    (re.compile(r"^Compartment (\d+) \(Sec (\d+),(\d+)\)$"),
     lambda m: f"Compartimento {m[1]} (sec. {m[2]},{m[3]})"),
    (re.compile(r"^Compartment (\d+)$"), lambda m: f"Compartimento {m[1]}"),
    (re.compile(rf"^Full-height long sides to be cut open by user \(height adjusted for lid profile: {_NUM}mm\)$"),
     lambda m: f"Laterales largos de altura completa, para cortar la tapa a mano (altura ajustada por el perfil de tapa: {m[1]}mm)"),
    (re.compile(rf"^Height adjusted for (?:lid|alu) profile \({_NUM}mm\)$"),
     lambda m: f"Altura ajustada por el perfil de tapa ({m[1]}mm)"),
    (re.compile(rf"^Positioned along length at {_NUM}mm$"), lambda m: f"Ubicado a {m[1]}mm a lo largo"),
    (re.compile(rf"^Positioned along width at {_NUM}mm$"), lambda m: f"Ubicado a {m[1]}mm a lo ancho"),
    (re.compile(rf"^Width-wise partition at pos {_NUM}mm$"), lambda m: f"Divisor transversal en {m[1]}mm"),
    (re.compile(rf"^Length-wise partition at pos {_NUM}mm$"), lambda m: f"Divisor longitudinal en {m[1]}mm"),
]

_SUFFIXES = [
    (" (Width-wise)", " (transversal)"),
    (" (Length-wise)", " (longitudinal)"),
    (" (Across Width)", " (transversal)"),
    (" (Across Length)", " (longitudinal)"),
]


def tr(text: str) -> str:
    """Traduce al español un texto generado por el dominio; si no lo conoce, lo devuelve igual."""
    if not text:
        return text
    if text in _EXACT:
        return _EXACT[text]
    for pattern, repl in _PATTERNS:
        m = pattern.match(text)
        if m:
            return repl(m)
    # Textos compuestos (piezas agrupadas, notas unidas)
    for sep in (" • ", " / "):
        if sep in text:
            return sep.join(tr(part) for part in text.split(sep))
    for suffix, es in _SUFFIXES:
        if text.endswith(suffix):
            return tr(text[: -len(suffix)]) + es
    # Cotas 3D: "Piso: 800 mm", "Cuerpo = 300 mm"
    for sep in (": ", " = "):
        if sep in text:
            head, rest = text.split(sep, 1)
            translated = tr(head)
            if translated != head:
                return f"{translated}{sep}{rest}"
    return text
