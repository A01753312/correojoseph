import streamlit as st
import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
import json
import pandas as pd
import time

# Configuración de la página
st.set_page_config(page_title="Gmail API App", page_icon="📧")

st.title("📧 Aplicación de Gmail")

# Scopes necesarios para Gmail
SCOPES = ['https://www.googleapis.com/auth/gmail.send',
          'https://www.googleapis.com/auth/gmail.readonly']

# Función para crear el flujo de autenticación
def get_flow():
    client_config = {
        "web": {
            "client_id": st.secrets.get("client_id", ""),
            "client_secret": st.secrets.get("client_secret", ""),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [st.secrets.get("redirect_uri", "http://localhost:8501")]
        }
    }
    
    flow = Flow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri=client_config["web"]["redirect_uris"][0]
    )
    return flow

# Función para enviar correo
def send_email(service, to, subject, body):
    try:
        message = MIMEText(body)
        message['to'] = to
        message['subject'] = subject
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        send_message = service.users().messages().send(
            userId="me",
            body={'raw': raw}
        ).execute()
        
        return True, f"Mensaje enviado! ID: {send_message['id']}"
    except Exception as e:
        return False, f"Error: {str(e)}"

# Función para listar mensajes
def list_messages(service, max_results=10):
    try:
        results = service.users().messages().list(
            userId='me',
            maxResults=max_results
        ).execute()
        
        messages = results.get('messages', [])
        return messages
    except Exception as e:
        st.error(f"Error al listar mensajes: {str(e)}")
        return []

# Verificar si hay credenciales guardadas
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

# Obtener código de la URL si existe
query_params = st.query_params
auth_code = query_params.get("code", None)

# Si hay código en la URL, autenticar automáticamente
if auth_code and st.session_state.credentials is None:
    try:
        flow = get_flow()
        flow.fetch_token(code=auth_code)
        st.session_state.credentials = flow.credentials
        # Limpiar parámetros de la URL
        st.query_params.clear()
        st.success("¡Autenticación exitosa!")
        st.rerun()
    except Exception as e:
        st.error(f"Error en la autenticación: {str(e)}")

# Proceso de autenticación
if st.session_state.credentials is None:
    st.header("🔐 Autenticación con Google")
    st.write("Para usar esta aplicación, necesitas autenticarte con tu cuenta de Gmail.")
    
    # Generar URL de autenticación
    try:
        flow = get_flow()
        auth_url, _ = flow.authorization_url(prompt='consent')
        
        # Mostrar botón que redirige directamente
        st.markdown(f"""
        <a href="{auth_url}" target="_self">
            <button style="
                background-color: #4285f4;
                color: white;
                padding: 10px 24px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                font-size: 16px;
            ">
                🔐 Iniciar sesión con Google
            </button>
        </a>
        """, unsafe_allow_html=True)
        
    except Exception as e:
        st.error(f"Error al crear el flujo de autenticación: {str(e)}")
        st.info("Asegúrate de tener configurado el archivo secrets.toml con client_id, client_secret y redirect_uri")

