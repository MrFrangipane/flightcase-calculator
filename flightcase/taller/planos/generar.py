#!/usr/bin/env python3
"""
generar.py — arma todo lo que hace falta para fabricar un flightcase
a partir de un proyecto de OpenSCAD hecho con flightcase_gen.

    python generar.py mi_case.scad
    python generar.py mi_case.scad --salida salida_case_mixer --sin-rotar

Genera en la carpeta de salida:
    planos.pdf          planos acotados de cada panel, aprovechamiento de
                        placas, lista de cortes de perfiles y materiales
    dxf/*.dxf           un DXF por pieza distinta, para CNC o plotear 1:1
    lista_cortes.csv    paneles y tramos de perfil
    materiales.csv      placas, barras y herrajes
    modelo.stl          modelo 3D completo (con --stl)
    render.png          vista 3D (si OpenSCAD puede renderizar)

Requiere OpenSCAD (2021.01 o más nuevo) y Python 3.8+ con matplotlib.
"""
import argparse
import textwrap
import csv
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import OrderedDict, defaultdict

# ----------------------------------------------------------------------
# OpenSCAD
# ----------------------------------------------------------------------
RUTAS_OPENSCAD = [
    r"C:\Program Files\OpenSCAD\openscad.exe",
    r"C:\Program Files (x86)\OpenSCAD\openscad.exe",
    "/Applications/OpenSCAD.app/Contents/MacOS/OpenSCAD",
]


def buscar_openscad(explicito=None):
    for cand in [explicito, os.environ.get("OPENSCAD"), shutil.which("openscad")] + RUTAS_OPENSCAD:
        if cand and os.path.isfile(cand):
            return cand
    sys.exit("No encuentro OpenSCAD. Instalalo o pasá la ruta con --openscad.")


def correr_openscad(exe, scad, salida, defs, pantalla_virtual=False, extra=()):
    cmd = [exe, "-o", salida] + list(extra)
    for k, v in defs.items():
        crudo = not isinstance(v, str) or v.startswith("[")   # listas van sin comillas
        cmd += ["-D", f"{k}={v}" if crudo else f'{k}="{v}"']
    cmd.append(scad)
    if pantalla_virtual and platform.system() == "Linux" and not os.environ.get("DISPLAY") \
            and shutil.which("xvfb-run"):
        cmd = ["xvfb-run", "-a"] + cmd
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode, r.stdout + r.stderr


def leer_datos(exe, scad):
    with tempfile.TemporaryDirectory() as tmp:
        echo = os.path.join(tmp, "datos.echo")
        rc, log = correr_openscad(exe, scad, echo, {"parte": "datos"})
        if rc != 0 or not os.path.exists(echo):
            sys.exit("OpenSCAD falló al leer el proyecto:\n" + log)
        with open(echo, encoding="utf-8", errors="replace") as f:
            lineas = f.read().splitlines()
    d = parsear_datos(lineas)
    if not d["paneles"]:
        sys.exit("El proyecto no devolvió paneles. ¿Llama a flightcase() al final?")
    return d


def parsear_datos(lineas):
    """Convierte las líneas @@TIPO|... del modo "datos" en el diccionario d."""
    d = {"info": {}, "extras": [], "panelmat": {}, "bandejas": {}, "paneles": OrderedDict(), "calados": defaultdict(list),
         "marcas": defaultdict(list), "perfiles": [], "herrajes": [], "avisos": []}
    for ln in lineas:
        if "@@" not in ln:
            continue
        cuerpo = ln.split("@@", 1)[1].rstrip('"')
        c = cuerpo.split("|")
        tipo, resto = c[0], c[1:]
        if tipo == "INFO":
            d["info"][resto[0]] = resto[1:] if len(resto) > 2 else resto[1]
        elif tipo == "PANEL":
            d["paneles"][resto[0]] = dict(id=resto[0], nombre=resto[1], grupo=resto[2],
                                          w=float(resto[3]), h=float(resto[4]))
        elif tipo == "CALADO":
            d["calados"][resto[0]].append(dict(tipo=resto[1], cx=float(resto[2]), cy=float(resto[3]),
                                               w=float(resto[4]), h=float(resto[5]), r=float(resto[6])))
        elif tipo == "MARCA":
            d["marcas"][resto[0]].append(dict(tipo=resto[1], x=float(resto[2]), y=float(resto[3]),
                                              w=float(resto[4]), h=float(resto[5]), texto=resto[6]))
        elif tipo == "PERFIL":
            d["perfiles"].append(dict(perfil=resto[0], desc=resto[1], largo=float(resto[2]),
                                      cant=int(float(resto[3])), corte=resto[4],
                                      ref=resto[5] if len(resto) > 5 else ""))
        elif tipo == "HERRAJE":
            d["herrajes"].append(dict(nombre=resto[0], cant=int(float(resto[1])), nota=resto[2],
                                      ref=resto[3] if len(resto) > 3 else ""))
        elif tipo == "BANDEJA":
            d["bandejas"][resto[0]] = dict(altura=float(resto[1]), soportes=int(float(resto[2])))
        elif tipo == "PANELMAT":
            d["panelmat"][resto[0]] = dict(material=resto[1], esp=float(resto[2]))
        elif tipo == "EXTRA":
            d["extras"].append(dict(nombre=resto[0], w=float(resto[1]), h=float(resto[2]),
                                    esp=float(resto[3]), cant=int(float(resto[4])), material=resto[5]))
        elif tipo == "AVISO":
            d["avisos"].append("|".join(resto))
    # perfil de cierre híbrido: macho y hembra son el mismo perfil, se suman los tramos iguales
    juntos = {}
    for p in d["perfiles"]:
        k = (p["perfil"], p["desc"], p["largo"], p["corte"])
        if k in juntos:
            juntos[k]["cant"] += p["cant"]
        else:
            juntos[k] = dict(p)
    d["perfiles"] = list(juntos.values())
    return d


# ----------------------------------------------------------------------
# Agrupar paneles idénticos
# ----------------------------------------------------------------------
def agrupar_piezas(d):
    """Agrupa paneles iguales. Un panel que coincide con otro dado vuelta o girado
    180° (izquierdo/derecho, tapa de un lado y del otro) es la misma pieza."""
    grupos = OrderedDict()

    def firma(p, pid, fx, fy):
        w, h = p["w"], p["h"]
        X = (lambda x: round(w - x if fx else x, 2))
        Y = (lambda y: round(h - y if fy else y, 2))
        return (round(w, 2), round(h, 2),
                tuple(sorted((c["tipo"], X(c["cx"]), Y(c["cy"]), c["w"], c["h"])
                             for c in d["calados"].get(pid, []))),
                tuple(sorted((m["tipo"], X(m["x"]), Y(m["y"]))
                             for m in d["marcas"].get(pid, []))))

    for pid, p in d["paneles"].items():
        mat = d["panelmat"].get(pid)
        variantes = [firma(p, pid, fx, fy) + ((mat["material"], mat["esp"]) if mat else ())
                     for fx in (False, True) for fy in (False, True)]
        existente = next((v for v in variantes if v in grupos), None)
        if existente is None:
            grupos[variantes[0]] = dict(ids=[], panel=p, calados=d["calados"].get(pid, []),
                                        marcas=d["marcas"].get(pid, []), espejo=False)
            if mat:
                grupos[variantes[0]].update(material=mat["material"], esp=mat["esp"])
            existente = variantes[0]
        elif existente != variantes[0]:
            grupos[existente]["espejo"] = True
        grupos[existente]["ids"].append(pid)
    piezas = []
    for i, g in enumerate(grupos.values(), 1):
        nombres = [d["paneles"][x]["nombre"] for x in g["ids"]]
        g.update(num=i, cant=len(g["ids"]), nombre=" / ".join(nombres),
                 w=g["panel"]["w"], h=g["panel"]["h"])
        piezas.append(g)
    return piezas


