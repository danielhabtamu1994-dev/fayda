import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io

# ፋይሎች በትክክል መኖራቸውን እናረጋግጥ
FONT_PATH = "Nyala.ttf"
BG_PATH = "1000123189.jpg"

st.set_page_config(page_title="Fayda Manual Editor", layout="wide")

st.title("🪪 ፋይዳ መታወቂያ አንባቢ (Manual Editor)")

uploaded_file = st.file_uploader("የቁም መታወቂያውን ይጫኑ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    # 1. OCR ሙሉውን እስክሪን እንዲያነብ ማድረግ
    if st.button("መረጃውን አንብብና አሳየኝ"):
        with st.spinner("ጽሁፉ እየተነበበ ነው..."):
            gray = cv2.cvtColor(image_cv, cv2.COLOR_BGR2GRAY)
            # ሁሉንም የአማርኛ እና የእንግሊዝኛ ጽሁፍ ማንበብ
            full_text = pytesseract.image_to_string(gray, lang='amh+eng')
            
            st.subheader("📝 የተገኘው ሙሉ ጽሁፍ")
            # ሁሉንም ጽሁፍ በትልቅ ሳጥን ውስጥ ያሳያል
            st.text_area("ከዚህ በታች ያለውን ጽሁፍ መርጠህ ተጠቀም፦", full_text, height=250)
            
            st.markdown("---")
            st.subheader("✏️ መረጃውን እዚህ ያርሙ")
            
            # ተጠቃሚው እዚህ ጋር ስምና ቀን ይሞላል
            col1, col2 = st.columns(2)
            with col1:
                st.session_state['name'] = st.text_input("ሙሉ ስም (Amharic & English):")
            with col2:
                st.session_state['dob'] = st.text_input("የትውልድ ቀን (DOB):")

    # 2. መታወቂያውን ማዘጋጀት
    if 'name' in st.session_state and st.button("መታወቂያውን አዘጋጅ"):
        with st.spinner("ምስሉ እየተዘጋጀ ነው..."):
            # ፎቶ መቁረጥ (ከመታወቂያው ላይ ፎቶ ያለበትን ቦታ)
            photo_crop = image_cv[int(h*0.12):int(h*0.42), int(w*0.05):int(w*0.35)]
            # የፋይዳ ቁጥር ሳጥን መቁረጥ
            fan_crop = image_cv[int(h*0.82):int(h*0.95), int(w*0.15):int(w*0.85)]

            try:
                bg_pil = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg_pil)
                font = ImageFont.truetype(FONT_PATH, 35)

                # ፎቶ መለጠፍ
                photo_pil = Image.fromarray(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2RGB)).resize((260, 310))
                bg_pil.paste(photo_pil, (65, 180))

                # የፋይዳ ቁጥር መለጠፍ
                fan_pil = Image.fromarray(cv2.cvtColor(fan_crop, cv2.COLOR_BGR2RGB)).resize((380, 70))
                bg_pil.paste(fan_pil, (100, 520))

                # ጽሁፎችን መጻፍ
                draw.text((415, 130), st.session_state['name'], font=font, fill="black")
                draw.text((415, 250), st.session_state['dob'], font=font, fill="black")

                st.image(bg_pil, caption="የተዘጋጀው መታወቂያ")
                
                buf = io.BytesIO()
                bg_pil.save(buf, format="PNG")
                st.download_button("መታወቂያውን አውርድ", buf.getvalue(), "fayda_custom.png")

            except Exception as e:
                st.error(f"ስህተት፦ {e}")
