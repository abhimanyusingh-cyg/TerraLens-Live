import streamlit as st
from ultralytics import YOLO
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- CONFIG ---
st.set_page_config(page_title="TerraLens AI", page_icon="♻️", layout="wide")
st.markdown('<link rel="manifest" href="/manifest.json">', unsafe_allow_html=True)

# --- CLEAN PREMIUM CSS ---
st.markdown("""
    <style>
    .stApp { background: #0E1117; color: white; }
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Global Card Style */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 20px;
        margin-bottom: 20px;
    }
    
    .hero-title {
        background: linear-gradient(90deg, #00FFA3, #00A3FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3rem; font-weight: 900; text-align: center;
        margin-bottom: 30px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FIREBASE (Using your working logic) ---
if not firebase_admin._apps:
    try:
        firebase_info = json.loads(st.secrets["firebase"]["service_account"])
        cred = credentials.Certificate(firebase_info)
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client()

@st.cache_resource
def load_engine(): return YOLO("best.pt")
model = load_engine()

# --- UI LAYOUT ---
st.markdown('<h1 class="hero-title">TERRALENS AI</h1>', unsafe_allow_html=True)

# Grid System
col_side, col_main = st.columns([1, 2.5], gap="medium")

with col_side:
    st.markdown("### 👤 Account")
    user_id = st.text_input("Enter ID", placeholder="User Email", label_visibility="collapsed")
    
    st.markdown("### 🏆 Leaders")
    # Leaderboard without expander for direct view
    try:
        users = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(5).stream()
        for u in users:
            d = u.to_dict()
            st.markdown(f"**{u.id}** : `{d.get('points', 0)} pts` ")
    except: st.write("Syncing...")

with col_main:
    img_input = st.camera_input("SCANNER", label_visibility="hidden")
    
    if img_input:
        img = Image.open(img_input)
        results = model.predict(img, conf=0.7)
        
        if len(results[0].boxes) > 0:
            st.image(results[0].plot(), use_container_width=True)
            label = model.names[int(results[0].boxes.cls[0])].upper()
            conf = results[0].boxes.conf[0]
            
            # Accuracy Logic
            is_valid = not (label == "PAPER" and conf < 0.82)
            display_label = label if is_valid else "UNVERIFIED MATERIAL"
            color = "#00FFA3" if is_valid else "#FF4B4B"
            
            st.markdown(f"""
                <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; border-left: 5px solid {color}; text-align: center;">
                    <h2 style="color:{color};">{display_label}</h2>
                    <p>Neural Confidence: {conf:.1%}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if is_valid and user_id:
                if st.button("CLAIM +10 CREDITS"):
                    # Points logic...
                    st.balloons()
        else:
            st.error("Neural analysis failed. Reposition the object.")
