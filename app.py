# app.py
# -*- coding: utf-8 -*-
"""
APP: Pedidos de compra según inventarios (Odoo + Mín/Máx)
Autor: ChatGPT (para Florit Flats)

MVP (con Totales por producto + KPI + Gráfica)
----------------------------------------------
- Usa por defecto el Excel oficial de mínimos y máximos (EXCEL FINAL INVENTARIOS.xlsx).
- Subes únicamente el extracto de inventario desde Odoo (Ubicación, Producto, Cantidad).
- Calcula cantidades **hasta el Máximo** por almacén y **muestra el RESUMEN TOTAL por producto** (suma de todos los almacenes).
- KPI: total de unidades a comprar y número de SKUs.
- Gráfica de barras (Top 20 productos por unidades a comprar).
- Nueva gráfica: **Unidades restantes (Stock vs Máximo)**.
- Descargas: Detalle por almacén y Resumen por producto (completo y sólo > 0).

Ejecutar
--------
streamlit run app.py
Requisitos: streamlit, pandas, numpy, openpyxl, xlsxwriter, matplotlib
"""

import io
import re
from pathlib import Path
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

st.set_page_config(page_title="Compras Odoo + Mín/Máx", layout="wide")

DEFAULT_MINMAX_PATH = Path(__file__).parent / "EXCEL FINAL INVENTARIOS.xlsx"

def _norm_text(x):
    import pandas as pd
    if x is None or pd.isna(x):
        return None
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    s = re.sub(r"\s*\(.*\)$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _norm_key(x):
    x = _norm_text(x)
    return x.upper() if x else None

def parse_minmax(path: str | Path) -> pd.DataFrame:
    xls = pd.ExcelFile(path, engine="openpyxl")
    df = pd.read_excel(path, sheet_name=xls.sheet_names[0])
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
    long_df = long_df[long_df["Almacen"].notna() & (long_df["Almacen"].str.strip() != "")]
    mm_agg = long_df.groupby(["Almacen", "Producto"], as_index=False).agg({"Min": "sum", "Max": "sum"})
    mm_agg["K_Almacen"] = mm_agg["Almacen"].map(_norm_key)
    mm_agg["K_Producto"] = mm_agg["Producto"].map(_norm_key)
    return mm_agg

def parse_odoo(file) -> pd.DataFrame:
    xls = pd.ExcelFile(file)
    df = pd.read_excel(file, sheet_name=xls.sheet_names[0])
    df = df.rename(columns={c: str(c).strip() for c in df.columns})
    col_loc = next((c for c in df.columns if "ubicación" in c.lower() or "ubicacion" in c.lower() or c.lower() == "ubicacion"), None)
    col_prod = next((c for c in df.columns if "producto" in c.lower()), None)
    col_qty = next((c for c in df.columns if c.lower() in ("cantidad", "quantity")), None)
    df = df[[col_loc, col_prod, col_qty]].copy()
    df.columns = ["Almacen", "Producto", "Stock"]
    df["Almacen"] = df["Almacen"].map(_norm_text)
    df["Producto"] = df["Producto"].map(_norm_text)
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0)
    stock = df.dropna(subset=["Almacen", "Producto"]).groupby(["Almacen", "Producto"], as_index=False).agg({"Stock": "sum"})
    stock["K_Almacen"] = stock["Almacen"].map(_norm_key)
    stock["K_Producto"] = stock["Producto"].map(_norm_key)
    return stock

