# -*- coding: utf-8 -*-
"""
Mejor oferta MG Financial Services — motor de cálculo y PDF.

Compara todas las ofertas del boletín para un auto (Tasa Baja 0% CXA, Tasa Baja 2% CXA, Lanzamiento 8.99%,
Estándar 13.74%, Estándar 17.74% y Especial 12.09%), aplica el bono de la forma que convenga (a tasa / al enganche /
al precio, excluyente) y dice la mejor opción por plazo y cuánto puede valer el seguro de contado para que cada
opción siga siendo la ideal.

Reglas (boletín BMGFS-16-10-2026, vigente del 09-oct al 02-nov-2026):
  · Tasa baja: el bono ya va a la tasa → el cliente paga precio de lista.
  · Bono flexible (Estándar / 12.09%): bono al enganche o al precio; el enganche mínimo de los vehículos con bono
    INCLUYE el bono aplicado al enganche.
  · Enganche < 20% → +4% a la tasa (plan 17.74% para modelos sin bono, desde 10%). Enganche máximo 75%.
  · El seguro se paga de contado (por defecto sale del pago inicial del cliente).
  · Mensualidad con IVA sobre intereses (tasa/12 × 1.16), pagos fijos.
  · No incluye Anualidades, University ni Seminuevos.

Para un nuevo boletín: actualiza BOLETIN, CATALOGO, CURVAS y ofertas_para().
"""
import io
import math
import re
from datetime import datetime

BOLETIN = "BMGFS-16-10-2026"
OFERTA_MES = "Octubre 2026"
VIGENCIA = "09/10/2026 al 02/11/2026"

PLAZOS = [12, 24, 36, 48, 60, 72]
IVA = 0.16

# ------------------------------------------------------------------------------------
# Curvas de tasa (12, 24, 36, 48, 60 meses) de las tablas de Tasa Baja
# ------------------------------------------------------------------------------------
CURVAS = {
    # Tasa Baja + 0% CXA (págs. 3-4)
    "A":  [0.00, 5.10, 7.70, 10.20, 11.00],
    "B":  [0.00, 5.70, 8.30, 10.60, 11.40],
    "C":  [0.00, 3.80, 6.80, 9.50, 10.40],
    "D":  [0.00, 0.00, 2.20, 5.90, 7.50],
    "E":  [0.00, 0.00, 4.10, 7.40, 8.70],
    "E2": [0.00, 0.00, 4.10, 7.30, 8.70],
    "F":  [0.00, 0.00, 0.00, 0.00, 2.60],
    "G":  [0.00, 0.00, 0.00, 4.60, 6.40],
    "H":  [0.00, 2.80, 6.10, 8.90, 10.00],
    "I":  [4.20, 9.20, 10.70, 12.50, 13.00],
    # Tasa Baja + 2% CXA (págs. 5-7)
    "a":  [0.00, 1.40, 4.50, 6.20, 7.20],
    "b":  [0.00, 2.40, 5.30, 6.80, 7.70],
    "c":  [0.00, 0.00, 3.50, 5.40, 6.50],
    "d":  [0.00, 0.00, 0.00, 0.00, 2.20],
    "e":  [0.00, 0.00, 0.00, 2.70, 4.30],
    "f":  [0.00, 0.00, 0.00, 0.00, 0.00],
    "g":  [0.00, 0.00, 0.00, 1.40, 3.20],
    "h":  [0.00, 0.00, 1.50, 3.90, 5.30],
    "i":  [0.00, 5.70, 7.60, 9.00, 9.20],
}

# ------------------------------------------------------------------------------------
# Catálogo: MSRP, bono, enganche sistema (color de la tabla de bonos: 20/25/30/40),
# tasa baja 0% CXA (eng. mín, curva, baremos) y tasa baja 2% CXA (eng. mín, curva, baremos)
# ------------------------------------------------------------------------------------
def V(msrp, bono, color, tb0=None, tb2=None, lanz=False):
    return dict(msrp=msrp, bono=bono, color=color, tb0=tb0, tb2=tb2, lanz=lanz)