# ----------------------------------------------------------------------
# Aprovechamiento de placas (MaxRects, mejor ajuste de lado corto)
# ----------------------------------------------------------------------
def acomodar_placas(piezas_sueltas, largo, ancho, kerf, margen, rotar=True):
    W = largo - 2 * margen + kerf
    H = ancho - 2 * margen + kerf
    pend = sorted(piezas_sueltas, key=lambda p: p["w"] * p["h"], reverse=True)
    placas = []

    def entra(p, w, h):
        return w <= W and h <= H

    for p in pend:
        pw, ph = p["w"] + kerf, p["h"] + kerf
        if not (entra(p, pw, ph) or (rotar and entra(p, ph, pw))):
            p["no_entra"] = True
            continue
        mejor = None
        for pi, pl in enumerate(placas):
            for fr in pl["libres"]:
                for rot, (w, h) in ((False, (pw, ph)), (True, (ph, pw))):
                    if rot and not rotar:
                        continue
                    if w <= fr[2] + 1e-6 and h <= fr[3] + 1e-6:
                        corto = min(fr[2] - w, fr[3] - h)
                        if mejor is None or corto < mejor[0]:
                            mejor = (corto, pi, fr, rot, w, h)
        if mejor is None:
            placas.append(dict(libres=[(0.0, 0.0, W, H)], piezas=[]))
            fr = (0.0, 0.0, W, H)
            rot = not (pw <= W and ph <= H)
            w, h = (ph, pw) if rot else (pw, ph)
            mejor = (0, len(placas) - 1, fr, rot, w, h)
        _, pi, fr, rot, w, h = mejor
        pl = placas[pi]
        x, y = fr[0], fr[1]
        pl["piezas"].append(dict(p, x=x + margen, y=y + margen, rot=rot,
                                 dw=(p["h"] if rot else p["w"]), dh=(p["w"] if rot else p["h"])))
        # partir rectángulos libres
        nuevos = []
        for f in pl["libres"]:
            fx, fy, fw, fh = f
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                nuevos.append(f)
                continue
            if x > fx:
                nuevos.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                nuevos.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                nuevos.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                nuevos.append((fx, y + h, fw, fy + fh - y - h))
        # descartar contenidos
        limpios = []
        for i, a in enumerate(nuevos):
            contenido = False
            for j, b in enumerate(nuevos):
                if i != j and a[0] >= b[0] and a[1] >= b[1] and \
                        a[0] + a[2] <= b[0] + b[2] and a[1] + a[3] <= b[1] + b[3] and \
                        (a != b or i > j):
                    contenido = True
                    break
            if not contenido and a[2] > 1 and a[3] > 1:
                limpios.append(a)
        pl["libres"] = limpios
    no_entran = [p for p in pend if p.get("no_entra")]
    return placas, no_entran


# ----------------------------------------------------------------------
# Corte de barras (primer ajuste decreciente)
# ----------------------------------------------------------------------
def cortar_barras(perfiles, barra, kerf, despunte=20):
    por_tipo = OrderedDict()
    for p in perfiles:
        for _ in range(p["cant"]):
            por_tipo.setdefault(p["perfil"], []).append(p)
    resultado = OrderedDict()
    util = barra - despunte
    for tipo, tramos in por_tipo.items():
        barras = []
        for t in sorted(tramos, key=lambda t: t["largo"], reverse=True):
            usa = t["largo"] + kerf
            for b in barras:
                if b["usado"] + usa <= util + kerf:
                    b["tramos"].append(t)
                    b["usado"] += usa
                    break
            else:
                barras.append(dict(tramos=[t], usado=usa))
        resultado[tipo] = barras
    return resultado


# ----------------------------------------------------------------------
# PDF
# ----------------------------------------------------------------------
def agregar_rebajes_dxf(ruta, rebajes):
    """Agrega los rebajes (no pasantes) como rectángulos en la capa REBAJE."""
    txt = open(ruta).read()
    lineas = []
    for c in rebajes:
        x0, y0, x1, y1 = c["cx"] - c["w"] / 2, c["cy"] - c["h"] / 2, c["cx"] + c["w"] / 2, c["cy"] + c["h"] / 2
        for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            lineas.append(f"  0\nLINE\n  8\nREBAJE\n 10\n{a[0]:g}\n 20\n{a[1]:g}\n 11\n{b[0]:g}\n 21\n{b[1]:g}\n")
    i = txt.index("ENTITIES\n") + len("ENTITIES\n")
    open(ruta, "w").write(txt[:i] + "".join(lineas) + txt[i:])


def paneles_entre(d):
    """{id_panel: [ids entre los que entra]} para las paredes que van entre otras
    (cortadas descuento_entre más cortas). Vacío con perfil híbrido o sin descuento."""
    de = float(d["info"].get("descuento", ["0"])[0])
    if de <= 0:
        return {}, 0
    ext_x = float(d["info"]["exterior"][0])
    pan = d["paneles"]
    entre = {}
    for pre in ("cuerpo", "tapa", "tapa2"):
        fr, tr, iz, de_ = (f"{pre}_frente", f"{pre}_trasera", f"{pre}_izq", f"{pre}_der")
        if fr not in pan or iz not in pan:
            continue
        frente_entero = abs(pan[fr]["w"] - ext_x) < 0.01
        enteros, medios = ((fr, tr), (iz, de_)) if frente_entero else ((iz, de_), (fr, tr))
        for m in medios:
            if m in pan:
                entre[m] = [e for e in enteros if e in pan]
    for extra in ("acceso_izq", "acceso_der"):
        if extra in pan and "cuerpo_izq" in entre:
            entre[extra] = entre["cuerpo_izq"]
    return entre, de


