# app.py
# -*- coding: utf-8 -*-
"""
APP: Pedidos de compra según inventarios (Odoo + Mín/Máx)
Autor: ChatGPT (para Florit Flats)

Funcionalidad MVP
-----------------
- Usa por defecto el Excel oficial de mínimos y máximos (EXCEL FINAL INVENTARIOS.xlsx).
- Subes únicamente el extracto de inventario desde Odoo (Ubicación, Producto, Cantidad).
- La app transforma el Excel de Mín/Máx a formato largo y agrega por Almacén/Producto.
- Cruza con el stock actual de Odoo y calcula:
  * Falta_hasta_Min = max(Min - Stock, 0)
  * Compra_hasta_Max = max(Max - Stock, 0)   ← criterio por defecto
- Descarga de Excel con las cantidades sugeridas para llegar al Máximo.

Roadmap (siguientes iteraciones)
---------------------------------
- Tabla de proveedores (MOQ, múltiplos, coste, lead time) y ajuste de cantidades.
- Pronóstico de demanda por reservas y tasa de ocupación.
- Vistas por proveedor y por almacén, y generación de pedidos automáticos.

Ejecutar
--------
streamlit run app.py
"""

import io
import re
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Compras Odoo + Mín/Máx", layout="wide")

# Archivo de Mín/Máx por defecto
from pathlib import Path
DEFAULT_MINMAX_PATH = Path(__file__).parent / "EXCEL FINAL INVENTARIOS.xlsx"  # Debe existir en el mismo directorio que app.py

# -------------------------------------------
# Utilidades
# -------------------------------------------

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

# -------------------------------------------
# Lectura Mín/Máx
# -------------------------------------------

def parse_minmax(path: str | Path) -> pd.DataFrame:
    # Intento de lectura con openpyxl (recomendado). Si falta, mostramos instrucción clara.
    try:
        xls = pd.ExcelFile(path, engine="openpyxl")
    except ImportError as ie:
        st.error("Falta el paquete **openpyxl**. Añade `openpyxl` a tu `requirements.txt` y vuelve a desplegar.")
        raise
    except FileNotFoundError:
        st.error(f"No se encontró el archivo de Mín/Máx en: {path}. Asegúrate de que **EXCEL FINAL INVENTARIOS.xlsx** esté en el mismo directorio que `app.py`.")
        raise
    sheet = xls.sheet_names[0]
    df = pd.read_excel(path, sheet_name=sheet)
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    col_aloj = next((c for c in df.columns if str(c).lower().startswith("aloj")), df.columns[0])
    col_alm  = next((c for c in df.columns if str(c).lower().startswith("almac")), df.columns[1])
    col_cap  = next((c for c in df.columns if "capacidad" in str(c).lower()), df.columns[2])

    rest = [c for c in df.columns if c not in (col_aloj, col_alm, col_cap)]
    long_frames = []
    for i in range(0, len(rest) - 1, 2):
        min_col, max_col = rest[i], rest[i+1]
        prod_name = re.sub(r"\.\d+$", "", str(min_col)).strip()
        tmp = df[[col_alm, min_col, max_col]].copy()
        tmp.columns = ["Almacen", "Min", "Max"]
        tmp["Producto"] = prod_name
        long_frames.append(tmp)

    long_df = pd.concat(long_frames, ignore_index=True)
    long_df["Almacen"] = long_df["Almacen"].map(_norm_text)
    long_df["Producto"] = long_df["Producto"].map(_norm_text)
    for c in ["Min", "Max"]:
        long_df[c] = pd.to_numeric(long_df[c], errors="coerce").fillna(0)

    mm_agg = (long_df.groupby(["Almacen", "Producto"], as_index=False)
              .agg({"Min":"sum","Max":"sum"}))
    mm_agg["K_Almacen"] = mm_agg["Almacen"].map(_norm_key)
    mm_agg["K_Producto"] = mm_agg["Producto"].map(_norm_key)
    return mm_agg

# -------------------------------------------
# Lectura Odoo
# -------------------------------------------

