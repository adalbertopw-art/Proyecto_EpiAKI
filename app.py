import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Asistente Epi-AKI", page_icon="🩺")

# --- 1. CONEXIÓN CON GOOGLE SHEETS (BASE DE DATOS) ---
def save_to_google_sheets(data_dict):
    try:
        # Configuración de credenciales
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Cargamos las credenciales desde los 'Secretos' de Streamlit
        if "google_sheets" in st.secrets:
            creds_dict = json.loads(st.secrets["google_sheets"]["json_key"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            # Abre la hoja de cálculo por su nombre
            # IMPORTANTE: Asegurate que tu hoja en Drive se llame EXACTAMENTE asi:
            sheet = client.open("Resultados_EpiAKI").sheet1
            
            # Prepara la fila a insertar
            row = [
                data_dict.get("multi_empleo", ""),
                data_dict.get("tipo_centro_principal", ""),
                data_dict.get("modelo_staff", ""),
                data_dict.get("timing_strategy", ""),
                data_dict.get("modalidad_real", ""),
                data_dict.get("dosis_data", ""),
                data_dict.get("anticoagulacion", ""),
                data_dict.get("brecha_recursos", False)
            ]
            sheet.append_row(row)
            return True
        else:
            st.error("No se encontraron credenciales de Google Sheets en Secrets.")
            return False
            
    except Exception as e:
        st.error(f"Error guardando datos: {e}")
        return False

# --- 2. CONFIGURACIÓN DE GEMINI (CEREBRO) ---
if "gemini" in st.secrets:
    genai.configure(api_key=st.secrets["gemini"]["api_key"])
else:
    st.error("Falta la API Key de Gemini en los Secrets.")

# Configuración del modelo
generation_config = {
  "temperature": 0.2,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
}

# Usamos Try/Except por si la API Key falla
try:
    model = genai.GenerativeModel(
      model_name="gemini-3-flash-preview",
      generation_config=generation_config,
      system_instruction="""
        **ROL:** Asistente de Investigación IA del estudio 'Epi-AKI Colombia'.
        **OBJETIVO:** Realizar entrevista estructurada a nefrólogos.
        
        **REGLAS:**
        1. Una sola pregunta a la vez.
        2. Al final, genera SOLO un bloque JSON puro con los resultados.
        
        **CUESTIONARIO RESUMIDO:**
        1. Multi-empleo (Unico/Multiple).
        2. Tipo de Centro Principal (Univ/Publico/Privado).
        3. Modelo Staff (Nefro/Enfermeria/Mixto).
        4. Timing LRA (Acelerada/Estandar/Volumen).
        5. Modalidad Real (TRRC/SLED/HDI).
        6. Dosis (Texto breve).
        7. Anticoagulación (Citrato/Heparina/Nada).

        **OUTPUT FINAL (JSON STRICT):**
        {
          "multi_empleo": "String",
          "tipo_centro_principal": "String",
          "modelo_staff": "String",
          "timing_strategy": "String",
          "modalidad_real": "String",
          "dosis_data": "String",
          "anticoagulacion": "String",
          "brecha_recursos": Boolean
        }
      """
    )
except Exception as e:
    st.error(f"Error configurando Gemini: {e}")

# --- 3. INTERFAZ DE CHAT ---

st.title("🩺 Estudio Epi-AKI Colombia")
st.markdown("Comité de LRA - ASOCOLNEF")

# Inicializar historial de chat
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Iniciar el chat con el modelo
    try:
        st.session_state.chat_session = model.start_chat(history=[])
        # Mensaje de bienvenida inicial (CONSENTIMIENTO)
        welcome_msg = """Bienvenido al Asistente Virtual del Comité de LRA (ASOCOLNEF). 
Esta herramienta recolecta datos anónimos sobre patrones de práctica en Colombia para publicación científica.

¿Autoriza el uso de sus respuestas con fines estadísticos? (Responda SI para iniciar)."""
        st.session_state.messages.append({"role": "model", "content": welcome_msg})
        st.session_state.chat_session.history.append({"role": "model", "parts": [welcome_msg]})
    except:
        st.warning("Esperando configuración correcta de secretos...")

# Mostrar mensajes anteriores
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Capturar input del usuario
if prompt := st.chat_input("Escriba su respuesta aquí..."):
    # Mostrar mensaje usuario
    st.chat_message("user").markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Enviar a Gemini
    try:
        response = st.session_state.chat_session.send_message(prompt)
        text_response = response.text
        
        # Detectar si hay JSON (Fin de encuesta)
        json_match = re.search(r"\{.*\}", text_response, re.DOTALL)
        
        if json_match:
            try:
                # Limpiar y parsear JSON
                json_str = json_match.group(0)
                data_dict = json.loads(json_str, strict=False)
                
                # Guardar en Google Sheets
                if save_to_google_sheets(data_dict):
                    final_msg = "✅ **¡Datos guardados exitosamente!** Gracias por participar."
                    st.balloons()
                else:
                    final_msg = "⚠️ Hubo un error de conexión, pero gracias por responder."
                
                # Mostrar mensaje final
                st.chat_message("model").markdown(final_msg)
                st.session_state.messages.append({"role": "model", "content": final_msg})
            except json.JSONDecodeError:
                 # Si el JSON viene mal formado, mostramos el texto normal
                st.chat_message("model").markdown(text_response)
                st.session_state.messages.append({"role": "model", "content": text_response})

        else:
            # Conversación normal
            st.chat_message("model").markdown(text_response)
            st.session_state.messages.append({"role": "model", "content": text_response})
            
    except Exception as e:
        st.error(f"Error de conexión con la IA: {e}")
