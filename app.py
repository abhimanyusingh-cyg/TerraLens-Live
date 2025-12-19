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
from datetime import datetime, timedelta

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Pro", page_icon="🌱", layout="centered")

# --- SECURITY FUNCTIONS ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

# --- ANTI-CHEAT FUNCTIONS ---
def get_image_hash(image_bytes):
    return hashlib.md5(image_bytes).hexdigest()

def check_duplicate_image(image_hash):
    doc = db.collection('processed_images').document(image_hash).get()
    return doc.exists

def save_image_hash(image_hash, username, label):
    db.collection('processed_images').document(image_hash).set({
        "used_by": username,
        "label": label,
        "timestamp": firestore.SERVER_TIMESTAMP
    })

# --- COOLDOWN LOGIC (NEW) ---
def check_cooldown(username):
    # User ka data lao
    doc = db.collection('users').document(username).get()
    if doc.exists:
        data = doc.to_dict()
        last_scan = data.get('last_scan_timestamp')
        
        if last_scan:
            # Current time (seconds mein)
            now = datetime.now().timestamp()
            # Difference nikalo
            diff = now - last_scan
            
            # Agar 60 seconds (1 Minute) se kam hua hai
            if diff < 60:
                return False, int(60 - diff) # Return seconds left
                
    return True, 0

def update_scan_time(username):
    # Current time save karo
    now = datetime.now().timestamp()
    db.collection('users').document(username).update({
        "last_scan_timestamp": now
    })

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

# --- MODEL LOADING ---
@st.cache_resource
def load_model():
    model = tf.keras.applications.MobileNetV2(weights='imagenet')
    return model

model = load_model()

# --- DATABASE FUNCTIONS ---
def create_user(username, password):
    doc_ref = db.collection('users').document(username)
    if doc_ref.get().exists:
        return False
    else:
        doc_ref.set({
            "name": username,
            "password": make_hashes(password),
            "points": 0
        })
        return True

def login_user(username, password):
    doc_ref = db.collection('users').document(username)
    doc = doc_ref.get()
    if doc.exists:
        user_data = doc.to_dict()
        stored_password = user_data.get("password")
        if stored_password and check_hashes(password, stored_password):
            return True, user_data.get("points")
    return False, 0

def update_points(username, points_to_add):
    doc_ref = db.collection('users').document(username)
    doc_ref.update({"points": firestore.Increment(points_to_add)})

def get_leaderboard():
    docs = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(5).stream()
    return [(doc.to_dict()['name'], doc.to_dict()['points']) for doc in docs]

def classify_image(image, model):
    img = ImageOps.fit(image, (224, 224), Image.Resampling.LANCZOS)
    img_array = np.array(img)
    img_array = tf.keras.applications.mobilenet_v2.preprocess_input(img_array)
    img_array = np.expand_dims(img_array, axis=0)
    predictions = model.predict(img_array)
    decoded = tf.keras.applications.mobilenet_v2.decode_predictions(predictions, top=1)[0][0]
    return decoded[1], decoded[2] * 100

# --- APP UI ---
st.title("🌱 TerraLens Ecosystem")

if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""

# --- SIDEBAR ---
st.sidebar.title("🔐 Secure Access")

if not st.session_state['logged_in']:
    choice = st.sidebar.selectbox("Menu", ["Login", "Sign Up"])
    if choice == "Sign Up":
        new_user = st.sidebar.text_input("Username")
        new_pass = st.sidebar.text_input("Password", type='password')
        if st.sidebar.button("Sign Up"):
            if new_user and new_pass:
                if create_user(new_user, new_pass):
                    st.sidebar.success("Account Created! Please Login.")
                else:
                    st.sidebar.error("Username already exists!")
    elif choice == "Login":
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type='password')
        if st.sidebar.button("Login"):
            is_valid, points = login_user(username, password)
            if is_valid:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.rerun()
            else:
                st.sidebar.error("Wrong Credentials")
else:
    username = st.session_state['username']
    doc = db.collection('users').document(username).get()
    current_points = doc.to_dict().get('points', 0)
    st.sidebar.success(f"Hi, {username}!")
    st.sidebar.metric("Balance", f"{current_points} 🪙")
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()

# --- MAIN CONTENT ---
if st.session_state['logged_in']:
    tab1, tab2, tab3 = st.tabs(["📸 Scan Waste", "🏆 Leaderboard", "🎁 Redeem Store"])

    with tab1:
        st.header("Earn Green Credits")
        st.info("ℹ️ Policy: You can scan 1 item every 60 seconds.")
        
        option = st.radio("Input Type:", ("Camera", "Upload File"), horizontal=True)
        image_input = st.camera_input("Snap!") if option == "Camera" else st.file_uploader("Upload", type=["jpg", "png"])

        if image_input:
            image = Image.open(image_input)
            st.image(image, caption="Uploaded Photo", use_column_width=True)
            
            image_input.seek(0)
            file_bytes = image_input.read()
            img_hash = get_image_hash(file_bytes)
            
            if st.button("♻️ Verify Now"):
                # 1. Check Cooldown (Time Limit)
                can_scan, seconds_left = check_cooldown(st.session_state['username'])
                
                if not can_scan:
                    st.error(f"⏳ Please wait {seconds_left} seconds before scanning again.")
                
                # 2. Check Duplicate (Exact Copy)
                elif check_duplicate_image(img_hash):
                    st.error("🚫 Duplicate Photo Detected!")
                    st.warning("Please do not use the exact same file.")
                
                else:
                    # 3. Run AI Model
                    with st.spinner("AI checking..."):
                        label, confidence = classify_image(image, model)
                        recyclable = ['bottle', 'carton', 'can', 'paper', 'plastic', 'box', 'cup']
                        
                        if any(x in label.lower() for x in recyclable):
                            st.balloons()
                            update_points(st.session_state['username'], 10)
                            
                            # Save Hash & Time
                            save_image_hash(img_hash, st.session_state['username'], label)
                            update_scan_time(st.session_state['username'])
                            
                            st.success(f"Verified: {label} (+10 🪙)")
                        else:
                            st.error(f"Trash Detected: {label}")
                            st.warning("Only Recyclables give points!")

    with tab2:
        st.header("🏆 Top Recyclers")
        leaders = get_leaderboard()
        for i, (name, pts) in enumerate(leaders):
            st.markdown(f"**{i+1}. {name}** — {pts} 🪙")

    with tab3:
        st.header("🎁 Redeem Store")
        st.write("Current Balance:", current_points, "🪙")

else:
    st.image("https://images.unsplash.com/photo-1532996122724-e3c354a0b15b")
