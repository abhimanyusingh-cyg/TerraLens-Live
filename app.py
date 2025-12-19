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

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraLens Pro", page_icon="🌱", layout="wide")

# --- 📱 MOBILE-OPTIMIZED SOLID CSS (NO TRANSPARENCY) ---
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6 !important; }
    
    /* Solid Cards for Metrics, History, & Badges */
    [data-testid="stMetric"], .history-card, .badge-card, .leaderboard-card {
        background-color: #ffffff !important;
        border: 1px solid #d1d5db !important;
        border-radius: 12px !important;
        padding: 1.2rem !important;
        margin-bottom: 1rem !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08) !important;
        opacity: 1 !important;
    }

    [data-testid="stMetricValue"] { color: #064e3b !important; font-weight: 800 !important; font-size: 1.8rem !important; }
    [data-testid="stMetricLabel"] { color: #4b5563 !important; font-weight: bold !important; }

    .history-card { border-left: 8px solid #059669 !important; color: #111827 !important; }
    
    div.stButton > button {
        background: #059669 !important;
        color: white !important;
        border-radius: 10px !important;
        font-weight: bold !important;
        width: 100%;
        height: 3rem;
    }
</style>
""", unsafe_allow_html=True)

# --- CORE LOGIC (INTEGRATED FEATURES) ---
def make_hashes(p): return hashlib.sha256(str.encode(p)).hexdigest()
def check_hashes(p, h): return make_hashes(p) == h

def get_rank(points):
    if points < 50: return "Green Rookie 🌱", "#94a3b8"
    if points < 200: return "Waste Warrior ⚔️", "#10b981"
    return "Eco Legend 👑", "#f59e0b"

def check_if_recyclable(label):
    mapping = {
        'plastic': ['bottle', 'plastic', 'lotion', 'cup', 'candle', 'lighter'],
        'paper': ['carton', 'paper', 'envelope', 'tissue', 'diaper', 'packet'],
        'metal': ['can', 'beer_glass', 'corkscrew'],
        'glass': ['goblet', 'wine_bottle']
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

# --- FIREBASE SETUP ---
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

# --- AUTH & UI ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
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
                st.success("Account Created!")
            else: st.error("User already exists")

else:
    # --- DASHBOARD LOGIC ---
    u_data = db.collection('users').document(st.session_state['username']).get().to_dict()
    pts = u_data.get('points', 0)
    rank, r_col = get_rank(pts)

    with st.sidebar:
        st.markdown(f"## 👤 {st.session_state['username']}")
        st.markdown(f"<div class='badge-card' style='border-color:{r_col}; background:{r_col}11;'>Rank: <b>{rank}</b></div>", unsafe_allow_html=True)
        st.metric("My Balance", f"{pts} 🪙")
        
        if pts >= 100:
            if st.button("🎓 View Certificate"):
                st.balloons()
                st.markdown(f"<div style='border:5px solid {r_col}; padding:15px; background:white; color:black; text-align:center;'><h3>Eco-Hero Award</h3><p>To: {st.session_state['username'].upper()}</p></div>", unsafe_allow_html=True)
        
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    tab1, tab2, tab3, tab4 = st.tabs(["📸 Scan", "📊 Stats", "📜 History", "🏆 Ranks"])

    with tab1:
        loc = get_geolocation()
        if loc and 'coords' in loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.success("📍 GPS Locked")
            img = st.camera_input("Scan Item")
            if img and st.button("Verify & Claim"):
                can, sec = check_cooldown(st.session_state['username'])
                if not can: st.error(f"Anti-Cheat: Wait {sec}s")
                else:
                    with st.spinner("AI Analysis..."):
                        label = tf.keras.applications.mobilenet_v2.decode_predictions(model.predict(np.expand_dims(tf.keras.applications.mobilenet_v2.preprocess_input(np.array(ImageOps.fit(Image.open(img), (224,224)))),0)), top=1)[0][0][1]
                        ok, cat = check_if_recyclable(label)
                        if ok:
                            db.collection('users').document(st.session_state['username']).update({
                                "points": firestore.Increment(10), "last_scan_timestamp": datetime.now().timestamp()
                            })
                            db.collection('scans').add({
                                "user": st.session_state['username'], "item": cat, "lat": lat, "lon": lon,
                                "timestamp": firestore.SERVER_TIMESTAMP, "date_str": datetime.now().strftime("%d %b, %H:%M")
                            })
                            st.success(f"Verified {cat}! +10 Pts")
                        else: st.error(f"Not Recyclable: {label}")
        else: st.warning("Enable GPS to scan")

    with tab2:
        st.subheader("Global Impact")
        all_scans = pd.DataFrame([d.to_dict() for d in db.collection('scans').stream()])
        if not all_scans.empty:
            c1, c2 = st.columns(2)
            c1.metric("Total Items", len(all_scans))
            c2.metric("CO2 Saved (Est.)", f"{len(all_scans)*0.5} kg")
            st.map(all_scans[['lat', 'lon']])
            st.bar_chart(all_scans['item'].value_counts())

    with tab3:
        st.subheader("Recent Activity")
        docs = db.collection('scans').where('user','==',st.session_state['username']).limit(20).stream()
        hist = [d.to_dict() for d in docs]
        hist.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        for h in hist:
            st.markdown(f"<div class='history-card'><b>{h['item']}</b><br><small>{h.get('date_str','Today')}</small></div>", unsafe_allow_html=True)

    with tab4:
        st.subheader("Top Warriors")
        leaders = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(10).stream()
        for i, l in enumerate(leaders):
            ld = l.to_dict()
            st.markdown(f"<div class='leaderboard-card'>{i+1}. {ld['name']} — {ld['points']} pts</div>", unsafe_allow_html=True)
