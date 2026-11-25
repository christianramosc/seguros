# -*- coding: utf-8 -*-
"""
Página «Mejor oferta MG»: eliges el auto y capturas lo que trae el cliente (desembolso o pago inicial), el seguro y el
GAP; compara todas las ofertas del boletín de MG Financial Services con el método del cotizador de Autoexpress
(CreditoClick; cálculo en oferta_mg.py, calibrado con cotizaciones reales).

Pago inicial = anticipo total del cotizador = enganche + comisión por apertura + seguro de contado año 1 + GAP de
contado; el enganche incluye el bono cuando va al enganche. Desembolso del cliente = pago inicial − bono al enganche.

Orden de la página:
  1. Datos de la operación: auto (precio de lista del boletín) · cliente (desembolso o pago inicial, plazo) ·
     seguro y GAP (montos del GAP de la tabla del cotizador). El IVA sobre intereses siempre aplica.
  2. Cotización: plan a cotizar (la mejor opción o cualquier otro que aplique) → tarjetas con mensualidad, pago
     inicial, desembolso y total → «Captura en el cotizador» con los valores exactos por sección del cotizador.
  3. Comparativo de todos los planes del boletín.
  4. Detalle: por plazo, mínimos por plan y oferta del auto.  5. Descargas (PDF del análisis y de mínimos).
"""
import datetime as dt
import re

import pandas as pd
import streamlit as st

import oferta_guardada
from ui import APAGADO, RESALTE, VERDE_T, esc, hero, insignias, nota, seccion, tarjeta

# oferta_mg al día (Streamlit Cloud conserva los módulos entre despliegues) y con la oferta comercial que se subió en
# la página «Oferta comercial» (o la incluida en la app si no se ha subido otra).
om = oferta_guardada.motor()
VERSION = f"{om._mtime}-{om.OFERTA_ID}"     # llave de los cachés: cambia con el código o con la oferta

IVA = True   # el IVA sobre intereses siempre va en las cotizaciones
SEGUROS = ("Contado", "Fraccionado", "Multianual")

D = lambda t: str(t).replace("$", "\\$")   # en markdown, «$» abre fórmulas
DOLAR = lambda t, **k: st.column_config.NumberColumn(t, format="dollar", **k)
TEXTO_L = lambda t: st.column_config.TextColumn(t, width="large")

hero("Mejor oferta MG", "Compara todas las ofertas del boletín con lo que trae el cliente.",
     f"Boletín {om.BOLETIN} · vigente {om.VIGENCIA}")
if om.VIGENCIA_FIN and dt.date.today() > om.VIGENCIA_FIN:
    st.warning(f"La oferta {om.BOLETIN} terminó el {om.VIGENCIA_FIN:%d/%m/%Y}. Sube el boletín nuevo en «Oferta "
               "comercial» para usar los bonos y tasas vigentes.", icon=":material/event_busy:")

# ----------------------------------------------------------------------------- 1. datos de la operación
autos = list(om.CATALOGO)
CAPTURAS = ("Desembolso", "Pago inicial")
st.session_state.setdefault("of_pago", 130000)
st.session_state.setdefault("of_pi", 0)
if st.session_state.get("of_veh") not in autos:      # el auto ya no está en la oferta nueva
    st.session_state.pop("of_veh", None)

