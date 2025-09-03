# app.py
# -*- coding: utf-8 -*-
"""
APP: Pedidos de compra según inventarios (Odoo + Mín/Máx)
Autor: ChatGPT (para Florit Flats)

Funcionalidad MVP
-----------------
- Subes dos archivos:
  1) Excel de mínimos y máximos por Alojamiento/Almacén (el que nos pasaste).
  2) Extracto de inventario desde Odoo (Ubicación, Producto, Cantidad).
- La app transforma el Excel de Mín/Máx a formato largo y agrega por Almacén/Producto.
- Cruza con el stock actual de Odoo y calcula:
  * Falta_hasta_Min = max(Min - Stock, 0)
  * Compra_hasta_Max = max(Max - Stock, 0)   ← criterio por defecto
- Descarga de Excel con las cantidades sugeridas para llegar al Máximo.

Roadmap (siguientes iteraciones)
---------------------------------
- Tabla de proveedores (MOQ, múltiplos, coste, lead time) y ajuste de cantidades.
- Pronóstico de demanda por reservas y tasa de ocupación (consumo por estancia, cobertura, safety stock).
- Vistas por proveedor y por almacén, y generación de pedidos automáticos.

Ejecutar
--------
streamlit run app.py
"""

import io
import re
import math
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Compras Odoo + Mín/Máx", layout="wide")

# -------------------------------------------
# Utilidades de normalización
# -------------------------------------------

def _norm_text(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    x = str(x).strip()
    # Quita sufijos tipo "NAME (17)"
    x = re.sub(r"\s*\(\d+\)$", "", x)
    # Espacios de más
    x = re.sub(r"\s+", " ", x)
    return x


def _norm_key(x: Optional[str]) -> Optional[str]:
    x = _norm_text(x)
    if x is None:
        return None
    return x.upper()


# -------------------------------------------
# Lectura Mín/Máx → largo (Almacen, Producto, Min, Max)
# -------------------------------------------

@st.cache_data(show_spinner=False)
def parse_minmax(file) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(file, sheet_name=sheet)

    # Normaliza encabezados
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    # Detecta primeras 3 columnas (Alojamiento, Almacén, Capacidad)
    # Usamos heurística por nombre y posición
    col_aloj = next((c for c in df.columns if str(c).lower().startswith("aloj")), df.columns[0])
    col_alm  = next((c for c in df.columns if str(c).lower().startswith("almac")), df.columns[1])
    col_cap  = next((c for c in df.columns if "capacidad" in str(c).lower()), df.columns[2])

    # Resto de columnas son pares (Min, Max) consecutivos: [D,E], [F,G], ...
    rest = [c for c in df.columns if c not in (col_aloj, col_alm, col_cap)]
    if len(rest) % 2 != 0:
        st.warning("El número de columnas de productos no es par. Verifica que cada 'Min' tenga su 'Max'.")

    long_frames = []
    for i in range(0, len(rest) - 1, 2):
        min_col, max_col = rest[i], rest[i+1]
        # Nombre base del producto (quitamos sufijos .1/.2/...)
        prod_name = re.sub(r"\.\d+$", "", str(min_col)).strip()
        tmp = df[[col_alm, min_col, max_col]].copy()
        tmp.columns = ["Almacen", "Min", "Max"]
        tmp["Producto"] = prod_name
        long_frames.append(tmp)

    if not long_frames:
        raise ValueError("No se detectaron columnas de productos. Revisa el Excel de Mín/Máx.")

    long_df = pd.concat(long_frames, ignore_index=True)

    # Limpieza y tipos
    long_df["Almacen"] = long_df["Almacen"].map(_norm_text)
    long_df["Producto"] = long_df["Producto"].map(_norm_text)

    for c in ["Min", "Max"]:
        long_df[c] = pd.to_numeric(long_df[c], errors="coerce").fillna(0)

    # Agregar por Almacén/Producto (suma entre alojamientos del mismo almacén)
    mm_agg = (long_df
              .groupby(["Almacen", "Producto"], as_index=False)
              .agg({"Min": "sum", "Max": "sum"}))

    # Llaves normalizadas para el join
    mm_agg["K_Almacen"] = mm_agg["Almacen"].map(_norm_key)
    mm_agg["K_Producto"] = mm_agg["Producto"].map(_norm_key)

    return mm_agg


# -------------------------------------------
# Lectura extracto Odoo → Stock por (Almacen, Producto)
# -------------------------------------------

@st.cache_data(show_spinner=False)
def parse_odoo(file) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(file, sheet_name=sheet)
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    # Identifica columnas por heurística
    col_loc = next((c for c in df.columns if "ubicación" in c.lower() or "ubicacion" in c.lower() or c.lower()=="ubicacion"), None)
    col_prod = next((c for c in df.columns if "producto" in c.lower()), None)
    col_qty = next((c for c in df.columns if c.lower() in ("cantidad", "quantity")), None)

    if not (col_loc and col_prod and col_qty):
        raise ValueError("No se encontraron columnas 'Ubicación', 'Producto' y 'Cantidad' en el extracto de Odoo.")

    df = df[[col_loc, col_prod, col_qty]].copy()
    df.columns = ["Almacen", "Producto", "Stock"]

    df["Almacen"] = df["Almacen"].map(_norm_text)
    df["Producto"] = df["Producto"].map(_norm_text)
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0)

    # Agregar para consolidar duplicados
    stock = (df
             .dropna(subset=["Almacen", "Producto"])
             .groupby(["Almacen", "Producto"], as_index=False)
             .agg({"Stock": "sum"}))

    stock["K_Almacen"] = stock["Almacen"].map(_norm_key)
    stock["K_Producto"] = stock["Producto"].map(_norm_key)

    return stock


