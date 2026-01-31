import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

st.set_page_config(page_title="Tablero de Resultados", page_icon="📊", layout="wide")

st.title("📊 Resultados en Tiempo Real: Epi-AKI Colombia")

# --- 1. FUNCIÓN PARA CARGAR DATOS DESDE GOOGLE SHEETS ---
@st.cache_data(ttl=60) # Actualiza los datos cada 60 segundos, no antes (ahorra recursos)
def load_data():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Leemos los secretos igual que en la app principal
        if "google_sheets" in st.secrets:
            creds_dict = json.loads(st.secrets["google_sheets"]["json_key"], strict=False)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            # Abrimos la hoja
            sheet = client.open("Resultados_EpiAKI").sheet1
            
            # Obtenemos todos los valores
            data = sheet.get_all_values()
            
            # Convertimos a DataFrame de Pandas
            # Asumimos que NO tienes encabezados en la fila 1, así que los ponemos manual:
            df = pd.DataFrame(data, columns=[
                "Multi-Empleo", 
                "Tipo Centro", 
                "Modelo Staff", 
                "Timing", 
                "Modalidad Real", 
                "Dosis Texto", 
                "Anticoagulación", 
                "Brecha"
            ])
            return df
        else:
            return None
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None

# --- 2. MOSTRAR MÉTRICAS ---
df = load_data()

if df is not None and not df.empty:
    
    # KPI Principal: Número de encuestados
    total_participantes = len(df)
    st.metric(label="Total de Nefrólogos Encuestados", value=total_participantes)
    
    st.markdown("---")

    # --- 3. GENERACIÓN DE GRÁFICAS ---
    
    # Fila 1: Centro y Staff
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tipo de Centro")
        fig_centro = px.pie(df, names='Tipo Centro', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_centro, use_container_width=True)

    with col2:
        st.subheader("Modelo de Staff LRA")
        fig_staff = px.bar(df, x='Modelo Staff', color='Modelo Staff', text_auto=True)
        st.plotly_chart(fig_staff, use_container_width=True)

    st.markdown("---")

    # Fila 2: Modalidad y Anticoagulación
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Modalidad Real Utilizada")
        # Contamos frecuencias para ordenar bonito
        conteo_mod = df['Modalidad Real'].value_counts().reset_index()
        conteo_mod.columns = ['Modalidad', 'Conteo']
        fig_mod = px.bar(conteo_mod, x='Modalidad', y='Conteo', color='Modalidad', text_auto=True)
        st.plotly_chart(fig_mod, use_container_width=True)

    with col4:
        st.subheader("Anticoagulación")
        fig_anti = px.pie(df, names='Anticoagulación', color_discrete_sequence=px.colors.qualitative.Pastel)
        st.plotly_chart(fig_anti, use_container_width=True)

    st.markdown("---")
    
    # Sección de Texto (Dosis)
    st.subheader("📝 Análisis de Dosis (Respuestas Texto)")
    with st.expander("Ver respuestas detalladas sobre Dosis"):
        st.table(df[['Dosis Texto', 'Modalidad Real']])

    # --- 4. DESCARGAR DATA ---
    st.markdown("### 📥 Exportar Datos")
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Descargar Tabla en CSV (Para Excel)",
        data=csv,
        file_name='resultados_epiaki.csv',
        mime='text/csv',
    )

else:
    st.warning("No hay datos todavía o hubo un error de conexión.")
