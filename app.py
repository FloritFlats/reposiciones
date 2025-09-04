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
- Descargas: Detalle por almacén y Resumen por producto (completo y sólo > 0).

Opcional
--------
- Si has puesto 0 donde no aplica (p. ej. cafés por alojamiento) en tu Excel, ya queda excluido.

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

st.set_page_config(page_title="Compras Odoo + Mín/Máx", layout="wide")

# Archivo de Mín/Máx por defecto (junto a app.py)
DEFAULT_MINMAX_PATH = Path(__file__).parent / "EXCEL FINAL INVENTARIOS.xlsx"

# --------------------------
# Utilidades
# --------------------------

def _norm_text(x):
    """Normaliza texto: recorta, quita sufijos entre paréntesis y espacios extra."""
    if x is None:
        return None
    x = str(x).strip()
    x = re.sub(r"\s*\(\d+\)$", "", x)  # quita " (17)" finales
    x = re.sub(r"\s+", " ", x)
    return x


def _norm_key(x):
    """Convierte a clave normalizada (mayúsculas tras normalizar)."""
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
    if len(rest) % 2 != 0:
        st.warning("El número de columnas de productos no es par. Comprueba los pares Min/Max.")

    long_frames = []
    for i in range(0, len(rest) - 1, 2):
        min_col, max_col = rest[i], rest[i+1]
        prod_name = re.sub(r"\.\d+$", "", str(min_col)).strip()
        tmp = df[[col_alm, min_col, max_col]].copy()
        tmp.columns = ["Almacen", "Min", "Max"]
        tmp["Producto"] = prod_name
        long_frames.append(tmp)

    if not long_frames:
        raise ValueError("No se detectaron columnas de productos.")

    long_df = pd.concat(long_frames, ignore_index=True)
    long_df["Almacen"] = long_df["Almacen"].map(_norm_text)
    long_df["Producto"] = long_df["Producto"].map(_norm_text)
    for c in ["Min", "Max"]:
        long_df[c] = pd.to_numeric(long_df[c], errors="coerce").fillna(0)

    # Agregado por almacén–producto (si pusiste 0 donde no aplica, aquí queda excluido)
    mm_agg = (
        long_df.groupby(["Almacen", "Producto"], as_index=False)
        .agg({"Min": "sum", "Max": "sum"})
    )
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

    col_loc = next((c for c in df.columns if "ubicación" in c.lower() or "ubicacion" in c.lower() or c.lower() == "ubicacion"), None)
    col_prod = next((c for c in df.columns if "producto" in c.lower()), None)
    col_qty = next((c for c in df.columns if c.lower() in ("cantidad", "quantity")), None)

    if not (col_loc and col_prod and col_qty):
        raise ValueError("El extracto debe contener columnas: Ubicación, Producto, Cantidad.")

    df = df[[col_loc, col_prod, col_qty]].copy()
    df.columns = ["Almacen", "Producto", "Stock"]

    df["Almacen"] = df["Almacen"].map(_norm_text)
    df["Producto"] = df["Producto"].map(_norm_text)
    df["Stock"] = pd.to_numeric(df["Stock"], errors="coerce").fillna(0)

    stock = (
        df.dropna(subset=["Almacen", "Producto"]) 
        .groupby(["Almacen", "Producto"], as_index=False)
        .agg({"Stock": "sum"})
    )
    stock["K_Almacen"] = stock["Almacen"].map(_norm_key)
    stock["K_Producto"] = stock["Producto"].map(_norm_key)
    return stock


# --------------------------
# Cálculo de necesidades y resúmenes
# --------------------------

