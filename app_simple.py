import streamlit as st
import pandas as pd

st.set_page_config(page_title="Informe desde Google Drive", page_icon="📋")

st.title("📋 Informe desde Google Drive (sin claves)")

# URL del archivo CSV exportado desde Google Sheets
google_sheet_url = "https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/export?format=csv"

try:
    df = pd.read_csv(google_sheet_url)
    st.success("✅ Archivo cargado correctamente.")
    st.dataframe(df)
except Exception as e:
    st.error(f"❌ No se pudo cargar el archivo: {e}")
