# -*- coding: utf-8 -*-
"""
Página «Mejor oferta MG»: eliges el auto y lo que el cliente pone de su bolsa (desembolso) y compara todas las ofertas
del boletín de MG Financial Services con el método del cotizador de Autoexpress (cálculo en oferta_mg.py).

Pago inicial (como en la cotización) = enganche + comisión por apertura + seguro contado año 1 + GAP contado; el
enganche incluye el bono cuando va al enganche. Desembolso del cliente = pago inicial − bono al enganche.
Arriba queda la mejor opción: pago inicial, desembolso, tasa, mensualidad y plazo.
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
CAPTURAS = ("Desembolso", "Pago inicial")
st.session_state.setdefault("of_pago", 130000)
st.session_state.setdefault("of_pi", 0)
with st.container(border=True):
    c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
    veh = c1.selectbox("Auto", autos, index=autos.index("MG5 2027 1.5L COM EXCITE AT"), key="of_veh")
    v = om.CATALOGO[veh]
    captura = c2.segmented_control("Capturo", CAPTURAS, default="Desembolso", key="of_captura",
                                   help="Captura el desembolso del cliente o el pago inicial de la cotización: el "
                                        "otro se calcula y no se puede modificar.") or "Desembolso"
    # el campo que no se captura se calcula: pago inicial = desembolso + bono al enganche (en Tasa Baja el bono va a
    # la tasa y ambos son iguales)
    if captura == "Pago inicial":
        st.session_state["of_pago"] = max(st.session_state["of_pi"] - v["bono"], 0)
    else:
        st.session_state["of_pi"] = st.session_state["of_pago"] + v["bono"]
    pago = c3.number_input("Desembolso del cliente (lo que trae)", min_value=0, step=5000, key="of_pago",
                           disabled=captura != "Desembolso",
                           help="Lo que el cliente pone de su bolsa: cubre su enganche, la comisión por apertura, el "
                                "seguro del primer año y el GAP de contado. El bono MG no sale de aquí: si va al "
                                "enganche se suma y el pago inicial de la cotización = desembolso + bono.")
    pago_inicial = c4.number_input("Pago inicial (como en la cotización)", min_value=0, step=5000, key="of_pi",
                                   disabled=captura != "Pago inicial",
                                   help="Enganche (incluye el bono al enganche) + comisión + seguro año 1 + GAP "
                                        "contado. Desembolso del cliente = pago inicial − bono al enganche; en Tasa "
                                        "Baja el bono va a la tasa y el cliente desembolsa todo el pago inicial.")
    if v["bono"]:
        (c3 if captura == "Pago inicial" else c4).caption(
            D(f"{'− ' if captura == 'Pago inicial' else '+ '}bono {om.money0(v['bono'])} al enganche · en Tasa Baja "
              f"son iguales"))
    c5, c6, c7, c8 = st.columns([3, 2, 2, 2])
    plazo = c5.segmented_control("Plazo", om.PLAZOS, default=60, key="of_plazo",
                                 format_func=lambda n: f"{n} m") or 60
    seguro1 = c6.number_input("Seguro primer año (contado)", min_value=0.0, value=0.0, step=500.0, key="of_seg",
                              help="Importe primer año de la cotización. Déjalo en 0 si aún no lo tienes: abajo "
                                   "sale hasta cuánto puede valer la póliza en cada plan.")
    seguro_anual = c7.number_input("Seguro anual resto del plazo", min_value=0.0, value=0.0, step=500.0,
                                   key="of_seg_anual",
                                   help="Importe anual resto del plazo (se financia y sube la mensualidad desde el "
                                        "mes 13). Si lo dejas en 0 se toma igual al del primer año.")
    precio_manual = c8.number_input("Precio (si es distinto al de lista)", min_value=0, value=0, step=1000,
                                    key="of_precio",
                                    help="Obligatorio en los modelos de Lanzamiento y «Otro». 0 = precio de lista.")
    c9, c10, c11 = st.columns([3, 4, 2])
    gap_modo = c9.segmented_control("GAP", om.GAP_MODOS, default="No", key="of_gap",
                                    disabled=not om.gap_disponible(),
                                    help="Contado: va en el pago inicial. Financiado: se suma al precio y entra al "
                                         "enganche y al crédito. Cada rango de precio tiene su monto."
                                    + ("" if om.gap_disponible() else " Pendiente: falta cargar la tabla de montos "
                                       "de GAP (TABLA_GAP en oferta_mg.py).")) or "No"
    cliente = c10.text_input("Cliente (aparece en el PDF)", key="of_cli")
    iva = c11.toggle("IVA sobre intereses", value=True, key="of_iva")
    if v["msrp"]:
        c1.caption(D(f"Precio de lista {om.money0(v['msrp'])} · bono MG {om.money0(v['bono'])}"
                     + (f" · color {om.COLORES[v['color']]} (sistema {v['color']}%): el cliente aporta desde "
                        f"{v['color'] / 100 - v['bono'] / v['msrp']:.2%}"
                        if v["color"] else "")))
    else:
        c1.caption("Sin precio en el boletín: captúralo en «Precio».")

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
elif res["gap"]:
    st.caption(D(f":material/shield_with_heart: GAP de {om.money(res['gap'])} "
                 + ("de contado (va en el pago inicial)." if gap_modo == "Contado" else
                    "financiado (se suma al precio).")))

# ----------------------------------------------------------------------------- lo que paga el cliente
if ranking:
    _, op, ev = ranking[0]
    st.markdown(f"##### :material/emoji_events: Lo que paga el cliente · mejor opción: **{op['nombre']}**")
    k = st.columns(5)
    tarjeta(k[0], "receipt_long", "Pago inicial", om.money(ev["pago_inicial"]), om.desglose(ev))
    tarjeta(k[1], "account_balance_wallet", "Desembolso del cliente", om.money(ev["desembolso"]),
            om.desglose_desembolso(ev))
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
    st.warning(f"Ninguna oferta es válida a {plazo} meses con este {captura.lower()}.")
if not seguro1:
    st.caption(":material/warning: Seguro en \\$0: supone que todo el "
               + ("pago inicial" if res["pago_inicial"] else "desembolso") + " es enganche. Captura el seguro o "
               "revisa abajo hasta cuánto puede valer la póliza.")
elif res["seguro_anual_estimado"]:
    st.caption(":material/info: Seguro anual del resto del plazo estimado igual al del primer año (meses 13+).")

# ----------------------------------------------------------------------------- póliza que cabe
st.markdown(f"##### :material/shield: Hasta cuánto puede valer la póliza (seguro año 1) · {plazo} meses")
pol = []
for o in res["ops"]:
    e = res["evals"][o["nombre"]]
    if not e:
        continue
    rs = res["rangos"][o["nombre"]]
    pi = res["pago_inicial"] or pago + e["bono_eng"]
    pol.append({"Oferta": o["nombre"], "Bono": e["forma"], "Pago inicial": pi, "Desembolso": pi - e["bono_eng"],
                "Póliza año 1": om.texto_rango(rs),
                "Con tu seguro": ("✓ cumple" if e["valida"] else e["motivo"]) if seguro1 else "",
                "_ok": bool(rs)})
if pol:
    st.dataframe(pd.DataFrame(pol).style.apply(lambda r: [VERDE if r["_ok"] else ""] * len(r), axis=1),
                 hide_index=True, width="stretch",
                 column_config={"Oferta": st.column_config.TextColumn("Oferta", width="large"),
                                "Pago inicial": DOLAR("Pago inicial"), "Desembolso": DOLAR("Desembolso"),
                                "_ok": None} | ({} if seguro1 else {"Con tu seguro": None}))
    st.caption("Rango del seguro de contado del primer año con el que cada plan cumple sus condiciones (enganche "
               "mínimo y máximo) con lo capturado; «No alcanza»: ni con seguro en \\$0. El seguro sale del pago "
               "inicial: entre más cuesta, menos enganche queda.")

# ----------------------------------------------------------------------------- detalle
t_rank, t_oferta, t_seg, t_plazo = st.tabs([":material/leaderboard: Comparativo", ":material/sell: Oferta del auto",
                                            ":material/shield: Seguro", ":material/calendar_view_month: Por plazo"])

with t_oferta:
    st.markdown(D(res["descripcion"]))
    req = pd.DataFrame([{
        "Oferta": q["oferta"], "Mínimo real cliente": f"{q['min_cliente']:.2%}",
        "Monto mínimo cliente": om.money0(q["min_cliente_monto"]),
        f"Desembolso mínimo ({plazo} m)": om.money0(q["desembolso_min"])
        + ("" if q["plazo_pago_min"] == plazo else f" ({q['plazo_pago_min']} m)"),
        f"Pago inicial mínimo ({plazo} m)": om.money0(q["pago_inicial_min"])
        + ("" if q["plazo_pago_min"] == plazo else f" ({q['plazo_pago_min']} m)"),
        "Mínimo sistema": f"{q['min_sistema']:.0%}" + (f" a <{q['min_max']:.0%}" if q["min_max"] else ""),
        "Bono": q["bono"], "Comisión": f"{q['cxa']:.0%}", "Tasas por plazo": q["tasas"], "Baremo": q["baremo"]}
        for q in res["requisitos"]])
    st.dataframe(req, hide_index=True, width="stretch",
                 column_config={"Oferta": st.column_config.TextColumn("Oferta", width="medium"),
                                "Tasas por plazo": st.column_config.TextColumn("Tasas por plazo", width="large")})
    st.caption("Eng. mínimo real del cliente: lo que pone de su bolsa. Con bono al enganche = enganche sistema − % del "
               "bono, exacto (el boletín lo redondea, p. ej. 9.96% → 10%); en Tasa Baja el bono va a la tasa y el cliente pone todo el enganche. Desembolso "
               "mínimo = enganche propio + seguro año 1 + GAP contado + comisión; pago inicial mínimo = desembolso + "
               "bono al enganche (como lo muestra la cotización).")
    st.markdown("**Mensualidad con el enganche mínimo, de 12 meses al plazo máximo**")
    mm, marca_mm = [], []
    for o in res["ops"]:
        fila, fm = {"Oferta": o["nombre"]}, {}
        for n in om.PLAZOS:
            e = res["mens_min"][o["nombre"]][n]
            fila[f"{n} m"] = f"{om.money(e['mens'])} ({e['tasa']:.2f}%)" if e else "—"
            fm[f"{n} m"] = e["mens"] if e else None
        mm.append(fila)
        marca_mm.append(fm)
    df_mm, df_mmv = pd.DataFrame(mm), pd.DataFrame(marca_mm)
    st.dataframe(df_mm.style.apply(lambda col: [VERDE if col.name in df_mmv and pd.notna(df_mmv.loc[i, col.name])
                                                and df_mmv.loc[i, col.name] == df_mmv[col.name].min() else ""
                                                for i in col.index], axis=0),
                 hide_index=True, width="stretch",
                 column_config={"Oferta": st.column_config.TextColumn("Oferta", width="large")})
    st.caption("Meses 1-12 con el desembolso mínimo de cada plan en cada plazo (incluye el seguro y el GAP "
               "capturados); entre paréntesis la tasa sin IVA. «—»: el plan no maneja ese plazo. En verde, la menor "
               "en cada plazo.")
    st.download_button("PDF de mínimos de toda la oferta", pdf_minimos(om.BOLETIN, iva),
                       file_name=f"Minimos_oferta_MG_{om.BOLETIN}.pdf", mime="application/pdf",
                       icon=":material/table_view:",
                       help="Todos los autos y planes del boletín: enganche mínimo del sistema y real del cliente, "
                            "desembolso y pago inicial mínimos (+ seguro de contado) y mensualidades con el "
                            "enganche mínimo de 12 meses al plazo máximo.")

with t_rank:
    st.caption(("Con el mismo pago inicial en todas (el desembolso del cliente cambia según dónde va el bono)"
                if res["pago_inicial"] else "Con el mismo desembolso del cliente en todas") +
               ": el enganche se ajusta a lo que queda después del seguro "
               "y la comisión (más el bono si va al enganche). Pago inicial = enganche + comisión + seguro año 1 + "
               "GAP contado. Ordenadas por el total de mensualidades.")
    filas = []
    for i, (t, o, e) in enumerate(ranking, 1):
        filas.append({"#": str(i), "Oferta": o["nombre"], "Mens. 1-12": om.money(e["mens"]),
                      "Mens. 13+": om.money(e["mens2"]), "Tasa": f"{e['tasa']:.2f}%",
                      "Desembolso": om.money(e["desembolso"]),
                      "Tasa c/IVA": f"{e['tasa_iva']:.2f}%", "Pago inicial": om.money(e["pago_inicial"]),
                      "Eng. cliente": om.money0(e["eng_cliente"]),
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
        st.markdown("**No aplican con este desembolso**")
        for o, e in no_aplican:
            st.caption(D(f":material/block: {o['nombre']} — {e['motivo'] if e else 'no maneja este plazo'} · "
                         f"seguro permitido: {om.texto_rango(res['rangos'][o['nombre']])}"))
    st.caption("Mensualidad = pago fijo del capital + seguro de vida (0.82% anual sobre el capital). Desde el mes 13 "
               "se suma el seguro de cada año, financiado a 12 meses (aproximado al centavo).")

with t_seg:
    st.caption(D("El seguro se paga de contado con "
                 + (f"el pago inicial ({om.money0(res['pago_inicial'])})" if res["pago_inicial"] else
                    f"el desembolso del cliente ({om.money0(pago)})") + ": entre más cuesta, menos "
                 f"enganche queda. Mejor oferta a {plazo} meses según el costo del seguro del primer año."))
    tr = res["tramos"]
    validos = [t for t in tr if t["oferta"]]
    if validos:
        tope = min(res["tope_seguro"], max(t["hasta"] for t in validos) * 1.08 + 1)
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
    st.caption("Mensualidad de los meses 1-12 (tasa) con el enganche que resulta del desembolso en cada plazo. "
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
        mp.append({"Plazo": f"{n} meses", "Mejor oferta": o["nombre"], "Pago inicial": e["pago_inicial"],
                   "Desembolso": e["desembolso"],
                   "Tasa": f"{e['tasa']:.2f}%", "Eng. cliente": e["eng_cliente"],
                   "% cliente": f"{e['pct_cliente']:.1%}", "Eng. total": e["eng_total"], "Comisión": e["cxa"],
                   "Mens. 1-12": e["mens"], "Mens. 13+": e["mens2"], "Total mensualidades": e["total"]})
    st.dataframe(pd.DataFrame(mp), hide_index=True, width="stretch",
                 column_config={c: DOLAR(c) for c in ["Pago inicial", "Desembolso", "Eng. cliente", "Eng. total", "Comisión", "Mens. 1-12",
                                                      "Mens. 13+", "Total mensualidades"]})

# ----------------------------------------------------------------------------- PDF
st.divider()
slug = re.sub(r"[^A-Za-z0-9]+", "_", veh).strip("_")
d1, _ = st.columns([1, 3])
d1.download_button("PDF del análisis", pdf(args, cliente.strip()), file_name=f"Mejor_oferta_{slug}_{plazo}m.pdf",
                   mime="application/pdf", type="primary", width="stretch", icon=":material/picture_as_pdf:")
st.caption("Cálculo con el método del cotizador de Autoexpress; verifica la cifra final en el cotizador oficial. "
           "No incluye Anualidades, University ni Seminuevos.")
