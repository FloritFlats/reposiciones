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

# Configuración inicial
st.set_page_config(page_title="Informe Reposiciones", layout="wide")
st.title("📋 Informe desde Google Sheets")

# Autenticación con Google
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
client = gspread.authorize(creds)

# Cargar datos
sheet_url = "https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/edit?usp=sharing"
sheet = client.open_by_url(sheet_url)
worksheet = sheet.sheet1
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Mostrar columnas originales para depurar
st.markdown("### 🧾 Columnas originales detectadas:")
st.write(df.columns.tolist())

# Renombrar columnas si están mal escritas
df.columns = df.columns.str.strip()

# Convertir fecha
if "Marca temporal" in df.columns:
    df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], errors="coerce")
else:
    st.error("❌ No se encuentra la columna 'Marca temporal'.")
    st.stop()

# Leer archivo de café y asociar
try:
    cafe_df = pd.read_excel("Cafe por propiedad.xlsx")
    cafe_df.columns = cafe_df.columns.str.strip()
    col_apto = [col for col in cafe_df.columns if "apartamento" in col.lower()]
    col_cafe = [col for col in cafe_df.columns if "café" in col.lower() or "cafe" in col.lower()]
    if col_apto and col_cafe:
        cafe_df = cafe_df.rename(columns={col_apto[0]: "Apartamento", col_cafe[0]: "Tipo de café"})
        df = df.merge(cafe_df, how="left", on="Apartamento")
    else:
        st.warning("⚠️ Archivo de café encontrado pero columnas no válidas.")
except Exception as e:
    st.warning(f"⚠️ No se pudo asociar el tipo de café: {e}")

# Selector de fecha
fecha = st.date_input("Selecciona una fecha")
df_fecha = df[df["Marca temporal"].dt.date == fecha]

# Intentar encontrar la columna de inventario
col_inventario = [col for col in df.columns if "inventario" in col.lower()]
if not col_inventario:
    st.error("❌ No se encontró ninguna columna que contenga la palabra 'inventario'.")
    st.stop()

col_apto = [col for col in df.columns if "apartamento" in col.lower()]
if not col_apto:
    st.error("❌ No se encontró ninguna columna que contenga 'Apartamento'.")
    st.stop()

# Mostrar tabla de filas completadas
df_completadas = df_fecha.dropna(subset=[col_inventario[0], col_apto[0]], how="all")
st.subheader("🧹 Filas completadas")
st.dataframe(df_completadas, use_container_width=True)

# Función para generar PDF
def generar_pdf(df, fecha):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [Paragraph(f"Informe de Reposiciones – {fecha.strftime('%d/%m/%Y')}", styles["Title"]), Spacer(1, 12)]
    for _, row in df.iterrows():
        fila = [f"{col}: {row[col]}" for col in df.columns if pd.notna(row[col])]
        table = Table([[f] for f in fila], colWidths=[500])
        table.setStyle(TableStyle([("BOX", (0,0), (-1,-1), 0.25, colors.grey),
                                   ("INNERGRID", (0,0), (-1,-1), 0.25, colors.grey)]))
        elements.append(table)
        elements.append(Spacer(1, 12))
    doc.build(elements)
    buffer.seek(0)
    return buffer

# Descargar PDF
if not df_completadas.empty:
    pdf_buffer = generar_pdf(df_completadas, fecha)
    st.download_button("📄 Descargar PDF", data=pdf_buffer, file_name=f"Informe_{fecha}.pdf", mime="application/pdf")
