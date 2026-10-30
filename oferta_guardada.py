# -*- coding: utf-8 -*-
"""Guarda la oferta comercial que se sube en la página «Oferta comercial», para que la app la siga usando aunque
se reinicie.

Dónde se guarda, en este orden:
1. El Google Sheet de hoja_google (permanente), en la pestaña oculta «_Oferta_MG»: columna A = la oferta en uso
   (JSON en base64, en trozos), columna B = la anterior (para deshacer). Usa los mismos secrets que las pólizas:
   [gcp_service_account] y SEGUIMIENTO_SHEET_URL (o POLIZAS_SHEET_URL).
2. Una copia en el servidor de Streamlit (~/.mg_oferta): se borra si la app se reinicia o se duerme.
Sin nada guardado se usa la oferta incluida en la app (oferta_base.json).
"""
import base64
import datetime as dt
import importlib
import json
import os
import sys

import streamlit as st

import hoja_google

PESTANA = "_Oferta_MG"
TROZO = 45000                      # caracteres por celda (Google admite hasta 50 000)
CARPETA = os.path.join(os.path.expanduser("~"), ".mg_oferta")


def _fresco(nombre):
    """Importa el módulo y lo recarga si su archivo cambió (Streamlit Cloud conserva los módulos entre despliegues)."""
    previo = nombre in sys.modules
    mod = importlib.import_module(nombre)
    mtime = os.path.getmtime(mod.__file__)
    if previo and getattr(mod, "_mtime", None) != mtime:
        mod = importlib.reload(mod)
    mod._mtime = mtime
    return mod


def permanente():
    return hoja_google.configurado()


# ----------------------------------------------------------------------------- lectura / escritura
def _archivo(cual):
    return os.path.join(CARPETA, f"{cual}.json")


def _leer_local(cual):
    try:
        with open(_archivo(cual), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _escribir_local(cual, oferta):
    os.makedirs(CARPETA, exist_ok=True)
    if oferta is None:
        if os.path.exists(_archivo(cual)):
            os.remove(_archivo(cual))
        return
    with open(_archivo(cual), "w", encoding="utf-8") as f:
        json.dump(oferta, f, ensure_ascii=False)


def _hoja():
    import gspread
    libro = hoja_google._cliente().open_by_url(hoja_google.url())
    try:
        return libro.worksheet(PESTANA), libro.title
    except gspread.WorksheetNotFound:
        ws = libro.add_worksheet(PESTANA, rows=2, cols=2)
        ws.hide()
        return ws, libro.title


def _leer_hoja():
    ws, _ = _hoja()
    col = lambda i: "".join(ws.col_values(i))
    leer_json = lambda t: json.loads(base64.b64decode(t).decode("utf-8")) if t else None
    return leer_json(col(1)), leer_json(col(2))


def _escribir_hoja(actual, anterior):
    from gspread.utils import ValueInputOption
    ws, titulo = _hoja()
    # JSON en base64 (sin espacios ni acentos que Google pudiera tocar), en trozos de TROZO caracteres
    trozos = lambda o: [] if o is None else (lambda t: [t[i:i + TROZO] for i in range(0, len(t), TROZO)])(
        base64.b64encode(json.dumps(o, ensure_ascii=False).encode("utf-8")).decode())
    a, b = trozos(actual), trozos(anterior)
    n = max(len(a), len(b), 1)
    filas = [[a[i] if i < len(a) else "", b[i] if i < len(b) else ""] for i in range(n)]
    ws.clear()
    ws.resize(rows=n, cols=2)
    ws.update(filas, "A1", value_input_option=ValueInputOption.raw)   # raw: que Google no lo tome como fórmula
    return titulo


@st.cache_resource(show_spinner=False)
def _memoria():
    """Lo guardado, leído una sola vez por proceso (compartido por todas las sesiones)."""
    return dict(cargado=False, actual=None, anterior=None, origen=None, error=None)


def leer(forzar=False):
    """{actual, anterior, origen, error}: actual/anterior son dicts de oferta o None (= la incluida en la app)."""
    m = _memoria()
    if m["cargado"] and not forzar:
        return m
    actual = anterior = origen = error = None
    if hoja_google.configurado():
        try:
            actual, anterior = _leer_hoja()
            origen = "Google Sheet" if actual else None
        except Exception as e:
            error = f"No se pudo leer el Google Sheet ({e})"
    if actual is None and anterior is None:
        actual, anterior = _leer_local("actual"), _leer_local("anterior")
        origen = "servidor" if actual else None
    m.update(cargado=True, actual=actual, anterior=anterior, origen=origen, error=error)
    return m


def _guardar(actual, anterior):
    """Escribe actual/anterior en el servidor y en el Sheet. Devuelve (permanente, mensaje)."""
    m = leer()
    _escribir_local("actual", actual)
    _escribir_local("anterior", anterior)
    m.update(actual=actual, anterior=anterior, origen="servidor" if actual else None)
    if not hoja_google.configurado():
        return False, ("Quedó en el servidor de la app: si Streamlit la reinicia vuelve la oferta incluida en la app "
                       "(configura el Google Sheet para que sea permanente).")
    try:
        titulo = _escribir_hoja(actual, anterior)
        m.update(origen="Google Sheet" if actual else None)
        return True, f"Quedó guardada en el Google Sheet «{titulo}» (pestaña oculta {PESTANA})."
    except Exception as e:
        return False, f"No se pudo guardar en el Google Sheet ({e}); quedó solo en el servidor de la app."


def guardar(oferta):
    """Usa `oferta` desde ahora; la que estaba en uso pasa a «anterior»."""
    m = leer()
    oferta = dict(oferta, guardada=dt.datetime.now().strftime("%d/%m/%Y %H:%M"))
    return _guardar(oferta, m["actual"])


def deshacer():
    """Vuelve a la oferta anterior (o a la incluida en la app si no había otra)."""
    m = leer()
    return _guardar(m["anterior"], m["actual"])


def usar_incluida():
    """Deja de usar la oferta subida y vuelve a la incluida en la app (la subida queda como «anterior»)."""
    m = leer()
    return _guardar(None, m["actual"])


# ----------------------------------------------------------------------------- motor
def motor():
    """oferta_mg al día y con la oferta guardada aplicada (la llaman todas las páginas al inicio)."""
    om = _fresco("oferta_mg")
    m = leer()
    oferta = m["actual"] or om.oferta_base()
    if getattr(om, "OFERTA_ID", None) != om.huella(oferta):
        om.aplicar(oferta)
    return om


def lector():
    return _fresco("boletin_mg")
