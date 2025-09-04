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

    # Identifica Alojamiento, Almacén, Capacidad
    col_aloj = next((c for c in df.columns if str(c).lower().startswith("aloj")), df.columns[0])
    col_alm  = next((c for c in df.columns if str(c).lower().startswith("almac")), df.columns[1])
    col_cap  = next((c for c in df.columns if "capacidad" in str(c).lower()), df.columns[2])

    # Pares consecutivos (Min, Max)
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

    # Agregado por almacén–producto (si ya pusiste 0 donde no aplica, aquí queda excluido)
    mm_agg = (long_df.groupby(["Almacen","Producto"], as_index=False)
                    .agg({"Min":"sum","Max":"sum"}))
    mm_agg["K_Almacen"] = mm_agg["Almacen"].map(_norm_key)
    mm_agg["K_Producto"] = mm_agg["Producto"].map(_norm_key)
    return mm_agg

# --------------------------
# Lectura extracto Odoo → Stock por Almacén–Producto
# --------------------------

def parse_odoo(file) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    df = pd.read_excel(file, sheet_name=xls.sheet_names[0])
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    col_loc = next((c for c in df.columns if "ubicación" in c.lower() or "ubicacion" in c.lower() or c.lower()=="ubicacion"), None)
    col_prod = next((c for c in df.columns if "producto" in c.lower()), None)
    col_qty = next((c for c in df.columns if c.lower() in ("cantidad","quantity")), None)

    if not (col_loc and col_prod and col_qty):
        raise ValueError("El extracto debe contener columnas: Ubicación, Producto, Cantidad.")

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

# --------------------------
# Cálculo de necesidades y resúmenes
# --------------------------

def calcular_necesidades(mm_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    df = mm_agg.merge(stock, on=["K_Almacen","K_Producto"], how="left", suffixes=("_MM","_OD"))
    df["Almacen"] = df["Almacen_MM"].fillna(df.get("Almacen_OD"))
    df["Producto"] = df["Producto_MM"].fillna(df.get("Producto_OD"))

    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df["Max"] = pd.to_numeric(df["Max"], errors="coerce").fillna(0)
    df["Stock"] = pd.to_numeric(df.get("Stock", 0), errors="coerce").fillna(0)

    df["Compra_hasta_Max"] = (df["Max"] - df["Stock"]).clip(lower=0)
    df["Falta_hasta_Min"]  = (df["Min"] - df["Stock"]).clip(lower=0)
    return df[["Almacen","Producto","Min","Max","Stock","Falta_hasta_Min","Compra_hasta_Max"]]


def resumen_por_producto(detalle: pd.DataFrame) -> pd.DataFrame:
    return (detalle.groupby("Producto", as_index=False)["Compra_hasta_Max"].sum()
                  .rename(columns={"Compra_hasta_Max":"Total_a_comprar"})
                  .sort_values("Producto"))


def to_excel_bytes(df: pd.DataFrame, sheet_name: str) -> bytes:
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    bio.seek(0)
    return bio.read()

# --------------------------
# UI
# --------------------------

st.title("🛒 Totales por producto – hasta Máximo")
with st.expander("Cómo funciona", expanded=False):
    st.markdown(
        """
        1. La app usa **EXCEL FINAL INVENTARIOS.xlsx** como fuente oficial de Mín/Máx.
        2. Sube el **extracto de Odoo** (Ubicación, Producto, Cantidad).
        3. Verás **Totales por producto** para comprar (suma de todos los almacenes) y podrás descargar el Excel.
        4. Si ya pusiste *0* donde no corresponde (p.ej. cafés por alojamiento), **queda excluido por defecto**.
        """
    )

odoo_file = st.file_uploader("Extracto de Odoo (Ubicación, Producto, Cantidad)", type=["xlsx","xls","csv"]) 

mm_agg = parse_minmax(DEFAULT_MINMAX_PATH)

if odoo_file is not None:
    try:
        stock = parse_odoo(odoo_file)
        detalle = calcular_necesidades(mm_agg, stock)

        # ===== Vista clave: Totales por producto =====
        st.subheader("Totales por producto a comprar (hasta Máximo)")
        resumen = resumen_por_producto(detalle)
        st.dataframe(resumen, use_container_width=True)
        st.success(f"Unidades totales a comprar (suma general): {int(resumen['Total_a_comprar'].sum()):,}")

        # Detalle por almacén (por si necesitas ver el desglose)
        with st.expander("Detalle por almacén (opcional)", expanded=False):
            st.dataframe(detalle.sort_values(["Producto","Almacen"]), use_container_width=True)

        # ===== KPI y gráfica =====
        resumen_pos = resumen[resumen["Total_a_comprar"] > 0].copy()
        total_units = int(resumen_pos["Total_a_comprar"].sum())
        sku_count = int(resumen_pos.shape[0])
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total de unidades a comprar", f"{total_units:,}")
        with c2:
            st.metric("Número de productos (SKU)", f"{sku_count}")

        # Bar chart (Top 20)
        import matplotlib.pyplot as plt
        top = resumen_pos.sort_values("Total_a_comprar", ascending=False).head(20)
        fig, ax = plt.subplots(figsize=(10,6))
        ax.bar(top["Producto"], top["Total_a_comprar"])
        ax.set_title("Compras totales por producto (Top 20) – hasta Máximo")
        ax.set_xlabel("Producto")
        ax.set_ylabel("Unidades a comprar")
        ax.tick_params(axis='x', rotation=75)
        fig.tight_layout()
        st.pyplot(fig)

        # Descargas
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button(
                label="⬇️ Descargar Excel – Resumen por producto",
                data=to_excel_bytes(resumen, "ResumenPorProducto"),
                file_name="Compra_Resumen_Por_Producto.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with c2:
            st.download_button(
                label="⬇️ Descargar Excel – Solo productos > 0",
                data=to_excel_bytes(resumen_pos, "ResumenPositivos"),
                file_name="Compra_Resumen_Por_Producto_POSITIVOS.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        with c3:
            st.download_button(
                label="⬇️ Descargar Excel – Detalle por almacén",
                data=to_excel_bytes(detalle, "DetalleAlmacen"),
                file_name="Compra_Detalle_Almacen.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
                file_name="Compra_Detalle_Almacen.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    except Exception as e:
        st.error(f"Error procesando el extracto de Odoo: {e}")
else:
    st.info("Sube el extracto de Odoo para ver los **totales por producto** a comprar (hasta Máximo).")
