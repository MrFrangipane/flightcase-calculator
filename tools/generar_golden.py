#!/usr/bin/env python3
"""Genera los casos de referencia (tests/golden/taller/*.json) con OpenSCAD.

Cada caso guarda los parámetros del proyecto y la salida "datos" de flightcase_gen,
para comprobar que flightcase/taller/modelo.py calcula exactamente lo mismo.

    python tools/generar_golden.py ruta/a/flightcase-generador [--openscad /ruta/openscad]
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from flightcase.taller.scad import leer_proyecto  # noqa: E402

DESTINO = RAIZ / "tests" / "golden" / "taller"

# Variantes sobre mi_case.scad para cubrir más reglas
VARIANTES = {
    "mi_case_hibrido": {"sistema": "hibrido", "ruedas": 0, "encastres": False},
    "mi_case_bisagras_pies": {"bisagras": 3, "topes": 1, "ruedas": 0, "encastres": False, "pies": 4, "ref_pie": "08-4907"},
    "mi_case_piano_espuma": {"bisagras": 1, "ref_bisagra": "08-2605", "ref_espuma": "08-019310", "ruedas": 0, "encastres": False},
    "mi_case_catalogo_emb": {"ref_cierre": "08-17250S", "ref_manija": "08-34082", "ref_esquinero": "08-41076",
                             "ref_angulo": "08-6105", "ref_placa": "05-001", "int_alto_cuerpo": 400},
    "mi_case_laterales_cubren": {"paredes_enteras": "laterales", "extremos_cubren": True, "descuento_entre": 5,
                                 "cierres_laterales": "si", "manijas_n": 2},
    "mi_case_grande_refuerzos": {"int_ancho": 1100, "int_prof": 700, "int_alto_cuerpo": 500, "int_alto_tapa": 150,
                                 "refuerzos": 2, "manija_corte_ancho": 120, "cierres_frente_n": 3},
    "mi_case_superficie": {"ref_manija": "08-3417", "ref_cierre": "08-1600", "rueda_agujero_d": 0, "cantidad_cases": 3},
    "mi_case_vertical_2tapas": {"tapas": 2, "int_alto_tapa2": 60, "ruedas": 0, "encastres": False},
}


def openscad_datos(exe, scad, overrides):
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "datos.echo")
        cmd = [exe, "-o", out, "-D", 'parte="datos"']
        for k, v in overrides.items():
            cmd += ["-D", f"{k}={json.dumps(v)}"]
        cmd.append(str(scad))
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        texto = open(out, encoding="utf-8", errors="replace").read() if os.path.exists(out) else ""
        if not texto:
            texto = r.stdout + r.stderr
    datos = {}
    for ln in texto.splitlines():
        if "@@" not in ln:
            continue
        cuerpo = ln.split("@@", 1)[1].rstrip().rstrip('"')
        tipo, *campos = cuerpo.split("|")
        datos.setdefault(tipo, []).append(campos)
    return datos


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("carpeta")
    ap.add_argument("--openscad", default="openscad")
    a = ap.parse_args()
    base = Path(a.carpeta)
    DESTINO.mkdir(parents=True, exist_ok=True)
    casos = {f.stem: (f, {}) for f in sorted(base.glob("*.scad"))}
    for nombre, ov in VARIANTES.items():
        casos[nombre] = (base / "mi_case.scad", ov)
    for nombre, (scad, ov) in casos.items():
        params = leer_proyecto(scad)
        params.update(ov)
        datos = openscad_datos(a.openscad, scad, ov)
        (DESTINO / f"{nombre}.json").write_text(
            json.dumps({"origen": scad.name, "params": params, "datos": datos}, indent=1, ensure_ascii=False) + "\n",
            encoding="utf-8")
        print(f"{nombre}: {sum(len(v) for v in datos.values())} filas")


if __name__ == "__main__":
    main()
