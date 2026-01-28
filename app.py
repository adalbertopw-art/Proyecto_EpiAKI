{\rtf1\ansi\ansicpg1252\cocoartf2866
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import streamlit as st\
import google.generativeai as genai\
import gspread\
from oauth2client.service_account import ServiceAccountCredentials\
import json\
import re\
\
# --- CONFIGURACI\'d3N DE LA P\'c1GINA ---\
st.set_page_config(page_title="Asistente Epi-AKI", page_icon="\uc0\u55358 \u56954 ")\
\
# --- 1. CONEXI\'d3N CON GOOGLE SHEETS (BASE DE DATOS) ---\
def save_to_google_sheets(data_dict):\
    try:\
        # Configuraci\'f3n de credenciales (Se explican en el tutorial abajo)\
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]\
        # Cargamos las credenciales desde los 'Secretos' de Streamlit\
        creds_dict = json.loads(st.secrets["google_sheets"]["json_key"])\
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)\
        client = gspread.authorize(creds)\
        \
        # Abre la hoja de c\'e1lculo por su nombre\
        sheet = client.open("Resultados_EpiAKI").sheet1\
        \
        # Prepara la fila a insertar (ordenada seg\'fan las columnas)\
        row = [\
            data_dict.get("multi_empleo", ""),\
            data_dict.get("tipo_centro_principal", ""),\
            data_dict.get("modelo_staff", ""),\
            data_dict.get("timing_strategy", ""),\
            data_dict.get("modalidad_real", ""),\
            data_dict.get("dosis_data", ""),\
            data_dict.get("anticoagulacion", ""),\
            data_dict.get("brecha_recursos", False)\
        ]\
        sheet.append_row(row)\
        return True\
    except Exception as e:\
        st.error(f"Error guardando datos: \{e\}")\
        return False\
\
# --- 2. CONFIGURACI\'d3N DE GEMINI (CEREBRO) ---\
# Usamos st.secrets para no exponer la API Key\
genai.configure(api_key=st.secrets["gemini"]["api_key"])\
\
# Configuraci\'f3n del modelo (Usamos 1.5 Pro por su capacidad l\'f3gica)\
generation_config = \{\
  "temperature": 0.2, # Baja temperatura para ser m\'e1s riguroso\
  "top_p": 0.95,\
  "top_k": 64,\
  "max_output_tokens": 8192,\
\}\
\
model = genai.GenerativeModel(\
  model_name="gemini-1.5-pro", # O "gemini-1.5-flash" si quiere m\'e1s velocidad\
  generation_config=generation_config,\
  system_instruction="""\
    **ROL:** Asistente de Investigaci\'f3n IA del estudio 'Epi-AKI Colombia'.\
    **OBJETIVO:** Realizar entrevista estructurada a nefr\'f3logos.\
    \
    **REGLAS:**\
    1. Una sola pregunta a la vez.\
    2. Al final, genera SOLO un bloque JSON puro con los resultados.\
    \
    **CUESTIONARIO RESUMIDO (L\'f3gica Interna):**\
    1. Multi-empleo (Unico/Multiple).\
    2. Tipo de Centro Principal (Univ/Publico/Privado).\
    3. Modelo Staff (Nefro/Enfermeria/Mixto).\
    4. Timing LRA (Acelerada/Estandar/Volumen).\
    5. Modalidad Real (TRRC/SLED/HDI).\
    6. Dosis (Texto breve).\
    7. Anticoagulaci\'f3n (Citrato/Heparina/Nada).\
\
    **OUTPUT FINAL:**\
    Cuando tengas los 7 datos, desp\'eddete y genera INMEDIATAMENTE este JSON:\
    \{\
      "multi_empleo": "...",\
      "tipo_centro_principal": "...",\
      "modelo_staff": "...",\
      "timing_strategy": "...",\
      "modalidad_real": "...",\
      "dosis_data": "...",\
      "anticoagulacion": "...",\
      "brecha_recursos": true/false\
    \}\
  """\
)\
\
# --- 3. INTERFAZ DE CHAT ---\
\
st.title("\uc0\u55358 \u56954  Estudio Epi-AKI Colombia")\
st.markdown("Comit\'e9 de LRA - ASOCOLNEF")\
\
# Inicializar historial de chat\
if "messages" not in st.session_state:\
    st.session_state.messages = []\
    # Iniciar el chat con el modelo\
    st.session_state.chat_session = model.start_chat(history=[])\
    # Mensaje de bienvenida del bot (Simulado para iniciar r\'e1pido)\
    welcome_msg = "Bienvenido colega. Soy el asistente virtual del estudio. Para iniciar: \'bfEjerce usted en una \'fanica instituci\'f3n o en m\'faltiples centros?"\
    st.session_state.messages.append(\{"role": "model", "content": welcome_msg\})\
    st.session_state.chat_session.history.append(\{"role": "model", "parts": [welcome_msg]\})\
\
# Mostrar mensajes anteriores\
for message in st.session_state.messages:\
    with st.chat_message(message["role"]):\
        st.markdown(message["content"])\
\
# Capturar input del usuario\
if prompt := st.chat_input("Escriba su respuesta aqu\'ed..."):\
    # 1. Mostrar mensaje usuario\
    st.chat_message("user").markdown(prompt)\
    st.session_state.messages.append(\{"role": "user", "content": prompt\})\
\
    # 2. Enviar a Gemini\
    try:\
        response = st.session_state.chat_session.send_message(prompt)\
        text_response = response.text\
        \
        # 3. Detectar si hay JSON (Fin de encuesta)\
        json_match = re.search(r"\\\{.*\\\}", text_response, re.DOTALL)\
        \
        if json_match:\
            # Si hay JSON, es el final. Extraemos los datos.\
            json_str = json_match.group(0)\
            data_dict = json.loads(json_str)\
            \
            # Guardamos en Google Sheets\
            if save_to_google_sheets(data_dict):\
                final_msg = "\uc0\u9989  **\'a1Datos guardados exitosamente!** Gracias por participar en el estudio Epi-AKI."\
                st.balloons()\
            else:\
                final_msg = "\uc0\u9888 \u65039  Hubo un error de conexi\'f3n, pero gracias por responder."\
            \
            # Mostramos mensaje final limpio (sin el JSON t\'e9cnico)\
            st.chat_message("model").markdown(final_msg)\
            st.session_state.messages.append(\{"role": "model", "content": final_msg\})\
            \
        else:\
            # Si NO hay JSON, sigue la conversaci\'f3n normal\
            st.chat_message("model").markdown(text_response)\
            st.session_state.messages.append(\{"role": "model", "content": text_response\})\
            \
    except Exception as e:\
        st.error(f"Error de conexi\'f3n: \{e\}")}