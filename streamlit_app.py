# -*- coding: utf-8 -*-
"""
App de seguimiento de pólizas de seguro (MG Colima · Autoexpress Inbursa).

A quién llamar hoy, oportunidades por mes y registro del contacto. Se suben los PDF / ZIP de las pólizas (Crédito
Click, columna Impresión) y/o el Excel Polizas_extraidas.xlsx; los datos de clientes solo viven en la sesión (nunca se
guardan en el repo ni en el servidor). El seguimiento se descarga en el mismo Excel.

Reglas (días naturales antes de cada aniversario de la póliza):
  · póliza externa: a más tardar 45 días antes (después se cierra)
  · pago de contado: desde 30 días antes hasta el día anterior
  · llamar al menos 7 días antes del límite de externa
  · al terminar el crédito el auto es del cliente: puede contratar el seguro que quiera.
"""
import datetime as dt
import html
import os
import time

# Streamlit Cloud corre en UTC: usar la hora de México para que «hoy» no cambie a las 6 pm
os.environ["TZ"] = "America/Mexico_City"
if hasattr(time, "tzset"):
    time.tzset()

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

import almacen  # noqa: E402
import seguimiento as ps  # noqa: E402

st.set_page_config(page_title="Pólizas MG Colima", page_icon="🛡️", layout="wide")

AZUL, TEXTO, TEXTO_2 = "#12305C", "#1B2A41", "#5A6B82"
MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def acceso_permitido():
    """Pide contraseña solo si existe APP_PASSWORD en los secrets."""
    try:
        clave = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        clave = ""
    if not clave or st.session_state.get("acceso_ok"):
        return True
    st.title("Pólizas MG Colima")
    intento = st.text_input("Contraseña", type="password")
    if intento:
        if intento == clave:
            st.session_state["acceso_ok"] = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    return False


if not acceso_permitido():
    st.stop()

st.markdown(f"""
<style>
.block-container {{ padding-top: 1.6rem; max-width: 1320px; }}
.hero {{ background: {AZUL}; color: #fff; border-radius: 14px; padding: 22px 28px; display: flex;
        justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }}
.hero h1 {{ font-size: 1.8rem; font-weight: 800; margin: 0; color: #fff; line-height: 1.1; }}
.hero p {{ margin: 6px 0 0; color: #C9D6EA; font-size: .95rem; }}
.hero .file {{ color: #C9D6EA; font-size: .85rem; text-align: right; }}
.kv {{ font-size: 2.1rem !important; font-weight: 800 !important; line-height: 1.1 !important; margin: 0 !important; }}
.ks {{ font-size: .82rem !important; color: {TEXTO_2}; margin: 2px 0 4px; white-space: nowrap; overflow: hidden;
       text-overflow: ellipsis; }}
.vacio {{ border: 2px dashed #CBD4E1; border-radius: 14px; padding: 36px; text-align: center; color: {TEXTO_2}; }}
.vacio b {{ color: {TEXTO}; font-size: 1.1rem; }}
</style>
""", unsafe_allow_html=True)


def hero(titulo, subtitulo, derecha=""):
    st.markdown(f"""<div class="hero"><div><h1>{html.escape(titulo)}</h1>
<p>{html.escape(subtitulo)}</p></div><div class="file">{html.escape(derecha)}</div></div>""", unsafe_allow_html=True)


def tarjeta(donde, icono, titulo, valor, detalle="", color=None):
    caja = donde.container(border=True)
    caja.markdown(f":material/{icono}: **{html.escape(titulo)}**")
    caja.markdown(f'<div class="kv" style="color:{color or TEXTO}">{html.escape(str(valor))}</div>'
                  f'<div class="ks" title="{html.escape(detalle)}">{html.escape(detalle)}</div>', unsafe_allow_html=True)


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
hoy = dt.date.today()
hero("Pólizas de seguro · MG Colima", "A quién llamar para póliza externa, pago de contado o fin de crédito.",
     f"Corte {hoy:%d/%m/%Y}")

