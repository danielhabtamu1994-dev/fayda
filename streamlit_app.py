import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import re

# ፋይሎች በትክክል መኖራቸውን እናረጋግጥ
FONT_PATH = "Nyala.ttf"
BG_PATH = "1000123189.jpg"

st.set_page_config(page_title="Fayda Auto-Convert Pro", layout="wide")

def clean_name_text(text):
    # ከስም ውስጥ ቁጥሮችን እና አላስፈላጊ ምልክቶችን ብቻ ያጠፋል
    # አማርኛ፣ እንግሊዝኛ እና ክፍት ቦታን (Space) ያስቀራል
    cleaned = re.sub(r'[^ሀ-ፐአ-ዘ\sA-Za-z]', '', text)
    # ከአንድ በላይ የሆኑ ክፍት ቦታዎችን ወደ አንድ ይቀንሳል
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def extract_id_details(text):
    details = {"name": "", "dob": ""}
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for i, line in enumerate(lines):
        if "Full Name" in line or "ሙሉ ስም" in line:
            # ርዕሱን ያጠፋል
            raw_name = re.sub(r'Full Name|ሙሉ ስም|[:|;]', '', line).strip()
            # መስመሩ ባዶ ከሆነ ቀጣዩን መስመር ይወስዳል
            if not raw_name and i+1 < len(lines):
                raw_name = lines[i+1]
            details["name"] = clean_name_text(raw_name)
            
    # ቀን ፍለጋ፦ ሁሉንም ቀኖች ያገኛል (ለምሳሌ 03/10/1994 እና 2002/06/10)
    # የ '|' ምልክትን እና ሌሎች ምልክቶችን አጥፍቶ ቀኖቹን ብቻ ያስቀራል
    dates = re.findall(r'\d{2,4}/\d{2}/\d{2,4}', text)
    if dates:
        # ሁሉንም የተገኙ ቀኖች በመስመር አገናኝቶ ያሳያል
        details["dob"] = " | ".join(dates)
        
    return details

st.title("🪪 የፋይዳ መታወቂያ ራስ-ሰር ማቀነባበሪያ (የተስተካከለ)")

uploaded_file = st.file_uploader("የቁም መታወቂያ ምስል እዚህ ያስገቡ", type=['png', 'jpg', 'jpeg'])

if uploaded_file is not None:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    # መረጃን አስቀድሞ ለማየት እና ለማረም
    if st.button("መረጃውን መጀመሪያ አውጣ"):
        gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
        raw_text = pytesseract.image_to_string(gray, lang='amh+eng')
        info = extract_id_details(raw_text)
        
        # ተጠቃሚው እንዲያርም ሳጥን ውስጥ እናስቀምጠው
        col_name, col_dob = st.columns(2)
        with col_name:
            final_name = st.text_input("የተገኘ ስም (አርም)፦", value=info["name"])
        with col_dob:
            final_dob = st.text_input("የተገኘ ቀን (አርም)፦", value=info["dob"])
            
        st.session_state['final_name'] = final_name
        st.session_state['final_dob'] = final_dob

    if st.button("መታወቂያውን አሁኑኑ አዘጋጅ"):
        name_to_draw = st.session_state.get('final_name', "")
        dob_to_draw = st.session_state.get('final_dob', "")
        
        with st.spinner("በሂደት ላይ ነው..."):
            # 1. ፎቶውን መቁረጥ (ROI)
            photo_crop = image_cv[int(h*0.18):int(h*0.48), int(w*0.30):int(w*0.65)]
            
            # 2. የፋይዳ ቁጥር ሳጥኑን መቁረጥ (ምስሉን)
            fan_box_crop = image_cv[int(h*0.80):int(h*0.93), int(w*0.20):int(w*0.80)]
            
            try:
                bg_pil = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg_pil)
                nyala_font = ImageFont.truetype(FONT_PATH, 30) # ቀኑ ረጅም ስለሚሆን ፎንቱን ትንሽ ቀነስኩት
                
                # ሀ. ፎቶውን ማሳረፍ
                photo_pil = Image.fromarray(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2RGB))
                photo_pil = photo_pil.resize((260, 310))
                bg_pil.paste(photo_pil, (65, 180))
                
                # ለ. የፋይዳ ቁጥር ሳጥኑን ማሳረፍ
                fan_pil = Image.fromarray(cv2.cvtColor(fan_box_crop, cv2.COLOR_BGR2RGB))
                fan_pil = fan_pil.resize((350, 60))
                bg_pil.paste(fan_pil, (100, 520))
                
                # ሐ. ጽሁፎችን መጻፍ
                draw.text((415, 130), name_to_draw, font=nyala_font, fill="black")
                draw.text((415, 240), dob_to_draw, font=nyala_font, fill="black")
                
                st.image(bg_pil, caption="የተዘጋጀው መታወቂያ")
                
                buf = io.BytesIO()
                bg_pil.save(buf, format="PNG")
                st.download_button("መታወቂያውን አውርድ", buf.getvalue(), f"{name_to_draw}.png")
                
            except Exception as e:
                st.error(f"ስህተት ተፈጥሯል፦ {e}")
