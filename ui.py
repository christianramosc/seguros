# -*- coding: utf-8 -*-
"""Estilos y piezas visuales compartidas por las páginas de la app."""
import html

import streamlit as st

AZUL, TEXTO, TEXTO_2 = "#12305C", "#1B2A41", "#5A6B82"
MESES_CORTOS = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def estilos():
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
