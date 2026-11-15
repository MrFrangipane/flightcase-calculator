#!/usr/bin/env python3
"""Convierte catalogo_fr.scad (OpenSCAD) en flightcase/resources/catalogo_fr.json.

    python tools/convertir_catalogo_scad.py ruta/a/catalogo_fr.scad
"""
import json
import re
import sys
from pathlib import Path


def convertir(texto: str):
    sin_coment = re.sub(r"//[^\n]*", "", texto)
    m = re.search(r"catalogo\s*=\s*(\[.*?\n\]);", sin_coment, re.S)
    if not m:
        raise SystemExit("No encuentro 'catalogo = [...];'")
    cuerpo = re.sub(r",\s*([\]\}])", r"\1", m.group(1))  # comas finales
    filas = json.loads(cuerpo)
    return [
        {"ref": r[0], "categoria": r[1], "nombre": r[2], "datos": {k: v for k, v in r[3]}, "verificado": bool(r[4])}
        for r in filas
    ]


if __name__ == "__main__":
    origen = Path(sys.argv[1])
    destino = Path(__file__).resolve().parent.parent / "flightcase" / "resources" / "catalogo_fr.json"
    filas = convertir(origen.read_text(encoding="utf-8"))
    destino.write_text(json.dumps(filas, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(filas)} referencias -> {destino}")
