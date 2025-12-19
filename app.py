import streamlit as st
from ultralytics import YOLO
from PIL import Image
import numpy as np
import firebase_admin
from firebase_admin import credentials, firestore
import hashlib
import time
import json

# --- PAGE CONFIG ---
st.set_page_config(page_title="TerraLens Pro V2", layout="wide")

# --- FIREBASE SETUP (Updated for Secrets) ---
if not firebase_admin._apps:
    try:
        # 1. Pehle Secrets se service_account ka string uthayenge
        secret_content = st.secrets["firebase"]["service_account"]
        
        # 2. String ko JSON dictionary mein convert karenge
        firebase_info = json.loads(secret_content)
        
        # 3. Firebase ko initialize karenge
        cred = credentials.Certificate(firebase_info)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        st.error(f"Firebase connection error: {e}")
        st.stop()

# Database client setup
db = firestore.client()

# --- AI MODEL LOAD (YOLOv8) ---
@st.cache_resource
def load_yolo_model():
    return YOLO('best.pt')

try:
    model = load_yolo_model()
except Exception as e:
    st.error(f"Model Load Error: {e}")

# --- WASTE MAPPING ---
# Roboflow ke classes ke hisaab se ise adjust karein
WASTE_MAP = {
    'plastic': {'points': 10, 'msg': "Great! Plastic recycled. ♻️"},
    'paper': {'points': 5, 'msg': "Paper added! Keep it up. 📄"},
    'metal': {'points': 15, 'msg': "Metal is valuable! Nice work. 🥫"},
    'glass': {'points': 12, 'msg': "Glass handled safely. 🍾"},
    'trash': {'points': 0, 'msg': "Non-recyclable item detected. 🚮"}
}

# --- FUNCTIONS ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def process_yolo(image):
    results = model(image)
    detected_items = []
    
    for r in results:
        # Bounding box wali image generate karna
        im_array = r.plot()  # Plotting boxes
        res_image = Image.fromarray(im_array[..., ::-1])
        
        for box in r.boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id].lower()
            conf = float(box.conf[0])
            if conf > 0.4: # 40% Confidence
                detected_items.append(label)
                
    return res_image, detected_items

# --- SESSION STATE ---
if 'user_id' not in st.session_state:
    st.session_state['user_id'] = None

# --- SIDEBAR: LOGIN/SIGNUP ---
with st.sidebar:
    st.title("🔐 User Portal")
    if not st.session_state['user_id']:
        choice = st.radio("Access", ["Login", "Sign Up"])
        u_email = st.text_input("Email")
        u_pass = st.text_input("Password", type='password')
        
        if st.button("Proceed"):
            h_pass = make_hashes(u_pass)
            if choice == "Sign Up":
                db.collection('users').document(u_email).set({
                    'email': u_email, 'pass': h_pass, 'points': 0, 'level': 'Rookie'
                })
                st.success("Account Created!")
            else:
                user_doc = db.collection('users').document(u_email).get()
                if user_doc.exists and user_doc.to_dict()['pass'] == h_pass:
                    st.session_state['user_id'] = u_email
                    st.rerun()
                else:
                    st.error("Invalid Credentials")
    else:
        st.write(f"Logged in as: **{st.session_state['user_id']}**")
        if st.button("Logout"):
            st.session_state['user_id'] = None
            st.rerun()

# --- MAIN APP INTERFACE ---
if st.session_state['user_id']:
    st.header("🌱 TerraLens AI Scanner (YOLOv8)")
    
    # User Stats
    u_data = db.collection('users').document(st.session_state['user_id']).get().to_dict()
    col1, col2 = st.columns(2)
    col1.metric("Your Eco-Points", u_data['points'])
    col2.metric("Current Rank", u_data['level'])

    # Camera Input
    img_file = st.camera_input("Scan Waste Item")

    if img_file:
        img = Image.open(img_file)
        with st.spinner('AI analyzing...'):
            processed_img, detected_labels = process_yolo(img)
        
        st.image(processed_img, caption="AI Result (Detection Boxes)")
        
        if detected_labels:
            # Sirf unique items pakadna
            unique_items = list(set(detected_labels))
            st.write(f"✅ Found: {', '.join(unique_items)}")
            
            total_points_earned = 0
            for item in unique_items:
                if item in WASTE_MAP:
                    points = WASTE_MAP[item]['points']
                    total_points_earned += points
                    st.info(f"{item.capitalize()}: {WASTE_MAP[item]['msg']}")
            
            if total_points_earned > 0:
                if st.button("Claim Points"):
                    new_pts = u_data['points'] + total_points_earned
                    # Level Logic
                    new_lvl = "Rookie"
                    if new_pts > 100: new_lvl = "Eco-Warrior"
                    if new_pts > 500: new_lvl = "Sustainability Legend"
                    
                    db.collection('users').document(st.session_state['user_id']).update({
                        'points': new_pts,
                        'level': new_lvl
                    })
                    st.balloons()
                    st.success(f"Added {total_points_earned} points to your account!")
                    time.sleep(2)
                    st.rerun()
        else:
            st.warning("AI couldn't verify the item. Try a better angle.")

else:
    st.info("Please Login from the sidebar to start scanning!")

# --- FOOTER: LEADERBOARD ---
st.divider()
st.subheader("🏆 Global Eco-Leaders")
top_users = db.collection('users').order_by('points', direction=firestore.Query.DESCENDING).limit(5).get()
for i, user in enumerate(top_users):
    d = user.to_dict()
    st.text(f"{i+1}. {d['email']} - {d['points']} pts ({d['level']})")
