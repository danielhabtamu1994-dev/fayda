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

st.set_page_config(page_title="Fayda Numeric ID", layout="wide")

st.title("🪪 ፋይዳ ስማርት አንባቢ (በቁጥር መለያ)")

uploaded_file = st.file_uploader("የቁም መታወቂያውን እዚህ ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    # መታወቂያውን ብቻ ለይቶ መቁረጥ
    id_only = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

    if st.button("መረጃውን በሰንጠረዥ አውጣ"):
        with st.spinner("ጽሁፉ እየተተነተነ ነው..."):
            gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
            full_text = pytesseract.image_to_string(gray, lang='amh+eng')
            
            # ጽሁፉን በመስመር መከፋፈል
            lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 1]
            # ሰንጠረዡን ማዘጋጀት
            numbered_data = [{"ቁጥር": idx, "የተገኘ ጽሁፍ": line} for idx, line in enumerate(lines, 1)]
            
            st.session_state['ocr_lines'] = lines
            st.subheader("📝 የንባብ ውጤት ዝርዝር")
            st.table(pd.DataFrame(numbered_data))

    st.markdown("---")
    st.subheader("🔢 የቁጥሮቹን መለያ እዚህ ያስገቡ")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        amh_idx = st.number_input("አማርኛ ስም ቁጥር (ለምሳሌ 5):", min_value=1, value=5)
        eng_idx = st.number_input("እንግሊዝኛ ስም ቁጥር (ለምሳሌ 6):", min_value=1, value=6)
    with col2:
        dob_idx = st.number_input("የትውልድ ቀን ቁጥር (ለምሳሌ 8):", min_value=1, value=8)
        sex_idx = st.number_input("ፆታ ቁጥር (ለምሳሌ 10):", min_value=1, value=10)
    with col3:
        exp_idx = st.number_input("የሚያበቃበት ቀን ቁጥር (ለምሳሌ 12):", min_value=1, value=12)

    if st.button("አግድም መታወቂያውን አዘጋጅ"):
        if 'ocr_lines' in st.session_state:
            lines = st.session_state['ocr_lines']
            try:
                # መረጃዎቹን ከሰንጠረዡ ላይ በቁጥር መውሰድ (Index ስለሚጀምር -1 እናደርጋለን)
                amh_name = lines[amh_idx-1] if amh_idx <= len(lines) else ""
                eng_name = lines[eng_idx-1] if eng_idx <= len(lines) else ""
                dob = lines[dob_idx-1] if dob_idx <= len(lines) else ""
                sex = lines[sex_idx-1] if sex_idx <= len(lines) else ""
                expiry = lines[exp_idx-1] if exp_idx <= len(lines) else ""

                # ባክግራውንዱን ማዘጋጀት
                bg = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg)
                font_name = ImageFont.truetype(FONT_PATH, 35)
                font_data = ImageFont.truetype(FONT_PATH, 25)

                # --- መረጃዎችን ማሳረፍ ---
                # ስም (አማርኛ እና እንግሊዝኛ)
                full_name = f"{amh_name} {eng_name}"
                draw.text((415, 110), full_name, font=font_name, fill="black")
                
                # ሌሎች መረጃዎች
                draw.text((415, 210), f"DOB: {dob}", font=font_data, fill="black")
                draw.text((415, 270), f"Sex: {sex}", font=font_data, fill="black")
                draw.text((415, 330), f"Expiry: {expiry}", font=font_data, fill="black")

                # ፎቶ እና FAN መቁረጥ
                h_id, w_id = id_only.shape[:2]
                photo = id_only[int(h_id*0.05):int(h_id*0.35), int(w_id*0.15):int(w_id*0.85)]
                fan_box = id_only[int(h_id*0.80):int(h_id*0.98), int(w_id*0.05):int(w_id*0.95)]

                photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((260, 310))
                bg.paste(photo_pil, (65, 180))

                fan_pil = Image.fromarray(cv2.cvtColor(fan_box, cv2.COLOR_BGR2RGB)).resize((380, 70))
                bg.paste(fan_pil, (100, 520))

                st.image(bg, caption="በቁጥር መለያ የተዘጋጀ መታወቂያ")
                
                buf = io.BytesIO()
                bg.save(buf, format="PNG")
                st.download_button("PNG አውርድ", buf.getvalue(), f"fayda_{eng_name}.png")

            except Exception as e:
                st.error(f"ስህተት ተከስቷል፦ {e}. ምናልባት የመረጡት ቁጥር ከሰንጠረዡ ውጭ ሊሆን ይችላል።")
        else:
            st.warning("እባክዎ መጀመሪያ 'መረጃውን በሰንጠረዥ አውጣ' የሚለውን ይጫኑ!")
