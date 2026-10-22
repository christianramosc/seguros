"""Guarda el último Excel cargado para no tener que subirlo cada vez.

Tres lugares, en este orden:
1. Google Drive (permanente), si en secrets están [gcp_service_account] y POLIZAS_DRIVE_FILE_ID.
   El archivo es tuyo en tu Drive y lo compartes como Editor con el client_email de la cuenta de servicio.
2. El Google Sheet de hoja_google (permanente), en una pestaña oculta, si está configurado.
3. Una copia en el servidor de Streamlit (se borra si la app se reinicia o se duerme por inactividad).
"""
import os

import streamlit as st

import hoja_google

LOCAL = os.path.join(os.path.expanduser("~"), ".polizas_mg", "ultimo.xlsx")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _drive():
    try:
        cuenta = st.secrets.get("gcp_service_account")
        archivo = st.secrets.get("POLIZAS_DRIVE_FILE_ID")
    except Exception:
        return None, None
    if not cuenta or not archivo:
        return None, None
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    cred = service_account.Credentials.from_service_account_info(
        dict(cuenta), scopes=["https://www.googleapis.com/auth/drive"])
    return AuthorizedSession(cred), str(archivo).strip()


def drive_configurado():
    try:
        return bool(st.secrets.get("gcp_service_account") and st.secrets.get("POLIZAS_DRIVE_FILE_ID"))
    except Exception:
        return False


def permanente():
    """True si el Excel se guarda en algún lugar que sobrevive a reinicios de la app."""
    return drive_configurado() or hoja_google.configurado()


def leer():
    """Devuelve (bytes, origen) del último Excel guardado, o (None, None)."""
    if drive_configurado():
        try:
            s, fid = _drive()
            r = s.get(f"https://www.googleapis.com/drive/v3/files/{fid}",
                      params={"alt": "media", "supportsAllDrives": "true"}, timeout=60)
            if r.ok and r.content[:2] == b"PK":  # un .xlsx es un ZIP
                return r.content, "Google Drive"
        except Exception:
            pass
    datos = hoja_google.leer_excel()
    if datos:
        return datos, "Google Sheet"
    if os.path.exists(LOCAL):
        with open(LOCAL, "rb") as f:
            return f.read(), "copia guardada en la app"
    return None, None


def guardar(datos):
    """Guarda el Excel. Devuelve (ok_drive, mensaje)."""
    os.makedirs(os.path.dirname(LOCAL), exist_ok=True)
    with open(LOCAL, "wb") as f:
        f.write(datos)
    if not drive_configurado():
        if hoja_google.configurado():
            return hoja_google.guardar_excel(datos)
        return False, "Guardado en la app (sin Drive ni Google Sheet configurados)"
    try:
        s, fid = _drive()
        r = s.patch(f"https://www.googleapis.com/upload/drive/v3/files/{fid}",
                    params={"uploadType": "media", "supportsAllDrives": "true"},
                    data=datos, headers={"Content-Type": XLSX}, timeout=120)
        if r.ok:
            return True, "Guardado en Google Drive"
        return False, f"No se pudo guardar en Drive ({r.status_code}); quedó la copia en la app"
    except Exception as e:
        return False, f"No se pudo guardar en Drive ({e}); quedó la copia en la app"
