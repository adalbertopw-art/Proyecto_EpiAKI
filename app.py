import streamlit as st
import google.generativeai as genai
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import re
import ast # Librería para el "Plan B" de lectura

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Asistente Epi-AKI", page_icon="🩺")

# --- 1. CONEXIÓN CON GOOGLE SHEETS (BLINDADA) ---
def save_to_google_sheets(data_dict):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        if "google_sheets" in st.secrets:
            # PASO CLAVE: Leer el secreto como texto crudo
            raw_json_str = st.secrets["google_sheets"]["json_key"]
            
            # LIMPIEZA DE CREDENCIALES:
            # A veces al pegar en Secrets, los "\n" se vuelven enters reales que rompen el JSON.
            # Este truco lo arregla permitiendo caracteres de control:
            try:
                creds_dict = json.loads(raw_json_str, strict=False)
            except json.JSONDecodeError:
                # Si falla, intentamos una limpieza manual agresiva de la clave privada
                # Esto es común si copiaste el JSON desde un PDF o Word
                clean_str = raw_json_str.replace('\n', '\\n') 
                creds_dict = json.loads(clean_str, strict=False)

            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            client = gspread.authorize(creds)
            
            # Abre la hoja de cálculo
            sheet = client.open("Resultados_EpiAKI").sheet1
            
            # Prepara la fila
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
            st.error("❌ ERROR: No hay secretos configurados.")
            return False
            
    except Exception as e:
        st.error(f"❌ ERROR DE CONEXIÓN CON EXCEL: {e}")
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