# ----------------------------------------------------------------------------- carga
def guardar_actual():
    """Guarda el Excel con el seguimiento actual para la próxima vez que se abra la app."""
    ok, msg = almacen.guardar(st.session_state["pol_excel"])
    st.session_state["pol_guardado"] = (ok, msg, dt.datetime.now())


# al abrir: si no hay nada cargado, toma el último Excel guardado
if st.session_state.get("pol_base") is None and not st.session_state.get("pol_auto"):
    st.session_state["pol_auto"] = True
    datos, origen = almacen.leer()
    if datos:
        try:
            base, excel, errores = ps.cargar([], datos)
            st.session_state.update(pol_base=base, pol_excel=excel, pol_err=errores, pol_origen=f"último Excel ({origen})")
        except Exception:
            pass

with st.container(border=True):
    c1, c2 = st.columns([3, 2])
    pdfs = c1.file_uploader("Pólizas (PDF o ZIP)", type=["pdf", "zip"], accept_multiple_files=True, key="pol_pdfs",
                            help="Los PDF que se descargan de Crédito Click (columna Impresión). Puedes subir varios "
                                 "o un ZIP. Si solo vas a revisar el seguimiento, basta con el Excel.")
    xls = c2.file_uploader("Excel anterior (opcional)", type=["xlsx"], key="pol_xlsx",
                           help="Polizas_extraidas.xlsx: conserva lo que ya capturaste (Contactado, Resultado, Notas) "
                                "y, si también subes PDFs nuevos, los junta con los clientes que ya tenías.")
    if st.button("Cargar", type="primary", disabled=not (pdfs or xls), icon=":material/upload:"):
        with st.spinner("Leyendo pólizas…" if pdfs else "Leyendo el Excel…"):
            try:
                base, excel, errores = ps.cargar([(f.name, f.getvalue()) for f in pdfs or []],
                                                 xls.getvalue() if xls else None)
                st.session_state.update(pol_base=base, pol_excel=excel, pol_err=errores,
                                        pol_origen=f"{len(pdfs)} archivo(s) PDF/ZIP" if pdfs else xls.name)
                st.session_state.pop("pol_editor", None)
                guardar_actual()
            except Exception as e:
                st.error(f"No se pudo cargar: {e}")

base = st.session_state.get("pol_base")
if base is None:
    st.markdown('<div class="vacio"><b>Sube las pólizas o tu Excel de pólizas</b><br>'
                'La primera vez sube los PDF o el ZIP; después basta con el Excel que descargas de aquí.</div>',
                unsafe_allow_html=True)
    st.stop()

if st.session_state.get("pol_err"):
    with st.expander(f":material/warning: {len(st.session_state['pol_err'])} PDF no se leyeron completos"):
        st.dataframe(pd.DataFrame(st.session_state["pol_err"], columns=["Archivo", "Motivo"]), hide_index=True)

with st.expander("Reglas", icon=":material/tune:"):
    r1, r2, r3 = st.columns(3)
    reglas = dict(
        externa=r1.number_input("Último día póliza externa (días antes del aniversario)", 1, 120, ps.REGLAS["externa"]),
        contado=r2.number_input("Abre ventana de contado (días antes)", 1, 120, ps.REGLAS["contado"]),
        aviso=r3.number_input("Llamar N días antes del límite de externa", 0, 60, ps.REGLAS["aviso"]))
    st.caption("Póliza externa hasta 45 días antes del aniversario (después se cierra) · contado desde 30 días antes "
               "hasta el día anterior · al terminar el crédito el auto es del cliente y puede contratar el seguro que "
               "quiera.")

df = ps.calcular(base, hoy, reglas)
proy = ps.proyeccion(base, hoy, 12, reglas)
n = lambda e: int((df["ESTATUS"] == e).sum())
contactados = df["CONTACTADO"].astype(str).str.lower().isin(["sí", "si"]).sum()
cierres = df["RESULTADO"].isin(ps.CIERRES).sum()

