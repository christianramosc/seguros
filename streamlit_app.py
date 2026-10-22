# -*- coding: utf-8 -*-
"""
App MG Colima · Autoexpress Inbursa.

Pestañas (arriba):
  · Pólizas       → seguimiento de pólizas de seguro (pag_polizas.py) · desactivada por ahora
  · Mejor oferta  → compara las ofertas del boletín de MG Financial Services para un auto (pag_oferta.py)
"""
import os
import time

# Streamlit Cloud corre en UTC: usar la hora de México para que «hoy» no cambie a las 6 pm
os.environ["TZ"] = "America/Mexico_City"
if hasattr(time, "tzset"):
    time.tzset()

import streamlit as st  # noqa: E402

import ui  # noqa: E402

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
]
st.navigation(PAGINAS, position="top" if len(PAGINAS) > 1 else "hidden").run()
