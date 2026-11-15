"""
instructivo.py — perspectiva explotada e instructivo de montaje.

Lo usa generar.py; no hace falta correrlo solo. Arma las láminas renderizando
el mismo proyecto de OpenSCAD con distintos parámetros (explotar, paso) y
escribe instructivo_montaje.pdf con textos que usan las medidas reales del case.
"""
import math
import re
import os
import textwrap

# colores neutros para las láminas (con el color real del case, un negro por
# ejemplo, no se distinguen los paneles)
NEUTRO_CUERPO = "#d8c08e"
NEUTRO_TAPA = "#c4a46c"


def fmt(v):
    return f"{float(v):.1f}".rstrip("0").rstrip(".")


def etiquetas_scad(d, piezas):
    pares = []
    for pz in piezas:
        for pid in pz["ids"]:
            pares.append(f'["{pid}","P{pz["num"]}"]')
    return "[" + ",".join(pares) + "]"


def renderizar_laminas(render, d, piezas, carpeta, pasos):
    """render(salida_png, defs, camara, tamaño) -> bool"""
    os.makedirs(carpeta, exist_ok=True)
    base = {"etiquetas": etiquetas_scad(d, piezas), "color_placa": NEUTRO_CUERPO,
            "color_tapa": NEUTRO_TAPA}
    ext = [float(x) for x in d["info"]["exterior"]]
    laminas = {}
    exp = os.path.join(carpeta, "explotado.png")
    sep = max(80, min(160, max(ext[0], ext[1]) * 0.15))
    if render(exp, dict(base, explotar=round(sep)), "0,0,0,66,0,32,0", "1600,1200"):
        laminas["explotado"] = exp
    for p in pasos:
        if p.get("detalle"):
            from . import detalle_junta
            ruta = os.path.join(carpeta, f"paso_{p['vista']}.png")
            detalle_junta.dibujar(ruta, solo_vistas=True, **p["detalle"])
            laminas[p["vista"]] = ruta
            continue
        if isinstance(p.get("vista"), str) and p.get("defs"):
            ruta = os.path.join(carpeta, f"paso_{p['vista']}.png")
            if render(ruta, dict(base, **p["defs"]), p.get("camara", "0,0,0,62,0,32,0"), "1400,1050"):
                laminas[p["vista"]] = ruta
            continue
        if not isinstance(p.get("vista"), int):
            continue
        ruta = os.path.join(carpeta, f"paso_{p['vista']}.png")
        defs = dict(base, paso=p["vista"])
        if p.get("abrir"):
            defs["abrir_tapa"] = round((ext[2] + ext[3]) * 0.45)
        if render(ruta, defs, p.get("camara", "0,0,0,62,0,32,0"), "1400,1050"):
            laminas[p["vista"]] = ruta
    return laminas


