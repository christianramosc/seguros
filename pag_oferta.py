# -*- coding: utf-8 -*-
"""
Página «Mejor oferta MG»: eliges el auto y lo que trae el cliente (pago inicial) y compara todas las ofertas del
boletín de MG Financial Services con el método del cotizador de Autoexpress (cálculo en oferta_mg.py).

El enganche se ajusta solo: pago inicial − seguro del primer año − comisión por apertura (+ bono si va al enganche).
Arriba queda lo que paga el cliente con la mejor opción: pago inicial, tasa, mensualidad y plazo.
"""
import importlib
import os
import re

import altair as alt
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
PALETA = ["#C8102E", "#1F4E79", "#2E8B57", "#E07B00", "#6A3D9A", "#00838F", "#8D6E63"]
D = lambda t: str(t).replace("$", "\\$")   # en markdown, «$» abre fórmulas
DOLAR = lambda t, **k: st.column_config.NumberColumn(t, format="dollar", **k)

hero("Mejor oferta MG", "Compara todas las ofertas del boletín con lo que trae el cliente.",
     f"Boletín {om.BOLETIN} · vigente {om.VIGENCIA}")

# ----------------------------------------------------------------------------- datos de la operación
autos = list(om.CATALOGO)
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    veh = c1.selectbox("Auto", autos, index=autos.index("MG5 2027 1.5L COM EXCITE AT"), key="of_veh")
    v = om.CATALOGO[veh]
    pago = c2.number_input("Pago inicial del cliente", min_value=0, value=130000, step=5000, key="of_pago",
                           help="Todo lo que trae el cliente: enganche + seguro del primer año + comisión por "
                                "apertura. El enganche se calcula con lo que queda (+ el bono si va al enganche).")
    seguro1 = c3.number_input("Seguro primer año (contado)", min_value=0.0, value=0.0, step=500.0, key="of_seg",
                              help="Importe primer año de la cotización. Déjalo en 0 si aún no lo tienes: la "
                                   "pestaña «Seguro» dice hasta cuánto puede valer.")
    seguro_anual = c4.number_input("Seguro anual resto del plazo", min_value=0.0, value=0.0, step=500.0,
                                   key="of_seg_anual",
                                   help="Importe anual resto del plazo (se financia y sube la mensualidad desde el "
                                        "mes 13). Si lo dejas en 0 se toma igual al del primer año.")
    c5, c6, c7, c8 = st.columns([3, 2, 2, 2])
    plazo = c5.segmented_control("Plazo", om.PLAZOS, default=60, key="of_plazo",
                                 format_func=lambda n: f"{n} m") or 60
    precio_manual = c6.number_input("Precio (si es distinto al de lista)", min_value=0, value=0, step=1000,
                                    key="of_precio",
                                    help="Obligatorio en los modelos de Lanzamiento y «Otro». 0 = precio de lista.")
    c7.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
    incluir_gap = c7.toggle("Incluir GAP", value=False, key="of_gap", disabled=not om.gap_disponible(),
                            help="El GAP se suma al precio para el enganche y se financia. Cada rango de precio "
                                 "tiene su monto." + ("" if om.gap_disponible() else
                                 " Pendiente: falta cargar la tabla de montos de GAP (TABLA_GAP en oferta_mg.py)."))
    cliente = c8.text_input("Cliente (aparece en el PDF)", key="of_cli")
    iva = st.toggle("IVA sobre intereses", value=True, key="of_iva")
    if v["msrp"]:
        c1.caption(D(f"Precio de lista {om.money0(v['msrp'])} · bono MG {om.money0(v['bono'])}"
                     + (f" · color {om.COLORES[v['color']]} (sistema {v['color']}%): el cliente aporta desde "
                        f"{max(v['color'] / 100 - v['bono'] / v['msrp'], om.ENGANCHE_MIN_CLIENTE):.1%}"
                        if v["color"] else "")))
    else:
        c1.caption("Sin precio en el boletín: captúralo en «Precio».")

if om.requiere_precio(veh) and not precio_manual:
    st.markdown('<div class="vacio"><b>Captura el precio del auto</b><br>'
                'Este modelo no trae precio en el boletín.</div>', unsafe_allow_html=True)
    st.stop()
