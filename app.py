import streamlit as st
from ultralytics import YOLO
from PIL import Image
import numpy as np

# --- AI MODEL LOAD (V2) ---
# Dhyan rahe 'best.pt' file aapke main folder mein honi chahiye
try:
    model = YOLO('best.pt') 
except Exception as e:
    st.error("Model file 'best.pt' nahi mili. Please upload it to your repo.")

# --- WASTE MAPPING LOGIC ---
# Roboflow ke dataset mein jo classes thi, unhe yahan map karein
# Agar aapke dataset mein alag categories hain, toh unhe update karein
WASTE_CATEGORIES = {
    'plastic': {'points': 10, 'recyclable': True},
    'metal': {'points': 15, 'recyclable': True},
    'paper': {'points': 5, 'recyclable': True},
    'glass': {'points': 12, 'recyclable': True},
    'trash': {'points': 0, 'recyclable': False}
}

def process_detection(image):
    # Model se prediction lena
    results = model(image)
    
    detections = []
    # Results ko process karna
    for r in results:
        # Detected image (boxes ke saath)
        im_array = r.plot()  # Bounding boxes draw karta hai
        res_image = Image.fromarray(im_array[..., ::-1]) # RGB conversion
        
        for box in r.boxes:
            class_id = int(box.cls[0])
            label = model.names[class_id].lower()
            conf = float(box.conf[0])
            if conf > 0.4: # 40% confidence threshold
                detections.append(label)
                
    return res_image, detections

# --- STREAMLIT UI UPDATE ---
st.title("🌱 TerraLens Pro V2: Live AI Scanner")

uploaded_file = st.camera_input("Scan Waste")

if uploaded_file:
    img = Image.open(uploaded_file)
    
    # Process Detection
    with st.spinner('AI analyzing frames...'):
        processed_img, detected_items = process_detection(img)
    
    # Show Output Image with Boxes
    st.image(processed_img, caption="AI Real-time Detection")
    
    if detected_items:
        st.success(f"Detected: {', '.join(set(detected_items))}")
        # Baaki points aur database logic yahan aayega...
    else:
        st.warning("Kuch pehchaan mein nahi aaya. Please try another angle.")
