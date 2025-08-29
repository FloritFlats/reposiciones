
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

# URL del Google Sheet compartido públicamente en CSV
URL_CSV = "https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/export?format=csv"

# Cargar datos desde Google Sheets
@st.cache_data
def cargar_datos():
    df = pd.read_csv(URL_CSV)
    return df

# Cargar café por propiedad
@st.cache_data
def cargar_cafe():
    return pd.read_excel("Cafe por propiedad.xlsx")

# Crear PDF con el informe
def generar_pdf(df_filtrado, fecha):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [Paragraph(f"Informe Diario - {fecha}", styles["Title"]), Spacer(1, 12)]

    columnas = df_filtrado.columns.tolist()
    data = [columnas] + df_filtrado.values.tolist()

    tabla = Table(data, repeatRows=1)
    tabla.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
    ]))

    story.append(tabla)
    doc.build(story)
    buffer.seek(0)
    return buffer

# --- App principal ---
st.set_page_config(page_title="Informe Diario de Reposiciones", layout="wide")
st.title("📋 Informe Diario de Reposiciones e Incidencias")

df = cargar_datos()
df_cafe = cargar_cafe()

# Unir tipo de café
df = df.merge(df_cafe, how="left", on="Apartamento")
df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], errors="coerce")
df["Fecha"] = df["Marca temporal"].dt.date
df["Hora"] = df["Marca temporal"].dt.strftime("%H:%M")

# Filtro por fecha
fechas_disponibles = sorted(df["Fecha"].dropna().unique())
fecha_seleccionada = st.sidebar.selectbox("Selecciona una fecha", fechas_disponibles)

df_filtrado = df[df["Fecha"] == fecha_seleccionada]

# Filtro por filas completadas (al menos una columna de contenido)
columnas_relevantes = df.columns[2:-3]  # Excluye marca temporal, apartamento y café
df_filtrado = df_filtrado[df_filtrado[columnas_relevantes].notna().any(axis=1)]

st.subheader(f"🧼 Limpiezas realizadas el {fecha_seleccionada}")
st.dataframe(df_filtrado, use_container_width=True)

# Botón de descarga en PDF
if not df_filtrado.empty:
    pdf = generar_pdf(df_filtrado, fecha_seleccionada)
    st.download_button(
        label="📥 Descargar informe en PDF",
        data=pdf,
        file_name=f"informe_{fecha_seleccionada}.pdf",
        mime="application/pdf"
    )
else:
    st.info("No hay limpiezas completadas para esta fecha.")