if pago <= 0:
    st.markdown('<div class="vacio"><b>Captura el pago inicial del cliente</b></div>', unsafe_allow_html=True)
    st.stop()


@st.cache_data(show_spinner="Comparando ofertas…")
def correr(*a):
    return om.analizar(*a)


@st.cache_data(show_spinner=False)
def pdf(a, cliente):
    return om.pdf_bytes(correr(*a), cliente)


args = (veh, float(pago), float(seguro1), float(seguro_anual), int(plazo), float(precio_manual), incluir_gap, iva)
res = correr(*args)
ranking = res["ranking"]
if incluir_gap and not res["gap"]:
    st.warning("Este precio no tiene monto de GAP en la tabla: se calcula sin GAP.")
elif res["gap"]:
    st.caption(D(f":material/shield_with_heart: Incluye GAP de {om.money(res['gap'])} (se suma al precio y se financia)."))

# ----------------------------------------------------------------------------- lo que paga el cliente
if ranking:
    _, op, ev = ranking[0]
    st.markdown(f"##### :material/emoji_events: Lo que paga el cliente · mejor opción: **{op['nombre']}**")
    k = st.columns(5)
    tarjeta(k[0], "account_balance_wallet", "Pago inicial", om.money(pago), om.desglose(ev))
    tarjeta(k[1], "savings", "Enganche del cliente", om.money0(ev["eng_cliente"]),
            f"{ev['pct_cliente']:.1%} del precio" + (f" · total {om.money0(ev['eng_total'])}" if ev["bono_eng"] else ""))
    tarjeta(k[2], "percent", "Tasa", f"{ev['tasa']:.2f}%",
            f"{ev['tasa_iva']:.2f}% con IVA · comisión {op['cxa']:.0%}")
    tarjeta(k[3], "payments", "Mensualidad", om.money(ev["mens"]),
            "Meses 1-12" + (f" · meses 13+: {om.money(ev['mens2'])}" if ev["mens2"] else ""), "#1E7B34")
    tarjeta(k[4], "event", "Plazo", f"{plazo} meses", f"Financiado {om.money0(ev['financiado'])}")
    notas = [f"Baremo **{op['baremo']}** · bono **{ev['forma']}**"
             + (f" **{om.money0(ev['bono_eng'])}** (enganche del cliente {om.money0(ev['eng_cliente'])} + bono)"
                if ev["bono_eng"] else "") + f" · financiado **{om.money(ev['financiado'])}** · "
             f"total de mensualidades "
             f"**{om.money(ev['total'])}**"]
    menor = min(ranking, key=lambda x: x[2]["mens"])
    if menor[1] is not op:
        notas.append(f"Menor mensualidad: {menor[1]['nombre']} con {om.money(menor[2]['mens'])}, pero cuesta "
                     f"{om.money(menor[0] - ranking[0][0])} más en total.")
    st.caption(D(" · ".join(notas)))
else:
    st.warning(f"Ninguna oferta es válida a {plazo} meses con este pago inicial.")
if not seguro1:
    st.caption(":material/warning: Seguro en \\$0: supone que todo el pago inicial es enganche. Captura el seguro o "
               "revisa la pestaña «Seguro».")
elif res["seguro_anual_estimado"]:
    st.caption(":material/info: Seguro anual del resto del plazo estimado igual al del primer año (meses 13+).")

# ----------------------------------------------------------------------------- detalle
t_rank, t_oferta, t_seg, t_plazo = st.tabs([":material/leaderboard: Comparativo", ":material/sell: Oferta del auto",
                                            ":material/shield: Seguro", ":material/calendar_view_month: Por plazo"])