CATALOGO = {
    "RX9 2025 2.0T COM ELEGANCE AT":            V(777000, 200000, 40, (22, "F", "425/452"), (30, "f", "454/597")),
    "RX9 2025 2.0T LUX PREMIER AT":             V(869900, 140000, 30, (20, "D", "426/453"), (30, "e", "463/598")),
    "MG4EV 2025 EDU COM 51 STYLE AT":           V(499000,  80000, 30, (22, "D", "426/453"), (30, "e", "463/598")),
    "MG4EV 2025 EDU DEL 77 EXTENDED RANGE AT":  V(609000,  90000, 25, (20, "E", "448/586"), (30, "e", "463/598")),
    "MGZS 2026 HEV COM EXCITE":                 V(545000, 100000, 30, (20, "D", "426/453"), (31, "d", "470/601")),
    "MGZS 2026 HEV LUX ELEGANCE":               V(580000,  80500, 25, (20, "E", "448/586"), (32, "e", "463/598")),
    "MGZS 2026 1.5T COM TURBO EXCITE CVT":      V(399900,  35000, 20, (23, "A", "431/458"), (33, "a", "469/600")),
    "MGZS 2026 1.5T LUX TURBO ELEGANCE AT":     V(490000,  90500, 30, (24, "G", "434/466"), (30, "d", "470/601")),
    "MGZS 2027 1.5T COM TURBO EXCITE AT":       V(399900,  35000, 20, (22, "A", "431/458"), (33, "a", "469/600")),
    "MGZS 2027 1.5T LUX TURBO ELEGANCE AT":     V(490000,  90500, 30, (24, "G", "434/466"), (30, "d", "470/601")),
    "New HS 2026 1.5T COM EXCITE AT":           V(599900, 100000, 30, (20, "D", "426/453"), (30, "g", "468/599")),
    "New HS 2026 2.0T LUX TROPHY AT":           V(659900,  80000, 25, (20, "H", "450/592"), (32, "h", "480/629")),
    "New HSHEV 2026 1.5L DEL EXCITE HYBRID AT": V(619900, 110000, 30, (20, "D", "426/453"), (33, "d", "470/601")),
    "New HSHEV 2026 1.5L LUX PREMIER HYBRID AT":V(689900,  90000, 25, (24, "E", "448/586"), (36, "e", "463/598")),
    "NEW MGHSHEV 2027 LUX PREMIER HYBRID AT":   V(689900,  90000, 25, (24, "E2", "448/586"), (36, "e", "463/598")),
    "NEW MGHSPHEV 2026 1.5T TURBO EXCITE PHEV AT": V(714900, 110000, 25, (20, "E", "448/586"), (30, "e", "463/598")),
    "NEW MGHSPHEV 2026 1.5T TURBO TROPHY PHEV AT": V(779900,  80000, 20, (25, "H", "450/592"), (32, "c", "473/624")),
    "MG3 2026 1.5L COM STYLE MT":               V(306000,  30000, 20, (20, "A", "431/458"), (30, "a", "469/600")),
    "MG3 2026 1.5L COM STYLE AT":               V(324000,  30000, 20, (20, "A", "431/458"), (30, "a", "469/600")),
    "MG3 2026 1.5L DEL EXCITE AT":              V(364000,  30000, 20, (20, "B", "435/497"), (30, "b", "472/622")),
    "MG3HEV 2026 1.5L COM EXCITE HYBRID AT":    V(422000,  45000, 25, (20, "C", "439/583"), (30, "c", "473/624")),
    "MG3HEV 2026 1.5L LUX ELEGANCE HYBRID AT":  V(464000,  45000, 20, (24, "C", "439/583"), (35, "c", "473/624")),
    "MG5 2027 1.5L STD STYLE MT":               V(299900,  25000, 20, (27, "A", "431/458"), (37, "a", "469/600")),
    "MG5 2027 1.5L COM EXCITE MT":              V(344000,  60000, 30, (20, "D", "426/453"), (35, "d", "470/601")),
    "MG5 2027 1.5L COM EXCITE AT":              V(378000,  60000, 30, (20, "E", "448/586"), (30, "e", "463/598")),
    "MG5 2027 1.5L DEL ELEGANCE AT":            V(399000,  60000, 25, (20, "E", "448/586"), (30, "e", "463/598")),
    "MG7 2026 2.0T COM PREMIER AT":             V(629000,  30000, 20, (20, "I", "449/588"), (37, "i", "476/625")),
    # El boletín dice "Eng 30%" en el título pero 33% en la columna; se usa 33% (lo más estricto)
    "MG7 2026 2.0T LUX TROPHY AT":              V(697000,  60000, 20, (22, "A", "431/458"), (33, "a", "469/600")),
    # Modelos de lanzamiento (sin bono, precio manual)
    "MG3 2027 STYLE (Lanzamiento)":             V(None, 0, None, lanz=True),
    "MG3 2027 EXCITE (Lanzamiento)":            V(None, 0, None, lanz=True),
    "ZS 2027 HEV LUX ELEGANCE (Lanzamiento)":   V(None, 0, None, lanz=True),
    "MG4 2026 EXTENDED RANGE (Lanzamiento)":    V(None, 0, None, lanz=True),
    "OTRO MODELO SIN BONO (precio manual)":     V(None, 0, None),
}