# -------------------------------------------
# Cálculo de necesidades
# -------------------------------------------

def calcular_necesidades(mm_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    df = mm_agg.merge(stock, on=["K_Almacen", "K_Producto"], how="left", suffixes=("_MM","_OD"))

    # Rellena claves y muestra nombres "bonitos"
    df["Almacen"] = df["Almacen_MM"].fillna(df["Almacen_OD"]) \
        if "Almacen_OD" in df.columns else df["Almacen_MM"]
    df["Producto"] = df["Producto_MM"].fillna(df["Producto_OD"]) \
        if "Producto_OD" in df.columns else df["Producto_MM"]

    # Valores numéricos
    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df["Max"] = pd.to_numeric(df["Max"], errors="coerce").fillna(0)
    df["Stock"] = pd.to_numeric(df.get("Stock", 0), errors="coerce").fillna(0)

    # Cálculos
    df["Falta_hasta_Min"] = (df["Min"] - df["Stock"]).clip(lower=0)
    df["Compra_hasta_Max"] = (df["Max"] - df["Stock"]).clip(lower=0)

    df["Por_debajo_de_Min"] = (df["Stock"] < df["Min"]).astype(int)
    df["En_objetivo"] = ((df["Stock"] >= df["Min"]) & (df["Stock"] <= df["Max"]).astype(bool)).astype(int)
    df["Sobre_Max"] = (df["Stock"] > df["Max"]).astype(int)

    cols = [
        "Almacen","Producto","Min","Max","Stock",
        "Falta_hasta_Min","Compra_hasta_Max",
        "Por_debajo_de_Min","En_objetivo","Sobre_Max"
    ]
    out = df[cols].sort_values(["Almacen","Producto"]).reset_index(drop=True)
    return out


# -------------------------------------------
# UI
# -------------------------------------------

st.title("🛒 APP de Compras – Odoo + Mín/Máx (MVP)")
with st.expander("Cómo funciona", expanded=False):
    st.markdown(
        """
        1. Sube el **Excel de Mín/Máx** por Alojamiento/Almacén (tu hoja con columnas A= Alojamiento, B= Almacén, C= Capacidad, y luego pares Min/Max).
        2. Sube el **extracto de Odoo** (debe contener *Ubicación*, *Producto*, *Cantidad*).
        3. La app calcula **Compra_hasta_Max** = Max − Stock (si es > 0).
        4. Descarga el Excel con los resultados.
        """
    )

col1, col2 = st.columns(2)
with col1:
    mm_file = st.file_uploader("Excel de Mín/Máx (por Alojamiento/Almacén)", type=["xlsx","xls"])
with col2:
    odoo_file = st.file_uploader("Extracto de Odoo (Ubicación, Producto, Cantidad)", type=["xlsx","xls","csv"]) 

mm_agg = stock = None

if mm_file is not None:
    try:
        mm_agg = parse_minmax(mm_file)
        st.success(f"Mín/Máx cargado: {len(mm_agg)} combinaciones Almacén–Producto")
        with st.expander("Vista rápida Mín/Máx agregado", expanded=False):
            st.dataframe(mm_agg.head(200), use_container_width=True)
    except Exception as e:
        st.error(f"Error leyendo Mín/Máx: {e}")

if odoo_file is not None:
    try:
        stock = parse_odoo(odoo_file)
        st.success(f"Extracto Odoo cargado: {len(stock)} filas de stock por Almacén–Producto")
        with st.expander("Vista rápida Stock Odoo", expanded=False):
            st.dataframe(stock.head(200), use_container_width=True)
    except Exception as e:
        st.error(f"Error leyendo Odoo: {e}")

if (mm_agg is not None) and (stock is not None):
    st.markdown("---")
    st.subheader("Resultado – Sugerencia de compra hasta Máximo")

    resultado = calcular_necesidades(mm_agg, stock)

    # Filtros rápidos
    c1, c2 = st.columns(2)
    with c1:
        almacenes = ["(Todos)"] + sorted(resultado["Almacen"].dropna().unique().tolist())
        f_alm = st.selectbox("Filtrar por Almacén", almacenes)
    with c2:
        f_txt = st.text_input("Buscar producto contiene…", "")

    res_view = resultado.copy()
    if f_alm != "(Todos)":
        res_view = res_view[res_view["Almacen"] == f_alm]
    if f_txt:
        res_view = res_view[res_view["Producto"].str.contains(f_txt, case=False, na=False)]

    st.dataframe(res_view, use_container_width=True)

    # Resumen numérico
    total_compra = int(res_view["Compra_hasta_Max"].sum()) if not res_view.empty else 0
    total_items = res_view.shape[0]
    st.info(f"Total de unidades sugeridas (hasta Máx) en la vista: **{total_compra:,}** · Filas: **{total_items}**")

    # Descarga en Excel/CSV
    def to_excel_bytes(df: pd.DataFrame) -> bytes:
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="CompraHastaMax")
        bio.seek(0)
        return bio.read()

    colx, coly = st.columns(2)
    with colx:
        st.download_button(
            label="⬇️ Descargar Excel (todo)",
            data=to_excel_bytes(resultado),
            file_name="Compra_Sugerida_hasta_MAXIMO.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with coly:
        st.download_button(
            label="⬇️ Descargar Excel (vista filtrada)",
            data=to_excel_bytes(res_view),
            file_name="Compra_Sugerida_filtrada.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    with st.expander("Plantilla para extracto Odoo (opcional)", expanded=False):
        # Construir plantilla con los productos detectados
        prods = resultado["Producto"].dropna().unique()
        tpl = pd.DataFrame({
            "Almacen": ["TU_ALMACEN/Stock" for _ in prods],
            "Producto": prods,
            "Stock": ["(rellenar)"] * len(prods),
        })
        st.dataframe(tpl.head(50))
        st.download_button(
            label="⬇️ Descargar plantilla Odoo",
            data=to_excel_bytes(tpl),
            file_name="Plantilla_Extracto_Odoo.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.info("Sube los dos archivos para calcular las cantidades a comprar hasta el Máximo.")