def generar_pdf(ruta, d, piezas, placas, barras, render_png, apilado_png=None, explotado_png=None,
                vistas_extra=()):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import patches
    from matplotlib.backends.backend_pdf import PdfPages

    A4 = (11.69, 8.27)
    info = d["info"]
    ext = [float(x) for x in info["exterior"]]
    inte = [float(x) for x in info["interior"]]
    tipo_i = info.get("tipo", ["1", "vertical", "0", str(ext[2]), str(ext[3])])
    dos_tapas, horizontal = tipo_i[0] == "2", tipo_i[1] == "horizontal"
    frontal = tipo_i[1] == "frontal"
    mundo = [float(x) for x in info.get("mundo", [ext[0], ext[1], ext[2] + ext[3]])]
    if dos_tapas:
        tramos = [float(tipo_i[4]), float(tipo_i[3]), float(tipo_i[2])]
    else:
        tramos = [float(tipo_i[3]), float(tipo_i[4])]
    tipo_txt = ("Dos tapas (una en cada extremo)" if dos_tapas else "Cuerpo con tapa") + \
        (", acostado (tapas a los costados)" if horizontal else
         (", parado con tapas adelante y atrás" if frontal else ""))
    material = info["material"]
    esp = float(info["espesor"])
    from matplotlib.colors import to_rgba

    def color_seguro(c, defecto="#f3e3c3"):
        try:
            return to_rgba(c)
        except ValueError:
            return to_rgba(defecto)

    colores_case = info.get("color", ["BurlyWood", "BurlyWood"])
    color_cuerpo = color_seguro(colores_case[0])
    color_tapa = color_seguro(colores_case[1])
    COTA = "#1f4e9c"
    MARCA = "#c0392b"

    def fmt(v):
        return f"{v:.1f}".rstrip("0").rstrip(".")

    def cota_h(ax, x1, x2, y, y_ref, txt=None, col=COTA):
        ax.plot([x1, x1], [y_ref, y], color=col, lw=0.5)
        ax.plot([x2, x2], [y_ref, y], color=col, lw=0.5)
        ax.annotate("", xy=(x1, y), xytext=(x2, y),
                    arrowprops=dict(arrowstyle="<|-|>", color=col, lw=0.8, shrinkA=0, shrinkB=0,
                                    mutation_scale=8))
        ax.text((x1 + x2) / 2, y, txt or fmt(abs(x2 - x1)), ha="center", va="bottom",
                fontsize=9, color=col, bbox=dict(fc="white", ec="none", pad=0.5))

    def cota_v(ax, y1, y2, x, x_ref, txt=None, col=COTA):
        ax.plot([x_ref, x], [y1, y1], color=col, lw=0.5)
        ax.plot([x_ref, x], [y2, y2], color=col, lw=0.5)
        ax.annotate("", xy=(x, y1), xytext=(x, y2),
                    arrowprops=dict(arrowstyle="<|-|>", color=col, lw=0.8, shrinkA=0, shrinkB=0,
                                    mutation_scale=8))
        ax.text(x, (y1 + y2) / 2, txt or fmt(abs(y2 - y1)), ha="center", va="center",
                fontsize=9, color=col, rotation=90, bbox=dict(fc="white", ec="none", pad=0.5))

    def pie(fig, titulo, pagina):
        fig.text(0.03, 0.965, titulo, fontsize=15, weight="bold", va="top")
        fig.text(0.97, 0.965,
                 f"Flightcase {fmt(mundo[0])} x {fmt(mundo[1])} x {fmt(mundo[2])} mm (ext.)",
                 fontsize=9, ha="right", va="top", color="#555")
        fig.text(0.97, 0.02, f"Hoja {pagina}", fontsize=8, ha="right", color="#777")
        fig.text(0.03, 0.02, "Medidas en mm. No medir sobre el papel: usar las cotas o el DXF.",
                 fontsize=8, color="#777")

    pdf = PdfPages(ruta)
    pag = 1

    # ---- Portada ----
    fig = plt.figure(figsize=A4)
    pie(fig, "Resumen", pag)
    lineas = [
        ("Sistema", "Ángulo de aluminio" if info["sistema"] == "angulo" else "Perfil híbrido"),
        ("Placa", material),
        ("Color", colores_case[0] if colores_case[0] == colores_case[1]
         else f"cuerpo {colores_case[0]}, tapa {colores_case[1]}"),
        ("Tipo", tipo_txt),
        ("Cantidad de cases", f"{cantidad_cases(d)} (cortes, placas y materiales para el total)"
         if cantidad_cases(d) > 1 else "1"),
        ("Exterior (ancho x prof. x alto)" if not horizontal else "Exterior (largo x prof. x alto)",
         f"{fmt(mundo[0])} x {fmt(mundo[1])} x {fmt(mundo[2])} mm"),
        ("Prof. tapa del. / cuerpo / tapa tras." if frontal else
         (("Largos tapa / cuerpo / tapa" if dos_tapas else "Alto cuerpo / tapa") if not horizontal
          else ("Largos tapa izq. / cuerpo / tapa der." if dos_tapas else "Largos cuerpo / tapa")),
         " / ".join(fmt(x) for x in tramos) + " mm (exteriores, sin esquineros)"),
        ("Paneles", f"{sum(p['cant'] for p in piezas)} piezas, {len(piezas)} distintas"),
    ]
    ruedas_info = info.get("ruedas", ["0", "0"])
    if ruedas_info[0] == "4":
        lineas.insert(7, ("Alto total con ruedas",
                          f"{fmt(mundo[2] + float(ruedas_info[1]))} mm "
                          f"(ruedas de {fmt(float(ruedas_info[1]))} mm)"))
    esp_espuma = float(info.get("espuma", "0"))
    if esp_espuma > 0:
        lineas.insert(4, ("Espuma interior",
                          f"{fmt(esp_espuma)} mm (el interior indicado es el espacio útil)"))
    lineas += [
        ("Placas", "; ".join(f"{n} de {m}" for m, n in contar_placas(placas).items())),
    ]
    for tipo, bs in barras.items():
        lineas.append((tipo, f"{len(bs)} barra(s) de {info['barra'][0]} mm"))
    y = 0.86
    for k, v in lineas:
        # el valor se parte en renglones para no pisar la vista 3D de la derecha
        fig.text(0.05, y, k, fontsize=11, color="#555")
        for i_ln, ln in enumerate(textwrap.wrap(v, 40) or [""]):
            if i_ln:
                y -= 0.028
            fig.text(0.28, y, ln, fontsize=11, weight="bold")
        y -= 0.038
    if d["avisos"]:
        y -= 0.02
        fig.text(0.05, y, "Avisos", fontsize=12, weight="bold", color=MARCA)
        y -= 0.01
        for a in d["avisos"]:
            for k, ln in enumerate(textwrap.wrap(a, 95)):
                y -= 0.024
                fig.text(0.05, y, ("• " if k == 0 else "   ") + ln, fontsize=8.5, color=MARCA)
            y -= 0.006
    fig.text(0.05, min(y - 0.06, 0.1),
             "Antes de cortar, medí tus perfiles, esquineros y herrajes reales y ajustá los\n"
             "descuentos en el .scad. Las medidas de este documento dependen de esos valores.",
             fontsize=9, color="#555")
    if render_png and os.path.exists(render_png):
        img = plt.imread(render_png)
        ax = fig.add_axes([0.62, 0.12, 0.36, 0.66])
        ax.imshow(img)
        ax.axis("off")
    pdf.savefig(fig)
    plt.close(fig)
    pag += 1

    # ---- Perspectiva explotada ----
    if explotado_png and os.path.exists(explotado_png):
        fig = plt.figure(figsize=A4)
        pie(fig, "Perspectiva explotada", pag)
        ax = fig.add_axes([0.05, 0.08, 0.9, 0.84])
        ax.imshow(plt.imread(explotado_png))
        ax.axis("off")
        fig.text(0.05, 0.05, "Los rótulos P1, P2... coinciden con las hojas de cada pieza y con los "
                             "nombres de los DXF. Colores neutros para distinguir los paneles.",
                 fontsize=9, color="#333")
        pdf.savefig(fig)
        plt.close(fig)
        pag += 1

    # ---- Vistas extra (cubierta removible, etc.) ----
    for titulo_v, png_v, texto_v in vistas_extra:
        if png_v and os.path.exists(png_v):
            fig = plt.figure(figsize=A4)
            pie(fig, titulo_v, pag)
            lns_v = textwrap.wrap(texto_v, 165)
            extra_v = max(0, len(lns_v) - 2) * 0.025   # texto largo: se achica la imagen para que no pise el pie
            ax = fig.add_axes([0.05, 0.1 + extra_v, 0.9, 0.82 - extra_v])
            ax.imshow(plt.imread(png_v))
            ax.axis("off")
            fig.text(0.05, 0.095 + extra_v, "\n".join(lns_v), fontsize=9, color="#333", va="top",
                     linespacing=1.4)
            pdf.savefig(fig)
            plt.close(fig)
            pag += 1

    # ---- Apilado ----
    if apilado_png and os.path.exists(apilado_png):
        fig = plt.figure(figsize=A4)
        pie(fig, "Apilado: ruedas sobre los platos del techo", pag)
        ax = fig.add_axes([0.05, 0.1, 0.9, 0.82])
        ax.imshow(plt.imread(apilado_png))
        ax.axis("off")
        prof = info["encastres"][1]
        fig.text(0.05, 0.06, f"Dos cases iguales apilados. Las ruedas del de arriba entran {prof} mm en "
                             f"los platos del de abajo. Solo encastran cases con las mismas medidas "
                             f"exteriores y la misma disposición de ruedas.", fontsize=9, color="#333")
        pdf.savefig(fig)
        plt.close(fig)
        pag += 1

    # ---- Una hoja por pieza ----
    id_num = {i: pz['num'] for pz in piezas for i in pz['ids']}
    for pz in piezas:
        w, h = pz["w"], pz["h"]
        fig = plt.figure(figsize=A4)
        pie(fig, f"Pieza {pz['num']}: {pz['nombre']}", pag)
        ax = fig.add_axes([0.06, 0.18, 0.88, 0.72])
        ax.set_aspect("equal")
        ax.axis("off")
        es_tapa_pz = any(d["paneles"].get(i, {}).get("grupo", "").startswith("tapa") for i in pz["ids"])
        base = color_tapa if es_tapa_pz else color_cuerpo
        relleno = tuple(0.35 * c + 0.65 for c in base[:3])  # tono claro para leer cotas
        ax.add_patch(patches.Rectangle((0, 0), w, h, fc=relleno, ec="black", lw=1.2))

        escala = max(w, h)
        paso = escala * 0.06
        # cotas generales
        cota_h(ax, 0, w, -paso * 1.2, 0, f"{fmt(w)}")
        cota_v(ax, 0, h, -paso * 1.2, 0, f"{fmt(h)}")

        # calados
        nivel_h = 1
        agujeros = [c for c in pz["calados"] if c["tipo"] == "agujero"]
        for c in agujeros:
            ax.add_patch(patches.Circle((c["cx"], c["cy"]), c["w"] / 2, fc="white", ec="black",
                                        lw=0.9))
        # si un tipo de calado se repite, se acota solo el de abajo a la izquierda
        acotar = {}
        for c in pz["calados"]:
            if c["tipo"] != "agujero":
                prev = acotar.get(c["tipo"])
                if prev is None or c["cx"] + c["cy"] < prev["cx"] + prev["cy"]:
                    acotar[c["tipo"]] = c
        repetidos = {t: sum(1 for c in pz["calados"] if c["tipo"] == t) for t in acotar}
        for c in pz["calados"]:
            if c["tipo"] == "agujero":
                continue
            x0, y0 = c["cx"] - c["w"] / 2, c["cy"] - c["h"] / 2
            ax.add_patch(patches.FancyBboxPatch(
                (x0, y0), c["w"], c["h"], boxstyle=f"round,pad=0,rounding_size={c['r']}",
                fc="#eeeeee" if c["tipo"] == "rebaje" else "white", ec="black", lw=1.0,
                ls="--" if c["tipo"] == "rebaje" else "-", hatch="..." if c["tipo"] == "rebaje" else "///"))
            rb = d["info"].get("rebaje", ["3"])
            ax.text(c["cx"], c["cy"], (f"REBAJE\n{fmt(c['w'])} x {fmt(c['h'])}\nprof. {fmt(float(rb[0]))}\ncara sup."
                                       if c["tipo"] == "rebaje" else
                                       f"CALADO {c['tipo'].upper()}\n{fmt(c['w'])} x {fmt(c['h'])}"
                                       f"\nR{fmt(c['r'])}"), ha="center", va="center", fontsize=7 if c["tipo"] == "rebaje" else 8,
                    bbox=dict(fc="white", ec="none", pad=1))
            if acotar.get(c["tipo"]) is c:
                cota_h(ax, 0, x0, y0 - paso * 0.6, y0)
                cota_v(ax, 0, y0, x0 - paso * 0.6, x0)
            ax.plot([c["cx"]] * 2, [y0 - paso * 0.3, y0 + c["h"] + paso * 0.3], color="#888",
                    lw=0.5, ls="-.")
            ax.plot([x0 - paso * 0.3, x0 + c["w"] + paso * 0.3], [c["cy"]] * 2, color="#888",
                    lw=0.5, ls="-.")

        # marcas
        notas = [(f"{n} rebajes iguales y simétricos de {fmt(float(d['info'].get('rebaje', ['3'])[0]))} mm de "
                  "profundidad en la cara de arriba (la que apoya contra el case), sobre los refuerzos de "
                  f"esquina; no son pasantes. Van desde el canto lateral y empiezan a "
                  f"{fmt(min(c['cy'] - c['h'] / 2 for c in pz['calados'] if c['tipo'] == 'rebaje'))} mm "
                  "del canto de cada extremo." if t == "rebaje" else
                  f"{n} calados de {t} iguales y simétricos; se acota uno.")
                 for t, n in repetidos.items() if n > 1]
        cierres = sorted([m for m in pz["marcas"] if m["tipo"] == "cierre"], key=lambda m: m["x"])
        for m in cierres:
            ax.plot([m["x"]] * 2, [0, h], color=MARCA, lw=0.7, ls="-.")
            ax.plot(m["x"], m["y"], marker="+", color=MARCA, ms=12, mew=1.2)
        xs_c = sorted({round(m["x"], 2) for m in cierres})
        for i, x in enumerate(xs_c):
            cota_h(ax, 0, x, h + paso * (0.8 + 0.9 * i), h, col=MARCA)
        if cierres:
            ys_c = sorted({round(m["y"], 2) for m in cierres})
            notas.append(f"Cierres (rojo): eje vertical acotado desde el borde izquierdo. "
                         f"El '+' marca el borde del perfil de cierre, a "
                         + " y ".join(fmt(y) for y in ys_c) + " mm del borde inferior.")
        for m in pz["marcas"]:
            if m["tipo"] == "rueda":
                x0, y0 = m["x"] - m["w"] / 2, m["y"] - m["h"] / 2
                ax.add_patch(patches.Rectangle((x0, y0), m["w"], m["h"], fc="none", ec=MARCA,
                                               lw=0.9, ls="--"))
        acc = sorted([m for m in pz["marcas"] if m["tipo"] == "cierre_acceso"], key=lambda m: m["y"])
        for i, m in enumerate(acc):
            ax.plot([0, w], [m["y"]] * 2, color=MARCA, lw=0.7, ls="-.")
            ax.plot(m["x"], m["y"], marker="+", color=MARCA, ms=12, mew=1.2)
            cota_v(ax, 0, m["y"], w + paso * (0.6 + 0.9 * i), w, col=MARCA)
        if acc:
            cub_n = d["paneles"].get("acceso_izq", {}).get("nombre", "").endswith("cubierta")
            notas.append(("Cierre de la junta de la cubierta" if cub_n else "Cierre de la tapa de acceso")
                         + " (rojo): eje horizontal acotado desde abajo; "
                         f"el '+' marca el borde del perfil de la junta, a {fmt(acc[0]['x'])} mm del "
                         "borde izquierdo.")
        bis = sorted([m for m in pz["marcas"] if m["tipo"] == "bisagra"], key=lambda m: m["x"])
        for i, m in enumerate(bis):
            ax.plot([m["x"]] * 2, [0, h], color="#7d3c98", lw=0.7, ls="-.")
            ax.plot(m["x"], m["y"], marker="x", color="#7d3c98", ms=10, mew=1.2)
            cota_h(ax, 0, m["x"], h + paso * (0.8 + 0.9 * (len(xs_c) + i)), h, col="#7d3c98")
        if bis:
            notas.append("Bisagras (violeta): eje acotado desde el borde izquierdo.")
        pies_m = [m for m in pz["marcas"] if m["tipo"] == "pie"]
        for m in pies_m:
            ax.add_patch(patches.Circle((m["x"], m["y"]), m["w"] / 2, fc="none", ec=MARCA, lw=0.9, ls="--"))
        if pies_m:
            m = min(pies_m, key=lambda m: (m["x"], m["y"]))
            cota_h(ax, 0, m["x"], m["y"] + m["w"] / 2 + paso * 0.5, m["y"], col=MARCA)
            cota_v(ax, 0, m["y"], m["x"] + m["w"] / 2 + paso * 0.5, m["x"], col=MARCA)
            notas.append(f"Pies (rojo): Ø{fmt(m['w'])} mm, centro acotado; simétricos en las 4 esquinas.")
        ruedas = [m for m in pz["marcas"] if m["tipo"] == "rueda"]
        if ruedas:
            m = min(ruedas, key=lambda m: (m["x"], m["y"]))
            x0, y0 = m["x"] - m["w"] / 2, m["y"] - m["h"] / 2
            if not agujeros:  # si hay agujeros, ellos definen la posición
                cota_h(ax, 0, x0, y0 + m["h"] + paso * 0.5, y0 + m["h"], col=MARCA)
                cota_v(ax, 0, y0, x0 + m["w"] + paso * 0.5, x0 + m["w"], col=MARCA)
            notas.append(f"Placas de rueda (rojo, por la cara exterior): {fmt(m['w'])} x "
                         f"{fmt(m['h'])} mm, simétricas en las 4 esquinas.")
        if agujeros:
            # acotar el grupo de agujeros de la esquina inferior izquierda
            a0 = min(agujeros, key=lambda c: (c["cx"] + c["cy"]))
            grupo = [c for c in agujeros if abs(c["cx"] - a0["cx"]) < 200 and abs(c["cy"] - a0["cy"]) < 200]
            xs = sorted({round(c["cx"], 2) for c in grupo})
            ys = sorted({round(c["cy"], 2) for c in grupo})
            cota_h(ax, 0, xs[0], -paso * 0.55, 0)
            cota_v(ax, 0, ys[0], -paso * 0.55, 0)
            ax.plot([xs[0], xs[0]], [0, ys[0]], color=COTA, lw=0.4, ls=":")
            ax.plot([0, xs[0]], [ys[0], ys[0]], color=COTA, lw=0.4, ls=":")
            if len(xs) > 1:
                cota_h(ax, xs[0], xs[1], ys[-1] + paso * 0.4, ys[-1])
            if len(ys) > 1:
                cota_v(ax, ys[0], ys[1], xs[-1] + paso * 0.4, xs[-1])
            notas.append(f"{len(agujeros)} agujeros Ø{fmt(a0['w'])} pasantes, mismo patrón "
                         f"en las 4 ruedas (simétrico).")

        n_niveles = len(xs_c) + len(bis)
        ax.set_xlim(-paso * 2.6, w + paso * (1.0 + 0.9 * len(acc)))
        ax.set_ylim(-paso * 2.4, h + paso * (1.2 + 0.9 * max(n_niveles, 0)))

        # rótulo
        grupos_pz = {d["paneles"][i]["grupo"] for i in pz["ids"] if i in d["paneles"]}
        es_bandeja = any(i in d["bandejas"] for i in pz["ids"])
        es_pared = not any(i in ("piso", "techo", "base2", "base_ruedas") for i in pz["ids"]) \
            and not pz.get("extra") and not es_bandeja
        vista = "Vista desde afuera."
        if pz.get("extra"):
            vista = "Pieza adicional (no forma parte de la caja)."
        elif es_bandeja:
            bj = d["bandejas"][pz["ids"][0]]
            vista = (f"Bandeja interna: cara de arriba a {fmt(bj['altura'])} mm del piso interior, "
                     f"centrada en el cuerpo y apoyada en {bj['soportes']} escuadras atornilladas a los costados.")
        elif "base_ruedas" in pz["ids"]:
            vista = ("Base de ruedas, vista desde abajo: va atornillada bajo el piso del case, "
                     "centrada, y las ruedas se montan en ella.")
        elif es_pared and "tapa" in grupos_pz:
            vista += " Borde inferior del dibujo = lado del perfil de cierre."
        elif es_pared and "tapa2" in grupos_pz:
            vista += " Borde superior del dibujo = lado del perfil de cierre."
        elif es_pared and dos_tapas:
            vista += " Los dos bordes (superior e inferior del dibujo) van a un perfil de cierre."
        elif es_pared:
            vista += " Borde superior del dibujo = lado del perfil de cierre."
        if pz.get("espejo"):
            vista += " Algunas de estas piezas van dadas vuelta o giradas (izquierda/derecha): se cortan iguales."
        entre, de_ent = paneles_entre(d)
        vecinos = sorted({id_num[v] for i in pz["ids"] for v in entre.get(i, []) if v in id_num})
        if vecinos and not pz.get("extra"):
            ent = f"las dos P{vecinos[0]}" if len(vecinos) == 1 else " y ".join(f"P{n}" for n in vecinos)
            notas.append(f"Juego de armado: entra entre {ent}; el ancho ({fmt(w)}) ya tiene descontados "
                         f"{fmt(de_ent)} mm. Al armar, centrala y dejá {fmt(de_ent / 2).replace('.', ',')} mm "
                         "de juego de cada lado (lo tapa el ala del ángulo).")
        mat_pz = pz.get("material", material)
        mat = mat_pz if len(mat_pz) <= 34 else mat_pz[:33] + "…"
        Nc = cantidad_cases(d)
        rot = [(0.06, "Cantidad", str(pz["cant"]) + (f" × {Nc} = {pz['cant'] * Nc}" if Nc > 1 else "")),
               (0.15 + (0.05 if Nc > 1 else 0), "Material", mat),
               (0.50, "Medida", f"{fmt(w)} x {fmt(h)} x {fmt(pz.get('esp', esp))}"),
               (0.70, "Archivo", pz["dxf"])]
        for x, k, v in rot:
            fig.text(x, 0.125, k, fontsize=8, color="#777")
            fig.text(x, 0.1, v, fontsize=10, weight="bold")
        yn = 0.072
        txt_n = vista + ("  " + " ".join(notas) if notas else "")
        lns = textwrap.wrap(txt_n, 175)
        fs_n, dy_n = 8, 0.018
        if len(lns) > 3:   # nota larga: letra un poco más chica para que no pise el pie de página
            lns = textwrap.wrap(txt_n, 192)
            fs_n, dy_n = 7.3, 0.0155
        for ln in lns:
            fig.text(0.06, yn, ln, fontsize=fs_n, color="#333")
            yn -= dy_n
        pdf.savefig(fig)
        plt.close(fig)
        pag += 1

    # ---- Placas ----
    colores = ["#e8c99b", "#cfe0c3", "#c9d9ee", "#f0c9c9", "#e3d1ee", "#f5e6a8", "#cde8e6"]
    for i, pl in enumerate(placas, 1):
        L, A = pl["L"], pl["A"]
        fig = plt.figure(figsize=A4)
        usado = sum(p["w"] * p["h"] for p in pl["piezas"])
        pie(fig, f"Placa {i} de {len(placas)}: {pl['material']} ({fmt(L)} x {fmt(A)})  "
                 f"aprovech. {100 * usado / (L * A):.0f}%", pag)
        ax = fig.add_axes([0.04, 0.1, 0.92, 0.8])
        ax.set_aspect("equal")
        ax.axis("off")
        ax.add_patch(patches.Rectangle((0, 0), L, A, fc="#fafafa", ec="black", lw=1.2))
        for p in pl["piezas"]:
            col = colores[(p["num"] - 1) % len(colores)]
            ax.add_patch(patches.Rectangle((p["x"], p["y"]), p["dw"], p["dh"], fc=col, ec="black",
                                           lw=0.8))
            txt = f"P{p['num']}  {p['nombre_corto']}\n{fmt(p['w'])} x {fmt(p['h'])}"
            if p["rot"]:
                txt += "  (girada)"
            vertical = p["dh"] > p["dw"] * 1.3
            angosta = (p["dw"] if not vertical else p["dh"]) < 300 or min(p["dw"], p["dh"]) < 120
            ax.text(p["x"] + p["dw"] / 2, p["y"] + p["dh"] / 2,
                    txt.replace("\n", "  ") if min(p["dw"], p["dh"]) < 120 else txt,
                    ha="center", va="center", rotation=90 if vertical else 0,
                    fontsize=6 if angosta else 8)
        cota_h(ax, 0, L, -70, 0)
        cota_v(ax, 0, A, -70, 0)
        ax.set_xlim(-160, L + 40)
        ax.set_ylim(-160, A + 40)
        fig.text(0.04, 0.06, f"Kerf {info['placa'][2]} mm entre piezas, margen "
                             f"{info['placa'][3]} mm al borde. 'Girada' = pieza rotada 90°; "
                             f"usá --sin-rotar si importa la veta.", fontsize=8, color="#333")
        pdf.savefig(fig)
        plt.close(fig)
        pag += 1

    # ---- Perfiles ----
    fig = plt.figure(figsize=A4)
    pie(fig, "Perfiles: lista de cortes y barras", pag)
    Nc = cantidad_cases(d)
    filas = [["Perfil", "Tramo", "Largo", "Cant." if Nc == 1 else f"C/U (x{Nc})", "Corte"]] + [
        [p["perfil"], p["desc"], fmt(p["largo"]), str(p["cant"]) if Nc == 1 else f"{p['cant']} ({p['cant'] * Nc})",
         "recto" if p["corte"] == "recto" else
         ("45° en la punta larga, recto en la junta" if p["corte"] == "45/recto" else
          "45° en el aro y 45° en la junta (plano del lateral)" if p["corte"] == "45/45L" else
          "inglete 45° ambos extremos (plano del lateral)" if p["corte"] == "45L/45L"
          else "inglete 45° ambos extremos")] for p in d["perfiles"]]
    ax = fig.add_axes([0.04, 0.5, 0.92, 0.4])
    ax.axis("off")
    tb = ax.table(cellText=filas[1:], colLabels=filas[0], loc="upper left", cellLoc="left",
                  colWidths=[0.2, 0.36, 0.1, 0.07, 0.27])
    tb.auto_set_font_size(False)
    tb.set_fontsize(9)
    tb.scale(1, 1.4)
    ax2 = fig.add_axes([0.04, 0.08, 0.92, 0.38])
    ax2.axis("off")
    barra = float(info["barra"][0])
    fila_y = 0
    for tipo, bs in barras.items():
        for j, b in enumerate(bs, 1):
            ax2.text(-80, fila_y + 0.35, f"{tipo} – barra {j}", ha="right", va="center", fontsize=8)
            ax2.add_patch(patches.Rectangle((0, fila_y), barra, 0.7, fc="#eee", ec="#999", lw=0.5))
            x = 0
            for t in b["tramos"]:
                ax2.add_patch(patches.Rectangle((x, fila_y), t["largo"], 0.7, fc="#b9c9dd",
                                                ec="black", lw=0.5))
                if t["largo"] > 120:
                    ax2.text(x + t["largo"] / 2, fila_y + 0.35, fmt(t["largo"]), ha="center",
                             va="center", fontsize=6.5)
                x += t["largo"] + float(info["barra"][1])
            ax2.text(barra + 40, fila_y + 0.35, f"sobra {fmt(barra - x)}", va="center",
                     fontsize=7, color="#555")
            fila_y -= 1
    ax2.set_xlim(-1800, barra + 700)
    ax2.set_ylim(min(fila_y, -10) + 0.5, 1.2)
    fig.text(0.04, 0.04, "Los perfiles de cierre se cortan a inglete: el largo es la punta larga "
                         "(cara exterior). Alterná el sentido del inglete al cortar para aprovechar "
                         "la barra.", fontsize=8, color="#333")
    pdf.savefig(fig)
    plt.close(fig)
    pag += 1

    # ---- Materiales ----
    fig = plt.figure(figsize=A4)
    pie(fig, "Lista de materiales", pag)
    lm = lista_materiales(d, placas, barras)

    def corto(t, n):
        return t if len(t) <= n else t[:n - 1] + "…"

    filas = [[fl["ref"], corto(fl["material"], 52), fl["cant"], corto(fl["detalle"], 64)] for fl in lm]
    ax = fig.add_axes([0.03, 0.12, 0.94, 0.78])
    ax.axis("off")
    tb = ax.table(cellText=filas, colLabels=["Ref.", "Material", "Cant.", "Detalle"],
                  loc="upper left", cellLoc="left", colWidths=[0.1, 0.38, 0.07, 0.45])
    tb.auto_set_font_size(False)
    tb.set_fontsize(8 if len(filas) > 16 else 9)
    tb.scale(1, 1.45)
    Nc = cantidad_cases(d)
    nota = "Cantidades para " + (f"{Nc} cases." if Nc > 1 else "1 case.") + \
        " Las referencias son las del catálogo de herrajes cargado (flightcase_gen/catalogo_fr.scad)."
    fig.text(0.03, 0.06, nota, fontsize=8, color="#333")
    pdf.savefig(fig)
    plt.close(fig)
    pdf.close()