ENGANCHE_MAX = 0.75

def curva_a_dict(curva):
    return {p: t for p, t in zip([12, 24, 36, 48, 60], CURVAS[curva])}

def estandar_1374():
    return {12: 13.74, 24: 14.24, 36: 14.24, 48: 15.24, 60: 15.24, 72: 16.74}

def estandar_1774(con_72=True):
    d = {12: 17.74, 24: 18.24, 36: 18.24, 48: 19.24, 60: 19.24}
    if con_72:
        d[72] = 20.74
    return d

def especial_1209():
    return {12: 12.09, 24: 12.09, 36: 12.09, 48: 12.09, 60: 12.09, 72: 13.59}

# ------------------------------------------------------------------------------------
# Ofertas aplicables al vehículo
#   modo "tasa"     → bono subsidiado en tasa, cliente paga precio de lista
#   modo "flexible" → bono al enganche o al precio
#   modo "sin_bono" → no lleva bono
# ------------------------------------------------------------------------------------
def ofertas_para(v):
    ops = []
    color = v["color"]
    if v["tb0"]:
        mn, cur, bar = v["tb0"]
        ops.append(dict(nombre=f"Tasa Baja Eng {mn}% + 0% CXA", baremo=bar, cxa=0.00,
                        modo="tasa", min=mn/100, max=None, tasas=curva_a_dict(cur)))
    if v["tb2"]:
        mn, cur, bar = v["tb2"]
        ops.append(dict(nombre=f"Tasa Baja Eng {mn}% + 2% CXA", baremo=bar, cxa=0.02,
                        modo="tasa", min=mn/100, max=None, tasas=curva_a_dict(cur)))
    if v["lanz"]:
        ops.append(dict(nombre="Lanzamiento 8.99% + 2% CXA", baremo="421/451", cxa=0.02,
                        modo="sin_bono", min=0.30, max=None,
                        tasas={p: 8.99 for p in [12, 24, 36, 48, 60]}))
    modo_std = "flexible" if v["bono"] > 0 else "sin_bono"
    if color:   # vehículo marcado en la tabla de bonos
        ops.append(dict(nombre=f"Estándar 13.74% + 0% CXA (bono flexible)", baremo="413/419", cxa=0.00,
                        modo=modo_std, min=(color + 10)/100, max=None, tasas=estandar_1374()))
        ops.append(dict(nombre=f"Estándar 17.74% + 0% CXA (bono flexible)", baremo="414/441", cxa=0.00,
                        modo=modo_std, min=color/100, max=None, tasas=estandar_1774(True)))
        ops.append(dict(nombre=f"Especial 12.09% + 2% CXA (bono flexible)", baremo="420/446", cxa=0.02,
                        modo=modo_std, min=(color + 20)/100, max=None, tasas=especial_1209()))
    else:       # toda la gama sin marca
        ops.append(dict(nombre="Estándar 13.74% + 0% CXA", baremo="412/417", cxa=0.00,
                        modo=modo_std, min=0.20, max=None, tasas=estandar_1374()))
        ops.append(dict(nombre="Estándar 17.74% + 0% CXA (enganche 10% a <20%)", baremo="412/417", cxa=0.00,
                        modo=modo_std, min=0.10, max=0.20, tasas=estandar_1774(False)))
        ops.append(dict(nombre="Especial 12.09% + 2% CXA", baremo="415/443", cxa=0.02,
                        modo=modo_std, min=0.30, max=None, tasas=especial_1209()))
    return ops


def requiere_precio(vehiculo):
    return CATALOGO[vehiculo]["msrp"] is None


# ------------------------------------------------------------------------------------
# Cálculos
# ------------------------------------------------------------------------------------
def mensualidad(monto, tasa_anual_pct, n, iva=True):
    r = tasa_anual_pct / 100 / 12 * ((1 + IVA) if iva else 1)
    if r == 0:
        return monto / n
    return monto * r / (1 - (1 + r) ** -n)