def parse_odoo(file) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    sheet = xls.sheet_names[0]
    df = pd.read_excel(file, sheet_name=sheet)
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    col_loc = next((c for c in df.columns if "ubicación" in c.lower() or "ubicacion" in c.lower() or c.lower()=="ubicacion"), None)
    col_prod = next((c for c in df.columns if "producto" in c.lower()), None)
    col_qty = next((c for c in df.columns if c.lower() in ("cantidad", "quantity")), None)

    df = df[[col_loc, col_prod, col_qty]].copy()
    df.columns = ["Almacen","Producto","Stock"]

    df["Almacen"] = df["Almacen"].map(_norm_text)
    df["Producto"] = df["Producto"].map(_norm_text)
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0)

    stock = (df.dropna(subset=["Almacen","Producto"])
               .groupby(["Almacen","Producto"], as_index=False)
               .agg({"Stock":"sum"}))
    stock["K_Almacen"] = stock["Almacen"].map(_norm_key)
    stock["K_Producto"] = stock["Producto"].map(_norm_key)
    return stock

# -------------------------------------------
# Cálculo
# -------------------------------------------

def calcular_necesidades(mm_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    df = mm_agg.merge(stock, on=["K_Almacen","K_Producto"], how="left", suffixes=("_MM","_OD"))
    df["Almacen"] = df["Almacen_MM"].fillna(df["Almacen_OD"])
    df["Producto"] = df["Producto_MM"].fillna(df["Producto_OD"])
    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df["Max"] = pd.to_numeric(df["Max"], errors="coerce").fillna(0)
    df["Stock"] = pd.to_numeric(df.get("Stock",0), errors="coerce").fillna(0)

    df["Falta_hasta_Min"] = (df["Min"] - df["Stock"]).clip(lower=0)
    df["Compra_hasta_Max"] = (df["Max"] - df["Stock"]).clip(lower=0)

    df["Por_debajo_de_Min"] = (df["Stock"] < df["Min"]).astype(int)
    df["En_objetivo"] = ((df["Stock"] >= df["Min"]) & (df["Stock"] <= df["Max"]).astype(bool)).astype(int)
    df["Sobre_Max"] = (df["Stock"] > df["Max"]).astype(int)

    cols = ["Almacen","Producto","Min","Max","Stock","Falta_hasta_Min","Compra_hasta_Max","Por_debajo_de_Min","En_objetivo","Sobre_Max"]
    return df[cols].sort_values(["Almacen","Producto"]).reset_index(drop=True)

# -------------------------------------------
# UI
# -------------------------------------------

st.title("🛒 APP de Compras – Odoo + Mín/Máx (MVP)")
with st.expander("Cómo funciona", expanded=False):
    st.markdown("""
    1. Se usa por defecto tu **Excel oficial de Mín/Máx** (EXCEL FINAL INVENTARIOS.xlsx).
    2. Sube únicamente el **extracto de Odoo** (Ubicación, Producto, Cantidad).
    3. La app calcula **Compra_hasta_Max** = Max − Stock (si es > 0) por almacén y producto.
    4. Descarga el Excel con los resultados.
    """)

odoo_file = st.file_uploader("Extracto de Odoo (Ubicación, Producto, Cantidad)", type=["xlsx","xls","csv"]) 

st.caption("Dependencias requeridas: streamlit, pandas, numpy, openpyxl, xlsxwriter (añádelas a requirements.txt)") 

mm_agg = parse_minmax(DEFAULT_MINMAX_PATH)

if odoo_file is not None:
    try:
        stock = parse_odoo(odoo_file)
        st.success(f"Extracto Odoo cargado: {len(stock)} filas")

        resultado = calcular_necesidades(mm_agg, stock)
        st.subheader("Resultado – Sugerencia de compra hasta Máximo")
        st.dataframe(resultado, use_container_width=True)

        total_compra = int(resultado["Compra_hasta_Max"].sum())
        st.info(f"Total de unidades sugeridas (hasta Máx): **{total_compra:,}**")

        def to_excel_bytes(df: pd.DataFrame) -> bytes:
            bio = io.BytesIO()
            with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="CompraHastaMax")
            bio.seek(0)
            return bio.read()

        st.download_button(
            label="⬇️ Descargar Excel",
            data=to_excel_bytes(resultado),
            file_name="Compra_Sugerida_hasta_MAXIMO.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    except Exception as e:
        st.error(f"Error leyendo Odoo: {e}")
else:
    st.info("Sube el extracto de Odoo para calcular las cantidades a comprar hasta el Máximo.")
