import streamlit as st
from ultralytics import YOLO
from PIL import Image
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore
import json
import time

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraLens Pro V2", page_icon="♻️", layout="centered")

# --- MODERN UI CSS ---
st.markdown("""
    <style>
    .main { background-color: #f8fbf8; }
    .stButton>button {
        width: 100%;
        border-radius: 12px;
        height: 3em;
        background-color: #2E7D32;
        color: white;
        font-weight: bold;
        border: none;
        transition: 0.3s;
    }
    .stButton>button:hover { background-color: #1B5E20; border: none; }
    .status-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        border-left: 5px solid #2E7D32;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    try:
        firebase_info = json.loads(st.secrets["firebase"]["service_account"])
        cred = credentials.Certificate(firebase_info)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase Setup Error: {e}")
        st.stop()

db = firestore.client()

# --- LOAD MODEL ---
@st.cache_resource
def load_model():
    return YOLO("best.pt")

model = load_model()

# --- APP HEADER ---
st.title("♻️ TerraLens Pro")
st.markdown("### AI-Powered Waste Classifier")

# --- SIDEBAR (Login/Leaderboard) ---
with st.sidebar:
    st.header("👤 User Profile")
    user_email = st.text_input("Login with Email")
    if user_email:
        st.success(f"Logged in as: {user_email}")
        
    st.divider()
    st.header("🏆 Leaderboard")
    users_ref = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(5)
    for doc in users_ref.stream():
        data = doc.to_dict()
        st.write(f"**{doc.id}**: {data.get('points', 0)} pts")

# --- MAIN CAPTURE ---
img_file = st.camera_input("Scan Waste Item")

if img_file:
    img = Image.open(img_file)
    # Model Prediction with Higher Confidence
    results = model.predict(img, conf=0.6) 
    
    # Result Processing
    if len(results[0].boxes) > 0:
        for result in results:
            # Show original image with boxes
            res_plotted = result.plot()
            st.image(res_plotted, caption="AI Detection Result", use_container_width=True)
            
            # Identify Top Label
            label_idx = int(result.boxes.cls[0])
            label_name = model.names[label_idx]
            prob = result.boxes.conf[0]
            
            # Modern UI Card for Result
            st.markdown(f"""
                <div class="status-card">
                    <h4>Detected: <span style="color:#2E7D32;">{label_name.upper()}</span></h4>
                    <p>Confidence: {prob:.2%}</p>
                </div>
                """, unsafe_allow_html=True)
            
            # Extra Feature: Eco-Insight
            insights = {
                "plastic": "Fact: Plastic takes 450+ years to decompose. Recycle it!",
                "paper": "Fact: Recycling 1 ton of paper saves 17 trees.",
                "metal": "Fact: Aluminum can be recycled infinitely without losing quality.",
                "glass": "Fact: Glass is 100% recyclable and can be reused forever."
            }
            st.info(insights.get(label_name.lower(), "Good job! Dispose of this responsibly."))

            # Update Points
            if user_email and st.button("Claim 10 Eco-Points"):
                user_ref = db.collection("users").document(user_email)
                user_doc = user_ref.get()
                current_points = user_doc.to_dict().get("points", 0) if user_doc.exists else 0
                user_ref.set({"points": current_points + 10}, merge=True)
                st.balloons()
                st.success("Points Added to your Profile!")
    else:
        st.warning("⚠️ Waste not identified clearly. Please try again with better light or different angle.")
