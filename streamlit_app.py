import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd

# ፋይሎች
FONT_PATH = "Nyala.ttf"
BG_PATH = "1000123189.jpg"

st.set_page_config(page_title="Fayda Precision ID", layout="wide")

st.title("🪪 ፋይዳ ስማርት አንባቢ (ትክክለኛ ልኬት)")

uploaded_file = st.file_uploader("የቁም መታወቂያውን እዚህ ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]
    
    # መታወቂያውን ብቻ ለይቶ መቁረጥ (ቀይ መስመር ያደረግክበት ቦታ)
    id_only = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

    if st.button("መረጃውን በሰንጠረዥ አውጣ"):
        with st.spinner("ጽሁፉ እየተተነተነ ነው..."):
            gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
            full_text = pytesseract.image_to_string(gray, lang='amh+eng')
            lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 1]
            st.session_state['ocr_lines'] = lines
            st.table(pd.DataFrame([{"ቁጥር": i+1, "ጽሁፍ": l} for i, l in enumerate(lines)]))

    st.markdown("---")
    
    # የቁጥር መለያዎች
    col1, col2, col3 = st.columns(3)
    with col1:
        amh_n = st.number_input("አማርኛ ስም ቁጥር (5):", value=5)
        eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር (6):", value=6)
    with col2:
        dob_n = st.number_input("የትውልድ ቀን ቁጥር (8):", value=8)
        sex_n = st.number_input("ፆታ ቁጥር (10):", value=10)
    with col3:
        exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር (12):", value=12)

    if st.button("አግድም መታወቂያውን አዘጋጅ"):
        if 'ocr_lines' in st.session_state:
            lines = st.session_state['ocr_lines']
            try:
                # በለካኸው ልኬት መሰረት ባክግራውንድ ላይ ማሳረፍ
                bg = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg)
                
                # የፎንት መጠኖች (በለካኸው የጽሁፍ ቁመት መሰረት)
                f_name = ImageFont.truetype(FONT_PATH, 35) # ለስም
                f_data = ImageFont.truetype(FONT_PATH, 28) # ለሌሎች
                
                # --- ትክክለኛ ቦታዎች (X, Y Coordinates) ---
                # 1. አማርኛ ስም
                draw.text((415, 110), lines[amh_n-1], font=f_name, fill="black")
                # 2. እንግሊዝኛ ስም (ከአማርኛው ስም በታች)
                draw.text((415, 160), lines[eng_n-1], font=f_name, fill="black")
                # 3. የልደት ቀን
                draw.text((415, 260), lines[dob_n-1], font=f_data, fill="black")
                # 4. ፆታ
                draw.text((415, 330), lines[sex_n-1], font=f_data, fill="black")
                # 5. የሚያበቃበት ቀን
                draw.text((415, 400), lines[exp_n-1], font=f_data, fill="black")

                # ፎቶ እና FAN መቁረጥ
                h_id, w_id = id_only.shape[:2]
                photo = id_only[int(h_id*0.05):int(h_id*0.35), int(w_id*0.15):int(w_id*0.85)]
                fan_box = id_only[int(h_id*0.80):int(h_id*0.98), int(w_id*0.05):int(w_id*0.95)]

                photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((260, 310))
                bg.paste(photo_pil, (65, 180))

                fan_pil = Image.fromarray(cv2.cvtColor(fan_box, cv2.COLOR_BGR2RGB)).resize((380, 70))
                bg.paste(fan_pil, (100, 520))

                st.image(bg, caption="በትክክለኛ ልኬት የተዘጋጀ")
                
                buf = io.BytesIO()
                bg.save(buf, format="PNG")
                st.download_button("PNG አውርድ", buf.getvalue(), "fayda_fixed.png")
            except Exception as e:
                st.error(f"ስህተት፦ {e}")
