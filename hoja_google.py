# -*- coding: utf-8 -*-
"""Copia de las pólizas en una pestaña de Google Sheets, para consultarla y usarla desde otras apps
(por ejemplo, reportessaleu).

Secrets (Streamlit Cloud → Settings → Secrets):
    POLIZAS_SHEET_URL = "https://docs.google.com/spreadsheets/d/…"   # opcional
    [gcp_service_account]                                            # el mismo JSON de la cuenta de servicio
Si no hay POLIZAS_SHEET_URL se usa SEGUIMIENTO_SHEET_URL (el Sheet de seguimiento de reportessaleu).
El Sheet debe estar compartido como Editor con el client_email de la cuenta de servicio.

El Excel completo también se guarda en la pestaña oculta RESPALDO (base64 en trozos), para que la app lo abra sola
aunque se reinicie, sin configurar Drive.

Cada vez que la app guarda el Excel, la pestaña PESTANA se reemplaza completa con una fila por crédito: los datos
del cliente, el teléfono y su nota, el seguimiento y el estatus calculado ese día. Las demás pestañas del Sheet no se
tocan.
"""
import base64
import datetime as dt

import pandas as pd
import streamlit as st

PESTANA = "Polizas"
COLUMNAS = ["ESTATUS", "QUÉ HACER", "CIERRA EN", "DÍAS QUE QUEDAN", "CLIENTE", "TELÉFONO", "NOTA TELÉFONO", "CORREO",
            "PRÓXIMA FECHA", "TIPO", "OPORTUNIDAD", "LLAMAR DESDE", "ÚLTIMO DÍA EXTERNA", "OPORTUNIDAD 0 EXTERNA",
            "ABRE CONTADO", "ÚLTIMO DÍA CONTADO", "CONTACTADO", "FECHA CONTACTO", "RESULTADO", "NOTAS", "ASEGURADORA",
            "PÓLIZA ACTUAL", "PRIMA ANUAL ACTUAL", "EXTERNA MÁS BARATA", "ASEGURADORA EXTERNA", "AHORRO EXTERNA",
            "NOTA COTIZACIÓN", "VEHÍCULO", "SERIE", "MOTOR", "RFC", "FOLIO CRÉDITO", "MUNICIPIO",
            "DIRECCIÓN", "CP", "PRIMERA OPORTUNIDAD", "FIN DEL CRÉDITO"]
RESPALDO = "_Polizas_excel"
TROZO = 45000                       # caracteres por celda (Google admite hasta 50 000)
TEXTO = {"TELÉFONO", "SERIE", "MOTOR", "RFC", "FOLIO CRÉDITO", "CP", "PÓLIZA ACTUAL"}   # que Google no los haga número


def _secret(nombre):
    try:
        return st.secrets.get(nombre)
    except Exception:
        return None


def url():
    return _secret("POLIZAS_SHEET_URL") or _secret("SEGUIMIENTO_SHEET_URL")


def configurado():
    return bool(url() and _secret("gcp_service_account"))


@st.cache_resource(show_spinner=False)
def _cliente():
    import gspread
    from gspread.http_client import BackOffHTTPClient
    return gspread.service_account_from_dict(dict(_secret("gcp_service_account")), http_client=BackOffHTTPClient)


@st.cache_data(ttl=600, show_spinner="Conectando con el Google Sheet…")
def _titulo(u):
    return _cliente().open_by_url(u).title


def panel(donde=st):
    """Como en reportessaleu: a qué Google Sheet se copian las pólizas (o por qué no se copian)."""
    if not configurado():
        donde.info("Sin Google Sheet: agrega SEGUIMIENTO_SHEET_URL (o POLIZAS_SHEET_URL) y [gcp_service_account] en "
                   "Settings → Secrets para copiar las pólizas a la pestaña Polizas.", icon=":material/cloud_off:")
        return
    try:
        titulo = _titulo(url())
    except Exception as e:
        donde.error(f"No se pudo abrir el Google Sheet: {e}. Compártelo como Editor con la cuenta de servicio.",
                    icon=":material/error:")
        return
    donde.success(f"Conectado a **{titulo}** · [abrir]({url()}) · pestaña {PESTANA}", icon=":material/cloud_done:")


def _celda(col, v):
    if v is None or (not isinstance(v, str) and pd.isna(v)):
        return ""
    if isinstance(v, (dt.date, dt.datetime, pd.Timestamp)):
        return pd.Timestamp(v).strftime("%Y-%m-%d")      # ISO: Google lo toma como fecha en cualquier idioma
    if col in TEXTO:
        s = str(v).strip().removesuffix(".0")
        return "'" + s if s else ""
    if isinstance(v, float):
        return int(v) if v.is_integer() else round(v, 2)
    if hasattr(v, "item"):                                # números de numpy
        return v.item()
    return v


def publicar(df):
    """df: resultado de seguimiento.calcular(). Reemplaza la pestaña PESTANA. Devuelve (ok, mensaje)."""
    if not configurado():
        return False, "Google Sheet sin configurar"
    try:
        import gspread
        from gspread.utils import ValueInputOption
        libro = _cliente().open_by_url(url())
        cols = [c for c in COLUMNAS if c in df.columns]
        ahora = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        tabla = [cols + ["ACTUALIZADO"]] + [[_celda(c, r[c]) for c in cols] + [ahora]
                                           for r in df[cols].to_dict("records")]
        try:
            ws = libro.worksheet(PESTANA)
            ws.clear()
            if ws.row_count < len(tabla) or ws.col_count < len(tabla[0]):
                ws.resize(rows=max(ws.row_count, len(tabla) + 20), cols=max(ws.col_count, len(tabla[0])))
        except gspread.WorksheetNotFound:
            ws = libro.add_worksheet(PESTANA, rows=len(tabla) + 20, cols=len(tabla[0]))
        ws.update(tabla, "A1", value_input_option=ValueInputOption.user_entered)
        ws.freeze(rows=1)
        return True, f"Copiado al Google Sheet «{libro.title}», pestaña {PESTANA}"
    except Exception as e:
        return False, f"No se pudo copiar al Google Sheet ({e})"


def guardar_excel(datos):
    """Guarda el Excel completo en la pestaña oculta RESPALDO. Devuelve (ok, mensaje)."""
    if not configurado():
        return False, "Google Sheet sin configurar"
    try:
        import gspread
        from gspread.utils import ValueInputOption
        texto = base64.b64encode(datos).decode()
        filas = [[texto[i:i + TROZO]] for i in range(0, len(texto), TROZO)]
        libro = _cliente().open_by_url(url())
        try:
            ws = libro.worksheet(RESPALDO)
            ws.clear()
            ws.resize(rows=len(filas), cols=1)
        except gspread.WorksheetNotFound:
            ws = libro.add_worksheet(RESPALDO, rows=len(filas), cols=1)
            ws.hide()
        ws.update(filas, "A1", value_input_option=ValueInputOption.raw)   # raw: que Google no lo tome como fórmula
        return True, "Guardado en el Google Sheet"
    except Exception as e:
        return False, f"No se pudo guardar en el Google Sheet ({e})"


def leer_excel():
    """Bytes del Excel guardado en la pestaña RESPALDO, o None."""
    if not configurado():
        return None
    try:
        datos = base64.b64decode("".join(_cliente().open_by_url(url()).worksheet(RESPALDO).col_values(1)))
        return datos if datos[:2] == b"PK" else None    # un .xlsx es un ZIP
    except Exception:
        return None