# ----------------------------------------------------------------------
# Lista de materiales
# ----------------------------------------------------------------------
def contar_placas(placas):
    cuenta = OrderedDict()
    for pl in placas:
        cuenta[pl["material"]] = cuenta.get(pl["material"], 0) + 1
    return cuenta


def cantidad_cases(d):
    try:
        return max(1, int(float(d["info"].get("cantidad", "1"))))
    except ValueError:
        return 1


def lista_materiales(d, placas, barras):
    """Filas: ref, material, cant (texto), detalle. Todo para la cantidad total de cases."""
    info = d["info"]
    N = cantidad_cases(d)
    kerf = float(info["barra"][1])
    filas = []
    ref_pl = info["placa"][4] if len(info["placa"]) > 4 else ""
    for mat, n in contar_placas(placas).items():
        principal = mat == info["material"]
        filas.append(dict(ref=ref_pl if principal else "", material=f"Placa {mat}", cant=str(n),
                          detalle=f"{info['placa'][0]} x {info['placa'][1]} mm"))
    for tipo, bs in barras.items():
        tramos = [p for p in d["perfiles"] if p["perfil"] == tipo]
        ref = tramos[0]["ref"] if tramos else ""
        metros = sum((p["largo"] + kerf) * p["cant"] * N for p in tramos) / 1000
        filas.append(dict(ref=ref, material=tipo, cant=str(len(bs)),
                          detalle=f"barras de {info['barra'][0]} mm ({metros:.2f} m en tramos)"))
    for h in d["herrajes"]:
        filas.append(dict(ref=h["ref"], material=h["nombre"], cant=str(h["cant"] * N),
                          detalle=h["nota"]))
    return filas


