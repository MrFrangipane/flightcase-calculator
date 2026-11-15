"""Reglas de construcción del taller: traducción a Python de flightcase_gen/flightcase.scad.

Calcula, a partir de los parámetros de un proyecto, lo mismo que la parte "datos" del
generador de OpenSCAD: paneles, calados, marcas, perfiles, herrajes y avisos. Los
nombres de variables siguen a los del .scad para poder compararlos línea a línea.
Las medidas están en milímetros. Ejes: X = ancho (frente), Y = profundidad, Z = alto.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..paths import bundled_resource

TRAMO_MINIMO = 30.0  # tramos de perfil más cortos se omiten (el esquinero llega al cierre)


# ---------------------------------------------------------------------------
# Formato de números y textos igual que str() de OpenSCAD
# ---------------------------------------------------------------------------

def fmt(x: Any) -> str:
    if isinstance(x, bool):
        return "true" if x else "false"
    if isinstance(x, (int, float)):
        if isinstance(x, float) and (math.isinf(x) or math.isnan(x)):
            return "inf" if x > 0 else ("-inf" if x < 0 else "nan")
        if float(x) == int(round(float(x))) and abs(x) < 1e15:
            return str(int(round(float(x))))
        s = f"{float(x):.6g}"
        return s
    if isinstance(x, list):
        return "[" + ", ".join(fmt(v) if not isinstance(v, str) else f'"{v}"' for v in x) + "]"
    if x is None:
        return "undef"
    return str(x)


def s(*partes: Any) -> str:
    return "".join(fmt(p) for p in partes)


def round_os(x: float) -> float:
    """round() de OpenSCAD: mitades lejos del cero."""
    return math.floor(x + 0.5) if x >= 0 else -math.floor(-x + 0.5)


# ---------------------------------------------------------------------------
# Catálogo de herrajes
# ---------------------------------------------------------------------------

class CatalogoTaller:
    def __init__(self, filas: Optional[List[Dict[str, Any]]] = None) -> None:
        if filas is None:
            filas = json.loads(bundled_resource("catalogo_fr.json").read_text(encoding="utf-8"))
        self.filas = filas
        self._por_ref = {}
        for f in filas:
            self._por_ref.setdefault(f["ref"], f)

    def fila(self, ref: str):
        return self._por_ref.get(ref) if ref else None

    def existe(self, ref: str) -> bool:
        return bool(ref) and ref in self._por_ref

    def nombre(self, ref: str) -> str:
        return self._por_ref[ref]["nombre"] if self.existe(ref) else ref

    def categoria(self, ref: str) -> str:
        return self._por_ref[ref]["categoria"] if self.existe(ref) else ""

    def verificado(self, ref: str) -> bool:
        return self._por_ref[ref]["verificado"] if self.existe(ref) else True

    def dato(self, ref: str, clave: str, defecto: Any) -> Any:
        if not self.existe(ref):
            return defecto
        return self._por_ref[ref]["datos"].get(clave, defecto)


def parametros_por_defecto() -> Dict[str, Any]:
    return json.loads(bundled_resource("taller_parametros.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Resultado
# ---------------------------------------------------------------------------

@dataclass
class Panel:
    id: str
    nombre: str
    grupo: str
    ancho: float
    alto: float


@dataclass
class Calado:
    panel: str
    tipo: str
    cx: float
    cy: float
    ancho: float
    alto: float
    radio: float


@dataclass
class Marca:
    panel: str
    tipo: str
    x: float
    y: float
    ancho: float
    alto: float
    texto: str


@dataclass
class Perfil:
    nombre: str
    descripcion: str
    largo: float
    cantidad: int
    corte: str
    ref: str


@dataclass
class Herraje:
    nombre: str
    cantidad: int
    detalle: str
    ref: str


@dataclass
class ResultadoTaller:
    info: Dict[str, List[str]]
    paneles: List[Panel]
    calados: List[Calado]
    marcas: List[Marca]
    perfiles: List[Perfil]
    extras: List[list]
    herrajes: List[Herraje]
    panelmat: List[list]
    bandejas: List[list]
    avisos: List[str]
    valores: Dict[str, Any] = field(default_factory=dict)

    def panel(self, pid: str) -> Optional[Panel]:
        return next((p for p in self.paneles if p.id == pid), None)


# ---------------------------------------------------------------------------
# Cálculo
# ---------------------------------------------------------------------------

def _pos_n(L: float, n: int, margen: float) -> List[float]:
    if n == 1:
        return [L / 2]
    return [margen + i * (L - 2 * margen) / (n - 1) for i in range(n)]


def calcular(params: Optional[Dict[str, Any]] = None, catalogo: Optional[CatalogoTaller] = None) -> ResultadoTaller:
    P = parametros_por_defecto()
    if params:
        P.update(params)
    cat = catalogo or CatalogoTaller()
    g = P.get

    int_ancho = g("int_ancho"); int_prof = g("int_prof")
    int_alto_cuerpo = g("int_alto_cuerpo"); int_alto_tapa = g("int_alto_tapa")
    tapas = g("tapas"); int_alto_tapa2 = g("int_alto_tapa2"); orientacion = g("orientacion")
    descuento_entre = g("descuento_entre")
    acceso_lateral = g("acceso_lateral"); acceso_junta = g("acceso_junta")
    acceso_cierres_n = g("acceso_cierres_n"); acceso_tipo = g("acceso_tipo")
    paredes_enteras = g("paredes_enteras"); paredes_enteras_cuerpo = g("paredes_enteras_cuerpo")
    cantidad_cases = g("cantidad_cases"); extremos_cubren = g("extremos_cubren")
    manijas_en = g("manijas_en"); piezas_extra = g("piezas_extra")
    placa_esp = g("placa_esp"); placa_material = g("placa_material")
    sistema = g("sistema"); angulo_ala = g("angulo_ala"); angulo_esp = g("angulo_esp")
    hibrido_descuento = g("hibrido_descuento"); hibrido_pared = g("hibrido_pared")
    esq_pata = g("esq_pata"); esq_descuento = g("esq_descuento")
    cierre_m_alto = g("cierre_m_alto"); cierre_m_sup = g("cierre_m_sup")
    cierre_h_alto = g("cierre_h_alto"); cierre_h_sup = g("cierre_h_sup")
    cierre_saliente = g("cierre_saliente"); cierre_hibrido = g("cierre_hibrido")
    manijas = g("manijas"); manija_corte_ancho = g("manija_corte_ancho"); manija_corte_alto = g("manija_corte_alto")
    manija_corte_radio = g("manija_corte_radio"); manija_centro_desde_arriba = g("manija_centro_desde_arriba")
    manijas_n = g("manijas_n"); manija_sep = g("manija_sep"); manija_pos = g("manija_pos")
    cierre_margen = g("cierre_margen"); cierres_laterales = g("cierres_laterales")
    cierres_frente_n = g("cierres_frente_n"); cierres_lateral_n = g("cierres_lateral_n")
    ruedas = g("ruedas"); rueda_diametro = g("rueda_diametro"); rueda_alto = g("rueda_alto")
    rueda_frenos = g("rueda_frenos"); rueda_placa = g("rueda_placa"); rueda_agujeros = g("rueda_agujeros")
    rueda_agujero_d = g("rueda_agujero_d"); rueda_margen = g("rueda_margen")
    base_ruedas = g("base_ruedas"); base_material = g("base_material"); base_pasantes = g("base_pasantes")
    bandejas = g("bandejas"); bandeja_soportes = g("bandeja_soportes"); ref_escuadra = g("ref_escuadra")
    encastres = g("encastres"); encastre_corte = g("encastre_corte"); encastre_radio = g("encastre_radio")
    encastre_ala = g("encastre_ala"); encastre_profundidad = g("encastre_profundidad")
    encastre_remaches = g("encastre_remaches")
    barra_largo = g("barra_largo"); sierra_kerf = g("sierra_kerf")
    placa_largo = g("placa_largo"); placa_ancho = g("placa_ancho"); placa_kerf = g("placa_kerf")
    placa_margen = g("placa_margen"); remache_paso = g("remache_paso"); remache_d = g("remache_d")
    ref_placa = g("ref_placa"); ref_angulo = g("ref_angulo"); ref_hibrido = g("ref_hibrido")
    ref_cierre_macho = g("ref_cierre_macho"); ref_cierre_hembra = g("ref_cierre_hembra")
    ref_esquinero = g("ref_esquinero"); ref_cierre = g("ref_cierre"); ref_manija = g("ref_manija")
    ref_rueda = g("ref_rueda"); ref_rueda_freno = g("ref_rueda_freno"); ref_plato = g("ref_plato")
    ref_remache = g("ref_remache"); usar_catalogo_remaches = g("usar_catalogo_remaches")
    pies = g("pies"); ref_pie = g("ref_pie"); pie_diametro = g("pie_diametro"); pie_alto = g("pie_alto")
    bisagras = g("bisagras"); ref_bisagra = g("ref_bisagra"); topes = g("topes")
    refuerzos = g("refuerzos"); refuerzo_nombre = g("refuerzo_nombre"); refuerzo_ala = g("refuerzo_ala")
    refuerzo_alto = g("refuerzo_alto"); refuerzo_remaches = g("refuerzo_remaches"); refuerzo_esp = g("refuerzo_esp")
    rebaje_refuerzos = g("rebaje_refuerzos"); rebaje_holgura = g("rebaje_holgura")
    ref_tope = g("ref_tope"); espuma_esp = g("espuma_esp"); ref_espuma = g("ref_espuma"); extras = g("extras")
    color_placa = g("color_placa"); color_tapa = g("color_tapa")
    cd = cat.dato; ce = cat.existe

    # ---- valores efectivos según catálogo ----
    E_placa_esp = cd(ref_placa, "esp", placa_esp)
    E_placa_material = cat.nombre(ref_placa) if ce(ref_placa) else placa_material
    E_placa_largo = cd(ref_placa, "largo", placa_largo)
    E_placa_ancho = cd(ref_placa, "ancho", placa_ancho)
    E_angulo_ala = cd(ref_angulo, "ala", angulo_ala)
    E_angulo_esp = cd(ref_angulo, "esp", angulo_esp)
    E_esq_pata = cd(ref_esquinero, "pata", esq_pata)
    _esq_paso = cd(ref_esquinero, "paso", 0)
    E_esq_descuento = esq_descuento if not ce(ref_esquinero) else (15 if _esq_paso > 0 else E_esq_pata + 2)
    _esq_remaches = cd(ref_esquinero, "remaches", 3)

    _man_cat = ce(ref_manija)
    _man_emb = cd(ref_manija, "tipo", "embutida") == "embutida"
    _corte_def = [manija_corte_ancho, manija_corte_alto]
    E_manija_corte_ancho = cd(ref_manija, "corte", _corte_def)[0] if _man_cat else manija_corte_ancho
    E_manija_corte_alto = cd(ref_manija, "corte", _corte_def)[1] if _man_cat else manija_corte_alto
    E_manija_corte_radio = cd(ref_manija, "radio", manija_corte_radio)
    _man_remaches = cd(ref_manija, "remaches", 6)

    _cie_tipo = cd(ref_cierre, "tipo", "superficie")
    _cie_emb = _cie_tipo == "embutido"
    _cie_corte = cd(ref_cierre, "corte", [0, 0])
    _cie_radio = cd(ref_cierre, "radio", 8)
    _cie_remaches = cd(ref_cierre, "remaches", 6)

    _rueda_ref_geo = ref_rueda_freno if ref_rueda_freno != "" else ref_rueda
    E_rueda_diametro = cd(_rueda_ref_geo, "diametro", rueda_diametro)
    E_rueda_alto = cd(_rueda_ref_geo, "alto", rueda_alto)
    E_rueda_placa = cd(_rueda_ref_geo, "placa", rueda_placa)
    E_rueda_agujeros = cd(_rueda_ref_geo, "agujeros", rueda_agujeros)
    E_rueda_agujero_d = 0 if rueda_agujero_d == 0 else cd(_rueda_ref_geo, "agujero_d", rueda_agujero_d)

    _pla_cat = ce(ref_plato)
    E_encastre_corte = cd(ref_plato, "corte", encastre_corte)
    E_encastre_radio = cd(ref_plato, "radio", encastre_radio)
    E_encastre_ala = ((cd(ref_plato, "exterior", E_encastre_corte)[1] - E_encastre_corte[1]) / 2) if _pla_cat else encastre_ala
    E_encastre_profundidad = cd(ref_plato, "prof", encastre_profundidad)
    E_encastre_remaches = cd(ref_plato, "remaches", encastre_remaches)

    _espuma = cd(ref_espuma, "esp", 0) if ce(ref_espuma) else espuma_esp

    # remache: el elegido o el más corto del catálogo que alcance
    _hib = sistema == "hibrido"
    _rem_l_min = E_placa_esp + (hibrido_pared if _hib else E_angulo_esp) + 3
    remaches_cat = [f["ref"] for f in cat.filas if f["categoria"] == "remache"]
    _rem_cands_d = [r for r in remaches_cat if cd(r, "d", 0) == remache_d and cd(r, "l", 0) >= _rem_l_min]
    _rem_cands = _rem_cands_d if _rem_cands_d else [r for r in remaches_cat if cd(r, "l", 0) >= _rem_l_min]
    _rem_l_best = min([cd(r, "l", 999) for r in _rem_cands] + [999])
    if ref_remache != "":
        E_remache_ref = ref_remache
    elif usar_catalogo_remaches:
        cands = [r for r in _rem_cands if cd(r, "l", 0) == _rem_l_best]
        E_remache_ref = cands[0] if cands else None
    else:
        E_remache_ref = None
    E_remache_d = cd(E_remache_ref or "", "d", remache_d)

    # ---- medidas interiores (con espuma crece el case) ----
    E_int_ancho = int_ancho + 2 * _espuma
    E_int_prof = int_prof + 2 * _espuma
    E_int_alto_cuerpo = int_alto_cuerpo + _espuma
    E_int_alto_tapa = int_alto_tapa + _espuma

    _t = E_placa_esp
    _d = hibrido_descuento if _hib else 0
    _hp = hibrido_pared if _hib else 0
    pared = _t + _hp

    _2t = tapas == 2
    _hz = orientacion == "horizontal"
    _fr = orientacion == "frontal"
    _acost = _hz or _fr
    _fe = paredes_enteras != "laterales"
    _fec = (paredes_enteras if paredes_enteras_cuerpo == "" else paredes_enteras_cuerpo) != "laterales"
    _ce = _t if (extremos_cubren and not _hib) else 0
    E_int_alto_tapa2 = (int_alto_tapa if int_alto_tapa2 < 0 else int_alto_tapa2) + _espuma

    ext_ancho = E_int_ancho + 2 * pared
    ext_prof = E_int_prof + 2 * pared
    ext_alto_tapa2 = E_int_alto_tapa2 + pared if _2t else 0
    ext_alto_cuerpo = E_int_alto_cuerpo if _2t else E_int_alto_cuerpo + pared
    ext_alto_tapa = E_int_alto_tapa + pared
    ext_alto = ext_alto_tapa2 + ext_alto_cuerpo + ext_alto_tapa
    z_cierre2 = ext_alto_tapa2
    z_cierre = ext_alto_tapa2 + ext_alto_cuerpo
    mundo_largo = ext_alto if _hz else ext_ancho
    mundo_prof = ext_alto if _fr else ext_prof
    mundo_alto = ext_ancho if _hz else (ext_prof if _fr else ext_alto)

    h_pared_cuerpo = ext_alto_cuerpo - 2 * cierre_m_sup if _2t else ext_alto_cuerpo - cierre_m_sup - _d - _ce
    h_pared_tapa = ext_alto_tapa - cierre_h_sup - _d - _ce
    h_pared_tapa2 = ext_alto_tapa2 - cierre_h_sup - _d - _ce
    z0_cuerpo = z_cierre2 + cierre_m_sup if _2t else _d + _ce

    _de = descuento_entre
    w_frente = ext_ancho - 2 * _d if _hib else (ext_ancho if _fe else ext_ancho - 2 * _t - _de)
    w_lateral = ext_prof - 2 * _d if _hib else (ext_prof - 2 * _t - _de if _fe else ext_prof)
    w_piso = ext_ancho - 2 * _d if _hib else (ext_ancho if _ce > 0 else ext_ancho - 2 * _t - _de)
    d_piso = ext_prof - 2 * _d if _hib else (ext_prof if _ce > 0 else ext_prof - 2 * _t - _de)

    off_frente = _d if _hib else (0 if _fe else _t + _de / 2)
    off_lateral = _d if _hib else (_t + _de / 2 if _fe else 0)
    wfc = w_frente if _hib else (ext_ancho if _fec else ext_ancho - 2 * _t - _de)
    wlc = w_lateral if _hib else (ext_prof - 2 * _t - _de if _fec else ext_prof)
    ofc = _d if _hib else (0 if _fec else _t + _de / 2)
    olc = _d if _hib else (_t + _de / 2 if _fec else 0)
    _ala_arista = 15 if _hib else E_angulo_ala

    # ---- tapa de acceso lateral ----
    junta_inglete = True
    _acc = acceso_lateral > 0 and not _hz
    _cub = _acc and acceso_tipo == "cubierta" and _fr
    _ing_junta = _cub and cierre_hibrido and junta_inglete
    _a_acc = acceso_lateral
    _j_acc = cierre_m_sup + cierre_h_sup if acceso_junta < 0 else acceso_junta
    _w_low = wlc - _a_acc - _j_acc

    def lat_pieza(cara, x):
        if not _acc:
            return [f"cuerpo_{cara}", x]
        if cara == "izq":
            return ["acceso_izq", x] if x < _a_acc else ["cuerpo_izq", x - _a_acc - _j_acc]
        return ["cuerpo_der", x] if x < _w_low else ["acceso_der", x - _w_low - _j_acc]

    def _band_esp(b):
        return b[3] if len(b) > 3 else E_placa_esp

    def _band_mat(b):
        return b[4] if len(b) > 4 else (s("Placa ", b[3], " mm") if len(b) > 3 else E_placa_material)

    # ---- nombres ----
    _t1 = " tapa del." if _fr else ((" tapa izq." if _hz else " tapa sup.") if _2t else " tapa")
    _t2 = " tapa tras." if _fr else (" tapa der." if _hz else " tapa inf.")

    def nombre_panel(pid):
        if pid == "piso":
            return "Piso (cuerpo)"
        if pid == "techo":
            return "Cara tapa delantera" if _fr else (("Cara tapa izq." if _2t else "Cara de la tapa") if _hz else ("Techo (tapa sup.)" if _2t else "Techo (tapa)"))
        if pid == "base2":
            return "Cara tapa trasera" if _fr else ("Cara tapa der." if _hz else "Fondo (tapa inf.)")
        if pid == "cuerpo_frente":
            return "Piso cuerpo" if _fr else "Frente cuerpo"
        if pid == "cuerpo_trasera":
            return ("Techo cuerpo (cubierta)" if _cub else "Techo cuerpo") if _fr else "Trasera cuerpo"
        if pid == "cuerpo_izq":
            return "Piso cuerpo" if _hz else "Lateral izq. cuerpo" + (" (parte fija)" if _acc else "")
        if pid == "cuerpo_der":
            return "Techo cuerpo" if _hz else "Lateral der. cuerpo" + (" (parte fija)" if _acc else "")
        if pid == "base_ruedas":
            return "Base de ruedas"
        if pid.startswith("bandeja"):
            return s("Bandeja interna ", int(pid[7:]) + 1) if len(bandejas) > 1 else "Bandeja interna"
        if pid == "acceso_izq":
            return "Lateral izq. de la cubierta" if _cub else "Tapa de acceso izq."
        if pid == "acceso_der":
            return "Lateral der. de la cubierta" if _cub else "Tapa de acceso der."
        for pre, suf in (("tapa_", _t1), ("tapa2_", _t2)):
            if pid.startswith(pre):
                cara = pid[len(pre):]
                if cara == "frente":
                    return ("Piso" if _fr else "Frente") + suf
                if cara == "trasera":
                    return ("Techo" if _fr else "Trasera") + suf
                if cara == "izq":
                    return ("Piso" if _hz else "Lateral izq.") + suf
                if cara == "der":
                    return ("Techo" if _hz else "Lateral der.") + suf
        return pid

    # ---- paneles ----
    filas_p = []
    if not _2t:
        filas_p.append(["piso", "cuerpo", w_piso, d_piso])
    filas_p += [["cuerpo_frente", "cuerpo", wfc, h_pared_cuerpo],
                ["cuerpo_trasera", "cuerpo", wfc, h_pared_cuerpo],
                ["cuerpo_izq", "cuerpo", _w_low if _acc else wlc, h_pared_cuerpo],
                ["cuerpo_der", "cuerpo", _w_low if _acc else wlc, h_pared_cuerpo]]
    if _acc:
        filas_p += [["acceso_izq", "cuerpo", _a_acc, h_pared_cuerpo], ["acceso_der", "cuerpo", _a_acc, h_pared_cuerpo]]
    filas_p += [["techo", "tapa", w_piso, d_piso],
                ["tapa_frente", "tapa", w_frente, h_pared_tapa],
                ["tapa_trasera", "tapa", w_frente, h_pared_tapa],
                ["tapa_izq", "tapa", w_lateral, h_pared_tapa],
                ["tapa_der", "tapa", w_lateral, h_pared_tapa]]
    if _2t:
        filas_p += [["base2", "tapa2", w_piso, d_piso],
                    ["tapa2_frente", "tapa2", w_frente, h_pared_tapa2],
                    ["tapa2_trasera", "tapa2", w_frente, h_pared_tapa2],
                    ["tapa2_izq", "tapa2", w_lateral, h_pared_tapa2],
                    ["tapa2_der", "tapa2", w_lateral, h_pared_tapa2]]
    if len(base_ruedas) >= 2:
        filas_p.append(["base_ruedas", "cuerpo", base_ruedas[0], base_ruedas[1]])
    for i, b in enumerate(bandejas):
        filas_p.append([f"bandeja{i}", "cuerpo", b[0], b[1]])
    paneles = [Panel(p[0], nombre_panel(p[0]), p[1], p[2], p[3]) for p in filas_p]
    por_id = {p.id: p for p in paneles}
    _panel_base = "cuerpo_izq" if _hz else ("cuerpo_frente" if _fr else ("base2" if _2t else "piso"))

    # ---- manijas ----
    _man_lugar = ("frente" if _hz else "laterales") if manijas_en == "auto" else manijas_en
    _man_paneles = ["cuerpo_frente", "cuerpo_trasera"] if _man_lugar == "frente" else ["cuerpo_izq", "cuerpo_der"]
    _man_w_panel = wfc if _man_lugar == "frente" else (_w_low if _acc else wlc)
    _man_wl = E_manija_corte_alto if _acost else E_manija_corte_ancho
    _man_hl = E_manija_corte_ancho if _acost else E_manija_corte_alto
    _man_cy = h_pared_cuerpo / 2 if (_2t or _acost) else h_pared_cuerpo - manija_centro_desde_arriba
    _man_cx0 = _man_w_panel / 2
    _man_n = max(1, min(2, manijas_n))
    if manija_sep > 0:
        _man_sep = manija_sep
    else:
        _man_sep = max(h_pared_cuerpo / 3, _man_hl + 60) if _acost else max(_man_w_panel / 3, _man_wl + 60)

    def _man_pos(p):
        if _fr and _man_lugar == "laterales":
            fx = _man_w_panel * (1 - manija_pos) if p == "cuerpo_izq" else _man_w_panel * manija_pos
        else:
            fx = _man_cx0
        out = []
        for i in range(_man_n):
            o = 0 if _man_n == 1 else (-1 if i == 0 else 1) * _man_sep / 2
            out.append([fx, _man_cy + o] if _acost else [_man_cx0 + o, _man_cy])
        return out

    # ---- ruedas, base, platos y pies ----
    _rueda_m = E_esq_pata + rueda_margen
    _piso_ox = (ext_ancho - w_piso) / 2
    _piso_oy = (ext_prof - d_piso) / 2
    _pb = por_id.get(_panel_base)
    _base = len(base_ruedas) >= 2
    _bx = base_ruedas[0] if _base else 0
    _by = base_ruedas[1] if _base else 0
    _bt = (base_ruedas[2] if len(base_ruedas) > 2 else 18) if _base else 0
    _bgap = hibrido_pared if _hib else E_angulo_esp
    _bo = [_pb.ancho / 2 - _bx / 2, _pb.alto / 2 - _by / 2] if _base else [0, 0]
    _bm = rueda_margen + 10
    _bl_offx = (olc if _hz else ofc) if _acost else _piso_ox
    _bl_x = max(_ala_arista, refuerzo_ala + rebaje_holgura if (_acost and refuerzos > 0) else 0) - _bl_offx + 10
    _bl_ylo = (((cierre_m_alto - cierre_m_sup) if _2t else _ala_arista - z0_cuerpo) + 10) if _acost else _ala_arista - _piso_oy + 10
    _bl_yhi = (cierre_m_alto - cierre_m_sup) + 10 if _acost else _ala_arista - _piso_oy + 10
    _bh = [E_rueda_agujeros[0] / 2 + E_rueda_agujero_d / 2, E_rueda_agujeros[1] / 2 + E_rueda_agujero_d / 2]
    _bp = _base and base_pasantes
    _rx0 = max(_bo[0] + _bm + E_rueda_placa[0] / 2, _bl_x + _bh[0] if _bp else -1e9)
    _rx1 = min(_bo[0] + _bx - _bm - E_rueda_placa[0] / 2, _pb.ancho - _bl_x - _bh[0] if _bp else 1e9)
    _ry0 = max(_bo[1] + _bm + E_rueda_placa[1] / 2, _bl_ylo + _bh[1] if _bp else -1e9)
    _ry1 = min(_bo[1] + _by - _bm - E_rueda_placa[1] / 2, _pb.alto - _bl_yhi - _bh[1] if _bp else 1e9)
    ruedas_en_base = ([[(_rx0 if sx == 0 else _rx1) - _bo[0], (_ry0 if sy == 0 else _ry1) - _bo[1]]
                       for sx in (0, 1) for sy in (0, 1)] if (_base and ruedas == 4) else [])
    _enc_ext = [E_encastre_corte[0] + 2 * E_encastre_ala, E_encastre_corte[1] + 2 * E_encastre_ala]
    _enc_m = max(E_esq_pata, _ala_arista) + rueda_margen
    _off_rx = max(_rueda_m + E_rueda_placa[0] / 2, _enc_m + _enc_ext[0] / 2 if encastres else 0)
    _off_ry = max(_rueda_m + E_rueda_placa[1] / 2, _enc_m + _enc_ext[1] / 2 if encastres else 0)
    if _base and not _acost and ruedas == 4:
        pos_ruedas = [[c[0] + _bo[0] + _piso_ox, c[1] + _bo[1] + _piso_oy] for c in ruedas_en_base]
    else:
        pos_ruedas = [[_off_rx if sx == 0 else ext_ancho - _off_rx, _off_ry if sy == 0 else ext_prof - _off_ry]
                      for sx in (0, 1) for sy in (0, 1)]
    ruedas_centros = pos_ruedas if (ruedas == 4 and not _acost) else []
    encastres_centros = pos_ruedas if (encastres and not _acost) else []

    _pb_offx = olc if _hz else ofc
    _pb_ylo = (cierre_m_alto - cierre_m_sup) if _2t else max(E_esq_pata, _ala_arista) - z0_cuerpo
    _pb_yhi = cierre_m_alto - cierre_m_sup

    def _base_pos(w, h):
        if not _acost:
            return []
        m = max(E_esq_pata, _ala_arista) + rueda_margen - _pb_offx
        return [[m + w / 2 if sx == 0 else _pb.ancho - m - w / 2,
                 _pb_ylo + rueda_margen + h / 2 if sy == 0 else _pb.alto - _pb_yhi - rueda_margen - h / 2]
                for sx in (0, 1) for sy in (0, 1)]

    if ruedas != 4:
        ruedas_base = []
    elif _base:
        ruedas_base = [[c[0] + _bo[0], c[1] + _bo[1]] for c in ruedas_en_base]
    elif _acost:
        ruedas_base = _base_pos(E_rueda_placa[0], E_rueda_placa[1])
    else:
        ruedas_base = [[c[0] - _piso_ox, c[1] - _piso_oy] for c in ruedas_centros]

    _pie_d = cd(ref_pie, "diametro", pie_diametro)
    _pie_h = cd(ref_pie, "alto", pie_alto)
    _pie_o = max(E_esq_pata, _ala_arista) + rueda_margen + _pie_d / 2
    pies_centros = ([[_pie_o if sx == 0 else ext_ancho - _pie_o, _pie_o if sy == 0 else ext_prof - _pie_o]
                     for sx in (0, 1) for sy in (0, 1)] if (pies == 4 and not _acost) else [])

    # ---- cierres y bisagras ----
    def n_cierres(L):
        return 1 if L <= 450 else (2 if L <= 1000 else 3)

    def pos_cierres(L):
        return _pos_n(L, n_cierres(L), cierre_margen)

    def _pos_c(L, n):
        return _pos_n(L, n, cierre_margen) if n > 0 else pos_cierres(L)

    _lat_cierres = True if cierres_laterales == "si" else (False if cierres_laterales == "no" else ext_prof > 450)
    _caras_lat = (["der"] if _hz else ["izq", "der"]) if _lat_cierres else []
    _piano = ce(ref_bisagra) and cd(ref_bisagra, "largo", 0) > 0
    _con_bisagras = bisagras > 0
    _y_cierre_cuerpo = h_pared_cuerpo - (cierre_m_alto - cierre_m_sup)
    _y_cierre_tapa = cierre_h_alto - cierre_h_sup
    _y_cierre2_cuerpo = cierre_m_alto - cierre_m_sup
    _y_cierre2_tapa = h_pared_tapa2 - (cierre_h_alto - cierre_h_sup)
    _sin_frente = cierres_frente_n < 0
    _caras_c1 = ([] if (_fr or _sin_frente) else ["frente"]) + ([] if (_con_bisagras or _sin_frente) else ["trasera"]) + _caras_lat
    _caras_c2 = (([] if (_fr or _sin_frente) else ["frente"]) + ([] if _sin_frente else ["trasera"]) + _caras_lat) if _2t else []

    def _xs_cara(c, of=off_frente, ol=off_lateral):
        if c in ("frente", "trasera"):
            return [x - of for x in _pos_c(ext_ancho, cierres_frente_n)]
        return [x - ol for x in _pos_c(ext_prof, cierres_lateral_n)]

    marcas: List[Marca] = []
    for plano, caras, y_cuerpo, pre_tapa, y_tapa in (
        ("c1", _caras_c1, _y_cierre_cuerpo, "tapa_", _y_cierre_tapa),
        ("c2", _caras_c2, _y_cierre2_cuerpo, "tapa2_", _y_cierre2_tapa),
    ):
        for c in caras:
            xs = _xs_cara(c)
            xcs = _xs_cara(c, ofc, olc)
            for k in range(len(xs)):
                x, xc = xs[k], xcs[k]
                lp = lat_pieza(c, xc) if c in ("izq", "der") else [f"cuerpo_{c}", xc]
                marcas.append(Marca(lp[0], "cierre", lp[1], y_cuerpo, 0, 0, plano))
                marcas.append(Marca(f"{pre_tapa}{c}", "cierre", x, y_tapa, 0, 0, plano))
    if _con_bisagras and not _piano:
        for x in _pos_n(ext_ancho, bisagras, cierre_margen):
            marcas.append(Marca("cuerpo_trasera", "bisagra", x - ofc, _y_cierre_cuerpo, 0, 0, "c1"))
            marcas.append(Marca("tapa_trasera", "bisagra", x - off_frente, _y_cierre_tapa, 0, 0, "c1"))
    for i in range(len(ruedas_base)):
        txt = "freno" if i < rueda_frenos else "placa rueda"
        if _base:
            marcas.append(Marca("base_ruedas", "rueda", ruedas_en_base[i][0], ruedas_en_base[i][1], E_rueda_placa[0], E_rueda_placa[1], txt))
        else:
            marcas.append(Marca(_panel_base, "rueda", ruedas_base[i][0], ruedas_base[i][1], E_rueda_placa[0], E_rueda_placa[1], txt))
    if pies == 4:
        lista = _base_pos(_pie_d, _pie_d) if _acost else [[q[0] - _piso_ox, q[1] - _piso_oy] for q in pies_centros]
        for c in lista:
            marcas.append(Marca(_panel_base, "pie", c[0], c[1], _pie_d, _pie_d, "pie"))
    if _acc:
        for cara in ("izq", "der"):
            for y in _pos_n(h_pared_cuerpo, acceso_cierres_n, cierre_margen):
                marcas.append(Marca(f"cuerpo_{cara}", "cierre_acceso",
                                    cierre_m_alto - cierre_m_sup if cara == "izq" else _w_low - (cierre_m_alto - cierre_m_sup),
                                    y, 0, 0, "-" if cara == "izq" else "+"))
                marcas.append(Marca(f"acceso_{cara}", "cierre_acceso",
                                    _a_acc - (cierre_h_alto - cierre_h_sup) if cara == "izq" else cierre_h_alto - cierre_h_sup,
                                    y, 0, 0, "+" if cara == "izq" else "-"))
    if manijas and not _man_emb:
        for p in _man_paneles:
            for q in _man_pos(p):
                marcas.append(Marca(p, "manija_sup", q[0], q[1], _man_wl, _man_hl, "asa de superficie"))

    # ---- rebajes en la base de ruedas ----
    _rb_x1 = refuerzo_ala - _pb_offx - _bo[0] + rebaje_holgura
    _rb_y0 = max(0, _pb_yhi - _bo[1] - rebaje_holgura)
    _rb_y1 = min(_by / 2, _pb_yhi + refuerzo_alto - _bo[1] + rebaje_holgura)
    _rebajes = []
    if _base and _acost and refuerzos > 0 and rebaje_refuerzos and _rb_x1 > 0 and _rb_y1 > _rb_y0:
        for sx in (0, 1):
            for sy in (0, 1):
                _rebajes.append(Calado("base_ruedas", "rebaje", _rb_x1 / 2 if sx == 0 else _bx - _rb_x1 / 2,
                                       (_rb_y0 + _rb_y1) / 2 if sy == 0 else _by - (_rb_y0 + _rb_y1) / 2,
                                       _rb_x1, _rb_y1 - _rb_y0, 0))

    # ---- calados ----
    calados: List[Calado] = []
    if manijas and _man_emb:
        for p in _man_paneles:
            for q in _man_pos(p):
                calados.append(Calado(p, "manija", q[0], q[1], _man_wl, _man_hl, E_manija_corte_radio))
    if _cie_emb:
        for m in marcas:
            if m.tipo == "cierre" and por_id[m.panel].grupo == "cuerpo":
                cy = m.y - 2 - _cie_corte[1] / 2 if m.texto == "c1" else m.y + 2 + _cie_corte[1] / 2
                calados.append(Calado(m.panel, "cierre", m.x, cy, _cie_corte[0], _cie_corte[1], _cie_radio))
    if E_rueda_agujero_d > 0 and (not _base or base_pasantes):
        for c in ruedas_base:
            for ax in (-1, 1):
                for ay in (-1, 1):
                    calados.append(Calado(_panel_base, "agujero", c[0] + ax * E_rueda_agujeros[0] / 2,
                                          c[1] + ay * E_rueda_agujeros[1] / 2, E_rueda_agujero_d, E_rueda_agujero_d, E_rueda_agujero_d / 2))
    if E_rueda_agujero_d > 0 and _base:
        for c in ruedas_en_base:
            for ax in (-1, 1):
                for ay in (-1, 1):
                    calados.append(Calado("base_ruedas", "agujero", c[0] + ax * E_rueda_agujeros[0] / 2,
                                          c[1] + ay * E_rueda_agujeros[1] / 2, E_rueda_agujero_d, E_rueda_agujero_d, E_rueda_agujero_d / 2))
    calados += _rebajes
    for c in encastres_centros:
        calados.append(Calado("techo", "encastre", c[0] - _piso_ox, c[1] - _piso_oy, E_encastre_corte[0], E_encastre_corte[1], E_encastre_radio))

    # ---- perfiles ----
    _L_x = ext_ancho - 2 * E_esq_descuento
    _L_y = ext_prof - 2 * E_esq_descuento
    _L_zc = ext_alto_cuerpo - 2 * cierre_m_alto if _2t else ext_alto_cuerpo - cierre_m_alto - E_esq_descuento
    _L_zt = ext_alto_tapa - cierre_h_alto - E_esq_descuento
    _L_zt2 = ext_alto_tapa2 - cierre_h_alto - E_esq_descuento
    _n_ax = "Aristas horizontales de las caras" if _fr else ("Aristas verticales de las caras" if _hz else ("Aristas a lo ancho (extremos)" if _2t else "Aristas a lo ancho (piso y techo)"))
    _n_ay = "Aristas verticales de las caras" if _fr else ("Aristas a lo profundo de las caras" if _hz else ("Aristas a lo profundo (extremos)" if _2t else "Aristas a lo profundo (piso y techo)"))
    _n_vz = "Aristas a lo profundo" if _fr else ("Largueros" if _hz else "Verticales")
    _n_rings = 4 if _2t else 2
    _j_cub = olc + _a_acc + _j_acc / 2
    _ref_arista = ref_hibrido if _hib else ref_angulo
    _perfil_arista = cat.nombre(_ref_arista) if ce(_ref_arista) else ("Perfil híbrido" if _hib else s("Ángulo ", E_angulo_ala, "x", E_angulo_ala, "x", E_angulo_esp))
    _perfil_macho = "Perfil híbrido" if cierre_hibrido else (cat.nombre(ref_cierre_macho) if ce(ref_cierre_macho) else "Cierre macho")
    _perfil_hembra = _perfil_macho if cierre_hibrido else (cat.nombre(ref_cierre_hembra) if ce(ref_cierre_hembra) else "Cierre hembra")
    _ref_cm = "" if cierre_hibrido else ref_cierre_macho
    _ref_ch = "" if cierre_hibrido else ref_cierre_hembra
    _lados_a = "Lados verticales (punta larga)" if _hz else ("Lados horizontales (punta larga)" if _fr else "Frente y trasera (punta larga)")
    _lados_b = "Lados horizontales (punta larga)" if _hz else ("Lados verticales (punta larga)" if _fr else "Laterales (punta larga)")
    candidatos = [
        [_perfil_arista, _n_ax, _L_x, 4, "recto", _ref_arista],
        [_perfil_arista, _n_ay, _L_y, 4, "recto", _ref_arista],
        [_perfil_arista, _n_vz + " cuerpo", _L_zc, 4, "recto", _ref_arista],
        [_perfil_arista, _n_vz + _t1, _L_zt, 4, "recto", _ref_arista],
        [_perfil_arista, _n_vz + _t2, _L_zt2 if _2t else 0, 4, "recto", _ref_arista],
        [_perfil_macho, _lados_a, ext_ancho + 2 * cierre_saliente, _n_rings, "45/45", _ref_cm],
        [_perfil_macho, _lados_b, 0 if _cub else ext_prof + 2 * cierre_saliente, _n_rings, "45/45", _ref_cm],
        [_perfil_macho, "Lados verticales, tramo de la cubierta", cierre_saliente + _j_cub if _cub else 0, _n_rings, "45/45L" if _ing_junta else "45/recto", _ref_cm],
        [_perfil_macho, "Lados verticales, tramo fijo", cierre_saliente + ext_prof - _j_cub if _cub else 0, _n_rings, "45/45L" if _ing_junta else "45/recto", _ref_cm],
        [_perfil_hembra, _lados_a, ext_ancho + 2 * cierre_saliente, _n_rings, "45/45", _ref_ch],
        [_perfil_hembra, _lados_b, ext_prof + 2 * cierre_saliente, _n_rings, "45/45", _ref_ch],
        [_perfil_macho, "Junta tapa de acceso lateral", _L_zc + (2 * cierre_m_alto if _ing_junta else 0) if _acc else 0, 2, "45L/45L" if _ing_junta else "recto", _ref_cm],
        [_perfil_hembra, "Junta tapa de acceso lateral", _L_zc + (2 * cierre_h_alto if _ing_junta else 0) if _acc else 0, 2, "45L/45L" if _ing_junta else "recto", _ref_ch],
    ]
    perfiles = [Perfil(*p) for p in candidatos if p[2] >= TRAMO_MINIMO]

    # ---- herrajes ----
    _n_cierres = len([m for m in marcas if (m.tipo == "cierre" and por_id[m.panel].grupo == "cuerpo")
                      or (m.tipo == "cierre_acceso" and m.panel in ("cuerpo_izq", "cuerpo_der"))])
    _n_bisagras = (1 if _piano else bisagras) if _con_bisagras else 0
    _largo_piano = ext_ancho - 2 * (E_esq_pata + 10)
    _bis_rem = 2 * (math.floor(_largo_piano / 50) + 1) if _piano else cd(ref_bisagra, "remaches", 6) * _n_bisagras
    _tope_rem = cd(ref_tope, "remaches", 8) * topes
    _n_refuerzos = refuerzos * 4 * (2 if _2t else 1)
    _ref_rem = refuerzo_remaches * _n_refuerzos

    def remaches_tramo(L):
        return math.floor(max(L - 40, 0) / remache_paso) + 1

    _rem_aristas = sum(2 * remaches_tramo(p.largo) * p.cantidad for p in perfiles if p.corte == "recto")
    _rem_cierre = sum(remaches_tramo(p.largo) * p.cantidad for p in perfiles if p.corte != "recto")
    _rem_total = (_rem_aristas + _rem_cierre + 8 * _esq_remaches + _n_cierres * _cie_remaches
                  + (len(_man_paneles) * _man_n * _man_remaches if manijas else 0) + (4 * E_encastre_remaches if encastres else 0)
                  + _bis_rem + _tope_rem + _ref_rem)
    _espuma_area = 2 * (E_int_ancho * E_int_prof + E_int_ancho * (E_int_alto_cuerpo + E_int_alto_tapa)
                        + E_int_prof * (E_int_alto_cuerpo + E_int_alto_tapa)) / 1e6
    _espuma_planchas = math.ceil(_espuma_area * 1.2 / 2)

    def nom(ref, defecto):
        return cat.nombre(ref) if ce(ref) else defecto

    if _sin_frente:
        cara_txt = "laterales"
    elif _lat_cierres:
        cara_txt = "frente y laterales" if _con_bisagras else "frente, trasera y laterales"
    else:
        cara_txt = "frente" if _con_bisagras else "frente y trasera"
    _cie_detalle = cara_txt + (s(", embutido: calado ", _cie_corte[0], "x", _cie_corte[1]) if _cie_emb else "")

    H = []
    H.append([nom(ref_esquinero, "Esquinero bola"), 8, s("pata ", E_esq_pata, " mm"), ref_esquinero])
    if _n_cierres > 0:
        H.append([nom(ref_cierre, "Cierre mariposa"), _n_cierres, _cie_detalle, ref_cierre])
    if manijas:
        H.append([nom(ref_manija, "Manija embutida"), len(_man_paneles) * _man_n,
                  s("calado ", E_manija_corte_ancho, "x", E_manija_corte_alto) if _man_emb else "de superficie", ref_manija])
    if ruedas == 4 and rueda_frenos > 0:
        H.append([nom(ref_rueda_freno, s("Rueda giratoria Ø", E_rueda_diametro, " con freno")), rueda_frenos,
                  s("agujeros ", E_rueda_agujeros[0], "x", E_rueda_agujeros[1]), ref_rueda_freno])
    if ruedas == 4 and rueda_frenos < 4:
        H.append([nom(ref_rueda, s("Rueda giratoria Ø", E_rueda_diametro, " sin freno")), 4 - rueda_frenos,
                  s("agujeros ", E_rueda_agujeros[0], "x", E_rueda_agujeros[1]), ref_rueda])
    if ruedas == 4:
        largo_bulon = (_bt + (E_placa_esp + _bgap if base_pasantes else 0) if _base else E_placa_esp) + 15
        H.append([s("Bulón M", math.floor(E_rueda_agujero_d - 0.5), " + arandela + tuerca autofrenante"), 16,
                  s("para agujero Ø", E_rueda_agujero_d, ", largo ≥ ", largo_bulon, " mm"), ""])
    if _base and not base_pasantes:
        H.append(["Tornillo para fijar la base al piso", 8, "o tuerca de clavar + bulón", ""])
    if bandejas:
        H.append([nom(ref_escuadra, "Escuadra para bandeja"), len(bandejas) * bandeja_soportes,
                  "2 por costado, atornilladas a costado y bandeja", ref_escuadra])
        H.append(["Tornillo para madera (escuadras de bandeja)", len(bandejas) * bandeja_soportes * 4,
                  s("4 por escuadra, que no atraviesen la placa de ", E_placa_esp, " mm"), ""])
    if encastres:
        H.append([nom(ref_plato, "Plato de apilado (encastre de rueda)"), 4,
                  s("calado ", E_encastre_corte[0], "x", E_encastre_corte[1], ", prof. ", E_encastre_profundidad), ref_plato])
    if pies == 4:
        H.append([nom(ref_pie, "Pie de goma"), 4, s("Ø", _pie_d, " x ", _pie_h, " mm"), ref_pie])
    if _n_bisagras > 0:
        H.append([nom(ref_bisagra, "Bisagra"), _n_bisagras, s("cortar a ", _largo_piano, " mm") if _piano else "en la trasera", ref_bisagra])
    if topes > 0:
        H.append([nom(ref_tope, "Tope de tapa"), topes, "sostiene la tapa abierta", ref_tope])
    if _n_refuerzos > 0:
        H.append([refuerzo_nombre, _n_refuerzos, "esquinas de la junta de cierre" + (" (cuerpo y tapa)" if refuerzos == 2 else " (cuerpo)"), ""])
    if _espuma > 0:
        H.append([nom(ref_espuma, s("Espuma ", _espuma, " mm")), _espuma_planchas,
                  s("planchas 2x1 m para ", round_os(_espuma_area * 100) / 100, " m² (+20%)"), ref_espuma])
    for e in extras:
        H.append([nom(e[0], e[0]), e[1], "extra", e[0]])
    H.append([cat.nombre(E_remache_ref) if E_remache_ref is not None else s("Remache pop Ø", remache_d),
              math.ceil(_rem_total * 1.1), s("estimado: paso ", remache_paso, " mm, +10%"),
              E_remache_ref if E_remache_ref is not None else ""])
    herrajes = [Herraje(*h) for h in H]

    # ---- avisos ----
    _man_top = _man_cy + _man_hl / 2
    _man_lim = _y_cierre_cuerpo - 10
    _man_inf = _y_cierre2_cuerpo + 10 if _2t else _ala_arista + 10
    bordes = []
    for c in encastres_centros:
        bordes += [c[0] - _enc_ext[0] / 2, c[1] - _enc_ext[1] / 2, ext_ancho - c[0] - _enc_ext[0] / 2, ext_prof - c[1] - _enc_ext[1] / 2]
    _enc_borde = min(bordes + [9999])
    _refs_usadas = [
        [ref_placa, "placa"], [ref_angulo, "angulo"], [ref_hibrido, "hibrido"],
        [ref_cierre_macho, "hibrido" if cierre_hibrido else "tapa_m"], [ref_cierre_hembra, "hibrido" if cierre_hibrido else "tapa_h"],
        [ref_esquinero, "esquinero"], [ref_cierre, "cierre"], [ref_manija, "manija"], [ref_rueda, "rueda"],
        [ref_rueda_freno, "rueda"], [ref_plato, "plato"], [ref_pie, "pie"], [ref_bisagra, "bisagra"], [ref_tope, "tope"],
        [ref_espuma, "espuma"], [ref_remache, "remache"]]
    _int_mx = ext_alto_cuerpo if _hz else E_int_ancho
    _int_my = ext_alto_cuerpo - 2 * (cierre_m_alto - cierre_m_sup) if _fr else E_int_prof
    _int_mz = E_int_ancho if _hz else (E_int_prof if _fr else ext_alto - 2 * pared)

    A: List[str] = []
    if refuerzos == 2 and ext_alto_tapa - cierre_h_alto - E_esq_pata < refuerzo_alto:
        A.append(s("El refuerzo de esquina (", refuerzo_alto, " mm) no entra en la tapa: entre el perfil de cierre y el esquinero quedan ",
                   ext_alto_tapa - cierre_h_alto - E_esq_pata, " mm. Poné refuerzos = 1 (solo en el cuerpo) o un refuerzo más corto."))
    if refuerzos > 0 and ext_alto_cuerpo - (2 * cierre_m_alto if _2t else cierre_m_alto + E_esq_pata) < (2 if _2t else 1) * refuerzo_alto:
        A.append(s("Los refuerzos de esquina del cuerpo (", refuerzo_alto, " mm) no entran entre el perfil de cierre y el esquinero."))
    if acceso_tipo == "cubierta" and _acc and not _fr:
        A.append('acceso_tipo = "cubierta" solo está resuelto para cases frontales (racks); se toman paneles sueltos.')
    for b in bandejas:
        if b[0] > _int_mx or b[1] > _int_my:
            A.append(s("La bandeja de ", b[0], " x ", b[1], " no entra en el interior (", _int_mx, " x ", _int_my, ")."))
    for b in bandejas:
        if b[2] > _int_mz or b[2] < _band_esp(b):
            A.append(s("La altura de la bandeja (", b[2], " mm) queda fuera del interior (0 a ", _int_mz, " mm)."))
    if _base and ruedas != 4:
        A.append("Hay base de ruedas pero ruedas = 0: la base va igual a la lista, sin ruedas.")
    fx = ext_prof if _hz else ext_ancho
    fy = ext_alto if _acost else ext_prof
    if _base and (_bx > fx or _by > fy):
        A.append(s("La base de ruedas (", _bx, " x ", _by, ") es más grande que la planta del case (", fx, " x ", fy,
                   "): revisá base_ruedas (orden: ancho y alto del plano del piso)."))
    if _base and ruedas == 4 and (_rx1 - _rx0 < E_rueda_placa[0] + 10 or _ry1 - _ry0 < E_rueda_placa[1] + 10):
        A.append("Las ruedas no entran en la base sin pisarse o sin que los bulones choquen con ángulos o perfiles de cierre.")
    if _base and _acost and _by > ext_alto_cuerpo + 2:
        A.append(s("La base de ruedas asoma ", (_by - ext_alto_cuerpo) / 2, " mm bajo cada tapa: las tapas se apoyan en ella al cerrar."))
    if _base and (fx - _bx) / 2 < E_esq_pata and (fy - _by) / 2 < E_esq_pata:
        A.append("Con base de ruedas, revisá las cantoneras de abajo: una cantonera de bola choca con la base en las esquinas. Usá cantoneras planas abajo o recortá las esquinas de la base.")
    if _acc and _a_acc >= wlc - _j_acc - 60:
        A.append("La tapa de acceso es casi tan alta como el lateral: revisá acceso_lateral.")
    if _acc:
        for c in ("izq", "der"):
            for x in _xs_cara(c):
                if _lat_cierres and ((c == "izq" and _a_acc - 30 <= x <= _a_acc + _j_acc + 30)
                                     or (c == "der" and _w_low - 30 <= x <= _w_low + _j_acc + 30)):
                    A.append(s("Un cierre del lateral ", c, " cae sobre la junta de la tapa de acceso: cambiá cierres_lateral_n o cierre_margen."))
    for r in _refs_usadas:
        if r[0] != "" and not ce(r[0]):
            A.append(s("La referencia ", r[0], " no está en el catálogo: revisá el número."))
    for r in _refs_usadas:
        if ce(r[0]) and cat.categoria(r[0]) != r[1]:
            A.append(s("La referencia ", r[0], " (", cat.nombre(r[0]), ") no es del tipo esperado (", r[1], ")."))
    est = [r[0] for r in _refs_usadas if ce(r[0]) and not cat.verificado(r[0])
           and r[1] in ("angulo", "esquinero", "cierre", "manija", "rueda", "plato")]
    if est:
        A.append("Medidas estimadas (no figuran en el catálogo) para " + ", ".join(est)
                 + ": confirmalas con el herraje real o con su plano 2D en adamhall.com antes de cortar o calar.")
    if usar_catalogo_remaches and ref_remache == "" and not _rem_cands_d and _rem_cands:
        A.append(s("No hay remache de Ø", remache_d, " con largo suficiente (≥ ", _rem_l_min, " mm): se eligió ",
                   cat.nombre(E_remache_ref), ". Perforá con la mecha de ese diámetro."))
    for i in range(len(calados)):
        for j in range(i + 1, len(calados)):
            a, b = calados[i], calados[j]
            if (a.panel == b.panel and a.tipo != "agujero" and b.tipo != "agujero"
                    and abs(a.cx - b.cx) < (a.ancho + b.ancho) / 2 + 10 and abs(a.cy - b.cy) < (a.alto + b.alto) / 2 + 10):
                A.append(s("En ", por_id[a.panel].nombre, " el calado de ", a.tipo, " queda a menos de 10 mm del de ", b.tipo,
                           ": se pisan. Mové la manija (manija_centro_desde_arriba), los cierres (cierre_margen) o elegí herrajes más chicos."))
    for e in extras:
        if not ce(e[0]):
            A.append(s("El extra ", e[0], " no está en el catálogo."))
    if not _hib and _esq_paso > 0 and abs(_esq_paso - E_angulo_ala) > 2:
        A.append(s("El esquinero ", ref_esquinero, " tiene paso de perfil de ", _esq_paso, " mm y el ángulo es de ",
                   E_angulo_ala, " mm: no calzan. Elegí un esquinero o un ángulo que coincidan."))
    if _hib and ce(ref_hibrido) and abs(cd(ref_hibrido, "placa", _t) - _t) > 0.3:
        A.append(s("El perfil híbrido ", ref_hibrido, " es para placa de ", cd(ref_hibrido, "placa", 0), " mm y la placa es de ", _t, " mm."))
    for r in (ref_cierre_macho, ref_cierre_hembra):
        if ce(r) and abs(cd(r, "placa", _t) - _t) > 0.3:
            A.append(s("El perfil ", r, " es para placa de ", cd(r, "placa", 0), " mm y la placa es de ", _t, " mm."))
    if cat.categoria(_rueda_ref_geo) == "rueda_otra":
        A.append(s("La rueda ", _rueda_ref_geo, " se monta en la esquina o en ángulo: el generador no la ubica; queda solo en la lista."))
    if usar_catalogo_remaches and ref_remache == "" and not _rem_cands:
        A.append(s("No hay remache de Ø", remache_d, " con largo ≥ ", _rem_l_min, " mm en el catálogo."))
    if ruedas == 4 and pies == 4:
        A.append("Elegiste ruedas y pies a la vez: van los dos en el piso, verificá que no se crucen.")
    if _cie_emb and _y_cierre_cuerpo - 2 - _cie_corte[1] < (_y_cierre2_cuerpo + 2 + _cie_corte[1] + 10 if _2t else _ala_arista + 10):
        A.append("El calado del cierre embutido no entra en la pared del cuerpo: el cuerpo es muy bajo para ese cierre.")
    if encastres and E_encastre_profundidad > int_alto_tapa - 5:
        A.append(s("El plato de apilado (", E_encastre_profundidad, " mm) no entra en la tapa: el interior de la tapa tiene ",
                   int_alto_tapa, " mm. Subí int_alto_tapa o usá un plato más bajo."))
    if encastres and _enc_borde < _ala_arista + 2:
        A.append(s("El reborde del plato de apilado pisa el ", "perfil" if _hib else "ángulo",
                   " del techo (queda a ", _enc_borde, " mm del borde). Aumentá rueda_margen."))
    if encastres and (ext_ancho - 2 * _off_rx < _enc_ext[0] + 10 or ext_prof - 2 * _off_ry < _enc_ext[1] + 10):
        A.append("Los platos de apilado quedan pegados o superpuestos: el case es chico para esos platos (usá platos más chicos).")
    if encastres and ruedas == 4 and E_encastre_corte[1] < E_rueda_diametro * 0.45:
        A.append("El plato es angosto para esa rueda: verificá que la rueda de otro case entre girada.")
    if ruedas == 4 and not _acost and (2 * _off_rx + E_rueda_placa[0] > ext_ancho or 2 * _off_ry + E_rueda_placa[1] > ext_prof):
        A.append("Las placas de rueda se superponen: el case es muy chico para 4 ruedas de esa placa.")
    if ruedas == 4 and not _hib and _rueda_m < E_angulo_ala + 2:
        A.append("La placa de rueda pisa el ángulo del piso: aumentá rueda_margen.")
    if manijas and _man_emb and _man_top > _man_lim:
        A.append(s("La manija invade el perfil de cierre: borde superior del calado a ", _man_top,
                   " mm, el límite es ", _man_lim, " mm. Aumentá manija_centro_desde_arriba o el alto del cuerpo."))
    if manijas and _man_emb and _man_cy - _man_hl / 2 < _man_inf:
        A.append("La manija queda muy cerca del borde inferior del panel (ángulo o perfil de cierre).")
    if manijas and _man_emb and _man_wl > _man_w_panel - 2 * (_ala_arista + 10):
        A.append("El calado de la manija es más ancho que el espacio libre del panel.")
    if _acost and encastres:
        A.append(s("En orientación ", orientacion, " no se ubican platos de apilado: quedan fuera del diseño."))
    if _acost and ruedas == 4 and (len(ruedas_base) < 4
                                   or ruedas_base[0][0] + E_rueda_placa[0] / 2 > ruedas_base[2][0] - E_rueda_placa[0] / 2
                                   or ruedas_base[0][1] + E_rueda_placa[1] / 2 > ruedas_base[1][1] - E_rueda_placa[1] / 2):
        A.append("Las placas de rueda no entran en el piso del cuerpo: usá ruedas con placa más chica o un cuerpo más grande.")
    if manijas and _man_n == 2 and (_man_sep < _man_hl + 20 if _acost else _man_sep < _man_wl + 20):
        A.append("Las dos manijas quedan muy juntas: aumentá manija_sep.")
    if _hib and extremos_cubren:
        A.append("Con perfil híbrido los extremos no pueden tapar las paredes: se ignora extremos_cubren.")
    if _2t and _L_zt2 < TRAMO_MINIMO:
        A.append(s("Las verticales de la", _t2, " darían ", _L_zt2, " mm: se omiten."))
    if _2t and _con_bisagras:
        A.append(s("Con dos tapas, las bisagras van solo en la", _t1, "; la otra cierra con cierres."))
    if _L_zt < TRAMO_MINIMO:
        A.append(s("Las verticales de la tapa darían ", _L_zt, " mm: se omiten, el esquinero llega directo al perfil de cierre. Verificá que la pata del esquinero no pise el cierre."))
    if _L_zc < TRAMO_MINIMO:
        A.append(s("Las verticales del cuerpo darían ", _L_zc, " mm: se omiten."))
    L_pl = E_placa_largo - 2 * placa_margen
    A_pl = E_placa_ancho - 2 * placa_margen
    for p in paneles:
        if not ((p.ancho <= L_pl and p.alto <= A_pl) or (p.alto <= L_pl and p.ancho <= A_pl)):
            A.append(s("El panel ", p.nombre, " no entra en una placa de ", E_placa_largo, "x", E_placa_ancho, "."))
    for p in perfiles:
        if p.largo > barra_largo - 2 * sierra_kerf:
            A.append(s("El tramo ", p.nombre, " de ", p.largo, " mm supera la barra."))

    # ---- info (igual que @@INFO del .scad) ----
    info = {
        "sistema": [sistema],
        "material": [E_placa_material],
        "espesor": [fmt(E_placa_esp)],
        "color": [color_placa, color_placa if color_tapa == "" else color_tapa],
        "interior": [fmt(v) for v in (int_ancho, int_prof, int_alto_cuerpo, int_alto_tapa)],
        "exterior": [fmt(v) for v in (ext_ancho, ext_prof, ext_alto_cuerpo, ext_alto_tapa)],
        "espuma": [fmt(_espuma)],
        "tapa_abatible": [fmt(1 if (_con_bisagras and not _2t and orientacion == "vertical") else 0), fmt(topes)],
        "tipo": [fmt(tapas), orientacion, fmt(ext_alto_tapa2), fmt(ext_alto_cuerpo), fmt(ext_alto_tapa)],
        "mundo": [fmt(mundo_largo), fmt(mundo_prof), fmt(mundo_alto)],
        "barra": [fmt(barra_largo), fmt(sierra_kerf)],
        "montaje": [fmt(v) for v in (remache_paso, E_remache_d, E_esq_descuento, 1 if manijas else 0, rueda_frenos,
                                     1 if _lat_cierres else 0, _n_cierres, 1 if _cie_emb else 0, _n_bisagras,
                                     1 if pies == 4 else 0, 1 if _man_emb else 0)],
        "encastres": [fmt(1 if encastres else 0), fmt(E_encastre_profundidad)],
        "ruedas": [fmt(ruedas), fmt((E_rueda_alto if ruedas == 4 else (_pie_h if pies == 4 else 0)) + (_bt + _bgap if _base else 0)),
                   fmt(E_rueda_agujero_d), fmt(E_rueda_agujeros[0]), fmt(E_rueda_agujeros[1])],
        "placa": [fmt(E_placa_largo), fmt(E_placa_ancho), fmt(placa_kerf), fmt(placa_margen), ref_placa],
        "cantidad": [fmt(cantidad_cases)],
        "cierre": [fmt(1 if cierre_hibrido else 0), ref_cierre_macho, fmt(cierre_m_alto), fmt(cierre_h_alto),
                   fmt(cierre_m_sup), fmt(cierre_h_sup), fmt(cierre_saliente), fmt(cd(ref_cierre_macho, "canal", 0)), fmt(E_placa_esp)],
        "descuento": [fmt(0 if _hib else descuento_entre)],
    }
    if _rebajes:
        info["rebaje"] = [fmt(refuerzo_esp), fmt(rebaje_holgura)]

    extras_p = [[e[0], e[1], e[2], e[3], e[4] if len(e) > 4 else 1, e[5] if len(e) > 5 else s("Placa ", e[3], " mm")]
                for e in piezas_extra]
    panelmat = [["base_ruedas", base_material, _bt]] if _base else []
    bandejas_out = []
    for i, b in enumerate(bandejas):
        if len(b) > 3:
            panelmat.append([f"bandeja{i}", _band_mat(b), _band_esp(b)])
        bandejas_out.append([f"bandeja{i}", b[2], bandeja_soportes])

    return ResultadoTaller(
        info=info, paneles=paneles, calados=calados, marcas=marcas, perfiles=perfiles, extras=extras_p,
        herrajes=herrajes, panelmat=panelmat, bandejas=bandejas_out, avisos=A,
        valores={"ext_ancho": ext_ancho, "ext_prof": ext_prof, "ext_alto": ext_alto, "pared": pared,
                 "placa_largo": E_placa_largo, "placa_ancho": E_placa_ancho, "placa_esp": E_placa_esp,
                 "placa_material": E_placa_material, "placa_kerf": placa_kerf, "placa_margen": placa_margen,
                 "barra_largo": barra_largo, "sierra_kerf": sierra_kerf, "cantidad_cases": cantidad_cases,
                 "remache_ref": E_remache_ref},
    )
