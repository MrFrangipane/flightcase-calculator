"""Las reglas del taller en Python dan lo mismo que el generador de OpenSCAD.

Los casos de tests/golden/taller se generaron con tools/generar_golden.py a partir de
los proyectos .scad del taller y de variantes que cubren más reglas.
"""

import json
from pathlib import Path

import pytest

from flightcase.taller.modelo import calcular, fmt

GOLDEN = sorted((Path(__file__).parent / "golden" / "taller").glob("*.json"))


def _filas(res):
    f = {}
    for k, v in res.info.items():
        f.setdefault("INFO", []).append([k] + list(v))
    f["PANEL"] = [[p.id, p.nombre, p.grupo, p.ancho, p.alto] for p in res.paneles]
    f["CALADO"] = [[c.panel, c.tipo, c.cx, c.cy, c.ancho, c.alto, c.radio] for c in res.calados]
    f["MARCA"] = [[m.panel, m.tipo, m.x, m.y, m.ancho, m.alto, m.texto] for m in res.marcas]
    f["PERFIL"] = [[p.nombre, p.descripcion, p.largo, p.cantidad, p.corte, p.ref] for p in res.perfiles]
    f["EXTRA"] = res.extras
    f["HERRAJE"] = [[h.nombre, h.cantidad, h.detalle, h.ref] for h in res.herrajes]
    f["PANELMAT"] = res.panelmat
    f["BANDEJA"] = res.bandejas
    f["AVISO"] = [[a] for a in res.avisos]
    return {k: [[fmt(x) if not isinstance(x, str) else x for x in fila] for fila in v] for k, v in f.items() if v}


def _igual(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a) - float(b)) <= 1e-3 * max(1.0, abs(float(b)))
    except ValueError:
        return False


@pytest.mark.parametrize("caso", GOLDEN, ids=[g.stem for g in GOLDEN])
def test_igual_que_openscad(caso):
    data = json.loads(caso.read_text(encoding="utf-8"))
    esperado = data["datos"]
    obtenido = _filas(calcular(data["params"]))
    if "INFO" in esperado:
        esperado["INFO"] = sorted(esperado["INFO"])
        obtenido["INFO"] = sorted(obtenido.get("INFO", []))
    assert sorted(obtenido) == sorted(esperado), "tipos de fila distintos"
    for tipo in esperado:
        e, o = esperado[tipo], obtenido[tipo]
        assert len(o) == len(e), f"{tipo}: {len(o)} filas en Python, {len(e)} en OpenSCAD"
        for fe, fo in zip(e, o):
            assert len(fe) == len(fo) and all(_igual(x, y) for x, y in zip(fo, fe)), f"{tipo}:\n  OpenSCAD {fe}\n  Python   {fo}"
