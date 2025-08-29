
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

# Asignar tipo de café directamente
tipos_cafe = {
    "ALFARO": "Tassimo",
    "ALMIRANTE 01": "Tassimo",
    "ALMIRANTE 02": "Tassimo",
    "APOLO 029": "Tassimo",
    "APOLO 180": "Tassimo",
    "APOLO 197": "Tassimo",
    "BENICALAP 01": "Dolce Gusto",
    "BENICALAP 02": "Dolce Gusto",
    "BENICALAP 03": "Dolce Gusto",
    "BENICALAP 04": "Dolce Gusto",
    "BENICALAP 05": "Dolce Gusto",
    "BENICALAP 06": "Dolce Gusto",
    "CADIZ": "Nespresso",
    "CARCAIXENT 01": "Molido",
    "CARCAIXENT 02": "Molido",
    "DENIA 61": "Tassimo",
    "DOLORES ALCAYDE 01": "Tassimo",
    "DOLORES ALCAYDE 02": "Tassimo",
    "DOLORES ALCAYDE 03": "Tassimo",
    "DOLORES ALCAYDE 04": "Tassimo",
    "DOLORES ALCAYDE 05": "Tassimo",
    "DOLORES ALCAYDE 06": "Tassimo",
    "DR.LLUCH": "Tassimo",
    "ERUDITO": "Nespresso",
    "GOZALBO": "Tassimo",
    "HOMERO 01": "Dolce Gusto",
    "HOMERO 02": "Molido",
    "LA ELIANA": "Tassimo",
    "LLADRO Y MALLI 00": "Nespresso",
    "LLADRO Y MALLI 01": "Nespresso",
    "LLADRO Y MALLI 02": "Nespresso",
    "LLADRO Y MALLI 03": "Nespresso",
    "LLADRO Y MALLI 04": "Nespresso",
    "LUIS MERELO 01": "Molido",
    "LUIS MERELO 02": "Molido",
    "LUIS MERELO 03": "Molido",
    "LUIS MERELO 04": "Molido",
    "LUIS MERELO 05": "Molido",
    "LUIS MERELO 06": "Molido",
    "LUIS MERELO 07": "Molido",
    "LUIS MERELO 08": "Molido",
    "LUIS MERELO 09": "Molido",
    "MALILLA 05": "Dolce Gusto",
    "MALILLA 06": "Nespresso",
    "MALILLA 07": "Dolce Gusto",
    "MALILLA 08": "Dolce Gusto",
    "MALILLA 14": "Dolce Gusto",
    "MALILLA 15": "Dolce Gusto",
    "MORAIRA": "Tassimo",
    "OLIVERETA 1": "Tassimo",
    "OLIVERETA 2": "Tassimo",
    "OLIVERETA 3": "Tassimo",
    "OLIVERETA 4": "Tassimo",
    "OLIVERETA 5": "Tassimo",
    "OVE 01": "Tassimo",
    "OVE 02": "Tassimo",
    "PADRE PORTA 01": "Lavazza",
    "PADRE PORTA 02": "Lavazza",
    "PADRE PORTA 03": "Lavazza",
    "PADRE PORTA 04": "Lavazza",
    "PADRE PORTA 05": "Lavazza",
    "PADRE PORTA 06": "Lavazza",
    "PADRE PORTA 07": "Lavazza",
    "PADRE PORTA 08": "Lavazza",
    "PADRE PORTA 09": "Lavazza",
    "PADRE PORTA 10": "Lavazza",
    "PASAJE AYF 01": "Tassimo",
    "PASAJE AYF 02": "Tassimo",
    "PASAJE AYF 03": "Tassimo",
    "PINTOR SALVADOR ABRIL 31": "Nespresso",
    "QUART I": "Nespresso",
    "QUART II": "Nespresso",
    "RETOR A": "Tassimo",
    "RETOR B": "Tassimo",
    "SAN LUIS": "Nespresso",
    "SERRANOS": "Nespresso",
    "SERRERIA 01": "Lavazza",
    "SERRERIA 02": "Lavazza",
    "SERRERIA 03": "Lavazza",
    "SERRERIA 04": "Lavazza",
    "SERRERIA 05": "Lavazza",
    "SERRERIA 06": "Lavazza",
    "SERRERIA 07": "Lavazza",
    "SERRERIA 08": "Lavazza",
    "SERRERIA 09": "Lavazza",
    "SERRERIA 10": "Lavazza",
    "SERRERIA 11": "Lavazza",
    "SERRERIA 12": "Lavazza",
    "SERRERIA 13": "Lavazza",
    "SEVILLA": "Nespresso",
    "TRAFALGAR 01": "Molido",
    "TRAFALGAR 02": "Molido",
    "TRAFALGAR 03": "Molido",
    "TRAFALGAR 04": "Molido",
    "TRAFALGAR 05": "Molido",
    "TRAFALGAR 06": "Molido",
    "TRAFALGAR 07": "Tassimo",
    "TUNDIDORES": "Tassimo",
    "VALLE": "Tassimo",
    "VISITACION": "Tassimo",
    "ZAPATEROS 10-2": "Tassimo",
    "ZAPATEROS 10-6": "Tassimo",
    "ZAPATEROS 10-8": "Tassimo",
    "ZAPATEROS 12-5": "Tassimo"
}

df["Tipo de café"] = df["Apartamento"].map(tipos_cafe)

# Selector de fecha
fecha = st.date_input("Selecciona una fecha")
df_fecha = df[df["Marca temporal"].dt.date == fecha]

# Filtrar columnas clave automáticamente
col_inventario = [col for col in df.columns if "inventario" in col.lower()]
col_apto = [col for col in df.columns if "apartamento" in col.lower()]

# Mostrar resultados
if col_apto and col_inventario:
    df_completadas = df_fecha.dropna(subset=[col_apto[0], col_inventario[0]], how="all")
    st.subheader("🧹 Filas completadas")
    st.dataframe(df_completadas, use_container_width=True)
else:
    st.error("❌ No se encontraron las columnas necesarias.")

# PDF
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

if not df_completadas.empty:
    pdf_buffer = generar_pdf(df_completadas, fecha)
    st.download_button("📄 Descargar PDF", data=pdf_buffer, file_name=f"Informe_{fecha}.pdf", mime="application/pdf")
