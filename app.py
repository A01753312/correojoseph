import streamlit as st
import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json
import pandas as pd
import time
import mimetypes
import urllib.parse

# Intentar importar pywhatkit (solo funciona si la app se ejecuta en una máquina local)
try:
    import pywhatkit as pwk
    HAS_PYWHATKIT = True
except Exception:
    HAS_PYWHATKIT = False

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

# Función para enviar correo MEJORADA
def send_email(service, to, subject, body, attachments=None):
    try:
        # Crear mensaje
        message = MIMEMultipart()
        message['to'] = to
        message['subject'] = subject
        
        # Agregar el cuerpo del mensaje
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Agregar archivos adjuntos si existen
        if attachments:
            for attachment in attachments:
                filename = attachment['name']
                content = attachment['content']
                
                # Detectar el tipo MIME correcto
                mime_type, _ = mimetypes.guess_type(filename)
                if mime_type is None:
                    mime_type = 'application/octet-stream'
                
                # Separar el tipo MIME principal y subtipo
                maintype, subtype = mime_type.split('/', 1)
                
                # Crear la parte del adjunto con el tipo MIME correcto
                part = MIMEBase(maintype, subtype)
                part.set_payload(content)
                encoders.encode_base64(part)
                
                # Agregar header con el nombre del archivo
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{filename}"'
                )
                message.attach(part)
        
        # Codificar el mensaje
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

# Obtener código de la URL si Google redirige de vuelta
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
        st.rerun()
    except Exception as e:
        st.error(f"Error en la autenticación: {str(e)}")

