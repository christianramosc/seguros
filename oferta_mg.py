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
  · No incluye Anualidades, University ni Seminuevos.

Cálculo igual al cotizador de Autoexpress (validado contra cotizaciones reales, oct-2026):
  · Pago inicial = enganche del cliente + seguro del primer año (contado) + comisión por apertura.
    Con lo que trae el cliente se despeja el enganche: enganche = pago − seguro − comisión (+ bono si va al enganche).
  · Enganche % sobre precio + GAP (si se incluye). Capital = precio + GAP − enganche total.
  · Comisión por apertura = CXA% + IVA sobre el monto total a financiar (capital + seguro anual × años 2 en adelante).
  · Tasa con IVA = tasa × 1.16 redondeada a 2 decimales; pagos fijos mensuales.
  · Seguro de vida = 0.82% anual sobre el capital, dentro de la mensualidad.
  · Seguro de los años 2 en adelante: cada año se financia a 12 meses a la misma tasa (sube la mensualidad desde el
    mes 13). El seguro de vida de esos meses se aproxima (diferencia de centavos).

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


# GAP: cada rango de precio del vehículo tiene su monto. PENDIENTE: aún no se tiene la tabla.
# Llénala como [(precio_hasta, monto_gap), ...] en orden ascendente, p. ej. [(400000, 9500), (600000, 13530)].
# Mientras esté vacía, el GAP queda desactivado en la app y en Colab.
TABLA_GAP = []


def gap_disponible():
    return bool(TABLA_GAP)


def monto_gap(precio):
    """Monto de GAP para el precio del vehículo; None si no hay tabla o el precio queda fuera de rango."""
    for hasta, monto in TABLA_GAP:
        if precio <= hasta:
            return float(monto)
    return None


def requiere_precio(vehiculo):
    return CATALOGO[vehiculo]["msrp"] is None


# ------------------------------------------------------------------------------------
# Cálculos (mismo método que el cotizador de Autoexpress)
# ------------------------------------------------------------------------------------
VIDA = 0.0082 / 12          # seguro de vida mensual sobre el capital
VIDA_AJUSTE_SEGURO = 1.2387  # factor observado del seguro de vida sobre el seguro financiado (meses 13+)


def tasa_con_iva(tasa, iva=True):
    return round(tasa * (1 + IVA), 2) if iva else tasa


def pago_fijo(monto, tasa_iva_pct, n):
    r = tasa_iva_pct / 1200
    return monto / n if r == 0 else monto * r / (1 - (1 + r) ** -n)


def mensualidad(monto, tasa_anual_pct, n, iva=True):
    """Pago fijo del capital (sin seguros)."""
    return round(pago_fijo(monto, tasa_con_iva(tasa_anual_pct, iva), n), 2)


