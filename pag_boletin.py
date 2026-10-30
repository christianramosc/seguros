# -*- coding: utf-8 -*-
"""
Página «Oferta comercial»: subes el PDF del boletín nuevo de MG Financial Services y la app lo lee (boletin_mg.py):
autos, precios de lista, bonos, enganche sistema (color), tasas bajas, planes Estándar / Especial y lanzamientos.
Muestra lo que no cuadró, qué cambia contra la oferta en uso y los nuevos mínimos; todo se puede corregir a mano en las
tablas. Al guardar, «Mejor oferta MG» (cálculos, tabla de mínimos y PDFs) usa la oferta nueva con el mismo método del
cotizador. Se guarda en el Google Sheet (oferta_guardada.py) para que siga activa aunque la app se reinicie.

También acepta el respaldo .json que se descarga aquí mismo.
"""
import datetime as dt
import hashlib
import importlib.util
import json

import pandas as pd
import streamlit as st

import oferta_guardada
from ui import APAGADO, RESALTE, hero, insignias, nota, seccion, tarjeta

om = oferta_guardada.motor()
bm = oferta_guardada.lector()
guardado = oferta_guardada.leer()
hoy = dt.date.today()

hero("Oferta comercial", "Sube el boletín nuevo: bonos, precios, tasas y mínimos se actualizan en toda la app.",
     f"En uso: {om.BOLETIN}")

if "bol_msj" in st.session_state:
    ok, msj = st.session_state.pop("bol_msj")
    (st.success if ok else st.warning)(msj, icon=":material/check_circle:" if ok else ":material/warning:")
if guardado.get("error"):
    st.warning(guardado["error"], icon=":material/cloud_off:")

# ----------------------------------------------------------------------------- oferta en uso
fin = om.VIGENCIA_FIN
vencida = bool(fin and hoy > fin)
if guardado["actual"]:
    donde = "Google Sheet" if guardado["origen"] == "Google Sheet" else "Servidor de la app"
    detalle = f"subida el {guardado['actual'].get('guardada', '—')}"
else:
    donde, detalle = "Incluida en la app", "aún no se ha subido otra"
seccion("Oferta en uso", f"{om.OFERTA_MES} · {om.OFERTA.get('fuente') or ''}")
c1, c2, c3, c4 = st.columns(4)
con_precio = [v for k, v in om.CATALOGO.items() if v["msrp"]]
tarjeta(c1, "", "Boletín", om.OFERTA_MES or om.BOLETIN, om.BOLETIN)
tarjeta(c2, "", "Vigencia", f"{fin:%d/%m/%Y}" if fin else "—",
        om.VIGENCIA + (" · terminó" if vencida else f" · quedan {(fin - hoy).days} días" if fin else ""),
        color="#F87171" if vencida else None)
tarjeta(c3, "", "Autos con precio", len(con_precio),
        f"{sum(1 for v in con_precio if v['bono'])} con bono · "
        f"{sum(1 for k, v in om.CATALOGO.items() if v['lanz'])} de lanzamiento")
tarjeta(c4, "", "Guardada en", donde, detalle)
if vencida:
    st.warning(f"La oferta {om.BOLETIN} terminó el {fin:%d/%m/%Y}: sube el boletín nuevo abajo.",
               icon=":material/event_busy:")

b1, b2, b3 = st.columns([1.2, 1.2, 2], vertical_alignment="center")
if guardado["actual"] or guardado["anterior"]:
    previa = guardado["anterior"]
    etiqueta = f"Volver a la anterior ({previa.get('boletin') if previa else 'la incluida en la app'})"
    if b1.button(etiqueta, icon=":material/undo:", width="stretch"):
        ok, msj = oferta_guardada.deshacer()
        st.session_state["bol_msj"] = (ok, f"Listo: la app volvió a la oferta "
                                           f"{previa.get('boletin') if previa else 'incluida en la app'}. {msj}")
        st.rerun()
b2.download_button("Descargar respaldo (.json)", json.dumps(om.OFERTA, ensure_ascii=False, indent=1),
                   file_name=f"Oferta_MG_{om.BOLETIN}.json", mime="application/json", width="stretch",
                   icon=":material/download:")
nota("«Mejor oferta MG» (comparativo, tabla y PDF de mínimos) ya calcula con esta oferta.", b3)
if not oferta_guardada.permanente():
    st.info("La oferta que subas se guarda en el servidor de la app: si Streamlit la reinicia (o se duerme por "
            "inactividad) vuelve la incluida en la app y habría que subirla otra vez. Para que se quede guardada, "
            "agrega en Settings → Secrets `[gcp_service_account]` y `SEGUIMIENTO_SHEET_URL` (un Google Sheet "
            "compartido como Editor con la cuenta de servicio): se guarda en una pestaña oculta «_Oferta_MG».",
            icon=":material/cloud_off:")

