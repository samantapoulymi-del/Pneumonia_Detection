import streamlit as st
import tensorflow as tf
import numpy as np
import os
import pandas as pd
import cv2
from PIL import Image
from datetime import datetime
import uuid
from docx import Document
from io import BytesIO
from reportlab.pdfgen import canvas
import random
import string
from streamlit_gsheets import GSheetsConnection
import time
import requests
import streamlit.components.v1 as components
import base64
from reportlab.lib.utils import ImageReader
import textwrap

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="PneumoniaLens AI", page_icon="🫁", layout="wide", initial_sidebar_state="collapsed")

# ---------------- SECURE CLOUD CONNECTIONS ----------------
try:
    SHEET_URL = st.secrets["api_urls"]["sheet_url"]
    APPS_SCRIPT_URL = st.secrets["api_urls"]["apps_script_url"]
    MODEL_DOWNLOAD_URL = st.secrets["api_urls"]["hf_model_url"]
except KeyError:
    st.error("⚠️ Secure URLs not found! Please add [api_urls] to your secrets.toml file.")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

def get_doctors_db():
    try:
        return conn.read(spreadsheet=SHEET_URL, worksheet="Doctors", ttl=0)
    except Exception:
        return pd.DataFrame(columns=["ID", "Name", "Email", "Department", "Password"])

def update_doctors_db(df):
    conn.update(spreadsheet=SHEET_URL, worksheet="Doctors", data=df)

def get_logs_db():
    try:
        return conn.read(spreadsheet=SHEET_URL, worksheet="Logs", ttl=0)
    except Exception:
        return pd.DataFrame(columns=["Scan ID", "Operator", "Result", "Confidence", "Timestamp"])

def update_logs_db(df):
    conn.update(spreadsheet=SHEET_URL, worksheet="Logs", data=df)

# ---------------- SESSION STATE INIT ----------------
if "logged_in_doctor" not in st.session_state:
    st.session_state.logged_in_doctor = None
if "doctor_name" not in st.session_state:
    st.session_state.doctor_name = ""
if "logged_in_admin" not in st.session_state:
    st.session_state.logged_in_admin = False
if "last_activity" not in st.session_state:
    st.session_state.last_activity = datetime.now()

if "show_login_toast" not in st.session_state:
    st.session_state.show_login_toast = False

if st.session_state.show_login_toast:
    st.toast(st.session_state.show_login_toast, icon="✅")
    st.session_state.show_login_toast = False

# ---------------- SECURITY: 15-MIN TIMEOUT & PERSISTENT TOKEN ----------------
def check_session():
    if "token" in st.query_params:
        if not st.session_state.logged_in_doctor:
            try:
                decoded_bytes = base64.urlsafe_b64decode(st.query_params["token"].encode())
                decoded_str = decoded_bytes.decode()
                recovered_id, recovered_name = decoded_str.split("||")
                
                st.session_state.logged_in_doctor = recovered_id
                st.session_state.doctor_name = recovered_name 
                st.session_state.last_activity = datetime.now()
            except Exception:
                st.query_params.clear()

    if st.session_state.logged_in_doctor or st.session_state.logged_in_admin:
        now = datetime.now()
        elapsed = (now - st.session_state.last_activity).total_seconds()
        if elapsed > 900:  
            st.session_state.logged_in_doctor = None
            st.session_state.doctor_name = "" 
            st.session_state.logged_in_admin = False
            st.query_params.clear() 
            st.warning("Session expired due to 15 minutes of inactivity.")
            st.rerun()

def update_activity():
    st.session_state.last_activity = datetime.now()

check_session()

# ---------------- STYLING ----------------
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

bg_img_path = "assets/bg.png"

if os.path.exists(bg_img_path):
    bg_base64 = get_base64_of_bin_file(bg_img_path)
    bg_css = f"""
    .stApp {{
        background-image: url("data:image/png;base64,{bg_base64}");
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
    }}
    @keyframes containerBreathe {{
        0% {{ box-shadow: 0 0 20px rgba(0, 255, 255, 0.05); border: 1px solid rgba(0, 255, 255, 0.1); }}
        50% {{ box-shadow: 0 0 45px rgba(0, 206, 209, 0.25); border: 1px solid rgba(0, 255, 255, 0.3); }}
        100% {{ box-shadow: 0 0 20px rgba(0, 255, 255, 0.05); border: 1px solid rgba(0, 255, 255, 0.1); }}
    }}
    .block-container {{
        background-color: rgba(0, 0, 0, 0.75); 
        backdrop-filter: blur(10px);
        padding: 2rem;
        border-radius: 15px;
        animation: containerBreathe 6s infinite ease-in-out;
    }}
    """
else:
    bg_css = ".stApp { background-color:#000000; }"

# INJECT ALL CSS 
st.markdown(f"""
<style>
{bg_css}

[data-testid="stHeader"] {{ display: none; }}
footer {{ visibility: hidden; }}

.stApp {{ color:white; }}

/* --- GLOWING TITLES (Preserves Emojis) --- */
h1, h2, h3 {{ 
    color: #00FFFF !important; 
    text-shadow: 0 0 15px rgba(0, 255, 255, 0.4);
    padding-bottom: 5px;
}}

/* --- THE CYBERPUNK SCROLLBAR --- */
::-webkit-scrollbar {{ width: 12px; height: 12px; }}
::-webkit-scrollbar-track {{ background: rgba(10, 10, 10, 0.9); border-left: 1px solid rgba(0, 255, 255, 0.1); }}
::-webkit-scrollbar-thumb {{ background: rgba(0, 255, 255, 0.3); border-radius: 10px; border: 2px solid rgba(10, 10, 10, 0.9); }}
::-webkit-scrollbar-thumb:hover {{ background: rgba(0, 255, 255, 0.8); box-shadow: 0 0 15px rgba(0, 255, 255, 0.5); }}

/* --- HOLOGRAPHIC INPUT FIELDS --- */
div[data-baseweb="input"], div[data-baseweb="select"] {{ transition: all 0.3s ease-in-out !important; border-radius: 8px !important; }}
div[data-baseweb="input"]:focus-within, div[data-baseweb="select"]:focus-within {{
    box-shadow: 0 0 25px 5px rgba(0, 255, 255, 0.5) !important;
    border: 1px solid #00FFFF !important;
    transform: translateY(-2px) !important;
    background-color: rgba(0, 20, 20, 0.8) !important;
}}

/* --- INTERACTIVE DATA IMAGES --- */
img {{ transition: transform 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.4s ease !important; border-radius: 8px !important; }}
img:hover {{ transform: scale(1.02) !important; box-shadow: 0 15px 30px rgba(0, 255, 255, 0.25) !important; }}

/* ========================================================= */
/* --- NEW: RUTHLESS STREAMLIT NATIVE OVERRIDES --- */

/* 2. Holographic System Alerts (Forces dark background) */
div[data-testid="stAlert"] {{
    background-color: rgba(10, 15, 20, 0.9) !important;
    border: 1px solid rgba(0, 255, 255, 0.2) !important;
    border-left: 6px solid #00FFFF !important;
    box-shadow: 0 8px 25px rgba(0, 255, 255, 0.15) !important;
    border-radius: 8px !important;
}}
div[data-testid="stAlert"] div[data-testid="stMarkdownContainer"] p {{
    color: #FFFFFF !important;
    font-size: 1.05rem !important;
}}

/* 3. The Bio-Scan Dropzone (File Uploader) */
div[data-testid="stFileUploadDropzone"] {{
    background-color: rgba(0, 30, 30, 0.5) !important;
    border: 2px dashed rgba(0, 255, 255, 0.5) !important;
    border-radius: 15px !important;
    transition: all 0.3s ease-in-out !important;
}}
div[data-testid="stFileUploadDropzone"]:hover {{
    background-color: rgba(0, 50, 50, 0.8) !important;
    border: 2px solid #00FFFF !important;
    box-shadow: 0 0 25px rgba(0, 255, 255, 0.4), inset 0 0 15px rgba(0, 255, 255, 0.2) !important;
    transform: scale(1.01);
}}

/* 4. The Cyan Energy Slider */
div[data-baseweb="slider"] div[role="slider"] {{
    background-color: #00FFFF !important;
    box-shadow: 0 0 15px 4px rgba(0, 255, 255, 0.6) !important;
    border: 2px solid #FFFFFF !important;
}}
div[data-baseweb="slider"] div[data-testid="stTickBar"] > div {{
    background-color: rgba(0, 255, 255, 0.4) !important;
}}
div[data-baseweb="slider"] div[data-testid="stTickBar"] > div[style*="background-color"] {{
    background-color: #00FFFF !important; /* Active track part */
    box-shadow: 0 0 10px rgba(0, 255, 255, 0.5) !important;
}}
/* ========================================================= */

/* --- AI TERMINAL TYPING EFFECT --- */
.typing-container {{ display: inline-block; }}
.typing-text {{
    overflow: hidden; white-space: nowrap; border-right: 3px solid transparent; width: 0;
    font-size: 1.5rem; font-weight: 600; color: #E0E0E0;
    animation: typing 2.5s steps(38, end) forwards, blinkCursor 0.75s step-end 4;
}}
@keyframes typing {{ from {{ width: 0; }} to {{ width: 38ch; }} }}
@keyframes blinkCursor {{ 0%, 100% {{ border-color: transparent; }} 50% {{ border-color: #00FFFF; }} }}

/* --- ANIMATED BUTTONS --- */
.stButton>button {{ background-color:#00FFFF; color:black; font-weight:bold; border-radius:30px; width: 100%; transition: all 0.35s ease; border: 2px solid #00FFFF; }}
.stButton>button:hover {{ box-shadow: 0px 0px 20px 4px rgba(0, 255, 255, 0.5); transform: translateY(-2px) scale(1.02); }}

/* --- SLEEK ANIMATED TABS --- */
@keyframes tabPulse {{
    0% {{ box-shadow: 0px 5px 15px 2px rgba(0, 255, 255, 0.3); }}
    50% {{ box-shadow: 0px 5px 25px 5px rgba(0, 255, 255, 0.6); }}
    100% {{ box-shadow: 0px 5px 15px 2px rgba(0, 255, 255, 0.3); }}
}}
.stTabs [data-baseweb="tab-list"] {{ gap: 15px; border-bottom: none; padding: 10px 10px 25px 10px !important; overflow: visible !important; }}
.stTabs [data-baseweb="tab"] {{ color: #00FFFF; border: 2px solid #00FFFF; border-radius: 30px; padding: 10px 25px; background-color: transparent; transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275); font-weight: 600; margin-bottom: 5px; }}
.stTabs [data-baseweb="tab"]:hover {{ background-color: #00FFFF !important; color: black !important; box-shadow: 0px 5px 15px 2px rgba(0, 255, 255, 0.5); transform: translateY(-4px); }}
.stTabs [aria-selected="true"] {{ background-color: #00FFFF !important; color: black !important; font-weight: bold; animation: tabPulse 3s infinite ease-in-out; transform: translateY(-2px) scale(1.02); }}

/* --- THE SYMMETRIC RED GLOW LINE --- */
.stTabs [data-baseweb="tab-highlight"] {{ background-color: #FF0033 !important; height: 4px !important; border-radius: 10px; box-shadow: 0px 0px 15px 4px rgba(255, 0, 51, 0.7) !important; bottom: 8px !important; }}

/* --- PAGE TRANSITION ANIMATIONS --- */
@keyframes fadeSlideUp {{ 0% {{ opacity: 0; transform: translateY(30px) scale(0.98); }} 100% {{ opacity: 1; transform: translateY(0) scale(1); }} }}
div[role="tabpanel"] {{ animation: fadeSlideUp 0.6s cubic-bezier(0.165, 0.84, 0.44, 1) forwards; }}
</style>
""", unsafe_allow_html=True)