with t_oferta:
    st.markdown(D(res["descripcion"]))
    req = pd.DataFrame([{
        "Oferta": q["oferta"], "Mínimo real cliente": f"{q['min_cliente']:.1%}",
        "Monto mínimo cliente": om.money0(q["min_cliente_monto"]),
        f"Pago inicial mínimo ({plazo} m)": om.money0(q["pago_min"])
        + ("" if q["plazo_pago_min"] == plazo else f" ({q['plazo_pago_min']} m)"),
        "Mínimo sistema": f"{q['min_sistema']:.0%}" + (f" a <{q['min_max']:.0%}" if q["min_max"] else ""),
        "Bono": q["bono"], "Comisión": f"{q['cxa']:.0%}", "Tasas por plazo": q["tasas"], "Baremo": q["baremo"]}
        for q in res["requisitos"]])
    st.dataframe(req, hide_index=True, width="stretch",
                 column_config={"Oferta": st.column_config.TextColumn("Oferta", width="medium"),
                                "Tasas por plazo": st.column_config.TextColumn("Tasas por plazo", width="large")})
    st.caption("Eng. mínimo real del cliente: lo que pone de su bolsa. Con bono al enganche = enganche sistema − % del "
               "bono (mínimo 10%); en Tasa Baja el bono va a la tasa y el cliente pone todo el enganche. El pago "
               "inicial mínimo suma el seguro del primer año y la comisión por apertura con lo capturado arriba.")

with t_rank:
    st.caption("Con el mismo pago inicial en todas: el enganche se ajusta a lo que queda después del seguro y la "
               "comisión (más el bono si va al enganche). Ordenadas por el total de mensualidades.")
    filas = []
    for i, (t, o, e) in enumerate(ranking, 1):
        filas.append({"#": str(i), "Oferta": o["nombre"], "Mens. 1-12": om.money(e["mens"]),
                      "Mens. 13+": om.money(e["mens2"]), "Tasa": f"{e['tasa']:.2f}%",
                      "Tasa c/IVA": f"{e['tasa_iva']:.2f}%", "Eng. cliente": om.money0(e["eng_cliente"]),
                      "% cliente": f"{e['pct_cliente']:.1%}", "Eng. total": om.money0(e["eng_total"]),
                      "% total": f"{e['pct']:.1%}", "Bono": e["forma"], "Comisión": om.money(e["cxa"]),
                      "Financiado": om.money0(e["financiado"]), "Total mensualidades": om.money(t),
                      "Baremo": o["baremo"], "Seguro permitido": om.texto_rango(res["rangos"][o["nombre"]])})
    if filas:
        st.dataframe(pd.DataFrame(filas).style.apply(lambda r: [VERDE if r["#"] == "1" else ""] * len(r), axis=1),
                     hide_index=True, width="stretch",
                     column_config={"#": st.column_config.TextColumn("#", width="small"),
                                    "Oferta": st.column_config.TextColumn("Oferta", width="large")})
    no_aplican = [(o, res["evals"][o["nombre"]]) for o in res["ops"]
                  if not (res["evals"][o["nombre"]] and res["evals"][o["nombre"]]["valida"])]
    if no_aplican:
        st.markdown("**No aplican con este pago inicial**")
        for o, e in no_aplican:
            st.caption(D(f":material/block: {o['nombre']} — {e['motivo'] if e else 'no maneja este plazo'} · "
                         f"seguro permitido: {om.texto_rango(res['rangos'][o['nombre']])}"))
    st.caption("Mensualidad = pago fijo del capital + seguro de vida (0.82% anual sobre el capital). Desde el mes 13 "
               "se suma el seguro de cada año, financiado a 12 meses (aproximado al centavo).")