def evaluar(op, n, d):
    """Cotiza la oferta `op` a `n` meses con los datos `d` (precio, gap, bono, pago, seguro1, seguro_anual, iva).
    El enganche se despeja del pago inicial del cliente. None si la oferta no maneja ese plazo."""
    if n not in op["tasas"]:
        return None
    anios = n // 12 - 1                       # años de seguro que se financian
    c = op["cxa"] * (1 + IVA)
    precio, gap, bono, sa = d["precio"], d["gap"], d["bono"], d["seguro_anual"]
    if op["modo"] in ("tasa", "sin_bono"):
        candidatos = [("a tasa" if op["modo"] == "tasa" else "sin bono", precio + gap, 0.0)]
    else:
        candidatos = [("al enganche", precio + gap, bono), ("al precio", precio - bono + gap, 0.0)]
    primero = None
    for forma, base, bono_eng in candidatos:
        eng_cli = (d["pago"] - d["seguro1"] - c * (base - bono_eng + sa * anios)) / (1 - c)
        eng_tot = eng_cli + bono_eng
        cap = base - eng_tot
        pct = eng_tot / base
        motivo = ""
        if eng_cli < 0:
            motivo = "El pago inicial no alcanza para seguro y comisión"
        elif pct < op["min"] - 1e-9:
            motivo = f"Enganche {pct:.1%} menor al mínimo {op['min']:.0%}"
        elif op["max"] is not None and pct >= op["max"] - 1e-9:
            motivo = f"Enganche {pct:.1%}: aplica desde {op['max']:.0%} otra tasa"
        elif pct > ENGANCHE_MAX + 1e-9:
            motivo = f"Enganche {pct:.1%} mayor al máximo 75%"
        elif cap <= 0:
            motivo = "No queda monto a financiar"
        ti = tasa_con_iva(op["tasas"][n], d["iva"])
        pm = round(pago_fijo(max(cap, 0), ti, n), 2)
        vida1 = round(max(cap, 0) * VIDA, 2)
        m1 = pm + vida1
        m2 = None
        if anios > 0:
            m2 = pm + round(pago_fijo(sa, ti, 12), 2) + round(vida1 + VIDA * sa * anios * VIDA_AJUSTE_SEGURO, 2)
        total = m1 * min(n, 12) + (m2 * (n - 12) if m2 else 0)
        r = dict(valida=not motivo, motivo=motivo, forma=forma, base=base, pct=pct, eng_cliente=eng_cli,
                 bono_eng=bono_eng, eng_total=eng_tot, financiado=cap, monto_total=cap + sa * anios,
                 cxa=c * (cap + sa * anios), tasa=op["tasas"][n], tasa_iva=ti, pago_capital=pm, vida=vida1,
                 mens=m1, mens2=m2, total=total, plazo=n, seguro1=d["seguro1"], pago=d["pago"])
        if r["valida"]:
            return r
        primero = primero or r
    return primero


def mejor_en(ops, n, d):
    mejor = None
    for op in ops:
        ev = evaluar(op, n, d)
        if ev and ev["valida"] and (mejor is None or ev["total"] < mejor[1]["total"] - 0.005):
            mejor = (op, ev)
    return mejor


def _con_seguro(d, s):
    """Datos con seguro del primer año `s` (si el anual no se capturó, se estima igual al primer año)."""
    return dict(d, seguro1=s, seguro_anual=d["seguro_anual_capturado"] or s)


def rango_seguro(op, n, d):
    """Rango del seguro del primer año (de $10 en $10) en el que la oferta es válida; None si nunca."""
    validos = [s for s in range(0, int(d["pago"]) + 1, 10)
               if (ev := evaluar(op, n, _con_seguro(d, s))) and ev["valida"]]
    return (validos[0], validos[-1]) if validos else None


def tramos_seguro(ops, n, d, max_filas=8):
    """Tramos del costo del seguro del primer año con la mejor oferta en cada uno."""
    crudos, actual = [], None
    for s in range(0, int(d["pago"]) + 1, 10):
        m = mejor_en(ops, n, _con_seguro(d, s))
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
            if t["desde"] > d["pago"] * 0.5:
                break
        else:
            op = next(o for o in ops if o["nombre"] == t["oferta"])
            lo = evaluar(op, n, _con_seguro(d, t["desde"]))
            hi = evaluar(op, n, _con_seguro(d, t["hasta"]))
            salida.append(dict(t, mens_min=lo["mens"], mens_max=hi["mens"]))
        if len(salida) >= max_filas:
            break
    return salida


def analizar(vehiculo, pago, seguro1=0.0, seguro_anual=0.0, plazo=60, precio_manual=0.0, incluir_gap=False,
             iva=True):
    """pago = todo lo que trae el cliente (enganche + seguro del primer año + comisión por apertura).
    incluir_gap: suma el GAP del rango de precio (solo si TABLA_GAP ya tiene montos)."""
    v = CATALOGO[vehiculo]
    precio = precio_manual if precio_manual and precio_manual > 0 else v["msrp"]
    if not precio:
        raise ValueError(f"«{vehiculo}» no tiene precio en el boletín: captura el precio.")
    gap = (monto_gap(precio) or 0.0) if incluir_gap and gap_disponible() else 0.0
    d = dict(precio=precio, gap=gap, bono=v["bono"], pago=pago, seguro1=seguro1 or 0.0,
             seguro_anual_capturado=seguro_anual or 0.0, seguro_anual=(seguro_anual or seguro1 or 0.0), iva=iva)
    ops = ofertas_para(v)
    evals = {o["nombre"]: evaluar(o, plazo, d) for o in ops}
    ranking = sorted([(ev["total"], o, ev) for o in ops if (ev := evals[o["nombre"]]) and ev["valida"]],
                     key=lambda x: x[0])
    matriz = {o["nombre"]: {n: evaluar(o, n, d) for n in PLAZOS} for o in ops}
    mejores = {n: mejor_en(ops, n, d) for n in PLAZOS}
    rangos = {o["nombre"]: (rango_seguro(o, plazo, d) if plazo in o["tasas"] else None) for o in ops}
    return dict(vehiculo=vehiculo, precio=precio, bono=v["bono"], gap=d["gap"], pago=pago, seguro=d["seguro1"],
                seguro_anual=d["seguro_anual"], seguro_anual_estimado=not seguro_anual and bool(seguro1),
                plazo=plazo, iva=iva, ops=ops, evals=evals, ranking=ranking, matriz=matriz, mejores=mejores,
                rangos=rangos, tramos=tramos_seguro(ops, plazo, d))