# ----------------------------------------------------------------------------- subir
seccion("Subir boletín nuevo", "PDF del boletín de MG Financial Services o un respaldo .json")
st.session_state.setdefault("bol_n", 0)
archivo = st.file_uploader("Boletín", type=["pdf", "json"], key=f"bol_pdf_{st.session_state['bol_n']}",
                           label_visibility="collapsed")


@st.cache_data(show_spinner="Leyendo el boletín…", max_entries=5)
def leer_pdf(datos, nombre, version):
    return bm.leer_boletin(datos, nombre)


@st.cache_data(show_spinner=False, max_entries=10)
def resumen_minimos(oferta_txt, version):
    """Por auto: el plan con el menor desembolso (sin seguro), y su mensualidad a 60 meses (o al plazo máximo).
    Se calcula con una copia aparte de oferta_mg para no tocar la oferta en uso."""
    spec = importlib.util.spec_from_file_location("oferta_mg_vista", om.__file__)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.aplicar(json.loads(oferta_txt))
    filas = {}
    for a in m.tabla_minimos(True):
        planes = [p for p in a["planes"] if p.get("desembolso_min") is not None]
        if not planes:
            continue
        p = min(planes, key=lambda p: (p["desembolso_min"], p["pago_inicial_min"]))
        n = 60 if p["mens"].get(60) else max((k for k, x in p["mens"].items() if x), default=None)
        if n is None:
            continue
        filas[a["vehiculo"]] = dict(plan=p["oferta"], eng=p["min_cliente"], desembolso=p["desembolso_min"],
                                    pago_inicial=p["pago_inicial_min"], plazo=n, mens=p["mens"][n])
    return filas


if archivo is not None:
    datos = archivo.getvalue()
    clave = hashlib.sha1(datos).hexdigest()[:10]
    if archivo.name.lower().endswith(".json"):
        try:
            nueva, avisos = json.loads(datos.decode("utf-8")), []
            assert isinstance(nueva.get("vehiculos"), dict)
        except Exception:
            st.error("Ese .json no es un respaldo de la oferta.", icon=":material/error:")
            st.stop()
    else:
        try:
            nueva, avisos = leer_pdf(datos, archivo.name, getattr(bm, "_mtime", 0))
        except Exception as e:
            st.error(f"No pude leer el PDF ({e}). ¿Es el boletín de MG Financial Services?", icon=":material/error:")
            st.stop()
        if not nueva["vehiculos"]:
            st.error("No encontré la tabla de bonos ni las ofertas en ese PDF.", icon=":material/error:")
            st.stop()
    titulo = "Revisa lo que leí"
else:
    with st.expander("O corrige a mano la oferta en uso", icon=":material/edit:"):
        nota("Edita las tablas de abajo (por ejemplo, un bono o una tasa que cambió) y guarda.")
        editar = st.toggle("Editar la oferta en uso", key=f"bol_editar_{st.session_state['bol_n']}")
    if not editar:
        st.stop()
    nueva, avisos, clave = json.loads(json.dumps(om.OFERTA)), [], f"uso{om.OFERTA_ID}"
    titulo = "Oferta en uso"

# ----------------------------------------------------------------------------- revisar y corregir
seccion(titulo, f"{nueva.get('boletin') or 'sin clave'} · {nueva.get('vigencia') or 'sin vigencia'}")
vehs = nueva["vehiculos"]
insignias([f"{len(vehs)} autos", f"{sum(1 for v in vehs.values() if v.get('bono'))} con bono",
           f"{sum(len(v.get('tasa_baja') or []) for v in vehs.values())} tasas bajas",
           f"{len(nueva.get('planes_bono') or [])} planes con bono",
           f"{len(nueva.get('planes_sin_bono') or [])} planes sin bono",
           f"{sum(1 for v in vehs.values() if v.get('lanzamiento'))} lanzamientos"])
if archivo is not None:
    if avisos:
        st.warning("**Revisa estos puntos** (puedes corregirlos en las tablas):\n\n" +
                   "\n".join(f"- {a}" for a in avisos), icon=":material/rule:")
    else:
        st.success("Leí el boletín completo y todo cuadró (precios, bonos, mínimos por color y tasas).",
                   icon=":material/task_alt:")