k = st.columns(5)
_pc = ps.para_contactar(df, hoy)
_ext = int(_pc["ESTATUS"].isin([ps.LLAMAR_EXT, ps.ADELANTAR]).sum())
_fin = int(_pc["ESTATUS"].isin([ps.FIN_LLAMAR, ps.ADELANTAR_FIN]).sum())
tarjeta(k[0], "call", "Llamar ya", _ext + _fin,
           f"{_ext} póliza externa · {_fin} fin de crédito (incluye lo que queda del mes)", "#9C0006")
tarjeta(k[1], "payments", "Contado abierto", n(ps.CONTADO), "Que paguen antes del día anterior al aniversario",
           "#9C5700")
tarjeta(k[2], "lock_clock", "Externa cerrada", n(ps.EXT_CERRADA), "Esperan su ventana de contado", "#C55A11")
mes_sig = proy[proy["MES"] == dt.date(hoy.year, hoy.month, 1)] if not proy.empty else proy
tarjeta(k[3], "event_upcoming", f"Este mes ({MESES[hoy.month - 1]})", len(mes_sig),
           f"Prima anual en juego ${mes_sig['PRIMA ANUAL ACTUAL'].sum():,.0f}" if len(mes_sig) else "Sin oportunidades")
tarjeta(k[4], "verified", "Contactados", int(contactados),
           f"{cierres} cerrados ({cierres / contactados:.0%})" if contactados else "Aún sin registrar")
st.caption(f"{len(df)} créditos · fuente: {st.session_state.get('pol_origen', '')}")
if st.session_state.get("pol_guardado"):
    ok, msg, cuando = st.session_state["pol_guardado"]
    st.caption(f"{':material/cloud_done:' if ok else ':material/save:'} {msg} · {cuando:%H:%M}"
               + ("" if almacen.drive_configurado() else
                  " · se conserva mientras la app esté activa; para guardarlo siempre, configura Drive (README)"))

COLS_HOY = ["ESTATUS", "CLIENTE", "TELÉFONO", "CIERRA EN", "PRÓXIMA FECHA", "OPORTUNIDAD", "LLAMAR DESDE",
            "ÚLTIMO DÍA EXTERNA", "ABRE CONTADO", "ÚLTIMO DÍA CONTADO", "QUÉ HACER", "ASEGURADORA",
            "PRIMA ANUAL ACTUAL", "CORREO", "VEHÍCULO", "FOLIO CRÉDITO", "MUNICIPIO"]
CONF = {c: st.column_config.DateColumn(c, format="DD/MM/YYYY") for c in
        ["PRÓXIMA FECHA", "LLAMAR DESDE", "ÚLTIMO DÍA EXTERNA", "ABRE CONTADO", "ÚLTIMO DÍA CONTADO", "FECHA",
         "FECHA CONTACTO", "FIN DEL CRÉDITO"]}
CONF["PRIMA ANUAL ACTUAL"] = st.column_config.NumberColumn("PRIMA ANUAL", format="dollar")


def con_seguimiento(base, editado):
    """Pasa lo capturado en la tabla de Seguimiento a la base (si marcó «Sí» sin fecha, se toma hoy)."""
    b = base.copy()
    if editado is None or editado.empty:
        return b
    for _, r in editado.iterrows():
        i = b.index[b["SERIE"] == r["SERIE"]]
        fecha = r["FECHA CONTACTO"]
        sin_fecha = fecha is None or pd.isna(fecha)
        if str(r["CONTACTADO"]).strip().lower() in ("sí", "si") and sin_fecha:
            fecha, sin_fecha = pd.Timestamp(hoy), False
        b.loc[i, "CONTACTADO"] = r["CONTACTADO"] if isinstance(r["CONTACTADO"], str) else ""
        b.loc[i, "FECHA CONTACTO"] = None if sin_fecha else pd.Timestamp(fecha).date()
        b.loc[i, "RESULTADO"] = r["RESULTADO"] if isinstance(r["RESULTADO"], str) else ""
        b.loc[i, "NOTAS"] = r["NOTAS"] if isinstance(r["NOTAS"], str) else ""
    return b