def evaluar(op, precio, bono, efectivo):
    """efectivo = enganche que realmente pone el cliente (ya sin seguro).
    Devuelve validez, forma del bono, % de enganche y monto financiado."""
    candidatos = []
    if op["modo"] in ("tasa", "sin_bono"):
        candidatos.append(("a tasa" if op["modo"] == "tasa" else "sin bono",
                           efectivo / precio, precio - efectivo))
    else:
        candidatos.append(("al enganche", (efectivo + bono) / precio, precio - efectivo - bono))
        candidatos.append(("al precio", efectivo / (precio - bono), precio - bono - efectivo))
    for forma, pct, financiado in candidatos:
        ok = pct >= op["min"] - 1e-9 and pct <= ENGANCHE_MAX + 1e-9 and financiado > 0
        if op["max"] is not None and pct >= op["max"] - 1e-9:
            ok = False
        if ok:
            return dict(valida=True, forma=forma, pct=pct, financiado=financiado)
    forma, pct, financiado = candidatos[0]
    return dict(valida=False, forma=forma, pct=pct, financiado=financiado)


def costo(op, ev, n, iva=True):
    """Lo que paga el cliente después del pago inicial: CXA + mensualidades."""
    if n not in op["tasas"]:
        return None
    m = mensualidad(ev["financiado"], op["tasas"][n], n, iva)
    cxa = ev["financiado"] * op["cxa"]
    return dict(tasa=op["tasas"][n], mens=m, cxa=cxa, total=cxa + m * n, interes=m * n - ev["financiado"])


def mejor_en(ops, precio, bono, efectivo, n, iva=True):
    mejor = None
    for op in ops:
        ev = evaluar(op, precio, bono, efectivo)
        if not ev["valida"]:
            continue
        c = costo(op, ev, n, iva)
        if c is None:
            continue
        if mejor is None or c["total"] < mejor[2]["total"] - 0.005:
            mejor = (op, ev, c)
    return mejor


def rango_seguro(op, precio, bono, pago, seguro_en_pago=True):
    """Rango de seguro de contado (de $10 en $10) en el que la oferta es válida; None si nunca."""
    if not seguro_en_pago:
        return (0, math.inf) if evaluar(op, precio, bono, pago)["valida"] else None
    validos = [s for s in range(0, int(pago) + 1, 10) if evaluar(op, precio, bono, pago - s)["valida"]]
    return (validos[0], validos[-1]) if validos else None


def tramos_seguro(ops, precio, bono, pago, plazo, iva=True, max_filas=8):
    """Tramos de costo del seguro con la mejor oferta en cada uno.
    Lista de dict(desde, hasta, oferta (None si ninguna), mens_min, mens_max)."""
    crudos, actual = [], None
    for s in range(0, int(pago) + 1, 10):
        m = mejor_en(ops, precio, bono, pago - s, plazo, iva)
        clave = m[0]["nombre"] if m else None
        if actual is None or clave != actual["oferta"]:
            if actual:
                crudos.append(actual)
            actual = dict(oferta=clave, desde=s, hasta=s)
        else:
            actual["hasta"] = s
    if actual:
        crudos.append(actual)
    salida = []
    for t in crudos:
        if t["oferta"] is None:
            salida.append(dict(t, mens_min=None, mens_max=None))
            if t["desde"] > pago * 0.5:
                break
        else:
            op = next(o for o in ops if o["nombre"] == t["oferta"])
            c_lo = costo(op, evaluar(op, precio, bono, pago - t["desde"]), plazo, iva)
            c_hi = costo(op, evaluar(op, precio, bono, pago - t["hasta"]), plazo, iva)
            salida.append(dict(t, mens_min=c_lo["mens"], mens_max=c_hi["mens"]))
        if len(salida) >= max_filas:
            break
    return salida


def analizar(vehiculo, pago, seguro=0.0, seguro_en_pago=True, plazo=60, precio_manual=0.0, iva=True):
    """Corre todo el análisis y regresa un dict con los resultados."""
    v = CATALOGO[vehiculo]
    precio = precio_manual if precio_manual and precio_manual > 0 else v["msrp"]
    if not precio:
        raise ValueError(f"«{vehiculo}» no tiene precio en el boletín: captura el precio.")
    bono = v["bono"]
    efectivo = pago - (seguro if seguro_en_pago else 0)
    ops = ofertas_para(v)
    evals = {o["nombre"]: evaluar(o, precio, bono, efectivo) for o in ops}
    rangos = {o["nombre"]: rango_seguro(o, precio, bono, pago, seguro_en_pago) for o in ops}
    ranking = []
    for o in ops:
        ev = evals[o["nombre"]]
        if ev["valida"]:
            c = costo(o, ev, plazo, iva)
            if c:
                ranking.append((c["total"], o, ev, c))
    ranking.sort(key=lambda x: x[0])
    mejores = {n: mejor_en(ops, precio, bono, efectivo, n, iva) for n in PLAZOS}
    tramos = tramos_seguro(ops, precio, bono, pago, plazo, iva) if seguro_en_pago else []
    return dict(vehiculo=vehiculo, precio=precio, bono=bono, pago=pago, seguro=seguro,
                seguro_en_pago=seguro_en_pago, plazo=plazo, iva=iva, efectivo=efectivo, ops=ops,
                evals=evals, rangos=rangos, ranking=ranking, mejores=mejores, tramos=tramos)


