import pandas as pd
import streamlit as st
from datetime import datetime
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors

# --- Cargar archivo desde Google Drive ---
GOOGLE_DRIVE_URL = "https://drive.google.com/uc?id=1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc"

@st.cache_data
def cargar_datos():
    try:
        df = pd.read_excel(GOOGLE_DRIVE_URL)
        return df
    except Exception as e:
        st.error(f"No se pudo cargar el archivo: {e}")
        return None

# --- UI ---
st.title("📋 Informe desde Google Drive (sin claves)")

fecha_filtrada = st.date_input("Selecciona una fecha")

df = cargar_datos()
if df is not None:
    df.columns = df.columns.str.strip()
    columnas_interes = [
        "Marca temporal", "Apartamento", "Incidencias a realizar", "Inventario ropa e consumibles",
        "Faltantes por entrada", "Faltantes reposiciones café", "Reposiciones sal",
        "Reposiciones té/infusión", "Reposiciones detergente de ropa", "Reposiciones insecticida",
        "Reposiciones gel de ducha", "Reposiciones champú", "Reposiciones jabón de manos",
        "Reposiciones escoba", "Reposiciones lavavajillas", "Reposiciones vinagre",
        "Reposiciones pastilla de descalcificado", "Reposiciones kit de cocina",
        "Reposiciones papel higiénico", "Reposiciones botella de agua", "Otras reposiciones",
        "Detergente finalizado", "Jabón de manos finalizado", "Sal de lavavajillas finalizado",
        "Vinagre finalizado", "Abrillantador finalizado"
    ]

    df = df[columnas_interes]
    df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], errors='coerce')
    df_filtrado = df[df["Marca temporal"].dt.date == fecha_filtrada]

    if not df_filtrado.empty:
        st.subheader("Filas completadas")
        df_completadas = df_filtrado.dropna(subset=["Inventario ropa e consumibles", "Apartamento"], how="all")
        st.dataframe(df_completadas)

        # Generar informe PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        for _, fila in df_completadas.iterrows():
            elements.append(Paragraph(f"<b>Apartamento:</b> {fila['Apartamento']}", styles['Normal']))
            elements.append(Paragraph(f"<b>Fecha:</b> {fila['Marca temporal'].strftime('%d/%m/%Y %H:%M')}", styles['Normal']))
            for col in columnas_interes[2:]:
                valor = fila.get(col)
                if pd.notna(valor):
                    elements.append(Paragraph(f"<b>{col}:</b> {valor}", styles['Normal']))
            elements.append(Spacer(1, 12))

        doc.build(elements)
        buffer.seek(0)
        st.download_button("📄 Descargar informe PDF", data=buffer, file_name="informe_reposiciones.pdf", mime="application/pdf")
    else:
        st.warning("No hay datos para la fecha seleccionada.")
else:
    st.stop()
