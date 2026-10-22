# -*- coding: utf-8 -*-
"""
Página «Mejor oferta MG»: eliges el auto y capturas el desembolso del cliente o el pago inicial; compara todas las
ofertas del boletín de MG Financial Services con el método del cotizador de Autoexpress (cálculo en oferta_mg.py).

Pago inicial (como en la cotización) = enganche + comisión por apertura + seguro contado año 1 + GAP contado; el
enganche incluye el bono cuando va al enganche. Desembolso del cliente = pago inicial − bono al enganche.

Orden de la página: datos → mejor opción (tarjetas) → una tabla con todos los planes (incluye hasta cuánto puede
valer la póliza y por qué no aplica un plan) → pestañas «Por plazo» y «Mínimos» → PDF.
"""
import importlib
import os
import re

import pandas as pd
import streamlit as st

import oferta_mg as om
from ui import hero, tarjeta

# Streamlit Cloud conserva los módulos importados entre despliegues: si oferta_mg.py cambió (boletín nuevo, ajustes),
# se recarga para no usar la versión anterior.
_mtime = os.path.getmtime(om.__file__)
if getattr(om, "_mtime", None) != _mtime:
    om = importlib.reload(om)
    om._mtime = _mtime

VERDE = "background-color: #E6F4EA; font-weight: 600"
GRIS = "color: #8A94A6"
D = lambda t: str(t).replace("$", "\\$")   # en markdown, «$» abre fórmulas
DOLAR = lambda t, **k: st.column_config.NumberColumn(t, format="dollar", **k)
TEXTO_L = lambda t: st.column_config.TextColumn(t, width="large")

hero("Mejor oferta MG", "Compara todas las ofertas del boletín con lo que trae el cliente.",
     f"Boletín {om.BOLETIN} · vigente {om.VIGENCIA}")

# ----------------------------------------------------------------------------- datos de la operación
autos = list(om.CATALOGO)
CAPTURAS = ("Desembolso", "Pago inicial")
st.session_state.setdefault("of_pago", 130000)
st.session_state.setdefault("of_pi", 0)
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    veh = c1.selectbox("Auto", autos, index=autos.index("MG5 2027 1.5L COM EXCITE AT"), key="of_veh")
    v = om.CATALOGO[veh]
    captura = c2.segmented_control("Capturo", CAPTURAS, default="Desembolso", key="of_captura",
                                   help="El otro campo se calcula y queda bloqueado.") or "Desembolso"
    # el campo que no se captura se calcula: pago inicial = desembolso + bono al enganche (en Tasa Baja son iguales)
    if captura == "Pago inicial":
        st.session_state["of_pago"] = max(st.session_state["of_pi"] - v["bono"], 0)
    else:
        st.session_state["of_pi"] = st.session_state["of_pago"] + v["bono"]
    pago = c3.number_input("Desembolso del cliente", min_value=0, step=5000, key="of_pago",
                           disabled=captura != "Desembolso",
                           help="Lo que pone de su bolsa: enganche propio + comisión + seguro año 1 + GAP contado.")
    pago_inicial = c4.number_input("Pago inicial", min_value=0, step=5000, key="of_pi",
                                   disabled=captura != "Pago inicial",
                                   help="Como en la cotización: desembolso + bono al enganche (en Tasa Baja son "
                                        "iguales).")
    c5, c6, c7, c8 = st.columns([3, 2, 2, 2])
    plazo = c5.segmented_control("Plazo", om.PLAZOS, default=60, key="of_plazo",
                                 format_func=lambda n: f"{n} m") or 60
    seguro1 = c6.number_input("Seguro año 1 (contado)", min_value=0.0, value=0.0, step=500.0, key="of_seg",
                              help="Déjalo en 0 si aún no lo tienes: la tabla dice hasta cuánto puede valer.")
    seguro_anual = c7.number_input("Seguro anual (años 2+)", min_value=0.0, value=0.0, step=500.0,
                                   key="of_seg_anual", help="Se financia desde el mes 13. En 0 = igual al año 1.")
    precio_manual = c8.number_input("Precio", min_value=0, value=0, step=1000, key="of_precio",
                                    help="0 = precio de lista. Obligatorio en Lanzamiento y «Otro».")
    if v["msrp"]:
        c1.caption(D(f"Lista {om.money0(v['msrp'])} · bono {om.money0(v['bono'])}"
                     + (f" · sistema {v['color']}% ({om.COLORES[v['color']]})" if v["color"] else "")))
    else:
        c1.caption("Sin precio en el boletín: captúralo en «Precio».")
    with st.expander("Más opciones"):
        e1, e2, e3 = st.columns([2, 3, 2])
        gap_modo = e1.segmented_control("GAP", om.GAP_MODOS, default="No", key="of_gap",
                                        disabled=not om.gap_disponible(),
                                        help="Contado: va en el pago inicial. Financiado: se suma al precio."
                                        + ("" if om.gap_disponible() else " Falta cargar TABLA_GAP.")) or "No"
        cliente = e2.text_input("Cliente (para el PDF)", key="of_cli")
        iva = e3.toggle("IVA sobre intereses", value=True, key="of_iva")

