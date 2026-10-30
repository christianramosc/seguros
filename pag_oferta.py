# -*- coding: utf-8 -*-
"""
Página «Mejor oferta MG»: eliges el auto y capturas el desembolso del cliente o el pago inicial; compara todas las
ofertas del boletín de MG Financial Services con el método del cotizador de Autoexpress (cálculo en oferta_mg.py).

Pago inicial (como en la cotización) = enganche + comisión por apertura + seguro contado año 1; el enganche incluye
el bono cuando va al enganche. Desembolso del cliente = pago inicial − bono al enganche.

Orden de la página: datos de la operación → mejor opción (tarjetas) → tabla con todos los planes → pestañas «Por
plazo», «Mínimos por plan» y «Oferta del auto» → descargas (PDF del análisis y PDF de mínimos).

Por ahora sin GAP (faltan los precios actualizados) ni seguro de los años 2+: se activan con MOSTRAR_GAP y
MOSTRAR_SEGURO_2.
"""
import datetime as dt
import re

import pandas as pd
import streamlit as st

import oferta_guardada
from ui import APAGADO, RESALTE, VERDE_T, hero, insignias, nota, seccion, tarjeta

# oferta_mg al día (Streamlit Cloud conserva los módulos entre despliegues) y con la oferta comercial que se subió en
# la página «Oferta comercial» (o la incluida en la app si no se ha subido otra).
om = oferta_guardada.motor()
VERSION = f"{om._mtime}-{om.OFERTA_ID}"     # llave de los cachés: cambia con el código o con la oferta

MOSTRAR_GAP = False        # desactivado hasta tener los precios de GAP actualizados
MOSTRAR_SEGURO_2 = False   # seguro de los años 2+ oculto: la mensualidad no lo incluye

D = lambda t: str(t).replace("$", "\\$")   # en markdown, «$» abre fórmulas
DOLAR = lambda t, **k: st.column_config.NumberColumn(t, format="dollar", **k)
TEXTO_L = lambda t: st.column_config.TextColumn(t, width="large")

hero("Mejor oferta MG", "Compara todas las ofertas del boletín con lo que trae el cliente.",
     f"Boletín {om.BOLETIN} · vigente {om.VIGENCIA}")
if om.VIGENCIA_FIN and dt.date.today() > om.VIGENCIA_FIN:
    st.warning(f"La oferta {om.BOLETIN} terminó el {om.VIGENCIA_FIN:%d/%m/%Y}. Sube el boletín nuevo en «Oferta "
               "comercial» para usar los bonos y tasas vigentes.", icon=":material/event_busy:")

# ----------------------------------------------------------------------------- datos de la operación
autos = list(om.CATALOGO)
CAPTURAS = ("Desembolso", "Pago inicial")
st.session_state.setdefault("of_pago", 130000)
st.session_state.setdefault("of_pi", 0)
seguro_anual, resto_fin, gap_modo, gap_monto = 0.0, False, "No", 0.0
with st.container(border=True):
    a1, a2 = st.columns([3, 1], vertical_alignment="bottom")
    if st.session_state.get("of_veh") not in autos:      # el auto ya no está en la oferta nueva
        st.session_state.pop("of_veh", None)
    defecto = "MG5 2027 1.5L COM EXCITE AT"
    veh = a1.selectbox("Auto", autos, index=autos.index(defecto) if defecto in autos else 0, key="of_veh")
    v = om.CATALOGO[veh]
    precio_manual = a2.number_input("Precio", min_value=0, value=0, step=1000, key="of_precio",
                                    help="0 = precio de lista. Obligatorio en Lanzamiento y «Otro».")
    if v["msrp"]:
        insignias([f"Lista {om.money0(v['msrp'])}", f"Bono {om.money0(v['bono'])}" if v["bono"] else "Sin bono",
                   f"Sistema {v['color']}% · {om.color_de(v['color'])}" if v["color"] else ""])
    else:
        insignias(["Sin precio en el boletín: captúralo en «Precio»"])

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
                           help="Lo que pone de su bolsa: enganche propio + comisión + seguro año 1.")
    pago_inicial = b3.number_input("Pago inicial", min_value=0, step=5000, key="of_pi",
                                   disabled=captura != "Pago inicial",
                                   help="Como en la cotización: desembolso + bono al enganche (en Tasa Baja son "
                                        "iguales).")
    plazo = b4.segmented_control("Plazo", om.PLAZOS, default=60, key="of_plazo",
                                 format_func=lambda n: f"{n} m") or 60

    c1, c2, c3 = st.columns([1, 1.3, 1.7], vertical_alignment="bottom")
    seguro1 = c1.number_input("Seguro año 1", min_value=0.0, value=0.0, step=500.0, key="of_seg",
                              help="Importe primer año. En 0 si aún no lo tienes: la tabla dice hasta cuánto puede "
                                   "valer.")
    seguro1_fin = (c2.segmented_control("Pago del seguro", ["Contado", "Financiado"], default="Contado",
                                        key="of_seg1_modo",
                                        help="Contado: va en el pago inicial. Financiado (multianual fraccionado): "
                                             "se amortiza en los meses 1-12 y paga comisión.")
                   or "Contado") == "Financiado"
    if MOSTRAR_SEGURO_2:
        seguro_anual = c3.number_input("Seguro anual (años 2+)", min_value=0.0, value=0.0, step=500.0,
                                       key="of_seg_anual", help="En 0 = igual al año 1.")
        resto_fin = (c3.segmented_control("Seguro años 2+", ["Financiado", "Contado"], default="Financiado",
                                          key="of_seg2_modo") or "Financiado") == "Financiado"
    if MOSTRAR_GAP:
        gap_modo = c3.segmented_control("GAP", om.GAP_MODOS, default="No", key="of_gap") or "No"
        gap_monto = c3.number_input("Monto GAP", min_value=0.0, value=0.0, step=100.0, key="of_gap_monto",
                                    disabled=gap_modo == "No")
    iva = c3.toggle("IVA sobre intereses", value=True, key="of_iva")

