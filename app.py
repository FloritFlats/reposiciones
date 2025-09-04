# app.py
# -*- coding: utf-8 -*-
"""
APP: Pedidos de compra según inventarios (Odoo + Mín/Máx)
Autor: ChatGPT (para Florit Flats)


MVP (con Totales por producto)
------------------------------
- Usa por defecto el Excel oficial de mínimos y máximos (EXCEL FINAL INVENTARIOS.xlsx).
- Subes únicamente el extracto de inventario desde Odoo (Ubicación, Producto, Cantidad).
- Calcula cantidades **hasta el Máximo** por almacén y **muestra el RESUMEN TOTAL por producto** (suma de todos los almacenes).
- Descargas: Detalle por almacén y Resumen por producto.


Opcional
--------
- Matriz de uso (Alojamiento, Producto, Usar 1/0) para excluir celdas específicas (p.ej. cafés por alojamiento).
*Si ya has puesto 0 en tu Excel de Mín/Máx donde no aplica, no necesitas subir matriz.*


Ejecutar
--------
streamlit run app.py
Requisitos: streamlit, pandas, numpy, openpyxl, xlsxwriter
"""


import io
import re
from pathlib import Path
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Compras Odoo + Mín/Máx", layout="wide")


# Archivo de Mín/Máx por defecto (junto a app.py)
DEFAULT_MINMAX_PATH = Path(__file__).parent / "EXCEL FINAL INVENTARIOS.xlsx"


# --------------------------
# Utilidades
# --------------------------


def _norm_text(x):
if x is None:
return None
x = str(x).strip()
x = re.sub(r"\s*\(\d+\)$", "", x)
x = re.sub(r"\s+", " ", x)
return x


def _norm_key(x):
x = _norm_text(x)
return x.upper() if x else None


# --------------------------
# Lectura Mín/Máx → agregado por Almacén–Producto
# --------------------------


def parse_minmax(path: str | Path) -> pd.DataFrame:
try:
xls = pd.ExcelFile(path, engine="openpyxl")
except ImportError:
st.error("Falta **openpyxl**. Añádelo a requirements.txt.")
raise
except FileNotFoundError:
st.error(f"No se encontró el archivo en: {path}")
raise


df = pd.read_excel(path, sheet_name=xls.sheet_names[0])
df = df.rename(columns={c: str(c).strip() for c in df.columns})
