# -*- coding: utf-8 -*-
"""
Mejor oferta MG Financial Services — motor de cálculo y PDF.

Compara todas las ofertas del boletín para un auto (Tasa Baja 0% CXA, Tasa Baja 2% CXA, Lanzamiento 8.99%,
Estándar 13.74%, Estándar 17.74% y Especial 12.09%), aplica el bono de cada forma posible (a la tasa, al enganche o al
precio, excluyente) y las compara como opciones separadas y dice la mejor opción por plazo y cuánto puede valer el seguro de contado para que cada
opción siga siendo la ideal.

Reglas del boletín (las tasas, bonos, precios y mínimos salen de los datos de la oferta; ver aplicar()):
  · Tasa baja: el bono ya va a la tasa → el cliente paga precio de lista.
  · Planes Estándar / 12.09% con bono: el bono puede ir al enganche o al precio (se muestran como dos opciones).
    Al enganche, el enganche mínimo INCLUYE el bono; al precio, el precio baja en el bono y el enganche mínimo se
    calcula sobre el precio con descuento.
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

Para un nuevo boletín: súbelo en la página «Oferta comercial» de la app (boletin_mg.py lee el PDF y aplicar() usa
sus datos). El método de cálculo no cambia.
"""
import hashlib
import io
import json
import math
import os
from datetime import date, datetime
from decimal import ROUND_HALF_DOWN, Decimal

PLAZOS = [12, 24, 36, 48, 60, 72]
IVA = 0.16
ENGANCHE_MIN_CLIENTE = 0.10   # referencia del boletín (redondeada); el cotizador acepta el mínimo exacto del sistema
OTRO = "OTRO MODELO SIN BONO (precio manual)"

# ------------------------------------------------------------------------------------
# La oferta comercial (datos del boletín)
#   La base viene en oferta_base.json (boletín de octubre 2026). Cuando se sube un boletín nuevo en la página
#   «Oferta comercial», boletin_mg.py lo lee y aplicar() reemplaza estos datos; el cálculo no cambia.
#   Formato: ver boletin_mg.py (porcentajes en %, montos en pesos, plazos y enganches sistema como llaves de texto).
# ------------------------------------------------------------------------------------
BASE_JSON = "oferta_base.json"


def _tasas(t):
    return {int(p): float(x) for p, x in sorted((t or {}).items(), key=lambda kv: int(kv[0]))}


def huella(oferta):
    """Identificador corto de los datos de la oferta (cambia si cambia cualquier precio, bono, tasa o mínimo)."""
    datos = {k: oferta.get(k) for k in ("boletin", "mes", "vigencia", "inicio", "fin", "enganche_max", "colores",
                                        "vehiculos", "planes_bono", "planes_sin_bono")}
    return hashlib.sha1(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:10]


def oferta_base():
    """Oferta incluida en la app (oferta_base.json; en el script de Colab va incrustada en OFERTA_BASE)."""
    if "OFERTA_BASE" in globals():
        return json.loads(json.dumps(globals()["OFERTA_BASE"]))
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), BASE_JSON), encoding="utf-8") as f:
        return json.load(f)


