import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd

# ፋይሎች መኖራቸውን እናረጋግጥ
FONT_PATH = "Nyala.ttf"
BG_PATH = "1000123189.jpg"

st.set_page_config(page_title="Fayda Table Reader", layout="wide")

st.title("🪪 ፋይዳ መታወቂያ አንባቢ (በሰንጠረዥ)")

uploaded_file = st.file_uploader("የቁም መታወቂያ ምስል ይጫኑ...", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    # 1. ባክግራውንድን ቆርጦ መታወቂያውን ብቻ ማስቀረት
    # ከመታወቂያው ዳርና ዳር 5% በመቁረጥ ነጩን ባክግራውንድ እናስወግዳለን
    cropped_id = image_cv[int(h*0.05):int(h*0.95), int(w*0.05):int(w*0.95)]

    if st.button("መረጃውን በሰንጠረዥ አውጣ"):
        with st.spinner("ጽሁፉ እየተተነተነ ነው..."):
            gray = cv2.cvtColor(cropped_id, cv2.COLOR_BGR2GRAY)
            # OCR ንባብ
            full_text = pytesseract.image_to_string(gray, lang='amh+eng')
            
            # ጽሁፉን በመስመር መከፋፈል እና በቁጥር መስጠት
            lines = [line.strip() for line in full_text.split('\n') if line.strip()]
            numbered_data = []
            for idx, line in enumerate(lines, 1):
                numbered_data.append({"ቁጥር": idx, "የተገኘ ጽሁፍ": line})
            
            # ውጤቱን በሰንጠረዥ ማሳየት
            st.subheader("📝 የተገኘው መረጃ ዝርዝር")
            df = pd.DataFrame(numbered_data)
            st.table(df) # ውጤቱ በሰንጠረዥ እንዲሆን
            
            st.markdown("---")
            st.subheader("✏️ መረጃውን እዚህ ይሙሉ")
            
            # ተጠቃሚው ከሰንጠረዡ ያየውን እዚህ ይሞላል
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("ሙሉ ስም (ከላይ በቁጥር 2 እና 3 ያለውን ኮፒ አድርገህ እዚህ ለጥፍ)፦", key="user_name")
            with col2:
                st.text_input("የትውልድ ቀን (ከላይ ያለውን ቁጥር አይተህ እዚህ ሙላ)፦", key="user_dob")

    # 2. መታወቂያውን ማዘጋጀት
    if "user_name" in st.session_state and st.button("መታወቂያውን አዘጋጅና አሳይ"):
        name = st.session_state.user_name
        dob = st.session_state.user_dob
        
        if name:
            with st.spinner("ምስሉ እየተዘጋጀ ነው..."):
                # ፎቶ እና FAN ሳጥን መቁረጥ (ከመታወቂያው ላይ)
                photo_crop = cropped_id[int(h*0.08):int(h*0.40), int(w*0.02):int(w*0.35)]
                fan_crop = cropped_id[int(h*0.80):int(h*0.93), int(w*0.12):int(w*0.85)]

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
                    draw.text((415, 130), name, font=font, fill="black")
                    draw.text((415, 250), dob, font=font, fill="black")

                    st.image(bg_pil, caption="የተዘጋጀው መታወቂያ")
                    
                    buf = io.BytesIO()
                    bg_pil.save(buf, format="PNG")
                    st.download_button("መታወቂያውን አውርድ", buf.getvalue(), f"{name}.png")

                except Exception as e:
                    st.error(f"ስህተት፦ {e}")
        else:
            st.warning("እባክህ መጀመሪያ ስምና ቀን ሙላ!")