tablas = bm.a_tablas(nueva)
PCT = lambda t, f="%.2f%%": st.column_config.NumberColumn(t, format=f, min_value=0.0, max_value=100.0)
TASAS = {c: PCT(c) for c in bm.COL_PLAZO.values()}
t_gen, t_autos, t_tb, t_pb, t_ps, t_lz = st.tabs(["Datos generales", "Autos y bonos", "Tasa baja", "Planes con bono",
                                                   "Planes sin bono", "Lanzamiento"])
with t_gen:
    g1, g2, g3 = st.columns(3)
    boletin = g1.text_input("Clave del boletín", nueva.get("boletin") or "", key=f"g_bol_{clave}")
    mes = g2.text_input("Mes de la oferta", nueva.get("mes") or "", key=f"g_mes_{clave}")
    eng_max = g3.number_input("Enganche máximo %", 1, 100, int(nueva.get("enganche_max") or 75), key=f"g_max_{clave}")
    g4, g5, _ = st.columns(3)
    fecha = lambda x: dt.date.fromisoformat(x) if x else None
    inicio = g4.date_input("Vigente desde", fecha(nueva.get("inicio")), format="DD/MM/YYYY", key=f"g_ini_{clave}")
    fin_n = g5.date_input("Vigente hasta", fecha(nueva.get("fin")), format="DD/MM/YYYY", key=f"g_fin_{clave}")
    colores = nueva.get("colores") or {}
    nota("Colores de la tabla de bonos: " + (", ".join(f"{c} = sistema {s}%" for s, c in colores.items()) or "—"))
with t_autos:
    nota("Un auto por fila, como en la tabla de bonos. Enganche sistema vacío = sin bono (aplican los planes de toda "
         "la gama). Sin precio = se captura en la cotización (lanzamientos).")
    autos = st.data_editor(tablas["autos"], key=f"ed_autos_{clave}", num_rows="dynamic", hide_index=True,
                           width="stretch", column_config={
                               "Auto": st.column_config.TextColumn("Auto", width="large", required=True),
                               "Precio de lista": st.column_config.NumberColumn(format="dollar", min_value=0),
                               "Bono": st.column_config.NumberColumn(format="dollar", min_value=0),
                               "Enganche sistema %": PCT("Enganche sistema %", "%.0f%%")})
nombres = [str(x).strip() for x in autos["Auto"].dropna() if str(x).strip()]
AUTO = st.column_config.SelectboxColumn("Auto", options=nombres, width="large", required=True)
with t_tb:
    nota("Tasa baja de cada versión (el bono ya va en la tasa). Una fila por auto y comisión (0% o 2%).")
    tb = st.data_editor(tablas["tasa_baja"], key=f"ed_tb_{clave}", num_rows="dynamic", hide_index=True,
                        width="stretch", column_config={"Auto": AUTO, "Comisión %": PCT("Comisión %"),
                                                        "Enganche desde %": PCT("Enganche desde %", "%.0f%%"),
                                                        **TASAS})
with t_pb:
    nota("Planes Estándar / Especial de los autos marcados en la tabla de bonos (bono al enganche o al precio). "
         "Mínimo por enganche sistema: incluye el bono cuando va al enganche.")
    pb = st.data_editor(tablas["planes_bono"], key=f"ed_pb_{clave}", num_rows="dynamic", hide_index=True,
                        width="stretch", column_config={"Comisión %": PCT("Comisión %"), **TASAS,
                                                        **{c: PCT(c, "%.0f%%") for c in tablas["planes_bono"].columns
                                                           if c.startswith("Mín.")}})
with t_ps:
    nota("Planes de toda la gama sin marca en la tabla de bonos. «Enganche hasta» limita un plan a un rango "
         "(p. ej. 17.74% de 10% a menos de 20%).")
    ps = st.data_editor(tablas["planes_sin_bono"], key=f"ed_ps_{clave}", num_rows="dynamic", hide_index=True,
                        width="stretch", column_config={"Comisión %": PCT("Comisión %"),
                                                        "Enganche desde %": PCT("Enganche desde %", "%.0f%%"),
                                                        "Enganche hasta %": PCT("Enganche hasta %", "%.0f%%"),
                                                        **TASAS})
with t_lz:
    nota("Modelos de lanzamiento: sin bono; aplican además los planes de toda la gama.")
    lz = st.data_editor(tablas["lanzamiento"], key=f"ed_lz_{clave}", num_rows="dynamic", hide_index=True,
                        width="stretch", column_config={"Auto": AUTO, "Comisión %": PCT("Comisión %"),
                                                        "Enganche desde %": PCT("Enganche desde %", "%.0f%%"),
                                                        **TASAS})