money = lambda x: "—" if x is None else f"${x:,.2f}"
money0 = lambda x: f"${x:,.0f}"


def texto_rango(rs):
    if rs is None:
        return "No alcanza"
    return f"hasta {money0(rs[1])}" if rs[0] == 0 else f"{money0(rs[0])} a {money0(rs[1])}"


def texto_mens(t):
    if t["oferta"] is None:
        return "—"
    if abs(t["mens_min"] - t["mens_max"]) < 0.01:
        return money(t["mens_min"])
    return f"{money(t['mens_min'])} a {money(t['mens_max'])}"


def desglose(ev):
    """Texto del pago inicial: enganche + seguro + comisión."""
    partes = [f"enganche {money0(ev['eng_cliente'])}", f"seguro {money0(ev['seguro1'])}"]
    if ev["cxa"]:
        partes.append(f"comisión {money0(ev['cxa'])}")
    return " + ".join(partes)


# ------------------------------------------------------------------------------------
# PDF
# ------------------------------------------------------------------------------------
def pdf_bytes(res, cliente=""):
    """PDF del análisis (bytes)."""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                    PageBreak, KeepTogether)
    from reportlab.graphics.shapes import Drawing, Rect, String

    ROJO = colors.HexColor("#C8102E"); NEGRO = colors.HexColor("#1A1A1A")
    GRIS = colors.HexColor("#F3F3F3"); GRIS2 = colors.HexColor("#D9D9D9")
    TXT2 = colors.HexColor("#5A5A5A"); VERDE = colors.HexColor("#E6F4EA"); VERDE_T = colors.HexColor("#1E7B34")
    PALETA = [colors.HexColor(c) for c in ["#C8102E", "#1F4E79", "#2E8B57", "#E07B00", "#6A3D9A", "#00838F",
                                           "#8D6E63"]]
    W, H = landscape(letter)
    M = 36
    ancho = W - 2 * M
    plazo, pago, seguro = res["plazo"], res["pago"], res["seguro"]

    def st(name, size=9, color=NEGRO, bold=False, align=0, leading=None):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                              textColor=color, alignment=align, leading=leading or size * 1.25)
    s_h1, s_sub, s_h2 = st("h1", 20, NEGRO, True), st("sub", 10, TXT2), st("h2", 13, ROJO, True)
    s_p, s_small = st("p", 9, NEGRO, leading=12), st("sm", 7.5, TXT2, leading=9.5)
    s_cell, s_cell_b = st("c", 8, NEGRO, leading=10), st("cb", 8, NEGRO, True, leading=10)
    s_cell_c, s_gris = st("cc", 8, NEGRO, align=TA_CENTER, leading=10), st("g", 7.5, TXT2, leading=9.5)
    s_head = st("hd", 7.5, colors.white, True, TA_CENTER, 9.5)
    s_lbl, s_det = st("lbl", 8, TXT2, True, TA_CENTER), st("det", 7.5, TXT2, align=TA_CENTER, leading=9.5)
    s_val = st("val", 20, NEGRO, True, TA_CENTER, 24)
    P = lambda t, s=s_cell: Paragraph(str(t), s)

    def encabezado(c, doc):
        c.saveState()
        c.setFillColor(NEGRO); c.rect(0, H - 34, W, 34, fill=1, stroke=0)
        c.setFillColor(ROJO); c.rect(0, H - 37, W, 3, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
        c.drawString(M, H - 22, "MG FINANCIAL SERVICES  |  Análisis de mejor oferta")
        c.setFont("Helvetica", 9)
        c.drawRightString(W - M, H - 22, f"Oferta comercial {OFERTA_MES.lower()} · {BOLETIN}")
        c.setFillColor(TXT2); c.setFont("Helvetica", 7.5)
        c.drawString(M, 20, "Cálculo con el método del cotizador de Autoexpress. Cifras de referencia: verificar en "
                            "el cotizador oficial.")
        c.drawRightString(W - M, 20, f"Página {doc.page}")
        c.restoreState()

    archivo = io.BytesIO()
    doc = BaseDocTemplate(archivo, pagesize=landscape(letter), leftMargin=M, rightMargin=M, topMargin=52,
                          bottomMargin=36, title=f"Mejor oferta {res['vehiculo']}", author="MG Colima")
    doc.addPageTemplates([PageTemplate(id="p", onPage=encabezado, frames=[Frame(M, 36, ancho, H - 88, id="f")])])
    story = [P(res["vehiculo"], s_h1)]
    sub = (f"Precio {money0(res['precio'])} · bono MG {money0(res['bono'])}"
           + (f" · GAP {money0(res['gap'])}" if res["gap"] else "")
           + f" · seguro 1er año {money(seguro) if seguro else 'por definir'}"
           + (f" · seguro anual resto del plazo {money(res['seguro_anual'])}"
              + (" (estimado)" if res["seguro_anual_estimado"] else "") if res["seguro_anual"] else "")
           + f" · generado el {datetime.now():%d/%m/%Y}")
    if cliente.strip():
        sub = f"Cliente: <b>{cliente.strip()}</b> · " + sub
    story += [P(sub, s_sub), Spacer(1, 10)]

    ranking = res["ranking"]
    if ranking:
        _, op, ev = ranking[0]
        story.append(P(f"LO QUE PAGA EL CLIENTE · MEJOR OPCIÓN: {op['nombre'].upper()}", st("r0", 9, ROJO, True)))
        story.append(Spacer(1, 4))
        datos = [("PAGO INICIAL", money(pago), desglose(ev)),
                 ("TASA", f"{ev['tasa']:.2f}%", f"{ev['tasa_iva']:.2f}% con IVA · comisión {op['cxa']:.0%}"),
                 ("MENSUALIDAD", money(ev["mens"]),
                  "meses 1-12" + (f" · meses 13+: {money(ev['mens2'])}" if ev["mens2"] else "")),
                 ("PLAZO", f"{plazo} meses", f"enganche {money0(ev['eng_total'])} ({ev['pct']:.1%})")]
        t = Table([[P(a, s_lbl) for a, _, _ in datos], [P(b, s_val) for _, b, _ in datos],
                   [P(c, s_det) for _, _, c in datos]], colWidths=[ancho / 4] * 4)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), VERDE), ("LINEABOVE", (0, 0), (-1, 0), 3, VERDE_T),
                               ("LINEAFTER", (0, 0), (-2, -1), 2, colors.white),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 2), (-1, 2), 8)]))
        story += [t, Spacer(1, 6)]
        notas = [f"Plan {op['nombre']} (baremo {op['baremo']}), bono {ev['forma']}, financiado "
                 f"{money(ev['financiado'])}, total de mensualidades {money(ev['total'])}."]
        menor = min(ranking, key=lambda x: x[2]["mens"])
        if menor[1] is not op:
            notas.append(f"Menor mensualidad: {menor[1]['nombre']} con {money(menor[2]['mens'])}, pero cuesta "
                         f"{money(menor[0] - ranking[0][0])} más en total.")
        if not seguro:
            notas.append("Seguro en $0: supone que todo el pago inicial es enganche. Revisa la sección del seguro.")
        story += [P(" ".join(notas), s_small), Spacer(1, 12)]
    else:
        story += [P(f"Ninguna oferta es válida a {plazo} meses con este pago inicial.", s_h2), Spacer(1, 10)]

    story.append(P(f"Comparativo de ofertas a {plazo} meses", s_h2))
    story.append(P("Con el mismo pago inicial en todas: el enganche se ajusta a lo que queda después del seguro y la "
                   "comisión (más el bono si va al enganche). Ordenadas por el total de mensualidades.", s_small))
    story.append(Spacer(1, 5))
    cab = ["#", "Oferta", "Baremo", "Bono", "Enganche", "Comisión", "Tasa / c IVA", "Financiado", "Mens. 1-12",
           "Mens. 13+", "Total mensualidades", "Seguro permitido"]
    filas = [[P(h, s_head) for h in cab]]
    for i, (tot, o, e) in enumerate(ranking, 1):
        b = s_cell_b if i == 1 else s_cell_c
        filas.append([P(i, s_cell_c), P(o["nombre"], s_cell_b if i == 1 else s_cell), P(o["baremo"], s_cell_c),
                      P(e["forma"], s_cell_c), P(f"{money0(e['eng_total'])}<br/>{e['pct']:.1%}", s_cell_c),
                      P(money(e["cxa"]), s_cell_c), P(f"{e['tasa']:.2f}% / {e['tasa_iva']:.2f}%", s_cell_c),
                      P(money0(e["financiado"]), s_cell_c), P(money(e["mens"]), b), P(money(e["mens2"]), s_cell_c),
                      P(money(tot), s_cell_c), P(texto_rango(res["rangos"][o["nombre"]]), s_cell_c)])
    malas = [o for o in res["ops"] if not (res["evals"][o["nombre"]] and res["evals"][o["nombre"]]["valida"])]
    for o in malas:
        e = res["evals"][o["nombre"]]
        filas.append([P("—", s_cell_c), P(o["nombre"], s_gris), P(o["baremo"], s_cell_c), P("", s_cell),
                      P(e["motivo"] if e else "No maneja este plazo", st("m", 7.5, TXT2, align=TA_CENTER))]
                     + [P("")] * 6 + [P(texto_rango(res["rangos"][o["nombre"]]), s_cell_c)])
    cw = [0.025, 0.19, 0.065, 0.07, 0.07, 0.07, 0.085, 0.08, 0.07, 0.07, 0.095, 0.11]
    tr = Table(filas, colWidths=[ancho * x for x in cw], repeatRows=1)
    est = [("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2), ("TOPPADDING", (0, 0), (-1, -1), 4),
           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if ranking:
        est.append(("BACKGROUND", (0, 1), (-1, 1), VERDE))
    for k in range(len(malas)):
        r = len(ranking) + 1 + k
        est += [("BACKGROUND", (0, r), (-1, r), GRIS), ("SPAN", (4, r), (10, r))]
    tr.setStyle(TableStyle(est))
    story += [tr, Spacer(1, 8),
              P("Mensualidad = pago fijo del capital + seguro de vida (0.82% anual sobre el capital). Desde el mes 13 "
                "se suma el seguro de cada año financiado a 12 meses (aproximado al centavo). Comisión por apertura "
                "= % + IVA sobre el monto total a financiar. Enganche menor a 20%: +4% a la tasa; máximo 75%. "
                "No incluye Anualidades, University ni Seminuevos.", s_small)]

    # --- Seguro
    story.append(PageBreak())
    tramos = res["tramos"]
    story.append(P("¿Cuánto puede valer el seguro del primer año?", s_h2))
    story.append(P(f"El seguro se paga de contado con el pago inicial ({money0(pago)}): entre más cuesta, menos "
                   f"enganche queda. Mejor oferta a {plazo} meses según el costo del seguro"
                   + ("" if res["seguro_anual_estimado"] is False and res["seguro_anual"] else
                      " (el seguro anual del resto del plazo se toma igual al del primer año)") + ".", s_p))
    story.append(Spacer(1, 8))
    validos = [t for t in tramos if t["oferta"]]
    if validos:
        tope = min(pago, max(t["hasta"] for t in validos) * 1.08 + 1)
        nombres = list(dict.fromkeys(t["oferta"] for t in validos))
        color_de = {n: PALETA[i % len(PALETA)] for i, n in enumerate(nombres)}
        d = Drawing(ancho, 52)
        esc = ancho / tope
        for t in tramos:
            if t["desde"] > tope:
                break
            x0, x1 = t["desde"] * esc, min(t["hasta"] + 10, tope) * esc
            d.add(Rect(x0, 18, max(x1 - x0, 0.8), 26, fillColor=color_de.get(t["oferta"], GRIS2),
                       strokeColor=colors.white, strokeWidth=0.6))
            if t["oferta"] and x1 - x0 > 50:
                d.add(String((x0 + x1) / 2, 28, money0(t["hasta"]), fontName="Helvetica-Bold", fontSize=7.5,
                             fillColor=colors.white, textAnchor="middle"))
        d.add(String(0, 4, "$0", fontName="Helvetica", fontSize=7, fillColor=TXT2))
        d.add(String(ancho, 4, money0(tope), fontName="Helvetica", fontSize=7, fillColor=TXT2, textAnchor="end"))
        if seguro and seguro <= tope:
            xs = seguro * esc
            d.add(Rect(xs - 1, 14, 2, 34, fillColor=NEGRO, strokeColor=None))
            d.add(String(xs, 2, f"Tu seguro {money0(seguro)}", fontName="Helvetica-Bold", fontSize=7,
                         fillColor=NEGRO, textAnchor="middle"))
        story += [d, Spacer(1, 8)]
    else:
        color_de = {}
    filas_t = [[P(h, s_head) for h in ["", "Seguro primer año", "Mejor oferta", f"Mensualidad a {plazo} m (1-12)"]]]
    sw = []
    for i, t in enumerate(tramos, 1):
        filas_t.append([P(""), P(f"{money0(t['desde'])} a {money0(t['hasta'])}", s_cell_c),
                        P(t["oferta"] or "Ninguna válida (enganche insuficiente)", s_cell_b if t["oferta"] else s_gris),
                        P(texto_mens(t), s_cell_c)])
        sw.append(("BACKGROUND", (0, i), (0, i), color_de.get(t["oferta"], GRIS2)))
        if seguro and t["desde"] <= seguro <= t["hasta"]:
            sw.append(("BACKGROUND", (1, i), (-1, i), VERDE))
    tt = Table(filas_t, colWidths=[ancho * x for x in (0.02, 0.2, 0.5, 0.28)])
    tt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2), ("TOPPADDING", (0, 0), (-1, -1), 5),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 5)] + sw))
    story += [tt, Spacer(1, 14)]

    # --- Matriz por plazo
    bloque = [P("Mensualidad (meses 1-12) por oferta y plazo", s_h2),
              P("Con el enganche que resulta del pago inicial en cada plazo. En verde, la mejor de cada plazo.",
                s_small), Spacer(1, 5)]
    filas_x = [[P(h, s_head) for h in ["Oferta", "Eng. mín"] + [f"{n} m" for n in PLAZOS]]]
    est_x = [("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
             ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2), ("TOPPADDING", (0, 0), (-1, -1), 4),
             ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    for r, o in enumerate(res["ops"], 1):
        fila = [P(o["nombre"]), P(f"{o['min']:.0%}", s_cell_c)]
        for j, n in enumerate(PLAZOS):
            e = res["matriz"][o["nombre"]][n]
            if not e or not e["valida"]:
                fila.append(P("—", s_cell_c))
                continue
            fila.append(P(f"<b>{money(e['mens'])}</b><br/><font size=6.5 color='#5A5A5A'>{e['tasa']:.2f}%</font>",
                          s_cell_c))
            m = res["mejores"][n]
            if m and m[0]["nombre"] == o["nombre"]:
                est_x.append(("BACKGROUND", (2 + j, r), (2 + j, r), VERDE))
        filas_x.append(fila)
    tx = Table(filas_x, colWidths=[ancho * 0.3, ancho * 0.07] + [ancho * 0.63 / 6] * 6, repeatRows=1)
    tx.setStyle(TableStyle(est_x))
    bloque.append(tx)
    story.append(KeepTogether(bloque))
    doc.build(story)
    return archivo.getvalue()