with st.container(border=True):
    st.markdown("**Vehículo**")
    a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
    defecto = "MG5 2027 1.5L COM EXCITE AT"
    veh = a1.selectbox("Auto", autos, index=autos.index(defecto) if defecto in autos else 0, key="of_veh",
                       label_visibility="collapsed")
    v = om.CATALOGO[veh]
    # el precio es el de lista del boletín; solo se captura en los modelos que no lo traen (Lanzamiento, «Otro»)
    precio_manual = 0
    if not v["msrp"]:
        precio_manual = a2.number_input("Precio de lista", min_value=0, value=0, step=1000, key="of_precio",
                                        help="Este modelo no trae precio en el boletín.")
    precio_lista = float(precio_manual or v["msrp"] or 0)
    vc = om.vehiculo_cotizador(veh, precio_lista or None)
    insignias([f"Lista {om.money0(precio_lista)}" if precio_lista else "Captura el precio de lista",
               f"Bono {om.money0(v['bono'])}" if v["bono"] else "Sin bono",
               f"Sistema {v['color']}% · {om.color_de(v['color'])}" if v["color"] else "",
               f"Cotizador: {vc[0]} · {vc[1]} · {vc[2]}" if vc else ""])

    st.markdown("**Cliente**")
    b1, b2, b3, b4 = st.columns([1.3, 1, 1, 1.6], vertical_alignment="bottom")
    captura = b1.segmented_control("Capturo", CAPTURAS, default="Desembolso", key="of_captura",
                                   help="El otro campo se calcula y queda bloqueado.") or "Desembolso"
    # el campo que no se captura se calcula: pago inicial = desembolso + bono al enganche (en Tasa Baja son iguales)
    if captura == "Pago inicial":
        st.session_state["of_pago"] = max(st.session_state["of_pi"] - v["bono"], 0)
    else:
        st.session_state["of_pi"] = st.session_state["of_pago"] + v["bono"]
    pago = b2.number_input("Desembolso del cliente", min_value=0, step=5000, key="of_pago",
                           disabled=captura != "Desembolso",
                           help="Lo que pone de su bolsa: enganche propio + comisión + seguro y GAP de contado.")
    pago_inicial = b3.number_input("Pago inicial", min_value=0, step=5000, key="of_pi",
                                   disabled=captura != "Pago inicial",
                                   help="El «Anticipo total» del cotizador: desembolso + bono al enganche.")
    plazo = b4.segmented_control("Plazo", om.PLAZOS, default=60, key="of_plazo",
                                 format_func=lambda n: f"{n} m") or 60

    st.markdown("**Seguro y GAP**")
    c1, c2, c3, c4 = st.columns([1.5, 1, 1.3, 1.2], vertical_alignment="bottom")
    modo_seg = c1.segmented_control(
        "Seguro (Autoexpress)", SEGUROS, default="Contado", key="of_seg1_modo",
        help="Igual que en el cotizador. Contado: año 1 en el pago inicial y los demás años fraccionados. "
             "Fraccionado (Financiado · Fraccionado): la prima anual se paga en 12 meses cada año. Multianual "
             "(Financiado · Multianual): la prima de todos los años va al capital, en todo el plazo.") or "Contado"
    seguro1 = c2.number_input("Prima a 5 años" if modo_seg == "Multianual" else "Prima anual",
                              min_value=0.0, value=0.0, step=500.0, key="of_seg",
                              help="La prima de la aseguradora que elijas en el cotizador (Multianual: «calculada a "
                                   "N años»). En 0 si aún no la tienes: el comparativo dice hasta cuánto puede valer.")
    gap_modo = c3.segmented_control("GAP", om.GAP_MODOS, default="No", key="of_gap") or "No"
    gap_plan = c4.selectbox("Plan GAP", om.GAP_PLANES, index=om.GAP_PLANES.index(om.GAP_PLAN_DEFAULT),
                            key="of_gap_plan", disabled=gap_modo == "No")
    if gap_modo != "No":   # monto de la tabla del cotizador (rango del precio de lista × plan)
        monto = om.monto_gap(precio_lista, gap_plan)
        insignias([f"GAP {gap_plan} {gap_modo.lower()}: {om.money0(monto)}" if monto else
                   "Sin GAP para este precio (el cotizador lo da hasta $2,000,000)"])
seguro1_fin, seguro_multi = modo_seg == "Fraccionado", modo_seg == "Multianual"

if om.requiere_precio(veh) and not precio_manual:
    st.markdown('<div class="vacio"><b>Captura el precio de lista</b><br>'
                'Este modelo no trae precio en el boletín.</div>', unsafe_allow_html=True)
    st.stop()
if (pago_inicial if captura == "Pago inicial" else pago) <= 0:
    st.markdown(f'<div class="vacio"><b>Captura el {captura.lower()}</b></div>', unsafe_allow_html=True)
    st.stop()


