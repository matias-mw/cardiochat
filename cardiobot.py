import streamlit as st
from openai import OpenAI
import requests
import json
import os
import base64
from datetime import datetime, timedelta
from fpdf import FPDF
from io import BytesIO

# Set up the Streamlit app
st.set_page_config(page_title="❤️ Asistente Cardiológico", page_icon="❤️")
st.title("❤️ Asistente Cardiológico")
st.subheader("¡Pregúntame cualquier cosa sobre salud cardiovascular!")

# Configure DeepSeek API
if "deepseek_key" not in st.session_state:
    try:
        st.session_state.deepseek_key = st.secrets["deepseek_key"]
    except:
        st.session_state.deepseek_key = None

if not st.session_state.deepseek_key:
    with st.sidebar:
        api_key = st.text_input("Enter your DeepSeek API key:", type="password")
        if api_key:
            st.session_state.deepseek_key = api_key
            st.rerun()
    st.warning("⚠️ Please enter your DeepSeek API key in the sidebar")
    st.stop()

# Initialize DeepSeek client
client = OpenAI(
    api_key=st.session_state.deepseek_key,
    base_url="https://api.deepseek.com/v1"  # Updated endpoint
)

# System prompt (now includes Spanish responses)
SYSTEM_PROMPT = """Eres un asistente cardiológico experto. Proporciona información en español sobre:
- Salud cardiovascular
- Factores de riesgo cardíaco
- Síntomas de enfermedades cardíacas
- Hábitos saludables para el corazón
- Nutrición para la salud cardíaca
- Ejercicio y actividad física

Reglas:
1. Mantén un tono profesional pero amigable
2. Solo responde sobre temas relacionados con la cardiología
3. Para problemas médicos, recomienda consultar a un cardiólogo
4. Proporciona respuestas concisas (1-3 párrafos)
5. Nunca recomiendes medicamentos específicos sin prescripción médica"""

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

# Display chat messages
for message in st.session_state.messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Hazme una pregunta sobre salud cardiovascular"):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate AI response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            # Get streaming response
            # Use the messages directly - DeepSeek API should handle the format
            stream = client.chat.completions.create(
                model="deepseek-chat",
                messages=st.session_state.messages,
                stream=True,
                temperature=0.3,
                max_tokens=1000
                
            )
            
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
        
        except Exception as e:
            st.error(f"Error: {str(e)}")
            if "401" in str(e):
                st.error("Invalid API key. Please check your credentials.")
                st.session_state.deepseek_key = None
                st.rerun()

    # Add AI response to history
    st.session_state.messages.append({"role": "assistant", "content": full_response})

def generate_pdf_report(patient_name, age, content):
    # Create PDF with UTF-8 support
    pdf = FPDF()
    pdf.add_page()
    
    # Set Arial Unicode font if available
    try:
        pdf.add_font('Arial', '', 'Arial.ttf', uni=True)
        pdf.set_font('Arial', '', 12)
    except:
        # Fallback to standard font
        pdf.set_font('Arial', '', 12)
    
    # Clean content to remove problematic characters
    def clean_text(text):
        return ''.join(c for c in text if ord(c) < 128)
    
    # Add title
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(200, 10, clean_text(f"Reporte de Salud Cardiovascular para {patient_name}"), ln=True, align='C')
    
    # Add date
    pdf.set_font('Arial', '', 12)
    pdf.cell(200, 10, clean_text(f"Fecha: {datetime.now().strftime('%Y-%m-%d')}"), ln=True, align='C')
    
    # Add patient information
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(200, 10, clean_text("Información del Paciente"), ln=True)
    
    pdf.set_font('Arial', '', 12)
    pdf.cell(200, 10, clean_text(f"Nombre: {patient_name}"), ln=True)
    pdf.cell(200, 10, clean_text(f"Edad: {age}"), ln=True)
    
    # Add content
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(200, 10, clean_text("Recomendaciones"), ln=True)
    
    pdf.set_font('Arial', '', 12)
    # Split content into lines to avoid encoding issues
    lines = content.split('\n')
    for line in lines:
        cleaned_line = clean_text(line)
        pdf.multi_cell(190, 10, cleaned_line)
    
    # Create a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        pdf.output(temp_file.name)
        # Read the file contents
        temp_file.seek(0)
        pdf_bytes = temp_file.read()
    
    # Return the bytes directly
    return pdf_bytes

# Sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("### ℹ️ Acerca de este asistente")
    st.markdown("Este chatbot proporciona información general sobre salud cardiovascular y temas relacionados con la cardiología.")

    st.markdown("---")
    st.markdown("### ⚠️ Descargo de responsabilidad")
    st.markdown("""
    Esto no sustituye el asesoramiento médico profesional. 
    Consulte siempre a un cardiólogo cualificado en caso de dudas médicas.
    """)
    
    # Add PDF report generation section
    st.markdown("---")
    st.subheader("Generar Reporte PDF")
    
    patient_name = st.text_input("Nombre del paciente:")
    age = st.number_input("Edad:", min_value=1, max_value=120, value=40)
    risk_factors = st.multiselect(
        "Factores de riesgo:",
        ["Hipertensión", "Diabetes", "Colesterol alto", "Tabaquismo", "Obesidad", "Sedentarismo", "Antecedentes familiares"]
    )
    
    if st.button("Generar Reporte"):
        if not patient_name:
            st.error("Por favor ingrese el nombre del paciente")
            st.stop()
        
        # Generate AI response
        try:
            risk_factors_text = ", ".join(risk_factors) if risk_factors else "ninguno"
            
            # Create messages in the format expected by the API
            report_messages = [
                {"role": "system", "content": "Genera un reporte detallado sobre salud cardiovascular para este paciente"},
                {"role": "user", "content": f"Genera un reporte detallado sobre salud cardiovascular para un paciente llamado {patient_name}, de {age} años, con los siguientes factores de riesgo: {risk_factors_text}"}
            ]
            
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=report_messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            report_content = response.choices[0].message.content
            
            try:
                # Generate PDF directly in memory
                pdf_bytes = generate_pdf_report(patient_name, age, report_content)
                
                # Download button
                st.download_button(
                    label="Descargar Reporte PDF",
                    data=pdf_bytes,
                    file_name=f"{patient_name}_cardio_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
                    mime="application/pdf"
                ) 
                
                # Clean up temporary files
                import os
                import glob
                for f in glob.glob("*.pdf"):
                    try:
                        os.remove(f)
                    except:
                        pass
                
                st.success("Reporte generado exitosamente!")
            except Exception as e:
                st.error(f"Error generando el reporte: {str(e)}")
        except Exception as e:
            st.error(f"Error generando el reporte: {str(e)}")
    
    if st.button("Limpiar historial de chat"):
        st.session_state.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        st.rerun()
