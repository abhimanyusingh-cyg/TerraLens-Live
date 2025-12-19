import streamlit as st
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import firebase_admin
from firebase_admin import firestore, credentials
import os
import json
import hashlib

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Pro", page_icon="🌱", layout="centered")

# --- SECURITY FUNCTIONS (HASHING) ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    if make_hashes(password) == hashed_text:
        return True
    return False

# --- FIREBASE SETUP ---
if not firebase_admin._apps:
    try:
        # Koshish karein Secrets se key lene ki (Cloud ke liye)
        key_dict = json.loads(st.secrets["textkey"])
        if "private_key" in key_dict:
            key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")
        cred = credentials.Certificate(key_dict)
        firebase_admin.initialize_app(cred)
    except:
        # Fallback for Local Testing (Cloud Shell Auto-Login)
        # Agar secrets nahi mile toh environment auth use karega
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT')
        if project_id:
            firebase_admin.initialize_app(options={'projectId': project_id})
        else:
            st.warning("⚠️ Database connect nahi ho paya. Check Secrets or Local Auth.")

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
        return False # User pehle se hai
    else:
        # Password ko Hash karke save karein
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
        # Check karein agar password match ho raha hai
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

# --- APP UI START ---
st.title("🌱 TerraLens Ecosystem")

# --- SESSION MANAGEMENT ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ""

# --- SIDEBAR: LOGIN / SIGNUP SYSTEM ---
st.sidebar.title("🔐 Secure Access")

if not st.session_state['logged_in']:
    choice = st.sidebar.selectbox("Menu", ["Login", "Sign Up"])
    
    if choice == "Sign Up":
        st.sidebar.subheader("Create New Account")
        new_user = st.sidebar.text_input("Username")
        new_pass = st.sidebar.text_input("Password", type='password')
        if st.sidebar.button("Sign Up"):
            if new_user and new_pass:
                if create_user(new_user, new_pass):
                    st.sidebar.success("Account Created! Please Login.")
                else:
                    st.sidebar.error("Username already exists!")
            else:
                st.sidebar.warning("Please fill all fields")

    elif choice == "Login":
        st.sidebar.subheader("Login to Dashboard")
        username = st.sidebar.text_input("Username")
        password = st.sidebar.text_input("Password", type='password')
        if st.sidebar.button("Login"):
            is_valid, points = login_user(username, password)
            if is_valid:
                st.session_state['logged_in'] = True
                st.session_state['username'] = username
                st.rerun()
            else:
                st.sidebar.error("Incorrect Username or Password")

else:
    # AGAR LOGIN HO GAYA HAI:
    username = st.session_state['username']
    
    # Live points fetch karein
    doc = db.collection('users').document(username).get()
    current_points = doc.to_dict().get('points', 0)
    
    st.sidebar.success(f"Welcome, {username}!")
    st.sidebar.metric("Your Balance", f"{current_points} 🪙")
    
    if st.sidebar.button("Logout"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.rerun()

# --- MAIN APP CONTENT (Only visible after Login) ---
if st.session_state['logged_in']:
    tab1, tab2, tab3 = st.tabs(["📸 Scan Waste", "🏆 Leaderboard", "🎁 Redeem Store"])

    # TAB 1: SCANNER
    with tab1:
        st.header("Earn Green Credits")
        option = st.radio("Input Type:", ("Camera", "Upload File"), horizontal=True)
        image_input = st.camera_input("Snap!") if option == "Camera" else st.file_uploader("Upload", type=["jpg", "png"])

        if image_input:
            image = Image.open(image_input)
            st.image(image, caption="Uploaded Photo", use_column_width=True)
            if st.button("♻️ Verify Now"):
                with st.spinner("AI checking..."):
                    label, confidence = classify_image(image, model)
                    recyclable = ['bottle', 'carton', 'can', 'paper', 'plastic', 'box', 'cup']
                    if any(x in label.lower() for x in recyclable):
                        st.balloons()
                        update_points(st.session_state['username'], 10)
                        st.success(f"Verified: {label} (+10 🪙)")
                    else:
                        st.error(f"Trash Detected: {label}")
                        st.warning("Only Recyclables give points!")

    # TAB 2: LEADERBOARD
    with tab2:
        st.header("🏆 Top Recyclers")
        leaders = get_leaderboard()
        for i, (name, pts) in enumerate(leaders):
            st.markdown(f"**{i+1}. {name}** — {pts} 🪙")

    # TAB 3: REDEEM STORE
    with tab3:
        st.header("🎁 Redeem Your Credits")
        col1, col2 = st.columns(2)
        with col1:
            st.info("🎟️ Amazon ₹50 Voucher")
            st.write("Cost: **500 🪙**")
            st.button("Redeem", key="amz")
        with col2:
            st.info("☕ Starbucks Coffee")
            st.write("Cost: **300 🪙**")
            st.button("Redeem", key="sbux")

else:
    # LANDING PAGE (Jab user logout ho)
    st.markdown("## 🌍 Welcome to TerraLens")
    st.info("👈 Please **Login** or **Sign Up** from the Sidebar to start earning credits!")
    st.image("https://images.unsplash.com/photo-1532996122724-e3c354a0b15b", caption="Recycle Today for a Better Tomorrow")
