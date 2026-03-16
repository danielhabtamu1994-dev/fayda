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

st.set_page_config(page_title="Fayda Professional Fixer", layout="wide")

def get_structured_data(text):
    # መረጃዎችን ለመለየት የሚያገለግል ተግባር
    data = {"amh_name": "", "eng_name": "", "dates": ""}
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # 1. ስም ፍለጋ (ከ Full Name በታች ያሉትን ሁለት መስመሮች መፈለግ)
    for i, line in enumerate(lines):
        if "Full Name" in line or "ሙሉ ስም" in line:
            if i + 1 < len(lines):
                data["amh_name"] = re.sub(r'[^ሀ-ፐአ-ዘ\s]', '', lines[i+1]).strip()
            if i + 2 < len(lines):
                data["eng_name"] = re.sub(r'[^A-Za-z\s]', '', lines[i+2]).strip()
    
    # 2. ቀን ፍለጋ (ሁሉንም ቀኖች ማውጣት)
    found_dates = re.findall(r'\d{2,4}/\w+/\d{2,4}|\d{2,4}/\d{2}/\d{2,4}', text)
    if found_dates:
        data["dates"] = " | ".join(found_dates)
        
    return data

st.title("🪪 ፋይዳ ፕሮፌሽናል ማቀነባበሪያ")

uploaded_file = st.file_uploader("የቁም መታወቂያውን ይጫኑ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    if st.button("መረጃውን አውጣና አዘጋጅ"):
        with st.spinner("በማቀነባበር ላይ..."):
            # OCR ንባብ
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
            raw_text = pytesseract.image_to_string(gray, lang='amh+eng')
            info = get_structured_data(raw_text)

            # 1. ፎቶውን መቁረጥ (ከላይ በግራ በኩል ካለው ቦታ)
            photo_crop = image_cv[int(h*0.10):int(h*0.35), int(w*0.05):int(w*0.35)]
            
            # 2. የፋይዳ ቁጥር ሳጥኑን መቁረጥ (ከታች መሃል)
            fan_crop = image_cv[int(h*0.82):int(h*0.95), int(w*0.15):int(w*0.85)]

            try:
                bg_pil = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg_pil)
                # ለአማርኛ እና እንግሊዝኛ ስም የሚሆኑ ፎንቶች
                font_large = ImageFont.truetype(FONT_PATH, 38)
                font_small = ImageFont.truetype(FONT_PATH, 28)

                # ሀ. ፎቶውን መለጠፍ
                photo_pil = Image.fromarray(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2RGB)).resize((250, 300))
                bg_pil.paste(photo_pil, (60, 180))

                # ለ. የፋይዳ ቁጥርን መለጠፍ
                fan_pil = Image.fromarray(cv2.cvtColor(fan_crop, cv2.COLOR_BGR2RGB)).resize((380, 70))
                bg_pil.paste(fan_pil, (100, 520))

                # ሐ. ጽሁፎችን መጻፍ
                # አማርኛ ስም
                draw.text((415, 110), info["amh_name"], font=font_large, fill="black")
                # እንግሊዝኛ ስም (ከስሩ)
                draw.text((415, 160), info["eng_name"], font=font_large, fill="black")
                # ቀን
                draw.text((415, 260), info["dates"], font=font_small, fill="black")

                st.image(bg_pil, caption="የተስተካከለ መታወቂያ")
                
                # Download
                buf = io.BytesIO()
                bg_pil.save(buf, format="PNG")
                st.download_button("መታወቂያውን አውርድ", buf.getvalue(), "fayda_fixed.png")

            except Exception as e:
                st.error(f"ስህተት፦ {e}")
