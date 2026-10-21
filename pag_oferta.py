# -*- coding: utf-8 -*-
"""
Página «Mejor oferta MG»: eliges el auto y el pago inicial del cliente y compara todas las ofertas del boletín de
MG Financial Services (cálculo en oferta_mg.py). Dice la mejor opción por plazo y hasta cuánto puede valer el seguro
de contado para que cada oferta siga siendo la ideal. Descarga el análisis en PDF.
"""
import re

import altair as alt
import pandas as pd
import streamlit as st

import oferta_mg as om
from ui import hero, tarjeta

VERDE = "background-color: #E6F4EA; font-weight: 600"
PALETA = ["#C8102E", "#1F4E79", "#2E8B57", "#E07B00", "#6A3D9A", "#00838F", "#8D6E63"]
D = lambda t: str(t).replace("$", "\\$")   # en markdown, «$» abre fórmulas
DOLAR = lambda t: st.column_config.NumberColumn(t, format="dollar")

hero("Mejor oferta MG", "Compara todas las ofertas del boletín para el auto y el pago inicial del cliente.",
     f"Boletín {om.BOLETIN} · vigente {om.VIGENCIA}")

# ----------------------------------------------------------------------------- datos de la operación
autos = list(om.CATALOGO)
with st.container(border=True):
    c1, c2, c3 = st.columns([3, 2, 2])
    veh = c1.selectbox("Auto", autos, index=autos.index("MG5 2027 1.5L COM EXCITE AT"), key="of_veh")
    v = om.CATALOGO[veh]
    pago = c2.number_input("Pago inicial del cliente", min_value=0, value=130000, step=5000, key="of_pago")
    seguro = c3.number_input("Seguro de contado", min_value=0, value=0, step=500, key="of_seg",
                             help="Déjalo en 0 si aún no lo tienes: la pestaña «Seguro» te dice hasta cuánto puede "
                                  "valer para que cada oferta sea la ideal.")
    c4, c5, c6 = st.columns([3, 2, 2])
    plazo = c4.segmented_control("Plazo", om.PLAZOS, default=60, key="of_plazo",
                                 format_func=lambda n: f"{n} m") or 60
    precio_manual = c5.number_input("Precio (si es distinto al de lista)", min_value=0, value=0, step=1000,
                                    key="of_precio",
                                    help="Obligatorio en los modelos de Lanzamiento y «Otro». 0 = precio de lista.")
    cliente = c6.text_input("Cliente (aparece en el PDF)", key="of_cli")
    t1, t2, _ = st.columns([2, 2, 3])
    seguro_en_pago = t1.toggle("El seguro sale del pago inicial", value=True, key="of_seg_pago")
    iva = t2.toggle("IVA sobre intereses", value=True, key="of_iva")
    if v["msrp"]:
        c1.caption(D(f"Precio de lista {om.money0(v['msrp'])} · bono MG {om.money0(v['bono'])}"))
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
def correr(veh, pago, seguro, seguro_en_pago, plazo, precio_manual, iva):
    return om.analizar(veh, pago, seguro, seguro_en_pago, plazo, precio_manual, iva)


@st.cache_data(show_spinner=False)
def pdf(veh, pago, seguro, seguro_en_pago, plazo, precio_manual, iva, cliente):
    return om.pdf_bytes(correr(veh, pago, seguro, seguro_en_pago, plazo, precio_manual, iva), cliente)


args = (veh, float(pago), float(seguro), seguro_en_pago, int(plazo), float(precio_manual), iva)
res = correr(*args)
precio, bono, efectivo, ranking = res["precio"], res["bono"], res["efectivo"], res["ranking"]

# ----------------------------------------------------------------------------- indicadores
k = st.columns(4)
tarjeta(k[0], "sell", "Precio", om.money0(precio), "Precio de lista" if not precio_manual else "Precio capturado")
tarjeta(k[1], "redeem", "Bono MG", om.money0(bono), "A tasa, al enganche o al precio (excluyente)")
tarjeta(k[2], "account_balance_wallet", "Enganche real", om.money0(efectivo),
        f"{efectivo / precio:.1%} del precio" + (" · sin seguro" if seguro and seguro_en_pago else ""))
if ranking:
    tarjeta(k[3], "payments", f"Mensualidad a {plazo} meses", om.money(ranking[0][3]["mens"]),
            ranking[0][1]["nombre"], "#1E7B34")
else:
    tarjeta(k[3], "block", f"A {plazo} meses", "Sin oferta", "Ninguna oferta es válida", "#9C0006")