if om.requiere_precio(veh) and not precio_manual:
    st.markdown('<div class="vacio"><b>Captura el precio del auto</b><br>'
                'Este modelo no trae precio en el boletín.</div>', unsafe_allow_html=True)
    st.stop()
if (pago_inicial if captura == "Pago inicial" else pago) <= 0:
    st.markdown(f'<div class="vacio"><b>Captura el {captura.lower()}</b></div>', unsafe_allow_html=True)
    st.stop()


@st.cache_data(show_spinner="Comparando ofertas…")
def correr(*a):
    return om.analizar(*a)


@st.cache_data(show_spinner="Armando la tabla de mínimos…")
def pdf_minimos(boletin, iva):
    return om.pdf_minimos(iva)


@st.cache_data(show_spinner=False)
def pdf(a, cliente):
    return om.pdf_bytes(correr(*a), cliente)


args = (veh, float(pago), float(seguro1), float(seguro_anual), int(plazo), float(precio_manual), gap_modo, iva,
        float(pago_inicial) if captura == "Pago inicial" else 0.0)
res = correr(*args)
ranking = res["ranking"]
if gap_modo != "No" and not res["gap"]:
    st.warning("Este precio no tiene monto de GAP en la tabla: se calcula sin GAP.")

# ----------------------------------------------------------------------------- mejor opción
if ranking:
    _, op, ev = ranking[0]
    st.markdown(f"##### :material/emoji_events: Mejor opción: **{op['nombre']}**")
    k = st.columns(5)
    tarjeta(k[0], "receipt_long", "Pago inicial", om.money(ev["pago_inicial"]), om.desglose(ev))
    tarjeta(k[1], "account_balance_wallet", "Desembolso", om.money(ev["desembolso"]), om.desglose_desembolso(ev))
    tarjeta(k[2], "payments", "Mensualidad", om.money(ev["mens"]),
            "Meses 1-12" + (f" · 13+: {om.money(ev['mens2'])}" if ev["mens2"] else ""), "#1E7B34")
    tarjeta(k[3], "percent", "Tasa", f"{ev['tasa']:.2f}%", f"{ev['tasa_iva']:.2f}% con IVA · com. {op['cxa']:.0%}")
    tarjeta(k[4], "event", "Plazo", f"{plazo} meses", f"Financiado {om.money0(ev['financiado'])}")
    nota = f"Baremo {op['baremo']} · bono {ev['forma']} · total de mensualidades {om.money(ev['total'])}"
    menor = min(ranking, key=lambda x: x[2]["mens"])
    if menor[1] is not op:
        nota += (f" · menor mensualidad: {menor[1]['nombre']} ({om.money(menor[2]['mens'])}), "
                 f"{om.money(menor[0] - ranking[0][0])} más en total")
    st.caption(D(nota))
else:
    st.warning(f"Ninguna oferta es válida a {plazo} meses con este {captura.lower()}.")
if not seguro1:
    st.caption(":material/warning: Seguro en \\$0: todo va a enganche. La columna «Póliza año 1» dice hasta cuánto "
               "puede valer.")

# ----------------------------------------------------------------------------- todos los planes
st.markdown(f"##### :material/leaderboard: Planes a {plazo} meses")
orden = {o["nombre"]: i for i, (_, o, _) in enumerate(ranking, 1)}
filas = []
for o in sorted(res["ops"], key=lambda o: orden.get(o["nombre"], 99)):
    e = res["evals"][o["nombre"]]
    fila = {"#": str(orden.get(o["nombre"], "")), "Oferta": o["nombre"],
            "Póliza año 1": om.texto_rango(res["rangos"][o["nombre"]])}
    if not e:
        filas.append(fila | {"Nota": "No maneja este plazo"})
        continue
    fila |= {"Bono": e["forma"], "Pago inicial": e["pago_inicial"], "Desembolso": e["desembolso"],
             "Enganche": f"{e['pct']:.1%}"}
    if e["valida"]:
        fila |= {"Mens. 1-12": e["mens"], "Mens. 13+": e["mens2"], "Tasa": f"{e['tasa']:.2f}%",
                 "Total mensualidades": e["total"]}
    else:
        fila["Nota"] = e["motivo"]
    filas.append(fila)
