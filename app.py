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
import time
from datetime import datetime
from streamlit_js_eval import get_geolocation

# --- PAGE CONFIGURATION (WIDE MODE) ---
st.set_page_config(page_title="TerraLens Pro", page_icon="🌱", layout="wide", initial_sidebar_state="expanded")

# --- 🎨 CUSTOM CSS (DESIGN MAGIC) ---
st.markdown("""
<style>
    /* 1. Main Background & Text */
    .stApp {
        background-color: #f4f9f4; /* Light Mint Green Background */
        color: #1a1a1a;
    }
    
    /* 2. Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111827; /* Dark Sidebar */
        color: #ffffff;
    }
    [data-testid="stSidebar"] * {
        color: #e5e7eb !important;
    }

    /* 3. Cards for Metrics (Dashboard Look) */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        color: #333;
    }
    
    /* 4. Gradient Buttons */
    div.stButton > button {
        background: linear-gradient(to right, #2E8B57, #3CB371);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 30px;
        font-weight: bold;
        transition: 0.3s;
        width: 100%;
    }
    div.stButton > button:hover {
        transform: scale(1.02);
        box-shadow: 0 5px 15px rgba(46, 139, 87, 0.4);
    }

    /* 5. Headers */
    h1, h2, h3 {
        font-family: 'Helvetica Neue', sans-serif;
        color: #064e3b; /* Dark Green */
    }
    
    /* 6. Tabs Design */
    .stTabs [data-baseweb="tab-list"] {
        gap: 10px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #ffffff;
        border-radius: 20px;
        padding: 10px 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [aria-selected="true"] {
        background-color: #2E8B57 !important;
        color: white !important;
    }

</style>
""", unsafe_allow_html=True)

# --- AI & UTILS (Logic wahi purana hai) ---
def check_if_recyclable(label):
    label = label.lower()
    mapping = {
        'plastic': ['bottle', 'plastic', 'lotion', 'sunscreen', 'cup', 'whistle'],
        'paper': ['carton', 'paper', 'envelope', 'tissue', 'diaper', 'packet'],
        'metal': ['can', 'beer_glass', 'corkscrew'],
        'glass': ['goblet', 'wine_bottle', 'beaker']
    }
    for category, keywords in mapping.items():
        if any(key in label for key in keywords):
            return True, category.upper()
    return False, label

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

def check_cooldown(username):
    doc = db.collection('users').document(username).get()
    if doc.exists:
        data = doc.to_dict()
        last_scan = data.get('last_scan_timestamp')
        if last_scan:
            if hasattr(last_scan, 'timestamp'): last_scan = last_scan.timestamp()
            now = datetime.now().timestamp()
            if (now - last_scan) < 60: return False, int(60 - (now - last_scan))
    return True, 0

# --- FIREBASE ---
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

# --- DB WRAPPERS ---
def create_user(username, password):
    doc = db.collection('users').document(username).get()
    if doc.exists: return False
    db.collection('users').document(username).set({"name": username, "password": make_hashes(password), "points": 0})
    return True

def login_user(username, password):
    doc = db.collection('users').document(username).get()
    if doc.exists and check_hashes(password, doc.to_dict().get("password")):
        return True, doc.to_dict().get("points")
    return False, 0

def save_scan_data(username, item_type, lat, lon):
    db.collection('users').document(username).update({"points": firestore.Increment(10), "last_scan_timestamp": datetime.now().timestamp()})
    db.collection('scans').add({"user": username, "item": item_type, "lat": lat, "lon": lon, "timestamp": firestore.SERVER_TIMESTAMP})

def get_analytics_data():
    docs = db.collection('scans').stream()
    return pd.DataFrame([doc.to_dict() for doc in docs])

def classify_image(image):
    img = ImageOps.fit(image, (224, 224), Image.Resampling.LANCZOS)
    img_array = tf.keras.applications.mobilenet_v2.preprocess_input(np.array(img))
    predictions = model.predict(np.expand_dims(img_array, axis=0))
    return tf.keras.applications.mobilenet_v2.decode_predictions(predictions, top=1)[0][0][1]

