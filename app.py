import streamlit as st
from ultralytics import YOLO
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- PREMIUM PAGE CONFIG ---
st.set_page_config(page_title="TerraLens Pro | Startup Edition", page_icon="🧪", layout="wide")

# --- HIGH-END CUSTOM CSS ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background: radial-gradient(circle, #1a1a1a 0%, #0d0d0d 100%);
        color: #e0e0e0;
    }
    /* Hide Streamlit Header/Footer */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    
    /* Modern Startup Card */
    .premium-card {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border-radius: 20px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        margin-bottom: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
    }
    /* Action Button */
    .stButton>button {
        background: linear-gradient(45deg, #00c853, #b2ff59);
        color: black !important;
        font-weight: 800 !important;
        border-radius: 50px !important;
        border: none !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    /* Metric styling */
    [data-testid="stMetricValue"] { color: #00c853 !important; font-size: 2rem; }
    </style>
    """, unsafe_allow_html=True)

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    try:
        firebase_info = json.loads(st.secrets["firebase"]["service_account"])
        cred = credentials.Certificate(firebase_info)
        firebase_admin.initialize_app(cred)
    except: pass
db = firestore.client()

@st.cache_resource
def load_model(): return YOLO("best.pt")
model = load_model()

# --- APP LAYOUT ---
col1, col2 = st.columns([1, 2])

with col1:
    st.image("https://cdn-icons-png.flaticon.com/512/3299/3299935.png", width=80)
    st.title("TerraLens AI")
    st.write("Next-Gen Waste Intelligence")
    
    # Leaderboard in a Card
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    st.subheader("🏆 Global Ranking")
    # ... (Leaderboard logic remains same)
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="premium-card">', unsafe_allow_html=True)
    img_file = st.camera_input("INITIALIZE AI SCANNER")
    st.markdown('</div>', unsafe_allow_html=True)

    if img_file:
        img = Image.open(img_file)
        results = model.predict(img, conf=0.65) # Higher threshold for better accuracy
        
        if len(results[0].boxes) > 0:
            res_plotted = results[0].plot()
            st.image(res_plotted, use_container_width=True)
            
            label = model.names[int(results[0].boxes.cls[0])].upper()
            
            # Smart Check for Accuracy (Stopping cloth-paper confusion)
            if label == "PAPER" and results[0].boxes.conf[0] < 0.75:
                label = "UNIDENTIFIED TEXTILE/WASTE"
                color = "#ff9800"
            else:
                color = "#00c853"
            
            st.markdown(f"""
                <div style="text-align: center; padding: 20px; border-radius: 15px; background: rgba(0,200,83,0.1); border: 1px solid {color};">
                    <h2 style="color:{color}; margin:0;">{label}</h2>
                    <p style="margin:0;">Neural Confidence: {results[0].boxes.conf[0]:.2%}</p>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button("CLAIM ECO-REWARDS"):
                st.balloons()
        else:
            st.error("AI Analysis: No specific waste category matched. Please reposition the item.")
