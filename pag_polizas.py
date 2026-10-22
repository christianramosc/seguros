# -*- coding: utf-8 -*-
"""
Página «Pólizas»: seguimiento de pólizas de seguro (MG Colima · Autoexpress Inbursa).

A quién llamar hoy, oportunidades por mes y registro del contacto. Se suben los PDF / ZIP de las pólizas (Crédito
Click, columna Impresión) y/o el Excel Polizas_extraidas.xlsx; los datos de clientes solo viven en la sesión (nunca se
guardan en el repo ni en el servidor). El seguimiento se descarga en el mismo Excel.

Reglas (días naturales antes de cada aniversario de la póliza):
  · póliza externa: ideal a más tardar 45 días antes; de 44 a 39 última oportunidad; a los 38 ya no
  · pago de contado: desde 30 días antes hasta el día anterior
  · llamar al menos 7 días antes del límite de externa
  · al terminar el crédito el auto es del cliente: puede contratar el seguro que quiera.
"""
import datetime as dt

import altair as alt
import pandas as pd
import streamlit as st

import almacen
import cotizaciones
import hoja_google
import seguimiento as ps
from ui import MESES_CORTOS, hero, tarjeta


MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
hoy = dt.date.today()
hero("Pólizas de seguro · MG Colima", "A quién llamar para póliza externa, pago de contado o fin de crédito.",
     f"Corte {hoy:%d/%m/%Y}")
hoja_google.panel()

# ----------------------------------------------------------------------------- carga
def guardar_actual():
    """Guarda el Excel con el seguimiento actual para la próxima vez que se abra la app."""
    ok, msg = almacen.guardar(st.session_state["pol_excel"])
    st.session_state["pol_guardado"] = (ok, msg, dt.datetime.now())
    copiar_al_sheet()


def copiar_al_sheet():
    """Copia para consulta en el Google Sheet (pestaña Polizas), con el estatus calculado hoy."""
    if hoja_google.configurado():
        with st.spinner("Copiando al Google Sheet…"):
            st.session_state["pol_sheet"] = hoja_google.publicar(ps.calcular(st.session_state["pol_base"],
                                                                            dt.date.today()))


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
        else:
            copiar_al_sheet()   # al abrir también: la pestaña Polizas queda con el estatus de hoy

with st.container(border=True):
    c1, c2, c3 = st.columns([3, 2, 2])
    pdfs = c1.file_uploader("Pólizas (PDF o ZIP)", type=["pdf", "zip"], accept_multiple_files=True, key="pol_pdfs",
                            help="Los PDF que se descargan de Crédito Click (columna Impresión). Puedes subir varios "
                                 "o un ZIP. Si solo vas a revisar el seguimiento, basta con el Excel.")
    xls = c2.file_uploader("Excel anterior (opcional)", type=["xlsx"], key="pol_xlsx",
                           help="Polizas_extraidas.xlsx: conserva lo que ya capturaste (Contactado, Resultado, Notas) "
                                "y, si también subes PDFs nuevos, los junta con los clientes que ya tenías.")
    cot = c3.file_uploader("Cotizaciones (opcional)", type=["xlsx"], key="pol_cot",
                           help="Excel de cotizaciones de póliza externa (Multicotizador Istra, hoja Comparativo, con "
                                "SERIE). Se guarda dentro del Excel de pólizas y el PDF agrega la comparativa.")
    hay_base = st.session_state.get("pol_excel") is not None
    if st.button("Cargar", type="primary", disabled=not (pdfs or xls or (cot and hay_base)), icon=":material/upload:"):
        with st.spinner("Leyendo pólizas…" if pdfs else "Leyendo el Excel…"):
            try:
                if pdfs or xls:
                    base, excel, errores = ps.cargar([(f.name, f.getvalue()) for f in pdfs or []],
                                                     xls.getvalue() if xls else None)
                    origen = f"{len(pdfs)} archivo(s) PDF/ZIP" if pdfs else xls.name
                else:                                    # solo cotizaciones: se agregan al Excel que ya está abierto
                    excel = ps.aplicar_seguimiento(st.session_state["pol_excel"], st.session_state["pol_base"])
                    errores, origen = st.session_state.get("pol_err", []), st.session_state.get("pol_origen", "")
                if cot:
                    if cotizaciones.leer(cot.getvalue()) is None:
                        raise ValueError("El Excel de cotizaciones no trae la hoja Comparativo con las columnas "
                                         "CLIENTE y SERIE.")
                    excel = cotizaciones.incrustar(excel, cot.getvalue())
                    base = ps.leer_contacto(excel)
                    origen += f" + cotizaciones ({cot.name})"
                st.session_state.update(pol_base=base, pol_excel=excel, pol_err=errores, pol_origen=origen)
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
    r1, r4, r2, r3 = st.columns(4)
    reglas = dict(
        externa=r1.number_input("Límite ideal póliza externa (días antes del aniversario)", 1, 120, ps.REGLAS["externa"]),
        cero=r4.number_input("Oportunidad 0 de externa (días antes)", 1, 120, ps.REGLAS["cero"],
                             help="Desde este día ya no se acepta la póliza externa. Entre el límite ideal y este día "
                                  "es la última oportunidad: cada día es menos probable."),
        contado=r2.number_input("Abre ventana de contado (días antes)", 1, 120, ps.REGLAS["contado"]),
        aviso=r3.number_input("Llamar N días antes del límite de externa", 0, 60, ps.REGLAS["aviso"]))
    st.caption("Póliza externa ideal hasta 45 días antes del aniversario; de 44 a 39 es la última oportunidad (cada día "
               "menos probable) y a los 38 ya no se acepta · contado desde 30 días antes "
               "hasta el día anterior · al terminar el crédito el auto es del cliente y puede contratar el seguro que "
               "quiera.")

