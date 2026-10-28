# -*- coding: utf-8 -*-
"""Estilos y piezas visuales compartidas por las páginas de la app.

Tema oscuro estilo shadcn/ui (paleta «zinc»): los colores base van en .streamlit/config.toml; aquí van las piezas
que Streamlit no trae (encabezado, tarjetas de cifra, insignias, títulos de sección).
"""
import html

import streamlit as st

# paleta zinc de shadcn/ui
FONDO, TARJETA, BORDE = "#09090B", "#18181B", "#27272A"
TEXTO, TEXTO_2, TEXTO_3 = "#FAFAFA", "#A1A1AA", "#71717A"
VERDE_T, ROJO = "#4ADE80", "#C8102E"
MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# resaltes para tablas (Styler) que se leen bien sobre fondo oscuro
RESALTE = "background-color: rgba(34, 197, 94, .14); color: #4ADE80; font-weight: 600"
APAGADO = f"color: {TEXTO_3}"


def esc(t):
    """Escapa HTML y el «$» (en markdown dos «$» abren una fórmula)."""
    return html.escape(str(t)).replace("$", "&#36;")


def estilos():
    st.markdown(f"""
<style>
.block-container {{ padding-top: 3.6rem; padding-bottom: 3rem; max-width: 1280px; }}
/* encabezado */
.hero {{ display: flex; justify-content: space-between; align-items: center; gap: 16px; flex-wrap: wrap;
        padding: 0 0 18px; margin-bottom: 22px; border-bottom: 1px solid {BORDE}; }}
.hero .marca {{ display: flex; align-items: center; gap: 14px; }}
.hero .logo {{ width: 40px; height: 40px; border-radius: 10px; background: {ROJO}; color: #fff; display: grid;
              place-items: center; font-weight: 700; font-size: .95rem; letter-spacing: .02em; }}
.hero h1 {{ font-size: 1.55rem !important; font-weight: 700; margin: 0 !important; padding: 0 !important;
           color: {TEXTO}; letter-spacing: -.02em; line-height: 1.15; }}
.hero p {{ margin: 3px 0 0 !important; color: {TEXTO_2}; font-size: .9rem; }}
/* insignias */
.badge {{ display: inline-flex; align-items: center; gap: 6px; border: 1px solid {BORDE}; border-radius: 999px;
         padding: 3px 11px; font-size: .78rem; font-weight: 500; color: {TEXTO_2}; background: {TARJETA};
         white-space: nowrap; }}
.badge.ok {{ color: {VERDE_T}; border-color: rgba(74, 222, 128, .35); background: rgba(34, 197, 94, .1); }}
.badges {{ display: flex; gap: 6px; flex-wrap: wrap; margin: 2px 0 4px; }}
/* títulos de sección */
.seccion {{ display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap;
           margin: 26px 0 10px; }}
.seccion .titulo {{ font-size: 1.15rem; font-weight: 600; color: {TEXTO}; letter-spacing: -.01em; }}
.seccion span {{ color: {TEXTO_2}; font-size: .82rem; }}
/* tarjetas de cifra */
.kt {{ color: {TEXTO_2}; font-size: .8rem; font-weight: 500; margin: 0 0 6px; display: flex; align-items: center;
      gap: 6px; }}
.kv {{ font-size: 1.7rem !important; font-weight: 700 !important; line-height: 1.1 !important; margin: 0 !important;
      letter-spacing: -.02em; font-variant-numeric: tabular-nums; }}
.ks {{ font-size: .76rem !important; color: {TEXTO_3}; margin: 6px 0 0; white-space: nowrap; overflow: hidden;
      text-overflow: ellipsis; }}
/* estados vacíos y notas */
.vacio {{ border: 1px dashed {BORDE}; border-radius: 12px; padding: 40px; text-align: center; color: {TEXTO_2};
         background: {TARJETA}; }}
.vacio b {{ color: {TEXTO}; font-size: 1.05rem; }}
.nota {{ color: {TEXTO_2}; font-size: .8rem; margin: 2px 0; }}
/* pestañas y botones más sobrios */
button[data-baseweb="tab"] {{ font-weight: 500; }}
[data-testid="stDownloadButton"] button {{ font-weight: 600; }}
button[kind="primary"], button[data-testid="stBaseButton-primary"] {{ color: {FONDO} !important; }}
button[kind="primary"] *, button[data-testid="stBaseButton-primary"] * {{ color: {FONDO} !important; }}
</style>
""", unsafe_allow_html=True)


def hero(titulo, subtitulo, derecha=""):
    """Encabezado de página: logo, título, subtítulo e insignia a la derecha."""
    st.markdown(f"""<div class="hero"><div class="marca"><div class="logo">MG</div><div>
<h1>{esc(titulo)}</h1><p>{esc(subtitulo)}</p></div></div>
{f'<span class="badge">{esc(derecha)}</span>' if derecha else ''}</div>""", unsafe_allow_html=True)


def seccion(titulo, detalle=""):
    """Título de sección con un detalle en gris a la derecha."""
    st.markdown(f'<div class="seccion"><div class="titulo">{esc(titulo)}</div><span>{esc(detalle)}</span></div>',
                unsafe_allow_html=True)


def insignias(textos, donde=st, ok=()):
    """Fila de insignias (las de `ok` en verde)."""
    donde.markdown('<div class="badges">' + "".join(
        f'<span class="badge{" ok" if t in ok else ""}">{esc(t)}</span>' for t in textos if t) + "</div>",
        unsafe_allow_html=True)


def nota(texto, donde=st):
    donde.markdown(f'<div class="nota">{esc(texto)}</div>', unsafe_allow_html=True)


def tarjeta(donde, icono, titulo, valor, detalle="", color=None):
    caja = donde.container(border=True)
    caja.markdown(f'<div class="kt">{esc(titulo)}</div>'
                  f'<div class="kv" style="color:{color or TEXTO}">{esc(str(valor))}</div>'
                  f'<div class="ks" title="{esc(detalle)}">{esc(detalle) or "&nbsp;"}</div>',
                  unsafe_allow_html=True)
