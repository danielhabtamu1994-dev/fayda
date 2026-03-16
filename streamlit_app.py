import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import re

# ፋይሎች መኖራቸውን እርግጠኛ ሁን
FONT_PATH = "Nyala.ttf"
BG_PATH = "1000123189.jpg"

st.set_page_config(page_title="Fayda Auto-Pro", layout="wide")

def clean_name_text(text):
    # ከስም ውስጥ ቁጥሮችን እና ምልክቶችን ማስወገጃ (Regex)
    # የአማርኛ ፊደላት፣ የእንግሊዝኛ ፊደላት እና ክፍት ቦታን ብቻ ያስቀራል
    cleaned = re.sub(r'[^ሀ-ፐአ-ዘ\sA-Za-z]', '', text)
    return cleaned.strip()

def extract_id_details(text):
    details = {"name": "", "dob": ""}
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        if "Full Name" in line or "ሙሉ ስም" in line:
            raw_name = re.sub(r'Full Name|ሙሉ ስም|[:|;]', '', line).strip()
            if not raw_name and i+1 < len(lines):
                raw_name = lines[i+1]
            details["name"] = clean_name_text(raw_name)
            
    # ቀን ፍለጋ (ከመስመር '|' በፊት ያለውን ብቻ መውሰድ)
    dob_match = re.search(r'\d{2}/\d{2}/\d{4}', text)
    if dob_match:
        details["dob"] = dob_match.group()
        
    return details

st.title("🪪 ፋይዳ አውቶ-ማዘጋጃ (የተስተካከለ)")

uploaded_file = st.file_uploader("የቁም መታወቂያ ምስል ይጫኑ...", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    if st.button("መታወቂያውን አዘጋጅ"):
        with st.spinner("ሲስተሙ እየቆረጠ ነው..."):
            # 1. OCR ንባብ (ለስም እና ለቀን)
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
            raw_text = pytesseract.image_to_string(gray, lang='amh+eng')
            info = extract_id_details(raw_text)
            
            # 2. ፎቶውን መቁረጥ (ROI)
            photo_crop = image_cv[int(h*0.18):int(h*0.48), int(w*0.30):int(w*0.65)]
            
            # 3. የፋይዳ ቁጥር ሳጥኑን መቁረጥ (ልክ እንደ ፎቶው)
            # ይህ ቦታ እንደ መታወቂያው ጥራት ትንሽ ማስተካከያ ሊፈልግ ይችላል
            fan_box_crop = image_cv[int(h*0.80):int(h*0.93), int(w*0.20):int(w*0.80)]
            
            try:
                # ባክግራውንድ ላይ መሳል
                bg_pil = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg_pil)
                nyala_font = ImageFont.truetype(FONT_PATH, 35)
                
                # ሀ. ፎቶውን ማሳረፍ
                photo_pil = Image.fromarray(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2RGB))
                photo_pil = photo_pil.resize((260, 310))
                bg_pil.paste(photo_pil, (65, 180))
                
                # ለ. የፋይዳ ቁጥር ሳጥኑን (ምስሉን) ማሳረፍ
                fan_pil = Image.fromarray(cv2.cvtColor(fan_box_crop, cv2.COLOR_BGR2RGB))
                fan_pil = fan_pil.resize((350, 60)) # መጠኑን እንደ ባክግራውንዱ ማስተካከል
                bg_pil.paste(fan_pil, (100, 520)) # የተቀመጠበት ቦታ (X, Y)
                
                # ሐ. ጽሁፎችን መጻፍ
                draw.text((415, 130), info["name"], font=nyala_font, fill="black")
                draw.text((415, 240), info["dob"], font=nyala_font, fill="black")
                
                st.image(bg_pil, caption="የተዘጋጀው መታወቂያ")
                
                buf = io.BytesIO()
                bg_pil.save(buf, format="PNG")
                st.download_button("መታወቂያውን አውርድ", buf.getvalue(), f"{info['name']}.png")
                
            except Exception as e:
                st.error(f"ስህተት ተፈጥሯል፦ {e}")