def calcular_necesidades(mm_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    """
    Combina Mín/Máx oficiales con el extracto Odoo.
    Importante: si un producto NO aparece en el extracto para un apartamento (almacén),
    se asume **Stock = 0** y por tanto se calcula la compra hasta Máximo.
    """
    df = mm_agg.merge(stock, on=["K_Almacen", "K_Producto"], how="left", suffixes=("_MM", "_OD"))

    # Nombres presentables
    df["Almacen"] = df["Almacen_MM"].fillna(df.get("Almacen_OD"))
    df["Producto"] = df["Producto_MM"].fillna(df.get("Producto_OD"))

    # Valores numéricos y asunción Stock=0 si falta en Odoo
    df["Min"] = pd.to_numeric(df["Min"], errors="coerce").fillna(0)
    df["Max"] = pd.to_numeric(df["Max"], errors="coerce").fillna(0)
    df["Stock"] = pd.to_numeric(df.get("Stock", 0), errors="coerce").fillna(0)  # <- aquí asumimos 0

    # Cálculos
    df["Compra_hasta_Max"] = (df["Max"] - df["Stock"]).clip(lower=0)
    df["Falta_hasta_Min"]  = (df["Min"] - df["Stock"]).clip(lower=0)

    # Ordenado "por apartamento" (cada apartamento = un almacén)
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

# --- Carga de extracto ---
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
    odoo_file = st.file_uploader(
        "Extracto de Odoo (Ubicación, Producto, Cantidad)",
        type=["xlsx", "xls", "csv"],
        accept_multiple_files=False,
        key="odoo_uploader",
        help="Arrastra y suelta tu Excel/CSV exportado desde Odoo.",
    )
elif mode == "Pegar CSV":
    st.caption("Pega aquí el CSV tal cual (incluye la primera fila con encabezados).")
    csv_pasted = st.text_area("Pegado CSV", height=200, key="odoo_csv_text")
elif mode == "Archivo en servidor":
    server_path = st.text_input("Ruta en el servidor (ej. data/Exportacion_Odoo.csv o .xlsx)", value="", key="odoo_server_path")

mm_agg = parse_minmax(DEFAULT_MINMAX_PATH)

# Normalizamos el input del extracto según el modo elegido
if mode == "Subir archivo" and odoo_file is not None:
    input_kind = "upload"
elif mode == "Pegar CSV" and csv_pasted:
    input_kind = "paste"
elif mode == "Archivo en servidor" and server_path:
    input_kind = "server"
else:
    input_kind = None

if input_kind is not None:
    # Cargar el extracto según el modo elegido
    if input_kind == "upload":
        stock = parse_odoo(odoo_file)
    elif input_kind == "paste":
        import io as _io
        csv_bytes = _io.BytesIO(csv_pasted.encode("utf-8"))
        stock = parse_odoo(csv_bytes)
    elif input_kind == "server":
        path = Path(server_path)
        if not path.exists():
            st.error(f"La ruta no existe: {path}")
            st.stop()
        stock = parse_odoo(str(path))

    st.success(f"Extracto Odoo cargado ({input_kind}). Filas: {len(stock)}")

    # === 1) BLOQUE POR APARTAMENTO (cada apartamento = almacén) ===
    st.subheader("🏠 Compras por apartamento (almacén)")
    detalle = calcular_necesidades(mm_agg, stock)
    st.dataframe(detalle, use_container_width=True)

    # === 2) BLOQUE TOTALES POR PRODUCTO ===
    st.subheader("📦 Totales por producto (suma de todos los apartamentos)")
    resumen = resumen_por_producto(detalle)
    resumen_pos = resumen[resumen["Total_a_comprar"] > 0].copy()
    st.dataframe(resumen_pos, use_container_width=True)

    # KPI
    total_units = int(resumen_pos["Total_a_comprar"].sum())
    sku_count = int(resumen_pos.shape[0])
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Total de unidades a comprar", f"{total_units:,}")
    with c2:
        st.metric("Número de productos (SKU)", f"{sku_count}")

    # Gráfica Top 20
    import matplotlib.pyplot as plt
    top = resumen_pos.sort_values("Total_a_comprar", ascending=False).head(20)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(top["Producto"], top["Total_a_comprar"])
    ax.set_title("Compras totales por producto (Top 20) – hasta Máximo")
    ax.set_xlabel("Producto")
    ax.set_ylabel("Unidades a comprar")
    ax.tick_params(axis="x", rotation=75)
    fig.tight_layout()
    st.pyplot(fig)

    # Descargas
    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            label="⬇️ Excel – Por apartamento",
            data=to_excel_bytes(detalle, "PorApartamento"),
            file_name="Compra_Por_Apartamento.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c2:
        st.download_button(
            label="⬇️ Excel – Resumen por producto",
            data=to_excel_bytes(resumen, "ResumenPorProducto"),
            file_name="Compra_Resumen_Por_Producto.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with c3:
        st.download_button(
            label="⬇️ Excel – Resumen (solo > 0)",
            data=to_excel_bytes(resumen_pos, "ResumenPositivos"),
            file_name="Compra_Resumen_Por_Producto_POSITIVOS.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

else:
    st.info("Sube o pega el extracto de Odoo para ver compras por **apartamento** y el **total por producto**.")

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
            )

    except Exception as e:
        st.error(f"Error procesando el extracto de Odoo: {e}")
else:
    st.info("Sube el extracto de Odoo para ver los **totales por producto** a comprar (hasta Máximo).")
