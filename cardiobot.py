import streamlit as st
from openai import OpenAI
import requests
import json
import os
import base64
from datetime import datetime, timedelta
from fpdf import FPDF
from io import BytesIO
import paypalrestsdk
from dotenv import load_dotenv
import uuid
import time

# Load environment variables
load_dotenv()

# Configure PayPal
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID") or st.secrets.get("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET") or st.secrets.get("PAYPAL_CLIENT_SECRET")
PAYPAL_MODE = os.getenv("PAYPAL_MODE", "sandbox")  # Use 'sandbox' for testing, 'live' for production

# Initialize PayPal SDK
paypalrestsdk.configure({
    "mode": PAYPAL_MODE,
    "client_id": PAYPAL_CLIENT_ID,
    "client_secret": PAYPAL_CLIENT_SECRET
})

# Premium feature settings
PREMIUM_PRICE = "4.99"  # USD
PREMIUM_DURATION = 30  # days
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

# System prompts for free and premium users
# Cardio prompts
CARDIO_FREE_PROMPT = """Eres un asistente cardiológico experto. Proporciona información en español sobre:
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
5. Nunca recomiendes medicamentos específicos sin prescripción médica
6. Menciona ocasionalmente que hay una versión premium disponible con respuestas más detalladas y generación de reportes"""

CARDIO_PREMIUM_PROMPT = """Eres un asistente cardiológico experto PREMIUM. Proporciona información detallada en español sobre:
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
4. Proporciona respuestas DETALLADAS y COMPLETAS (sin límite de párrafos)
5. Nunca recomiendes medicamentos específicos sin prescripción médica
6. Incluye referencias a estudios científicos cuando sea relevante
7. Ofrece explicaciones más técnicas y detalladas que la versión gratuita"""


# Initialize premium status
if "is_premium" not in st.session_state:
    st.session_state.is_premium = False  # Default to free version

if "premium_expiry" not in st.session_state:
    st.session_state.premium_expiry = None

# Check if premium has expired
if st.session_state.premium_expiry and datetime.now() > st.session_state.premium_expiry:
    st.session_state.is_premium = False
    st.session_state.premium_expiry = None
    
# Initialize chat history
if "cardio_messages" not in st.session_state:
    cardio_system_prompt = CARDIO_PREMIUM_PROMPT if st.session_state.is_premium else CARDIO_FREE_PROMPT
    st.session_state.cardio_messages = [{"role": "system", "content": cardio_system_prompt}]

# Display chat messages
for message in st.session_state.cardio_messages:
    if message["role"] != "system":
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Hazme una pregunta sobre salud cardiovascular"):
    # Add user message to history
    st.session_state.cardio_messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate AI response
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
                # Set different token limits based on premium status
                max_tokens = 2000 if st.session_state.is_premium else 1000
                
                # Show premium badge for premium users
                if st.session_state.is_premium:
                    st.caption("✨ Respuesta Premium")
                
                # Get streaming response
                stream = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=st.session_state.cardio_messages,
                    stream=True,
                    temperature=0.3,
                    max_tokens=max_tokens
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
        st.session_state.cardio_messages.append({"role": "assistant", "content": full_response})



  

