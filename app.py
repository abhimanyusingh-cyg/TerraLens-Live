import streamlit as st
from ultralytics import YOLO
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- 1. PREMIUM PAGE CONFIG & PWA LINK ---
st.set_page_config(
    page_title="TerraLens AI | Smart Waste Intelligence", 
    page_icon="🧪", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# PWA Manifest Connection
st.markdown('<link rel="manifest" href="/manifest.json">', unsafe_allow_html=True)

# --- 2. STARTUP GRADE CUSTOM CSS (DARK MODE) ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700;900&display=swap');
    
    /* Main Background */
    .stApp {
        background: radial-gradient(circle at top right, #1a1a1a, #050505);
        color: #FFFFFF;
        font-family: 'Inter', sans-serif;
    }
    
    /* Hide Default Headers */
    header {visibility: hidden;}
    footer {visibility: hidden;}

    /* Glassmorphism Containers */
    div[data-testid="stVerticalBlock"] > div:has(div.stMarkdown) {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(15px);
        border-radius: 28px;
        padding: 30px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 25px;
        box-shadow: 0 20px 40px rgba(0,0,0,0.4);
    }

    /* Main Gradient Title */
    .hero-title {
        background: linear-gradient(90deg, #00FFA3 0%, #03E5B7 50%, #00A3FF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-size: 3.5rem;
        font-weight: 900;
        text-align: center;
        letter-spacing: -2px;
        margin-bottom: 0px;
    }

    /* Neon Buttons */
    .stButton>button {
        background: linear-gradient(90deg, #00FFA3 0%, #03E5B7 100%) !important;
        color: #0E1117 !important;
        border: none !important;
        border-radius: 16px !important;
        font-weight: 800 !important;
        height: 3.8rem !important;
        text-transform: uppercase;
        letter-spacing: 1.2px;
        transition: 0.4s all ease !important;
    }
    
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 30px rgba(0, 255, 163, 0.4);
    }

    /* Input Fields */
    .stTextInput>div>div>input {
        background-color: rgba(255,255,255,0.05) !important;
        color: white !important;
        border-radius: 12px !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FIREBASE CORE (Secrets Mode) ---
if not firebase_admin._apps:
    try:
        secret_content = st.secrets["firebase"]["service_account"]
        firebase_info = json.loads(secret_content)
        cred = credentials.Certificate(firebase_info)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Systems Offline: {e}")
        st.stop()

db = firestore.client()

# --- 4. NEURAL ENGINE LOAD ---
@st.cache_resource
def load_engine():
    return YOLO("best.pt")

engine = load_engine()

# --- 5. APP LAYOUT ---
st.markdown('<h1 class="hero-title">TERRALENS AI</h1>', unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #888; font-size: 1.1rem; margin-top: -10px;'>Next-Gen Waste Intelligence Engine</p>", unsafe_allow_html=True)

left_col, right_col = st.columns([1, 1.2], gap="large")

with left_col:
    st.markdown("### 🛠️ System Control")
    user_id = st.text_input("Enter Enterprise/User ID", placeholder="admin@terralens.ai")
    
    with st.expander("📊 Global Eco-Leaderboard", expanded=False):
        try:
            leader_ref = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(5)
            for doc in leader_ref.stream():
                data = doc.to_dict()
                st.write(f"🏆 **{doc.id}** — `{data.get('points', 0)} pts` ")
        except:
            st.info("Leaderboard initializing...")

    st.markdown("---")
    img_input = st.camera_input("INITIALIZE NEURAL SCAN", label_visibility="collapsed")

with right_col:
    st.markdown("### 🔍 Live Analysis")
    if img_input:
        img = Image.open(img_input)
        
        # High-threshold prediction
        results = engine.predict(img, conf=0.7)
        
        if len(results[0].boxes) > 0:
            # Result Visualization
            st.image(results[0].plot(), use_container_width=True)
            
            raw_label = engine.names[int(results[0].boxes.cls[0])].upper()
            confidence = results[0].boxes.conf[0]
            
            # --- ACCURACY FILTER (Cloth vs Paper Logic) ---
            if raw_label == "PAPER" and confidence < 0.82:
                # If AI says paper but surety is low, it's likely Cloth or Mixed waste
                final_label = "UNIDENTIFIED TEXTILE / MIXED"
                status_color = "#FF9800"
                eligible = False
            else:
                final_label = raw_label
                status_color = "#00FFA3"
                eligible = True
            
            # Result Card
            st.markdown(f"""
                <div style="background: rgba(0, 255, 163, 0.05); padding: 25px; border-radius: 20px; border: 1px solid {status_color}; text-align: center;">
                    <h2 style="color: {status_color}; margin-bottom: 5px;">{final_label}</h2>
                    <p style="color: #888; margin: 0;">Neural Confidence: {confidence:.2%}</p>
                </div>
            """, unsafe_allow_html=True)

            # Eco-Reward Logic
            if eligible and user_id:
                if st.button("CLAIM ECO-CREDITS +10"):
                    user_ref = db.collection("users").document(user_id)
                    doc = user_ref.get()
                    pts = doc.to_dict().get("points", 0) if doc.exists else 0
                    user_ref.set({"points": pts + 10}, merge=True)
                    st.balloons()
                    st.toast(f"Credits added to {user_id}", icon="✅")
            elif not eligible:
                st.info("💡 Tip: Try capturing from a different angle for verified credits.")
        else:
            st.error("Neural analysis failed: Category out of bounds. Please reposition item.")
    else:
        st.info("Waiting for optical input... Please scan a waste item.")