df = ps.calcular(base, hoy, reglas)
proy = ps.proyeccion(base, hoy, 12, reglas)
n = lambda e: int((df["ESTATUS"] == e).sum())
contactados = df["CONTACTADO"].astype(str).str.lower().isin(["sí", "si"]).sum()
cierres = df["RESULTADO"].isin(ps.CIERRES).sum()

k = st.columns(5)
_pc = ps.para_contactar(df, hoy)
_ext = int(_pc["ESTATUS"].isin([ps.LLAMAR_EXT, ps.ULTIMA, ps.ADELANTAR]).sum())
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
               + ("" if almacen.permanente() else
                  " · se conserva mientras la app esté activa; para guardarlo siempre, configura Drive o el Google "
                  "Sheet (README)"))
if st.session_state.get("pol_sheet"):
    ok, msg = st.session_state["pol_sheet"]
    st.caption(f"{':material/table_chart:' if ok else ':material/warning:'} {msg}")

COLS_HOY = ["ESTATUS", "CLIENTE", "TELÉFONO", "NOTA TELÉFONO", "CIERRA EN", "PRÓXIMA FECHA", "OPORTUNIDAD", "LLAMAR DESDE",
            "ÚLTIMO DÍA EXTERNA", "OPORTUNIDAD 0 EXTERNA", "ABRE CONTADO", "ÚLTIMO DÍA CONTADO", "QUÉ HACER", "ASEGURADORA",
            "PRIMA ANUAL ACTUAL", "EXTERNA MÁS BARATA", "ASEGURADORA EXTERNA", "AHORRO EXTERNA", "NOTA COTIZACIÓN",
            "CORREO", "VEHÍCULO", "FOLIO CRÉDITO", "MUNICIPIO"]
CONF = {c: st.column_config.DateColumn(c, format="DD/MM/YYYY") for c in
        ["PRÓXIMA FECHA", "LLAMAR DESDE", "ÚLTIMO DÍA EXTERNA", "OPORTUNIDAD 0 EXTERNA", "ABRE CONTADO", "ÚLTIMO DÍA CONTADO", "FECHA",
         "FECHA CONTACTO", "FIN DEL CRÉDITO"]}
CONF["PRIMA ANUAL ACTUAL"] = st.column_config.NumberColumn("PRIMA ANUAL", format="dollar")
CONF["EXTERNA MÁS BARATA"] = st.column_config.NumberColumn("EXTERNA MÁS BARATA", format="dollar")
CONF["AHORRO EXTERNA"] = st.column_config.NumberColumn("AHORRO EXTERNA", format="dollar",
                                                       help="Prima anual actual menos la externa más barata")


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
    st.markdown(f"**Para contactar ya ({len(urg)})** · ordenados por estatus y por lo que vence primero. Incluye a los que les "
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
        ver(del_mes, ["LLAMAR DESDE", "FECHA", "TIPO", "OPORTUNIDAD", "CLIENTE", "TELÉFONO", "NOTA TELÉFONO", "CORREO", "ASEGURADORA",
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
    cols_ed = ["ESTATUS", "CLIENTE", "TELÉFONO", "NOTA TELÉFONO", "PRÓXIMA FECHA", "CIERRA EN"] + ps.COLS_SEG + ["SERIE"]
    datos = ed[cols_ed].copy()
    datos["FECHA CONTACTO"] = pd.to_datetime(datos["FECHA CONTACTO"], errors="coerce")
    editado = st.data_editor(
        datos, hide_index=True, width="stretch", key="pol_editor",
        disabled=["ESTATUS", "CLIENTE", "TELÉFONO", "NOTA TELÉFONO", "PRÓXIMA FECHA", "CIERRA EN", "SERIE"],
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