def generate_pdf_report(patient_name, age, content, report_type="cardio"):
    # Helper function to clean text for FPDF (which uses latin-1 encoding)
    def clean_for_pdf(text):
        # Replace common Unicode characters with their Latin-1 equivalents
        replacements = {
            '\u2013': '-',  # en dash
            '\u2014': '-',  # em dash
            '\u2018': "'",  # left single quote
            '\u2019': "'",  # right single quote
            '\u201c': '"',  # left double quote
            '\u201d': '"',  # right double quote
            '\u2022': '-',  # bullet
            '\u2026': '...',  # ellipsis
            '\u00a0': ' ',  # non-breaking space
        }
        
        for unicode_char, replacement in replacements.items():
            text = text.replace(unicode_char, replacement)
        
        # For any other non-Latin-1 characters, replace with closest equivalent or remove
        result = ""
        for char in text:
            if ord(char) < 256:  # Latin-1 range
                result += char
            else:
                # Try to find a close equivalent or just skip
                result += ' '
        
        return result
    
    # Create PDF with UTF-8 support
    class PDF(FPDF):
        def __init__(self, report_type="cardio"):
            super().__init__()
            self.report_type = report_type
            
        def header(self):
            # Logo - could add a logo here if needed
            # self.image('logo.png', 10, 8, 33)
            # Set font for the header
            self.set_font('helvetica', 'B', 18)
            # Title based on report type
            if self.report_type == "nutrition":
                title = 'Reporte Nutricional'
            else:
                title = 'Reporte de Salud Cardiovascular'
            self.cell(0, 15, title, 0, 1, 'C')
            # Line break
            self.ln(5)
        
        def footer(self):
            # Position at 1.5 cm from bottom
            self.set_y(-15)
            # Set font for the footer
            self.set_font('helvetica', 'I', 8)
            # Page number
            self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'C')
    
    # Initialize PDF with UTF-8 support
    pdf = PDF()
    pdf.alias_nb_pages()  # For page numbering
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Use helvetica which has better Unicode support
    pdf.set_font('helvetica', '', 12)
    
    # Add date with proper formatting
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", 0, 1, 'R')
    pdf.ln(5)
    
    # Add patient information in a nice box
    pdf.set_fill_color(240, 240, 240)  # Light gray background
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, "Información del Paciente", 0, 1, 'L', True)
    
    pdf.set_font('helvetica', '', 12)
    pdf.cell(40, 10, "Nombre:", 0, 0)
    pdf.cell(0, 10, patient_name, 0, 1)
    
    pdf.cell(40, 10, "Edad:", 0, 0)
    pdf.cell(0, 10, str(age), 0, 1)
    
    pdf.ln(5)
    
    # Add content with better formatting
    pdf.set_font('helvetica', 'B', 14)
    pdf.cell(0, 10, "Recomendaciones", 0, 1, 'L', True)
    
    pdf.set_font('helvetica', '', 12)
    
    # Process content paragraph by paragraph for better formatting
    paragraphs = content.split('\n\n')
    for paragraph in paragraphs:
        if paragraph.strip():
            # Check if this is a heading (starts with # or is all caps)
            if paragraph.startswith('#') or paragraph.isupper():
                pdf.set_font('helvetica', 'B', 12)
                heading_text = paragraph.replace('#', '').strip()
                heading_text = clean_for_pdf(heading_text)
                pdf.multi_cell(0, 10, heading_text)
                pdf.set_font('helvetica', '', 12)
            # Check if this is a bullet point list (lines starting with *)
            elif any(line.strip().startswith('*') for line in paragraph.split('\n')):
                for line in paragraph.split('\n'):
                    line = line.strip()
                    if line.startswith('*'):
                        # This is a bullet point
                        bullet_text = line[1:].strip()  # Remove the asterisk and trim
                        bullet_text = clean_for_pdf(bullet_text)  # Clean for PDF compatibility
                        pdf.set_x(pdf.get_x() + 5)  # Indent
                        pdf.cell(5, 10, '-', 0, 0)  # Use hyphen instead of bullet character
                        pdf.multi_cell(0, 10, bullet_text)
                    elif line:
                        # Regular line in a list context
                        clean_line = clean_for_pdf(line)
                        pdf.multi_cell(0, 10, clean_line)
            else:
                # Simplified approach: Remove markdown formatting characters
                # Replace ** and * with empty string to remove them from the text
                clean_paragraph = paragraph
                clean_paragraph = clean_paragraph.replace('**', '')  # Remove bold markers
                clean_paragraph = clean_paragraph.replace('*', '')   # Remove italic markers
                
                # Clean the paragraph for PDF compatibility
                clean_paragraph = clean_for_pdf(clean_paragraph)
                
                # Write the cleaned paragraph
                pdf.multi_cell(0, 10, clean_paragraph)
            
            pdf.ln(5)
    
    # Create a BytesIO object to store the PDF in memory
    pdf_buffer = BytesIO()
    # For FPDF, we need to use a temporary file
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
        pdf.output(temp_file.name)
        # Read the file contents
        with open(temp_file.name, 'rb') as f:
            pdf_bytes = f.read()
        # Clean up the temporary file
        import os
        try:
            os.unlink(temp_file.name)
        except:
            pass
    
    # Return the bytes directly
    return pdf_bytes