# ----------------------------------------------------------------------------- recomendación
if ranking:
    _, op, ev, c = ranking[0]
    with st.container(border=True):
        st.markdown(f"#### :material/emoji_events: Mejor opción a {plazo} meses: {op['nombre']}")
        st.markdown(D(f"Baremo **{op['baremo']}** · bono **{ev['forma']}** · tasa **{c['tasa']:.2f}%** · "
                    f"financiado **{om.money(ev['financiado'])}** · CXA **{om.money(c['cxa'])}** · "
                    f"mensualidad **{om.money(c['mens'])}** · total CXA + pagos **{om.money(c['total'])}**"))
        menor = min(ranking, key=lambda x: x[3]["mens"])
        if menor[1] is not op:
            st.caption(D(f"Menor mensualidad: {menor[1]['nombre']} con {om.money(menor[3]['mens'])}, pero cuesta "
                       f"{om.money(menor[0] - ranking[0][0])} más en total."))
        ceros = [n for n, t in op["tasas"].items() if t == 0]
        if ceros:
            st.caption(D(f"Esta oferta tiene 0% hasta {max(ceros)} meses: "
                       f"{om.money(om.mensualidad(ev['financiado'], 0, max(ceros), iva))} al mes."))
        if not seguro and seguro_en_pago:
            st.caption(":material/warning: Seguro en \\$0: supone que todo el pago inicial es enganche. Revisa la "
                       "pestaña «Seguro».")
else:
    st.warning(f"Ninguna oferta es válida a {plazo} meses con este pago inicial.")

# ----------------------------------------------------------------------------- detalle
t_rank, t_seg, t_plazo = st.tabs([":material/leaderboard: Ranking", ":material/shield: Seguro",
                                  ":material/calendar_view_month: Por plazo"])

with t_rank:
    st.caption("Ordenadas por lo que paga el cliente después del pago inicial (CXA + mensualidades). Como el pago "
               "inicial es el mismo en todas, es la comparación justa aunque el monto financiado cambie según dónde "
               "se aplique el bono.")
    filas = []
    for i, (t, o, e, cc) in enumerate(ranking, 1):
        filas.append({"#": i, "Oferta": o["nombre"], "Baremo PF/PM": o["baremo"], "Bono": e["forma"],
                      "Tasa": f"{cc['tasa']:.2f}%", "Financiado": e["financiado"], "CXA": cc["cxa"],
                      "Mensualidad": cc["mens"], "Total CXA + pagos": t,
                      "Seguro permitido": om.texto_rango(res["rangos"][o["nombre"]], seguro_en_pago),
                      "Motivo": ""})
    for o in res["ops"]:
        e = res["evals"][o["nombre"]]
        if e["valida"] and plazo in o["tasas"]:
            continue
        motivo = ("No maneja este plazo" if plazo not in o["tasas"] else
                  f"No cumple enganche mínimo {o['min']:.0%}" + (f" (o excede {o['max']:.0%})" if o["max"] else ""))
        filas.append({"#": None, "Oferta": o["nombre"], "Baremo PF/PM": o["baremo"], "Bono": "", "Tasa": "",
                      "Financiado": None, "CXA": None, "Mensualidad": None, "Total CXA + pagos": None,
                      "Seguro permitido": om.texto_rango(res["rangos"][o["nombre"]], seguro_en_pago),
                      "Motivo": motivo})
    tabla = pd.DataFrame(filas)
    estilo = tabla.style.apply(lambda r: [VERDE if r["#"] == 1 else ""] * len(r), axis=1)
    st.dataframe(estilo, hide_index=True, width="stretch",
                 column_config={"#": st.column_config.NumberColumn("#", format="%d", width="small"),
                                "Financiado": DOLAR("Financiado"), "CXA": DOLAR("CXA"),
                                "Mensualidad": DOLAR("Mensualidad"), "Total CXA + pagos": DOLAR("Total CXA + pagos"),
                                "Oferta": st.column_config.TextColumn("Oferta", width="large")})

