"""Detalle de la unión a inglete del vertical del aro (H3/H2) con la junta lateral (H5) de la cubierta."""
import textwrap
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Polygon

TAN, TAN2 = "#d8b98a", "#e9d5b0"
ACERO, ACERO2 = "#9fb0c3", "#c6d2df"
NAR, NAR2 = "#f39c12", "#f8c471"

def notas(L5, L5c):
    return [
        "El H3 y el H5 se unen a inglete 45°, como una esquina de marco, en el plano del lateral P3. Los dos rodean al panel: el P3 entra 21 mm en el canal de cada uno.",
        f"La punta larga de los dos llega a la esquina de afuera, donde se cruzan el centro de la junta de la cubierta y el centro de la junta con la tapa. El H5 mide {L5} en la punta larga (la profundidad del cuerpo) y {L5c} en la corta, del lado del panel.",
        "El H3 tiene dos ingletes girados 90° entre sí: abajo cierra con el H1 (esquina del aro, plano del frente) y arriba con el H5 (plano del lateral). Marcá en cada tramo cuál es cuál antes de cortar.",
        "Arriba se repite en espejo: el H2 y el H5 de la cubierta (girado 180°) también van a inglete. Entre los cantos del P3 y el P4 quedan 8 mm.",
        "Armá primero cada lateral con su H5 y sus dos H3 (o H2) a inglete, y después paralo sobre el piso (o el techo) para cerrar los ingletes del aro con los H1.",
    ]