# `version` (código de oferta_mg.py + oferta comercial en uso) entra a la llave del caché: si cambia el cálculo o se
# sube un boletín nuevo, no se reusan resultados de la versión anterior.
@st.cache_data(show_spinner="Comparando ofertas…")
def correr(version, *a):
    return om.analizar(*a)


@st.cache_data(show_spinner="Armando la tabla de mínimos…")
def pdf_minimos(version, boletin):
    return om.pdf_minimos(IVA)


@st.cache_data(show_spinner=False)
def pdf(version, a, cliente):
    return om.pdf_bytes(correr(version, *a), cliente)


args = (veh, float(pago), float(seguro1), 0.0, int(plazo), float(precio_manual), gap_modo, IVA,
        float(pago_inicial) if captura == "Pago inicial" else 0.0, seguro1_fin, True, 0.0, seguro_multi, gap_plan)
res = correr(VERSION, *args)
ranking = res["ranking"]


def bloque(titulo, filas, donde):
    """Caja con «campo: valor» de una sección del cotizador."""
    cuerpo = "".join(f'<div style="margin:2px 0 8px"><div class="kt" style="margin:0">{esc(c)}</div>'
                     f'<div style="font-weight:600">{esc(val)}</div></div>' for c, val in filas)
    donde.container(border=True).markdown(f'<div class="kt" style="color:#FAFAFA;font-size:.9rem">{esc(titulo)}'
                                          f'</div>{cuerpo}', unsafe_allow_html=True)


# ----------------------------------------------------------------------------- 2. cotización
if ranking:
    nombres = [o["nombre"] for _, o, _ in ranking]
    if st.session_state.get("of_plan") not in nombres:
        st.session_state.pop("of_plan", None)
    seccion("Cotización", f"{len(ranking)} plan(es) aplican a {plazo} meses · ★ = menor total de mensualidades")
    elegido = st.selectbox("Plan a cotizar", nombres, key="of_plan",
                           format_func=lambda n: ("★ " if n == nombres[0] else "") + n)
    tot, op, ev = next(x for x in ranking if x[1]["nombre"] == elegido)
    insignias([f"Baremo {op['baremo']}", f"Tasa {ev['tasa']:.2f}% ({ev['tasa_iva']:.2f}% con IVA)",
               f"Comisión {op['cxa']:.0%}", f"Bono {ev['forma']}",
               f"Precio del plan {om.texto_precio(ev)}" if ev["bono_precio"] else ""],
              ok=(f"Baremo {op['baremo']}",))
    k = st.columns(4)
    tarjeta(k[0], "", "Mensualidad", om.money(ev["mens"]), "meses 1-12, con seguro de vida", VERDE_T)
    tarjeta(k[1], "", "Pago inicial", om.money(ev["pago_inicial"]), om.desglose(ev))
    tarjeta(k[2], "", "Desembolso del cliente", om.money(ev["desembolso"]), om.desglose_desembolso(ev))
    tarjeta(k[3], "", "Total de mensualidades", om.money(tot), f"{plazo} pagos")
    notas = []
    if elegido != nombres[0]:
        notas.append(f"La de menor total es {nombres[0]}: {om.money(ranking[0][0])} "
                     f"({om.money(tot - ranking[0][0])} menos).")
    menor = min(ranking, key=lambda x: x[2]["mens"])
    if menor[1]["nombre"] != elegido:
        notas.append(f"Menor mensualidad: {menor[1]['nombre']} ({om.money(menor[2]['mens'])}).")
    if not seguro1:
        notas.append("Sin prima capturada: todo el desembolso va a enganche; el comparativo dice hasta cuánto puede "
                     "valer el seguro.")
    for t in notas:
        nota(t)

    # ------------------------------------------------------------------------- captura en el cotizador
    seccion("Captura en el cotizador", "valores exactos para CreditoClick")
    grupos = {}
    for sec, campo, valor in om.captura_cotizador(res, op, ev):
        grupos.setdefault(sec, []).append((campo, valor))
    cols = st.columns(len(grupos))
    for (sec, filas_g), col in zip(grupos.items(), cols):
        bloque({"Resultado": "Resultado esperado"}.get(sec, sec), filas_g, col)
    nota("Captura en este orden: vehículo → GAP → enganche en $ → plan → plazo → seguro. Si cambias el enganche, el "
         "plan o el GAP, el cotizador borra el seguro: vuelve a elegirlo. Compara contra la mensualidad del resumen "
         "(arriba); la tabla de abajo del cotizador suma además el seguro de desempleo.")
