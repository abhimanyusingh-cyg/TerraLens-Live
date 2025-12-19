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

# --- 🎨 FINAL MOBILE-OPTIMIZED CSS ---
st.markdown("""
<style>
    /* Main Background */
    .stApp { background-color: #f8fafc; }

    /* SOLID METRIC CARDS (Total Items, Points) */
    [data-testid="stMetric"] {
        background-color: #ffffff !important; 
        border: 2px solid #e2e8f0 !important;
        border-radius: 15px !important;
        padding: 20px !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05) !important;
        opacity: 1 !important;
    }
    [data-testid="stMetricLabel"] { color: #64748b !important; font-weight: bold !important; opacity: 1 !important; }
    [data-testid="stMetricValue"] { color: #064e3b !important; font-weight: 800 !important; opacity: 1 !important; }

    /* SOLID HISTORY & BADGE CARDS */
    .history-card, .badge-card {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 15px !important;
        margin-bottom: 12px !important;
        opacity: 1 !important;
        color: #1e293b !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05) !important;
    }
    .history-card { border-left: 6px solid #10b981 !important; }

    /* BUTTONS */
    div.stButton > button {
        background: linear-gradient(90deg, #059669 0%, #10b981 100%);
        color: white !important;
        border-radius: 25px !important;
        border: none !important;
        padding: 10px 25px !important;
        font-weight: 600 !important;
        width: 100%;
    }

    /* TABLE & DATAFRAME FIX */
    [data-testid="stTable"], [data-testid="stDataFrame"] {
        background-color: #ffffff !important;
        border-radius: 12px !important;
        padding: 10px !important;
        opacity: 1 !important;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIC FUNCTIONS (ALL INTEGRATED) ---
def get_rank(points):
    if points < 50: return "Green Rookie 🌱", "#94a3b8"
    if points < 200: return "Waste Warrior ⚔️", "#10b981"
    return "Eco Legend 👑", "#f59e0b"

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

def check_if_recyclable(label):
    label = label.lower()
    mapping = {
        'plastic': ['bottle', 'plastic', 'lotion', 'sunscreen', 'cup', 'whistle', 'candle'],
        'paper': ['carton', 'paper', 'envelope', 'tissue', 'towel', 'diaper', 'packet'],
        'metal': ['can', 'beer_glass', 'corkscrew'],
        'glass': ['goblet', 'wine_bottle', 'beaker']
    }
    for category, keywords in mapping.items():
        if any(key in label for key in keywords): return True, category.upper()
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

# --- DATA ACTIONS ---
def save_scan_data(username, item_type, lat, lon):
    db.collection('users').document(username).update({
        "points": firestore.Increment(10),
        "last_scan_timestamp": datetime.now().timestamp()
    })
    db.collection('scans').add({
        "user": username, "item": item_type, "lat": lat, "lon": lon,
        "timestamp": firestore.SERVER_TIMESTAMP, 
        "time_str": datetime.now().strftime("%H:%M"),
        "date_str": datetime.now().strftime("%d %b")
    })

# --- UI LOGIC ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🌱 TerraLens Pro")
    c1, c2 = st.columns([1,1.5])
    with c1:
        st.subheader("Join the Movement")
        choice = st.radio("Access", ["Login", "Sign Up"], horizontal=True)
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.button("Go"):
            if choice == "Login":
                doc = db.collection('users').document(u).get()
                if doc.exists and check_hashes(p, doc.to_dict()['password']):
                    st.session_state['logged_in'], st.session_state['username'] = True, u
                    st.rerun()
                else: st.error("Wrong details")
            else:
                if db.collection('users').document(u).get().exists: st.error("Exists")
                else: 
                    db.collection('users').document(u).set({"name": u, "password": make_hashes(p), "points": 0})
                    st.success("Account Created!")
    with c2: st.image("https://images.unsplash.com/photo-1542601906990-b4d3fb778b09", caption="AI Powered Earth Care")

else:
    # --- DASHBOARD ---
    u_info = db.collection('users').document(st.session_state['username']).get().to_dict()
    pts = u_info.get('points', 0)
    rank, r_col = get_rank(pts)

    with st.sidebar:
        st.markdown(f"## 👤 {st.session_state['username']}")
        st.markdown(f"<div class='badge-card' style='background:{r_col}22; border-color:{r_col}; color:{r_col};'> {rank} </div>", unsafe_allow_html=True)
        st.metric("Total Balance", f"{pts} 🪙")
        
        if pts >= 100:
            if st.button("🎓 View Certificate"):
                st.balloons()
                st.markdown(f"""
                <div style="border:5px solid {r_col}; padding:20px; text-align:center; background:white; color:black;">
                    <h3>Earth Guardian Award</h3>
                    <p>Presented to</p>
                    <h2 style="color:#059669;">{st.session_state['username'].upper()}</h2>
                    <p>For achieving the rank of <b>{rank}</b></p>
                </div>""", unsafe_allow_html=True)
        
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    t1, t2, t3, t4 = st.tabs(["📸 Scanner", "📊 Impact Dashboard", "📜 History", "🏆 Leaderboard"])

    with t1:
        st.subheader("♻️ New Scan")
        loc = get_geolocation()
        if loc and 'coords' in loc:
            lat, lon = loc['coords']['latitude'], loc['coords']['longitude']
            st.success("📍 GPS Locked")
            img = st.camera_input("Snapshot")
            if img:
                if st.button("Verify & Claim Points"):
                    can, sec = check_cooldown(st.session_state['username'])
                    if not can: st.error(f"Wait {sec}s (Anti-Cheat Active)")
                    else:
                        with st.spinner("Analyzing..."):
                            label = tf.keras.applications.mobilenet_v2.decode_predictions(model.predict(np.expand_dims(tf.keras.applications.mobilenet_v2.preprocess_input(np.array(ImageOps.fit(Image.open(img), (224,224)))),0)), top=1)[0][0][1]
                            ok, cat = check_if_recyclable(label)
                            if ok:
                                save_scan_data(st.session_state['username'], cat, lat, lon)
                                st.success(f"Verified {cat}! +10 Points")
                            else: st.error(f"Not Recyclable: {label}")
        else: st.warning("Please enable GPS to scan.")

    with t2:
        st.subheader("🌏 Real-time Impact Analytics")
        df = pd.DataFrame([d.to_dict() for d in db.collection('scans').stream()])
        if not df.empty:
            m1, m2 = st.columns(2)
            m1.metric("Total Items", len(df))
            m2.metric("Community Points", len(df)*10)
            st.map(df[['lat', 'lon']])
            st.bar_chart(df['item'].value_counts())

    with t3:
        st.subheader("Your Scan Timeline")
        docs = db.collection('scans').where('user','==',st.session_state['username']).limit(20).stream()
        hist = [d.to_dict() for d in docs]
        hist.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
        
        for h in hist:
            st.markdown(f"<div class='history-card'><b>{h['item']}</b> Waste <br><small>📅 {h.get('date_str','Today')} at {h.get('time_str','--')}</small></div>", unsafe_allow_html=True)

    with t4:
        st.subheader("Global Ranks")
        leaders = pd.DataFrame([{"Name": d.to_dict()['name'], "Points": d.to_dict()['points']} for d in db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(10).stream()])
        st.table(leaders)