def aplicar(oferta):
    """Usa `oferta` (dict del boletín) para todos los cálculos y PDFs."""
    global OFERTA, OFERTA_ID, BOLETIN, OFERTA_MES, VIGENCIA, VIGENCIA_FIN, ENGANCHE_MAX, COLORES, CATALOGO, \
        PLANES_BONO, PLANES_SIN_BONO
    o = json.loads(json.dumps(oferta))
    pct = lambda x: float(x) / 100
    planes_bono = [dict(baremo=str(p["baremo"]), cxa=pct(p.get("cxa") or 0),
                        min={int(s): pct(m) for s, m in (p.get("min") or {}).items() if m not in (None, "")},
                        tasas=_tasas(p["tasas"])) for p in o.get("planes_bono") or []]
    planes_sin = [dict(baremo=str(p["baremo"]), cxa=pct(p.get("cxa") or 0), min=pct(p.get("min") or 0),
                       max=pct(p["max"]) if p.get("max") else None, tasas=_tasas(p["tasas"]))
                  for p in o.get("planes_sin_bono") or []]
    catalogo = {}
    for nombre, v in (o.get("vehiculos") or {}).items():
        lz = v.get("lanzamiento")
        catalogo[nombre] = dict(
            msrp=v.get("msrp") or None, bono=v.get("bono") or 0, color=v.get("sistema") or None,
            tb=[dict(eng=t["eng"], cxa=pct(t.get("cxa") or 0), baremo=str(t["baremo"]), tasas=_tasas(t["tasas"]))
                for t in v.get("tasa_baja") or []],
            lanz=(dict(eng=lz["eng"], cxa=pct(lz.get("cxa") or 0), baremo=str(lz["baremo"]), tasas=_tasas(lz["tasas"]))
                  if lz else None))
    catalogo[OTRO] = dict(msrp=None, bono=0, color=None, tb=[], lanz=None)
    OFERTA, OFERTA_ID = o, huella(o)
    BOLETIN = o.get("boletin") or "boletín sin clave"
    OFERTA_MES = o.get("mes") or ""
    VIGENCIA = o.get("vigencia") or ""
    try:
        VIGENCIA_FIN = date.fromisoformat(o["fin"]) if o.get("fin") else None
    except ValueError:
        VIGENCIA_FIN = None
    ENGANCHE_MAX = pct(o.get("enganche_max") or 75)
    COLORES = {int(s): c for s, c in (o.get("colores") or {}).items()}
    PLANES_BONO, PLANES_SIN_BONO, CATALOGO = planes_bono, planes_sin, catalogo


def color_de(sistema):
    return COLORES.get(sistema) or f"sistema {sistema}%"


def min_color(plan, sistema):
    """Enganche mínimo de un plan con bono para el enganche sistema del auto. Si el boletín no trae ese sistema,
    se usa la diferencia más común entre el mínimo del plan y el sistema (p. ej. 13.74% = sistema + 10)."""
    if sistema in plan["min"]:
        return plan["min"][sistema]
    difs = [round(m - s / 100, 4) for s, m in plan["min"].items()]
    return round(sistema / 100 + max(set(difs), key=difs.count), 4) if difs else None


def min_real_cliente(v, precio):
    """Enganche mínimo del cliente con el bono al enganche (el plan con bono de menor enganche), o None."""
    if not v["color"] or not precio:
        return None
    mins = [m for p in PLANES_BONO if (m := min_color(p, v["color"])) is not None]
    return (min(mins) if mins else v["color"] / 100) - v["bono"] / precio


def nombre_plan(plan, tipo):
    t = plan["tasas"][min(plan["tasas"])]
    cxa = f"{plan['cxa'] * 100:g}% CXA"
    if tipo == "tasa":
        return f"Tasa Baja Eng {plan['eng']:g}% + {cxa}"
    if tipo == "lanz":
        return f"Lanzamiento {t:.2f}% + {cxa}"
    return f"{'Especial' if plan['cxa'] else 'Estándar'} {t:.2f}% + {cxa}"


# ------------------------------------------------------------------------------------
# Ofertas aplicables al vehículo
#   modo "tasa"     → bono subsidiado en tasa, cliente paga precio de lista
#   modo "flex_eng"   → bono al enganche
#   modo "flex_precio" → bono al precio (descuento)
#   modo "sin_bono" → no lleva bono
# ------------------------------------------------------------------------------------
def ofertas_para(v):
    ops = []
    color = v["color"]
    for t in v["tb"]:
        ops.append(dict(nombre=nombre_plan(t, "tasa"), baremo=t["baremo"], cxa=t["cxa"], modo="tasa",
                        min=t["eng"] / 100, max=None, tasas=dict(t["tasas"])))
    if v["lanz"]:
        lz = v["lanz"]
        ops.append(dict(nombre=nombre_plan(lz, "lanz"), baremo=lz["baremo"], cxa=lz["cxa"], modo="sin_bono",
                        min=lz["eng"] / 100, max=None, tasas=dict(lz["tasas"])))
    if color:   # vehículo marcado en la tabla de bonos: cada plan con el bono al enganche y con el bono al precio
        for forma, modo in (("enganche", "flex_eng"), ("precio", "flex_precio")):
            for p in PLANES_BONO:
                mn = min_color(p, color)
                if mn is None:
                    continue
                ops.append(dict(nombre=f"{nombre_plan(p, 'std')} (bono al {forma})", baremo=p["baremo"], cxa=p["cxa"],
                                modo=modo, min=mn, max=None, tasas=dict(p["tasas"])))
    else:       # toda la gama sin marca
        for p in PLANES_SIN_BONO:
            nombre = nombre_plan(p, "std")
            if p["max"]:
                nombre += f" (enganche {p['min']:.0%} a <{p['max']:.0%})"
            ops.append(dict(nombre=nombre, baremo=p["baremo"], cxa=p["cxa"], modo="sin_bono", min=p["min"],
                            max=p["max"], tasas=dict(p["tasas"])))
    vistos = set()
    for o in ops:                 # nombres únicos (el análisis los usa como llave)
        if o["nombre"] in vistos:
            o["nombre"] += f" · {o['baremo']}"
        vistos.add(o["nombre"])
    return ops


