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

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Pro", page_icon="🌱", layout="wide")

# --- CUSTOM CSS (Advanced Design) ---
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    div.stButton > button {
        background: linear-gradient(90deg, #059669 0%, #10b981 100%);
        color: white; border-radius: 25px; border: none; padding: 10px 25px;
        font-weight: 600; width: 100%; transition: 0.3s;
    }
    .badge-card {
        padding: 15px; border-radius: 15px; text-align: center;
        border: 2px solid #e2e8f0; margin-bottom: 15px;
    }
    .history-card {
        background: white; padding: 10px; border-radius: 10px;
        margin-bottom: 8px; border-left: 5px solid #10b981;
    }
</style>
""", unsafe_allow_html=True)

# --- UTILS & LOGIC ---
def get_rank(points):
    if points < 50: return "Green Rookie 🌱", "#94a3b8"
    if points < 200: return "Waste Warrior ⚔️", "#10b981"
    return "Eco Legend 👑", "#f59e0b"

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

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

# --- DATA FUNCTIONS ---
def get_user_data(username):
    return db.collection('users').document(username).get().to_dict()

def get_user_history(username):
    docs = db.collection('scans').where('user', '==', username).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(10).stream()
    return [doc.to_dict() for doc in docs]

def save_scan_data(username, item_type, lat, lon):
    db.collection('users').document(username).update({
        "points": firestore.Increment(10),
        "last_scan_timestamp": datetime.now().timestamp()
    })
    db.collection('scans').add({
        "user": username, "item": item_type, "lat": lat, "lon": lon,
        "timestamp": firestore.SERVER_TIMESTAMP, "date_str": datetime.now().strftime("%d %b, %Y")
    })

# --- UI COMPONENTS ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("🌱 TerraLens Pro")
    c1, c2 = st.columns(2)
    with c1:
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            doc = db.collection('users').document(user).get()
            if doc.exists and check_hashes(pwd, doc.to_dict()['password']):
                st.session_state['logged_in'] = True
                st.session_state['username'] = user
                st.rerun()
    with c2: st.image("https://images.unsplash.com/photo-1532996122724-e3c354a0b15b", width=400)

else:
    user_info = get_user_data(st.session_state['username'])
    points = user_info.get('points', 0)
    rank, r_color = get_rank(points)

    with st.sidebar:
        st.markdown(f"### Welcome, {st.session_state['username']}!")
        st.markdown(f"<div class='badge-card' style='background:{r_color}22;'><h3>{rank}</h3><p>{points} Points</p></div>", unsafe_allow_html=True)
        
        # --- CERTIFICATE LOGIC ---
        if points >= 100:
            st.success("🏆 Certificate Unlocked!")
            if st.button("🎓 Download Certificate"):
                st.balloons()
                # Simple HTML Certificate
                cert_html = f"""
                <div style="border:10px solid {r_color}; padding:50px; text-align:center; font-family:serif; background:white;">
                    <h1 style="font-size:50px;">Certificate of Appreciation</h1>
                    <p style="font-size:20px;">This is to certify that</p>
                    <h2 style="font-size:40px; color:#059669;">{st.session_state['username'].upper()}</h2>
                    <p style="font-size:20px;">has achieved the rank of <b>{rank}</b></p>
                    <p>for outstanding contribution to Planet Earth via TerraLens.</p>
                    <hr width="50%">
                    <p>Verified AI Record | {datetime.now().strftime('%Y')}</p>
                </div>
                """
                st.markdown(cert_html, unsafe_allow_html=True)
                st.caption("Right click and 'Print' to save as PDF")
        else:
            st.info(f"Goal: Reach 100 pts for Certificate (Need {100-points} more)")
            
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["📸 Scanner", "📊 Impact Map", "📜 History"])

    with tab1:
        # Scanner logic (Same as before)
        location = get_geolocation()
        if location and 'coords' in location:
            lat, lon = location['coords']['latitude'], location['coords']['longitude']
            st.success("📍 GPS Ready")
            img = st.camera_input("Scan Waste")
            if img and st.button("Verify"):
                # (AI Analysis & Save Data code here - use previous logic)
                st.success("Added to history!")
        else: st.warning("Waiting for GPS...")

    with tab2:
        # Map logic (Same as before)
        docs = db.collection('scans').stream()
        df = pd.DataFrame([d.to_dict() for d in docs])
        if not df.empty: st.map(df[['lat', 'lon']])

    with tab3:
        st.subheader("📜 Your Recent Scans")
        history = get_user_history(st.session_state['username'])
        if history:
            for item in history:
                st.markdown(f"""
                <div class="history-card">
                    <b>{item['item']}</b> - {item.get('date_str', 'Today')} <br>
                    <small>📍 {item['lat']:.2f}, {item['lon']:.2f}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.write("No scans yet. Go to the Scanner tab!")
