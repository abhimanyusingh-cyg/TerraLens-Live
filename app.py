import streamlit as st
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import firebase_admin
from firebase_admin import firestore, credentials
import os
import json
import hashlib
import pandas as pd
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="TerraLens Enterprise", page_icon="🌱", layout="wide")

# --- 2. PREMIUM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    [data-testid="stMetric"], .history-card, .badge-card, .leaderboard-card {
        background-color: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-radius: 12px !important;
        padding: 1.2rem !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        opacity: 1 !important;
    }
    .cert-container {
        border: 10px double #059669; padding: 40px; background-color: white;
        text-align: center; font-family: 'Georgia', serif; color: #1e293b;
    }
    div.stButton > button {
        background: linear-gradient(90deg, #059669 0%, #10b981 100%);
        color: white !important; border-radius: 25px !important; font-weight: bold !important; height: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. CORE LOGIC & FUNCTIONS (IMPORTANT: DO NOT SKIP) ---
def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def check_hashes(p, h): return make_hashes(p) == h

def get_rank(points):
    if points < 50: return "Green Rookie 🌱", "#94a3b8"
    if points < 200: return "Waste Warrior ⚔️", "#10b981"
    return "Eco Legend 👑", "#f59e0b"

def check_if_recyclable(label):
    mapping = {
        'plastic': ['bottle', 'plastic', 'lotion', 'cup', 'candle', 'lighter', 'container'],
        'paper': ['carton', 'paper', 'envelope', 'tissue', 'diaper', 'packet', 'box'],
        'metal': ['can', 'beer_glass', 'corkscrew', 'tin'],
        'glass': ['goblet', 'wine_bottle', 'beaker']
    }
    label = label.lower()
    for cat, keys in mapping.items():
        if any(k in label for k in keys): return True, cat.upper()
    return False, label

def check_cooldown(username):
    doc = db.collection('users').document(username).get()
    if doc.exists:
        last_scan = doc.to_dict().get('last_scan_timestamp')
        if last_scan:
            diff = datetime.now().timestamp() - last_scan
            if diff < 60: return False, int(60 - diff)
    return True, 0

# --- THE MISSING FUNCTION FIXED ---
def save_scan_data(username, item_type, lat, lon):
    # 1. Update user points and timestamp
    db.collection('users').document(username).update({
        "points": firestore.Increment(10),
        "last_scan_timestamp": datetime.now().timestamp()
    })
    # 2. Log the scan activity
    db.collection('scans').add({
        "user": username,
        "item": item_type,
        "lat": lat,
        "lon": lon,
        "timestamp": firestore.SERVER_TIMESTAMP,
        "time_str": datetime.now().strftime("%H:%M"),
        "date_str": datetime.now().strftime("%d %b")
    })

# --- 4. FIREBASE SETUP ---
if not firebase_admin._apps:
    try:
        key_dict = json.loads(st.secrets["textkey"])
        if "private_key" in key_dict: key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except:
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if project_id: firebase_admin.initialize_app(options={'projectId': project_id})

db = firestore.client()
model = tf.keras.applications.MobileNetV2(weights='imagenet')

# --- 5. APP UI ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    col1, col2 = st.columns([1, 1.2])
    with col1:
        st.title("🌱 TerraLens Pro")
        mode = st.radio("Access", ["Login", "Sign Up"], horizontal=True)
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Access Dashboard"):
            if mode == "Login":
                doc = db.collection('users').document(u).get()
                if doc.exists and check_hashes(p, doc.to_dict()['password']):
                    st.session_state['logged_in'], st.session_state['username'] = True, u
                    st.rerun()
                else: st.error("Invalid Credentials")
            else:
                if not db.collection('users').document(u).get().exists:
                    db.collection('users').document(u).set({"name": u, "password": make_hashes(p), "points": 0})
                    st.success("Account Created! Please Login.")
                else: st.error("User exists")
    with col2:
        st.image("https://images.unsplash.com/photo-1542601906990-b4d3fb778b09", caption="Sustainability Dashboard")

else:
    # --- LOGGED IN USER DATA ---
    u_info = db.collection('users').document(st.session_state['username']).get().to_dict()
    pts = u_info.get('points', 0)
    rank, r_col = get_rank(pts)

    with st.sidebar:
        st.markdown(f"## 👤 {st.session_state['username']}")
        st.markdown(f"<div class='badge-card' style='border-color:{r_col}; background:{r_col}11;'>Rank: <b>{rank}</b></div>", unsafe_allow_html=True)
        st.metric("Balance", f"{pts} 🪙")
        
        if pts >= 100:
            if st.button("🎓 View Certificate"):
                st.balloons()
                cert_html = f"""<div class="cert-container"><h1>Award of Excellence</h1><p>Presented to</p><h2>{st.session_state['username'].upper()}</h2><p>Rank: {rank}</p></div>"""
                st.markdown(cert_html, unsafe_allow_html=True)
        
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📸 Scan", "📊 Stats", "🎁 Rewards", "📜 History", "🏆 Leaderboard"])

    with tab1:
        st.subheader("♻️ Verify Waste")
        loc = get_geolocation()
        if loc and 'coords' in loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.success("📍 GPS Locked")
            img = st.camera_input("Snapshot")
            if img:
                if st.button("🔍 Verify & Claim 10 Points"):
                    can, sec = check_cooldown(st.session_state['username'])
                    if not can: st.error(f"Wait {sec}s (Anti-Cheat)")
                    else:
                        with st.spinner("Analyzing..."):
                            # AI Logic
                            pil_img = Image.open(img)
                            img_resized = ImageOps.fit(pil_img, (224, 224), Image.Resampling.LANCZOS)
                            img_array = tf.keras.applications.mobilenet_v2.preprocess_input(np.array(img_resized))
                            preds = model.predict(np.expand_dims(img_array, axis=0))
                            decoded = tf.keras.applications.mobilenet_v2.decode_predictions(preds, top=3)[0]
                            
                            found = False
                            for _, label, prob in decoded:
                                ok, cat = check_if_recyclable(label)
                                if ok:
                                    save_scan_data(st.session_state['username'], cat, lat, lon)
                                    st.balloons()
                                    st.success(f"✅ Verified as {cat}! (+10 🪙)")
                                    found = True
                                    break
                            if not found:
                                st.error(f"❌ Not Recyclable. AI saw: {decoded[0][1]}")

    with tab2:
        st.subheader("ESG Analytics")
        docs_all = db.collection('scans').stream()
        df = pd.DataFrame([d.to_dict() for d in docs_all])
        if not df.empty:
            st.map(df[['lat', 'lon']])
            st.divider()
            st.download_button("📥 Download ESG Report (CSV)", df.to_csv(index=False).encode('utf-8'), "TerraLens_Report.csv", "text/csv")
        else: st.info("No data available yet.")

    with tab3:
        st.subheader("🎁 Rewards Store")
        c1, c2 = st.columns(2)
        with c1: st.info("☕ **Free Coffee** \n\n 200 🪙 Required")
        with c2: st.info("🌲 **Plant a Tree** \n\n 500 🪙 Required")

    with tab4:
        st.subheader("Recent Activity")
        docs = db.collection('scans').where('user','==',st.session_state['username']).limit(10).stream()
        hist = [d.to_dict() for d in docs]
        hist.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        for h in hist:
            st.markdown(f"<div class='history-card'><b>{h['item']}</b> Waste <br><small>{h.get('date_str','Today')}</small></div>", unsafe_allow_html=True)

    with tab5:
        st.subheader("Global Leaderboard")
        leaders = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(5).stream()
        for i, l in enumerate(leaders):
            ld = l.to_dict()
            st.markdown(f"<div class='leaderboard-card'>{i+1}. {ld['name']} - {ld['points']} pts</div>", unsafe_allow_html=True)
