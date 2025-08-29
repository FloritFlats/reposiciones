import streamlit as st
import pandas as pd

st.set_page_config(page_title="Informe desde Drive", layout="wide")
st.title("📋 Informe desde Google Drive (sin claves)")

# ID del archivo público en Google Drive
file_id = "1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc"  # <-- tu archivo
url = f"https://docs.google.com/spreadsheets/d/1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc/edit?gid=1040407590#gid=1040407590"

try:
    df = pd.read_excel(url)
    st.success("✅ Datos cargados correctamente desde Google Drive")
    st.dataframe(df)
except Exception as e:
    st.error(f"❌ No se pudo cargar el archivo: {e}")