# PayPal payment functions
def create_paypal_payment():
    """Create a PayPal payment for premium subscription"""
    payment = paypalrestsdk.Payment({
        "intent": "sale",
        "payer": {
            "payment_method": "paypal"
        },
        "transactions": [{
            "amount": {
                "total": PREMIUM_PRICE,
                "currency": "USD"
            },
            "description": f"Suscripción Premium por {PREMIUM_DURATION} días - Asistente Cardiológico"
        }],
        "redirect_urls": {
            "return_url": "https://example.com/success",  # These URLs are not used in Streamlit
            "cancel_url": "https://example.com/cancel"    # We'll handle the flow manually
        }
    })
    
    if payment.create():
        for link in payment.links:
            if link.method == "REDIRECT" and link.rel == "approval_url":
                return payment.id, link.href
    
    return None, None

def execute_paypal_payment(payment_id, payer_id):
    """Execute a previously created PayPal payment"""
    payment = paypalrestsdk.Payment.find(payment_id)
    if payment.execute({"payer_id": payer_id}):
        return True
    return False

def activate_premium():
    """Activate premium features for the user"""
    st.session_state.is_premium = True
    st.session_state.premium_expiry = datetime.now() + timedelta(days=PREMIUM_DURATION)
    # Update system prompts for premium users
    st.session_state.cardio_messages[0] = {"role": "system", "content": CARDIO_PREMIUM_PROMPT}
    st.session_state.nutrition_messages[0] = {"role": "system", "content": NUTRITION_PREMIUM_PROMPT}


# Sidebar
with st.sidebar:
    # Premium status indicator
    if st.session_state.is_premium and st.session_state.premium_expiry:
        expiry_date = st.session_state.premium_expiry.strftime("%d/%m/%Y")
        st.success(f"✨ PREMIUM ACTIVO hasta {expiry_date} ✨")
        
        # Display premium benefits
        st.markdown("### 🌟 Beneficios Premium")
        st.markdown("""
        - ✅ Respuestas detalladas y completas
        - ✅ Generación de reportes PDF
        - ✅ Referencias a estudios científicos
        - ✅ Explicaciones técnicas avanzadas
        """)
    else:
        st.info("💡 Versión gratuita")
        
        # Premium upgrade section
        st.markdown("### 🌟 Actualiza a Premium")
        st.markdown("""
        **Beneficios Premium:**
        - ✅ Respuestas detalladas y completas
        - ✅ Generación de reportes PDF
        - ✅ Referencias a estudios científicos
        - ✅ Explicaciones técnicas avanzadas
        
        Solo $4.99 USD por 30 días
        """)
        
        # PayPal payment flow
        if "payment_id" not in st.session_state:
            st.session_state.payment_id = None
            
        if "payment_url" not in st.session_state:
            st.session_state.payment_url = None
            
        if "payer_id" not in st.session_state:
            st.session_state.payer_id = None
            
        if "payment_completed" not in st.session_state:
            st.session_state.payment_completed = False
            
        # Step 1: Create payment
        if not st.session_state.payment_id and not st.session_state.payment_completed:
            if st.button("Actualizar a Premium"):
                with st.spinner("Conectando con PayPal..."):
                    payment_id, payment_url = create_paypal_payment()
                    if payment_id and payment_url:
                        st.session_state.payment_id = payment_id
                        st.session_state.payment_url = payment_url
                        st.rerun()
                    else:
                        st.error("Error al conectar con PayPal. Intente nuevamente.")
        
        # Step 2: Show PayPal link
        elif st.session_state.payment_id and not st.session_state.payer_id and not st.session_state.payment_completed:
            st.markdown(f"[Completar pago con PayPal]({st.session_state.payment_url})")
            st.info("Después de completar el pago en PayPal, copia el código 'PayerID' y pégalo abajo.")
            
            payer_id = st.text_input("Ingresa el PayerID de PayPal:")
            if payer_id:
                st.session_state.payer_id = payer_id
                st.rerun()
                
            if st.button("Cancelar pago"):
                st.session_state.payment_id = None
                st.session_state.payment_url = None
                st.rerun()
        
        # Step 3: Execute payment
        elif st.session_state.payment_id and st.session_state.payer_id and not st.session_state.payment_completed:
            with st.spinner("Verificando pago..."):
                if execute_paypal_payment(st.session_state.payment_id, st.session_state.payer_id):
                    st.session_state.payment_completed = True
                    activate_premium()
                    st.success("¡Pago completado! Premium activado.")
                    st.rerun()
                else:
                    st.error("Error al procesar el pago. Intente nuevamente.")
                    st.session_state.payer_id = None
                    st.rerun()
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
