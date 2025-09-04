import streamlit as st
import pandas as pd
import re
from pathlib import Path
import io

DEFAULT_MINMAX_PATH = "EXCEL FINAL INVENTARIOS.xlsx"

# --------------------------
# Funciones auxiliares
# --------------------------

def _norm_text(x):
    if x is None:
        return None
    s = str(x).strip()
    s = re.sub(r"\s*\(.*\)$", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def parse_minmax(path: str) -> pd.DataFrame:
    xls = pd.ExcelFile(path)
    df = pd.read_excel(path, sheet_name=xls.sheet_names[0])
    df = df.rename(columns={c: str(c).strip() for c in df.columns})

    col_aloj = next((c for c in df.columns if str(c).lower().startswith("aloj")), df.columns[0])
    col_alm = next((c for c in df.columns if str(c).lower().startswith("almac")), df.columns[1])
    col_cap = next((c for c in df.columns if "capacidad" in str(c).lower()), df.columns[2])

    rest = [c for c in df.columns if c not in (col_aloj, col_alm, col_cap)]
    long_frames = []
    for i in range(0, len(rest)-1, 2):
        min_col, max_col = rest[i], rest[i+1]
        prod_name = re.sub(r"\.\d+$", "", str(min_col)).strip()
        tmp = df[[col_alm, min_col, max_col]].copy()
        tmp.columns = ["Almacen", "Min", "Max"]
        tmp["Producto"] = prod_name
        long_frames.append(tmp)

    mm = pd.concat(long_frames, ignore_index=True)
    mm["Almacen"] = mm["Almacen"].map(_norm_text)
    mm["Producto"] = mm["Producto"].map(_norm_text)
    mm["Min"] = pd.to_numeric(mm["Min"], errors="coerce").fillna(0)
    mm["Max"] = pd.to_numeric(mm["Max"], errors="coerce").fillna(0)

    mm["K_Almacen"] = mm["Almacen"].str.upper().str.strip()
    mm["K_Producto"] = mm["Producto"].str.upper().str.strip()
    return mm

def parse_odoo(file) -> pd.DataFrame:
    if str(file).lower().endswith(".csv"):
        od = pd.read_csv(file)
    else:
        xls = pd.ExcelFile(file)
        od = pd.read_excel(file, sheet_name=xls.sheet_names[0])
    od = od.rename(columns={c: str(c).strip() for c in od.columns})
    od = od.rename(columns={"Ubicación": "Almacen", "Cantidad": "Stock"})
    od["Almacen"] = od["Almacen"].map(_norm_text)
    od["Producto"] = od["Producto"].map(_norm_text)
    od["Stock"] = pd.to_numeric(od["Stock"], errors="coerce").fillna(0)

    od["K_Almacen"] = od["Almacen"].str.upper().str.strip()
    od["K_Producto"] = od["Producto"].str.upper().str.strip()

    stock = (od.dropna(subset=["Almacen", "Producto"])
               .groupby(["K_Almacen", "K_Producto"], as_index=False)
               .agg({"Stock": "sum"}))
    return stock

def calcular_necesidades(mm_agg: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    df = mm_agg.merge(stock, on=["K_Almacen", "K_Producto"], how="left")
    df["Almacen"] = df["Almacen"].fillna(df.get("Almacen"))
    df["Producto"] = df["Producto"].fillna(df.get("Producto"))
    df["Stock"] = pd.to_numeric(df.get("Stock", 0), errors="coerce").fillna(0)

    df["Compra_hasta_Max"] = (df["Max"] - df["Stock"]).clip(lower=0)
    df["Falta_hasta_Min"] = (df["Min"] - df["Stock"]).clip(lower=0)

    df = df[["Almacen", "Producto", "Stock", "Min", "Max", "Falta_hasta_Min", "Compra_hasta_Max"]]
    return df.sort_values(["Almacen", "Producto"]).reset_index(drop=True)

def resumen_por_producto(detalle: pd.DataFrame) -> pd.DataFrame:
    resumen = (detalle.groupby("Producto", as_index=False)["Compra_hasta_Max"].sum()
                      .rename(columns={"Compra_hasta_Max": "Total_a_comprar"}))
    return resumen.sort_values("Total_a_comprar", ascending=False)

def to_excel_bytes(df: pd.DataFrame, sheet_name="Hoja") -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    return output.getvalue()

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
        4. Verás primero el **detalle por apartamento** y después el **resumen total por producto**.  
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
    )
elif mode == "Pegar CSV":
    st.caption("Pega aquí el CSV (incluye la fila de encabezados).")
    csv_pasted = st.text_area("Pegado CSV", height=200, key="odoo_csv_text")
elif mode == "Archivo en servidor":
    server_path = st.text_input(
        "Ruta en el servidor (ej. data/Exportacion_Odoo.csv o .xlsx)",
        value="",
        key="odoo_server_path",
    )

mm_agg = parse_minmax(DEFAULT_MINMAX_PATH)

if mode == "Subir archivo" and odoo_file is not None:
    input_kind = "upload"
elif mode == "Pegar CSV" and csv_pasted:
    input_kind = "paste"
elif mode == "Archivo en servidor" and server_path:
    input_kind = "server"
else:
    input_kind = None

if input_kind is not None:
    if input_kind == "upload":
        stock = parse_odoo(odoo_file)
    elif input_kind == "paste":
        csv_bytes = io.BytesIO(csv_pasted.encode("utf-8"))
        stock = parse_odoo(csv_bytes)
    elif input_kind == "server":
        path = Path(server_path)
        if not path.exists():
            st.error(f"La ruta no existe: {path}")
            st.stop()
        stock = parse_odoo(str(path))

    st.success(f"Extracto Odoo cargado ({input_kind}). Filas: {len(stock)}")

    # --- Por apartamento ---
    st.subheader("🏠 Compras por apartamento (almacén)")
    detalle = calcular_necesidades(mm_agg, stock)
    st.dataframe(detalle, use_container_width=True)

    # --- Totales por producto ---
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

    # Gráfica
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