cols = ["#", "Oferta", "Bono", "Pago inicial", "Desembolso", "Enganche", "Mens. 1-12", "Mens. 13+", "Tasa",
        "Total mensualidades", "Póliza año 1", "Nota"]
df = pd.DataFrame(filas).reindex(columns=cols)
if not seguro_anual and not seguro1:
    df = df.drop(columns="Mens. 13+")   # sin seguro capturado es igual a la de los meses 1-12
if df["Nota"].isna().all():
    df = df.drop(columns="Nota")
st.dataframe(df.style.apply(lambda r: [VERDE if r["#"] == "1" else GRIS if not r["#"] else ""] * len(r), axis=1),
             hide_index=True, width="stretch",
             column_config={"#": st.column_config.TextColumn("#", width="small"), "Oferta": TEXTO_L("Oferta"),
                            "Nota": TEXTO_L("Nota")}
             | {c: DOLAR(c) for c in ["Pago inicial", "Desembolso", "Mens. 1-12", "Mens. 13+",
                                      "Total mensualidades"]})
st.caption("Ordenados por total de mensualidades. «Póliza año 1»: rango del seguro de contado con el que el plan "
           "cumple; en gris, los que no aplican.")

# ----------------------------------------------------------------------------- detalle
t_plazo, t_min = st.tabs([":material/calendar_view_month: Por plazo", ":material/sell: Mínimos y oferta del auto"])

with t_plazo:
    mat, marca = [], []
    for o in res["ops"]:
        fila, fm = {"Oferta": o["nombre"]}, {}
        for n in om.PLAZOS:
            e = res["matriz"][o["nombre"]][n]
            fila[f"{n} m"] = f"{om.money(e['mens'])} ({e['tasa']:.2f}%)" if e and e["valida"] else "—"
            m = res["mejores"][n]
            fm[f"{n} m"] = bool(m and m[0]["nombre"] == o["nombre"])
        mat.append(fila)
        marca.append(fm)
    df_m, df_marca = pd.DataFrame(mat), pd.DataFrame(marca)
    st.dataframe(df_m.style.apply(lambda col: [VERDE if col.name in df_marca and df_marca.loc[i, col.name] else ""
                                               for i in col.index], axis=0),
                 hide_index=True, width="stretch", column_config={"Oferta": TEXTO_L("Oferta")})
    st.caption("Mensualidad meses 1-12 (tasa) con lo capturado. En verde, la mejor de cada plazo.")

with t_min:
    filas_min, valores = [], []
    for q in res["requisitos"]:
        fila = {"Oferta": q["oferta"],
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
    st.dataframe(df_min.style.apply(lambda col: [VERDE if col.name in df_val and pd.notna(df_val.loc[i, col.name])
                                                 and df_val.loc[i, col.name] == df_val[col.name].min() else ""
                                                 for i in col.index], axis=0),
                 hide_index=True, width="stretch",
                 column_config={"Oferta": TEXTO_L("Oferta"), "Desembolso mín.": DOLAR("Desembolso mín."),
                                "Pago inicial mín.": DOLAR("Pago inicial mín.")})
    st.caption(f"Con el enganche mínimo de cada plan (incluye seguro y GAP capturados; desembolso y pago inicial a "
               f"{plazo} m). Mensualidad meses 1-12 (tasa); en verde, la menor de cada plazo.")
    with st.expander("Oferta del boletín para este auto"):
        st.markdown(D(res["descripcion"]))
    st.download_button("PDF de mínimos de toda la oferta", pdf_minimos(om.BOLETIN, iva),
                       file_name=f"Minimos_oferta_MG_{om.BOLETIN}.pdf", mime="application/pdf",
                       icon=":material/table_view:", help="Todos los autos y planes del boletín.")

# ----------------------------------------------------------------------------- PDF
st.divider()
slug = re.sub(r"[^A-Za-z0-9]+", "_", veh).strip("_")
d1, d2 = st.columns([1, 3], vertical_alignment="center")
d1.download_button("PDF del análisis", pdf(args, cliente.strip()), file_name=f"Mejor_oferta_{slug}_{plazo}m.pdf",
                   mime="application/pdf", type="primary", width="stretch", icon=":material/picture_as_pdf:")
d2.caption("Método del cotizador de Autoexpress: verifica la cifra final en el cotizador oficial. No incluye "
           "Anualidades, University ni Seminuevos.")
