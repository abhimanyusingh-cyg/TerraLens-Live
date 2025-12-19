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
from streamlit_js_eval import get_geolocation # GPS Library

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Enterprise", page_icon="🌍", layout="wide")

# --- AI SMART MAPPING ---
def check_if_recyclable(label):
    label = label.lower()
    mapping = {
        'plastic': ['bottle', 'plastic', 'lotion', 'sunscreen', 'nematode', 'whistle', 'candle', 'lighter', 'cup'],
        'paper': ['carton', 'paper', 'envelope', 'tissue', 'towel', 'diaper', 'packet', 'menu', 'comic_book'],
        'metal': ['can', 'beer_glass', 'pop_bottle', 'corkscrew'],
        'glass': ['goblet', 'wine_bottle', 'beaker']
    }
    for category, keywords in mapping.items():
        if any(key in label for key in keywords):
            return True, category.upper()
    return False, label

# --- SECURITY & ANTI-CHEAT FUNCTIONS (RESTORED) ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text: return True
    return False

def check_cooldown(username):
    # User ka last scan time check karo
    doc = db.collection('users').document(username).get()
    if doc.exists:
        data = doc.to_dict()
        last_scan = data.get('last_scan_timestamp')
        
        if last_scan:
            # Timestamp check (Current time - Last Scan Time)
            # Firestore timestamp ko datetime mein convert karna pad sakta hai
            if hasattr(last_scan, 'timestamp'): 
                last_scan = last_scan.timestamp()
            
            now = datetime.now().timestamp()
            diff = now - last_scan
            
            # Agar 60 seconds se kam hua hai
            if diff < 60:
                return False, int(60 - diff)
    return True, 0

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    try:
        key_dict = json.loads(st.secrets["textkey"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except:
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if project_id:
            firebase_admin.initialize_app(options={'projectId': project_id})

db = firestore.client()
model = tf.keras.applications.MobileNetV2(weights='imagenet')

# --- DB FUNCTIONS ---
def create_user(username, password):
    doc_ref = db.collection('users').document(username)
    if doc_ref.get().exists: return False
    doc_ref.set({"name": username, "password": make_hashes(password), "points": 0})
    return True

def login_user(username, password):
    doc_ref = db.collection('users').document(username)
    doc = doc_ref.get()
    if doc.exists:
        if check_hashes(password, doc.to_dict().get("password")):
            return True, doc.to_dict().get("points")
    return False, 0

def save_scan_data(username, item_type, lat, lon):
    # 1. User ke points aur timer update karo
    db.collection('users').document(username).update({
        "points": firestore.Increment(10),
        "last_scan_timestamp": datetime.now().timestamp() # Timer set for cooldown
    })
    
    # 2. Scan ka data save karo (Map aur Charts ke liye)
    db.collection('scans').add({
        "user": username,
        "item": item_type,
        "lat": lat,
        "lon": lon,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

def get_analytics_data():
    # Charts ke liye data lao
    docs = db.collection('scans').stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        data.append(d)
    return pd.DataFrame(data)

def classify_image(image):
    img = ImageOps.fit(image, (224, 224), Image.Resampling.LANCZOS)
    img_array = tf.keras.applications.mobilenet_v2.preprocess_input(np.array(img))
    predictions = model.predict(np.expand_dims(img_array, axis=0))
    decoded = tf.keras.applications.mobilenet_v2.decode_predictions(predictions, top=1)[0][0]
    return decoded[1]

# --- APP UI ---
st.title("🌍 TerraLens Enterprise Dashboard")

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# LOGIN SYSTEM
if not st.session_state['logged_in']:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("### 🔐 Secure Login")
        menu = st.selectbox("Option", ["Login", "Sign Up"])
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        
        if menu == "Sign Up" and st.button("Create Account"):
            if create_user(user, pwd): st.success("Created! Login now.")
            else: st.error("User exists!")
            
        elif menu == "Login" and st.button("Login"):
            valid, pts = login_user(user, pwd)
            if valid:
                st.session_state['logged_in'] = True
                st.session_state['username'] = user
                st.rerun()
            else: st.error("Invalid Credentials")
    with col2:
        st.image("https://images.unsplash.com/photo-1532996122724-e3c354a0b15b", caption="AI Powered Waste Management")

else:
    # --- DASHBOARD (Logged In) ---
    with st.sidebar:
        st.write(f"👤 **{st.session_state['username']}**")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["📸 Scan & Earn", "📊 Analytics & Map", "🏆 Leaderboard"])

    # --- TAB 1: SCANNER + ANTI-CHEAT + GPS ---
    with tab1:
        col_scan, col_info = st.columns([2, 1])
        
        with col_scan:
            st.subheader("♻️ Waste Verification")
            
            # GPS Auto Fetch
            location = get_geolocation()
            lat, lon = None, None
            if location and 'coords' in location:
                lat = location['coords']['latitude']
                lon = location['coords']['longitude']
                st.success(f"📍 Location Locked")
            else:
                st.warning("⚠️ Fetching GPS... (Please Allow)")

            img_file = st.camera_input("Take a photo")
            
            if img_file:
                if lat is None:
                    st.error("🚫 GPS Required for verification.")
                else:
                    st.image(img_file, width=300)
                    if st.button("Verify Waste"):
                        # 1. COOLDOWN CHECK (ANTI-CHEAT)
                        can_scan, time_left = check_cooldown(st.session_state['username'])
                        
                        if not can_scan:
                            st.error(f"⏳ Cooldown Active! Wait {time_left} seconds.")
                            st.toast(f"Please wait {time_left}s", icon="⏳")
                        else:
                            # 2. AI ANALYSIS
                            with st.spinner("AI analyzing material..."):
                                raw_label = classify_image(Image.open(img_file))
                                is_valid, category = check_if_recyclable(raw_label)
                                
                                if is_valid:
                                    save_scan_data(st.session_state['username'], category, lat, lon)
                                    st.balloons()
                                    st.success(f"✅ Verified: {category} (+10 🪙)")
                                else:
                                    st.error("❌ Non-Recyclable Item")
                                    st.caption(f"AI Detected: {raw_label}")
        
        with col_info:
            st.info("ℹ️ Rules:\n1. Ensure good lighting.\n2. GPS must be on.\n3. Wait 60s between scans.")

    # --- TAB 2: ANALYTICS (CHARTS & MAPS) ---
    with tab2:
        st.subheader("🌏 Real-time Impact Report")
        
        df = get_analytics_data()
        
        if not df.empty:
            # Row 1: Key Metrics
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Waste Collected", f"{len(df)} Items")
            m2.metric("Active Users", f"{df['user'].nunique()}")
            top_item = df['item'].mode()[0] if not df.empty else "N/A"
            m3.metric("Most Common Waste", top_item)
            
            st.divider()
            
            # Row 2: Charts (Pie & Bar)
            c1, c2 = st.columns(2)
            
            with c1:
                st.markdown("#### Waste Composition")
                # Pie Chart Data
                counts = df['item'].value_counts()
                st.bar_chart(counts) # Streamlit ka simple bar chart (Pie chart ke liye extra library chahiye hoti hai, ye fast hai)
                
            with c2:
                st.markdown("#### Live Collection Map")
                # Map Data
                map_data = df[['lat', 'lon']].dropna()
                st.map(map_data)
                
        else:
            st.info("No data yet. Start scanning to see analytics!")

    # --- TAB 3: LEADERBOARD ---
    with tab3:
        st.subheader("🏆 Top Green Warriors")
        docs = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(10).stream()
        
        data = []
        for doc in docs:
            data.append(doc.to_dict())
        
        leader_df = pd.DataFrame(data)
        if not leader_df.empty:
            st.dataframe(leader_df[['name', 'points']], use_container_width=True, hide_index=True)
