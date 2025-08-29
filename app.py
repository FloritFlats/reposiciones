import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# Título
st.set_page_config(page_title="Informe de Reposiciones")
st.title("📋 Informe de Reposiciones")

# --- AUTENTICACIÓN CON GOOGLE SHEETS (usando secrets)
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Cargar credenciales desde el secreto seguro
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)

# Autenticación con gspread
client = gspread.authorize(creds)

# --- LECTURA DEL GOOGLE SHEET
spreadsheet_id = "1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc"  # tu ID
sheet = client.open_by_key(spreadsheet_id)
worksheet = sheet.sheet1  # puedes cambiarlo si usas otra pestaña

# Convertir a DataFrame
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# --- INTERFAZ DE FILTRADO
st.subheader("📅 Filtrar por fecha")
fechas = df["Marca temporal"].unique()
fecha_seleccionada = st.selectbox("Selecciona una fecha:", fechas)

# Filtrar DataFrame
df_filtrado = df[df["Marca temporal"] == fecha_seleccionada]

# Mostrar resultados
st.subheader("📊 Datos filtrados")
st.dataframe(df_filtrado)