with t_seg:
    st.caption(D(f"El seguro se paga de contado con el pago inicial ({om.money0(pago)}): entre más cuesta, menos "
                 f"enganche queda. Mejor oferta a {plazo} meses según el costo del seguro del primer año."))
    tr = res["tramos"]
    validos = [t for t in tr if t["oferta"]]
    if validos:
        tope = min(pago, max(t["hasta"] for t in validos) * 1.08 + 1)
        nombres = list(dict.fromkeys(t["oferta"] for t in validos))
        g = pd.DataFrame([{"desde": t["desde"], "hasta": min(t["hasta"] + 10, tope),
                           "Oferta": t["oferta"] or "Ninguna válida", "y": "Seguro",
                           "Rango": f"{om.money0(t['desde'])} a {om.money0(t['hasta'])}",
                           "Mensualidad": om.texto_mens(t)} for t in tr if t["desde"] <= tope])
        barra = alt.Chart(g).mark_bar(height=36).encode(
            x=alt.X("desde:Q", title="Seguro del primer año", axis=alt.Axis(format="$,.0f"),
                    scale=alt.Scale(domain=[0, tope])),
            x2="hasta:Q", y=alt.Y("y:N", title=None, axis=None),
            color=alt.Color("Oferta:N", title=None, legend=alt.Legend(orient="bottom", columns=2),
                            scale=alt.Scale(domain=nombres + ["Ninguna válida"],
                                            range=PALETA[:len(nombres)] + ["#D9D9D9"])),
            tooltip=["Oferta", "Rango", "Mensualidad"])
        if seguro1 and seguro1 <= tope:
            barra = barra + alt.Chart(pd.DataFrame({"x": [seguro1]})).mark_rule(
                color="#1A1A1A", strokeWidth=3).encode(x="x:Q")
        st.altair_chart(barra.properties(height=120), width="stretch")
    df_t = pd.DataFrame([{"Seguro primer año": f"{om.money0(t['desde'])} a {om.money0(t['hasta'])}",
                          "Mejor oferta": t["oferta"] or "Ninguna válida (enganche insuficiente)",
                          f"Mensualidad a {plazo} m (1-12)": om.texto_mens(t),
                          "_tuyo": bool(seguro1) and t["desde"] <= seguro1 <= t["hasta"]} for t in tr])
    if not df_t.empty:
        st.dataframe(df_t.style.apply(lambda r: [VERDE if r["_tuyo"] else ""] * len(r), axis=1),
                     hide_index=True, width="stretch", column_config={"_tuyo": None})
    st.caption("Si no capturas el seguro anual del resto del plazo, se toma igual al del primer año."
               + (" En verde, el tramo de tu seguro." if seguro1 else ""))

with t_plazo:
    st.caption("Mensualidad de los meses 1-12 (tasa) con el enganche que resulta del pago inicial en cada plazo. "
               "En verde, la mejor de cada plazo.")
    mat, marca = [], []
    for o in res["ops"]:
        fila, fm = {"Oferta": o["nombre"], "Eng. mín": f"{o['min']:.0%}"}, {}
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
                 hide_index=True, width="stretch",
                 column_config={"Oferta": st.column_config.TextColumn("Oferta", width="large")})
    st.markdown("**Mejor opción en cada plazo**")
    mp = []
    for n in om.PLAZOS:
        m = res["mejores"][n]
        if not m:
            mp.append({"Plazo": f"{n} meses", "Mejor oferta": "Ninguna válida"})
            continue
        o, e = m
        mp.append({"Plazo": f"{n} meses", "Mejor oferta": o["nombre"], "Pago inicial": pago,
                   "Tasa": f"{e['tasa']:.2f}%", "Eng. cliente": e["eng_cliente"],
                   "% cliente": f"{e['pct_cliente']:.1%}", "Eng. total": e["eng_total"], "Comisión": e["cxa"],
                   "Mens. 1-12": e["mens"], "Mens. 13+": e["mens2"], "Total mensualidades": e["total"]})
    st.dataframe(pd.DataFrame(mp), hide_index=True, width="stretch",
                 column_config={c: DOLAR(c) for c in ["Pago inicial", "Eng. cliente", "Eng. total", "Comisión", "Mens. 1-12",
                                                      "Mens. 13+", "Total mensualidades"]})

# ----------------------------------------------------------------------------- PDF
st.divider()
slug = re.sub(r"[^A-Za-z0-9]+", "_", veh).strip("_")
d1, _ = st.columns([1, 3])
d1.download_button("PDF del análisis", pdf(args, cliente.strip()), file_name=f"Mejor_oferta_{slug}_{plazo}m.pdf",
                   mime="application/pdf", type="primary", width="stretch", icon=":material/picture_as_pdf:")
st.caption("Cálculo con el método del cotizador de Autoexpress; verifica la cifra final en el cotizador oficial. "
           "No incluye Anualidades, University ni Seminuevos.")
