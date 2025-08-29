
import streamlit as st
import pandas as pd
import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Informe desde Google Drive (sin claves)", layout="wide")
st.title("📋 Informe desde Google Drive (sin claves)")

# --- ENLACES DE GOOGLE SHEETS ---
url_datos = "https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/export?format=xlsx"
url_cafe = "https://floritflats.github.io/reposiciones/data/Cafe%20por%20propiedad.xlsx"

# --- CARGA DE DATOS ---
@st.cache_data
def cargar_datos(url):
    return pd.read_excel(url)

try:
    df = cargar_datos(url_datos)
    df_cafe = cargar_datos(url_cafe)
except Exception as e:
    st.error(f"No se pudo cargar el archivo: {e}")
    st.stop()

# --- RENOMBRADO DE COLUMNAS CLAVE ---
df = df.rename(columns=lambda x: x.strip())

# --- UNIFICAR FORMATO DE NOMBRE DE COLUMNAS ---
columnas_deseadas = {
    "Marca temporal": "Marca temporal",
    "Apartamento": "Apartamento",
    "Inventario ropa e consumables": "Inventario ropa e consumables",
    "Faltantes por entrada": "Faltantes por entrada",
    "Faltantes reposiciones café": "Faltantes reposiciones café",
    "Reposiciones sal": "Reposiciones sal",
    "Reposiciones té/infusión": "Reposiciones té/infusión",
    "Reposiciones detergente de ropa": "Reposiciones detergente de ropa",
    "Reposiciones insecticida": "Reposiciones insecticida",
    "Reposiciones gel de ducha": "Reposiciones gel de ducha",
    "Reposiciones champú": "Reposiciones champú",
    "Reposiciones jabón de manos": "Reposiciones jabón de manos",
    "Reposiciones escoba": "Reposiciones escoba",
    "Reposiciones lavavajillas": "Reposiciones lavavajillas",
    "Reposiciones vinagre": "Reposiciones vinagre",
    "Reposiciones pastilla de descalcificado": "Reposiciones pastilla de descalcificado",
    "Reposiciones kit de cocina": "Reposiciones kit de cocina",
    "Reposiciones papel higiénico": "Reposiciones papel higiénico",
    "Reposiciones botella de agua": "Reposiciones botella de agua",
    "Otras reposiciones": "Otras reposiciones",
    "Detergente finalizado": "Detergente finalizado",
    "Jabón de manos finalizado": "Jabón de manos finalizado",
    "Sal de lavavajillas finalizado": "Sal de lavavajillas finalizado",
    "Vinagre finalizado": "Vinagre finalizado",
    "Abrillantador finalizado": "Abrillantador finalizado",
    "Incidencias a realizar": "Incidencias a realizar"
}

df = df.rename(columns=columnas_deseadas)
columnas_existentes = [col for col in columnas_deseadas.values() if col in df.columns]
df = df[columnas_existentes + ["Marca temporal", "Apartamento"]]

# --- FORMATO DE FECHA ---
df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], errors="coerce")

# --- ASOCIAR TIPO DE CAFÉ ---
try:
    df_cafe = df_cafe.rename(columns=lambda x: x.strip())
    df = df.merge(df_cafe, how="left", on="Apartamento")
except Exception as e:
    st.warning("⚠️ No se pudo asociar el tipo de café. Revisa las columnas en el Excel.")

# --- FILTRADO POR FECHA ---
fecha_unica = st.date_input("Selecciona una fecha", value=datetime.date.today())
df_filtrado = df[df["Marca temporal"].dt.date == fecha_unica]

# --- MOSTRAR FILAS COMPLETADAS ---
st.subheader("Filas completadas")
try:
    df_completadas = df_filtrado.dropna(subset=["Inventario ropa e consumables", "Apartamento"], how="all")
    st.dataframe(df_completadas, use_container_width=True)
except Exception as e:
    st.error(f"Ocurrió un error: {e}")

# --- DESCARGA EN PDF ---
def exportar_pdf(dataframe):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph("Informe de reposiciones", styles["Heading1"]))
    elements.append(Spacer(1, 12))

    data = [list(dataframe.columns)] + dataframe.astype(str).values.tolist()
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    return buffer

if not df_filtrado.empty:
    pdf_buffer = exportar_pdf(df_filtrado)
    st.download_button("📄 Descargar informe en PDF", data=pdf_buffer, file_name="informe_reposiciones.pdf", mime="application/pdf")
