import streamlit as st
import tensorflow as tf
from PIL import Image, ImageOps
import numpy as np
import firebase_admin
from firebase_admin import firestore
from firebase_admin import credentials
import os
import json

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="TerraLens Pro", page_icon="🌱", layout="centered")

# --- FIREBASE SETUP (Fix for Private Key Error) ---
try:
    # Secrets se JSON string uthayein
    key_dict = json.loads(st.secrets["textkey"])
    
    # --- BUG FIX: New Lines ko repair karein ---
    # Copy-paste mein aksar '\n' kharab ho jata hai, ye line usse theek kar degi
    if "private_key" in key_dict:
        key_dict["private_key"] = key_dict["private_key"].replace("\\n", "\n")

    cred = credentials.Certificate(key_dict)
    
    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    db = firestore.client()
except Exception as e:
    st.error(f"❌ Firebase Error: {e}")
    st.stop()
db = firestore.client()
# --- MODEL LOADING ---
@st.cache_resource
def load_model():
    model = tf.keras.applications.MobileNetV2(weights='imagenet')
    return model

model = load_model()

# --- FUNCTIONS ---
def get_user_data(username):
    doc_ref = db.collection('users').document(username)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    else:
        new_data = {"name": username, "points": 0}
        doc_ref.set(new_data)
        return new_data

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

# --- SIDEBAR LOGIN ---
st.sidebar.title("👤 Profile")
if 'username' not in st.session_state:
    username_input = st.sidebar.text_input("Enter Name to Login:")
    if st.sidebar.button("Login"):
        if username_input:
            st.session_state['username'] = username_input
            st.rerun()
else:
    username = st.session_state['username']
    user_data = get_user_data(username)
    current_points = user_data.get('points', 0)
    st.sidebar.success(f"Hi, {username}!")
    st.sidebar.metric("Wallet Balance", f"{current_points} 🪙")
    if st.sidebar.button("Logout"):
        del st.session_state['username']
        st.rerun()

# --- MAIN TABS ---
if 'username' in st.session_state:
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
                    recyclable = ['bottle', 'carton', 'can', 'paper', 'plastic', 'box']
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
    st.info("👈 Please Login from the Sidebar to start!")