oferta, errores = bm.de_tablas(
    dict(autos=autos, tasa_baja=tb, lanzamiento=lz, planes_bono=pb, planes_sin_bono=ps),
    dict(boletin=boletin, mes=mes, inicio=inicio, fin=fin_n, enganche_max=eng_max, colores=colores,
         fuente=nueva.get("fuente") or (archivo.name if archivo is not None else "")))
for e in errores:
    st.error(e, icon=":material/error:")
revisar = [a for a in bm.validar(oferta, hoy) if a not in avisos]
if revisar:
    st.warning("\n".join(f"- {a}" for a in revisar), icon=":material/info:")

# ----------------------------------------------------------------------------- qué cambia
igual = om.huella(oferta) == om.OFERTA_ID
cambios = bm.cambios(om.OFERTA, oferta)
seccion("Qué cambia contra la oferta en uso", f"{len(cambios)} cambios" if cambios else "sin cambios")
if cambios:
    st.dataframe(pd.DataFrame(cambios), hide_index=True, width="stretch",
                 column_config={"Qué": st.column_config.TextColumn(width="medium"),
                                "Antes": st.column_config.TextColumn(width="large"),
                                "Ahora": st.column_config.TextColumn(width="large")})
else:
    nota("Es la misma oferta que ya está en uso.")

if not errores:
    nuevo = resumen_minimos(json.dumps(oferta), getattr(om, "_mtime", 0))
    previo = resumen_minimos(json.dumps(om.OFERTA), getattr(om, "_mtime", 0))
    seccion("Mínimos con esta oferta", "sin seguro de contado · el plan de menor desembolso de cada auto")
    filas = []
    for veh, r in nuevo.items():
        a = previo.get(veh)
        filas.append({"Auto": veh, "Plan de menor desembolso": r["plan"], "Enganche del cliente": r["eng"],
                      "Desembolso mínimo": r["desembolso"], "Antes": a["desembolso"] if a else None,
                      "Pago inicial mínimo": r["pago_inicial"], "Plazo": r["plazo"], "Mensualidad": r["mens"],
                      "Mensualidad antes": (previo[veh]["mens"] if a and a["plazo"] == r["plazo"] else None)})
    df = pd.DataFrame(filas)
    if not df.empty:
        cambio = {"Desembolso mínimo": df["Antes"].fillna(-1) != df["Desembolso mínimo"],
                  "Mensualidad": df["Mensualidad antes"].fillna(-1).round(2) != df["Mensualidad"].round(2)}
        sty = df.style.apply(lambda f: [RESALTE if c in cambio and cambio[c][f.name]
                                        else APAGADO if c in ("Antes", "Mensualidad antes") else ""
                                        for c in f.index], axis=1)
        DOL = lambda t: st.column_config.NumberColumn(t, format="dollar")
        st.dataframe(sty, hide_index=True, width="stretch", column_config={
            "Auto": st.column_config.TextColumn(width="large"),
            "Enganche del cliente": st.column_config.NumberColumn(format="percent"),
            "Desembolso mínimo": DOL("Desembolso mínimo"), "Antes": DOL("Antes"),
            "Pago inicial mínimo": DOL("Pago inicial mínimo"), "Mensualidad": DOL("Mensualidad"),
            "Mensualidad antes": DOL("Mensualidad antes"), "Plazo": st.column_config.NumberColumn(format="%d m")})
        nota("En verde lo que cambia contra la oferta en uso. La tabla completa por plan y plazo sale en el PDF de "
             "mínimos de «Mejor oferta MG».")

# ----------------------------------------------------------------------------- guardar
st.divider()
g1, g2 = st.columns([1.3, 2], vertical_alignment="center")
if g1.button("Guardar y usar esta oferta", type="primary", width="stretch", icon=":material/save:",
             disabled=bool(errores) or igual):
    ok, msj = oferta_guardada.guardar(oferta)
    st.session_state["bol_msj"] = (ok, f"Listo: la app ya calcula con la oferta {oferta['boletin']}. {msj}")
    om.aplicar(oferta)
    st.session_state["bol_n"] += 1           # limpia el archivo subido y el modo de edición
    st.rerun()
nota("Corrige los errores en rojo para poder guardar." if errores else
     "Ya es la oferta en uso." if igual else
     "Desde que guardes, toda la app calcula con esta oferta (la actual queda como «anterior» para deshacer).", g2)
