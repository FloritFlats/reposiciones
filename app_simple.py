
import streamlit as st
import pandas as pd
from datetime import datetime
from google.oauth2 import service_account
import gspread
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import tempfile

st.set_page_config(page_title="Informe desde Google Drive (sin claves)", layout="wide")

st.markdown("### 📝 Informe desde Google Drive (sin claves)")

# Autenticación con Google Sheets
try:
    credentials = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    gc = gspread.authorize(credentials)

    # ID de la hoja
    sheet_id = "1i0iM2S6xrd9hbfZ0lGnU6UHV813cFPgY2CCnr1vbrcc"
    sheet_name = "Respuestas limpieza"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"

    df = pd.read_csv(url)

    # Renombrar columnas clave si existen
    if "Marca temporal" in df.columns:
        df = df.rename(columns={"Marca temporal": "Marca temporal"})
    if "Apartamento" not in df.columns:
        st.warning("No se encuentra la columna 'Apartamento' en el archivo.")
        st.stop()

    # Convertir fechas
    df["Marca temporal"] = pd.to_datetime(df["Marca temporal"], errors="coerce")

    # Leer café por apartamento
    try:
        cafe_df = pd.read_excel("Cafe por propiedad.xlsx")
        cafe_df.columns = cafe_df.columns.str.strip()
        cafe_df = cafe_df.rename(columns={cafe_df.columns[0]: "Apartamento", cafe_df.columns[1]: "Tipo de café"})
        df = df.merge(cafe_df, how="left", on="Apartamento")
    except Exception as e:
        st.warning("⚠ No se pudo asociar el tipo de café. Revisa las columnas en el Excel.")

    # Filtro de fecha
    fecha = st.date_input("Selecciona una fecha", value=datetime.today())
    df_filtrado = df[df["Marca temporal"].dt.date == fecha]

    # Mostrar tabla de filas completadas
    columnas_utiles = [
        "Marca temporal", "Apartamento", "Incidencias a realizar", "Inventario ropa e consumibles",
        "Faltantes por entrada", "Faltantes reposiciones café", "Reposiciones sal", "Reposiciones té/infusión",
        "Reposiciones detergente de ropa", "Reposiciones insecticida", "Reposiciones gel de ducha",
        "Reposiciones champú", "Reposiciones jabón de manos", "Reposiciones escoba", "Reposiciones lavavajillas",
        "Reposiciones vinagre", "Reposiciones pastilla de descalcificado", "Reposiciones kit de cocina",
        "Reposiciones papel higiénico", "Reposiciones botella de agua", "Otras reposiciones",
        "Detergente finalizado", "Jabón de manos finalizado", "Sal de lavavajillas finalizado",
        "Vinagre finalizado", "Abrillantador finalizado", "Tipo de café"
    ]
    columnas_existentes = [col for col in columnas_utiles if col in df_filtrado.columns]
    df_completadas = df_filtrado.dropna(subset=["Inventario ropa e consumibles", "Apartamento"], how="all")

    st.markdown("## 🧹 Filas completadas")
    st.dataframe(df_completadas[columnas_existentes], use_container_width=True)

    # Generar PDF
    if not df_completadas.empty:
        def generar_pdf(dataframe):
            buffer = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            doc = SimpleDocTemplate(buffer.name, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [Paragraph("Informe Diario de Limpieza", styles["Title"]), Spacer(1, 12)]

            for i, row in dataframe.iterrows():
                apartamento = row.get("Apartamento", "Sin nombre")
                fecha_limpieza = row.get("Marca temporal", "")
                fecha_limpieza = fecha_limpieza.strftime("%Y-%m-%d %H:%M") if pd.notnull(fecha_limpieza) else ""
                elements.append(Paragraph(f"Apartamento: {apartamento} - {fecha_limpieza}", styles["Heading3"]))
                tabla_data = []
                for col in columnas_existentes:
                    valor = row.get(col, "")
                    tabla_data.append([col, str(valor)])
                table = Table(tabla_data, colWidths=[200, 300])
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                elements.append(table)
                elements.append(Spacer(1, 12))
            doc.build(elements)
            return buffer.name

        if st.button("📄 Descargar informe en PDF"):
            path_pdf = generar_pdf(df_completadas)
            with open(path_pdf, "rb") as f:
                st.download_button(
                    label="📥 Descargar PDF",
                    data=f,
                    file_name=f"Informe_Limpieza_{fecha}.pdf",
                    mime="application/pdf"
                )
    else:
        st.info("No hay filas completas para la fecha seleccionada.")

except Exception as e:
    st.error(f"No se pudo cargar el archivo: {e}")
