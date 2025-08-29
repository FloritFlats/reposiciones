
import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Configuración
st.set_page_config(page_title="Informe Reposiciones", layout="wide")
st.title("📋 Informe desde Google Drive")

# Autenticación con Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

# Cargar datos desde Google Sheets
sheet_url = "https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/edit?usp=sharing"
sheet = client.open_by_url(sheet_url)
worksheet = sheet.sheet1
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Convertir fechas
df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], errors="coerce")

# Cargar archivo café por propiedad
cafe_df = pd.read_excel("Cafe por propiedad.xlsx")
if "Apartamento" in cafe_df.columns and "Tipo de café" in cafe_df.columns:
    df = df.merge(cafe_df, how="left", on="Apartamento")
else:
    st.warning("⚠️ No se pudo asociar el tipo de café. Revisa las columnas en el Excel.")

# Selector de fecha
fecha_seleccionada = st.date_input("Selecciona una fecha")
df_filtrado = df[df["Marca temporal"].dt.date == fecha_seleccionada]

# Filtrar filas completas
columnas_clave = ["Inventario ropa e consumibles", "Apartamento"]
try:
    df_completadas = df_filtrado.dropna(subset=columnas_clave, how="all")
except KeyError as e:
    st.error(f"❌ Error: {e}")
    st.stop()

# Mostrar resultados
st.subheader("Filas completadas")
st.dataframe(df_completadas)

# Función para generar PDF
def generar_pdf(df, fecha):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"Informe de Reposiciones – {fecha.strftime('%d/%m/%Y')}", styles["Title"]))
    elements.append(Spacer(1, 12))

    for i, row in df.iterrows():
        elementos = [f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])]
        table_data = [[e] for e in elementos]
        table = Table(table_data, colWidths=[500])
        table.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
                                   ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey)]))
        elements.append(table)
        elements.append(Spacer(1, 24))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# Botón de descarga
if not df_completadas.empty:
    pdf_buffer = generar_pdf(df_completadas, fecha_seleccionada)
    st.download_button("📄 Descargar informe PDF", data=pdf_buffer, file_name=f"Informe_{fecha_seleccionada}.pdf")