# --- NEXT-GEN CARD STYLING WITH FLOATING & MOVING BORDER ---
st.markdown("""
<style>
/* Continuous Zero-Gravity Floating */
@keyframes floatCard {
    0% { transform: translateY(0px); box-shadow: 0 8px 32px rgba(0,0,0,0.6), 0 0 10px rgba(0,255,255,0.05); }
    100% { transform: translateY(-8px); box-shadow: 0 15px 35px rgba(0,0,0,0.7), 0 0 25px rgba(0,206,209,0.25); }
}

/* The Spinning Border Energy Glow */
@keyframes borderMovingGlow {
    0% { background-position: 0% 50%; }
    100% { background-position: 300% 50%; }
}

.card-grid-2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 25px; margin-bottom: 35px; }
.card-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 25px; margin-bottom: 35px; }

.custom-card { 
    background: linear-gradient(145deg, rgba(20,20,20,0.85) 0%, rgba(5,5,5,0.95) 100%); 
    backdrop-filter: blur(12px);
    border: 1px solid transparent; 
    border-radius: 16px; 
    padding: 25px; 
    transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); 
    height: 100%; 
    animation: floatCard 4s ease-in-out infinite alternate;
    position: relative;
    overflow: hidden; 
}

/* Stagger the floating so they don't move exactly together */
.card-grid-2 .custom-card:nth-child(2), .card-grid-3 .custom-card:nth-child(2) { animation-delay: 0.5s; }
.card-grid-3 .custom-card:nth-child(3) { animation-delay: 1s; }
.card-grid-2 .custom-card:nth-child(4), .card-grid-3 .custom-card:nth-child(4) { animation-delay: 1.5s; }

/* The Moving Energy Border */
.custom-card::after {
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 16px;
    padding: 2px; 
    background: linear-gradient(90deg, #00FFFF, transparent, #FF0033, transparent, #00FFFF);
    background-size: 300% 100%;
    -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
    -webkit-mask-composite: destination-out;
    mask-composite: exclude;
    animation: borderMovingGlow 5s linear infinite;
    pointer-events: none;
    opacity: 0.6;
}

/* The Glass Shimmer Beam */
.custom-card::before {
    content: '';
    position: absolute;
    top: 0; left: -150%;
    width: 50%; height: 100%;
    background: linear-gradient(to right, rgba(255,255,255,0) 0%, rgba(0,255,255,0.15) 50%, rgba(255,255,255,0) 100%);
    transform: skewX(-25deg);
    transition: all 0.75s ease-in-out;
    z-index: 2;
    pointer-events: none;
}

.custom-card:hover { 
    transform: scale(1.02); 
    box-shadow: 0 20px 40px rgba(0, 255, 255, 0.3), inset 0 0 25px rgba(0,255,255,0.1); 
    animation-play-state: paused; 
}
.custom-card:hover::after {
    opacity: 1; 
    background-size: 200% 100%; 
}
.custom-card:hover::before {
    left: 200%; 
}

.card-title { 
    color: #00FFFF; 
    font-size: 1.2rem; 
    font-weight: 800; 
    margin-bottom: 15px; 
    border-bottom: 1px solid rgba(0, 255, 255, 0.15); 
    padding-bottom: 10px; 
    letter-spacing: 0.5px;
    transition: all 0.3s ease;
}

/* Magnetic Title Expansion */
.custom-card:hover .card-title {
    letter-spacing: 1.5px;
    text-shadow: 0 0 15px rgba(0, 255, 255, 0.8);
    border-bottom: 1px solid rgba(0, 255, 255, 0.6);
}

.card-text { 
    color: #D1D5DB; 
    font-size: 1rem; 
    line-height: 1.7; 
}
.card-text i { color: #9CA3AF; }

/* Breathing Neon Glow for KPI Numbers */
@keyframes neonPulse {
    0% { text-shadow: 0 0 10px rgba(0,255,255,0.3); transform: scale(1); }
    50% { text-shadow: 0 0 25px rgba(0,255,255,0.8); transform: scale(1.05); }
    100% { text-shadow: 0 0 10px rgba(0,255,255,0.3); transform: scale(1); }
}

.kpi-value {
    font-size: 3.5rem; 
    font-weight: 900; 
    background: -webkit-linear-gradient(45deg, #ffffff, #00FFFF);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
    animation: neonPulse 3s ease-in-out infinite;
}
.kpi-label {
    color: #00FFFF; 
    font-size: 1.1rem; 
    font-weight: 700; 
    text-transform: uppercase; 
    letter-spacing: 1.5px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- MODEL & GRAD-CAM ----------------
@st.cache_resource
def load_model():
    model_path = "pneumonia_3class_97_perfection.h5"
    model_url = MODEL_DOWNLOAD_URL 

    if not os.path.exists(model_path):
        with st.spinner("☁️ AI Model not found. Downloading from Cloud..."):
            try:
                response = requests.get(model_url, stream=True)
                if response.status_code == 200:
                    with open(model_path, "wb") as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                else:
                    st.error("❌ Cloud connection failed.")
                    return None
            except Exception as e:
                st.error(f"❌ Download Error: {e}")
                return None

    return tf.keras.models.load_model(model_path, compile=False)

model = load_model()
CLASS_NAMES = ['NORMAL', 'BACTERIAL PNEUMONIA', 'VIRAL PNEUMONIA']

def make_gradcam_heatmap(img_array, model, last_conv_layer_name="relu"):
    grad_model = tf.keras.models.Model(model.inputs, [model.get_layer(last_conv_layer_name).output, model.output])
    with tf.GradientTape() as tape:
        last_conv_layer_output, preds = grad_model(img_array)
        if isinstance(preds, list): preds = tf.convert_to_tensor(preds[0])
        pred_index = tf.argmax(preds[0])
        class_channel = preds[:, pred_index]
    grads = tape.gradient(class_channel, last_conv_layer_output)
    pooled_grads = tf.reduce_mean(grads, axis=(0, 1, 2))
    last_conv_layer_output = last_conv_layer_output[0]
    heatmap = last_conv_layer_output @ pooled_grads[..., tf.newaxis]
    heatmap = tf.squeeze(heatmap)
    heatmap = tf.maximum(heatmap, 0) / tf.reduce_max(heatmap)
    return heatmap.numpy()

# ---------------- TOP HEADER DASHBOARD ----------------
col_head1, col_head2, col_head3 = st.columns([2, 1, 1])
with col_head1:
    st.markdown("<h1 style='margin-bottom: 0px;'>🫁 Pneumonia Lens</h1>", unsafe_allow_html=True)
    st.markdown("""
    <div style="color: #a3a8b8; font-size: 14px; margin-top: 5px;">
        <ul style="margin: 0px; padding-left: 20px;">
            <li>v2.0 DenseNet121</li>
            <li>3-class Architecture</li>
            <li>True Accuracy - 81.50%</li>
            <li>60 layers fine-tuned model</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
with col_head2:
    st.write("") 
    if st.session_state.logged_in_admin:
        st.success("Admin Session Active")
    elif st.session_state.logged_in_doctor:
        st.success(f"👨‍⚕️ Dr. {st.session_state.doctor_name}") 
    else:
        st.info("System: Restricted Access")
with col_head3:
    st.write("") 
    if st.session_state.logged_in_admin or st.session_state.logged_in_doctor:
        if st.button("Secure Logout"):
            st.session_state.logged_in_doctor = None
            st.session_state.doctor_name = ""       
            st.session_state.logged_in_admin = False
            st.query_params.clear() 
            st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# ---------------- NAVIGATION TABS & DYNAMIC WORKSPACES ----------------

# ---> 1. DOCTOR WORKSPACE (Only visible when a Doctor is logged in) <---
if st.session_state.logged_in_doctor:
    tab_scan, = st.tabs(["🔍 AI Diagnostic Scan"])
    
    with tab_scan:
        update_activity()
        st.title("AI Diagnostic Scan")

        if model is None:
            st.error("Model 'pneumonia_3class_97_perfection.h5' not found.")
        else:
            confidence_threshold = st.slider("Set Diagnostic Confidence Threshold", 0.0, 1.0, 0.50, 0.01)
            st.caption("Lowering this increases detection speed; raising it reduces 'false positives'.")
            uploaded_file = st.file_uploader("Upload Chest X-ray", type=["jpg","jpeg","png"])

            if uploaded_file:
                with st.status("DenseNet121 scanning through 60 layers, please wait...") as status:
                    pil_img = Image.open(uploaded_file).convert("RGB")
                    orig_width, orig_height = pil_img.size
                    img_res = pil_img.resize((224,224))
                    img_arr = np.array(img_res)/255.0
                    img_in = np.expand_dims(img_arr, axis=0)

                    preds_raw = model.predict(img_in)[0]
                    idx = np.argmax(preds_raw)
                    confidence = preds_raw[idx] 
                    raw_label = CLASS_NAMES[idx]

                    if confidence >= confidence_threshold:
                        final_label = raw_label
                        status_color = "success"
                    else:
                        final_label = "UNCERTAIN / MANUAL REVIEW REQUIRED"
                        status_color = "error"

                    heatmap = make_gradcam_heatmap(img_in, model)
                    h_res = cv2.resize(heatmap, (orig_width, orig_height)) 
                    h_col = cv2.applyColorMap(np.uint8(255 * h_res), cv2.COLORMAP_JET)
                    h_rgb = cv2.cvtColor(h_col, cv2.COLOR_BGR2RGB)
                    
                    orig_cv2 = np.array(pil_img)
                    overlay = cv2.addWeighted(orig_cv2, 0.6, h_rgb, 0.4, 0)
                    
                    status.update(label="Scanned successfully!", state="complete", expanded=False)

                logs_df = get_logs_db()
                new_log = pd.DataFrame([{
                    "Scan ID": str(uuid.uuid4())[:8],
                    "Operator": st.session_state.logged_in_doctor,
                    "Result": final_label,
                    "Confidence": f"{confidence*100:.2f}%",
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }])
                logs_df = pd.concat([logs_df, new_log], ignore_index=True)
                update_logs_db(logs_df)

                col1, col2 = st.columns(2)
                with col1:
                    st.image(pil_img, caption=f"Original ({orig_width}x{orig_height})", use_container_width=True)
                with col2:
                    st.image(overlay, caption=f"Grad-CAM Heatmap ({orig_width}x{orig_height})", use_container_width=True)

                if final_label == "NORMAL":
                    findings_text = "The DenseNet121 model analyzed the thoracic cavity and detected no significant opacities or consolidations indicative of pneumonia. The lung fields appear generally clear within the analyzed parameters."
                elif final_label == "BACTERIAL PNEUMONIA":
                    findings_text = "The model detected focal consolidations and dense lobar opacities highly indicative of a bacterial infection. The Grad-CAM heatmap highlights the specific localized regions driving this high-confidence classification."
                elif final_label == "VIRAL PNEUMONIA":
                    findings_text = "The model detected diffuse, patchy, or ground-glass opacities characteristic of a viral respiratory infection. The Grad-CAM heatmap localizes the distributed bilateral patterns typical of viral pneumonia."
                else:
                    findings_text = "The AI model was unable to reach the required confidence threshold. Manual radiologist review is strongly advised to determine the exact pathology."

                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.metric("Diagnosis", final_label)
                with col_m2:
                    st.metric("Confidence", f"{confidence*100:.2f}%")
                
                st.markdown("---")
                st.markdown(f"#### 📋 Clinical Findings - {final_label}")
                st.info(findings_text)
                st.markdown("<br>", unsafe_allow_html=True)

                def generate_pdf():
                    buffer = BytesIO()
                    c = canvas.Canvas(buffer, pagesize=(595.27, 841.89)) 
                    width, height = 595.27, 841.89
                    
                    c.setLineWidth(2)
                    c.setStrokeColorRGB(0.2, 0.2, 0.2)
                    c.rect(30, 30, width - 60, height - 60)
                    
                    c.saveState() 
                    c.setFont("Helvetica-Bold", 65)
                    c.setFillColorRGB(0.92, 0.92, 0.92) 
                    c.translate(width / 2, height / 2) 
                    c.rotate(45) 
                    c.drawCentredString(0, 0, "PneumoniaLens AI")
                    c.restoreState() 
                    
                    c.setFillColorRGB(0, 0, 0) 
                    c.setFont("Helvetica-Bold", 18)
                    c.drawString(50, height - 70, "PneumoniaLens AI Diagnostic Report")
                    c.setLineWidth(1)
                    c.line(50, height - 80, width - 50, height - 80) 
                    
                    overlay_pil = Image.fromarray(overlay)
                    img_original = ImageReader(pil_img)
                    img_heatmap = ImageReader(overlay_pil)
                    
                    img_y = height - 330 
                    
                    c.setLineWidth(1)
                    c.setStrokeColorRGB(0.6, 0.6, 0.6) 
                    c.rect(50, img_y, 230, 230)
                    c.rect(310, img_y, 230, 230)
                    
                    c.drawImage(img_original, 50, img_y, width=230, height=230, preserveAspectRatio=True)
                    c.drawImage(img_heatmap, 310, img_y, width=230, height=230, preserveAspectRatio=True)
                    
                    c.setFillColorRGB(0, 0, 0)
                    c.setFont("Helvetica-Oblique", 10)
                    c.drawString(115, img_y - 15, "Original X-Ray")
                    c.drawString(355, img_y - 15, "Grad-CAM Heatmap Focus")
                    
                    meta_y = img_y - 60
                    c.setFont("Helvetica", 12)
                    c.drawString(50, meta_y, f"Operator: Dr. {st.session_state.doctor_name}")
                    c.drawString(50, meta_y - 20, f"Date & Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    
                    c.setFont("Helvetica-Bold", 12)
                    c.drawString(50, meta_y - 50, f"AI Diagnosis: {final_label}")
                    c.drawString(50, meta_y - 70, f"Confidence Score: {confidence*100:.2f}%")
                    
                    find_y = meta_y - 110
                    c.setFont("Helvetica-Bold", 14)
                    c.drawString(50, find_y, f"Clinical Findings - {final_label}:")
                    
                    text_obj = c.beginText(50, find_y - 25)
                    text_obj.setFont("Helvetica", 11)
                    wrapped_text = textwrap.wrap(findings_text, width=85)
                    for line in wrapped_text:
                        text_obj.textLine(line)
                    c.drawText(text_obj)
                    
                    disc_y = find_y - 110 
                    c.setFont("Helvetica-Bold", 10)
                    c.drawString(50, disc_y, "CLINICAL DISCLAIMER:")
                    
                    disclaimer = "This report was generated by an Artificial Intelligence model (PneumoniaLens v2.0). As an AI, it is subject to errors and false positives/negatives. It cannot account for patient history, bloodwork, or full clinical context. This software is strictly an assistive 'second-opinion' tool and MUST NOT be used as a standalone diagnostic device. Please consult a specialized radiologist or attending physician for a definitive diagnosis and treatment plan."
                    
                    disc_obj = c.beginText(50, disc_y - 15)
                    disc_obj.setFont("Helvetica", 9)
                    wrapped_disc = textwrap.wrap(disclaimer, width=100)
                    for line in wrapped_disc:
                        disc_obj.textLine(line)
                    c.drawText(disc_obj)
                    
                    c.save()
                    buffer.seek(0)
                    return buffer
                st.download_button("Download Detailed PDF Report", generate_pdf(), file_name=f"PneumoniaLens AI Detailed Report - {final_label}.pdf", type="primary")
        st.caption("This diagnostic tool is designed to assist radiologists by providing a second opinion. It is not a replacement for professional medical judgment. Always consult with a healthcare provider for diagnosis and treatment decisions.")


# ---> 2. ADMIN WORKSPACE (Only visible when Admin is logged in) <---
elif st.session_state.logged_in_admin:
    tab_admin, = st.tabs(["🛡️ Administrator Control Panel"])
    
    with tab_admin:
        update_activity()
        st.title("System Administrator Dashboard")
        st.success("✅ Global Admin access granted.")
        st.markdown("---")
        st.markdown("### 📋 Administrator Control Panel")
        st.markdown("#### ➕ Register Medical Staff")
        
        with st.expander("Open Registration Form"):
            with st.form("admin_doc_reg_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    admin_reg_first = st.text_input("First Name")
                    admin_reg_email = st.text_input("Professional Email")
                with col2:
                    admin_reg_last = st.text_input("Last Name")
                    admin_reg_dept = st.selectbox("Department", ["Radiology", "Emergency Triage", "Internal Medicine", "General Practice"])
                
                submit_admin_reg = st.form_submit_button("Generate Credentials & Register")

                if submit_admin_reg:
                    if admin_reg_first and admin_reg_last and admin_reg_email:
                        with st.spinner("Sending request to Cloud API..."):
                            payload = {
                                "firstName": admin_reg_first,
                                "lastName": admin_reg_last,
                                "email": admin_reg_email,
                                "dept": admin_reg_dept
                            }
                            try:
                                response = requests.post(APPS_SCRIPT_URL, json=payload)
                                if response.status_code == 200:
                                    result = response.json()
                                    if result.get("status") == "success":
                                        new_id = result["id"]
                                        new_pass = result["password"]
                                        st.success(f"✅ Doctor Registered Successfully via API!")
                                        st.code(f"Doctor ID: {new_id}\nPassword: {new_pass}", language="text")
                                    else:
                                        st.error(f"Backend Error: {result.get('message')}")
                                else:
                                    st.error("Cloud server error. Could not connect to API.")
                            except Exception as e:
                                st.error(f"Failed to connect: {e}")
                    else:
                        st.error("Please fill in all required fields.")
        
        st.markdown("#### Cloud Registered Doctors")
        docs_df = get_doctors_db()
        if docs_df.empty:
            st.info("No doctors registered yet.")
        else:
            st.dataframe(docs_df.drop(columns=["Password"], errors="ignore"), use_container_width=True, hide_index=True)
            with st.form("revoke_form", clear_on_submit=True):
                revoke_id = st.text_input("Enter Doctor ID to Revoke:")
                submit_revoke = st.form_submit_button("Revoke Access")
                
                if submit_revoke:
                    st.cache_data.clear()
                    docs_df = get_doctors_db()
                    docs_df["ID"] = docs_df["ID"].astype(str).str.split('.').str[0].str.strip()
                    clean_revoke_id = str(revoke_id).strip()
                    
                    if clean_revoke_id in docs_df["ID"].values:
                        docs_df = docs_df[docs_df["ID"] != clean_revoke_id]
                        update_doctors_db(docs_df)
                        st.success(f"Access revoked for ID: {clean_revoke_id}")
                        st.rerun()
                    else:
                        st.error("Doctor ID not found in database.")
        
        st.markdown("#### Cloud Diagnostic Logs")
        logs_df = get_logs_db()
        if logs_df.empty:
            st.info("No diagnostic history found.")
        else:
            st.dataframe(logs_df, use_container_width=True, hide_index=True)


# ---> 3. PUBLIC WEBSITE (Visible when logged out) <---
else:
    tab_home, tab_login, tab_analytics, tab_doc = st.tabs([
        "🏠 Home",
        "🔐 Login Portal",
        "📊 Model Analytics",
        "📖 Documentation"
    ])

    # ======================= HOME ============================
    with tab_home:
        update_activity()
        st.title("Welcome to PneumoniaLens AI")
        
        # --- NEW: AI TERMINAL TYPING EFFECT ---
        st.markdown("""
        <div class="typing-container">
            <div class="typing-text">Advanced Clinical Second-Opinion System</div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        st.markdown("### 🎯 Our Mission: Bridging the Diagnostic Gap")
        st.markdown("""
        <div class="card-grid-2">
            <div class="custom-card">
                <div class="card-title">🧩 The Core Problem</div>
                <div class="card-text">In a highly stressful and dynamic environment, the sheer volume of thoracic images can result in "diagnostic fatigue." Our mission is to offer a second pair of eyes that uses AI to specialize in the critical 3-way differential diagnosis between normal lungs and the two different forms of pneumonia.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">📊 Clinically Honest Accuracy</div>
                <div class="card-text">While other models boast a purported '99%' accuracy rate for a simple binary set, we're more realistic with a grounded accuracy rate of <b>81.50%</b> for the much more difficult 3-class problem, which acknowledges the visual overlap between viral and bacterial patterns.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">⚡ Rapid Triage</div>
                <div class="card-text">With the ability to analyze 60 layers of DenseNet121 architecture in mere seconds, this is a digital filter that works before the human eye ever lays a hand on the image, ensuring critical cases are flagged immediately.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">⚖️ Standardizing Care</div>
                <div class="card-text">Our goal is to eliminate the subjective element of interpretation. Whether the image is the first of the morning or the last of a 12-hour graveyard shift, the AI provides a consistent, objective baseline.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🏥 Practical Use Cases & Real-World Handling")
        st.markdown("""
        <div class="card-grid-3">
            <div class="custom-card">
                <div class="card-title">🚑 Emergency Dept. Triage</div>
                <div class="card-text">
                    <i>The Situation:</i> Ten X-rays arrive simultaneously in a crowded ER.<br><br>
                    <i>How the Model Handles It:</i> The AI instantly scans the batch. It identifies a "Bacterial" signature with high confidence in one patient, signaling a potential lobar consolidation that requires immediate antibiotics.
                </div>
            </div>
            <div class="custom-card">
                <div class="card-title">🦠 Viral vs. Bacterial</div>
                <div class="card-text">
                    <i>The Situation:</i> A patient presents with fever and cough; the visual symptoms are ambiguous.<br><br>
                    <i>How the Model Handles It:</i> Uses deep-feature extraction to look for subtle texture differences (patchy vs consolidated). By providing a Confidence Metric, it assists the clinician in deciding between antibiotics or antivirals.
                </div>
            </div>
            <div class="custom-card">
                <div class="card-title">🔍 Fatigue Reduction</div>
                <div class="card-text">
                    <i>The Situation:</i> A radiologist is on their 100th scan of a 12-hour shift.<br><br>
                    <i>How the Model Handles It:</i> The Grad-CAM Focus Map acts as a "Heatmap of Interest." It highlights the specific region of the lung that triggered the AI's classification, ensuring small areas of interest aren't missed.
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
                
        st.markdown("### 🎯Core Visualization")
        gradcam_path = "assets/gradcam_final_overlay.png" 
        col_img, col_text = st.columns([1.2, 1]) 
        
        with col_img:
            if os.path.exists(gradcam_path):
                st.image(gradcam_path, use_container_width=True)
            else:
                st.error(f"⚠️ Image not found at: {gradcam_path}")
                
        with col_text:
            st.markdown("#### Explainable AI (XAI) in Action")
            st.write("This Grad-CAM (Gradient-weighted Class Activation Mapping) overlay demonstrates how our AI interprets thoracic X-rays. Instead of a 'black box' diagnosis, the model produces a heatmap highlighting the exact regions of the lung that heavily influenced its decision.")
            st.markdown("""
            * **🔴 Red/Warm Areas:** High-importance regions indicating severe pathology (e.g., dense consolidations).
            * **🔵 Blue/Cool Areas:** Low-importance regions representing healthy tissue or background.
            """)
            st.info("This provides clinical transparency, allowing doctors to verify that the AI is looking at the correct anatomical features rather than image artifacts.")

            st.markdown("<br><br>", unsafe_allow_html=True) 
            components.html(
                """
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                body {
                    margin: 0;
                    padding: 30px; 
                    display: flex;
                    justify-content: center;
                    background: transparent;
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    overflow: visible;
                }
                html { overflow: visible; }
                
                /* Sonar Ripple Pulse for Main Call to Action */
                @keyframes pulseRing {
                    0% { box-shadow: 0 0 0 0 rgba(0, 255, 255, 0.7); }
                    70% { box-shadow: 0 0 0 20px rgba(0, 255, 255, 0); }
                    100% { box-shadow: 0 0 0 0 rgba(0, 255, 255, 0); }
                }

                .get-started-btn {
                    position: relative;
                    background-color: transparent;
                    color: #00FFFF;
                    font-size: 18px;
                    font-weight: 600;
                    padding: 14px 36px;
                    border: 2px solid #00FFFF;
                    border-radius: 30px;
                    cursor: pointer;
                    transition: all 0.35s ease;
                    outline: none;
                    animation: pulseRing 2.5s infinite; 
                }
                .get-started-btn span {
                    display: inline-block;
                    position: relative;
                    transition: 0.35s;
                }
                .get-started-btn span:after {
                    content: '➔'; 
                    position: absolute;
                    opacity: 0;
                    top: 50%;
                    transform: translateY(-50%); 
                    right: -40px;
                    font-size: 26px; 
                    transition: 0.35s;
                }
                .get-started-btn:hover {
                    background-color: #00FFFF;
                    color: black;
                    box-shadow: 0px 0px 25px 8px rgba(0, 255, 255, 0.6);
                    animation-play-state: paused; 
                }
                .get-started-btn:hover span {
                    padding-right: 45px; 
                }
                .get-started-btn:hover span:after {
                    opacity: 1;
                    right: 0px;
                }
                </style>
                </head>
                <body>
                    <button class="get-started-btn" onclick="
                        const tabs = window.parent.document.querySelectorAll('button[data-baseweb=\\'tab\\']');
                        for (let i = 0; i < tabs.length; i++) {
                            if (tabs[i].innerText.includes('Login Portal')) {
                                tabs[i].click();
                                break;
                            }
                        }
                    ">
                        <span>Get Started</span>
                    </button>
                </body>
                </html>
                """,
                height=120
            )

    # ================= LOGIN PORTAL ==========================
    with tab_login:
        update_activity()
        st.title("🔐 Authentication & Management")
        
        sub_tab_register, sub_tab_login, sub_tab_admin = st.tabs(["📝 Register", "👨‍⚕️ Doctor Login", "🛡️ Admin Access"])

        with sub_tab_register:
            st.subheader("Medical Staff Registration")
            st.info("The system will automatically generate a secure 6-digit Doctor ID and Password.")
            
            with st.form("registration_form", clear_on_submit=True):
                reg_first = st.text_input("First Name")
                reg_last = st.text_input("Last Name")
                reg_email = st.text_input("Professional Email")
                reg_dept = st.selectbox("Department", ["Radiology", "Emergency Triage", "Internal Medicine", "General Practice"])

                submit_reg = st.form_submit_button("Generate Credentials & Register")

                if submit_reg:
                    if reg_first and reg_last and reg_email:
                        with st.spinner("Connecting to secure Cloud API..."):
                            payload = {
                                "firstName": reg_first,
                                "lastName": reg_last,
                                "email": reg_email,
                                "dept": reg_dept
                            }
                            try:
                                response = requests.post(APPS_SCRIPT_URL, json=payload)
                                if response.status_code == 200:
                                    result = response.json()
                                    if result.get("status") == "success":
                                        new_id = result["id"]
                                        new_pass = result["password"]
                                        st.success("✅ Registration Successful! Credentials securely generated by Cloud Backend.")
                                        st.code(f"Doctor ID: {new_id}\nPassword: {new_pass}", language="text")
                                    else:
                                        st.error(f"Backend Error: {result.get('message')}")
                                else:
                                    st.error("Cloud server error. Could not connect to API.")
                            except Exception as e:
                                st.error(f"Failed to connect to backend API: {e}")
                    else:
                        st.error("Please fill in all required fields (Name and Email).")
            st.info("In case you don't want to register use the Id and Password given below to log in as Dr.Guest Id- 111111 Password- 1234567890")
        
        with sub_tab_login:
            st.subheader("Doctor Login")
            with st.form("doctor_login_form", clear_on_submit=True):
                log_id = st.text_input("Doctor ID (6-digit number)")
                log_pw = st.text_input("Password", type="password")
                submit_doc = st.form_submit_button("Login")

                if submit_doc:
                    with st.spinner("Verifying with Database..."):
                        st.cache_data.clear()
                        docs_df = get_doctors_db()
                        docs_df["ID"] = docs_df["ID"].astype(str).str.split('.').str[0].str.strip()
                        docs_df["Password"] = docs_df["Password"].astype(str).str.strip()
                        
                        clean_id = str(log_id).strip()
                        clean_pw = str(log_pw).strip()
                        match = docs_df[(docs_df["ID"] == clean_id) & (docs_df["Password"] == clean_pw)]
                    
                    if not match.empty:
                        st.session_state.logged_in_doctor = clean_id
                        doctor_name = match.iloc[0]["Name"]
                        st.session_state.doctor_name = doctor_name 
                        
                        raw_token_string = f"{clean_id}||{doctor_name}"
                        encoded_token = base64.urlsafe_b64encode(raw_token_string.encode()).decode()
                        st.query_params["token"] = encoded_token
                        
                        st.session_state.show_login_toast = f"Authenticated successfully: Dr. {doctor_name}"
                        st.rerun() 
                    else:
                        st.error("Invalid Doctor ID or Password.")
            st.info("In case you didn't registered use the Id and Password given below to log in as Dr.Guest Id- 111111 Password- 1234567890")
            
        with sub_tab_admin:
            st.subheader("System Administrator Login")
            try:
                ADMIN_ID = st.secrets["admin"]["id"]
                ADMIN_PW = st.secrets["admin"]["password"]
            except KeyError:
                st.error("⚠️ Admin credentials not found in secrets.toml! Defaulting to admin/admin")
                ADMIN_ID = "admin"
                ADMIN_PW = "admin"
            
            with st.form("admin_login_form", clear_on_submit=True):
                a_u = st.text_input("Admin ID")
                a_p = st.text_input("Admin Password", type="password")
                submit_admin = st.form_submit_button("Authorize Admin")
                
                if submit_admin:
                    if a_u == ADMIN_ID and a_p == ADMIN_PW:
                        st.session_state.logged_in_admin = True
                        st.rerun()
                    else:
                        st.error("Unauthorized access.")

    # =================== ANALYTICS ===========================
    with tab_analytics:
        update_activity()
        st.title("📊 Detailed Model Analytics")

        st.markdown("""
        <div class="card-grid-3">
            <div class="custom-card">
                <div class="card-title">🛠️ Fine-Tuning Methodology</div>
                <div class="card-text">Based on DenseNet121 architecture (ImageNet pre-training), the team successfully fine-tuned the model by unfreezing 60 specific layers to capture intricate thoracic features. A strict class-weight dictionary was applied during training to address the significant visual overlap between Viral and Bacterial pneumonia presentations.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">💻 Training Environment</div>
                <div class="card-text">The project utilized a hybrid approach, combining local development with scalable cloud infrastructure. The neural network was fully trained and optimized using a high-performance NVIDIA T4 GPU via Google Colab, leveraging accelerated computing for complex medical deep learning tasks.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">📊 Key Performance Metrics</div>
                <div class="card-text">The final architecture was trained through exactly 30 full epochs to maximize accuracy while avoiding overfitting. The resulting model established a grounded, clinically honest <b>81.50% true accuracy</b> on the complex 3-class differential diagnosis problem.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("### 📈 Training Results")
        st.markdown("""
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px;">
            <div class="custom-card" style="text-align: center; padding: 25px;">
                <div class="kpi-value">81.50%</div>
                <div class="kpi-label">🎯 Accuracy</div>
            </div>
            <div class="custom-card" style="text-align: center; padding: 25px;">
                <div class="kpi-value">82.00%</div>
                <div class="kpi-label">⚖️ Precision</div>
            </div>
            <div class="custom-card" style="text-align: center; padding: 25px;">
                <div class="kpi-value">81.00%</div>
                <div class="kpi-label">🔄 Recall</div>
            </div>
            <div class="custom-card" style="text-align: center; padding: 25px;">
                <div class="kpi-value">81.00%</div>
                <div class="kpi-label">✨ F1-Score</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 📈 Training History Curves")
        curve1_path = "assets/curve1.png"
        curve2_path = "assets/curve2.png"

        st.markdown(f"""
        <div class="custom-card" style="margin-bottom: 30px;">
            <div class="card-title">📉 Training & Validation Progress</div>
            <div class="card-text" style="text-align: center; margin-bottom: 20px; font-style: oblique;">
                These curves visualize the DenseNet121 model's learning progress. The convergence between the validation (orange) and training (blue) lines for both accuracy and loss demonstrates a well-generalized model with optimized weights.
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if os.path.exists(curve1_path):
                st.image(curve1_path, use_container_width=True)
            else:
                st.error(f"⚠️ Image not found: {curve1_path}")
                
        with col_c2:
            if os.path.exists(curve2_path):
                st.image(curve2_path, use_container_width=True)
            else:
                st.error(f"⚠️ Image not found: {curve2_path}")

        st.markdown("---")
        st.markdown("### 📈 3-Class Confusion Matrix")
        matrix_path = "assets/final_confusion_matrix_3class.png"

        col_mat1, col_mat2 = st.columns([1.2, 1])
        with col_mat1:
            if os.path.exists(matrix_path):
                st.image(matrix_path, use_container_width=True)
            else:
                st.error(f"⚠️ Image not found at: {matrix_path}")
                
        with col_mat2:
            st.markdown("#### Performance Breakdown")
            st.write("The confusion matrix provides a transparent look at the model's predictive performance across all three categories during rigorous testing.")
            st.markdown("""
            * **Diagonal Alignment:** The strong values across the diagonal indicate a high rate of true positives for normal, bacterial, and viral cases.
            * **The Viral/Bacterial Overlap:** As seen in the matrix, the majority of misclassifications occur between viral and bacterial pneumonia. This accurately reflects real-world clinical difficulty, as these pathologies often share overlapping visual traits.
            """)
            st.info("By implementing class balancing during training, we penalized the model heavily for missing bacterial cases, prioritizing patient safety in triage scenarios.")
        st.markdown("---")

    # ================= DOCUMENTATION =========================
    with tab_doc:
        update_activity()
        st.title("📃 Documentation & Technical Specs")
        
        st.markdown("""
        <div class="custom-card" style="border-left: 5px solid #00FFFF; margin-bottom: 30px;">
            <div class="card-title">🧠 DenseNet121 – Clinical Architecture</div>
            <div class="card-text">
                DenseNet-121 is a 121-layer Convolutional Neural Network (CNN) architecture. It enhances the efficiency of Deep Learning by providing a direct connection between each layer and every other layer in a feed-forward manner. DenseNet-121 utilizes <b>"dense blocks"</b> to concatenate feature maps, which drastically reduces the number of parameters while maximizing information flow across the network.
            </div>
        </div>
        """, unsafe_allow_html=True)
        # ADD CENTRALIZED IMAGE BELOW ARCHITECTURE DESCRIPTION
        doc_img_path = "assets/densenet_working_process.png" # Changed to .jpg based on your uploaded file
        if os.path.exists(doc_img_path):
            col1, col2, col3 = st.columns([1, 2, 1]) # The middle column is twice as wide
            with col2:
                st.image(doc_img_path, caption="DenseNet Working Process", use_container_width=True)
        else:
            st.error(f"⚠️ Image not found at: {doc_img_path}. Please check your 'assets' folder.")
        st.markdown("<h3 style='color: #00FFFF; margin-bottom: 15px;'>✨ Key Architectural Features</h3>", unsafe_allow_html=True)
        st.markdown("""
        <div class="card-grid-2">
            <div class="custom-card">
                <div class="card-title">🔗 Dense Connectivity</div>
                <div class="card-text">Unlike standard CNNs, DenseNet-121 connects every layer to all subsequent layers in a block. This encourages maximum feature reuse and effectively solves the vanishing gradient problem during training.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">🏗️ Block Structure</div>
                <div class="card-text">Features an initial 7x7 convolutional layer followed by four dense blocks (containing 6, 12, 24, and 16 layers respectively). Efficient transition layers are implemented between each block.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">⚡ Computational Efficiency</div>
                <div class="card-text">Utilizes a strict 32-filter growth rate. This structural choice makes the network highly computationally efficient and vastly improves deep-feature usage compared to standard ResNet models.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">🖼️ Standardized Input</div>
                <div class="card-text">Thoracic X-ray images are automatically pre-processed, normalized (scaled to 0-1), and resized to a standard <b>224x224</b> resolution matrix before being ingested into the network for clinical inference.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.title("❔ Most Probable FAQs")
        st.markdown("""
        <div class="card-grid-3">
            <div class="custom-card">
                <div class="card-title">1. Why DenseNet121 over ResNet or VGG16?</div>
                <div class="card-text">DenseNet121 utilizes dense connections to maximize feature reuse and gradient flow, allowing the model to capture subtle medical patterns with significantly fewer parameters than VGG or ResNet.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">2. How was the overfitting handled?</div>
                <div class="card-text">We combined data augmentation (rotation, zooming) with dropout layers to prevent the model from memorizing the training set, ensuring it generalizes to real-world clinical images.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">3. What is the clinical value of Grad-CAM?</div>
                <div class="card-text">Grad-CAM provides Explainable AI (XAI) by overlaying heatmaps on X-rays; this allows radiologists to verify that the AI is focusing on actual pathology rather than image noise.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">4. Why use an adjustable threshold?</div>
                <div class="card-text">It allows clinicians to tune the model for high sensitivity in emergency triage (missing no cases) or high specificity in routine screening (reducing false alarms).</div>
            </div>
            <div class="custom-card">
                <div class="card-title">5. How is a '0.0%' idle CPU load maintained?</div>
                <div class="card-text">By using <code>@st.cache_resource</code>, the 81MB model is loaded into RAM once upon startup; this eliminates redundant processing and keeps the app responsive without taxing the CPU during idle periods.</div>
            </div>
            <div class="custom-card">
                <div class="card-title">6. How was the '81.50%' accuracy validated?</div>
                <div class="card-text">The metric was established on a rigorous, unseen test split and further verified through 'in-the-wild' testing with diverse external images to ensure robust real-world performance.</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# ==========================================
# FLOATING AI ASSISTANT WIDGET
# ==========================================
try:
    LLM_API_KEY = st.secrets["api"]["key"]
except:
    LLM_API_KEY = ""

bot_user_name = st.session_state.doctor_name if st.session_state.doctor_name else "Guest"
welcome_msg = f"Hello {bot_user_name}! I am the PneumoniaLens Assistant. Ask me about our AI model, our team, or any medical terms!"

raw_chat_code = f"""
<script>
(function() {{
    const currentUser = "{bot_user_name}";
    const API_KEY = "{LLM_API_KEY}"; 
    const existingContainer = window.parent.document.getElementById('plens-chatbot-container');
    const existingStyle = window.parent.document.getElementById('plens-chatbot-style');
    
    if (existingContainer) {{
        if (existingContainer.getAttribute('data-user') === currentUser) {{
            return; 
        }} else {{
            existingContainer.remove();
            if (existingStyle) existingStyle.remove();
        }}
    }}

    const style = window.parent.document.createElement('style');
    style.id = 'plens-chatbot-style';
    style.innerHTML = `
        @keyframes floatIdle {{
            0% {{ transform: translateY(0px); }}
            50% {{ transform: translateY(-8px); }}
            100% {{ transform: translateY(0px); }}
        }}
        #plens-chatbot-container {{ position: fixed; bottom: 80px; right: 30px; z-index: 999999; font-family: 'Segoe UI', Tahoma, sans-serif; }}
        #chat-fab {{ width: 65px; height: 65px; border-radius: 50%; background: linear-gradient(135deg, #008080, #00ced1); box-shadow: 0 4px 20px rgba(0, 255, 255, 0.4), 0 0 0 2px rgba(0, 255, 255, 0.8); display: flex; justify-content: center; align-items: center; cursor: pointer; transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275), box-shadow 0.3s ease; float: right; position: relative; animation: floatIdle 3s ease-in-out infinite; }}
        #chat-fab:hover {{ transform: scale(1.1) rotate(-5deg); box-shadow: 0 6px 25px rgba(0, 255, 255, 0.8), 0 0 0 2px rgba(0, 255, 255, 1); animation-play-state: paused; }}
        #chat-fab svg {{ width: 32px; height: 32px; fill: black; transition: transform 0.3s ease; }}
        
        #chat-tooltip {{ position: absolute; right: 80px; bottom: 15px; background: linear-gradient(135deg, #00FFFF, #008080); color: black; padding: 8px 14px; border-radius: 20px; border-bottom-right-radius: 0px; font-size: 13px; font-weight: bold; box-shadow: 0 4px 10px rgba(0, 255, 255, 0.4); opacity: 0; transform: translateX(20px) scale(0.9); transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275); pointer-events: none; white-space: nowrap; }}
        #chat-tooltip.show {{ opacity: 1; transform: translateX(0) scale(1); }}

        #chat-window {{ 
            display: none; 
            position: fixed; 
            top: 50%; 
            left: 50%; 
            width: 850px; 
            max-width: 95vw; 
            height: 600px; 
            max-height: 85vh; 
            background: rgba(15, 15, 15, 0.95); 
            border: 1px solid rgba(0, 255, 255, 0.5); 
            border-radius: 20px; 
            box-shadow: 0 25px 50px rgba(0,0,0,0.9), 0 0 30px rgba(0, 255, 255, 0.2); 
            flex-direction: column; 
            overflow: hidden; 
            transform-origin: center center; 
            transform: translate(-50%, -50%) scale(0.8); 
            opacity: 0; 
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.2); 
            z-index: 999999;
        }}
        #chat-window.open {{ 
            display: flex; 
            transform: translate(-50%, -50%) scale(1); 
            opacity: 1; 
            backdrop-filter: blur(10px); 
        }}
        
        #chat-header {{ background: rgba(20, 20, 20, 0.9); padding: 16px 20px; color: #00FFFF; font-weight: 800; font-size: 16px; display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #00FFFF; box-shadow: 0 4px 10px rgba(0,0,0,0.3); z-index: 10; }}
        .header-title {{ display: flex; align-items: center; gap: 10px; }}
        .online-dot {{ width: 10px; height: 10px; background-color: #00FF00; border-radius: 50%; box-shadow: 0 0 8px #00FF00; animation: pulse 2s infinite; }}
        @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 0 rgba(0, 255, 0, 0.7); }} 70% {{ box-shadow: 0 0 0 6px rgba(0, 255, 0, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(0, 255, 0, 0); }} }}
        #chat-close {{ cursor: pointer; color: #00FFFF; font-size: 24px; transition: color 0.2s, transform 0.2s; }}
        #chat-close:hover {{ color: #ff4b4b; transform: scale(1.2); }}
        #chat-messages {{ flex: 1; padding: 25px; overflow-y: auto; display: flex; flex-direction: column; gap: 15px; }}
        #chat-messages::-webkit-scrollbar {{ width: 6px; }}
        #chat-messages::-webkit-scrollbar-thumb {{ background: rgba(0, 255, 255, 0.5); border-radius: 3px; }}
        .msg-row {{ display: flex; align-items: flex-end; gap: 10px; animation: popIn 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards; opacity: 0; transform: translateY(10px); max-width: 100%; }}
        .bot-row {{ justify-content: flex-start; }}
        .user-row {{ justify-content: flex-end; }}
        .avatar {{ width: 35px; height: 35px; background: #1C1829; border-radius: 50%; display: flex; justify-content: center; align-items: center; border: 1px solid #00FFFF; flex-shrink: 0; box-shadow: 0 0 8px rgba(0,255,255,0.3); }}
        .avatar svg {{ width: 20px; height: 20px; fill: #00FFFF; }}
        .msg-content {{ display: flex; flex-direction: column; max-width: 80%; }}
        .msg-bubble {{ padding: 14px 18px; font-size: 15px; line-height: 1.5; word-wrap: break-word; box-shadow: 0 4px 6px rgba(0,0,0,0.2); }}
        .bot-msg {{ background: #1a1a1a; color: #E0E0E0; border-radius: 16px 16px 16px 4px; border: 1px solid rgba(0, 255, 255, 0.3); }}
        .user-msg {{ background: linear-gradient(135deg, #00ced1, #008080); color: black; font-weight: 500; border-radius: 16px 16px 4px 16px; border: 1px solid rgba(0, 255, 255, 0.3); }}
        .msg-time {{ font-size: 11px; color: #787088; margin-top: 5px; padding: 0 5px; }}
        .user-time {{ text-align: right; }}
        .bot-time {{ text-align: left; }}
        .typing-bubble {{ display: flex; align-items: center; gap: 5px; padding: 14px 16px; min-height: 20px; }}
        .dot {{ width: 8px; height: 8px; background-color: #00FFFF; border-radius: 50%; animation: bounce 1.4s infinite ease-in-out both; }}
        .dot:nth-child(1) {{ animation-delay: -0.32s; }}
        .dot:nth-child(2) {{ animation-delay: -0.16s; }}
        @keyframes bounce {{ 0%, 80%, 100% {{ transform: scale(0); opacity: 0.5; }} 40% {{ transform: scale(1); opacity: 1; }} }}
        @keyframes popIn {{ to {{ opacity: 1; transform: translateY(0); }} }}
        #chat-input-area {{ display: flex; padding: 20px; background: rgba(20, 20, 20, 0.9); border-top: 1px solid rgba(0, 255, 255, 0.3); align-items: center; gap: 15px; }}
        #chat-input {{ flex: 1; background: #13111C; border: 1px solid rgba(255,255,255,0.1); color: white; padding: 15px 20px; border-radius: 30px; outline: none; font-size: 15px; transition: all 0.3s; }}
        #chat-input:focus {{ border-color: #00FFFF; box-shadow: 0 0 10px rgba(0, 255, 255, 0.2); }}
        #send-btn {{ background: #008080; border: none; border-radius: 50%; width: 45px; height: 45px; display: flex; justify-content: center; align-items: center; cursor: pointer; transition: transform 0.2s, background 0.2s; }}
        #send-btn:hover:not(:disabled) {{ transform: scale(1.1) rotate(15deg); background: #00FFFF; }}
        #send-btn svg {{ fill: black; width: 20px; height: 20px; }}
    `;
    window.parent.document.head.appendChild(style);

    const getTime = () => new Date().toLocaleTimeString([], {{ hour: '2-digit', minute: '2-digit' }});
    const botIcon = `<svg viewBox="0 0 24 24"><path d="M12 2a2 2 0 0 1 2 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 0 1 7 7h1a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1h-1v1a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2v-1H1a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1h1a7 7 0 0 1 7-7h1V5.73A2 2 0 1 1 12 2zm-3 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z"/></svg>`;

    const chatHTML = `
        <div id="chat-tooltip">PneumoniaLens Support 👋</div>
        <div id="chat-window">
            <div id="chat-header">
                <div class="header-title"><div class="online-dot"></div> PneumoniaLens AI</div>
                <div id="chat-close" onclick="window.togglePlensChat()">✖</div>
            </div>
            <div id="chat-messages">
                <div class="msg-row bot-row">
                    <div class="avatar">${{botIcon}}</div>
                    <div class="msg-content">
                        <div class="msg-bubble bot-msg">{welcome_msg}</div>
                        <div class="msg-time bot-time">${{getTime()}}</div>
                    </div>
                </div>
            </div>
            <div id="typing-indicator" class="msg-row bot-row" style="display: none;">
                <div class="avatar">${{botIcon}}</div>
                <div class="msg-content"><div class="msg-bubble bot-msg typing-bubble"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>
            </div>
            <div id="chat-input-area">
                <input type="text" id="chat-input" placeholder="Ask about the team or model..." onkeypress="window.handlePlensEnter(event)" autocomplete="off">
                <button id="send-btn" onclick="window.sendPlensMessage()">
                    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"></path></svg>
                </button>
            </div>
        </div>
        <div id="chat-fab" onclick="window.togglePlensChat()">
            <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2z"></path></svg>
        </div>
    `;
    
    const container = window.parent.document.createElement('div');
    container.id = 'plens-chatbot-container';
    container.setAttribute('data-user', currentUser);
    container.innerHTML = chatHTML;
    window.parent.document.body.appendChild(container);

    function triggerTooltip() {{
        const tooltip = window.parent.document.getElementById('chat-tooltip');
        const chatWin = window.parent.document.getElementById('chat-window');
        if (tooltip && !chatWin.classList.contains('open')) {{
            tooltip.classList.add('show');
            setTimeout(() => {{ tooltip.classList.remove('show'); }}, 5000);
        }}
    }}
    setTimeout(triggerTooltip, 5000);

    const getRandomResponse = (array) => array[Math.floor(Math.random() * array.length)];

    window.parent.togglePlensChat = function() {{
        const chatWin = window.parent.document.getElementById('chat-window');
        const tooltip = window.parent.document.getElementById('chat-tooltip');
        if (chatWin.classList.contains('open')) {{
            chatWin.classList.remove('open');
            setTimeout(() => chatWin.style.display = 'none', 400); 
        }} else {{
            if(tooltip) tooltip.classList.remove('show'); 
            chatWin.style.display = 'flex';
            setTimeout(() => chatWin.classList.add('open'), 10);
            window.parent.document.getElementById('chat-input').focus();
        }}
    }};

    window.parent.handlePlensEnter = function(e) {{
        if (e.key === 'Enter') {{ window.parent.sendPlensMessage(); }}
    }};

    window.parent.sendPlensMessage = async function() {{
        const inputField = window.parent.document.getElementById('chat-input');
        const sendBtn = window.parent.document.getElementById('send-btn');
        const msgBox = window.parent.document.getElementById('chat-messages');
        const typingInd = window.parent.document.getElementById('typing-indicator');
        const text = inputField.value.trim();
        
        if (!text) return;

        inputField.disabled = true; sendBtn.disabled = true;
        const timeNow = getTime();
        msgBox.innerHTML += `
            <div class="msg-row user-row">
                <div class="msg-content">
                    <div class="msg-bubble user-msg">${{text}}</div>
                    <div class="msg-time user-time">${{timeNow}}</div>
                </div>
            </div>
        `;
        inputField.value = '';
        msgBox.scrollTop = msgBox.scrollHeight;

        msgBox.appendChild(typingInd); 
        typingInd.style.display = 'flex';
        msgBox.scrollTop = msgBox.scrollHeight;
        
        let reply = "";
        let tLower = text.toLowerCase();
        let useAPI = false;

        if (tLower.includes('password') || tLower.includes('admin') || tLower.includes('database')) {{
            reply = "🛡️ <b>Security Alert:</b> I am programmed to protect clinical data. I cannot reveal administrative passwords!";
        }}
        else if (tLower.includes('team') || tLower.includes('built') || tLower.includes('creator') || tLower.includes('who made') || tLower.includes('who make') || tLower.includes('author')) {{
            reply = "PneumoniaLens AI was built by a brilliant team of four developers: <b>Puskar Mandal, Poulymi Samanta, Ronit Das, and Jayanti Jana</b>. 🚀";
        }}
        else if (tLower.includes('college') || tLower.includes('institute') || tLower.includes('university') || tLower.includes('nsti')) {{
            reply = "This project was proudly developed by the students at <b>NSTI Howrah</b>! 🎓";
        }}
        else if (tLower.includes('mentor') || tLower.includes('guide') || tLower.includes('sayanti')) {{
            reply = "Our project was expertly guided by our esteemed mentor, <b>Sayanti Manna</b>. We are incredibly grateful for her guidance and support throughout development! 🌟";
        }}
        else if (tLower.includes('model') || tLower.includes('architecture') || tLower.includes('densenet')) {{
            reply = "The system is powered by a fine-tuned <b>DenseNet121</b> Deep Learning architecture with 60 unfrozen layers.";
        }}
        else if (tLower.includes('accuracy') || tLower.includes('performance') || tLower.includes('results')) {{
            reply = "The model achieves a clinically honest <b>81.50% true accuracy</b> on a highly complex 3-class differential diagnosis.";
        }}
        else if (tLower.match(/\\b(hi|hello|hey|yo)\\b/)) {{ 
            reply = getRandomResponse(["Hi there! I am the PneumoniaLens Assistant.", "Hello! Let me know if you have any questions.", "Hey! What's on your mind?"]); 
        }}
        else {{
            useAPI = true;
        }}

        if (useAPI) {{
            if (!API_KEY || API_KEY === "") {{
                reply = "That's a great question! My external medical API is currently disconnected, but I can still tell you all about our <b>NSTI Howrah Team</b>, our <b>Mentor Sayanti Manna</b>, or our <b>DenseNet121 model</b>!";
            }} else {{
                try {{
                    const response = await fetch('https://api.groq.com/openai/v1/chat/completions', {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${{API_KEY}}`
                        }},
                        body: JSON.stringify({{
                            model: 'llama-3.1-8b-instant', 
                            messages: [
                                {{role: 'system', content: 'You are the PneumoniaLens AI Assistant. You help explain general medical terms, pneumonia symptoms, and AI concepts to users. Keep answers professional, friendly, and strictly under 3 sentences. Do NOT give fatal medical diagnoses.'}},
                                {{role: 'user', content: text}}
                            ]
                        }})
                    }});
                    
                    const data = await response.json();
                    if (data.choices && data.choices[0].message) {{
                        reply = data.choices[0].message.content;
                    }} else {{
                        reply = "I'm having trouble connecting to my cloud brain right now. Please ask me about the team instead!";
                    }}
                }} catch (error) {{
                    reply = "I encountered a network error connecting to the API. Please try again later.";
                }}
            }}
        }}

        typingInd.style.display = 'none';
        const botTime = getTime();
        msgBox.innerHTML += `
            <div class="msg-row bot-row">
                <div class="avatar">${{botIcon}}</div>
                <div class="msg-content">
                    <div class="msg-bubble bot-msg">${{reply}}</div>
                    <div class="msg-time bot-time">${{botTime}}</div>
                </div>
            </div>
        `;
        msgBox.scrollTop = msgBox.scrollHeight;

        inputField.disabled = false;
        sendBtn.disabled = false;
        inputField.focus();
    }};
}})();
</script>
"""

components.html(raw_chat_code, height=0, width=0)