def colorear(v):
    if v in ps.ESTATUS:
        _, fondo, letra = ps.ESTATUS[v]
        return f"background-color: #{fondo}; color: #{letra}; font-weight: 600"
    return ""


def ver(d, cols, alto=None):
    if d.empty:
        st.info("Sin clientes en esta vista.")
        return
    cols = [c for c in cols if c in d.columns]
    estilo = d[cols].style.map(colorear, subset=[c for c in ["ESTATUS"] if c in cols])
    st.dataframe(estilo, hide_index=True, width="stretch", column_config=CONF, **({"height": alto} if alto else {}))


t_hoy, t_mes, t_todos, t_seg = st.tabs([":material/today: Hoy", ":material/calendar_month: Por mes",
                                        ":material/groups: Todos", ":material/edit_note: Seguimiento"])

with t_hoy:
    urg = ps.para_contactar(df, hoy)
    st.markdown(f"**Para contactar ya ({len(urg)})** · ordenados por lo que vence primero. Incluye a los que les "
                f"toca llamar en lo que queda de {MESES[hoy.month - 1]}: su externa sigue abierta, puedes adelantarte.")
    ver(urg, COLS_HOY)
    esp = df[df["ESTATUS"] == ps.EXT_CERRADA].sort_values("ABRE CONTADO")
    st.markdown(f"**Externa cerrada · llamar cuando abra el contado ({len(esp)})**")
    ver(esp, COLS_HOY)

with t_mes:
    if proy.empty:
        st.info("Sin oportunidades en los próximos 12 meses.")
    else:
        g = proy.assign(Mes=proy["MES"].map(lambda d: f"{MESES_CORTOS[d.month - 1]} {d.year}"),
                        orden=proy["MES"]).groupby(["orden", "Mes", "TIPO"]).size().reset_index(name="Oportunidades")
        graf = alt.Chart(g).mark_bar().encode(
            x=alt.X("Mes:N", sort=alt.SortField("orden"), title=None),
            y=alt.Y("Oportunidades:Q", title="Oportunidades"),
            color=alt.Color("TIPO:N", title=None, scale=alt.Scale(domain=["Aniversario", "Fin de crédito"],
                                                                   range=["#1D4A86", "#8E5BB5"])),
            tooltip=["Mes", "TIPO", "Oportunidades"]).properties(height=240)
        st.altair_chart(graf, width="stretch")
        st.caption("Mes en que toca empezar a llamar (7 días antes del límite de póliza externa). "
                   "Las que ya están abiertas cuentan en el mes actual.")
        meses = sorted(proy["MES"].unique())
        etiqueta = lambda d: f"{MESES[d.month - 1].capitalize()} {d.year}"
        m = st.selectbox("Mes", meses, format_func=etiqueta, key="pol_mes")
        del_mes = proy[proy["MES"] == m]
        a, b, c = st.columns(3)
        a.metric("Oportunidades", len(del_mes))
        b.metric("Fin de crédito", int((del_mes["TIPO"] == "Fin de crédito").sum()))
        c.metric("Prima anual en juego", f"${del_mes['PRIMA ANUAL ACTUAL'].sum():,.0f}")
        ver(del_mes, ["LLAMAR DESDE", "FECHA", "TIPO", "OPORTUNIDAD", "CLIENTE", "TELÉFONO", "CORREO", "ASEGURADORA",
                      "PRIMA ANUAL ACTUAL", "VEHÍCULO"])
        st.session_state["pol_pdf_mes"] = (del_mes, etiqueta(m))

