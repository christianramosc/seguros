# -*- coding: utf-8 -*-
"""
App MG Colima · Autoexpress Inbursa.

Pestañas (arriba):
  · Pólizas       → seguimiento de pólizas de seguro (pag_polizas.py) · desactivada por ahora
  · Mejor oferta  → compara las ofertas del boletín de MG Financial Services para un auto (pag_oferta.py)
  · Oferta comercial → sube el boletín nuevo (PDF): bonos, tasas y mínimos se actualizan en toda la app
                       (pag_boletin.py; se guarda con oferta_guardada.py)
"""
import importlib
import os
import sys
import time

# Streamlit Cloud corre en UTC: usar la hora de México para que «hoy» no cambie a las 6 pm
os.environ["TZ"] = "America/Mexico_City"
if hasattr(time, "tzset"):
    time.tzset()

import streamlit as st  # noqa: E402

import ui  # noqa: E402


def al_dia(nombre):
    """Streamlit Cloud conserva los módulos importados entre despliegues: recarga el módulo si su archivo cambió (o
    si todavía no se había revisado en este proceso), para no usar código de la versión anterior."""
    mod = sys.modules.get(nombre)
    if mod is None or not getattr(mod, "__file__", None):
        return
    t = os.path.getmtime(mod.__file__)
    if getattr(mod, "_mtime", None) != t:
        mod = importlib.reload(mod)
        mod._mtime = t


for _m in ("ui", "hoja_google", "oferta_mg", "boletin_mg", "oferta_guardada"):
    al_dia(_m)

st.set_page_config(page_title="MG Colima", page_icon="🛡️", layout="wide")


def acceso_permitido():
    """Pide contraseña solo si existe APP_PASSWORD en los secrets."""
    try:
        clave = st.secrets.get("APP_PASSWORD", "")
    except Exception:
        clave = ""
    if not clave or st.session_state.get("acceso_ok"):
        return True
    st.title("MG Colima")
    intento = st.text_input("Contraseña", type="password")
    if intento:
        if intento == clave:
            st.session_state["acceso_ok"] = True
            st.rerun()
        st.error("Contraseña incorrecta.")
    return False


if not acceso_permitido():
    st.stop()

ui.estilos()

# «Pólizas» desactivada por ahora: para volver a mostrarla, descomenta su línea (y quita default= de la otra).
PAGINAS = [
    # st.Page("pag_polizas.py", title="Pólizas", icon=":material/shield:", default=True),
    st.Page("pag_oferta.py", title="Mejor oferta MG", icon=":material/directions_car:", url_path="oferta",
            default=True),
    st.Page("pag_boletin.py", title="Oferta comercial", icon=":material/upload_file:", url_path="boletin"),
]
st.navigation(PAGINAS, position="top" if len(PAGINAS) > 1 else "hidden").run()
