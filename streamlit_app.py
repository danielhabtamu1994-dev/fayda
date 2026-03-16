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

st.set_page_config(page_title="Fayda Manual Controller", layout="wide")

# የጽሁፎችን መጀመሪያ ቦታ በ Session State መያዝ
if 'pos' not in st.session_state:
    st.session_state.pos = {
        'amh_x': 415, 'amh_y': 110,
        'eng_x': 415, 'eng_y': 160,
        'dob_x': 415, 'dob_y': 260,
        'sex_x': 415, 'sex_y': 330,
        'exp_x': 415, 'exp_y': 400
    }

st.title("🪪 ፋይዳ ስማርት አንባቢ (በእጅ ማስተካከያ ያለው)")

uploaded_file = st.file_uploader("የቁም መታወቂያውን ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]
    id_only = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

    if st.button("1. መረጃውን በሰንጠረዥ አውጣ"):
        gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
        full_text = pytesseract.image_to_string(gray, lang='amh+eng')
        lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 1]
        st.session_state['ocr_lines'] = lines
        st.table(pd.DataFrame([{"ቁጥር": i+1, "ጽሁፍ": l} for i, l in enumerate(lines)]))

    st.markdown("---")
    
    # የቁጥር መለያዎች
    col_n1, col_n2, col_n3 = st.columns(3)
    with col_n1:
        amh_n = st.number_input("አማርኛ ስም ቁጥር:", value=5)
        eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር:", value=6)
    with col_n2:
        dob_n = st.number_input("የትውልድ ቀን ቁጥር:", value=8)
        sex_n = st.number_input("ፆታ ቁጥር:", value=10)
    with col_n3:
        exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር:", value=12)

    st.markdown("### 🕹️ ጽሁፎችን ማንቀሳቀሻ (Manual Controls)")
    
    # የማንቀሳቀሻ ቁልፎች ተግባር
    def move(label, axis, delta):
        st.session_state.pos[f"{label}_{axis}"] += delta

    # ለእያንዳንዱ ጽሁፍ አራት አቅጣጫ ቁልፎች
    labels = [("የአማርኛ ስም", "amh"), ("የእንግሊዝኛ ስም", "eng"), ("የትውልድ ቀን", "dob")]
    cols = st.columns(3)
    
    for i, (name, key) in enumerate(labels):
        with cols[i]:
            st.write(f"**{name}**")
            c1, c2, c3 = st.columns(3)
            with c2: st.button("🔼", on_click=move, args=(key, 'y', -5), key=f"up_{key}")
            with c1: st.button("◀️", on_click=move, args=(key, 'x', -5), key=f"left_{key}")
            with c3: st.button("▶️", on_click=move, args=(key, 'x', 5), key=f"right_{key}")
            with c2: st.button("🔽", on_click=move, args=(key, 'y', 5), key=f"down_{key}")

    if st.button("2. መታወቂያውን አዘጋጅ / አድስ 🔄"):
        if 'ocr_lines' in st.session_state:
            lines = st.session_state['ocr_lines']
            try:
                bg = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg)
                f_name = ImageFont.truetype(FONT_PATH, 35)
                f_data = ImageFont.truetype(FONT_PATH, 28)
                p = st.session_state.pos

                # ጽሁፎችን በ Session State ባለው ቦታ መሰረት መጻፍ
                draw.text((p['amh_x'], p['amh_y']), lines[amh_n-1], font=f_name, fill="black")
                draw.text((p['eng_x'], p['eng_y']), lines[eng_n-1], font=f_name, fill="black")
                draw.text((p['dob_x'], p['dob_y']), lines[dob_n-1], font=f_data, fill="black")
                draw.text((p['sex_x'], p['sex_y']), lines[sex_n-1], font=f_data, fill="black")
                draw.text((p['exp_x'], p['exp_y']), lines[exp_n-1], font=f_data, fill="black")

                # ፎቶ እና FAN
                h_id, w_id = id_only.shape[:2]
                photo = id_only[int(h_id*0.05):int(h_id*0.35), int(w_id*0.15):int(w_id*0.85)]
                fan_box = id_only[int(h_id*0.80):int(h_id*0.98), int(w_id*0.05):int(w_id*0.95)]
                
                photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((260, 310))
                bg.paste(photo_pil, (65, 180))
                fan_pil = Image.fromarray(cv2.cvtColor(fan_box, cv2.COLOR_BGR2RGB)).resize((380, 70))
                bg.paste(fan_pil, (100, 520))

                st.image(bg, caption="የተስተካከለ መታወቂያ")
                
                buf = io.BytesIO()
                bg.save(buf, format="PNG")
                st.download_button("PNG አውርድ", buf.getvalue(), "fayda_custom.png")
            except Exception as e:
                st.error(f"ስህተት፦ {e}")