if om.requiere_precio(veh) and not precio_manual:
    st.markdown('<div class="vacio"><b>Captura el precio del auto</b><br>'
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
def pdf_minimos(version, boletin, iva):
    return om.pdf_minimos(iva)


@st.cache_data(show_spinner=False)
def pdf(version, a, cliente):
    return om.pdf_bytes(correr(version, *a), cliente)


args = (veh, float(pago), float(seguro1), float(seguro_anual), int(plazo), float(precio_manual), gap_modo, iva,
        float(pago_inicial) if captura == "Pago inicial" else 0.0, seguro1_fin, resto_fin,
        float(gap_monto) if gap_modo != "No" else 0.0)
res = correr(VERSION, *args)
ranking = res["ranking"]

# ----------------------------------------------------------------------------- mejor opción
if ranking:
    _, op, ev = ranking[0]
    seccion("Mejor opción", f"{op['nombre']} · baremo {op['baremo']} · bono {ev['forma']}")
    if ev["bono_precio"]:
        insignias([f"Precio del plan: {om.texto_precio(ev)}"], ok=(f"Precio del plan: {om.texto_precio(ev)}",))
    k = st.columns(5)
    tarjeta(k[0], "", "Mensualidad", om.money(ev["mens"]),
            "Meses 1-12" + (f" · 13+: {om.money(ev['mens2'])}" if ev["mens2"] and MOSTRAR_SEGURO_2 else ""),
            VERDE_T)
    tarjeta(k[1], "", "Pago inicial", om.money(ev["pago_inicial"]), om.desglose(ev))
    tarjeta(k[2], "", "Desembolso", om.money(ev["desembolso"]), om.desglose_desembolso(ev))
    tarjeta(k[3], "", "Tasa", f"{ev['tasa']:.2f}%", f"{ev['tasa_iva']:.2f}% con IVA · com. {op['cxa']:.0%}")
    tarjeta(k[4], "", "Plazo", f"{plazo} meses", f"Financiado {om.money0(ev['financiado'])}")
    notas = [f"Total de mensualidades {om.money(ev['total'])}."]
    menor = min(ranking, key=lambda x: x[2]["mens"])
    if menor[1] is not op:
        notas.append(f"Menor mensualidad: {menor[1]['nombre']} ({om.money(menor[2]['mens'])}), "
                     f"{om.money(menor[0] - ranking[0][0])} más en total.")
    if not seguro1:
        notas.append("Seguro en $0: todo va a enganche; la columna «Póliza año 1» dice hasta cuánto puede valer.")
    if seguro1_fin:
        notas.append("Seguro financiado: no va en el pago inicial y paga comisión.")
    for t in notas:
        nota(t)
else:
    st.warning(f"Ninguna oferta es válida a {plazo} meses con este {captura.lower()}.")

# ----------------------------------------------------------------------------- todos los planes
seccion("Planes del boletín", f"a {plazo} meses · ordenados por total de mensualidades")
orden = {o["nombre"]: i for i, (_, o, _) in enumerate(ranking, 1)}
filas = []
for o in sorted(res["ops"], key=lambda o: orden.get(o["nombre"], 99)):
    e = res["evals"][o["nombre"]]
    fila = {"#": str(orden.get(o["nombre"], "—")), "Oferta": o["nombre"],
            "Póliza año 1": om.texto_rango(res["rangos"][o["nombre"]])}
    if not e:
        filas.append(fila | {"Nota": "No maneja este plazo"})
        continue
    fila |= {"Bono": e["forma"],
             "Precio": (f"{om.money0(e['precio_plan'])} (−{om.money0(e['bono_precio'])})" if e["bono_precio"]
                        else om.money0(e["precio_plan"])), "Pago inicial": e["pago_inicial"],
             "Desembolso": e["desembolso"], "Enganche": f"{e['pct']:.1%}"}
    if e["valida"]:
        fila |= {"Mensualidad": e["mens"], "Mens. 13+": e["mens2"], "Tasa": f"{e['tasa']:.2f}%",
                 "Total": e["total"]}
    else:
        fila["Nota"] = e["motivo"]
    filas.append(fila)
cols = ["#", "Oferta", "Mensualidad", "Mens. 13+", "Tasa", "Precio", "Pago inicial", "Desembolso", "Enganche",
        "Bono", "Total", "Póliza año 1", "Nota"]
df = pd.DataFrame(filas).reindex(columns=cols)
if not MOSTRAR_SEGURO_2 or (not seguro_anual and not seguro1):
    df = df.drop(columns="Mens. 13+")
if df["Nota"].isna().all():
    df = df.drop(columns="Nota")
for c in ["Mensualidad", "Mens. 13+", "Pago inicial", "Desembolso", "Total"]:
    if c in df:
        df[c] = df[c].map(lambda x: om.money(x) if pd.notna(x) else None)
df = df.fillna("—")
st.dataframe(df.style.apply(lambda r: [RESALTE if r["#"] == "1" else APAGADO if r["#"] == "—" else ""] * len(r),
                            axis=1),
             hide_index=True, width="stretch",
             column_config={"#": st.column_config.TextColumn("#", width="small"), "Oferta": TEXTO_L("Oferta"),
                            "Precio": st.column_config.TextColumn("Precio", help="Con el bono al precio: precio de lista − bono"),
                            "Nota": TEXTO_L("Nota")})
nota("«Precio»: con el bono al precio, el precio de lista ya con el bono descontado (el enganche % se calcula sobre ese precio). "
     "«Póliza año 1»: rango del seguro con el que el plan cumple. En gris, los planes que no aplican.")

# ----------------------------------------------------------------------------- detalle
seccion("Detalle")
t_plazo, t_min, t_oferta = st.tabs([":material/calendar_view_month: Por plazo", ":material/flag: Mínimos por plan",
                                    ":material/sell: Oferta del auto"])

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
    st.dataframe(df_m.style.apply(lambda col: [RESALTE if col.name in df_marca and df_marca.loc[i, col.name]
                                               else "" for i in col.index], axis=0),
                 hide_index=True, width="stretch", column_config={"Oferta": TEXTO_L("Oferta")})
    nota("Mensualidad meses 1-12 (tasa) con lo capturado. En verde, la mejor de cada plazo.")

with t_min:
    filas_min, valores = [], []
    for q in res["requisitos"]:
        fila = {"Oferta": q["oferta"],
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
                 column_config={"Oferta": TEXTO_L("Oferta"), "Desembolso mín.": DOLAR("Desembolso mín."),
                                "Pago inicial mín.": DOLAR("Pago inicial mín.")})
    nota(f"Con el enganche mínimo de cada plan (incluye el seguro capturado; desembolso y pago inicial a {plazo} m). "
         "Mensualidad meses 1-12 (tasa); en verde, la menor de cada plazo.")

with t_oferta:
    st.markdown(D(res["descripcion"]))

# ----------------------------------------------------------------------------- descargas
seccion("Descargas")
slug = re.sub(r"[^A-Za-z0-9]+", "_", veh).strip("_")
d1, d2 = st.columns(2)
with d1.container(border=True):
    st.markdown("**PDF del análisis**")
    nota("Esta cotización: mejor opción, comparativo de planes, mensualidad por plazo y requisitos del auto.")
    cliente = st.text_input("Cliente", key="of_cli", placeholder="Nombre del cliente (opcional)",
                            label_visibility="collapsed")
    st.download_button("Descargar análisis", pdf(VERSION, args, cliente.strip()),
                       file_name=f"Mejor_oferta_{slug}_{plazo}m.pdf", mime="application/pdf", type="primary",
                       width="stretch", icon=":material/picture_as_pdf:")
with d2.container(border=True):
    st.markdown("**PDF de mínimos de toda la oferta**")
    nota("Todos los autos y planes del boletín: enganche, desembolso y pago inicial mínimos y mensualidades.")
    st.download_button("Descargar mínimos", pdf_minimos(VERSION, om.BOLETIN, iva),
                       file_name=f"Minimos_oferta_MG_{om.BOLETIN}.pdf", mime="application/pdf", width="stretch",
                       icon=":material/table_view:")

nota("Método del cotizador de Autoexpress: verifica la cifra final en el cotizador oficial. No incluye Anualidades, "
     "University ni Seminuevos.")