def num(v):
    """Número para CSV: sin decimales de más y con coma decimal (Excel en español)."""
    return f"{v:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def dibujar_perfil_cierre(ruta, info, vertical=False):
    """Corte de la junta: perfil híbrido macho (cuerpo) y hembra (tapa), el mismo perfil girado 180°.
    Horizontal (cases frontales o acostados): cuerpo a la izquierda, tapa a la derecha, afuera arriba.
    Vertical (cases parados): cuerpo abajo, tapa arriba, afuera a la izquierda."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    from .instructivo import fmt as _f

    def fmt(v):
        return _f(v).replace(".", ",")
    ci = info["cierre"]
    ref, m_sup, h_sup = ci[1], float(ci[4]), float(ci[5])
    e, canal, t = float(ci[6]), float(ci[7]), float(ci[8])
    j = m_sup + h_sup                       # entre cantos
    L = canal + j / 2                       # de la punta de cada perfil al centro de la junta
    u = 2.5                                 # la unión exterior queda corrida 2,5 del centro (plano 6203)
    g, w = 0.35, 2.0                         # luz entre perfiles y espesor del alma
    k = t / 10
    linea = [(-e, u), (0, u), (0, 1.9), (0.8 * k, 1.9), (2.5 * k, -1.6), (3.5 * k, -1.6), (5 * k, 0),
             (6.5 * k, 1.6), (7.5 * k, 1.6), (9.2 * k, -1.9), (t, -1.9), (t, -u), (t + e, -u)]
    abajo = [(x, y + g) for x, y in linea]
    fondo = [(x, min(y + g + w, j / 2)) for x, y in linea if 0 < x < t or (x == 0 and y < u)]
    fondo = [(x, y) for x, y in fondo if 0 <= x <= t]
    hembra = ([(-e, L)] + abajo + [(t + e, L), (t, L)]
              + [(t, fondo[-1][1])] + fondo[::-1] + [(0, fondo[0][1]), (0, L)])
    macho = [(t - x, -y) for x, y in hembra]
    # coordenadas de dibujo "horizontal": a = a lo largo (cuerpo -, tapa +), b = espesor (afuera +)
    hembra = [(y, x) for x, y in hembra]
    macho = [(y, x) for x, y in macho]

    def T(a, b):
        return (-b, a) if vertical else (a, b)

    def TP(pts):
        return [T(a, b) for a, b in pts]

    def rect(a0, b0, da, db):
        return [T(a0, b0), T(a0 + da, b0), T(a0 + da, b0 + db), T(a0, b0 + db)]

    fig, ax = plt.subplots(figsize=(8, 11) if vertical else (12, 7))
    madera = "#d9b98a"
    ax.add_patch(Polygon(rect(j / 2, 0, L + 7 - j / 2, t), fc=madera, ec="k", lw=0.8))
    ax.add_patch(Polygon(rect(-L - 7, 0, L + 7 - j / 2, t), fc=madera, ec="k", lw=0.8))
    ax.add_patch(Polygon(TP(hembra), fc="#c9d1d9", ec="k", lw=1.1, hatch="////"))
    ax.add_patch(Polygon(TP(macho), fc="#c9d1d9", ec="k", lw=1.1, hatch="\\\\"))
    rot = 90 if vertical else 0
    ax.text(*T(L - 7, t / 2), "PANEL TAPA", ha="center", va="center", fontsize=9, weight="bold", rotation=rot)
    ax.text(*T(-L + 7, t / 2), "PANEL CUERPO", ha="center", va="center", fontsize=9, weight="bold", rotation=rot)
    if vertical:
        ax.annotate("Perfil híbrido (tapa,\ngirado 180°)", T(L - 2, -e + 0.4), T(L + 4, -e - 6), fontsize=10, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.7))
        ax.annotate("Perfil híbrido\n(cuerpo)", T(-L + 2, -e + 0.4), T(-L - 4, -e - 6), fontsize=10, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.7))
    else:
        ax.annotate("Perfil híbrido (tapa,\ngirado 180°)", T(L - 2, -e + 0.4), T(L + 4, -e - 7), fontsize=10, ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.7))
        ax.annotate("Perfil híbrido\n(cuerpo)", T(-L + 2, -e + 0.4), T(-L - 4, -e - 7), fontsize=10, ha="right", va="center",
                    arrowprops=dict(arrowstyle="-", lw=0.7))
    ax.plot(*zip(T(0, -e - 2), T(0, t + e + 17)), color="red", lw=0.8, ls="--")
    if vertical:
        ax.text(*T(0.8, t + e + 17), "centro de la junta\n(plano de cierre)", color="red", fontsize=8.5,
                ha="left", va="bottom")
    else:
        ax.text(*T(0.8, t + e + 17), "centro de la junta\n(plano de cierre)", color="red", fontsize=8.5,
                ha="left", va="top")

    def ch(b, a0, a1, txt, lado):
        """cota a lo largo de la junta, a la altura b del espesor; lado +1 afuera, -1 adentro"""
        ax.annotate("", T(a0, b), T(a1, b), arrowprops=dict(arrowstyle="<->", lw=0.8))
        for a in (a0, a1):
            ax.plot(*zip(T(a, b - 1.2 * lado), T(a, b + 0.6 * lado)), color="k", lw=0.5)
        if vertical:
            ax.text(*T((a0 + a1) / 2, b + 1.0 * lado), txt, ha="right" if lado > 0 else "left",
                    va="center", fontsize=10)
        else:
            ax.text(*T((a0 + a1) / 2, b + 1.0 * lado), txt, ha="center",
                    va="bottom" if lado > 0 else "top", fontsize=10)
    ch(-e - 5, j / 2, L, f"{fmt(canal)}", -1)
    ch(-e - 5, -j / 2, j / 2, f"{fmt(j)}", -1)
    if vertical:
        ax.text(*T(0, -e - 8.5), "entre cantos", ha="left", va="center", fontsize=9)
    else:
        ax.text(*T(0, -e - 8), "entre cantos", ha="center", va="top", fontsize=9)
    ch(-e - 5, -L, -j / 2, f"{fmt(canal)}", -1)
    ch(t + e + 5, -u, L, f"{fmt(L + u)}", 1)
    ch(t + e + 5, -L, -u, f"{fmt(L - u)}", 1)
    ax.annotate("", T(L + 10, 0), T(L + 10, t), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.annotate("", T(-L - 10, -e), T(-L - 10, t + e), arrowprops=dict(arrowstyle="<->", lw=0.8))
    if vertical:
        ax.text(*T(L + 11, t / 2), f"{fmt(t)}", ha="center", va="bottom", fontsize=10)
        ax.text(*T(-L - 11, t / 2), f"{fmt(t + 2 * e)}", ha="center", va="top", fontsize=10)
        ax.text(*T(L + 16, t + e + 1), "← AFUERA", fontsize=9, color="#555", ha="right", va="bottom")
        ax.text(*T(L + 16, -e - 1), "ADENTRO →", fontsize=9, color="#555", ha="left", va="bottom")
        ax.set_xlim(-t - e - 24, e + 16)
        ax.set_ylim(-L - 16, L + 22)
    else:
        ax.text(*T(L + 11, t / 2), f"{fmt(t)}", ha="left", va="center", fontsize=10)
        ax.text(*T(-L - 11, t / 2), f"{fmt(t + 2 * e)}", ha="right", va="center", fontsize=10)
        ax.text(*T(L + 8, t + e + 1), "↑ AFUERA", fontsize=9, color="#555", ha="left", va="bottom")
        ax.text(*T(L + 8, -e - 1), "↓ ADENTRO", fontsize=9, color="#555", ha="left", va="top")
        ax.set_xlim(-L - 22, L + 26)
        ax.set_ylim(-e - 13, t + e + 20)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("Junta con perfil híbrido (corte)", fontsize=12, weight="bold", loc="left")
    fig.savefig(ruta, dpi=160, bbox_inches="tight")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description="Genera planos, DXF y listas de un flightcase.")
    ap.add_argument("proyecto", help="archivo .scad del proyecto (ej. mi_case.scad)")
    ap.add_argument("--salida", help="carpeta de salida (por defecto: salida_<proyecto>)")
    ap.add_argument("--openscad", help="ruta al ejecutable de OpenSCAD")
    ap.add_argument("--sin-rotar", action="store_true",
                    help="no girar piezas al acomodarlas en la placa (respetar veta)")
    ap.add_argument("--stl", action="store_true", help="exportar también el modelo 3D en STL")
    ap.add_argument("--sin-render", action="store_true",
                    help="no generar imágenes 3D (tampoco el instructivo)")
    ap.add_argument("--sin-instructivo", action="store_true",
                    help="no generar la perspectiva explotada ni el instructivo de montaje")
    args = ap.parse_args()

    scad = os.path.abspath(args.proyecto)
    base = os.path.splitext(os.path.basename(scad))[0]
    salida = os.path.abspath(args.salida or f"salida_{base}")
    os.makedirs(os.path.join(salida, "dxf"), exist_ok=True)
    exe = buscar_openscad(args.openscad)

    print(f"Leyendo {os.path.basename(scad)} con OpenSCAD...")
    d = leer_datos(exe, scad)
    for a in d["avisos"]:
        print("  AVISO:", a)

    piezas = agrupar_piezas(d)
    N = cantidad_cases(d)
    if N > 1:
        print(f"Cantidad de cases: {N} (cortes y materiales para el total)")
    print(f"Exportando {len(piezas)} DXF...")
    for pz in piezas:
        nombre = f"{pz['num']:02d}_{pz['ids'][0]}_x{pz['cant']}.dxf"
        pz["dxf"] = nombre
        rc, log = correr_openscad(exe, scad, os.path.join(salida, "dxf", nombre),
                                  {"parte": "panel", "panel_id": pz["ids"][0]})
        if rc != 0:
            print(f"  error exportando {nombre}:\n{log}")
        rebs = [c for c in pz["calados"] if c["tipo"] == "rebaje"]
        if rebs and rc == 0:
            agregar_rebajes_dxf(os.path.join(salida, "dxf", nombre), rebs)

    # piezas adicionales (otro material / espesor)
    for i, e in enumerate(d["extras"]):
        num_p = len(piezas) + 1
        nombre = f"{num_p:02d}_extra{i + 1}_x{e['cant']}.dxf"
        correr_openscad(exe, scad, os.path.join(salida, "dxf", nombre),
                        {"parte": "rect", "rect_w": e["w"], "rect_h": e["h"]})
        piezas.append(dict(num=num_p, ids=[f"extra{i + 1}"], cant=e["cant"], nombre=e["nombre"],
                           w=e["w"], h=e["h"], calados=[], marcas=[], dxf=nombre, extra=True,
                           material=e["material"], esp=e["esp"]))

    material_principal = d["info"]["material"]
    por_material = OrderedDict()
    for pz in piezas:
        if pz.get("extra"):
            corto = pz["nombre"]
        else:
            corto = d["paneles"][pz["ids"][0]]["nombre"].replace(" cuerpo", "").replace(" tapa", "")
        mat = pz.get("material", material_principal)
        for _ in range(pz["cant"] * N):
            por_material.setdefault(mat, []).append(
                dict(num=pz["num"], w=pz["w"], h=pz["h"], nombre_corto=corto))
    pl = d["info"]["placa"]
    placas, no_entran = [], []
    for mat, sueltas in por_material.items():
        pls, ne = acomodar_placas(sueltas, float(pl[0]), float(pl[1]), float(pl[2]),
                                  float(pl[3]), rotar=not args.sin_rotar)
        for p in pls:
            p.update(material=mat, L=float(pl[0]), A=float(pl[1]))
        placas += pls
        no_entran += ne
    for p in no_entran:
        print(f"  AVISO: la pieza {p['num']} ({p['w']} x {p['h']}) no entra en la placa.")
    barras = cortar_barras([dict(p, cant=p["cant"] * N) for p in d["perfiles"]],
                           float(d["info"]["barra"][0]), float(d["info"]["barra"][1]))

    # CSV
    with open(os.path.join(salida, "lista_cortes.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        tot = (lambda c: [c * N]) if N > 1 else (lambda c: [])
        w.writerow(["Tipo", "Pieza", "Descripción", "Largo/Ancho", "Alto", "Espesor",
                    "C/U" if N > 1 else "Cant."] + ([f"Total (x{N})"] if N > 1 else []) + ["Corte", "Archivo"])
        for pz in piezas:
            w.writerow(["Panel", f"P{pz['num']}", pz["nombre"], num(pz["w"]), num(pz["h"]),
                        num(pz["esp"]) if "esp" in pz else num(float(d["info"]["espesor"])), pz["cant"]]
                       + tot(pz["cant"]) + ["", pz["dxf"]])
        for p in d["perfiles"]:
            w.writerow(["Perfil", p["perfil"], p["desc"], num(p["largo"]), "", "", p["cant"]]
                       + tot(p["cant"]) + [p["corte"], ""])
    with open(os.path.join(salida, "materiales.csv"), "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Ref.", "Material", "Cantidad", "Detalle"])
        for fl in lista_materiales(d, placas, barras):
            w.writerow([fl["ref"], fl["material"], fl["cant"], fl["detalle"]])

    # 3D
    render = os.path.join(salida, "render.png")
    if not args.sin_render:
        print("Renderizando vista 3D...")
        rc, log = correr_openscad(
            exe, scad, render, {"parte": "modelo"}, pantalla_virtual=True,
            extra=["--imgsize=1600,1200", "--camera=0,0,0,74,0,35,0", "--viewall",
                   "--autocenter", "--colorscheme=Tomorrow", "--projection=p"])
        if rc != 0:
            print("  (no se pudo generar render.png; sigo sin imagen)")
            render = None
    else:
        render = None
    apilado = None
    if not args.sin_render and d["info"].get("encastres", ["0"])[0] == "1":
        apilado = os.path.join(salida, "apilado.png")
        print("Renderizando vista de apilado...")
        rc, log = correr_openscad(
            exe, scad, apilado, {"parte": "apilado"}, pantalla_virtual=True,
            extra=["--imgsize=1600,1200", "--camera=0,0,0,82,0,28,0", "--viewall",
                   "--autocenter", "--colorscheme=Tomorrow", "--projection=p"])
        if rc != 0:
            apilado = None
    vistas_extra = []
    from .instructivo import fmt
    ci = d["info"].get("cierre", [])
    if len(ci) >= 9 and ci[0] == "1" and ci[1] and float(ci[7]) > 0:
        png_p = os.path.join(salida, "perfil_cierre.png")
        fc = lambda v: fmt(v).replace(".", ",")   # coma decimal en el texto
        dibujar_perfil_cierre(png_p, d["info"], vertical=d["info"].get("tipo", ["1", "vertical"])[1] == "vertical")
        aros = [p for p in d["perfiles"] if p["corte"] != "recto"]
        vistas_extra.append((
            "Perfil híbrido", png_p,
            f"El mismo perfil va en el cuerpo y en la tapa, girado: el panel entra {fc(float(ci[7]))} mm en el canal "
            f"y entre cantos quedan {fc(float(ci[4]) + float(ci[5]))} mm. "
            + ("Aros a inglete 45°, medidos en la punta larga: los largos están en la hoja de perfiles; "
               "en el aro del cuerpo los lados verticales van partidos en la junta de la cubierta"
               if any(p["corte"] in ("45/recto", "45/45L") for p in aros) else
               "Aros a inglete 45°, medidos en la punta larga: "
               + "; ".join(f"{p['cant']} × {fc(p['largo'])} mm ({p['desc'].split(' (')[0].lower()})" for p in aros))
            + f". Cada lado lleva {fc(float(ci[6]))} mm más por esquina porque la pared del perfil sobresale de la cara."))
        jt = [p for p in d["perfiles"] if p["corte"] == "45L/45L"]
        if jt:   # cubierta con perfil híbrido: detalle de la unión a inglete de la junta lateral
            from . import detalle_junta
            png_d = os.path.join(salida, "detalle_union_junta.png")
            L5, L5c = fmt(jt[0]["largo"]), fmt(jt[0]["largo"] - 2 * float(ci[2]))
            detalle_junta.dibujar(png_d, L5=L5, L5c=L5c, solo_vistas=True)
            vistas_extra.append((
                "Detalle: unión a inglete de la junta de la cubierta", png_d,
                " ".join(f"{k}. {n}" for k, n in enumerate(detalle_junta.notas(L5, L5c), 1))))
    if not args.sin_render and d["paneles"].get("acceso_izq", {}).get("nombre", "").endswith("cubierta"):
        png_c = os.path.join(salida, "cubierta.png")
        print("Renderizando la cubierta removible...")
        rc, _ = correr_openscad(
            exe, scad, png_c, {"parte": "modelo", "cubierta_abierta": 300}, pantalla_virtual=True,
            extra=["--imgsize=1600,1200", "--camera=0,0,0,68,0,35,0", "--viewall", "--autocenter",
                   "--colorscheme=Tomorrow", "--projection=p"])
        if rc == 0:
            vistas_extra.append((
                "Cubierta removible", png_c,
                "El techo y los laterales de arriba salen juntos como una cubierta en U; la bandeja "
                "queda fija en la parte de abajo. Para sacarla: abrir las tapas, soltar los cierres "
                "de las juntas laterales y levantar."))
    tab = d["info"].get("tapa_abatible", ["0", "0"])
    if not args.sin_render and tab[0] == "1":
        png_t = os.path.join(salida, "tapa_abierta.png")
        print("Renderizando la tapa abierta...")
        rc, _ = correr_openscad(
            exe, scad, png_t, {"parte": "modelo", "angulo_tapa": 100}, pantalla_virtual=True,
            extra=["--imgsize=1600,1200", "--camera=0,0,0,62,0,20,0", "--viewall", "--autocenter",
                   "--colorscheme=Tomorrow", "--projection=p"])
        if rc == 0:
            n_topes = int(tab[1])
            vistas_extra.append((
                "Tapa abierta", png_t,
                "La tapa gira sobre las bisagras de la trasera (abierta a 100°)."
                + (f" {'Los topes' if n_topes > 1 else 'El tope'} (esquemático"
                   f"{'s' if n_topes > 1 else ''}, por dentro de "
                   f"{'cada lateral' if n_topes > 1 else 'un lateral'}) sostiene"
                   f"{'n' if n_topes > 1 else ''} la tapa abierta." if n_topes else
                   " Sin topes: la tapa se apoya hacia atrás.")))
        png_tt = os.path.join(salida, "tapa_abierta_atras.png")
        rc, _ = correr_openscad(
            exe, scad, png_tt, {"parte": "modelo", "angulo_tapa": 100}, pantalla_virtual=True,
            extra=["--imgsize=1600,1200", "--camera=0,0,0,95,0,205,0", "--viewall", "--autocenter",
                   "--colorscheme=Tomorrow", "--projection=p"])
        if rc == 0:
            vistas_extra.append((
                "Tapa abierta, vista trasera", png_tt,
                "Bisagras en la trasera, sobre la línea de cierre: la tapa gira sobre su eje."))
    laminas, pasos = {}, []
    if not args.sin_render and not args.sin_instructivo:
        from . import instructivo

        def render_png(salida_png, defs, camara, tam):
            rc, _ = correr_openscad(
                exe, scad, salida_png, dict({"parte": "modelo"}, **defs), pantalla_virtual=True,
                extra=[f"--imgsize={tam}", f"--camera={camara}", "--viewall", "--autocenter",
                       "--colorscheme=Tomorrow", "--projection=p"])
            return rc == 0 and os.path.exists(salida_png)

        print("Renderizando perspectiva explotada y láminas de montaje...")
        pasos = instructivo.armar_pasos(d, piezas)
        laminas = instructivo.renderizar_laminas(render_png, d, piezas,
                                                 os.path.join(salida, "montaje"), pasos)
    if args.stl:
        print("Exportando STL (puede tardar)...")
        correr_openscad(exe, scad, os.path.join(salida, "modelo.stl"), {"parte": "modelo"})

    print("Armando planos.pdf...")
    generar_pdf(os.path.join(salida, "planos.pdf"), d, piezas, placas, barras, render, apilado,
                laminas.get("explotado"), vistas_extra)
    if pasos:
        print("Armando instructivo_montaje.pdf...")
        instructivo.generar_instructivo(os.path.join(salida, "instructivo_montaje.pdf"), d, piezas,
                                        laminas, render, pasos)
    print(f"Listo: {salida}")


if __name__ == "__main__":
    main()