with t_seg:
    if not seguro_en_pago:
        st.info("El seguro se paga aparte del pago inicial, así que no cambia la mejor oferta.")
    else:
        st.caption(D(f"El seguro se paga de contado con el pago inicial ({om.money0(pago)}): entre más cuesta, menos "
                   f"enganche queda. Mejor oferta a {plazo} meses según el costo del seguro."))
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
                x=alt.X("desde:Q", title="Costo del seguro de contado", axis=alt.Axis(format="$,.0f"),
                        scale=alt.Scale(domain=[0, tope])),
                x2="hasta:Q", y=alt.Y("y:N", title=None, axis=None),
                color=alt.Color("Oferta:N", title=None, legend=alt.Legend(orient="bottom", columns=2),
                                scale=alt.Scale(domain=nombres + ["Ninguna válida"],
                                                range=PALETA[:len(nombres)] + ["#D9D9D9"])),
                tooltip=["Oferta", "Rango", "Mensualidad"])
            capas = barra
            if seguro and seguro <= tope:
                regla = alt.Chart(pd.DataFrame({"x": [seguro]})).mark_rule(color="#1A1A1A", strokeWidth=3).encode(
                    x="x:Q")
                capas = barra + regla
            st.altair_chart(capas.properties(height=120), width="stretch")
        df_t = pd.DataFrame([{"Seguro de contado": f"{om.money0(t['desde'])} a {om.money0(t['hasta'])}",
                              "Mejor oferta": t["oferta"] or "Ninguna válida (enganche insuficiente)",
                              f"Mensualidad a {plazo} m": om.texto_mens(t),
                              "_tuyo": bool(seguro) and t["desde"] <= seguro <= t["hasta"]} for t in tr])
        st.dataframe(df_t.style.apply(lambda r: [VERDE if r["_tuyo"] else ""] * len(r), axis=1),
                     hide_index=True, width="stretch", column_config={"_tuyo": None})
        st.caption("Dentro de cada tramo la mensualidad sube un poco: al pagar más seguro queda menos enganche y se "
                   "financia más." + (" En verde, el tramo de tu seguro." if seguro else ""))

with t_plazo:
    st.caption("Mensualidad (tasa) de cada oferta con el enganche real del cliente. En verde, la mejor de cada plazo.")
    mat, marca = [], []
    for o in res["ops"]:
        e = res["evals"][o["nombre"]]
        fila = {"Oferta": o["nombre"], "Eng. mín": f"{o['min']:.0%}", "Bono": e["forma"] if e["valida"] else "no aplica"}
        fm = {}
        for n in om.PLAZOS:
            cc = om.costo(o, e, n, iva) if e["valida"] else None
            fila[f"{n} m"] = "—" if cc is None else f"{om.money(cc['mens'])} ({cc['tasa']:.2f}%)"
            m = res["mejores"][n]
            fm[f"{n} m"] = bool(m and m[0]["nombre"] == o["nombre"])
        mat.append(fila)
        marca.append(fm)
    df_m = pd.DataFrame(mat)
    df_marca = pd.DataFrame(marca)

    def verde(col):
        return [VERDE if col.name in df_marca and df_marca.loc[i, col.name] else "" for i in col.index]

    st.dataframe(df_m.style.apply(verde, axis=0), hide_index=True, width="stretch",
                 column_config={"Oferta": st.column_config.TextColumn("Oferta", width="large")})
    st.markdown("**Mejor opción en cada plazo**")
    mp = []
    for n in om.PLAZOS:
        m = res["mejores"][n]
        if not m:
            mp.append({"Plazo": f"{n} meses", "Mejor oferta": "Ninguna válida"})
            continue
        o, e, cc = m
        mp.append({"Plazo": f"{n} meses", "Mejor oferta": o["nombre"], "Bono": e["forma"],
                   "Tasa": f"{cc['tasa']:.2f}%", "Financiado": e["financiado"], "Mensualidad": cc["mens"],
                   "CXA": cc["cxa"], "Intereses + IVA": cc["interes"], "Total CXA + pagos": cc["total"]})
    st.dataframe(pd.DataFrame(mp), hide_index=True, width="stretch",
                 column_config={c: DOLAR(c) for c in ["Financiado", "Mensualidad", "CXA", "Intereses + IVA",
                                                      "Total CXA + pagos"]})

# ----------------------------------------------------------------------------- PDF
st.divider()
slug = re.sub(r"[^A-Za-z0-9]+", "_", veh).strip("_")
d1, _ = st.columns([1, 3])
d1.download_button("PDF del análisis", pdf(*args, cliente.strip()), file_name=f"Mejor_oferta_{slug}_{plazo}m.pdf",
                   mime="application/pdf", type="primary", width="stretch", icon=":material/picture_as_pdf:")
st.caption("Mensualidades sin seguro, con IVA sobre intereses y pagos fijos; verifica la cifra final en el cotizador "
           "oficial. No incluye Anualidades, University ni Seminuevos.")