def armar_pasos(d, piezas):
    """Devuelve la lista de pasos con título, texto y lámina a mostrar."""
    info = d["info"]
    ext = [float(x) for x in info["exterior"]]
    hib = info["sistema"] == "hibrido"
    mont = info.get("montaje", ["100", "4", "25", "1", "2", "0", "4"])
    paso_rem, rem_d, esq_desc = float(mont[0]), float(mont[1]), float(mont[2])
    hay_manijas, frenos, lat_cierres, n_cierres = mont[3] == "1", int(float(mont[4])), \
        mont[5] == "1", int(float(mont[6]))
    extra = mont[7:] + ["0"] * (4 - len(mont[7:]))
    cie_emb, n_bis, hay_pies, man_emb = extra[0] == "1", int(float(extra[1])), extra[2] == "1", \
        extra[3] != "0"
    ruedas = info.get("ruedas", ["0"])[0] == "4"
    encastres = info.get("encastres", ["0"])[0] == "1"
    mecha = rem_d + 0.1

    num = {}
    for pz in piezas:
        for pid in pz["ids"]:
            num[pid] = f"P{pz['num']}"
    tipo_i = info.get("tipo", ["1", "vertical"])
    dos, hz = tipo_i[0] == "2", tipo_i[1] == "horizontal"
    nom = {pid: p["nombre"] for pid, p in d["paneles"].items()}

    def may(t):
        return t[:1].upper() + t[1:]

    def pn(pid):
        """'Frente cuerpo (P2)'"""
        return f"{nom.get(pid, pid).lower()} ({num.get(pid, '?')})"

    fr = tipo_i[1] == "frontal"
    t1 = "tapa delantera" if fr else ("tapa izquierda" if (dos and hz) else ("tapa superior" if dos else "tapa"))
    t2 = "tapa trasera" if fr else ("tapa derecha" if hz else "tapa inferior")

    def per(tipo, desc):
        for p in d["perfiles"]:
            if p["perfil"].startswith(tipo) and p["desc"].startswith(desc):
                return p
        return None

    def largos_aro(tipo):
        tr = [p for p in d["perfiles"] if p["perfil"].startswith(tipo) and not p["desc"].startswith("Junta")]
        return " y ".join(f"{p['cant']} × {fmt(p['largo'])}" for p in tr) + " mm" if tr else ""

    def herraje(prefijos, defecto):
        for h in d["herrajes"]:
            if any(h["nombre"].lower().startswith(p) for p in prefijos):
                return h
        return dict(nombre=defecto, cant=0, nota="", ref="")

    def con_ref(h):
        return f"{h['nombre'].lower()}" + (f" (ref. {h['ref']})" if h.get("ref") else "")

    esq = herraje(["esquinero", "cantonera"], "Esquinero bola")
    cie = herraje(["cierre"], "Cierre mariposa")
    man = herraje(["manija", "asa"], "Manija embutida")
    diag = math.hypot(ext[0], ext[1])
    arista = d["perfiles"][0]["perfil"]
    cortes45 = [p["perfil"] for p in d["perfiles"] if p["corte"] != "recto"]
    macho_n = cortes45[0] if cortes45 else "Cierre macho"
    hembra_n = cortes45[-1] if cortes45 else "Cierre hembra"

    def aros_cubierta():
        """Con cubierta removible, qué tramos lleva cada aro (el del cuerpo va partido en la junta)."""
        if not d["paneles"].get("acceso_izq", {}).get("nombre", "").endswith("cubierta"):
            return None
        hor = [p for p in d["perfiles"] if p["perfil"] == macho_n and "horizontales (punta larga)" in p["desc"]]
        ver_ = [p for p in d["perfiles"] if p["perfil"] == hembra_n and "verticales (punta larga)" in p["desc"]]
        tc = [p for p in d["perfiles"] if "tramo de la cubierta" in p["desc"]]
        tf = [p for p in d["perfiles"] if "tramo fijo" in p["desc"]]
        jl = [p for p in d["perfiles"] if p["desc"].startswith("Junta tapa de acceso")]
        if not (hor and ver_ and tc and tf):
            return None
        h, v = fmt(hor[0]["largo"]), fmt(ver_[-1]["largo"])
        return (f"Los aros del cuerpo no se arman enteros: van partidos a la altura de la junta de la cubierta. "
                f"En cada extremo, el tramo de abajo (1 × {h} y 2 × {fmt(tf[0]['largo'])} mm) va en la parte fija "
                f"y el de arriba (1 × {h} y 2 × {fmt(tc[0]['largo'])} mm), en la cubierta; los verticales llevan 45° "
                f"en la punta y corte recto en la junta (pasos 3 y 4). Cada aro de tapa lleva 2 × {h} y 2 × {v} mm."
                + (f" Los {sum(p['cant'] for p in jl)} tramos rectos de {fmt(jl[0]['largo'])} mm no van en los aros: "
                   "son las juntas de la cubierta (pasos 3 y 4)." if jl else ""))

    pasos = []
    pasos.append(dict(
        titulo="Verificar piezas y herramientas",
        vista=None,
        texto=[
            "Separá los paneles por número (P1, P2...) según la lista de paneles de esta hoja y "
            "marcá en cada uno la cara exterior y el borde que va contra el perfil de cierre "
            "(ver planos).",
            "Controlá con cinta que cada panel mida lo indicado: un error de 1 mm en un panel "
            "se nota en todas las aristas.",
            f"Herramientas: sierra con disco para aluminio (cortes rectos y a 45°), remachadora, "
            f"mecha de {fmt(mecha)} mm para remaches de {fmt(rem_d)} mm, escuadra, cinta métrica, "
            f"prensas o sargentos" + (", mecha y llave para los bulones de ruedas" if ruedas else "")
            + ".",
            "Cortá todos los perfiles antes de empezar, siguiendo la hoja de barras del PDF de planos.",
        ]))

    pasos.append(dict(
        titulo="Armar los aros de cierre",
        vista=2,
        texto=[
            (f"Hay dos planos de cierre: armá 2 aros macho y 2 aros hembra. " if dos else "")
            + (f"Perfil de cierre cortado a inglete 45°: {largos_aro(macho_n)} en total, medidos en la "
               f"punta larga" + ("." if aros_cubierta() else "; cada aro lleva dos tramos de cada largo.") if macho_n == hembra_n else
               f"Perfil macho cortado a inglete 45° ({largos_aro(macho_n)}, "
               f"medidos en la punta larga). Lo mismo con la hembra ({largos_aro(hembra_n)})."),
            *([aros_cubierta()] if aros_cubierta() else []),
            "Presentá cada aro sobre una mesa plana, en escuadra. Las dos diagonales del aro "
            f"tienen que dar iguales: unos {fmt(round(diag))} mm.",
            "Encastrá el macho con la hembra para comprobar que cierran parejo y sin juego. "
            "Marcá con lápiz el frente de " + ("cada par de aros" if dos else "los dos aros")
            + " para no invertirlos después.",
        ]))

    par_ent, par_med = (("cuerpo_frente", "cuerpo_izq") if abs(d["paneles"]["cuerpo_frente"]["w"] - ext[0]) < 0.01
                        else ("cuerpo_izq", "cuerpo_frente"))
    def duo(pid):
        """'piso (P1) y techo (P2)' o 'los dos laterales (P3)'"""
        opp = {"cuerpo_frente": "cuerpo_trasera", "cuerpo_izq": "cuerpo_der"}.get(pid, pid)
        a, b = nom.get(pid, pid).lower(), nom.get(opp, opp).lower()
        a, b = (x.replace(" (cubierta)", "").replace(" (parte fija)", "") for x in (a, b))
        if num.get(pid) == num.get(opp):
            base = a.split(" ")[0]
            plural = {"lateral": "laterales", "frente": "frentes", "piso": "pisos"}.get(base, base + "s")
            return f"los dos {plural} ({num.get(pid, '?')})"
        return f"{a.replace(' cuerpo', '')} ({num.get(pid, '?')}) y {b.replace(' cuerpo', '')} ({num.get(opp, '?')})"

    cuerpo_txt = [
        (f"Encastrá los dos bordes de las paredes del cuerpo en los aros macho, uno en cada extremo: "
         if dos else "Encastrá el borde superior de las paredes del cuerpo en el aro macho: ")
        + f"{duo(par_ent)} van de punta a punta y {duo(par_med)}, entre ellos.",
        (("El cuerpo no lleva frente ni fondo de madera: es un marco de cuatro paredes abierto "
          "adelante y atrás, y lo cierran las dos tapas. " if fr else
          "El cuerpo no lleva panel en los extremos: es un marco de cuatro paredes abierto hacia "
          "las dos tapas, que son las que lo cierran. ")
         + "Si querés más rigidez, podés pasar cola vinílica en los cantos donde se tocan las paredes "
           "antes de remachar." if dos else
         ((f"Apoyá las cuatro paredes sobre el piso ({num.get('piso', '?')}): el piso va entero "
           f"({fmt(d['paneles']['piso']['w'])} × {fmt(d['paneles']['piso']['h'])}) y tapa el canto de abajo de "
           "las paredes, al ras de sus caras de afuera. Podés pasar cola vinílica en el canto de las paredes "
           "antes de apoyarlas, para más rigidez.")
          if "piso" in d["paneles"] and abs(d["paneles"]["piso"]["w"] - ext[0]) < 0.01 else
          (f"Colocá el piso ({num.get('piso', '?')}) entre las cuatro paredes, al ras del borde "
           f"inferior. Podés pasar cola vinílica en los cantos para más rigidez."))),
        f"Escuadrá: las diagonales de " + ("cada boca del marco" if dos else "la boca del cuerpo") + f" tienen que medir iguales (≈ {fmt(round(diag))} mm). "
        f"Sujetá con prensas o cinta mientras remachás.",
        f"Remachá el macho por fuera cada {fmt(paso_rem)} mm aprox. (mecha {fmt(mecha)} mm), "
        f"empezando por el centro de cada lado hacia las esquinas.",
    ]
    man_ids = [c_id for c_id, cs in d["calados"].items() if any(c["tipo"] == "manija" for c in cs)]
    if hay_manijas and man_ids:
        n_man = max(len([c for c in d["calados"][man_ids[0]] if c["tipo"] == "manija"]), 1)
        cuerpo_txt.insert(1, f"{may(duo(man_ids[0]))} llevan " + ("el calado de la manija" if n_man == 1 else
                             f"{'dos' if n_man == 2 else n_man} calados de manija cada uno")
                             + ("." if dos or hz else ": orientá los calados hacia arriba (lado del cierre)."))
    if hib:
        cuerpo_txt[1] = ("Colocá los perfiles híbridos del cuerpo: las paredes entran en sus canales; "
                         "ningún panel toca a otro.")
    cub = d["paneles"].get("acceso_izq", {}).get("nombre", "").endswith("cubierta")
    paso_cub = None
    if cub:
        jl = [p for p in d["perfiles"] if p["desc"].startswith("Junta tapa de acceso")]
        tc = [p for p in d["perfiles"] if "tramo de la cubierta" in p["desc"]]
        tf = [p for p in d["perfiles"] if "tramo fijo" in p["desc"]]
        hor = [p for p in d["perfiles"] if p["perfil"] == macho_n and "horizontales (punta larga)" in p["desc"]]
        ang = [p for p in d["perfiles"] if p["perfil"] == arista and p["desc"] == "Aristas a lo profundo cuerpo"]
        n1, n3, n2, n4 = (num.get(k, "?") for k in ("cuerpo_frente", "cuerpo_izq", "cuerpo_trasera", "acceso_izq"))
        pp = lambda k: d["paneles"][k]
        h_ = fmt(hor[0]["largo"]) if hor else "?"
        j_ = fmt(jl[0]["largo"]) if jl else "?"
        cuerpo_txt[0] = (
            "El cuerpo se arma en dos partes: la parte fija, en este paso, y la cubierta desmontable, en el "
            f"siguiente. Parte fija: el piso ({n1}) va de punta a punta y los dos laterales de abajo ({n3}) "
            "se apoyan en sus bordes, encastrados en los dos extremos en el tramo de abajo del aro de cierre"
            + (f" (1 × {h_} abajo y 2 × {fmt(tf[0]['largo'])} mm a los costados)" if tf else "") + ".")
        cuerpo_txt.insert(2, (
            f"En el canto de arriba de cada lateral fijo ({n3}) colocá un tramo recto de perfil híbrido de "
            f"{j_} mm, entre los dos tramos verticales del aro: es la mitad de la junta con la cubierta. "
            "La parte fija queda abierta arriba."))
        for k, t in enumerate(cuerpo_txt):
            if t.startswith("Escuadrá:"):
                cuerpo_txt[k] = (f"Escuadrá: los laterales tienen que quedar a 90° del piso y el ancho por fuera "
                                 f"tiene que dar {fmt(ext[0])} mm abajo y arriba, en los dos extremos. Sujetá con "
                                 "prensas o cinta mientras remachás.")
        acc_n = len([m for m in d["marcas"].get("cuerpo_izq", []) if m["tipo"] == "cierre_acceso"])
        cub_txt = [
            f"Piezas: el techo ({n2}, {fmt(pp('cuerpo_trasera')['w'])} × {fmt(pp('cuerpo_trasera')['h'])}) y los dos "
            f"laterales de la cubierta ({n4}, {fmt(pp('acceso_izq')['w'])} × {fmt(pp('acceso_izq')['h'])}). Perfil "
            f"híbrido: en cada extremo, el tramo de arriba del aro (1 × {h_}"
            + (f" y 2 × {fmt(tc[0]['largo'])} mm" if tc else " mm") + f"), y 2 tramos rectos de {j_} mm para la junta.",
            "Armala boca abajo sobre una mesa plana: el techo "
            f"({n2}) va de punta a punta y los dos laterales ({n4}) se apoyan en sus bordes, encastrados en "
            "los dos extremos en el tramo de arriba del aro (queda una U en cada extremo). Empujá cada panel "
            "hasta el fondo del canal.",
            f"En el canto libre de cada lateral ({n4}) colocá un tramo recto de perfil híbrido de {j_} mm, "
            "girado 180° respecto del de la parte fija, entre los dos tramos verticales del aro. Tiene que "
            "encastrar con el perfil del lateral fijo.",
            (f"Remachá ya los 2 ángulos de las aristas de arriba a lo largo ({fmt(ang[0]['largo'])} mm), al techo y "
             "a cada lateral: le dan rigidez a la cubierta. Los demás ángulos se colocan más adelante, con el case "
             "cerrado." if ang else "Remachá los ángulos de las dos aristas de arriba al techo y a cada lateral."),
            f"Remachá el perfil híbrido por fuera cada {fmt(paso_rem)} mm (mecha {fmt(mecha)} mm). Escuadrá: el "
            f"ancho por fuera tiene que dar {fmt(ext[0])} mm en los dos extremos y en el medio, igual que la parte fija.",
            "Probá la cubierta sobre la parte fija: los perfiles de la junta tienen que encastrar en todo el "
            "largo y los tramos verticales del aro, coincidir en la junta. Tiene que asentar sola y salir hacia "
            "arriba sin trabarse."
            + (" La bandeja queda en la parte fija y no se toca al sacarla." if d.get("bandejas") else ""),
            "Para sacarla con el case armado: quitá las dos tapas (sus aros abrazan también la cubierta), "
            + (f"soltá los {2 * acc_n} cierres de las juntas laterales ({acc_n} por costado) " if acc_n else "soltá los cierres de las juntas laterales ")
            + "y levantala. Esos cierres se colocan en el paso de los cierres, con la palanca en la parte fija.",
        ]
        alto_v = ext[1]
        paso_cub = dict(titulo="Armar la cubierta desmontable", vista="cubierta",
                        defs={"paso": 3, "cubierta_abierta": round(alto_v * 0.3), "resaltar_cubierta": 1},
                        camara="0,0,0,68,0,35,0", texto=cub_txt)
    elif "acceso_izq" in d["paneles"]:
        jl = [p for p in d["perfiles"] if p["desc"].startswith("Junta tapa de acceso")]
        cuerpo_txt.insert(2, (
            f"Costados con tapa de acceso: la parte fija ({pn('cuerpo_izq')}) se arma como una pared "
            f"más; la tapa de acceso ({pn('acceso_izq')}) va arriba. En la junta, perfil macho en la "
            f"parte fija y hembra en la tapa de acceso"
            + (f" (tramos rectos de {fmt(jl[0]['largo'])} mm)" if jl else "")
            + ". El ángulo de la arista superior se remacha solo al techo del cuerpo: la tapa de "
              "acceso entra por debajo de su ala y la sostiene el cierre de la junta."))
    for bid, bj in d.get("bandejas", {}).items():
        bp = d["paneles"][bid]
        cuerpo_txt.append(
            f"{nom.get(bid, bid)} ({num.get(bid, '?')}, {fmt(bp['w'])} × {fmt(bp['h'])}): marcá en los "
            f"dos costados la altura de la cara de arriba, {fmt(bj['altura'])} mm desde el piso "
            f"interior. Atornillá {bj['soportes']} escuadras ({bj['soportes'] // 2} por costado) con el "
            "ala de apoyo a esa altura menos el espesor de la bandeja, apoyá la bandeja centrada y "
            "atornillala a las escuadras. Conviene hacerlo antes de cerrar el último costado.")
    from .generar import paneles_entre
    entre, de_ent = paneles_entre(d)

    def nota_juego(*pres):
        es = [i for i in entre if any(i.startswith(p + "_") for p in pres)]
        medios = sorted({num[i] for i in es if i in num})
        enteros = sorted({num[e] for i in es for e in entre[i] if e in num})
        if not medios or hib:
            return None
        ent = f"las dos {enteros[0]}" if len(enteros) == 1 else " y ".join(enteros)
        return (f"Juego de armado: las piezas {' y '.join(medios)} van entre {ent} y están cortadas "
                f"{fmt(de_ent)} mm más cortas. Centralas y dejá {fmt(de_ent / 2).replace('.', ',')} mm de juego de cada lado; "
                "no las fuerces. El hueco queda tapado por el ala del ángulo.")
    nj = nota_juego("cuerpo")
    if nj:
        cuerpo_txt.insert(1, nj)
    def pasos_cubierta(gen):
        """Rack con cubierta en U y perfil híbrido: instructivo paso a paso, perfil por perfil."""
        porT = {p["titulo"]: p for p in gen}
        P = lambda k: num.get(k, "?")
        med = lambda k: f"{fmt(d['paneles'][k]['w'])} × {fmt(d['paneles'][k]['h'])}"
        def pf(cond):
            r = [p for p in d["perfiles"] if cond(p)]
            return r[0] if r else None
        H1 = pf(lambda p: p["perfil"] == macho_n and "horizontales (punta larga)" in p["desc"])
        H2 = pf(lambda p: "tramo de la cubierta" in p["desc"])
        H3 = pf(lambda p: "tramo fijo" in p["desc"])
        H4 = pf(lambda p: p["perfil"] == hembra_n and "verticales (punta larga)" in p["desc"])
        H5 = pf(lambda p: p["desc"].startswith("Junta tapa de acceso"))
        if not all((H1, H2, H3, H4, H5)):
            return gen
        L = lambda h: fmt(h["largo"])
        ci = info.get("cierre", [])
        canal = fmt(float(ci[7])) if len(ci) > 7 and ci[7] else "21"
        semi = fmt(float(ci[4])) if len(ci) > 4 and ci[4] else "4"
        junta = fmt(float(ci[4]) + float(ci[5])) if len(ci) > 5 and ci[4] and ci[5] else "8"
        ang_c = pf(lambda p: p["perfil"] == arista and p["desc"] == "Aristas a lo profundo cuerpo")
        acc_n = len([m for m in d["marcas"].get("cuerpo_izq", []) if m["tipo"] == "cierre_acceso"])
        p1, p2, p3, p4 = P("cuerpo_frente"), P("cuerpo_trasera"), P("cuerpo_izq"), P("acceso_izq")
        p5, p6, p7, p8 = P("techo"), P("tapa_frente"), P("tapa_trasera"), P("tapa_izq")
        rem = f"Remachá por fuera cada {fmt(paso_rem)} mm (mecha {fmt(mecha)} mm), empezando por el centro de cada tramo hacia las puntas."
        empuja = f"Antes de remachar, empujá cada panel hasta el fondo del canal ({canal} mm)."
        out = [porT["Verificar piezas y herramientas"]]

        ing = H5["corte"] == "45L/45L"
        c23 = ("45° en las dos puntas: una en el plano del aro y la otra, girada 90°, en el plano del lateral"
               if ing else "45° en una punta y recto en la otra")
        out.append(dict(titulo="Cortar y marcar los perfiles híbridos", vista=2, texto=[
            "Cortá los tramos según la hoja de barras de los planos y escribí en cada uno su letra:",
            f"H1 · {L(H1)} mm · inglete 45° en las dos puntas · {H1['cant']} tramos: 2 para la parte fija (abajo), "
            "2 para la cubierta (arriba) y 4 para las tapas (2 por tapa).",
            f"H2 · {L(H2)} mm · {c23} · {H2['cant']} tramos: los verticales de la cubierta.",
            f"H3 · {L(H3)} mm · {c23} · {H3['cant']} tramos: los verticales de la parte fija.",
            f"H4 · {L(H4)} mm · inglete 45° en las dos puntas · {H4['cant']} tramos: los verticales de las tapas (2 por tapa).",
            f"H5 · {L(H5)} mm · " + ("inglete 45° en las dos puntas, en el plano del lateral" if ing else "recto en las dos puntas")
            + f" · {H5['cant']} tramos: las juntas laterales (2 en la parte fija y 2 en la cubierta).",
            "Los largos son de la punta larga, medidos en la arista de afuera"
            + (": en H2, H3 y H5, la del lado de la junta" if ing else "") + ". Alterná el sentido del inglete al "
            "cortar para aprovechar la barra.",
            ("Ojo: en H2 y H3 los dos ingletes están girados 90° entre sí; uno cierra con el H1 y el otro con el "
             "H5 (ver el detalle de la unión)." if ing else ""),
            "Marcá con una flecha la cara de afuera de cada tramo. En cada junta un lado lleva el perfil derecho y "
            "el otro, girado 180°: probalo con dos retazos.",
        ]))
        out[-1]["texto"] = [t for t in out[-1]["texto"] if t]
        if ing:
            from . import detalle_junta
            l5c = fmt(H5["largo"] - 2 * (float(ci[2]) if len(ci) > 2 and ci[2] else 25))
            out.append(dict(titulo="Detalle: unión a inglete de la junta (leer antes de armar)", vista="detalle_junta",
                            detalle={"L5": L(H5), "L5c": l5c},
                            texto=[f"{k}. {n}" for k, n in enumerate(detalle_junta.notas(L(H5), l5c), 1)]))

        def lateral(pid, H, n_h, cual, junta_txt):
            return [
                f"Piezas: los dos laterales {P(pid)} ({med(pid)}), 4 × {H} y 2 × H5.",
                f"1. Apoyá un lateral ({P(pid)}) en la mesa con la cara de afuera hacia abajo.",
                f"2. Encastrá un H5 en el canto {cual}{junta_txt} Sus dos puntas a 45° quedan en el plano del panel.",
                f"3. Encastrá un {H} en el canto de adelante y otro en el de atrás. La punta a 45° que está en el plano "
                f"del lateral va del lado del H5 y cierra el inglete con él; la otra punta (la del aro) queda en el "
                "otro extremo.",
                f"4. Controlá la esquina: el H5 sobresale {semi} mm del canto del panel y cada {H}, {semi} mm del "
                f"canto delantero o trasero; las puntas largas se juntan en la esquina de afuera. El H5 mide en total "
                f"lo mismo que el cuerpo de profundidad ({L(H5)} mm).",
                f"5. {empuja} {rem}",
                "6. Repetí con el otro lateral (sale en espejo).",
            ]

        out.append(dict(titulo="Parte fija: perfiles de los laterales", vista="fija_perf",
                        defs={"paso": 3, "vista_parte": "fija", "resaltar_que": "perfiles"},
                        texto=lateral("cuerpo_izq", "H3", 4, "de arriba",
                                      " con la flecha hacia afuera: es el lado «derecho» de la junta (el H5 de la "
                                      "cubierta irá girado 180°).")))

        out.append(dict(titulo="Parte fija: piso y esquinas de abajo", vista="fija_aro",
                        defs={"paso": 3, "vista_parte": "fija", "resaltar_que": "aro"}, texto=[
            f"Piezas: piso {p1} ({med('cuerpo_frente')}), los dos laterales ya con sus perfiles y 2 × H1.",
            f"1. Apoyá el piso ({p1}) en la mesa con la cara de afuera hacia abajo. Encastrá un H1 en el canto de "
            "adelante y otro en el de atrás, con las puntas a 45° hacia arriba.",
            f"2. Pará los dos laterales sobre los bordes del piso y cerrá los ingletes: en cada una de las 4 "
            "esquinas de abajo, la punta del aro de cada H3 se junta con el H1 a 45°.",
            f"3. Escuadrá: los laterales a 90° del piso y {fmt(ext[0])} mm de ancho por fuera, abajo y arriba, en "
            "los dos extremos. Sujetá con prensas.",
            f"4. {empuja} Remachá los H1 por fuera cada {fmt(paso_rem)} mm.",
            (f"5. Remachá los 2 ángulos de las aristas de abajo a lo largo ({fmt(ang_c['largo'])} mm), al piso y a "
             "cada lateral: le dan rigidez a la parte fija." if ang_c else
             "5. Remachá los ángulos de las dos aristas de abajo a lo largo."),
            "6. La parte fija queda abierta arriba: no lleva techo.",
        ]))

        bj = list(d.get("bandejas", {}).items())
        if bj:
            bid, b0 = bj[0]
            out.append(dict(titulo="Parte fija: bandeja interna", vista="fija_bandeja",
                            defs={"paso": 3, "vista_parte": "fija", "resaltar_que": "bandeja"}, texto=[
                f"Pieza: bandeja ({P(bid)}, {med(bid)}"
                + (f", {d['panelmat'][bid]['material'].lower()}" if d.get("panelmat", {}).get(bid) else "") + ")"
                + f" y {b0['soportes']} escuadras.",
                f"1. Marcá en los dos laterales ({p3}) la altura de la cara de arriba de la bandeja: "
                f"{fmt(b0['altura'])} mm desde el piso interior.",
                f"2. Atornillá {b0['soportes']} escuadras ({b0['soportes'] // 2} por lateral) con el ala de apoyo a "
                "esa altura menos el espesor de la bandeja, con tornillos que no atraviesen el lateral.",
                "3. Apoyá la bandeja centrada y atornillala a las escuadras.",
            ]))

        out.append(dict(titulo="Cubierta: perfiles de los laterales", vista="cub_perf",
                        defs={"paso": 3, "vista_parte": "cubierta", "resaltar_que": "perfiles"},
                        camara="0,0,0,68,0,35,0",
                        texto=lateral("acceso_izq", "H2", 4, "libre (el de abajo)",
                                      ", girado 180° respecto del de la parte fija: presentalo antes encastrado sobre "
                                      "un H5 de la parte fija para confirmar el sentido.")))

        out.append(dict(titulo="Cubierta: techo y esquinas de arriba", vista="cub_aro",
                        defs={"paso": 3, "vista_parte": "cubierta", "resaltar_que": "aro"},
                        camara="0,0,0,68,0,35,0", texto=[
            f"Piezas: techo {p2} ({med('cuerpo_trasera')}), los dos laterales de la cubierta ya con sus perfiles "
            "y 2 × H1.",
            f"1. Apoyá el techo ({p2}) en la mesa con la cara de afuera hacia abajo (la cubierta se arma boca "
            "abajo). Encastrá un H1 en el canto de adelante y otro en el de atrás, con las puntas a 45° hacia arriba.",
            "2. Pará los dos laterales sobre los bordes del techo y cerrá los ingletes: en las 4 esquinas, la "
            "punta del aro de cada H2 se junta con el H1 a 45°.",
            f"3. Escuadrá: {fmt(ext[0])} mm de ancho por fuera en los dos extremos y en el medio, igual que la "
            "parte fija. Sujetá con prensas.",
            f"4. {empuja} Remachá los H1 por fuera cada {fmt(paso_rem)} mm.",
            (f"5. Remachá los 2 ángulos de las aristas del techo a lo largo ({fmt(ang_c['largo'])} mm): le dan "
             "rigidez a la cubierta." if ang_c else "5. Remachá los ángulos de las dos aristas del techo."),
        ]))

        out.append(dict(titulo="Probar la cubierta sobre la parte fija", vista="prueba_cub",
                        defs={"paso": 3, "resaltar_que": "junta", "cubierta_abierta": round(ext[1] * 0.12)}, texto=[
            "1. Bajá la cubierta sobre la parte fija: los H5 tienen que encastrar en todo el largo, de los dos lados.",
            f"2. Mirá cada esquina de la junta: los ingletes de arriba (H2 con H5) y los de abajo (H3 con H5) tienen "
            f"que quedar alineados, con {junta} mm entre los cantos del lateral de abajo y el de arriba.",
            "3. La cubierta tiene que asentar sola y salir hacia arriba sin trabarse."
            + (" La bandeja no se toca al sacarla." if bj else ""),
            "4. Marcá con lápiz el frente de la parte fija y de la cubierta, para armarlas siempre igual.",
            "5. Dejá la cubierta puesta para los pasos que siguen.",
        ]))

        out.append(dict(titulo="Armar los aros de las tapas", vista=2, texto=[
            "Piezas: por tapa, 2 × H1 y 2 × H4 (dos tapas).",
            "1. Presentá cada aro sobre una mesa plana con los ingletes cerrados: H1 arriba y abajo, H4 a los "
            f"costados. Las dos diagonales tienen que dar iguales: unos {fmt(round(diag))} mm.",
            "2. Encastrá el aro en la boca del cuerpo armado (parte fija + cubierta): tiene que cerrar parejo, sin "
            "juego, en todo el contorno, incluida la junta de la cubierta. Si no encastra, giralo 180°.",
            "3. Marcá con lápiz en cada aro el lado que coincide con la marca de frente del cuerpo.",
        ]))

        t = porT.get("Armar las tapas")
        if t:
            out.append(dict(t, texto=[
                f"Piezas por tapa: los dos laterales {p8} ({med('tapa_izq')}), piso {p6} y techo {p7} "
                f"({med('tapa_frente')}), la cara {p5} ({med('techo')}) y su aro.",
                f"1. Encastrá los dos {p8} en los H4 del aro (de punta a punta) y el {p6} y el {p7} entre ellos, en los H1.",
                f"2. {empuja} Escuadrá con las diagonales y remachá el aro cada {fmt(paso_rem)} mm.",
                f"3. Apoyá la cara ({p5}) entera por encima, tapando el canto de las cuatro paredes.",
                "4. Respetá la marca de frente: cada tapa tiene que cerrar en el mismo sentido en que probaste su aro.",
            ]))

        a = porT.get("Colocar los ángulos de aluminio")
        if a:
            tx = list(a["texto"])
            tx[0] = ("Cerrá las dos tapas sobre el cuerpo (aros encastrados) y sujetá: los ángulos de las tapas "
                     "se colocan con el case cerrado para que tapas y cuerpo queden alineados.")
            tx[1] = tx[1].replace("; los 2 de arriba ya están en la cubierta", "; ya colocados en los pasos de la parte fija y la cubierta")
            out.append(dict(a, texto=tx))
        for k in ("Colocar esquineros y refuerzos", "Colocar los esquineros", "Colocar los cierres",
                  "Colocar las manijas", "Colocar ruedas", "Colocar ruedas y platos de apilado"):
            if k in porT:
                out.append(porT[k])
        f = porT.get("Control final")
        if f:
            out.append(dict(f, texto=list(f["texto"]) + [
                "Sacá y volvé a poner la cubierta una vez: quitá las dos tapas (sus aros abrazan también la "
                "cubierta), soltá " + (f"los {2 * acc_n} cierres de las juntas laterales ({acc_n} por costado)"
                                       if acc_n else "los cierres de las juntas laterales")
                + " y levantala. Tiene que salir y volver a entrar sin forzar."]))
        return out

    pasos.append(dict(titulo="Armar la parte fija del cuerpo" if paso_cub else "Armar el cuerpo", vista=3,
                      texto=cuerpo_txt))
    if paso_cub:
        pasos.append(paso_cub)

    cubre = abs(d["paneles"]["techo"]["w"] - ext[0]) < 0.01
    def arma_tapa(pre, cara):
        """Texto de armado de una tapa: qué paredes van enteras, cuáles entre ellas y la cara."""
        ent, med = ((pre + "_frente", pre + "_izq")
                    if abs(d["paneles"][pre + "_frente"]["w"] - ext[0]) < 0.01 else (pre + "_izq", pre + "_frente"))
        opp = ent.replace("_frente", "_trasera").replace("_izq", "_der")
        corto = lambda i: nom.get(i, "").lower().split(" tapa")[0]
        return (f"las dos {num.get(ent, '?')} ({corto(ent)} y {corto(opp)}) de punta a punta y "
                f"las dos {num.get(med, '?')} entre ellas, encastradas en un aro hembra; después la cara "
                f"{num.get(cara, '?')} " + ("entera por encima, tapando el canto de las cuatro paredes."
                                          if cubre else "adentro de las cuatro paredes."))
    mismas = dos and all(num.get("tapa_" + x) == num.get("tapa2_" + x) for x in ("frente", "izq")) \
        and num.get("techo") == num.get("base2")
    if not dos:
        armado_t = f"Armala igual que el cuerpo: {arma_tapa('tapa', 'techo')}"
    elif mismas:
        armado_t = (f"Las dos tapas ({t1} y {t2}) son iguales y se arman igual que el cuerpo: "
                    + arma_tapa("tapa", "techo"))
    else:
        armado_t = (f"Se arman igual que el cuerpo. {may(t1)}: {arma_tapa('tapa', 'techo')} "
                    f"{may(t2)}: {arma_tapa('tapa2', 'base2')}")
    tapa_txt = [
        armado_t,
        ("Respetá la marca de frente de cada aro: cada tapa tiene que cerrar en el mismo sentido en que "
         "probaste los aros." if dos else "Respetá la marca de frente del aro: la tapa tiene que cerrar "
         "en el mismo sentido en que probaste los aros."),
        f"Escuadrá con las diagonales y remachá la hembra cada {fmt(paso_rem)} mm.",
    ]
    if encastres:
        tapa_txt.insert(1, f"El techo {num['techo']} lleva los calados de los platos de apilado. "
                           f"Su posición tiene que coincidir con las ruedas del piso: orientá el "
                           f"techo con el mismo frente que el piso.")
    if hib:
        tapa_txt[0] = "Con los perfiles híbridos de cada tapa. " + armado_t
    nj = nota_juego("tapa", "tapa2")
    if nj:
        tapa_txt.insert(1, nj)
    pasos.append(dict(titulo="Armar las tapas" if dos else "Armar la tapa", vista=4, abrir=True,
                      texto=tapa_txt))

    if not hib:
        rectos = [p for p in d["perfiles"] if p["corte"] == "recto" and p["perfil"] == arista]
        def desc_a(t):
            t = t.lower()
            for a, b in ((" cuerpo", " del cuerpo"), (" tapa del.", " de la tapa delantera"),
                         (" tapa tras.", " de la tapa trasera"), (" tapa sup.", " de la tapa superior"),
                         (" tapa inf.", " de la tapa inferior"), (" tapa izq.", " de la tapa izquierda"),
                         (" tapa der.", " de la tapa derecha"), (" tapa", " de la tapa")):
                if t.endswith(a):
                    return t[:-len(a)] + b
            t = t.replace(" (", ", ").replace(")", "")
            return t.replace("de las caras", "de las tapas") if fr else t
        lineas = [f"{p['cant']} × {fmt(p['largo'])} mm ({desc_a(p['desc'])}"
                  + ("; los 2 de arriba ya están en la cubierta" if paso_cub and p["desc"] == "Aristas a lo profundo cuerpo" else "")
                  + ")" for p in rectos]
        vt = any("tapa" in p["desc"] for p in rectos)
        txt = [
            ("Cerrá las dos tapas sobre el cuerpo" if dos else "Cerrá la tapa sobre el cuerpo")
            + " (macho y hembra encastrados) y sujetá: los ángulos se colocan con el case cerrado "
            "para que tapas y cuerpo queden alineados.",
            (f"{may(arista)}" if arista.lower().startswith("ángulo") else f"Ángulos ({arista})")
            + ": " + "; ".join(lineas) + ".",
            f"Cada tramo deja {fmt(esq_desc)} mm libres en los extremos que van a un esquinero. "
            f"Los tramos a lo largo del case terminan contra el perfil de cierre.",
            f"Perforá y remachá ambas alas cada {fmt(paso_rem)} mm, alternando lados para no "
            f"torcer el ángulo.",
        ]
        if not vt:
            txt.append("La tapa es corta: no lleva ángulo a lo largo, el esquinero llega directo al "
                       "perfil de cierre.")
        pasos.append(dict(titulo="Colocar los ángulos de aluminio", vista=5, texto=txt))

    pasos.append(dict(
        titulo="Colocar los esquineros",
        vista=6,
        texto=[
            f"8 × {con_ref(esq)}, uno en cada vértice, cubriendo los extremos de los perfiles.",
            "Presentá el esquinero, marcá sus agujeros, perforá y remachá en todos sus orificios.",
            "Si el esquinero no apoya plano, revisá que los perfiles no lleguen demasiado cerca "
            "del vértice y repasá el corte.",
        ]))
    refz = herraje(["refuerzo"], "")
    nota_base = None
    if ruedas and "base_ruedas" in d["paneles"]:
        bp = d["paneles"]["base_ruedas"]
        mu = [float(x) for x in info.get("mundo", [ext[0], ext[1], ext[2] + ext[3]])]
        mx, my = (mu[0] - bp["w"]) / 2, (mu[1] - bp["h"]) / 2   # margen base-borde del case
        PATA, R_ALA, R_ALTO = 45, 45, 60
        if mx < PATA and my < PATA and "bola" in esq["nombre"].lower():
            nota_base = ("Base de ruedas: en las 4 esquinas de abajo el esquinero bola pisa la base. "
                         "Usá esquineros planos abajo o recortá las esquinas de la base.")
        ci = info.get("cierre", [])
        m_alto = float(ci[2]) if len(ci) > 2 and ci[2] else 0
        rebs = [c for c in d["calados"].get("base_ruedas", []) if c["tipo"] == "rebaje"]
        if refz["nombre"] and rebs:
            esp_r = info.get("rebaje", ["3"])[0]
            nota_base = (
                f"Los 4 refuerzos de abajo del cuerpo quedan debajo de la base de ruedas: por eso la base "
                f"({num.get('base_ruedas', '?')}) lleva 4 rebajes de {fmt(rebs[0]['w'])} × {fmt(rebs[0]['h'])} mm "
                f"y {fmt(esp_r)} mm de profundidad en la cara de arriba (ver planos). Hacé los rebajes antes "
                "de montar la base. Los esquineros bola no tocan la base.")
        elif refz["nombre"] and fr and m_alto and mx < R_ALA:
            y1 = ext[2] / 2 - m_alto
            if bp["h"] / 2 > y1 - R_ALTO:
                nota_base = ("Los 4 refuerzos de abajo del cuerpo quedan debajo de la base de ruedas: "
                             "rebajá la base en esas zonas o no pongas esos 4 refuerzos.")
    if refz["nombre"]:
        pasos[-1]["titulo"] = "Colocar esquineros y refuerzos"
        pasos[-1]["texto"].append(
            f"{refz['cant']} × {refz['nombre'][:1].lower() + refz['nombre'][1:]}, uno en cada esquina de " + ("cada junta de cierre" if dos else "la junta de cierre")
            + (", del lado del cuerpo y del lado de la tapa" if "tapa" in refz["nota"] else ", del lado del cuerpo")
            + ": apoyado contra el perfil de cierre y montado sobre el ángulo, con un ala en cada cara. "
              "Nunca cruzan la junta, para que " + ("las tapas se puedan abrir." if dos else "la tapa se pueda abrir.") + " Remachá en todos sus orificios.")
    if nota_base:
        pasos[-1]["texto"].append(nota_base)

    txt = [
        f"{n_cierres} × {con_ref(cie)}, con el case cerrado. Cada cierre se centra en su eje: "
        f"la palanca en el cuerpo y el gancho en la tapa"
        + (", en los dos planos de cierre." if dos else "."),
    ]
    # una línea por cada pared del cuerpo que lleva cierres
    lin_c = {}
    for pid in ("cuerpo_frente", "cuerpo_trasera", "cuerpo_izq", "cuerpo_der", "acceso_izq", "acceso_der"):
        xs = sorted({round(m["x"]) for m in d["marcas"].get(pid, []) if m["tipo"] == "cierre"})
        if xs:
            w_p = d["paneles"][pid]["w"]
            espejo = tuple(sorted(round(w_p - x) for x in xs))
            # la pieza opuesta es la misma pieza dada vuelta: sus ejes son los espejados
            k_esp = (num.get(pid, "?"), espejo)
            if pid.endswith("_der") and k_esp in lin_c:
                lin_c[k_esp].append(pid)
            else:
                lin_c.setdefault((num.get(pid, "?"), tuple(xs)), []).append(pid)
    cub_c = d["paneles"].get("acceso_izq", {}).get("nombre", "").endswith("cubierta")
    for (n_p, xs), pids in lin_c.items():
        quien = duo(pids[0]) if len(pids) == 2 else pn(pids[0]).replace(" (cubierta)", "").replace(" (parte fija)", "").replace(" cuerpo (", " (")
        if cub_c and pids[0].startswith("cuerpo_izq"):
            quien = f"los dos laterales de abajo ({n_p})"
        elif cub_c and pids[0].startswith("acceso_"):
            quien = f"los dos laterales de la cubierta ({n_p})"
        ejes = ", ".join(fmt(x) for x in xs)
        w_p = d["paneles"][pids[0]]["w"]
        centro = len(xs) == 1 and abs(xs[0] - w_p / 2) < 1
        x_min = min(min(xs), min(w_p - x for x in xs))
        if centro:
            donde = f"ejes centrados en el panel, a {ejes} mm del borde izquierdo"
        elif cub_c and len(xs) == 1 and pids[0].startswith("cuerpo_"):
            donde = f"ejes a {fmt(x_min)} mm del canto de abajo (lado del piso)"
        elif cub_c and len(xs) == 1 and pids[0].startswith("acceso_"):
            donde = f"ejes a {fmt(x_min)} mm del canto de arriba (lado del techo)"
        elif len(pids) == 2 and len(xs) == 1 and abs(xs[0] - x_min) > 0.5:
            donde = (f"ejes a {ejes} mm del borde izquierdo del panel (la pieza opuesta va dada vuelta: "
                     f"a {fmt(x_min)} mm)")
        else:
            donde = f"ejes a {ejes} mm del borde izquierdo del panel"
        txt.append(may(quien) + ": " + donde
                   + (", un cierre en cada junta (adelante y atrás)." if dos else "."))
    acc_m = [m for m in d["marcas"].get("cuerpo_izq", []) if m["tipo"] == "cierre_acceso"]
    cub = d["paneles"].get("acceso_izq", {}).get("nombre", "").endswith("cubierta")
    if acc_m:
        txt.append(("Cubierta: " if cub else "Tapas de acceso: ") + str(len(acc_m))
                   + (" cierres" if len(acc_m) > 1 else " cierre") + " por costado en la junta, a "
                   + " y ".join(fmt(m["y"]) for m in acc_m)
                   + " mm del borde inferior del panel (ver planos); la palanca en la parte fija.")
    if cie_emb:
        txt.insert(1, "Son cierres embutidos: el calado ya está hecho en las paredes del cuerpo, "
                      "junto al perfil macho. Insertá la cubeta desde afuera y remachala "
                      "por el reborde.")
    txt.append("Ajustá la posición del gancho para que el cierre tense firme pero sin forzar, "
               "y recién ahí remachá.")
    if n_bis:
        bis = herraje(["bisagra"], "Bisagra")
        pos_b = sorted({round(m["x"]) for m in d["marcas"].get("cuerpo_trasera", [])
                        if m["tipo"] == "bisagra"})
        if pos_b:
            txt.append(f"{len(pos_b)} × {con_ref(bis)}, en la trasera: ejes a "
                       + ", ".join(fmt(x) for x in pos_b) + " mm del borde izquierdo, con el case "
                       "cerrado para que la tapa quede alineada.")
        else:
            txt.append(f"Bisagra de piano: {con_ref(bis)}, {bis['nota']}, centrada en la trasera "
                       "sobre la línea de cierre, con el case cerrado.")
        tope = herraje(["tope"], "")
        if tope["nombre"]:
            nt = int(tope.get("cant") or 1)
            txt.append(f"{nt} × {con_ref(tope)}" + (", uno por dentro de cada lateral" if nt == 2 else
                                                   ", por dentro de un lateral" if nt == 1 else ", por dentro")
                       + ": montalos con la tapa abierta al ángulo que quieras." if nt > 1 else
                       f"{nt} × {con_ref(tope)}, por dentro de un lateral: montalo con la tapa abierta al "
                       "ángulo que quieras.")
    pasos.append(dict(titulo="Colocar cierres y bisagras" if n_bis else "Colocar los cierres",
                      vista=7, texto=txt))

    if hay_manijas:
        pasos.append(dict(
            titulo="Colocar las manijas",
            vista=8,
            texto=[
                f"Insertá una {con_ref(man)} en cada calado de manija"
                f": {duo(man_ids[0]) if man_ids else 'ver planos'}.",
                "Verificá que la cubeta entre sin forzar y que la manija gire hasta tope sin rozar.",
                "Remachá por fuera en todos los orificios del reborde.",
            ] if man_emb else [
                f"Asas de superficie ({con_ref(man)}): una en cada panel marcado en los planos, "
                "centrada en la marca.",
                "Atornillá o remachá según el modelo; si atornillás, poné tuerca o arandela por dentro.",
            ]))

    base_id = next((pid for pid, ms in d["marcas"].items()
                    if any(m["tipo"] in ("rueda", "pie") for m in ms)), "piso")
    # panel del case que queda abajo (con base de ruedas, el que la sostiene)
    base_id_piso = ("cuerpo_izq" if hz else "cuerpo_frente" if fr else ("base2" if dos else "piso"))
    base_txt = pn(base_id)
    if ruedas or encastres or hay_pies:
        txt = []
        if hay_pies:
            pie = herraje(["pie"], "Pie de goma")
            txt += [f"Pies ({con_ref(pie)}): con el case dado vuelta, uno en cada marca del piso "
                    f"({base_txt}); atornillalos o remachalos según el modelo."]
        if ruedas and "base_ruedas" in d["paneles"]:
            bp = d["paneles"]["base_ruedas"]
            mat_b = d["panelmat"].get("base_ruedas", {}).get("material", "")
            pas = any(m["tipo"] == "agujero" for m in d["calados"].get(base_id_piso, []))
            txt += [
                f"Base de ruedas ({num.get('base_ruedas', '?')}, {fmt(bp['w'])} × {fmt(bp['h'])} {mat_b}): con el "
                f"case dado vuelta, centrala sobre el piso ({num.get(base_id_piso, '?')}), apoyada en las alas de "
                "los ángulos" + (", con los rebajes hacia el case, calzando sobre los 4 refuerzos."
                                if any(c["tipo"] == "rebaje" for c in d["calados"].get("base_ruedas", [])) else "."),
                ("Presentá cada rueda sobre sus 4 agujeros y pasá los bulones atravesando base y piso: "
                 "cabeza con arandela grande por dentro del case, arandela y tuerca autofrenante del "
                 "lado de la rueda (16 en total). Eso fija también la base." if pas else
                 "Atornillá la base al piso y después montá cada rueda sobre sus 4 agujeros de la base "
                 "con bulón, arandela y tuerca autofrenante (16 en total)."),
                f"Las {frenos} ruedas con freno van del mismo lado (normalmente el frente)."
                if 0 < frenos < 4 else "",
            ]
        elif ruedas:
            txt += [
                "Ruedas: con el case dado vuelta, presentá cada rueda sobre sus 4 agujeros del piso "
                f"({base_txt}).",
                "Pasá los bulones desde adentro con arandela grande, y ajustá por fuera con "
                "arandela y tuerca autofrenante (16 en total).",
                f"Las {frenos} ruedas con freno van del mismo lado (normalmente el frente)."
                if 0 < frenos < 4 else "",
            ]
        if encastres:
            txt += [f"Platos de apilado: insertá los 4 platos en los calados del techo "
                    f"({num['techo']}) y remachalos por el reborde."]
        partes = [n for n, v in (("ruedas", ruedas), ("pies", hay_pies), ("platos de apilado", encastres)) if v]
        pasos.append(dict(titulo="Colocar " + " y ".join(partes),
                          vista=9, camara="0,0,0,80,0,32,0" if (ruedas or hay_pies) else "0,0,0,55,0,32,0",
                          texto=[t for t in txt if t]))

    final = [
        ("Abrí y cerrá las dos tapas varias veces: tienen que encastrar solas y" if dos else
         "Abrí y cerrá la tapa varias veces: tiene que encastrar sola y") + " los cierres tensar parejo.",
        "Revisá que no queden remaches flojos ni filos en los cortes de aluminio.",
    ]
    if encastres and ruedas:
        final.append("Si armaste dos cases iguales, apilalos y comprobá que las ruedas del de "
                     "arriba entren en los platos sin trabarse.")
    pasos.append(dict(titulo="Control final", vista="final", texto=final))
    if macho_n == hembra_n:   # perfil de cierre híbrido: el mismo en cuerpo y tapa
        reemplazos = [("2 aros macho y 2 aros hembra", "4 aros"), ("aros macho", "aros de cierre"),
                      ("aros hembra", "aros de cierre"), ("aro macho", "aro de cierre"),
                      ("aro hembra", "aro de cierre"), ("Perfil macho", "Perfil de cierre híbrido"),
                      ("Lo mismo con la hembra", "Mismos largos para el aro de la tapa"),
                      ("el macho con la hembra", "el aro del cuerpo con el de la tapa"),
                      ("el macho", "el perfil de cierre"), ("la hembra", "el perfil de cierre"),
                      ("(macho y hembra encastrados)", "(aros encastrados)"),
                      ("macho en la parte fija y hembra en la cubierta", "perfil de cierre en la parte fija y en la cubierta"),
                      ("perfil macho en la parte fija y hembra en la tapa de acceso", "perfil de cierre en la parte fija y en la tapa de acceso"),
                      ("perfil macho", "perfil de cierre")]
        for p in pasos:
            for i, t in enumerate(p["texto"]):
                for a, b in reemplazos:
                    t = t.replace(a, b)
                p["texto"][i] = t
        ci = info.get("cierre", [])
        if len(ci) >= 9 and ci[1] and float(ci[7]) > 0:
            ref, m_alto, h_alto = ci[1], float(ci[2]), float(ci[3])
            m_sup, h_sup, canal = float(ci[4]), float(ci[5]), float(ci[7])
            for p in pasos:
                if p["titulo"] == "Armar los aros de cierre":
                    p["texto"].insert(1, (
                        f"Perfil híbrido: es el mismo en el cuerpo y en la tapa; el de la tapa va girado 180°. "
                        f"El panel entra {fmt(canal)} mm en el canal del perfil y entre el canto del cuerpo y "
                        f"el de la tapa quedan {fmt(m_sup + h_sup)} mm ({fmt(m_sup)} + {fmt(h_sup)}). Cada perfil "
                        f"llega {fmt(m_alto).replace('.', ',')} mm desde su borde hasta el centro de la junta. Colocá "
                        "todos los aros del cuerpo con la misma cara hacia afuera, así encastran con los de la tapa."))
                if p["titulo"] == "Armar el cuerpo":
                    p["texto"].insert(len(p["texto"]) - 1,
                        f"Empujá cada panel hasta el fondo del canal ({fmt(canal)} mm): si no llega, el case "
                        "queda más largo y la tapa no cierra pareja.")
    if paso_cub and macho_n == hembra_n:
        pasos = pasos_cubierta(pasos)
    import re
    for p in pasos:
        p["texto"] = [re.sub(r"(\d)\.(\d)", r"\1,\2", t) for t in p["texto"]]
    return pasos