def dibujar(ruta, L5="720", L5c="670", solo_vistas=False, dpi=150):
    fig = plt.figure(figsize=(11.69, 8.27))
    if not solo_vistas: fig.text(0.04, 0.95, "Detalle: unión a inglete del vertical de la parte fija (H3) con la junta lateral (H5)", fontsize=15, weight="bold")
    if not solo_vistas: fig.text(0.04, 0.915, "Esquina de adelante y arriba del lateral fijo P3 (la de atrás es igual, en espejo). Medidas en mm, esquema sin escala exacta.", fontsize=9.5, color="#555")
    
    # ---------- Vista A: desde afuera ----------
    ax = fig.add_axes([0.02, 0.06, 0.58, 0.86] if solo_vistas else [0.02, 0.27, 0.58, 0.62]); ax.set_aspect("equal"); ax.axis("off")
    X1, Y0, Y1 = 115, -75, 75
    ax.set_xlim(-45, X1 + 70); ax.set_ylim(Y0 - 8, Y1 + 14)
    ax.add_patch(Rectangle((0, Y0), X1, -Y0, fc=TAN, ec="k", lw=1))            # P3
    ax.add_patch(Rectangle((0, 8), X1, Y1 - 8, fc=TAN2, ec="k", lw=1))          # P4
    ax.add_patch(Rectangle((-29, Y0), 25, Y1 - Y0, fc="#eeeeee", ec="#999", lw=0.8, ls="--"))  # aro tapa
    ax.text(-16.5, -30, "aro de la tapa (H4)\nva por fuera de la junta", rotation=90, ha="center", va="center", fontsize=8, color="#777")
    ax.add_patch(Polygon([(-4, Y0), (21, Y0), (21, -21), (-4, 4)], closed=True, fc=ACERO, ec="k", lw=1.2))     # H3
    ax.add_patch(Polygon([(-4, Y1), (21, Y1), (21, 29), (-4, 4)], closed=True, fc=ACERO2, ec="k", lw=1.2))      # H2
    ax.add_patch(Polygon([(-4, 4), (X1, 4), (X1, -21), (21, -21)], closed=True, fc=NAR, ec="k", lw=1.2))       # H5 fija
    ax.add_patch(Polygon([(-4, 4), (X1, 4), (X1, 29), (21, 29)], closed=True, fc=NAR2, ec="k", lw=1.2))        # H5 cubierta
    # cantos ocultos de los paneles
    ax.plot([0, 0], [Y0, 0], "k--", lw=0.7); ax.plot([0, X1], [0, 0], "k--", lw=0.7)
    ax.plot([0, 0], [8, Y1], "k--", lw=0.7); ax.plot([0, X1], [8, 8], "k--", lw=0.7)
    ax.plot([-40, X1 + 5], [4, 4], color="red", ls="-.", lw=0.9)
    ax.text(X1 + 4, -3, "centro de la junta\nde la cubierta", color="red", fontsize=8, ha="left", va="top")
    ax.plot([-4, -4], [Y0 - 6, Y1 + 8], color="red", ls="-.", lw=0.9)
    ax.text(-3, Y1 + 9, "centro de la junta con la tapa", color="red", fontsize=8, ha="center", va="bottom")
    ax.text(8.5, -48, "H3", fontsize=12, weight="bold", ha="center"); ax.text(8.5, 45, "H2", fontsize=12, weight="bold", ha="center")
    ax.text(70, -10, "H5 (parte fija)", fontsize=11, weight="bold", ha="center", va="center")
    ax.text(70, 17, "H5 de la cubierta (girado 180°)", fontsize=9.5, weight="bold", ha="center", va="center")
    ax.text(70, -50, "P3 lateral fijo", fontsize=11, ha="center"); ax.text(70, 55, "P4 lateral de la cubierta", fontsize=11, ha="center")
    def cota_h(x0, x1, y, t):
        ax.annotate("", (x0, y), (x1, y), arrowprops=dict(arrowstyle="<->", lw=0.8))
        ax.text((x0 + x1) / 2, y - 1.5, t, ha="center", va="top", fontsize=8.5)
    def cota_v(x, y0, y1, t, lado=1):
        ax.annotate("", (x, y0), (x, y1), arrowprops=dict(arrowstyle="<->", lw=0.8))
        ax.text(x + 1.5 * lado, (y0 + y1) / 2, t, ha="left" if lado > 0 else "right", va="center", fontsize=8.5)
    cota_h(0, 21, -68, "21")
    cota_v(X1 + 40, 0, 8, "")
    ax.text(X1 + 42, 14, "8 entre cantos\nde P3 y P4", fontsize=8.5, va="bottom")
    ax.plot([X1, X1 + 42], [0, 0], "k:", lw=0.6); ax.plot([X1, X1 + 42], [8, 8], "k:", lw=0.6)
    cota_v(30, -21, 0, "21", 1)
    cota_v(24, 0, 4, "4", 1)
    ax.annotate("inglete 45° en el plano del lateral:\nla punta larga del H5 llega hasta el\ncentro de la junta con la tapa", (6, -6), (32, -40), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.annotate("punta larga del H3 y del H5:\nesquina en los dos centros de junta", (-4, 4), (-42, 30), fontsize=8.5,
                arrowprops=dict(arrowstyle="->", lw=0.8))
    ax.text(-40, Y0 - 6, "A · Vista desde afuera (lateral derecho, el frente del case a la izquierda)", fontsize=9.5, weight="bold")
    
    # ---------- Vista B: corte por la junta ----------
    bx = fig.add_axes([0.64, 0.10, 0.33, 0.82] if solo_vistas else [0.64, 0.30, 0.33, 0.58]); bx.set_aspect("equal"); bx.axis("off")
    bx.set_xlim(-14, 28); bx.set_ylim(-50, 44)
    bx.add_patch(Rectangle((0, -32), 10, 32, fc=TAN, ec="k"))
    bx.add_patch(Rectangle((0, 8), 10, 36, fc=TAN2, ec="k"))
    def perfil(sg, col):   # sg = +1 abajo (parte fija), -1 arriba (cubierta, girado)
        y = lambda v: 4 - sg * (4 - v) if sg > 0 else 4 + (4 - v)
        pts = [(-1.5, -21), (-1.5, 4), (11.5, 4), (11.5, -21), (10, -21), (10, 0), (0, 0), (0, -21)]
        if sg < 0:
            pts = [(x, 8 - yy) for x, yy in pts]
        bx.add_patch(Polygon(pts, closed=True, fc=col, ec="k", lw=1.1))
    perfil(1, NAR); perfil(-1, NAR2)
    # encastre esquemático
    # encastre esquemático: los dos perfiles son iguales, uno girado 180° (zigzag simétrico)
    bx.plot([0, 2.5, 5, 7.5, 10], [4, 6, 4, 2, 4], color="k", lw=1.1)
    bx.plot([-12, 24], [4, 4], color="red", ls="-.", lw=0.9)
    bx.text(24, 4.6, "centro de\nla junta", color="red", fontsize=8, ha="right", va="bottom")
    bx.text(5, -27, "P3", ha="center", fontsize=11); bx.text(5, 34, "P4", ha="center", fontsize=11)
    bx.text(17, -10, "H5\nparte fija", fontsize=9, va="center"); bx.text(17, 18, "H5\ncubierta\n(girado 180°)", fontsize=9, va="center")
    bx.annotate("", (-9, 0), (-9, -21), arrowprops=dict(arrowstyle="<->", lw=0.8)); bx.text(-9.6, -10.5, "21", ha="right", va="center", fontsize=8.5)
    bx.annotate("", (-5, 0), (-5, 8), arrowprops=dict(arrowstyle="<->", lw=0.8)); bx.text(-5.6, 4, "8", ha="right", va="center", fontsize=8.5)
    bx.text(-13, 40, "← AFUERA", fontsize=8.5, color="#555")
    bx.text(-13, -40, "B · Corte por la junta\n(mirando desde el frente)", fontsize=9.5, weight="bold", va="bottom")
    bx.text(-13, -49, "Los dos son el mismo perfil híbrido, uno girado 180°.\nEncastre simplificado: la forma real está\nen la hoja «Perfil híbrido».", fontsize=7.5, color="#666", va="bottom")
    
    if not solo_vistas:
        y = 0.215
        for k0, n in enumerate(notas(L5, L5c), 1):
            for k, ln in enumerate(textwrap.wrap(f"{k0}. {n}", 175)):
                fig.text(0.04 if k == 0 else 0.052, y, ln, fontsize=8.6); y -= 0.022
            y -= 0.004
    fig.savefig(ruta, dpi=dpi)
    plt.close(fig)
