import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

st.set_page_config(page_title="Tablero de Resultados", page_icon="📊", layout="wide")

# --- 🔒 BLOQUE DE SEGURIDAD (EL PORTERO) ---
def check_password():
    """Retorna True si el usuario ingresa la clave correcta."""
    
    # 1. Verificar si ya ingresó la clave antes (para no pedirla a cada rato)
    if st.session_state.get("password_correct", False):
        return True

    # 2. Mostrar el campo de contraseña
    st.title("🔒 Acceso Restringido a Investigadores")
    password_input = st.text_input("Ingrese la clave de administrador:", type="password")
    
    # 3. Validar contra los Secrets
    if password_input:
        if password_input == st.secrets["admin"]["password"]:
            st.session_state["password_correct"] = True
            st.success("Acceso concedido.")
            st.rerun()  # Recarga la página para mostrar el contenido
        else:
            st.error("❌ Contraseña incorrecta")
    
    return False

# Si la contraseña no es correcta, detenemos el código aquí.
if not check_password():
    st.stop()

# -------------------------------------------------------
# A PARTIR DE AQUÍ, SOLO VE EL CÓDIGO QUIEN TENGA LA CLAVE
# -------------------------------------------------------

st.title("📊 Resultados en Tiempo Real: Epi-AKI Colombia")

# --- 1. FUNCIÓN PARA CARGAR DATOS ---
@st.cache_data(ttl=60)
def load_data():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if "google_sheets" in st.secrets:
            # Truco para leer JSON sucio si es necesario
            raw_json = st.secrets["google_sheets"]["json_key"]
            try:
                creds_dict = json.loads(raw_json, strict=False)
            except:
                creds_dict = json.loads(raw_json.replace('\n', '\\n'), strict=False)
                
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            sheet = client.open("Resultados_EpiAKI").sheet1
            data = sheet.get_all_values()
            
            # Crear DataFrame manual
            df = pd.DataFrame(data, columns=[
                "Multi-Empleo", "Tipo Centro", "Modelo Staff", 
                "Timing", "Modalidad Real", "Dosis Texto", 
                "Anticoagulación", "Brecha"
            ])
            return df
        else:
            return None
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return None

# --- 2. MOSTRAR MÉTRICAS Y GRÁFICAS ---
df = load_data()

if df is not None and not df.empty:
    
    total = len(df)
    st.metric("Total Encuestados", total)
    st.markdown("---")

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Tipo de Centro")
        fig_centro = px.pie(df, names='Tipo Centro', hole=0.4)
        st.plotly_chart(fig_centro, use_container_width=True)

    with col2:
        st.subheader("Modelo de Staff")
        fig_staff = px.bar(df, x='Modelo Staff', color='Modelo Staff')
        st.plotly_chart(fig_staff, use_container_width=True)

    st.markdown("---")
    
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("Modalidad")
        fig_mod = px.bar(df, x='Modalidad Real', color='Modalidad Real')
        st.plotly_chart(fig_mod, use_container_width=True)
    with col4:
        st.subheader("Anticoagulación")
        fig_anti = px.pie(df, names='Anticoagulación')
        st.plotly_chart(fig_anti, use_container_width=True)

    with st.expander("Ver Datos de Dosis"):
        st.table(df[['Dosis Texto', 'Modalidad Real']])
        
else:
    st.info("Esperando datos... (Si acabas de poner la clave, intenta recargar la página)")
