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

st.set_page_config(page_title="Fayda Smart Scanner", layout="wide")

st.title("🪪 ፋይዳ ስማርት አንባቢ (መታወቂያውን ብቻ ለይቶ አውጪ)")

uploaded_file = st.file_uploader("የቁም መታወቂያ ምስል ይጫኑ...", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    # --- 1. በቀይ ያከበብክበትን ቦታ ብቻ መቁረጥ ---
    # በግራና በቀኝ 15%፣ ከላይ 18%፣ ከታች 15% ቆርጠን መሃሉን ብቻ እናስቀራለን
    top = int(h * 0.18)
    bottom = int(h * 0.85)
    left = int(w * 0.10)
    right = int(w * 0.90)
    
    id_only = image_cv[top:bottom, left:right]
    
    # ለተጠቃሚው የታረመውን ምስል ማሳያ
    st.subheader("🔍 OCR የሚያነበው ይሄንን ክፍል ብቻ ነው፦")
    st.image(id_only, channels="BGR", width=300)

    if st.button("መረጃውን በሰንጠረዥ አውጣ"):
        with st.spinner("ጽሁፉ እየተተነተነ ነው..."):
            # ምስሉን ለንባብ እንዲያመች ማስተካከል
            gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
            # ንባብ
            full_text = pytesseract.image_to_string(gray, lang='amh+eng')
            
            # ውጤቱን በሰንጠረዥ ማደራጀት
            lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 2]
            numbered_data = [{"ቁጥር": idx, "የተገኘ ጽሁፍ": line} for idx, line in enumerate(lines, 1)]
            
            st.subheader("📝 የንባብ ውጤት በሰንጠረዥ")
            df = pd.DataFrame(numbered_data)
            st.table(df)
            
            st.markdown("---")
            st.info("ከላይኛው ሰንጠረዥ ያዩትን መረጃ ኮፒ አድርገው እዚህ ይሙሉ")
            
            col1, col2 = st.columns(2)
            with col1:
                st.text_input("ሙሉ ስም (አማርኛና እንግሊዝኛ)፦", key="final_name")
            with col2:
                st.text_input("የትውልድ ቀን (DOB)፦", key="final_dob")

    # --- 2. መታወቂያ ማዘጋጃ ---
    if "final_name" in st.session_state and st.button("አግድም መታወቂያውን አዘጋጅ"):
        name = st.session_state.final_name
        dob = st.session_state.final_dob
        
        if name:
            with st.spinner("ምስሉ እየተዘጋጀ ነው..."):
                # ፎቶ እና FAN መቁረጥ (ከታረመው ምስል ላይ)
                h_id, w_id = id_only.shape[:2]
                photo = id_only[int(h_id*0.05):int(h_id*0.35), int(w_id*0.15):int(w_id*0.85)]
                fan_box = id_only[int(h_id*0.80):int(h_id*0.98), int(w_id*0.05):int(w_id*0.95)]

                try:
                    bg = Image.open(BG_PATH).convert("RGB")
                    draw = ImageDraw.Draw(bg)
                    font = ImageFont.truetype(FONT_PATH, 35)

                    # ፎቶ (መጠን 260x310)
                    photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((260, 310))
                    bg.paste(photo_pil, (65, 180))

                    # FAN (መጠን 380x70)
                    fan_pil = Image.fromarray(cv2.cvtColor(fan_box, cv2.COLOR_BGR2RGB)).resize((380, 70))
                    bg.paste(fan_pil, (100, 520))

                    # ጽሁፍ
                    draw.text((415, 130), name, font=font, fill="black")
                    draw.text((415, 250), dob, font=font, fill="black")

                    st.image(bg, caption="የተዘጋጀው መታወቂያ")
                    
                    buf = io.BytesIO()
                    bg.save(buf, format="PNG")
                    st.download_button("PNG አውርድ", buf.getvalue(), f"fayda_{name}.png")
                except Exception as e:
                    st.error(f"ስህተት፦ {e}")