# Proceso de autenticación
if st.session_state.credentials is None:
    st.header("🔐 Autenticación con Google")
    st.write("Para usar esta aplicación, necesitas autenticarte con tu cuenta de Gmail.")
    
    # Mostrar botón de login
    if st.button("Iniciar sesión con Google"):
        try:
            flow = get_flow()
            auth_url, _ = flow.authorization_url(prompt='consent')
            st.markdown(f"[Haz clic aquí para autenticarte]({auth_url})")
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
    tab1, tab2, tab3 = st.tabs(["📊 Enviar desde Excel", "📬 Ver Emails", "📱 Enviar WhatsApp"])
    
    with tab1:
        st.header("📊 Enviar correos masivos desde Excel")
        st.write("Sube un archivo Excel con las columnas: `Nombre`, `Celular`, y `email`")
        
        # Mostrar ejemplo
        with st.expander("📝 Ver formato de ejemplo"):
            ejemplo_df = pd.DataFrame({
                'Nombre': ['Juan Pérez', 'María García'],
                'Celular': ['5551234567', '5559876543'],
                'email': ['juan@example.com', 'maria@example.com']
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
                required_columns = ['Nombre', 'Celular', 'email']
                if not all(col in df.columns for col in required_columns):
                    st.error(f"El archivo debe contener las columnas: {', '.join(required_columns)}")
                else:
                    st.success(f"✅ Archivo cargado correctamente: {len(df)} contactos encontrados")
                    
                    # Mostrar vista previa
                    st.write("Vista previa de los contactos:")
                    st.dataframe(df)
                    
                    st.divider()
                    
                    # Plantilla de asunto
                    st.subheader("📝 Plantilla de asunto")
                    st.write("Usa `{Nombre}`, `{Celular}`, o `{email}` para personalizar")
                    subject_template = st.text_input(
                        "Asunto del correo:", 
                        placeholder="Ej: Hola {Nombre}, tenemos una oferta para ti",
                        value="Hola {Nombre}"
                    )
                    
                    # Plantilla de mensaje
                    st.subheader("✉️ Plantilla de mensaje")
                    st.write("Usa `{Nombre}`, `{Celular}`, o `{email}` para personalizar el mensaje")
                    message_template = st.text_area(
                        "Mensaje del correo:", 
                        placeholder="Ej: Estimado/a {Nombre}, te contactamos al {Celular}...",
                        value="Estimado/a {Nombre},\n\nGracias por tu interés.\n\nSaludos cordiales",
                        height=200
                    )
                    
                    # Archivos adjuntos
                    st.subheader("📎 Archivos adjuntos (opcional)")
                    uploaded_attachments = st.file_uploader(
                        "Sube archivos para adjuntar a todos los correos",
                        type=['pdf', 'doc', 'docx', 'jpg', 'jpeg', 'png', 'xlsx', 'xls', 'txt', 'zip'],
                        accept_multiple_files=True
                    )
                    
                    if uploaded_attachments:
                        st.write(f"📎 {len(uploaded_attachments)} archivo(s) adjunto(s):")
                        for att in uploaded_attachments:
                            st.write(f"  - {att.name} ({att.size / 1024:.1f} KB)")
                    
                    # Vista previa del primer correo
                    if len(df) > 0:
                        st.subheader("👁️ Vista previa del primer correo")
                        first_row = df.iloc[0]
                        preview_subject = subject_template.format(
                            Nombre=first_row['Nombre'],
                            Celular=first_row['Celular'],
                            email=first_row['email']
                        )
                        preview_message = message_template.format(
                            Nombre=first_row['Nombre'],
                            Celular=first_row['Celular'],
                            email=first_row['email']
                        )
                        
                        st.write(f"**Para:** {first_row['email']}")
                        st.write(f"**Asunto:** {preview_subject}")
                        st.text_area("**Mensaje:**", value=preview_message, height=150, disabled=True)
                    
                    st.divider()
                    
                    # Botón para enviar
                    if st.button("📤 Enviar todos los correos"):
                        if not subject_template.strip() or not message_template.strip():
                            st.error("Por favor completa el asunto y mensaje")
                        else:
                            # Preparar archivos adjuntos UNA SOLA VEZ antes del loop
                            attachments = []
                            if uploaded_attachments:
                                for att in uploaded_attachments:
                                    # Leer el contenido del archivo UNA SOLA VEZ
                                    att.seek(0)  # Ir al inicio del archivo
                                    file_content = att.read()  # Leer todo el contenido
                                    
                                    attachments.append({
                                        'name': att.name,
                                        'content': file_content  # Ya es bytes, no necesita más procesamiento
                                    })
                                    st.write(f"📎 Preparado: {att.name} ({len(file_content)} bytes)")
                            
                            progress_bar = st.progress(0)
                            status_text = st.empty()
                            
                            enviados = 0
                            errores = 0
                            
                            for idx, row in df.iterrows():
                                nombre = str(row['Nombre']).strip()
                                celular = str(row['Celular']).strip()
                                email = str(row['email']).strip()
                                
                                # Personalizar asunto y mensaje
                                try:
                                    asunto_personalizado = subject_template.format(
                                        Nombre=nombre,
                                        Celular=celular,
                                        email=email
                                    )
                                    mensaje_personalizado = message_template.format(
                                        Nombre=nombre,
                                        Celular=celular,
                                        email=email
                                    )
                                except KeyError as e:
                                    st.error(f"Error en la plantilla: {e}. Usa solo {{Nombre}}, {{Celular}}, o {{email}}")
                                    break
                                
                                status_text.text(f"Enviando a {nombre} ({email})...")
                                
                                # Pasar los adjuntos preparados (no leer de nuevo)
                                success, msg = send_email(
                                    service, 
                                    email, 
                                    asunto_personalizado, 
                                    mensaje_personalizado, 
                                    attachments if attachments else None
                                )
                                
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
    
    with tab2:
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

    with tab3:
        st.header("📱 Enviar WhatsApp (individual o masivo)")
        st.write("Sube un archivo Excel con las columnas: `Nombre` y `Celular` (sin prefijo +52)")

        uploaded_wa = st.file_uploader("Sube el Excel para WhatsApp", type=['xlsx', 'xls'], key='wa_excel')
        if uploaded_wa is not None:
            try:
                df_wa = pd.read_excel(uploaded_wa, dtype=str)
                required_wa = ['Nombre', 'Celular']
                if not all(col in df_wa.columns for col in required_wa):
                    st.error(f"El archivo debe contener las columnas: {', '.join(required_wa)}")
                else:
                    st.success(f"✅ Archivo cargado correctamente: {len(df_wa)} contactos encontrados")
                    st.dataframe(df_wa)

                    st.divider()
                    st.subheader("✉️ Plantilla de mensaje para WhatsApp")
                    st.write("Usa `{Nombre}` y `{Celular}` para personalizar")
                    wa_template = st.text_area("Mensaje:", value="Hola {Nombre}, te contactamos al {Celular}.", height=160)

                    # Selección individual o masiva
                    mode = st.radio("Enviar a:", ["Individual (elige un contacto)", "Masivo (todos)"])

                    # Método de envío
                    method = st.selectbox("Método de envío:", ["wa.me (enlaces)", "pywhatkit (local)"])

                    if mode.startswith("Individual"):
                        # Elegir contacto
                        names = df_wa['Nombre'].astype(str).tolist()
                        choice = st.selectbox("Elige un contacto:", names)
                        selected_row = df_wa[df_wa['Nombre'].astype(str) == choice].iloc[0]
                        numero = str(selected_row['Celular']).strip()
                        nombre = str(selected_row['Nombre']).strip()
                        preview = wa_template.format(Nombre=nombre, Celular=numero)
                        st.write(f"**Para:** +52{numero}")
                        st.text_area("**Mensaje:**", value=preview, height=140, disabled=True)

                        if method.startswith("wa.me"):
                            link = f"https://wa.me/52{numero}?text={urllib.parse.quote(preview)}"
                            st.markdown(
                                f"""
                                <a href="{link}" target="_blank">
                                    <button style="
                                        background-color:#25D366;
                                        color:white;
                                        padding:10px 18px;
                                        border:none;
                                        border-radius:8px;
                                        font-size:16px;
                                        cursor:pointer;
                                    ">
                                        📲 Enviar WhatsApp
                                    </button>
                                </a>
                                """,
                                unsafe_allow_html=True
                            )
                        else:
                            if not HAS_PYWHATKIT:
                                st.warning("pywhatkit no está disponible en este entorno. Ejecuta la app localmente para usar pywhatkit.")
                            if st.button("📤 Enviar por pywhatkit (local)"):
                                if not HAS_PYWHATKIT:
                                    st.error("pywhatkit no disponible — instala pywhatkit y ejecuta localmente")
                                else:
                                    try:
                                        pwk.sendwhatmsg_instantly(f"+52{numero}", preview, wait_time=15, tab_close=True, close_time=3)
                                        st.success("Mensaje enviado (se abrió WhatsApp Web)")
                                    except Exception as e:
                                        st.error(f"Error enviando por pywhatkit: {e}")

                    else:
                        # Masivo — comportamiento previo
                        st.info("Generar enlaces wa.me para todos o usar pywhatkit (local) para envíos automáticos en tu máquina")
                        if method.startswith("wa.me"):
                            st.subheader("Enlaces de envío (clic para abrir WhatsApp)")

                            for _, r in df_wa.iterrows():
                                numero = str(r['Celular']).strip()
                                nombre = str(r['Nombre']).strip()
                                texto = wa_template.format(Nombre=nombre, Celular=numero)
                                encoded = urllib.parse.quote(texto)
                                link = f"https://wa.me/52{numero}?text={encoded}"

                                st.markdown(
                                    f"""
                                    <div style="margin-bottom:15px; padding:10px; border:1px solid #ddd; border-radius:8px;">
                                        <b>{nombre}</b> (+52{numero})<br><br>
                                        <a href="{link}" target="_blank">
                                            <button style="
                                                background-color:#25D366;
                                                color:white;
                                                padding:8px 14px;
                                                border:none;
                                                border-radius:6px;
                                                font-size:15px;
                                                cursor:pointer;
                                            ">
                                                📲 Enviar WhatsApp
                                            </button>
                                        </a>
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )
                        else:
                            intervalo = st.number_input("Segundos entre mensajes:", min_value=5, max_value=300, value=15)
                            if not HAS_PYWHATKIT:
                                st.warning("pywhatkit no está instalado aquí. Ejecuta localmente para usar esta opción.")
                            if st.button("📤 Enviar masivo por pywhatkit (local)"):
                                if not HAS_PYWHATKIT:
                                    st.error("pywhatkit no disponible — instala pywhatkit y ejecuta localmente")
                                else:
                                    progress = st.progress(0)
                                    status = st.empty()
                                    enviados = 0
                                    errores = 0
                                    for idx, row in df_wa.iterrows():
                                        nombre = str(row['Nombre']).strip()
                                        celular = str(row['Celular']).strip()
                                        texto = wa_template.format(Nombre=nombre, Celular=celular)
                                        status.text(f"Enviando a {nombre} (+52{celular})...")
                                        try:
                                            pwk.sendwhatmsg_instantly(f"+52{celular}", texto, wait_time=15, tab_close=True, close_time=3)
                                            enviados += 1
                                        except Exception as e:
                                            errores += 1
                                            st.warning(f"Error enviando a {celular}: {e}")
                                        progress.progress((idx + 1) / len(df_wa))
                                        time.sleep(intervalo)
                                    status.empty()
                                    progress.empty()
                                    st.success(f"Proceso finalizado: {enviados} enviados, {errores} errores")
            except Exception as e:
                st.error(f"Error procesando el Excel para WhatsApp: {e}")

# Sidebar con información
with st.sidebar:
    st.header("ℹ️ Información")
    st.write("Esta aplicación te permite:")
    st.write("- 📊 Enviar correos masivos desde Excel")
    st.write("- 📎 Adjuntar archivos a los correos")
    st.write("- 📬 Ver tus últimos emails")
    st.write("- 🔐 Autenticación segura con OAuth2")
    
    st.divider()
    st.write("**Estado:**")
    if st.session_state.credentials:
        st.success("Conectado")
    else:
        st.warning("No autenticado")