# -*- coding: utf-8 -*-
"""
Mejor oferta MG Financial Services — motor de cálculo y PDF.

Compara todas las ofertas del boletín para un auto (Tasa Baja 0% CXA, Tasa Baja 2% CXA, Lanzamiento 8.99%,
Estándar 13.74%, Estándar 17.74% y Especial 12.09%), aplica el bono de la forma que corresponda (a la tasa o al
enganche, excluyente) y dice la mejor opción por plazo y cuánto puede valer el seguro de contado para que cada
opción siga siendo la ideal.

Reglas (boletín BMGFS-16-10-2026, vigente del 09-oct al 02-nov-2026):
  · Tasa baja: el bono ya va a la tasa → el cliente paga precio de lista.
  · Planes Estándar / 12.09% con bono: el bono va al enganche (no al precio); el enganche mínimo de los vehículos
    con bono INCLUYE el bono aplicado al enganche.
  · Enganche < 20% → +4% a la tasa (plan 17.74% para modelos sin bono, desde 10%). Enganche máximo 75%.
  · Enganche mínimo real del cliente (bono al enganche) = enganche sistema − % del bono, exacto. La columna
    «Enganche mínimo real del cliente» del boletín lo redondea (p. ej. 9.96% aparece como 10%); el cotizador acepta
    el mínimo exacto del sistema (validado: MG5 Elegance AT, plan 414, enganche 25% = $99,750 con bono de $60,000).
  · No incluye Anualidades, University ni Seminuevos.

Cálculo igual al cotizador de Autoexpress (validado contra cotizaciones reales, oct-2026):
  · Pago inicial (como en la cotización) = enganche + comisión por apertura + seguro contado año 1 + GAP contado.
  · Seguro año 1: contado (va en el pago inicial) o financiado (se suma al monto a financiar, paga comisión y se
    amortiza en los meses 1-12 a la misma tasa, igual que el de los años 2+). Seguro años 2+: financiado (cada año a
    12 meses desde el mes 13) o contado (el cliente lo paga cada aniversario; no sube la mensualidad).
    Año 1 financiado = «Autoexpress Multianual Fraccionado»: el importe anual se financia también en el año 1.
  · Seguro de vida (prima total repartida en los n meses): sin seguro financiado = 4.1% del capital; con seguro
    financiado = 4.08995% de (capital + importe anual × años del plazo). Validado con 18 cotizaciones (12 a 72 meses).
    El enganche incluye el bono cuando va al enganche.
  · Desembolso del cliente = lo que pone de su bolsa = pago inicial − bono al enganche. Es el dato que se captura:
    enganche = desembolso − seguro − GAP contado − comisión (+ bono si va al enganche).
  · Enganche % sobre precio + GAP (si se incluye). Capital = precio + GAP − enganche total.
  · Comisión por apertura = CXA% + IVA sobre el monto total a financiar (capital + seguro anual × años 2 en adelante).
  · Tasa con IVA = tasa × 1.16 redondeada a 2 decimales; pagos fijos mensuales.
  · Seguro de vida dentro de la mensualidad (ver vida_capital y vida_con_seguro).
  · Seguro de los años 2 en adelante: cada año se financia a 12 meses a la misma tasa (sube la mensualidad desde el
    mes 13). El seguro de vida de esos meses se aproxima (diferencia de centavos).

Para un nuevo boletín: actualiza BOLETIN, CATALOGO, CURVAS y ofertas_para().
"""
import io
import math
from decimal import ROUND_HALF_DOWN, Decimal
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
ENGANCHE_MIN_CLIENTE = 0.10   # referencia del boletín (redondeada); el cotizador acepta el mínimo exacto del sistema
COLORES = {20: "gris", 25: "amarillo", 30: "azul", 40: "verde"}   # color en la tabla de bonos = enganche sistema

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
#   modo "flexible" → bono al enganche
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
        ops.append(dict(nombre=f"Estándar 13.74% + 0% CXA (bono al enganche)", baremo="413/419", cxa=0.00,
                        modo=modo_std, min=(color + 10)/100, max=None, tasas=estandar_1374()))
        ops.append(dict(nombre=f"Estándar 17.74% + 0% CXA (bono al enganche)", baremo="414/441", cxa=0.00,
                        modo=modo_std, min=color/100, max=None, tasas=estandar_1774(True)))
        ops.append(dict(nombre=f"Especial 12.09% + 2% CXA (bono al enganche)", baremo="420/446", cxa=0.02,
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
# Seguro de vida sin seguro de auto financiado: prima total = 4.1% del capital, repartida en los n meses (a 60 meses
# equivale a 0.82% anual), redondeando el medio centavo hacia abajo. Exacta en 11 de 11 cotizaciones (12 a 72 meses).
VIDA_CAPITAL = Decimal("0.041")


def vida_capital(cap, n):
    return float((Decimal(repr(float(cap))) * VIDA_CAPITAL / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN))
# Seguro de vida cuando hay seguro de auto financiado: prima total = 4.08995% de (capital + importe anual × años del
# plazo), repartida en los n meses. Exacta en 11 de 14 cotizaciones reales (24, 36, 48 y 60 meses; contado y
# multianual) y a $0.01 en las otras 3.
VIDA_TOTAL = 0.0408995


def vida_con_seguro(cap, sa, n):
    return round(VIDA_TOTAL * (cap + sa * n / 12) / n, 2)


def tasa_con_iva(tasa, iva=True):
    return round(tasa * (1 + IVA), 2) if iva else tasa


def pago_fijo(monto, tasa_iva_pct, n):
    r = tasa_iva_pct / 1200
    return monto / n if r == 0 else monto * r / (1 - (1 + r) ** -n)


def mensualidad(monto, tasa_anual_pct, n, iva=True):
    """Pago fijo del capital (sin seguros)."""
    return round(pago_fijo(monto, tasa_con_iva(tasa_anual_pct, iva), n), 2)


def evaluar(op, n, d):
    """Cotiza la oferta `op` a `n` meses con los datos `d` (precio, gap financiado, gap_contado, bono, pago =
    desembolso del cliente, seguro1, seguro_anual, iva). El enganche se despeja del desembolso del cliente. Si `d`
    trae `pago_inicial`, ese es el fijo y el desembolso de cada forma del bono = pago inicial − bono al enganche.
    None si la oferta no maneja ese plazo."""
    if n not in op["tasas"]:
        return None
    anios = n // 12 - 1                       # años de seguro que se financian
    c = op["cxa"] * (1 + IVA)
    precio, gap, bono = d["precio"], d["gap"], d["bono"]
    # Año 1 financiado = «Autoexpress Multianual Fraccionado»: el importe primer año de la cotización es $0 y el
    # importe anual se financia también en el año 1 (12 meses), igual que en los años 2+.
    s1f = d["seguro_anual"] if d.get("s1_fin") else 0.0           # seguro año 1 financiado
    s1c = 0.0 if d.get("s1_fin") else d["seguro1"]                # seguro año 1 de contado (pago inicial)
    sa = d["seguro_anual"] if d.get("resto_fin", True) else 0.0   # seguro años 2+ financiado
    if op["modo"] in ("tasa", "sin_bono"):
        candidatos = [("a tasa" if op["modo"] == "tasa" else "sin bono", precio + gap, 0.0)]
    elif d.get("pago_inicial"):   # el pago inicial capturado ya trae el bono al enganche (como en la cotización)
        candidatos = [("al enganche", precio + gap, bono)]
    else:
        candidatos = [("al enganche", precio + gap, bono)]
    primero = None
    for forma, base, bono_eng in candidatos:
        pago = d["pago_inicial"] - bono_eng if d.get("pago_inicial") else d["pago"]
        eng_cli = (pago - s1c - d["gap_contado"] - c * (base - bono_eng + s1f + sa * anios)) / (1 - c)
        eng_tot = eng_cli + bono_eng
        cap = base - eng_tot
        pct = eng_tot / base
        pct_cli = eng_cli / base
        motivo = ""
        if eng_cli < 0:
            motivo = "El desembolso no alcanza para seguro y comisión"
        elif pct < op["min"] - 1e-6:
            motivo = f"Enganche {pct:.2%} menor al mínimo {op['min']:.0%}"
        elif op["max"] is not None and pct >= op["max"] - 1e-9:
            motivo = f"Enganche {pct:.1%}: aplica desde {op['max']:.0%} otra tasa"
        elif pct > ENGANCHE_MAX + 1e-9:
            motivo = f"Enganche {pct:.1%} mayor al máximo 75%"
        elif cap <= 0:
            motivo = "No queda monto a financiar"
        ti = tasa_con_iva(op["tasas"][n], d["iva"])
        pm = round(pago_fijo(max(cap, 0), ti, n), 2)
        vida1 = vida_capital(max(cap, 0), n)
        m1 = pm + vida1
        if s1f:   # seguro año 1 financiado (multianual fraccionado): se amortiza en los meses 1-12
            m1 = pm + round(pago_fijo(s1f, ti, 12), 2) + vida_con_seguro(max(cap, 0), s1f, n)
        m2 = None
        if anios > 0:
            m2 = pm + vida1
            if sa:
                m2 = pm + round(pago_fijo(sa, ti, 12), 2) + vida_con_seguro(max(cap, 0), sa, n)
        total = m1 * min(n, 12) + (m2 * (n - 12) if m2 else 0)
        r = dict(valida=not motivo, motivo=motivo, forma=forma, base=base, pct=pct, eng_cliente=eng_cli,
                 pct_cliente=pct_cli,
                 bono_eng=bono_eng, eng_total=eng_tot, financiado=cap, monto_total=cap + s1f + sa * anios,
                 cxa=c * (cap + s1f + sa * anios), tasa=op["tasas"][n], tasa_iva=ti, pago_capital=pm, vida=vida1,
                 mens=m1, mens2=m2, total=total, plazo=n, seguro1=s1c, seguro1_fin=s1f, gap_contado=d["gap_contado"],
                 resto_fin=bool(sa), aprox_vida=bool(s1f),
                 desembolso=pago, pago_inicial=eng_tot + c * (cap + s1f + sa * anios) + s1c + d["gap_contado"])
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


def tope_seguro(d):
    """Hasta dónde puede llegar el seguro: lo capturado (pago inicial o desembolso)."""
    return int(d.get("pago_inicial") or d["pago"])


def rango_seguro(op, n, d):
    """Rango del seguro del primer año (de $10 en $10) en el que la oferta es válida; None si nunca."""
    validos = [s for s in range(0, tope_seguro(d) + 1, 10)
               if (ev := evaluar(op, n, _con_seguro(d, s))) and ev["valida"]]
    return (validos[0], validos[-1]) if validos else None


def tramos_seguro(ops, n, d, max_filas=8):
    """Tramos del costo del seguro del primer año con la mejor oferta en cada uno."""
    crudos, actual = [], None
    for s in range(0, tope_seguro(d) + 1, 10):
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
            if t["desde"] > tope_seguro(d) * 0.5:
                break
        else:
            op = next(o for o in ops if o["nombre"] == t["oferta"])
            lo = evaluar(op, n, _con_seguro(d, t["desde"]))
            hi = evaluar(op, n, _con_seguro(d, t["hasta"]))
            salida.append(dict(t, mens_min=lo["mens"], mens_max=hi["mens"]))
        if len(salida) >= max_filas:
            break
    return salida


def texto_tasas(op):
    """Tasas por plazo, juntando plazos con la misma tasa: «12-24 m 0% · 36 m 4.10% …»."""
    grupos = []
    for n, t in op["tasas"].items():
        if grupos and grupos[-1][1] == t:
            grupos[-1][0].append(n)
        else:
            grupos.append(([n], t))
    return " · ".join((f"{g[0]} m" if len(g) == 1 else f"{g[0]}-{g[-1]} m") + f" {t:.2f}%" for g, t in grupos)


def requisito(op, d, n=None):
    """Enganche mínimo de la oferta: del sistema (incluye el bono si va al enganche) y real del cliente; y el
    desembolso y el pago inicial mínimos (con seguro, GAP contado y comisión) a `n` meses."""
    precio, gap, bono = d["precio"], d["gap"], d["bono"]
    base = precio + gap
    if op["modo"] == "flexible":
        bono_eng = bono
        cli_pct = op["min"] - bono / base
        forma = "al enganche"
    else:
        bono_eng = 0.0
        cli_pct = op["min"]
        forma = "a la tasa (ya incluido)" if op["modo"] == "tasa" else "sin bono"
    cli_monto = cli_pct * base
    n = n if n in op["tasas"] else max(op["tasas"])
    anios = n // 12 - 1
    c = op["cxa"] * (1 + IVA)
    cap = base - cli_monto - bono_eng
    s1f = d["seguro_anual"] if d.get("s1_fin") else 0.0
    s1c = 0.0 if d.get("s1_fin") else d["seguro1"]
    sa = d["seguro_anual"] if d.get("resto_fin", True) else 0.0
    desembolso_min = cli_monto + s1c + d["gap_contado"] + c * (cap + s1f + sa * anios)
    return dict(oferta=op["nombre"], baremo=op["baremo"], cxa=op["cxa"], tasas=texto_tasas(op),
                min_sistema=op["min"], min_max=op["max"], min_cliente=cli_pct, min_cliente_monto=cli_monto,
                bono=forma, desembolso_min=math.ceil(round(desembolso_min, 2)),
                pago_inicial_min=math.ceil(round(desembolso_min + bono_eng, 2)), plazo_pago_min=n)


def mens_minimo(op, d):
    """Cotización con el enganche mínimo de la oferta en cada plazo de PLAZOS (None si no lo maneja)."""
    salida = {}
    for n in PLAZOS:
        e = None
        if n in op["tasas"]:
            e = evaluar(op, n, dict(d, pago=requisito(op, d, n)["desembolso_min"], pago_inicial=0.0))
        salida[n] = e if e and e["valida"] else None
    return salida


def describir(vehiculo, precio, bono):
    """Descripción de la oferta del boletín para el auto."""
    v = CATALOGO[vehiculo]
    if v["color"]:
        pct_b = bono / precio
        real = v["color"] / 100 - pct_b
        txt = (f"Marcado en {COLORES[v['color']]} en la tabla de bonos (enganche sistema {v['color']}%). Bono MG de "
               f"{money0(bono)} ({pct_b:.1%} del precio de lista {money0(precio)}), pagado 100% por MG Motors "
               f"México. El bono se usa de una sola forma: a la tasa (planes de Tasa Baja: el cliente paga precio de "
               f"lista y aporta todo el enganche) o al enganche (planes Estándar y Especial). Con el bono al enganche el cliente aporta desde {real:.2%} ({money0(real * precio)}) "
               f"y el bono completa el {v['color']}% del sistema en el plan 17.74%; los planes 13.74% y 12.09% piden "
               f"{v['color'] + 10}% y {v['color'] + 20}%.")
    elif v["lanz"]:
        txt = ("Modelo de lanzamiento: tasa 8.99% con 2% de comisión desde 30% de enganche (12 a 60 meses). No tiene "
               "bono; también aplican los planes de toda la gama (13.74% desde 20%, 12.09% desde 30%).")
    else:
        txt = ("Sin bono en la tabla de bonos: aplican los planes de toda la gama (13.74% desde 20%, 17.74% de 10% a "
               "menos de 20%, 12.09% desde 30%).")
    return txt + (" Enganche máximo 75%. Enganche menor a 20%: +4% a la tasa. "
                  f"Oferta vigente {VIGENCIA}.")


GAP_MODOS = ("No", "Contado", "Financiado")


def analizar(vehiculo, pago, seguro1=0.0, seguro_anual=0.0, plazo=60, precio_manual=0.0, gap_modo="No",
             iva=True, pago_inicial=0.0, seguro1_fin=False, resto_fin=True, gap_monto=0.0):
    """pago = desembolso del cliente: lo que pone de su bolsa (pago inicial − bono al enganche).
    pago_inicial: si se captura (> 0) manda sobre `pago`: es el pago inicial de la cotización y el desembolso de cada
    plan sale de él (− bono al enganche si el plan lo lleva).
    gap_modo: «No», «Contado» (va en el pago inicial) o «Financiado» (se suma al precio). gap_monto: el monto de
    GAP de la cotización; si es 0 se busca en TABLA_GAP (pendiente).
    seguro1_fin: el seguro del año 1 se financia (no va en el pago inicial). resto_fin: el de los años 2+ se financia
    (si no, el cliente lo paga de contado cada año)."""
    v = CATALOGO[vehiculo]
    precio = precio_manual if precio_manual and precio_manual > 0 else v["msrp"]
    if not precio:
        raise ValueError(f"«{vehiculo}» no tiene precio en el boletín: captura el precio.")
    gap = 0.0
    if gap_modo != "No":
        gap = float(gap_monto) if gap_monto and gap_monto > 0 else ((monto_gap(precio) or 0.0) if gap_disponible()
                                                                    else 0.0)
    d = dict(precio=precio, gap=gap if gap_modo == "Financiado" else 0.0,
             gap_contado=gap if gap_modo == "Contado" else 0.0, bono=v["bono"], pago=pago_inicial or pago,
             pago_inicial=pago_inicial or 0.0, seguro1=seguro1 or 0.0,
             seguro_anual_capturado=seguro_anual or 0.0, seguro_anual=(seguro_anual or seguro1 or 0.0), iva=iva,
             s1_fin=bool(seguro1_fin), resto_fin=bool(resto_fin))
    ops = ofertas_para(v)
    evals = {o["nombre"]: evaluar(o, plazo, d) for o in ops}
    ranking = sorted([(ev["total"], o, ev) for o in ops if (ev := evals[o["nombre"]]) and ev["valida"]],
                     key=lambda x: x[0])
    matriz = {o["nombre"]: {n: evaluar(o, n, d) for n in PLAZOS} for o in ops}
    mejores = {n: mejor_en(ops, n, d) for n in PLAZOS}
    rangos = {o["nombre"]: (rango_seguro(o, plazo, d) if plazo in o["tasas"] else None) for o in ops}
    return dict(vehiculo=vehiculo, precio=precio, bono=v["bono"], gap=gap, gap_modo=gap_modo if gap else "No",
                pago=(ranking[0][2]["desembolso"] if ranking else pago) if pago_inicial else pago,
                pago_inicial=pago_inicial or 0.0, tope_seguro=tope_seguro(d), seguro=d["seguro1"],
                seguro_anual=d["seguro_anual"], seguro_anual_estimado=not seguro_anual and bool(seguro1),
                seguro1_fin=bool(seguro1_fin), resto_fin=bool(resto_fin),
                plazo=plazo, iva=iva, ops=ops, evals=evals, ranking=ranking, matriz=matriz, mejores=mejores,
                rangos=rangos, tramos=tramos_seguro(ops, plazo, d),
                color=COLORES.get(v["color"]), descripcion=describir(vehiculo, precio, v["bono"]),
                requisitos=[requisito(o, d, plazo) for o in ops],
                mens_min={o["nombre"]: mens_minimo(o, d) for o in ops})


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
    """Texto del pago inicial: enganche + comisión + seguro año 1 + GAP contado."""
    partes = [f"eng. {money0(ev['eng_total'])}"]
    if ev["cxa"]:
        partes.append(f"com. {money0(ev['cxa'])}")
    if ev["seguro1"] or not ev["seguro1_fin"]:
        partes.append(f"seguro {money0(ev['seguro1'])}")
    if ev["gap_contado"]:
        partes.append(f"GAP {money0(ev['gap_contado'])}")
    return " + ".join(partes)


def desglose_desembolso(ev):
    """Texto del desembolso del cliente: enganche propio + comisión + seguro año 1 + GAP contado."""
    partes = [f"eng. propio {money0(ev['eng_cliente'])} ({ev['pct_cliente']:.1%})"]
    if ev["cxa"]:
        partes.append(f"com. {money0(ev['cxa'])}")
    if ev["seguro1"] or not ev["seguro1_fin"]:
        partes.append(f"seguro {money0(ev['seguro1'])}")
    if ev["gap_contado"]:
        partes.append(f"GAP {money0(ev['gap_contado'])}")
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
    plazo, pago, seguro = res["plazo"], res["pago"], res["seguro"]   # pago = desembolso del cliente

    def st(name, size=9, color=NEGRO, bold=False, align=0, leading=None):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                              textColor=color, alignment=align, leading=leading or size * 1.25)
    s_h1, s_sub, s_h2 = st("h1", 20, NEGRO, True), st("sub", 10, TXT2), st("h2", 13, ROJO, True)
    s_p, s_small = st("p", 9, NEGRO, leading=12), st("sm", 7.5, TXT2, leading=9.5)
    s_cell, s_cell_b = st("c", 8, NEGRO, leading=10), st("cb", 8, NEGRO, True, leading=10)
    s_cell_c, s_gris = st("cc", 8, NEGRO, align=TA_CENTER, leading=10), st("g", 7.5, TXT2, leading=9.5)
    s_head = st("hd", 7.5, colors.white, True, TA_CENTER, 9.5)
    s_lbl, s_det = st("lbl", 8, TXT2, True, TA_CENTER), st("det", 7.5, TXT2, align=TA_CENTER, leading=9.5)
    s_val = st("val", 18, NEGRO, True, TA_CENTER, 22)
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
           + (f" · GAP {res['gap_modo'].lower()} {money0(res['gap'])}" if res["gap"] else "")
           + f" · seguro 1er año {money(seguro) if seguro else 'por definir'}"
           + (" (financiado)" if seguro and res.get("seguro1_fin") else " (contado)" if seguro else "")
           + (f" · seguro anual resto del plazo {money(res['seguro_anual'])}"
              + (" (estimado)" if res["seguro_anual_estimado"] else "")
              + (" financiado" if res.get("resto_fin", True) else " de contado cada año")
              if res["seguro_anual"] else "")
           + f" · generado el {datetime.now():%d/%m/%Y}")
    if cliente.strip():
        sub = f"Cliente: <b>{cliente.strip()}</b> · " + sub
    story += [P(sub, s_sub), Spacer(1, 10)]

    ranking = res["ranking"]
    if ranking:
        _, op, ev = ranking[0]
        story.append(P(f"LO QUE PAGA EL CLIENTE · MEJOR OPCIÓN: {op['nombre'].upper()}", st("r0", 9, ROJO, True)))
        story.append(Spacer(1, 4))
        datos = [("PAGO INICIAL", money(ev["pago_inicial"]), desglose(ev)),
                 ("DESEMBOLSO DEL CLIENTE", money(ev["desembolso"]), desglose_desembolso(ev)),
                 ("TASA", f"{ev['tasa']:.2f}%", f"{ev['tasa_iva']:.2f}% con IVA · comisión {op['cxa']:.0%}"),
                 ("MENSUALIDAD", money(ev["mens"]),
                  "meses 1-12" + (f" · meses 13+: {money(ev['mens2'])}" if ev["mens2"] else "")),
                 ("PLAZO", f"{plazo} meses", f"financiado {money0(ev['financiado'])}")]
        t = Table([[P(a, s_lbl) for a, _, _ in datos], [P(b, s_val) for _, b, _ in datos],
                   [P(c, s_det) for _, _, c in datos]], colWidths=[ancho / 5] * 5)
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
            notas.append("Seguro en $0: supone que todo el desembolso es enganche. Revisa la sección del seguro.")
        story += [P(" ".join(notas), s_small), Spacer(1, 12)]
    else:
        story += [P(f"Ninguna oferta es válida a {plazo} meses con este desembolso.", s_h2), Spacer(1, 10)]

    story.append(P(f"Comparativo de ofertas a {plazo} meses", s_h2))
    story.append(P("Con el mismo desembolso del cliente en todas: el enganche se ajusta a lo que queda después del "
                   "seguro y la comisión (más el bono si va al enganche). Pago inicial = enganche + comisión + seguro "
                   "año 1 + GAP contado. Ordenadas por el total de mensualidades.", s_small))
    story.append(Spacer(1, 5))
    cab = ["#", "Oferta", "Bono", "Eng. cliente", "Eng. total", "Com.", "Pago inicial", "Tasa / c IVA",
           "Financ.", "Mens. 1-12", "Mens. 13+", "Total mens.", "Seguro permitido"]
    nom = lambda o, est: P(f"{o['nombre']}<br/><font size=6.5 color='#5A5A5A'>Baremo {o['baremo']}</font>", est)
    filas = [[P(h, s_head) for h in cab]]
    for i, (tot, o, e) in enumerate(ranking, 1):
        b = s_cell_b if i == 1 else s_cell_c
        filas.append([P(i, s_cell_c), nom(o, s_cell_b if i == 1 else s_cell), P(e["forma"], s_cell_c),
                      P(f"{money0(e['eng_cliente'])}<br/>{e['pct_cliente']:.1%}", b),
                      P(f"{money0(e['eng_total'])}<br/>{e['pct']:.1%}", s_cell_c),
                      P(money(e["cxa"]), s_cell_c), P(money0(e["pago_inicial"]), s_cell_c),
                      P(f"{e['tasa']:.2f}% / {e['tasa_iva']:.2f}%", s_cell_c),
                      P(money0(e["financiado"]), s_cell_c), P(money(e["mens"]), b), P(money(e["mens2"]), s_cell_c),
                      P(money(tot), s_cell_c), P(texto_rango(res["rangos"][o["nombre"]]), s_cell_c)])
    malas = [o for o in res["ops"] if not (res["evals"][o["nombre"]] and res["evals"][o["nombre"]]["valida"])]
    for o in malas:
        e = res["evals"][o["nombre"]]
        filas.append([P("—", s_cell_c), nom(o, s_gris), P("", s_cell),
                      P(e["motivo"] if e else "No maneja este plazo", st("m", 7.5, TXT2, align=TA_CENTER))]
                     + [P("")] * 8 + [P(texto_rango(res["rangos"][o["nombre"]]), s_cell_c)])
    cw = [0.025, 0.16, 0.075, 0.07, 0.07, 0.06, 0.075, 0.08, 0.065, 0.07, 0.07, 0.085, 0.095]
    tr = Table(filas, colWidths=[ancho * x for x in cw], repeatRows=1)
    est = [("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
           ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2), ("TOPPADDING", (0, 0), (-1, -1), 4),
           ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
    if ranking:
        est.append(("BACKGROUND", (0, 1), (-1, 1), VERDE))
    for k in range(len(malas)):
        r = len(ranking) + 1 + k
        est += [("BACKGROUND", (0, r), (-1, r), GRIS), ("SPAN", (3, r), (11, r))]
    tr.setStyle(TableStyle(est))
    story += [tr, Spacer(1, 8),
              P("Mensualidad = pago fijo del capital + seguro de vida (4.1% del capital repartido en el plazo; con "
                "seguro financiado, 4.09% de capital + seguros). Desde el mes 13 "
                "se suma el seguro de cada año financiado a 12 meses (aproximado al centavo). Comisión por apertura "
                "= % + IVA sobre el monto total a financiar. Enganche menor a 20%: +4% a la tasa; máximo 75%. "
                "No incluye Anualidades, University ni Seminuevos.", s_small)]

    # --- Oferta del boletín para el auto
    story.append(PageBreak())
    story.append(P("Oferta del boletín para este auto", s_h2))
    story.append(P(res["descripcion"], s_p))
    story.append(Spacer(1, 6))
    cab_o = ["Oferta", "Tasas por plazo", "Com.", "Bono", "Eng. mínimo sistema",
             "Eng. mínimo real del cliente", f"Desembolso mínimo ({plazo} m)", f"Pago inicial mínimo ({plazo} m)"]
    filas_o = [[P(h, s_head) for h in cab_o]]
    for q in res["requisitos"]:
        sis = f"{q['min_sistema']:.0%}" + (f" a &lt;{q['min_max']:.0%}" if q["min_max"] else "")
        otro = "" if q["plazo_pago_min"] == plazo else f" ({q['plazo_pago_min']} m)"
        filas_o.append([P(f"{q['oferta']}<br/><font size=6.5 color='#5A5A5A'>Baremo {q['baremo']}</font>"),
                        P(q["tasas"], st("tz", 7.5, NEGRO, leading=9.5)), P(f"{q['cxa']:.0%}", s_cell_c),
                        P(q["bono"], s_cell_c), P(sis, s_cell_c),
                        P(f"<b>{q['min_cliente']:.2%}</b><br/>{money0(q['min_cliente_monto'])}", s_cell_c),
                        P(money0(q["desembolso_min"]) + otro, s_cell_c),
                        P(money0(q["pago_inicial_min"]) + otro, s_cell_c)])
    to = Table(filas_o, colWidths=[ancho * x for x in (0.2, 0.22, 0.06, 0.1, 0.08, 0.11, 0.115, 0.115)],
               repeatRows=1)
    to.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2), ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [to, Spacer(1, 4),
              P("Eng. mínimo real del cliente: lo que el cliente pone de su bolsa. Con bono al enganche = enganche "
                "sistema − % del bono (exacto; el boletín lo redondea); en Tasa Baja el bono va a la tasa y el cliente pone todo el "
                "enganche. Desembolso mínimo = enganche propio + seguro año 1 + GAP contado + comisión; pago inicial "
                "mínimo = desembolso + bono al enganche (como lo muestra la cotización).", s_small),
              Spacer(1, 14)]

    # --- Seguro
    tramos = res["tramos"]
    story.append(P("¿Cuánto puede valer el seguro del primer año?", s_h2))
    story.append(P(f"El seguro se paga de contado con "
                   + (f"el pago inicial ({money0(res['pago_inicial'])})" if res["pago_inicial"] else
                      f"el desembolso del cliente ({money0(pago)})") + ": entre más cuesta, menos "
                   f"enganche queda. Mejor oferta a {plazo} meses según el costo del seguro"
                   + ("" if res["seguro_anual_estimado"] is False and res["seguro_anual"] else
                      " (el seguro anual del resto del plazo se toma igual al del primer año)") + ".", s_p))
    story.append(Spacer(1, 8))
    validos = [t for t in tramos if t["oferta"]]
    if validos:
        tope = min(res["tope_seguro"], max(t["hasta"] for t in validos) * 1.08 + 1)
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
              P("Con el enganche que resulta del desembolso del cliente en cada plazo. En verde, la mejor de cada plazo.",
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


# ------------------------------------------------------------------------------------
# Tabla de mínimos de toda la oferta (sin seguro: «+ seguro de contado»)
# ------------------------------------------------------------------------------------
def tabla_minimos(iva=True):
    """Por auto y plan: enganche mínimo (sistema y real del cliente), comisión, desembolso y pago inicial mínimos
    sin el seguro de contado, y la mensualidad (meses 1-12) con ese enganche mínimo en cada plazo, de 12 meses al
    plazo máximo del plan. Los modelos sin precio en el boletín salen solo con porcentajes y tasas."""
    salida = []
    for veh, v in CATALOGO.items():
        if veh.startswith("OTRO"):
            continue
        precio = v["msrp"]
        d = dict(precio=precio or 0.0, gap=0.0, gap_contado=0.0, bono=v["bono"], pago=0.0, seguro1=0.0,
                 seguro_anual=0.0, seguro_anual_capturado=0.0, iva=iva)
        planes = []
        for op in ofertas_para(v):
            nmax = max(op["tasas"])
            fila = dict(oferta=op["nombre"], baremo=op["baremo"], cxa=op["cxa"], min_sistema=op["min"],
                        min_max=op["max"], plazo_max=nmax, tasas=op["tasas"],
                        bono=("a la tasa" if op["modo"] == "tasa" else "al enganche" if op["modo"] == "flexible"
                              else "sin bono"))
            if precio:
                q = requisito(op, d, nmax)
                emax = evaluar(op, nmax, dict(d, pago=q["desembolso_min"]))
                fila.update(min_cliente=q["min_cliente"], min_cliente_monto=q["min_cliente_monto"],
                            comision=emax["cxa"], desembolso_min=q["desembolso_min"],
                            pago_inicial_min=q["pago_inicial_min"], financiado=emax["financiado"],
                            mens={n: (e["mens"] if e else None) for n, e in mens_minimo(op, d).items()})
            else:
                fila.update(min_cliente=op["min"])
            planes.append(fila)
        salida.append(dict(vehiculo=veh, precio=precio, bono=v["bono"], color=COLORES.get(v["color"]),
                           sistema=v["color"], lanz=v["lanz"], planes=planes,
                           min_real=(v["color"] / 100 - v["bono"] / precio if v["color"] else None)))
    return salida


def pdf_minimos(iva=True):
    """PDF con la tabla de mínimos de toda la oferta (bytes): un bloque por auto con los mínimos de cada plan y las
    mensualidades de 12 meses al plazo máximo."""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                    KeepTogether)

    ROJO = colors.HexColor("#C8102E"); NEGRO = colors.HexColor("#1A1A1A"); GRIS2 = colors.HexColor("#D9D9D9")
    TXT2 = colors.HexColor("#5A5A5A"); GRIS = colors.HexColor("#F3F3F3")
    VERDE = colors.HexColor("#E6F4EA")
    FONDO = {"gris": "#EDEDED", "amarillo": "#FFF4CC", "azul": "#DCE6F2", "verde": "#E2F0D9", None: "#F3F3F3"}
    W, H = landscape(letter)
    M = 28
    ancho = W - 2 * M

    def st(name, size=8, color=NEGRO, bold=False, align=0, leading=None):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                              textColor=color, alignment=align, leading=leading or size * 1.25)
    s_h1, s_p, s_small = st("h1", 16, NEGRO, True), st("p", 8.5, NEGRO, leading=11), st("sm", 7, TXT2, leading=9)
    s_c, s_cc, s_cb = st("c", 7.3, leading=9), st("cc", 7.3, align=TA_CENTER, leading=9), \
        st("cb", 7.3, NEGRO, True, TA_CENTER, 9)
    s_head = st("hd", 6.8, colors.white, True, TA_CENTER, 8.4)
    s_veh = st("veh", 9, NEGRO, True, leading=11)
    P = lambda t, s=s_c: Paragraph(str(t), s)
    MAS = "<br/><font size=6 color='#C8102E'>+ seguro</font>"
    tasa = lambda t: f"<br/><font size=6 color='#5A5A5A'>{t:.2f}%</font>"

    def encabezado(c, doc):
        c.saveState()
        c.setFillColor(NEGRO); c.rect(0, H - 32, W, 32, fill=1, stroke=0)
        c.setFillColor(ROJO); c.rect(0, H - 35, W, 3, fill=1, stroke=0)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11)
        c.drawString(M, H - 21, "MG FINANCIAL SERVICES  |  Mínimos de la oferta comercial")
        c.setFont("Helvetica", 8.5)
        c.drawRightString(W - M, H - 21, f"Oferta comercial {OFERTA_MES.lower()} · {BOLETIN} · vigente {VIGENCIA}")
        c.setFillColor(TXT2); c.setFont("Helvetica", 7)
        c.drawString(M, 14, "Montos sin seguro de contado: súmalo al desembolso y al pago inicial. Mensualidad meses "
                            "1-12 con el enganche mínimo (incluye seguro de vida); bajo cada una, la tasa sin IVA.")
        c.drawRightString(W - M, 14, f"Página {doc.page}")
        c.restoreState()

    archivo = io.BytesIO()
    doc = BaseDocTemplate(archivo, pagesize=landscape(letter), leftMargin=M, rightMargin=M, topMargin=44,
                          bottomMargin=26, title=f"Mínimos oferta {BOLETIN}", author="MG Colima")
    doc.addPageTemplates([PageTemplate(id="p", onPage=encabezado, frames=[Frame(M, 26, ancho, H - 70, id="f")])])
    story = [P(f"Tabla de mínimos por auto · {OFERTA_MES}", s_h1), Spacer(1, 4),
             P("Un bloque por auto y una fila por plan. <b>Enganche:</b> mínimo del sistema (incluye el bono cuando "
               "va al enganche) y <b>mínimo real del cliente</b> (lo que pone de su bolsa). <b>Lo que paga al "
               "inicio:</b> comisión por apertura, <b>desembolso mínimo</b> (enganche propio + comisión) y <b>pago "
               "inicial mínimo</b> como en la cotización (enganche + comisión); a ambos hay que sumarles el seguro de "
               "contado (y el GAP de contado si aplica). <b>Mensualidad con el enganche mínimo</b> de 12 meses al "
               "plazo máximo de cada plan («—» si el plan no maneja ese plazo); en verde, la menor del auto en cada "
               "plazo. La comisión aquí no incluye la del seguro financiado (2.32% de los seguros de los años 2 en "
               "adelante en planes con comisión). Color del bloque = color en la tabla de bonos (enganche sistema): "
               "gris 20%, amarillo 25%, azul 30%, verde 40%.", s_p), Spacer(1, 8)]

    fijas = ["Plan", "Eng. mín. sistema", "Eng. mín. real cliente", "Comisión", "Desembolso mínimo",
             "Pago inicial mínimo", "Financiado"]
    cw = [0.22, 0.055, 0.08, 0.055, 0.075, 0.075, 0.065] + [0.375 / len(PLAZOS)] * len(PLAZOS)
    ncol = len(fijas) + len(PLAZOS)
    c0 = len(fijas)
    cab1 = [P("Plan", s_head)] + [P("ENGANCHE", s_head), ""] + [P("LO QUE PAGA AL INICIO", s_head), "", "", ""] + \
           [P("MENSUALIDAD CON EL ENGANCHE MÍNIMO (MESES 1-12)", s_head)] + [""] * (len(PLAZOS) - 1)
    cab2 = [""] + [P(h, s_head) for h in fijas[1:]] + [P(f"{n} meses", s_head) for n in PLAZOS]
    for a in tabla_minimos(iva):
        if a["precio"]:
            det = f"precio {money0(a['precio'])}"
            if a["bono"]:
                det += (f" · bono {money0(a['bono'])} ({a['bono'] / a['precio']:.1%}) · color {a['color']} "
                        f"(sistema {a['sistema']}%) · el cliente aporta desde {a['min_real']:.2%}")
            else:
                det += " · sin bono"
        else:
            det = "lanzamiento · sin precio en el boletín: montos según el precio del auto (solo % y tasas)"
        # fila 0: auto · filas 1-2: cabeceras agrupadas · de la 3 en adelante: un plan por fila
        filas = [[P(f"{a['vehiculo']} <font size=7.3 color='#5A5A5A'>· {det}</font>", s_veh)] + [""] * (ncol - 1),
                 cab1, cab2]
        est = [("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FONDO[a["color"]])),
               ("BACKGROUND", (0, 1), (-1, 2), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
               ("SPAN", (0, 1), (0, 2)), ("SPAN", (1, 1), (2, 1)), ("SPAN", (3, 1), (6, 1)), ("SPAN", (c0, 1), (-1, 1)),
               ("LINEBELOW", (1, 1), (-1, 1), 0.4, TXT2),
               ("LINEBEFORE", (1, 1), (1, -1), 0.6, GRIS2), ("LINEBEFORE", (3, 1), (3, -1), 0.6, GRIS2),
               ("LINEBEFORE", (c0, 1), (c0, -1), 0.6, GRIS2), ("BOX", (0, 0), (-1, -1), 0.6, NEGRO),
               ("TOPPADDING", (0, 0), (-1, -1), 1.8), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
               ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3)]
        menor = {n: min((q["mens"][n] for q in a["planes"] if q.get("mens") and q["mens"].get(n)), default=None)
                 for n in PLAZOS}
        for q in a["planes"]:
            r = len(filas)
            sis = f"{q['min_sistema']:.0%}" + (f" a &lt;{q['min_max']:.0%}" if q["min_max"] else "")
            plan = (f"<b>{q['oferta']}</b><br/><font size=6.3 color='#5A5A5A'>baremo {q['baremo']} · com. "
                    f"{q['cxa']:.0%} · bono {q['bono']}</font>")
            if a["precio"]:
                fila = [P(plan), P(sis, s_cc),
                        P(f"<b>{q['min_cliente']:.2%}</b><br/>{money0(q['min_cliente_monto'])}", s_cc),
                        P(money0(q["comision"]), s_cc), P(money0(q["desembolso_min"]) + MAS, s_cb),
                        P(money0(q["pago_inicial_min"]) + MAS, s_cb), P(money0(q["financiado"]), s_cc)]
                for j, n in enumerate(PLAZOS):
                    m = q["mens"].get(n)
                    fila.append(P(money(m) + tasa(q["tasas"][n]), s_cc) if m else P("—", s_cc))
                    if m and menor[n] is not None and abs(m - menor[n]) < 0.005:
                        est.append(("BACKGROUND", (c0 + j, r), (c0 + j, r), VERDE))
            else:
                fila = [P(plan), P(sis, s_cc), P(f"<b>{q['min_cliente']:.2%}</b>", s_cc)] + [P("—", s_cc)] * 4
                fila += [P(f"{q['tasas'][n]:.2f}%", s_cc) if n in q["tasas"] else P("—", s_cc) for n in PLAZOS]
            filas.append(fila)
            est.append(("LINEBELOW", (0, r), (-1, r), 0.3, GRIS2))
            if (r - 3) % 2:
                est.append(("BACKGROUND", (0, r), (c0 - 1, r), GRIS))
        t = Table(filas, colWidths=[ancho * x for x in cw])
        t.setStyle(TableStyle(est))
        story += [KeepTogether(t), Spacer(1, 9)]
    story.append(P("Enganche mínimo real del cliente: con bono al enganche = enganche sistema − % del bono, nunca menos "
                   "de 10%; en Tasa Baja el bono va a la tasa y el cliente pone todo el enganche. Enganche menor a 20%: "
                   "+4% a la tasa; máximo 75%. Cálculo con el método del cotizador de Autoexpress: verificar en el "
                   "cotizador oficial.", s_small))
    doc.build(story)
    return archivo.getvalue()