aplicar(oferta_base())


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
    if op["modo"] == "flex_eng":
        candidatos = [("al enganche", precio + gap, bono)]
    elif op["modo"] == "flex_precio":
        candidatos = [("al precio", precio - bono + gap, 0.0)]
    else:
        candidatos = [("a tasa" if op["modo"] == "tasa" else "sin bono", precio + gap, 0.0)]
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
            motivo = f"Enganche {pct:.1%} mayor al máximo {ENGANCHE_MAX:.0%}"
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
                 # precio del plan: con el bono al precio, el precio de lista menos el bono
                 precio_lista=precio, bono_precio=bono if forma == "al precio" else 0.0,
                 precio_plan=precio - (bono if forma == "al precio" else 0.0),
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
    if op["modo"] == "flex_eng":
        bono_eng = bono
        cli_pct = op["min"] - bono / base
        forma = "al enganche"
    elif op["modo"] == "flex_precio":
        base = precio - bono + gap
        bono_eng = 0.0
        cli_pct = op["min"]
        forma = "al precio"
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
                bono=forma, precio_plan=precio - (bono if forma == "al precio" else 0.0),
                bono_precio=bono if forma == "al precio" else 0.0,
                desembolso_min=math.ceil(round(desembolso_min, 2)),
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
    tasa1 = lambda p: f"{p['tasas'][min(p['tasas'])]:.2f}%"
    gama = ", ".join(f"{tasa1(p)} " + (f"de {p['min']:.0%} a menos de {p['max']:.0%}" if p["max"]
                                       else f"desde {p['min']:.0%}") for p in PLANES_SIN_BONO)
    if v["color"]:
        pct_b = bono / precio
        real = min_real_cliente(v, precio)
        mins = ", ".join(f"{tasa1(p)} desde {min_color(p, v['color']):.0%}" for p in PLANES_BONO
                         if min_color(p, v["color"]) is not None)
        txt = (f"Marcado en {color_de(v['color'])} en la tabla de bonos (enganche sistema {v['color']}%). Bono MG de "
               f"{money0(bono)} ({pct_b:.1%} del precio de lista {money0(precio)}), pagado 100% por MG Motors "
               f"México. El bono se usa de una sola forma: a la tasa (planes de Tasa Baja: el cliente paga precio de "
               f"lista y aporta todo el enganche), al enganche o al precio (planes Estándar y Especial; se comparan como "
               f"opciones separadas). Enganche mínimo de los planes con bono: {mins}. Con el bono al enganche ese "
               f"mínimo incluye el bono: el cliente aporta desde {real:.2%} ({money0(real * precio)}). Con el bono al "
               f"precio el auto queda en {money0(precio - bono)} y el cliente pone el enganche completo sobre ese "
               f"precio.")
    elif v["lanz"]:
        lz = v["lanz"]
        txt = (f"Modelo de lanzamiento: tasa {tasa1(lz)} con {lz['cxa'] * 100:g}% de comisión desde {lz['eng']:g}% de "
               f"enganche ({min(lz['tasas'])} a {max(lz['tasas'])} meses). No tiene bono; también aplican los planes de "
               f"toda la gama ({gama}).")
    else:
        txt = f"Sin bono en la tabla de bonos: aplican los planes de toda la gama ({gama})."
    return txt + (f" Enganche máximo {ENGANCHE_MAX:.0%}. Enganche menor a 20%: +4% a la tasa. "
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
                rangos=rangos,
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


def texto_precio(ev):
    """Precio del plan: con el bono al precio muestra el descuento («$490,000 − $90,500 = $399,500»)."""
    if ev.get("bono_precio"):
        return f"{money0(ev['precio_lista'])} − bono {money0(ev['bono_precio'])} = {money0(ev['precio_plan'])}"
    return money0(ev["precio_plan"])


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
    """PDF del análisis (bytes): resumen y mejor opción, comparativo de planes, mensualidades por plazo y requisitos
    de la oferta para el auto."""
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                    KeepTogether, CondPageBreak)

    ROJO = colors.HexColor("#C8102E"); NEGRO = colors.HexColor("#18181B"); GRIS = colors.HexColor("#F4F4F5")
    GRIS2 = colors.HexColor("#E4E4E7"); TXT2 = colors.HexColor("#52525B"); TXT3 = colors.HexColor("#71717A")
    VERDE = colors.HexColor("#E8F5EC"); VERDE_T = colors.HexColor("#15803D"); BLANCO = colors.white
    W, H = landscape(letter)
    M = 34
    ancho = W - 2 * M
    plazo, seguro = res["plazo"], res["seguro"]
    ranking = res["ranking"]

    def st(name, size=8.5, color=NEGRO, bold=False, align=0, leading=None):
        return ParagraphStyle(name, fontName="Helvetica-Bold" if bold else "Helvetica", fontSize=size,
                              textColor=color, alignment=align, leading=leading or size * 1.25)
    s_h1, s_sub = st("h1", 19, NEGRO, True, leading=22), st("sub", 9, TXT2)
    s_h2, s_h2d = st("h2", 12, NEGRO, True, leading=15), st("h2d", 8, TXT3)
    s_p, s_small = st("p", 8.5, TXT2, leading=11.5), st("sm", 7, TXT3, leading=9)
    s_c, s_cb = st("c", 8, leading=10), st("cb", 8, NEGRO, True, leading=10)
    s_cc, s_ccb = st("cc", 8, align=TA_CENTER, leading=10), st("ccb", 8, NEGRO, True, TA_CENTER, 10)
    s_cr, s_crb = st("cr", 8, align=TA_RIGHT, leading=10), st("crb", 8, NEGRO, True, TA_RIGHT, 10)
    s_head = st("hd", 7.2, BLANCO, True, TA_CENTER, 9)
    s_lbl, s_val, s_det = st("lbl", 7, TXT3, True, leading=9), st("val", 15, NEGRO, True, leading=18), \
        st("det", 7, TXT2, leading=9)
    P = lambda t, s=s_c: Paragraph(str(t), s)
    gris = lambda t: f"<font size=6.6 color='#71717A'>{t}</font>"

    def encabezado(c, doc):
        c.saveState()
        c.setFillColor(NEGRO); c.rect(0, H - 30, W, 30, fill=1, stroke=0)
        c.setFillColor(ROJO); c.rect(0, H - 30, 6, 30, fill=1, stroke=0)
        c.setFillColor(BLANCO); c.setFont("Helvetica-Bold", 10.5)
        c.drawString(M, H - 19.5, "MG FINANCIAL SERVICES")
        c.setFont("Helvetica", 9); c.setFillColor(colors.HexColor("#A1A1AA"))
        c.drawString(M + c.stringWidth("MG FINANCIAL SERVICES", "Helvetica-Bold", 10.5) + 12, H - 19.5,
                     "Análisis de la mejor oferta")
        c.drawRightString(W - M, H - 19.5, f"Oferta {OFERTA_MES.lower()} · {BOLETIN} · vigente {VIGENCIA}")
        c.setStrokeColor(GRIS2); c.setLineWidth(0.6); c.line(M, 26, W - M, 26)
        c.setFillColor(TXT3); c.setFont("Helvetica", 7)
        c.drawString(M, 15, "Cálculo con el método del cotizador de Autoexpress Inbursa. Cifras de referencia: verifica "
                            "la cotización final en el cotizador oficial.")
        c.drawRightString(W - M, 15, f"Página {doc.page}")
        c.restoreState()

    def titulo(texto, detalle=""):
        t = Table([[P(texto, s_h2), P(detalle, st("h2r", 8, TXT3, align=TA_RIGHT))]],
                  colWidths=[ancho * 0.55, ancho * 0.45])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("LINEBELOW", (0, 0), (-1, 0), 1.2, NEGRO),
                               ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        return [t, Spacer(1, 6)]

    def tabla(filas, cw, estilo_extra=(), repetir=1, pad=4.5):
        t = Table(filas, colWidths=[ancho * x for x in cw], repeatRows=repetir)
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), NEGRO), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("LINEBELOW", (0, 1), (-1, -1), 0.4, GRIS2), ("TOPPADDING", (0, 0), (-1, -1), pad),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), pad), ("LEFTPADDING", (0, 0), (-1, -1), 5),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 5)] + list(estilo_extra)))
        return t

    archivo = io.BytesIO()
    doc = BaseDocTemplate(archivo, pagesize=landscape(letter), leftMargin=M, rightMargin=M, topMargin=44,
                          bottomMargin=34, title=f"Mejor oferta {res['vehiculo']}", author="MG Colima")
    doc.addPageTemplates([PageTemplate(id="p", onPage=encabezado, frames=[Frame(M, 32, ancho, H - 76, id="f")])])

    # ---------------------------------------------------------------- encabezado del análisis
    story = [P(res["vehiculo"], s_h1)]
    linea = [f"Generado el {datetime.now():%d/%m/%Y}"]
    if cliente.strip():
        linea.insert(0, f"Cliente: <b>{cliente.strip()}</b>")
    story += [P(" · ".join(linea), s_sub), Spacer(1, 8)]
    seg_txt = (f"{money(seguro)} " + ("financiado" if res.get("seguro1_fin") else "de contado")) if seguro else \
        "por definir"
    datos = [("PRECIO DE LISTA", money0(res["precio"])), ("BONO MG", money0(res["bono"]) if res["bono"] else "Sin bono"),
             ("SEGURO AÑO 1", seg_txt), ("PLAZO", f"{plazo} meses")]
    if res["gap"]:
        datos.append(("GAP", f"{money0(res['gap'])} {res['gap_modo'].lower()}"))
    chips = Table([[P(f"{a}<br/><font size=10 color='#18181B'><b>{b}</b></font>", st("chip", 6.8, TXT3, leading=12))
                    for a, b in datos]], colWidths=[ancho / len(datos)] * len(datos))
    chips.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), GRIS), ("LINEAFTER", (0, 0), (-2, -1), 2, BLANCO),
                               ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                               ("LEFTPADDING", (0, 0), (-1, -1), 10)]))
    story += [chips, Spacer(1, 12)]

    # ---------------------------------------------------------------- mejor opción
    if ranking:
        _, op, ev = ranking[0]
        story += titulo("Mejor opción", f"{op['nombre']} · baremo {op['baremo']}")
        mens2 = (ev["mens2"] if res.get("resto_fin") and ev["mens2"] and abs(ev["mens2"] - ev["mens"]) > 0.005
                 else None)
        izq = [P("MENSUALIDAD", st("ml", 7.5, colors.HexColor("#FECACA"), True)),
               P(money(ev["mens"]), st("mv", 26, BLANCO, True, leading=30)),
               P(("meses 1-12 · " + f"desde el mes 13: {money(mens2)}") if mens2 else f"fija los {plazo} meses",
                 st("md", 7.5, colors.HexColor("#FEE2E2"))),
               Spacer(1, 6),
               P(f"Tasa {ev['tasa']:.2f}% ({ev['tasa_iva']:.2f}% con IVA) · comisión {op['cxa']:.0%}",
                 st("mt", 8, BLANCO))]
        bono_txt = {"al enganche": f"Bono {money0(res['bono'])} al enganche",
                    "al precio": f"Bono {money0(res['bono'])} al precio", "a tasa": "Bono aplicado a la tasa"}
        celdas = [("PAGO INICIAL", money(ev["pago_inicial"]), desglose(ev)),
                  ("DESEMBOLSO DEL CLIENTE", money(ev["desembolso"]), desglose_desembolso(ev)),
                  ("PRECIO DEL PLAN", money0(ev["precio_plan"]),
                   texto_precio(ev) if ev["bono_precio"] else bono_txt.get(ev["forma"], "Sin bono")),
                  ("ENGANCHE", f"{money0(ev['eng_total'])}  ({ev['pct']:.1%})",
                   (f"cliente {money0(ev['eng_cliente'])} + bono {money0(ev['bono_eng'])}" if ev["bono_eng"] else
                    f"sobre {money0(ev['base'])}")),
                  ("MONTO FINANCIADO", money0(ev["financiado"]),
                   f"monto total a financiar {money0(ev['monto_total'])}" if ev["monto_total"] - ev["financiado"] > 1
                   else "sin seguros financiados"),
                  ("TOTAL DE MENSUALIDADES", money(ev["total"]), f"{plazo} pagos")]
        bloques = [[P(a, s_lbl), P(b, s_val), P(c, s_det)] for a, b, c in celdas]
        der = Table([bloques[0:3], bloques[3:6]], colWidths=[ancho * 0.66 / 3] * 3)
        der.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, 0), 0.5, GRIS2),
                                 ("LINEAFTER", (0, 0), (-2, -1), 0.5, GRIS2), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                 ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        tarjeta = Table([[izq, der]], colWidths=[ancho * 0.34, ancho * 0.66])
        tarjeta.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), ROJO), ("BOX", (0, 0), (-1, -1), 0.6, GRIS2),
                                     ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (0, 0), 16),
                                     ("TOPPADDING", (0, 0), (0, 0), 12), ("BOTTOMPADDING", (0, 0), (0, 0), 12),
                                     ("LEFTPADDING", (1, 0), (1, 0), 0), ("RIGHTPADDING", (1, 0), (1, 0), 0),
                                     ("TOPPADDING", (1, 0), (1, 0), 0), ("BOTTOMPADDING", (1, 0), (1, 0), 0)]))
        story += [KeepTogether([tarjeta]), Spacer(1, 5)]
        menor = min(ranking, key=lambda x: x[2]["mens"])
        if menor[1] is not op:
            story.append(P(f"La mensualidad más baja es la de {menor[1]['nombre']} ({money(menor[2]['mens'])}), pero "
                           f"cuesta {money(menor[0] - ranking[0][0])} más en total.", s_small))
        if not seguro:
            story.append(P("Sin seguro capturado: todo el desembolso se toma como enganche.", s_small))
        story.append(Spacer(1, 12))
    else:
        story += [P(f"Ninguna oferta es válida a {plazo} meses con este desembolso.", st("nv", 12, ROJO, True)),
                  Spacer(1, 10)]

    # ---------------------------------------------------------------- comparativo
    con13 = res.get("resto_fin") and any(e["mens2"] and abs(e["mens2"] - e["mens"]) > 0.005 for _, _, e in ranking)
    bloque = titulo(f"Comparativo de planes a {plazo} meses",
                    "mismo desembolso del cliente en todos · ordenados por total de mensualidades")
    cab = ["#", "Plan", "Precio del plan", "Enganche", "Pago inicial", "Desembolso", "Tasa", "Mensualidad"] + \
        (["Desde mes 13"] if con13 else []) + ["Total mensualidades"]
    filas = [[P(h, s_head) for h in cab]]
    for i, (tot, o, e) in enumerate(ranking, 1):
        b = i == 1
        precio_c = (f"{money0(e['precio_plan'])}<br/>{gris('lista − bono ' + money0(e['bono_precio']))}"
                    if e["bono_precio"] else money0(e["precio_plan"]))
        eng_c = f"{money0(e['eng_total'])} · {e['pct']:.1%}" + (
            f"<br/>{gris('cliente ' + money0(e['eng_cliente']) + ' + bono')}" if e["bono_eng"] else "")
        fila = [P(i, s_ccb if b else s_cc),
                P(f"{o['nombre']}<br/>{gris('baremo ' + o['baremo'] + ' · bono ' + e['forma'])}", s_cb if b else s_c),
                P(precio_c, s_cr), P(eng_c, s_cr), P(money0(e["pago_inicial"]), s_cr), P(money0(e["desembolso"]), s_cr),
                P(f"{e['tasa']:.2f}%", s_cc), P(money(e["mens"]), s_crb if b else s_cr)]
        if con13:
            fila.append(P(money(e["mens2"]), s_cr))
        fila.append(P(money(tot), s_cr))
        filas.append(fila)
    cw = ([0.03, 0.25, 0.1, 0.12, 0.085, 0.085, 0.06, 0.085, 0.085, 0.1] if con13 else
          [0.03, 0.28, 0.115, 0.13, 0.09, 0.09, 0.06, 0.1, 0.105])
    s = sum(cw); cw = [x / s for x in cw]
    extra = [("BACKGROUND", (0, 1), (-1, 1), VERDE), ("LINEBEFORE", (0, 1), (0, 1), 3, VERDE_T)] if ranking else []
    if ranking:
        bloque.append(tabla(filas, cw, extra))
        story += bloque
    malas = [(o, res["evals"][o["nombre"]]) for o in res["ops"]
             if not (res["evals"][o["nombre"]] and res["evals"][o["nombre"]]["valida"])]
    if malas:
        items = [P(f"<b>{o['nombre']}</b> — {e['motivo'] if e else 'no maneja este plazo'}", s_small)
                 for o, e in malas]
        mitad = (len(items) + 1) // 2
        cols = [items[:mitad], items[mitad:] or [P("", s_small)]]
        tm = Table([[P("NO APLICAN CON ESTE DESEMBOLSO", st("na", 7, TXT3, True)), ""], [cols[0], cols[1]]],
                   colWidths=[ancho / 2] * 2)
        tm.setStyle(TableStyle([("SPAN", (0, 0), (1, 0)), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("BACKGROUND", (0, 0), (-1, -1), GRIS), ("LEFTPADDING", (0, 0), (-1, -1), 8),
                                ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [Spacer(1, 6), tm]

    story += [Spacer(1, 8),
              P("<b>Cómo leerlo.</b> Pago inicial = enganche + comisión por apertura + seguro de contado del año 1 "
                "(como en la cotización). Desembolso = lo que pone el cliente de su bolsa (pago inicial − bono al "
                "enganche). Con el bono al precio, el auto queda en precio de lista − bono y el enganche se calcula "
                "sobre ese precio. Mensualidad = pago fijo del capital + seguro de vida (y del seguro financiado, si "
                f"aplica). Enganche menor a 20%: +4% a la tasa; máximo {ENGANCHE_MAX:.0%}. No incluye Anualidades, "
                "University ni Seminuevos.", s_small)]

    # ---------------------------------------------------------------- mensualidades por plazo
    con_opcion = [o for o in res["ops"] if any(e and e["valida"] for e in res["matriz"][o["nombre"]].values())]
    if con_opcion:
        story += [CondPageBreak(220), Spacer(1, 14)]
    bloque = titulo("Mensualidad por plazo", "meses 1-12 con el mismo desembolso · en verde, la mejor de cada plazo")
    filas_x = [[P(h, s_head) for h in ["Plan", "Precio del plan"] + [f"{n} meses" for n in PLAZOS]]]
    est_x = []
    for r, o in enumerate(con_opcion, 1):
        e0 = next((x for x in res["matriz"][o["nombre"]].values() if x), None)
        precio_c = money0(e0["precio_plan"]) if e0 else "—"
        fila = [P(f"{o['nombre']}<br/>{gris('baremo ' + o['baremo'])}"), P(precio_c, s_cr)]
        for j, n in enumerate(PLAZOS):
            e = res["matriz"][o["nombre"]][n]
            if not e or not e["valida"]:
                fila.append(P("—", st("gx", 8, TXT3, align=TA_CENTER)))
                continue
            tasa_txt = gris(f"{e['tasa']:.2f}%")
            fila.append(P(f"<b>{money(e['mens'])}</b><br/>{tasa_txt}", s_cc))
            m = res["mejores"][n]
            if m and m[0]["nombre"] == o["nombre"]:
                est_x.append(("BACKGROUND", (2 + j, r), (2 + j, r), VERDE))
        filas_x.append(fila)
    bloque.append(tabla(filas_x, [0.28, 0.1] + [0.62 / 6] * 6, est_x))
    sin = len(res["ops"]) - len(con_opcion)
    if sin:
        bloque += [Spacer(1, 3), P(f"{sin} plan(es) sin opción en ningún plazo con este desembolso (ver requisitos).",
                                   s_small)]
    bloque.append(Spacer(1, 2))
    if con_opcion:
        story.append(KeepTogether(bloque))

    # ---------------------------------------------------------------- oferta del auto
    story += [Spacer(1, 14)]
    bloque = titulo("Requisitos de la oferta para este auto", f"mínimos a {plazo} meses con el seguro capturado")
    v = CATALOGO[res["vehiculo"]]
    if v["color"]:
        resumen = (f"Color <b>{color_de(v['color'])}</b> en la tabla de bonos (enganche sistema {v['color']}%) · bono MG "
                   f"<b>{money0(res['bono'])}</b> ({res['bono'] / res['precio']:.1%} del precio). El bono va a la tasa "
                   f"(Tasa Baja), al enganche (el cliente aporta desde {min_real_cliente(v, res['precio']):.2%}) "
                   f"o al precio (el auto queda en {money0(res['precio'] - res['bono'])}).")
    else:
        resumen = res["descripcion"]
    bloque += [P(resumen, s_p), Spacer(1, 6)]
    cab_o = ["Plan", "Precio del plan", "Tasas por plazo", "Com.", "Enganche mínimo (sistema)",
             "Enganche mínimo del cliente", "Desembolso mínimo", "Pago inicial mínimo"]
    filas_o = [[P(h, s_head) for h in cab_o]]
    for q in res["requisitos"]:
        sis = f"{q['min_sistema']:.0%}" + (f" a &lt;{q['min_max']:.0%}" if q["min_max"] else "")
        otro = "" if q["plazo_pago_min"] == plazo else "<br/>" + gris(f"a {q['plazo_pago_min']} m")
        precio_c = (f"{money0(q['precio_plan'])}<br/>{gris('lista − bono ' + money0(q['bono_precio']))}"
                    if q["bono_precio"] else money0(q["precio_plan"]))
        corto = q["oferta"].replace(" (bono al enganche)", "").replace(" (bono al precio)", "")
        filas_o.append([P(f"{corto}<br/>{gris('baremo ' + q['baremo'] + ' · bono ' + q['bono'])}"),
                        P(precio_c, s_cr), P(q["tasas"], st("tz", 7.3, TXT2, leading=9.2)),
                        P(f"{q['cxa']:.0%}", s_cc), P(sis, s_cc),
                        P(f"<b>{q['min_cliente']:.2%}</b> · {money0(q['min_cliente_monto'])}", s_cc),
                        P(money0(q["desembolso_min"]) + otro, s_cr), P(money0(q["pago_inicial_min"]) + otro, s_cr)])
    bloque.append(tabla(filas_o, [0.25, 0.1, 0.21, 0.045, 0.08, 0.12, 0.1, 0.095], pad=3.5))
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
        if veh == OTRO:
            continue
        precio = v["msrp"]
        d = dict(precio=precio or 0.0, gap=0.0, gap_contado=0.0, bono=v["bono"], pago=0.0, seguro1=0.0,
                 seguro_anual=0.0, seguro_anual_capturado=0.0, iva=iva)
        planes = []
        for op in ofertas_para(v):
            nmax = max(op["tasas"])
            fila = dict(oferta=op["nombre"], baremo=op["baremo"], cxa=op["cxa"], min_sistema=op["min"],
                        min_max=op["max"], plazo_max=nmax, tasas=op["tasas"],
                        bono=("a la tasa" if op["modo"] == "tasa" else "al enganche" if op["modo"] == "flex_eng"
                              else "al precio" if op["modo"] == "flex_precio"
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
                           min_real=min_real_cliente(v, precio)))
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
               + ", ".join(f"{c} {s}%" for s, c in sorted(COLORES.items())) + ".", s_p), Spacer(1, 8)]

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
        est = [("SPAN", (0, 0), (-1, 0)), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(FONDO.get(a["color"], "#F3F3F3"))),
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
    story.append(P("Enganche mínimo real del cliente: con bono al enganche = enganche mínimo del plan − % del bono "
                   "(exacto, como lo acepta el cotizador); en Tasa Baja el bono va a la tasa y el cliente pone todo el "
                   f"enganche. Enganche menor a 20%: +4% a la tasa; máximo {ENGANCHE_MAX:.0%}. Cálculo con el método "
                   "del cotizador de Autoexpress: verificar en el cotizador oficial.", s_small))
    doc.build(story)
    return archivo.getvalue()