with t_todos:
    f1, f2, f3 = st.columns(3)
    est = f1.multiselect("Estatus", list(ps.ESTATUS), placeholder="Todos", key="pol_f_est")
    ase = f2.multiselect("Aseguradora", sorted(df["ASEGURADORA"].dropna().unique()), placeholder="Todas",
                         key="pol_f_ase")
    txt = f3.text_input("Buscar cliente, serie o folio", key="pol_f_txt")
    vista = df
    if est:
        vista = vista[vista["ESTATUS"].isin(est)]
    if ase:
        vista = vista[vista["ASEGURADORA"].isin(ase)]
    if txt:
        t = txt.strip().upper()
        vista = vista[vista["CLIENTE"].str.upper().str.contains(t, regex=False) |
                      vista["SERIE"].str.upper().str.contains(t, regex=False) |
                      vista["FOLIO CRÉDITO"].astype(str).str.contains(t, regex=False)]
    st.caption(f"{len(vista)} de {len(df)} créditos")
    ver(vista, COLS_HOY + ["FIN DEL CRÉDITO", "DIRECCIÓN", "SERIE"], alto=520)

with t_seg:
    st.caption("Registra aquí el contacto. Para no perderlo, **descarga el Excel** al terminar (la app no guarda "
               "datos de clientes) y la próxima vez súbelo en «Excel anterior».")
    solo = st.toggle("Solo los que hay que contactar ahora", value=True, key="pol_seg_solo")
    ed = df if not solo else df[df["ESTATUS"].isin(ps.URGENTES + [ps.EXT_CERRADA, ps.CONTACTADO])]
    cols_ed = ["ESTATUS", "CLIENTE", "TELÉFONO", "PRÓXIMA FECHA", "CIERRA EN"] + ps.COLS_SEG + ["SERIE"]
    datos = ed[cols_ed].copy()
    datos["FECHA CONTACTO"] = pd.to_datetime(datos["FECHA CONTACTO"], errors="coerce")
    editado = st.data_editor(
        datos, hide_index=True, width="stretch", key="pol_editor",
        disabled=["ESTATUS", "CLIENTE", "TELÉFONO", "PRÓXIMA FECHA", "CIERRA EN", "SERIE"],
        column_config={**CONF,
                       "CONTACTADO": st.column_config.SelectboxColumn("CONTACTADO", options=["Sí", "No"]),
                       "FECHA CONTACTO": st.column_config.DateColumn("FECHA CONTACTO", format="DD/MM/YYYY"),
                       "RESULTADO": st.column_config.SelectboxColumn("RESULTADO", options=ps.RESULTADOS, width="medium"),
                       "NOTAS": st.column_config.TextColumn("NOTAS", width="large")})
    if st.button("Guardar y actualizar estatus", icon=":material/save:", type="primary",
                 help="Guarda lo capturado (ya no tienes que volver a subir el Excel) y actualiza indicadores."):
        st.session_state["pol_base"] = con_seguimiento(st.session_state["pol_base"], editado)
        st.session_state["pol_excel"] = ps.aplicar_seguimiento(st.session_state["pol_excel"],
                                                               st.session_state["pol_base"])
        st.session_state.pop("pol_editor", None)
        guardar_actual()
        st.rerun()
    res = df[df["RESULTADO"].astype(str).str.strip() != ""]
    if not res.empty:
        st.bar_chart(res["RESULTADO"].value_counts().rename("Clientes"), horizontal=True, height=200,
                     color="#1D4A86")

# ----------------------------------------------------------------------------- descargas
st.divider()
d1, d2, _ = st.columns([1, 1, 2])
excel = ps.aplicar_seguimiento(st.session_state["pol_excel"], con_seguimiento(st.session_state["pol_base"], editado))
d1.download_button("Excel con seguimiento", excel, file_name=f"Polizas_extraidas_{hoy:%Y%m%d}.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch",
                   icon=":material/table_view:", type="primary")
mes_pdf, titulo = st.session_state.get("pol_pdf_mes", (mes_sig, f"{MESES[hoy.month - 1]} {hoy.year}"))
d2.download_button("PDF para contactar", ps.pdf(df, mes_pdf, titulo, hoy),
                   file_name=f"Polizas_contactar_{hoy:%Y%m%d}.pdf", mime="application/pdf", width="stretch",
                   icon=":material/picture_as_pdf:")
st.caption("El PDF trae a quién contactar ya y las oportunidades del mes elegido en «Por mes».")
