"""Lectura de proyectos de OpenSCAD hechos con flightcase_gen (asignaciones literales).

Un proyecto es una lista de ``nombre = valor;`` con números, textos, booleanos y
listas, más ``include <...>`` y ``flightcase();``. Se leen sólo las asignaciones.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, Union

_IDENT = re.compile(r"^\s*([A-Za-z_$][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$", re.S)


def _sin_comentarios(texto: str) -> str:
    out, i, n = [], 0, len(texto)
    en_texto = False
    while i < n:
        c = texto[i]
        if en_texto:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(texto[i + 1])
                i += 2
                continue
            if c == '"':
                en_texto = False
            i += 1
            continue
        if c == '"':
            en_texto = True
            out.append(c)
            i += 1
        elif texto.startswith("//", i):
            j = texto.find("\n", i)
            i = n if j < 0 else j
        elif texto.startswith("/*", i):
            j = texto.find("*/", i + 2)
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _sentencias(texto: str) -> Iterator[str]:
    """Separa por ';' de primer nivel (fuera de textos, corchetes y llaves)."""
    nivel, en_texto, actual = 0, False, []
    i = 0
    while i < len(texto):
        c = texto[i]
        actual.append(c)
        if en_texto:
            if c == "\\" and i + 1 < len(texto):
                actual.append(texto[i + 1])
                i += 2
                continue
            if c == '"':
                en_texto = False
        elif c == '"':
            en_texto = True
        elif c in "[({":
            nivel += 1
        elif c in "])}":
            nivel -= 1
        elif c == ";" and nivel == 0:
            yield "".join(actual[:-1])
            actual = []
        i += 1
    resto = "".join(actual).strip()
    if resto:
        yield resto


def valor_literal(texto: str) -> Any:
    """Convierte un literal de OpenSCAD (número, texto, bool, lista) a Python."""
    t = texto.strip()
    t = re.sub(r",\s*\]", "]", t)
    return json.loads(t)


def leer_asignaciones(texto: str) -> Dict[str, Any]:
    """Devuelve las asignaciones literales de un archivo .scad (la última gana)."""
    valores: Dict[str, Any] = {}
    for sent in _sentencias(_sin_comentarios(texto)):
        s = sent.strip()
        if not s or s.startswith(("include", "use", "module", "function", "if", "for")):
            # una línea 'include <...>' no termina en ';': puede venir pegada a la siguiente asignación
            s = re.sub(r"^\s*(include|use)\s*<[^>]*>\s*", "", s)
            if not s:
                continue
        s = re.sub(r"^\s*(include|use)\s*<[^>]*>\s*", "", s)
        m = _IDENT.match(s)
        if not m:
            continue
        nombre, crudo = m.group(1), m.group(2)
        try:
            valores[nombre] = valor_literal(crudo)
        except ValueError:
            continue  # expresión: no se puede leer sin evaluar OpenSCAD
    return valores


def leer_proyecto(ruta: Union[str, Path]) -> Dict[str, Any]:
    return leer_asignaciones(Path(ruta).read_text(encoding="utf-8"))