else:
    st.warning(f"Ningún plan aplica a {plazo} meses con este {captura.lower()}. Revisa «Mínimos por plan».")

# ----------------------------------------------------------------------------- 3. comparativo
seccion("Comparativo de planes", f"a {plazo} meses · ordenados por total de mensualidades")
orden = {o["nombre"]: i for i, (_, o, _) in enumerate(ranking, 1)}
hay_precio = any(e and e["bono_precio"] for e in res["evals"].values())
filas = []
for o in sorted(res["ops"], key=lambda o: orden.get(o["nombre"], 99)):
    e = res["evals"][o["nombre"]]
    fila = {"#": str(orden.get(o["nombre"], "—")), "Plan": o["nombre"], "Baremo": o["baremo"],
            "Póliza año 1": om.texto_rango(res["rangos"][o["nombre"]])}
    if not e:
        filas.append(fila | {"Nota": "No maneja este plazo"})
        continue
    fila |= {"Precio": (f"{om.money0(e['precio_plan'])} (−{om.money0(e['bono_precio'])})" if e["bono_precio"]
                        else om.money0(e["precio_plan"])),
             "Enganche": e["eng_total"], "Enganche %": f"{e['pct']:.2%}", "Pago inicial": e["pago_inicial"],
             "Desembolso": e["desembolso"]}
    if e["valida"]:
        fila |= {"Mensualidad": e["mens"], "Tasa": f"{e['tasa']:.2f}%", "Total": e["total"]}
    else:
        fila["Nota"] = e["motivo"]
    filas.append(fila)
cols = ["#", "Plan", "Baremo", "Mensualidad", "Tasa", "Enganche", "Enganche %", "Pago inicial", "Desembolso",
        "Total", "Precio", "Póliza año 1", "Nota"]
df = pd.DataFrame(filas).reindex(columns=cols)
if not hay_precio:
    df = df.drop(columns="Precio")
if df["Nota"].isna().all():
    df = df.drop(columns="Nota")
for c in ["Mensualidad", "Pago inicial", "Desembolso", "Enganche", "Total"]:
    df[c] = df[c].map(lambda x: om.money(x) if pd.notna(x) else None)
df = df.fillna("—")
sel = st.session_state.get("of_plan") or (ranking[0][1]["nombre"] if ranking else None)
st.dataframe(df.style.apply(lambda r: [RESALTE if r["Plan"] == sel else APAGADO if r["#"] == "—" else ""] * len(r),
                            axis=1),
             hide_index=True, width="stretch",
             column_config={"#": st.column_config.TextColumn("#", width="small"), "Plan": TEXTO_L("Plan"),
                            "Enganche": st.column_config.TextColumn("Enganche", help="Lo que se captura en el "
                                                                    "cotizador (incluye el bono al enganche)"),
                            "Precio": st.column_config.TextColumn("Precio", help="Con el bono al precio: lista − bono"),
                            "Nota": TEXTO_L("Nota")})
nota("En verde, el plan que estás cotizando; en gris, los que no aplican. «Póliza año 1»: rango de la prima con el "
     "que el plan cumple. Mensualidad de los meses 1-12 con seguro de vida.")

# ----------------------------------------------------------------------------- 4. detalle
seccion("Detalle")
t_plazo, t_min, t_oferta = st.tabs([":material/calendar_view_month: Por plazo", ":material/flag: Mínimos por plan",
                                    ":material/sell: Oferta del auto"])

