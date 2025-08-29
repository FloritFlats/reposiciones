import streamlit as st
import pandas as pd
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import datetime

st.set_page_config(page_title="Informe desde Google Drive", page_icon=":clipboard:", layout="wide")
st.title("📋 Informe desde Google Drive (sin claves)")

# Cargar Google Sheet
sheet_url = "https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/export?format=csv"
df = pd.read_csv(sheet_url)

# Limpiar nombres de columnas
df.columns = df.columns.str.strip()

# Selección de columnas relevantes
columnas_relevantes = [
    "Marca temporal", "Apartamento", "Incidencias a realizar", "Inventario ropa e consumibles",
    "Faltantes por entrada", "Faltantes reposiciones café", "Reposiciones sal", "Reposiciones té/infusión",
    "Reposiciones detergente de ropa", "Reposiciones insecticida", "Reposiciones gel de ducha",
    "Reposiciones champú", "Reposiciones jabón de manos", "Reposiciones escoba",
    "Reposiciones lavavajillas", "Reposiciones vinagre", "Reposiciones pastilla de descalcificado",
    "Reposiciones kit de cocina", "Reposiciones papel higiénico", "Reposiciones botella de agua",
    "Otras reposiciones", "Detergente finalizado", "Jabón de manos finalizado",
    "Sal de lavavajillas finalizado", "Vinagre finalizado", "Abrillantador finalizado"
]

df = df[[col for col in columnas_relevantes if col in df.columns]]
df = df.rename(columns={"Marca temporal": "Fecha"})

# Convertir fechas
df["Fecha"] = pd.to_datetime(df["Fecha"], errors="coerce")

# Filtro por día
fecha_seleccionada = st.date_input("Selecciona una fecha", value=datetime.date.today())
df_filtrado = df[df["Fecha"].dt.date == fecha_seleccionada]

# Cargar tipo de café por apartamento
try:
    df_cafe = pd.read_excel("Cafe por propiedad.xlsx")
    df_cafe.columns = df_cafe.columns.str.strip()
    if "Apartamento" in df.columns and "Apartamento" in df_cafe.columns:
        df = df.merge(df_cafe, how="left", on="Apartamento")
        df_filtrado = df[df["Fecha"].dt.date == fecha_seleccionada]
    else:
        st.warning("⚠️ No se pudo asociar el tipo de café. Revisa las columnas en el Excel.")
except Exception as e:
    st.warning(f"No se pudo cargar el archivo de café: {e}")

# Mostrar datos filtrados
st.subheader("Filas completadas")
df_completadas = df_filtrado.dropna(subset=["Inventario ropa e consumibles", "Apartamento"], how="all")
st.dataframe(df_completadas)

# Generar PDF si hay datos
if not df_completadas.empty:
    def generar_pdf(dataframe):
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        elements = []
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Informe de limpieza - {fecha_seleccionada}", styles["Title"]))
        elements.append(Spacer(1, 12))

        table_data = [list(dataframe.columns)] + dataframe.astype(str).values.tolist()
        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('GRID', (0,0), (-1,-1), 0.5, colors.black)
        ]))
        elements.append(table)
        doc.build(elements)
        buffer.seek(0)
        return buffer

    pdf_buffer = generar_pdf(df_completadas)
    st.download_button("📄 Descargar informe en PDF", data=pdf_buffer, file_name=f"informe_{fecha_seleccionada}.pdf")
else:
    st.info("No hay filas completadas para esta fecha.")
