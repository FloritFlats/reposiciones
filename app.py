import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="App Reposiciones", layout="wide")
st.title("📋 Informe de Reposiciones")

# Conectar con Google Sheets
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds = Credentials.from_service_account_file("credenciales.json", scopes=scope)
gc = gspread.authorize(creds)

# ID del documento y nombre de la hoja
sheet_id = "1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc"
sheet_name = "Hoja 1"  # Asegúrate que tu hoja se llama exactamente así

# Leer los datos
sh = gc.open_by_key(sheet_id)
worksheet = sh.worksheet(sheet_name)
data = worksheet.get_all_records()
df = pd.DataFrame(data)

# Mostrar en pantalla
st.subheader("📊 Datos desde Google Sheets")
st.dataframe(df)

