import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

# Título
st.set_page_config(page_title="Informe de Reposiciones")
st.title("📋 Informe de Reposiciones")

import streamlit as st
import pandas as pd
import gspread
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Informe de Reposiciones")
st.title("📋 Informe de Reposiciones")

# Conexión con Google Sheets usando secretos seguros
scope = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
client = gspread.authorize(creds)

# ID del documento
spreadsheet_id = "1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc"
sheet = client.open_by_key(spreadsheet_id)
worksheet = sheet.sheet1  # Puedes cambiar el nombre si usas otra pestaña
data = worksheet.get_all_records()

df = pd.DataFrame(data)
st.subheader("📊 Datos desde Google Sheets")
st.dataframe(df)
