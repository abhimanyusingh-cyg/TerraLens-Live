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
from streamlit_js_eval import get_geolocation # NEW LIBRARY FOR GPS

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Enterprise", page_icon="🌍", layout="centered")

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

# --- UTILS & SECURITY ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text: return True
    return False

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
    db.collection('users').document(username).update({"points": firestore.Increment(10)})
    db.collection('scans').add({
        "user": username,
        "item": item_type,
        "lat": lat, # REAL GPS LAT
        "lon": lon, # REAL GPS LON
        "timestamp": firestore.SERVER_TIMESTAMP
    })

def get_map_data():
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

# LOGIN
if not st.session_state['logged_in']:
    menu = st.selectbox("Option", ["Login", "Sign Up"])
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    
    if menu == "Sign Up" and st.button("Create Account"):
        if create_user(user, pwd): st.success("Account Created!")
        else: st.error("User exists!")
        
    elif menu == "Login" and st.button("Login"):
        valid, pts = login_user(user, pwd)
        if valid:
            st.session_state['logged_in'] = True
            st.session_state['username'] = user
            st.rerun()
        else: st.error("Invalid Credentials")

else:
    # LOGGED IN UI
    with st.sidebar:
        st.write(f"👤 **{st.session_state['username']}**")
        if st.button("Logout"):
            st.session_state['logged_in'] = False
            st.rerun()

    tab1, tab2, tab3 = st.tabs(["📸 Scan", "🌏 Live Map", "🏆 Ranks"])

    with tab1:
        st.header("Recycle Waste")
        
        # --- NEW: AUTOMATIC GPS FETCHER ---
        st.info("📡 Getting your GPS Location...")
        location = get_geolocation() # Ye browser se location mangega

        lat, lon = None, None
        if location and 'coords' in location:
            lat = location['coords']['latitude']
            lon = location['coords']['longitude']
            st.success(f"📍 Location Found: {lat:.4f}, {lon:.4f}")
        else:
            st.warning("⚠️ Waiting for GPS... (Allow location access in browser)")

        img_file = st.camera_input("Take a photo")
        
        if img_file:
            if lat is None:
                st.error("🚫 Cannot verify without Location! Please allow GPS.")
            else:
                st.image(img_file, width=300)
                if st.button("♻️ Verify"):
                    with st.spinner("Analyzing..."):
                        raw_label = classify_image(Image.open(img_file))
                        is_valid, category = check_if_recyclable(raw_label)
                        
                        if is_valid:
                            # Ab hum Real GPS Coordinates save kar rahe hain
                            save_scan_data(st.session_state['username'], category, lat, lon)
                            st.balloons()
                            st.success(f"Verified: {category} (+10 🪙)")
                        else:
                            st.error(f"Item not recyclable.")
                            st.caption(f"AI Detected: {raw_label}")

    with tab2:
        st.header("🌏 Impact Map")
        map_data = get_map_data()
        if not map_data.empty:
            st.map(map_data, zoom=14) 
            st.write(f"Live Scans: {len(map_data)}")
        else:
            st.info("No data available.")

    with tab3:
        st.subheader("Leaderboard")
        docs = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(5).stream()
        for i, doc in enumerate(docs):
            st.write(f"{i+1}. {doc.to_dict()['name']} - {doc.to_dict()['points']} 🪙")