def generar_instructivo(ruta, d, piezas, laminas, render_final, pasos):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    A4 = (11.69, 8.27)
    info = d["info"]
    ext = [float(x) for x in info["exterior"]]
    mundo = info.get("mundo", [ext[0], ext[1], ext[2] + ext[3]])
    titulo_case = f"Flightcase {fmt(mundo[0])} × {fmt(mundo[1])} × {fmt(mundo[2])} mm"
    pdf = PdfPages(ruta)
    hoja = [1]

    def encabezado(fig, titulo):
        fig.text(0.03, 0.955, titulo, fontsize=17, weight="bold", va="top")
        fig.text(0.97, 0.955, titulo_case, fontsize=9, ha="right", va="top", color="#555")
        fig.text(0.97, 0.02, f"Instructivo de montaje · hoja {hoja[0]}", fontsize=8,
                 ha="right", color="#777")
        hoja[0] += 1

    def imagen(fig, ruta_img, rect):
        if ruta_img and os.path.exists(ruta_img):
            ax = fig.add_axes(rect)
            ax.imshow(plt.imread(ruta_img))
            ax.axis("off")

    # ---- Portada: perspectiva explotada + lista de piezas ----
    fig = plt.figure(figsize=A4)
    encabezado(fig, "Perspectiva explotada")
    imagen(fig, laminas.get("explotado"), [0.0, 0.06, 0.62, 0.86])
    y = 0.86
    fig.text(0.63, y, "Paneles", fontsize=12, weight="bold")
    y -= 0.04
    for pz in piezas:
        fig.text(0.63, y, f"P{pz['num']}", fontsize=10, weight="bold")
        import textwrap
        nl = textwrap.wrap(pz['nombre'], 62) or [""]
        for k, ln in enumerate(nl):
            fig.text(0.67, y - 0.02 * k, ln, fontsize=8.5)
        y -= 0.02 * (len(nl) - 1)
        fig.text(0.67, y - 0.022, f"{fmt(pz['w'])} × {fmt(pz['h'])} mm · {pz['cant']} u.",
                 fontsize=8.5, color="#555")
        y -= 0.055
    y -= 0.01
    fig.text(0.63, y, "Perfiles y herrajes", fontsize=12, weight="bold")
    y -= 0.035
    tipos = []
    for p in d["perfiles"]:
        if p["perfil"] not in tipos:
            tipos.append(p["perfil"])
    for tp in tipos:
        n = sum(p["cant"] for p in d["perfiles"] if p["perfil"] == tp)
        fig.text(0.63, y, f"• {tp}: {n} tramos", fontsize=8.5)
        y -= 0.026
    for h in d["herrajes"]:
        if y < 0.06:
            break
        fig.text(0.63, y, f"• {h['nombre']}: {h['cant']}", fontsize=8.5)
        y -= 0.026
    fig.text(0.03, 0.02, "Las láminas usan un color neutro para distinguir los paneles. "
                         "En naranja, lo que se agrega en cada paso.", fontsize=8, color="#777")
    pdf.savefig(fig)
    plt.close(fig)

    # ---- Pasos ----
    for i, p in enumerate(pasos, 1):
        fig = plt.figure(figsize=A4)
        encabezado(fig, f"Paso {i}. {p['titulo']}")
        if p["vista"] == "final":
            img = render_final
        elif p["vista"] is None:
            img = laminas.get("explotado")
        else:
            img = laminas.get(p["vista"])
        es_lista = p["vista"] is None
        if not es_lista:
            imagen(fig, img, [0.02, 0.06, 0.58, 0.84])
        x_txt = 0.04 if es_lista else 0.62
        # el texto se achica para que entre; si aun así no entra, sigue en otra hoja
        n_lin = sum(len(textwrap.wrap(t, 52)) for t in p["texto"])
        esc = 1.0 if n_lin <= 22 else max(0.78, 22 / n_lin)
        fs, paso_l, ancho = 10 * esc, 0.032 * esc, int(52 / esc)
        y = 0.86
        for parrafo in p["texto"]:
            lineas = textwrap.wrap(parrafo, ancho)
            if y - paso_l * len(lineas) < 0.06:
                pdf.savefig(fig)
                plt.close(fig)
                fig = plt.figure(figsize=A4)
                encabezado(fig, f"Paso {i}. {p['titulo']} (continuación)")
                if not es_lista:
                    imagen(fig, img, [0.02, 0.06, 0.58, 0.84])
                y = 0.86
            numerado = re.match(r"^\d+\. ", parrafo) is not None   # pasos numerados: sin viñeta
            for k, ln in enumerate(lineas):
                fig.text(x_txt, y, (("" if numerado else "•  ") if k == 0 else ("     " if numerado else "    ")) + ln,
                         fontsize=fs, va="top")
                y -= paso_l
            y -= 0.018 * esc
        if es_lista:
            # lista de paneles a la derecha
            Nc = int(float(d["info"].get("cantidad", "1") or 1))
            esp_def = fmt(float(d["info"]["espesor"]))
            filas = []
            for pz in piezas:
                nombre = "\n".join(textwrap.wrap(pz["nombre"].replace(" / ", " / "), 40))
                fila = [f"P{pz['num']}", nombre, f"{fmt(pz['w'])} × {fmt(pz['h'])}",
                        fmt(pz["esp"]) if "esp" in pz else esp_def, str(pz["cant"])]
                if Nc > 1:
                    fila.append(str(pz["cant"] * Nc))
                filas.append(fila)
            cols = ["Panel", "Nombre", "Medida (mm)", "Esp.", "C/U"] + (["Total"] if Nc > 1 else [])
            anchos = [0.08, 0.5, 0.2, 0.08, 0.07] + ([0.09] if Nc > 1 else [])
            fig.text(0.52, 0.86, "Lista de paneles" + (f"  (para {Nc} cases)" if Nc > 1 else ""),
                     fontsize=12, weight="bold", va="top")
            ax = fig.add_axes([0.52, 0.08, 0.45, 0.74])
            ax.axis("off")
            tb = ax.table(cellText=filas, colLabels=cols, colWidths=anchos, loc="upper left",
                          cellLoc="left")
            tb.auto_set_font_size(False)
            n_lin_tab = sum(f[1].count("\n") + 1 for f in filas)
            tb.set_fontsize(8.5 if n_lin_tab <= 22 else 7)
            tb.scale(1, 1.4 if n_lin_tab <= 22 else 1.15)
            # filas más altas cuando el nombre ocupa varias líneas
            for (r, c), cel in tb.get_celld().items():
                if r > 0:
                    cel.set_height(cel.get_height() * (filas[r - 1][1].count("\n") + 1))
            for (r, c), cel in tb.get_celld().items():
                if r == 0:
                    cel.set_text_props(weight="bold")
                    cel.set_facecolor("#eeeeee")
                if c == 0:
                    cel.set_text_props(weight="bold")
        pdf.savefig(fig)
        plt.close(fig)
    pdf.close()