else:
    # Usuario autenticado - mostrar funcionalidades
    st.success("✅ Autenticado correctamente")
    
    if st.button("Cerrar sesión"):
        st.session_state.credentials = None
        st.rerun()
    
    # Crear el servicio de Gmail
    service = build('gmail', 'v1', credentials=st.session_state.credentials)
    
    # Tabs para diferentes funcionalidades
    tab1, tab2, tab3 = st.tabs(["📤 Enviar Email", "📊 Enviar desde Excel", "📬 Ver Emails"])
    
    with tab1:
        st.header("Enviar un correo electrónico")
        
        to_email = st.text_input("Para:", placeholder="ejemplo@gmail.com")
        subject = st.text_input("Asunto:", placeholder="Asunto del correo")
        body = st.text_area("Mensaje:", placeholder="Escribe tu mensaje aquí...", height=200)
        
        if st.button("Enviar Correo"):
            if to_email and subject and body:
                success, message = send_email(service, to_email, subject, body)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.warning("Por favor completa todos los campos")
    
    with tab2:
        st.header("📊 Enviar correos masivos desde Excel")
        st.write("Sube un archivo Excel con las columnas: `email`, `asunto`, y `mensaje`")
        
        # Mostrar ejemplo
        with st.expander("📝 Ver formato de ejemplo"):
            ejemplo_df = pd.DataFrame({
                'email': ['ejemplo1@gmail.com', 'ejemplo2@gmail.com'],
                'asunto': ['Asunto 1', 'Asunto 2'],
                'mensaje': ['Mensaje para el primer contacto', 'Mensaje para el segundo contacto']
            })
            st.dataframe(ejemplo_df)
            st.info("Tu archivo Excel debe tener estas tres columnas exactamente.")
        
        # Subir archivo
        uploaded_file = st.file_uploader("Sube tu archivo Excel", type=['xlsx', 'xls'])
        
        if uploaded_file is not None:
            try:
                # Leer el archivo Excel
                df = pd.read_excel(uploaded_file)
                
                # Verificar que tenga las columnas necesarias
                required_columns = ['email', 'asunto', 'mensaje']
                if not all(col in df.columns for col in required_columns):
                    st.error(f"El archivo debe contener las columnas: {', '.join(required_columns)}")
                else:
                    st.success(f"✅ Archivo cargado correctamente: {len(df)} correos encontrados")
                    
                    # Mostrar vista previa
                    st.write("Vista previa de los correos:")
                    st.dataframe(df)
                    
                    # Botón para enviar
                    if st.button("📤 Enviar todos los correos"):
                        progress_bar = st.progress(0)
                        status_text = st.empty()
                        
                        enviados = 0
                        errores = 0
                        
                        for idx, row in df.iterrows():
                            email = str(row['email']).strip()
                            asunto = str(row['asunto']).strip()
                            mensaje = str(row['mensaje']).strip()
                            
                            status_text.text(f"Enviando a {email}...")
                            
                            success, msg = send_email(service, email, asunto, mensaje)
                            
                            if success:
                                enviados += 1
                            else:
                                errores += 1
                                st.warning(f"Error enviando a {email}: {msg}")
                            
                            # Actualizar barra de progreso
                            progress_bar.progress((idx + 1) / len(df))
                            
                            # Pequeña pausa para no sobrecargar la API
                            time.sleep(0.5)
                        
                        status_text.empty()
                        progress_bar.empty()
                        
                        st.success(f"✅ Proceso completado: {enviados} enviados, {errores} errores")
                        
            except Exception as e:
                st.error(f"Error al procesar el archivo: {str(e)}")
    
    with tab3:
        st.header("Tus últimos correos")
        
        num_messages = st.slider("Número de mensajes a mostrar:", 1, 20, 10)
        
        if st.button("Cargar mensajes"):
            with st.spinner("Cargando mensajes..."):
                messages = list_messages(service, num_messages)
                
                if messages:
                    st.write(f"Mostrando {len(messages)} mensajes:")
                    for msg in messages:
                        try:
                            msg_data = service.users().messages().get(
                                userId='me',
                                id=msg['id'],
                                format='metadata',
                                metadataHeaders=['From', 'Subject', 'Date']
                            ).execute()
                            
                            headers = msg_data.get('payload', {}).get('headers', [])
                            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'Sin asunto')
                            from_email = next((h['value'] for h in headers if h['name'] == 'From'), 'Desconocido')
                            date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Sin fecha')
                            
                            with st.expander(f"📧 {subject}"):
                                st.write(f"**De:** {from_email}")
                                st.write(f"**Fecha:** {date}")
                                st.write(f"**ID:** {msg['id']}")
                        except Exception as e:
                            st.error(f"Error al cargar mensaje: {str(e)}")
                else:
                    st.info("No se encontraron mensajes")

# Sidebar con información
with st.sidebar:
    st.header("ℹ️ Información")
    st.write("Esta aplicación te permite:")
    st.write("- 📤 Enviar correos electrónicos")
    st.write("- 📊 Enviar correos masivos desde Excel")
    st.write("- 📬 Ver tus últimos emails")
    st.write("- 🔐 Autenticación segura con OAuth2")
    
    st.divider()
    st.write("**Estado:**")
    if st.session_state.credentials:
        st.success("Conectado")
    else:
        st.warning("No autenticado")