# --- UI LOGIC ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# --- 1. LANDING PAGE (Design Upgrade) ---
if not st.session_state['logged_in']:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("<br><br>", unsafe_allow_html=True) # Spacing
        st.title("🌱 TerraLens Pro")
        st.markdown("### The Future of Waste Management")
        st.markdown("Turn your waste into wealth with AI-powered scanning and real-time impact tracking.")
        
        tab_login, tab_signup = st.tabs(["Login", "Create Account"])
        
        with tab_login:
            user = st.text_input("Username", key="l_user")
            pwd = st.text_input("Password", type="password", key="l_pass")
            if st.button("🚀 Access Dashboard"):
                valid, pts = login_user(user, pwd)
                if valid:
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user
                    st.rerun()
                else: st.error("Invalid Credentials")
        
        with tab_signup:
            new_user = st.text_input("Choose Username", key="s_user")
            new_pass = st.text_input("Choose Password", type="password", key="s_pass")
            if st.button("✨ Create Account"):
                if create_user(new_user, new_pass): st.success("Account Created! Login now.")
                else: st.error("Username taken.")

    with col2:
        # Hero Image (High Quality)
        st.image("https://images.unsplash.com/photo-1542601906990-b4d3fb778b09?q=80&w=1000&auto=format&fit=crop", caption="Clean Earth, Green Earth")

# --- 2. DASHBOARD (Logged In) ---
else:
    # Sidebar Profile
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        st.markdown(f"## Hi, {st.session_state['username']}!")
        
        # Balance Card in Sidebar
        st.markdown(
            f"""
            <div style="background-color:#2E8B57; padding:15px; border-radius:10px; text-align:center; color:white;">
                <h3 style="color:white; margin:0;">🪙 Balance</h3>
                <h1 style="color:white; margin:0;">{login_user(st.session_state['username'], 'dummy')[1]}</h1>
            </div>
            """, unsafe_allow_html=True
        )
        st.write("")
        if st.button("🚪 Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    # Main Tabs
    tab1, tab2, tab3 = st.tabs(["📸 AI Scanner", "📊 Live Analytics", "🏆 Leaderboard"])

    # TAB 1: SCANNER
    with tab1:
        st.markdown("### ♻️ Verify & Recycle")
        
        # Modern Location Card
        location = get_geolocation()
        lat, lon = None, None
        
        if location and 'coords' in location:
            lat, lon = location['coords']['latitude'], location['coords']['longitude']
            st.success("✅ GPS Active: Location Locked")
        else:
            st.warning("📡 Waiting for GPS Signal...")

        col_cam, col_guide = st.columns([2, 1])
        with col_cam:
            img_file = st.camera_input("Place item in frame")
            if img_file and lat:
                if st.button("🔍 Analyze Waste"):
                    can_scan, wait = check_cooldown(st.session_state['username'])
                    if not can_scan: st.error(f"⏳ Cooldown: Wait {wait}s"); st.toast("Cooldown Active!", icon="🛑")
                    else:
                        with st.spinner("Processing..."):
                            cat = check_if_recyclable(classify_image(Image.open(img_file)))
                            if cat[0]:
                                save_scan_data(st.session_state['username'], cat[1], lat, lon)
                                st.balloons()
                                st.success(f"Verified: {cat[1]} (+10 PTS)")
                            else: st.error("❌ Not Recyclable"); st.warning(f"Detected: {cat[1]}")
        with col_guide:
            st.info("💡 **Tips:**\n\n1. Keep object in center.\n2. Ensure good lighting.\n3. Only upload recyclables.")

    # TAB 2: ANALYTICS
    with tab2:
        st.markdown("### 🌏 Impact Overview")
        df = get_analytics_data()
        
        if not df.empty:
            # Metrics Row
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Scans", len(df), "+2 Today")
            c2.metric("Active Users", df['user'].nunique())
            c3.metric("Top Waste", df['item'].mode()[0] if not df.empty else "N/A")
            
            # Charts Row
            g1, g2 = st.columns([1, 2])
            with g1:
                st.markdown("**Waste Composition**")
                st.bar_chart(df['item'].value_counts(), color="#2E8B57")
            with g2:
                st.markdown("**Collection Hotspots**")
                st.map(df[['lat', 'lon']].dropna())
        else:
            st.info("Start scanning to see live data.")

    # TAB 3: LEADERBOARD
    with tab3:
        st.markdown("### 🏆 Top Green Warriors")
        docs = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(10).stream()
        
        # Custom Table Design
        data = [{"Rank": i+1, "User": d.to_dict()['name'], "Points": d.to_dict()['points']} for i, d in enumerate(docs)]
        st.dataframe(pd.DataFrame(data), use_container_width=True, hide_index=True)