with t_plazo:
    mat, marca = [], []
    for o in res["ops"]:
        fila, fm = {"Plan": o["nombre"]}, {}
        for n in om.PLAZOS:
            e = res["matriz"][o["nombre"]][n]
            fila[f"{n} m"] = f"{om.money(e['mens'])} ({e['tasa']:.2f}%)" if e and e["valida"] else "—"
            m = res["mejores"][n]
            fm[f"{n} m"] = bool(m and m[0]["nombre"] == o["nombre"])
        mat.append(fila)
        marca.append(fm)
    df_m, df_marca = pd.DataFrame(mat), pd.DataFrame(marca)
    st.dataframe(df_m.style.apply(lambda col: [RESALTE if col.name in df_marca and df_marca.loc[i, col.name]
                                               else "" for i in col.index], axis=0),
                 hide_index=True, width="stretch", column_config={"Plan": TEXTO_L("Plan")})
    nota("Mensualidad meses 1-12 (tasa) con lo capturado. En verde, la mejor de cada plazo.")

with t_min:
    filas_min, valores = [], []
    for q in res["requisitos"]:
        fila = {"Plan": q["oferta"], "Baremo": q["baremo"],
                "Precio": (f"{om.money0(q['precio_plan'])} (−{om.money0(q['bono_precio'])})" if q["bono_precio"]
                           else om.money0(q["precio_plan"])),
                "Eng. sistema": f"{q['min_sistema']:.0%}" + (f" a <{q['min_max']:.0%}" if q["min_max"] else ""),
                "Eng. cliente": f"{q['min_cliente']:.2%} · {om.money0(q['min_cliente_monto'])}",
                "Desembolso mín.": q["desembolso_min"], "Pago inicial mín.": q["pago_inicial_min"]}
        val = {}
        for n in om.PLAZOS:
            e = res["mens_min"][q["oferta"]][n]
            fila[f"{n} m"] = f"{om.money(e['mens'])} ({e['tasa']:.2f}%)" if e else "—"
            val[f"{n} m"] = e["mens"] if e else None
        filas_min.append(fila)
        valores.append(val)
    df_min, df_val = pd.DataFrame(filas_min), pd.DataFrame(valores)
    st.dataframe(df_min.style.apply(lambda col: [RESALTE if col.name in df_val and pd.notna(df_val.loc[i, col.name])
                                                 and df_val.loc[i, col.name] == df_val[col.name].min() else ""
                                                 for i in col.index], axis=0),
                 hide_index=True, width="stretch",
                 column_config={"Plan": TEXTO_L("Plan"), "Desembolso mín.": DOLAR("Desembolso mín."),
                                "Pago inicial mín.": DOLAR("Pago inicial mín.")})
    nota(f"Con el enganche mínimo de cada plan (incluye el seguro capturado; desembolso y pago inicial a {plazo} m). "
         "Mensualidad meses 1-12 (tasa); en verde, la menor de cada plazo.")

with t_oferta:
    st.markdown(D(res["descripcion"]))

# ----------------------------------------------------------------------------- 5. descargas
seccion("Descargas")
slug = re.sub(r"[^A-Za-z0-9]+", "_", veh).strip("_")
d1, d2 = st.columns(2)
with d1.container(border=True):
    st.markdown("**PDF del análisis**")
    nota("Esta cotización (mejor opción), comparativo de planes, mensualidad por plazo y requisitos del auto.")
    cliente = st.text_input("Cliente", key="of_cli", placeholder="Nombre del cliente (opcional)",
                            label_visibility="collapsed")
    st.download_button("Descargar análisis", pdf(VERSION, args, cliente.strip()),
                       file_name=f"Mejor_oferta_{slug}_{plazo}m.pdf", mime="application/pdf", type="primary",
                       width="stretch", icon=":material/picture_as_pdf:")
with d2.container(border=True):
    st.markdown("**PDF de mínimos de toda la oferta**")
    nota("Todos los autos y planes del boletín: enganche, desembolso y pago inicial mínimos y mensualidades.")
    st.download_button("Descargar mínimos", pdf_minimos(VERSION, om.BOLETIN),
                       file_name=f"Minimos_oferta_MG_{om.BOLETIN}.pdf", mime="application/pdf", width="stretch",
                       icon=":material/table_view:")

nota("Método del cotizador de Autoexpress: verifica la cifra final en el cotizador oficial. No incluye Anualidades, "
     "University ni Seminuevos.")
