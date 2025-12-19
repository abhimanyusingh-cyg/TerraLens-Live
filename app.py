import streamlit as st
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import firebase_admin
from firebase_admin import firestore, credentials
import os
import json
import hashlib
import time
from datetime import datetime
import pandas as pd # Maps ke liye data handle karne ke liye

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Enterprise", page_icon="🌍", layout="centered")

# --- MOCK LOCATIONS (DEMO COORDINATES) ---
# Real life mein ye GPS se aayega, abhi hum Campus Zones define kar rahe hain
ZONES = {
    "Select Zone": {"lat": 0, "lon": 0},
    "Main Cafeteria": {"lat": 28.5457, "lon": 77.3327}, # Example Coordinates
    "Admin Block": {"lat": 28.5440, "lon": 77.3330},
    "Girls Hostel": {"lat": 28.5460, "lon": 77.3340},
    "Boys Hostel": {"lat": 28.5470, "lon": 77.3310},
    "Sports Complex": {"lat": 28.5430, "lon": 77.3350}
}

# --- SECURITY & UTILS ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

def get_image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

# --- DATABASE CONNECTION ---
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

# --- CORE FUNCTIONS ---
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

def save_scan_data(username, label, zone_name, lat, lon):
    # 1. Update User Points
    db.collection('users').document(username).update({"points": firestore.Increment(10)})
    
    # 2. Save Scan Location for Map (Analytics)
    db.collection('scans').add({
        "user": username,
        "item": label,
        "zone": zone_name,
        "lat": lat,
        "lon": lon,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

def get_map_data():
    # Saare scans fetch karo map par dikhane ke liye
    docs = db.collection('scans').stream()
    data = []
    for doc in docs:
        d = doc.to_dict()
        if 'lat' in d and 'lon' in d:
            data.append({"lat": d['lat'], "lon": d['lon']})
    return pd.DataFrame(data)

def classify_image(image):
    img = ImageOps.fit(image, (224, 224), Image.Resampling.LANCZOS)
    img_array = tf.keras.applications.mobilenet_v2.preprocess_input(np.array(img))
    predictions = model.predict(np.expand_dims(img_array, axis=0))
    decoded = tf.keras.applications.mobilenet_v2.decode_predictions(predictions, top=1)[0][0]
    return decoded[1]

# --- APP UI ---
st.title("🌍 TerraLens Enterprise")

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

# SIDEBAR
st.sidebar.title("🔐 Access Portal")
if not st.session_state['logged_in']:
    menu = st.sidebar.selectbox("Menu", ["Login", "Sign Up"])
    user = st.sidebar.text_input("Username")
    pwd = st.sidebar.text_input("Password", type="password")
    
    if menu == "Sign Up" and st.sidebar.button("Create Account"):
        if create_user(user, pwd): st.sidebar.success("Created! Login now.")
        else: st.sidebar.error("User exists!")
        
    elif menu == "Login" and st.sidebar.button("Login"):
        valid, pts = login_user(user, pwd)
        if valid:
            st.session_state['logged_in'] = True
            st.session_state['username'] = user
            st.rerun()
        else: st.sidebar.error("Invalid Credentials")
else:
    st.sidebar.success(f"User: {st.session_state['username']}")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.rerun()

# MAIN TABS
if st.session_state['logged_in']:
    # Adding a 4th Tab for Analytics
    tab1, tab2, tab3, tab4 = st.tabs(["📸 Scanner", "🌏 Global Map", "🏆 Leaders", "🎁 Store"])

    # TAB 1: SCANNER WITH LOCATION
    with tab1:
        st.header("♻️ Recycle & Tag")
        
        # New Feature: Location Selector
        selected_zone = st.selectbox("📍 Where are you recycling?", list(ZONES.keys()))
        
        img_file = st.camera_input("Scan Waste")
        
        if img_file:
            if selected_zone == "Select Zone":
                st.warning("⚠️ Please select a valid Location Zone first!")
            else:
                st.image(img_file, caption="Preview", width=300)
                if st.button("Verify & Upload"):
                    with st.spinner("Analyzing Material..."):
                        label = classify_image(Image.open(img_file))
                        recyclable = ['bottle', 'carton', 'can', 'paper', 'plastic', 'box', 'cup']
                        
                        if any(x in label.lower() for x in recyclable):
                            # Save Data with Coordinates
                            coords = ZONES[selected_zone]
                            save_scan_data(st.session_state['username'], label, selected_zone, coords['lat'], coords['lon'])
                            
                            st.balloons()
                            st.success(f"Verified: {label} @ {selected_zone} (+10 🪙)")
                        else:
                            st.error(f"Trash Detected: {label}")

    # TAB 2: LIVE MAP (BUSINESS INTELLIGENCE)
    with tab2:
        st.header("🌏 Live Impact Tracker")
        st.markdown("Real-time recycling activity across zones.")
        
        # Fetch Data
        map_data = get_map_data()
        
        if not map_data.empty:
            st.map(map_data) # This creates the interactive map
            st.markdown(f"**Total Items Recycled:** {len(map_data)}")
        else:
            st.info("No data yet. Start scanning!")

    # TAB 3 & 4 (Standard)
    with tab3:
        st.subheader("Top Recyclers")
        # (Simplified Leaderboard for brevity)
        docs = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(5).stream()
        for i, doc in enumerate(docs):
            st.write(f"{i+1}. {doc.to_dict()['name']} - {doc.to_dict()['points']} 🪙")
            
    with tab4:
        st.header("🎁 Rewards")
        st.info("Redeem functionality coming soon.")

else:
    st.info("Please Login to access the Enterprise Dashboard.")