money = lambda x: "—" if x is None else f"${x:,.2f}"
money0 = lambda x: f"${x:,.0f}"


def texto_rango(rs, seguro_en_pago=True):
    if not seguro_en_pago:
        return "N/A (seguro aparte)"
    if rs is None:
        return "No alcanza"
    return f"hasta {money0(rs[1])}" if rs[0] == 0 else f"{money0(rs[0])} a {money0(rs[1])}"


def texto_mens(t):
    if t["oferta"] is None:
        return "—"
    if abs(t["mens_min"] - t["mens_max"]) < 0.01:
        return money(t["mens_min"])
    return f"{money(t['mens_min'])} a {money(t['mens_max'])}"


# ------------------------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------------------------
def pdf_bytes(res, cliente=""):
    """PDF del análisis (bytes)."""
    VEHICULO, precio, bono, efectivo, ops = res["vehiculo"], res["precio"], res["bono"], res["efectivo"], res["ops"]
    PAGO_INICIAL, SEGURO_CONTADO, PLAZO_DESEADO = res["pago"], res["seguro"], res["plazo"]
    SEGURO_SALE_DEL_PAGO_INICIAL, iva, ranking = res["seguro_en_pago"], res["iva"], res["ranking"]
    tramos_pdf = [(t["desde"], t["hasta"], t["oferta"], texto_mens(t)) for t in res["tramos"]]
    NOMBRE_CLIENTE = cliente or ""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
                                    Table, TableStyle, PageBreak, KeepTogether)
    from reportlab.graphics.shapes import Drawing, Rect, String

    ROJO = colors.HexColor("#C8102E"); NEGRO = colors.HexColor("#1A1A1A")
    GRIS = colors.HexColor("#F3F3F3"); GRIS2 = colors.HexColor("#D9D9D9")
    TXT2 = colors.HexColor("#5A5A5A"); VERDE = colors.HexColor("#E6F4EA")
    VERDE_T = colors.HexColor("#1E7B34")
    PALETA = [colors.HexColor(c) for c in
              ["#C8102E", "#1F4E79", "#2E8B57", "#E07B00", "#6A3D9A", "#00838F", "#8D6E63"]]

    W, H = landscape(letter)
    M = 36
    ancho = W - 2 * M

    def st(name, size=9, color=NEGRO, bold=False, align=0, leading=None):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica",
                              fontSize=size, textColor=color, alignment=align,
                              leading=leading or size * 1.25)
    s_h1 = st("h1", 20, NEGRO, True)
    s_sub = st("sub", 10, TXT2)
    s_h2 = st("h2", 13, ROJO, True)
    s_p = st("p", 9, NEGRO, leading=12)
    s_small = st("sm", 7.5, TXT2, leading=9.5)
    s_cell = st("c", 8, NEGRO, leading=10)
    s_cell_b = st("cb", 8, NEGRO, True, leading=10)
    s_cell_c = st("cc", 8, NEGRO, align=TA_CENTER, leading=10)
    s_head = st("hd", 8, colors.white, True, TA_CENTER, 10)
    s_lbl = st("lbl", 7.5, TXT2, align=TA_CENTER)
    s_val = st("val", 14, NEGRO, True, TA_CENTER, 17)

    def P(t, s=s_cell):
        return Paragraph(str(t), s)

    def encabezado(c, doc):
        c.saveState()
        c.setFillColor(NEGRO); c.rect(0, H - 34, W, 34, fill=1, stroke=0)
        c.setFillColor(ROJO); c.rect(0, H - 37, W, 3, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
        c.drawString(M, H - 22, "MG FINANCIAL SERVICES  |  Análisis de mejor oferta")
        c.setFont("Helvetica", 9)
        c.drawRightString(W - M, H - 22, f"Oferta comercial {OFERTA_MES.lower()} · {BOLETIN}")
        c.setFillColor(TXT2); c.setFont("Helvetica", 7.5)
        c.drawString(M, 20, "Mensualidades sin seguro, con IVA sobre intereses y pagos fijos. "
                            "Cifras de referencia: verificar en el cotizador oficial.")
        c.drawRightString(W - M, 20, f"Página {doc.page}")
        c.restoreState()

    archivo = io.BytesIO()
    doc = BaseDocTemplate(archivo, pagesize=landscape(letter), leftMargin=M, rightMargin=M,
                          topMargin=52, bottomMargin=36,
                          title=f"Mejor oferta {VEHICULO}", author="MG Colima")
    doc.addPageTemplates([PageTemplate(id="p", onPage=encabezado,
                                       frames=[Frame(M, 36, ancho, H - 88, id="f")])])
    story = []

    # --- Título
    story.append(P(VEHICULO, s_h1))
    sub = f"Generado el {datetime.now():%d/%m/%Y}"
    if NOMBRE_CLIENTE.strip():
        sub = f"Cliente: <b>{NOMBRE_CLIENTE.strip()}</b>  ·  " + sub
    story.append(P(sub, s_sub))
    story.append(Spacer(1, 10))

    # --- Tarjetas de datos
    datos = [("Precio de lista", money0(precio)), ("Bono MG", money0(bono)),
             ("Pago inicial", money0(PAGO_INICIAL)),
             ("Seguro de contado", money0(SEGURO_CONTADO) if SEGURO_CONTADO else "Por definir"),
             (f"Enganche real ({efectivo / precio:.1%})", money0(efectivo)),
             ("Plazo analizado", f"{PLAZO_DESEADO} meses")]
    tarjetas = Table([[P(l, s_lbl) for l, _ in datos], [P(v_, s_val) for _, v_ in datos]],
                     colWidths=[ancho / len(datos)] * len(datos))
    tarjetas.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), GRIS), ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 2, ROJO),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 8)]))
    story += [tarjetas, Spacer(1, 12)]

    # --- Recomendación
    if ranking:
        _, op, ev, c = ranking[0]
        lineas = [P(f"MEJOR OPCIÓN A {PLAZO_DESEADO} MESES", st("r0", 9, ROJO, True)),
                  P(op["nombre"], st("r1", 15, NEGRO, True, leading=19)),
                  P(f"Baremo {op['baremo']}  ·  bono {ev['forma']}  ·  tasa {c['tasa']:.2f}%  ·  "
                    f"financiado {money(ev['financiado'])}  ·  CXA {money(c['cxa'])}  ·  "
                    f"total CXA + pagos {money(c['total'])}", s_p)]
        menor_m = min(ranking, key=lambda x: x[3]["mens"])
        if menor_m[1] is not op:
            lineas.append(P(f"Menor mensualidad: {menor_m[1]['nombre']} con {money(menor_m[3]['mens'])}, "
                            f"pero cuesta {money(menor_m[0] - ranking[0][0])} más en total.", s_small))
        ceros = [n for n, t in op["tasas"].items() if t == 0]
        if ceros:
            n0 = max(ceros)
            lineas.append(P(f"Esta oferta tiene 0% hasta {n0} meses: "
                            f"{money(mensualidad(ev['financiado'], 0, n0, iva))} al mes.", s_small))
        if SEGURO_CONTADO == 0 and SEGURO_SALE_DEL_PAGO_INICIAL:
            lineas.append(P("Seguro en $0: supone que todo el pago inicial es enganche. "
                            "Consulta la sección del seguro para ver cómo cambia la recomendación.", s_small))
        caja = Table([[lineas, [P("Mensualidad", st("mlbl", 9, TXT2, align=TA_RIGHT)),
                                P(money(c["mens"]), st("mval", 26, ROJO, True, TA_RIGHT, 30))]]],
                     colWidths=[ancho * 0.72, ancho * 0.28])
        caja.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), VERDE), ("LINEBEFORE", (0, 0), (0, 0), 5, VERDE_T),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (0, 0), 12), ("RIGHTPADDING", (-1, 0), (-1, 0), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9)]))
        story += [caja, Spacer(1, 14)]
    else:
        story += [P("Ninguna oferta es válida con este pago inicial y plazo.", s_h2), Spacer(1, 10)]

    # --- Ranking
    story.append(P(f"Ranking de ofertas a {PLAZO_DESEADO} meses", s_h2))
    story.append(P("Ordenadas por el total que paga el cliente después del pago inicial (CXA + mensualidades). "
                   "Como el pago inicial es el mismo en todas, es la comparación justa aunque el monto "
                   "financiado cambie según dónde se aplique el bono.", s_small))
    story.append(Spacer(1, 5))
    cab = ["#", "Oferta", "Baremo PF/PM", "Bono", "Tasa", "Financiado", "CXA", "Mensualidad",
           "Total CXA + pagos", "Seguro permitido"]
    filas_r = [[P(h, s_head) for h in cab]]
    for i, (t, o, e, cc) in enumerate(ranking, 1):
        rs = res["rangos"][o["nombre"]]
        seg = ("N/A" if not SEGURO_SALE_DEL_PAGO_INICIAL else
               "—" if rs is None else
               (f"hasta {money0(rs[1])}" if rs[0] == 0 else f"{money0(rs[0])} a {money0(rs[1])}"))
        filas_r.append([P(i, s_cell_c), P(o["nombre"], s_cell_b if i == 1 else s_cell),
                        P(o["baremo"], s_cell_c), P(e["forma"], s_cell_c), P(f"{cc['tasa']:.2f}%", s_cell_c),
                        P(money(e["financiado"]), s_cell_c), P(money(cc["cxa"]), s_cell_c),
                        P(money(cc["mens"]), s_cell_b if i == 1 else s_cell_c),
                        P(money(t), s_cell_c), P(seg, s_cell_c)])
    no_validas = [o for o in ops if not res["evals"][o["nombre"]]["valida"]
                  or PLAZO_DESEADO not in o["tasas"]]
    for o in no_validas:
        motivo = ("no maneja este plazo" if PLAZO_DESEADO not in o["tasas"]
                  else f"no cumple enganche mínimo {o['min']:.0%}" +
                       (f" (o excede {o['max']:.0%})" if o["max"] else ""))
        filas_r.append([P("—", s_cell_c), P(o["nombre"], st("nv", 8, TXT2)), P(o["baremo"], s_cell_c),
                        P("", s_cell), P(motivo, st("nv2", 7.5, TXT2, align=TA_CENTER))] + [P("")] * 5)
    cw = [0.03, 0.27, 0.08, 0.08, 0.06, 0.1, 0.08, 0.1, 0.11, 0.09]
    tr = Table(filas_r, colWidths=[ancho * x for x in cw], repeatRows=1)
    estilo = [("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if ranking:
        estilo.append(("BACKGROUND", (0, 1), (-1, 1), VERDE))
    for k, o in enumerate(no_validas):
        r = len(ranking) + 1 + k
        estilo += [("BACKGROUND", (0, r), (-1, r), GRIS), ("SPAN", (4, r), (9, r))]
    tr.setStyle(TableStyle(estilo))
    story.append(tr)
    story.append(Spacer(1, 12))
    story.append(P("Reglas consideradas: en Tasa Baja el bono va a la tasa y el cliente paga precio de lista; "
                   "en ofertas de bono flexible el bono va al enganche o al precio (excluyente) y el enganche "
                   "mínimo incluye el bono. Enganche menor a 20%: +4% a la tasa. Enganche máximo 75%. "
                   "No incluye Anualidades, University ni Seminuevos.", s_small))


    # --- Seguro
    if SEGURO_SALE_DEL_PAGO_INICIAL and tramos_pdf:
        story.append(PageBreak())
        story.append(P("¿Cuánto puede valer el seguro?", s_h2))
        story.append(P(f"El seguro se paga de contado con el pago inicial ({money0(PAGO_INICIAL)}), así que entre "
                       f"más cuesta, menos enganche queda. La tabla muestra qué oferta es la ideal a "
                       f"{PLAZO_DESEADO} meses según el costo del seguro.", s_p))
        story.append(Spacer(1, 10))
        validos = [t for t in tramos_pdf if t[2]]
        tope = max(t[1] for t in validos) if validos else PAGO_INICIAL
        tope = min(PAGO_INICIAL, tope * 1.08 + 1)
        nombres = []
        for t in validos:
            if t[2] not in nombres:
                nombres.append(t[2])
        color_de = {n: PALETA[i % len(PALETA)] for i, n in enumerate(nombres)}

        # Barra segmentada
        dw, bh = ancho, 26
        d = Drawing(dw, bh + 26)
        esc = dw / tope
        for (a, b, n, _) in tramos_pdf:
            if a > tope:
                break
            x0, x1 = a * esc, min(b + 10, tope) * esc
            d.add(Rect(x0, 18, max(x1 - x0, 0.8), bh, fillColor=color_de.get(n, GRIS2),
                       strokeColor=colors.white, strokeWidth=0.6))
            if n and x1 - x0 > 50:
                d.add(String((x0 + x1) / 2, 18 + bh / 2 - 3, money0(b), fontName="Helvetica-Bold",
                             fontSize=7.5, fillColor=colors.white, textAnchor="middle"))
        d.add(String(0, 4, "$0", fontName="Helvetica", fontSize=7, fillColor=TXT2))
        d.add(String(dw, 4, money0(tope), fontName="Helvetica", fontSize=7, fillColor=TXT2,
                     textAnchor="end"))
        if SEGURO_CONTADO and SEGURO_CONTADO <= tope:
            xs = SEGURO_CONTADO * esc
            d.add(Rect(xs - 1, 14, 2, bh + 8, fillColor=NEGRO, strokeColor=None))
            d.add(String(xs, 2, f"Tu seguro {money0(SEGURO_CONTADO)}", fontName="Helvetica-Bold",
                         fontSize=7, fillColor=NEGRO, textAnchor="middle"))
        story += [d, Spacer(1, 8)]

        filas_t = [[P(h, s_head) for h in ["", "Seguro de contado", "Mejor oferta", f"Mensualidad a {PLAZO_DESEADO}m"]]]
        sw = []
        for i, (a, b, n, mtxt) in enumerate(tramos_pdf, 1):
            filas_t.append([P(""), P(f"{money0(a)} a {money0(b)}", s_cell_c),
                            P(n or "Ninguna válida (enganche insuficiente)", s_cell_b if n else st("nv3", 8, TXT2)),
                            P(mtxt, s_cell_c)])
            sw.append(("BACKGROUND", (0, i), (0, i), color_de.get(n, GRIS2)))
            if SEGURO_CONTADO and a <= SEGURO_CONTADO <= b:
                sw.append(("BACKGROUND", (1, i), (-1, i), VERDE))
        tt = Table(filas_t, colWidths=[ancho * x for x in (0.02, 0.2, 0.5, 0.28)])
        tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2),
                                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)] + sw))
        story += [tt, Spacer(1, 6),
                  P("Dentro de cada tramo la mensualidad sube un poco: al pagar más seguro queda menos "
                    "enganche y se financia más.", s_small)]
    else:
        story.append(PageBreak())

    # --- Matriz por plazo
    story.append(Spacer(1, 14))
    bloque = [P("Mensualidades por oferta y plazo", s_h2),
              P("Mensualidad (tasa) con el enganche real del cliente. En verde, la mejor opción de cada plazo.",
                s_small), Spacer(1, 5)]
    mejores = {}
    for n in PLAZOS:
        m = res["mejores"][n]
        mejores[n] = m[0]["nombre"] if m else None
    cab = ["Oferta", "Eng. mín", "Bono"] + [f"{n} m" for n in PLAZOS]
    filas_x = [[P(h, s_head) for h in cab]]
    est_x = [("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2),
             ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for r, o in enumerate(ops, 1):
        e = res["evals"][o["nombre"]]
        fila = [P(o["nombre"], s_cell if e["valida"] else st("nvx", 8, TXT2)),
                P(f"{o['min']:.0%}", s_cell_c), P(e["forma"] if e["valida"] else "no aplica", s_cell_c)]
        for j, n in enumerate(PLAZOS):
            cc = costo(o, e, n, iva) if e["valida"] else None
            if cc is None:
                fila.append(P("—", s_cell_c))
            else:
                fila.append(P(f"<b>{money(cc['mens'])}</b><br/><font size=6.5 color='#5A5A5A'>"
                              f"{cc['tasa']:.2f}%</font>", s_cell_c))
                if mejores[n] == o["nombre"]:
                    est_x.append(("BACKGROUND", (3 + j, r), (3 + j, r), VERDE))
        if not e["valida"]:
            est_x.append(("BACKGROUND", (0, r), (2, r), GRIS))
        filas_x.append(fila)
    tx = Table(filas_x, colWidths=[ancho * 0.28, ancho * 0.06, ancho * 0.08] + [ancho * 0.58 / 6] * 6,
               repeatRows=1)
    tx.setStyle(TableStyle(est_x))
    bloque.append(tx)
    story.append(KeepTogether(bloque))

    doc.build(story)
    return archivo.getvalue()