def calcular_necesidades(mm_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    df = mm_agg.merge(stock, on=["K_Almacen", "K_Producto"], how="left", suffixes=("_MM", "_OD"))
    df["Almacen"] = df["Almacen_MM"].fillna(df.get("Almacen_OD"))
    df["Producto"] = df["Producto_MM"].fillna(df.get("Producto_OD"))
    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df["Max"] = pd.to_numeric(df["Max"], errors="coerce").fillna(0)
    df["Stock"] = pd.to_numeric(df.get("Stock", 0), errors="coerce").fillna(0)
    df = df[df["Almacen"].notna() & (df["Almacen"].astype(str).str.strip() != "")]
    df["Compra_hasta_Max"] = (df["Max"] - df["Stock"]).clip(lower=0)
    df["Falta_hasta_Min"]  = (df["Min"] - df["Stock"]).clip(lower=0)
    df = df[["Almacen", "Producto", "Stock", "Min", "Max", "Falta_hasta_Min", "Compra_hasta_Max"]]
    return df.sort_values(["Almacen", "Producto"]).reset_index(drop=True)

def resumen_por_producto(detalle: pd.DataFrame) -> pd.DataFrame:
    return (
        detalle.groupby("Producto", as_index=False)["Compra_hasta_Max"].sum()
        .rename(columns={"Compra_hasta_Max": "Total_a_comprar"})
        .sort_values("Producto")
    )

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
        3. Si un producto **no aparece** en el extracto de un apartamento (almacén), **se asume Stock = 0**.
        4. Verás primero el **detalle por apartamento (almacén)** con compras por producto, y después el **resumen total por producto**.
        """
    )

st.markdown("### 📥 Cargar extracto de Odoo")
mode = st.radio(
    "Cómo quieres cargar el extracto:",
    ["Subir archivo", "Pegar CSV", "Archivo en servidor"],
    index=0,
    horizontal=True,
)

odoo_file = None
csv_pasted = None
server_path = None

if mode == "Subir archivo":
    odoo_file = st.file_uploader("Extracto de Odoo (Ubicación, Producto, Cantidad)", type=["xlsx", "xls", "csv"], accept_multiple_files=False)
elif mode == "Pegar CSV":
    st.caption("Pega aquí el CSV tal cual (incluye la primera fila con encabezados).")
    csv_pasted = st.text_area("Pegado CSV", height=200)
elif mode == "Archivo en servidor":
    server_path = st.text_input("Ruta en el servidor (ej. data/Exportacion_Odoo.csv o .xlsx)", value="")

mm_agg = parse_minmax(DEFAULT_MINMAX_PATH)

if mode == "Subir archivo" and odoo_file is not None:
    stock = parse_odoo(odoo_file)
elif mode == "Pegar CSV" and csv_pasted:
    import io as _io
    csv_bytes = _io.BytesIO(csv_pasted.encode("utf-8"))
    stock = parse_odoo(csv_bytes)
elif mode == "Archivo en servidor" and server_path:
    path = Path(server_path)
    if not path.exists():
        st.error(f"La ruta no existe: {path}")
        st.stop()
    stock = parse_odoo(str(path))
else:
    stock = None

if stock is not None:
    st.success(f"Extracto Odoo cargado. Filas: {len(stock)}")

    st.subheader("🏠 Compras por apartamento (almacén)")
    detalle = calcular_necesidades(mm_agg, stock)
    st.dataframe(detalle, use_container_width=True)

    st.subheader("📦 Totales por producto (suma de todos los apartamentos)")
    resumen = resumen_por_producto(detalle)
    resumen_pos = resumen[resumen["Total_a_comprar"] > 0].copy()
    st.dataframe(resumen_pos, use_container_width=True)

    total_units = int(resumen_pos["Total_a_comprar"].sum())
    sku_count = int(resumen_pos.shape[0])
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total de unidades a comprar", f"{total_units:,}")
    with c2:
        st.metric("Número de productos (SKU)", f"{sku_count}")

    top = resumen_pos.sort_values("Total_a_comprar", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(top["Producto"], top["Total_a_comprar"])
    ax.set_title("Compras totales por producto (Top 20) – hasta Máximo")
    ax.set_xlabel("Producto")
    ax.set_ylabel("Unidades a comprar")
    ax.tick_params(axis="x", rotation=75)
    fig.tight_layout()
    st.pyplot(fig)

    # Nueva gráfica: Unidades restantes (Stock vs Máximo)
    st.subheader("📊 Unidades restantes (Stock vs Máximo)")
    unidades = detalle.groupby("Producto", as_index=False).agg({"Stock": "sum", "Max": "sum", "Min": "sum"})
    unidades["Faltan"] = unidades["Max"] - unidades["Stock"]
    unidades = unidades.sort_values("Stock")

    fig2, ax2 = plt.subplots(figsize=(10, max(6, len(unidades)*0.3)))
    ax2.barh(unidades["Producto"], unidades["Stock"], color="skyblue", label="Stock actual")
    ax2.barh(unidades["Producto"], unidades["Faltan"], left=unidades["Stock"], color="lightcoral", label="Faltan hasta Max")
    ax2.scatter(unidades["Min"], range(len(unidades)), color="black", marker="D", label="Min")
    ax2.set_xlabel("Unidades")
    ax2.set_ylabel("Producto")
    ax2.set_title("Unidades restantes vs Máximo por producto")
    ax2.legend()
    st.pyplot(fig2)

    # === Productos por debajo del Min ===
    bajos = unidades.loc[unidades["Stock"] < unidades["Min"], ["Producto", "Stock", "Min"]].copy()
    if not bajos.empty:
        bajos["Déficit_hasta_Min"] = (bajos["Min"] - bajos["Stock"]).clip(lower=0).astype(int)
        bajos = bajos.sort_values("Déficit_hasta_Min", ascending=False).reset_index(drop=True)
        st.warning("⚠️ Productos por debajo del punto de pedido (Min):")
        st.dataframe(bajos, use_container_width=True)
        st.download_button(
            label="⬇️ Excel – Productos por debajo de Min",
            data=to_excel_bytes(bajos, "PorDebajoMin"),
            file_name="Productos_por_debajo_de_Min.xlsx",
        )

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button("⬇️ Excel – Por apartamento", data=to_excel_bytes(detalle, "PorApartamento"), file_name="Compra_Por_Apartamento.xlsx")
    with c2:
        st.download_button("⬇️ Excel – Resumen por producto", data=to_excel_bytes(resumen, "ResumenPorProducto"), file_name="Compra_Resumen_Por_Producto.xlsx")
    with c3:
        st.download_button("⬇️ Excel – Resumen (solo > 0)", data=to_excel_bytes(resumen_pos, "ResumenPositivos"), file_name="Compra_Resumen_Por_Producto_POSITIVOS.xlsx")
else:
    st.info("Sube o pega el extracto de Odoo para ver compras por **apartamento** y el **total por producto**.")