try:
    # Usamos 'gemini-3-flash' que es rápido y estable
    model = genai.GenerativeModel(
      model_name="gemini-3-flash-preview",
      generation_config=generation_config,
      system_instruction="""
        **ROL:** Asistente de Investigación Senior del estudio 'Epi-AKI Colombia'.
        **TONO:** Colegial, profesional, pero conversacional (de médico a médico).
        
        **OBJETIVO:** Realizar una entrevista fluida. No parezcas un robot interrogador. Usa frases conectoras como "Entiendo la realidad de su centro", "Dato importante", etc.
        
        **REGLAS DE ORO:**
        1. UNA sola pregunta a la vez. Espera la respuesta.
        2. Si la respuesta es muy corta (ej: "si"), asume el contexto y sigue.
        3. AL FINAL: Genera el JSON estrictamente.

        **GUIÓN DE PREGUNTAS (Adaptativo):**

        **P1 (Contexto Laboral):**
        "Para iniciar y caracterizar la muestra: ¿En su práctica actual ejerce en una única institución o tiene vinculación con múltiples centros (multi-empleo)?"

        **P2 (Centro Principal):**
        "Para las siguientes preguntas, piense solo en su centro de mayor volumen de pacientes. ¿Cómo clasificaría esa institución principal: Hospital Universitario, Público General o Clínica Privada?"

        **P3 (Modelo de Staff - CRÍTICA):**
        "En ese centro, ¿quién lidera la prescripción y programación de la máquina?
        A) Nefrólogo (con apoyo de enfermería renal)
        B) Modelo Mixto (Decisión compartida Nefro/UCI)
        C) Liderado por UCI (Intensivista programa)"

        **P4 (Timing):**
        "En un paciente KDIGO 3 séptico pero estable (sin urgencia vital inmediata): ¿Cuál es su 'trigger' habitual de inicio?
        A) Estrategia Acelerada (Preventiva)
        B) Estrategia Estándar (Espera vigilante / Indicación absoluta)
        C) Guiada por Volumen (Prioriza la sobrecarga hídrica)"

        **P5 (Modalidad Real):**
        "En paciente inestable con vasopresores: ¿Qué modalidad utiliza **realmente** con mayor frecuencia (considerando disponibilidad de insumos/máquinas)?
        A) TRRC (Continua pura)
        B) SLED / PIRR (Híbrida)
        C) Intermitente"

        **P6 (Dosis - ESPECÍFICA):**
        "Respecto a la prescripción:
        - Si usa TRRC: ¿Cuál es su dosis efluente objetivo (ml/kg/h)?
        - Si usa SLED: ¿Cuántas horas dura su sesión estándar?"

        **P7 (Anticoagulación):**
        "Finalmente, ¿cuál es su primera línea de anticoagulación del circuito en ese centro?
        A) Citrato Regional
        B) Heparina No Fraccionada
        C) Sin anticoagulación"

        **OUTPUT FINAL (JSON):**
        Cuando tengas los 7 datos, despídete agradeciendo y genera SOLO este JSON:
        {
          "multi_empleo": "Unico" | "Multiple",
          "tipo_centro_principal": "Universitario" | "Publico" | "Privado",
          "modelo_staff": "Solo_Nefro" | "Mixto_UCI" | "Solo_UCI",
          "timing_strategy": "Acelerada" | "Estandar" | "Volumen",
          "modalidad_real": "TRRC" | "SLED" | "HDI",
          "dosis_data": "Texto exacto del usuario",
          "anticoagulacion": "Citrato" | "Heparina" | "Ninguna"
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
    try:
        st.session_state.chat_session = model.start_chat(history=[])
        # Mensaje de bienvenida CON CONSENTIMIENTO
        welcome_msg = """Bienvenido al Asistente Virtual del Comité de LRA (ASOCOLNEF). 
Esta herramienta recolecta datos anónimos sobre patrones de práctica en Colombia para publicación científica.

¿Autoriza el uso de sus respuestas con fines estadísticos? (Responda SI para iniciar)."""
        
        st.session_state.messages.append({"role": "model", "content": welcome_msg})
        st.session_state.chat_session.history.append({"role": "model", "parts": [welcome_msg]})
    except:
        st.warning("Iniciando sistema...")

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
            # --- ZONA BLINDADA DE LIMPIEZA DE DATOS ---
            try:
                # 1. Capturar el JSON sucio
                json_str = json_match.group(0)
                
                # 2. LIMPIEZA AGRESIVA: Quitamos saltos de línea invisibles que rompen 'heparina'
                clean_json_str = json_str.replace("\n", " ").replace("\r", "").replace("\t", " ")
                
                # 3. Intentar leer con método estricto
                data_dict = json.loads(clean_json_str, strict=False)
                
                # 4. Guardar
                if save_to_google_sheets(data_dict):
                    final_msg = "✅ **¡Datos guardados exitosamente!** Gracias por participar."
                    st.balloons()
                else:
                    final_msg = "⚠️ Datos recibidos, pero hubo un error de conexión con Excel. (Ver detalle arriba)"

                st.chat_message("model").markdown(final_msg)
                st.session_state.messages.append({"role": "model", "content": final_msg})

            except json.JSONDecodeError:
                # PLAN B: Si falla JSON, usamos AST (Lector de Python más tolerante)
                try:
                    # Convertimos valores de JS a Python
                    python_str = json_str.replace("true", "True").replace("false", "False").replace("null", "None")
                    data_dict = ast.literal_eval(python_str)
                    
                    if save_to_google_sheets(data_dict):
                        final_msg = "✅ **¡Datos guardados!** (Recuperación automática)."
                        st.balloons()
                        st.chat_message("model").markdown(final_msg)
                        st.session_state.messages.append({"role": "model", "content": final_msg})
                except Exception as e:
                    st.error(f"Error técnico procesando respuesta: {e}")
                    st.code(json_str) # Mostrar código para depurar si todo falla
            # ------------------------------------------

        else:
            # Conversación normal
            st.chat_message("model").markdown(text_response)
            st.session_state.messages.append({"role": "model", "content": text_response})
            
    except Exception as e:
        st.error(f"Error de conexión con la IA: {e}")
