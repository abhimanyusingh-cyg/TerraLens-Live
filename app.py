import streamlit as st
from ultralytics import YOLO
from PIL import Image
import firebase_admin
from firebase_admin import credentials, firestore
import json

# --- 1. CONFIG & PWA ---
st.set_page_config(
    page_title="TerraLens Pro", 
    page_icon="♻️", 
    layout="wide",
    initial_sidebar_state="expanded" # Isse sidebar hamesha dikhega
)
st.markdown('<link rel="manifest" href="/manifest.json">', unsafe_allow_html=True)

# --- 2. PREMIUM CSS ---
st.markdown("""
    <style>
    .stApp { background: #0E1117; color: white; }
    header {visibility: hidden;}
    
    .reward-box {
        background: linear-gradient(135deg, #00FFA3 0%, #00A3FF 100%);
        color: black; padding: 20px; border-radius: 20px;
        text-align: center; font-weight: bold; margin-bottom: 20px;
    }
    
    /* Certificate Style */
    .cert-style {
        border: 5px solid #00FFA3;
        padding: 20px;
        text-align: center;
        background: white;
        color: black;
        border-radius: 10px;
        font-family: 'serif';
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FIREBASE SETUP ---
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

# --- 4. SIDEBAR PORTAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3299/3299935.png", width=80)
    st.title("TerraLens Portal")
    
    user_email = st.text_input("📧 User Login", placeholder="email@example.com")
    
    points = 0
    if user_email:
        user_ref = db.collection("users").document(user_email)
        user_doc = user_ref.get()
        user_data = user_doc.to_dict() if user_doc.exists else {"points": 0}
        points = user_data.get("points", 0)
        
        st.markdown(f"""<div class="reward-box"><p style="margin:0;">ECO-SCORE</p><h1 style="margin:0;">{points}</h1></div>""", unsafe_allow_html=True)
        
        if points >= 100:
            st.success("🎖️ LEVEL: GREEN WARRIOR")
            if st.button("📜 View Certificate"):
                st.markdown(f"""
                <div class="cert-style">
                    <h1>CERTIFICATE</h1>
                    <p>This is to certify that</p>
                    <h3>{user_email}</h3>
                    <p>has achieved the rank of <b>Green Warrior</b></p>
                    <p>for contributing to a Sustainable Future.</p>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.progress(min(points/100, 1.0), text=f"{(100-points if points < 100 else 0)} pts to Certificate")

    st.divider()
    st.subheader("🏆 Global Ranks")
    try:
        top_users = db.collection("users").order_by("points", direction=firestore.Query.DESCENDING).limit(5).stream()
        for u in top_users:
            st.write(f"🥇 {u.id[:10]}... : `{u.to_dict().get('points')} pts` ")
    except: st.write("Syncing...")

# --- 5. MAIN SCANNER ---
st.markdown("<h1 style='text-align: center; color: #00FFA3;'>TERRALENS SCANNER</h1>", unsafe_allow_html=True)

col_cam, col_res = st.columns([1.5, 1])

with col_cam:
    img_file = st.camera_input("SCANNER", label_visibility="hidden")

with col_res:
    st.markdown("### 🔍 Analysis Report")
    if img_file:
        img = Image.open(img_file)
        results = model.predict(img, conf=0.7)
        
        if len(results[0].boxes) > 0:
            st.image(results[0].plot(), use_container_width=True)
            label = model.names[int(results[0].boxes.cls[0])].upper()
            conf = results[0].boxes.conf[0]
            
            is_valid = not (label == "PAPER" and conf < 0.82)
            
            if is_valid:
                st.success(f"Verified: {label}")
                if user_email and st.button("CLAIM +10 CREDITS"):
                    db.collection("users").document(user_email).set({"points": points + 10}, merge=True)
                    st.balloons()
                    st.rerun()
            else:
                st.warning("⚠️ High Risk: Item looks like Textile/Cloth. Verification failed.")
        else:
            st.error("Neural analysis failed. Reposition item.")
    else:
        st.info("Scanner Ready. Analyzing real-time environmental impact...")
