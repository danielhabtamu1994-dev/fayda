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

st.set_page_config(page_title="Fayda Precision Mapper", layout="wide")

st.title("🪪 ፋይዳ መታወቂያ - ትክክለኛ መረጃ ማሳረፊያ")

uploaded_file = st.file_uploader("የቁም መታወቂያውን እዚህ ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]

    # 1. OCR ንባብ በሰንጠረዥ
    if st.button("መረጃውን አንብብና በሰንጠረዥ አሳይ"):
        # መታወቂያውን ብቻ መቁረጥ (ቀደም ብለን በለካነው ልክ)
        id_only = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]
        gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
        full_text = pytesseract.image_to_string(gray, lang='amh+eng')
        
        lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 1]
        numbered_data = [{"ቁጥር": idx, "የተገኘ ጽሁፍ": line} for idx, line in enumerate(lines, 1)]
        
        st.subheader("📝 የንባብ ውጤት")
        st.table(pd.DataFrame(numbered_data))
        
        st.markdown("---")
        # መረጃ መሙያ ሳጥኖች
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("ሙሉ ስም (አማርኛ እና እንግሊዝኛ)፦", key="final_name", placeholder="ለምሳሌ፦ ዳንኤል ሀብታሙ Daniel Habtamu")
        with col2:
            st.text_input("የትውልድ ቀን (DOB)፦", key="final_dob", placeholder="ለምሳሌ፦ 03/10/1994 | 2002/Jun/10")

    # 2. በለካነው ልኬት መሰረት ባክግራውንድ ላይ ማሳረፍ
    if "final_name" in st.session_state and st.button("መታወቂያውን በትክክለኛው ልኬት አዘጋጅ"):
        name = st.session_state.final_name
        dob = st.session_state.final_dob
        
        with st.spinner("በሂደት ላይ ነው..."):
            try:
                # ባክግራውንዱን መክፈት
                bg = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg)
                
                # በለካነው የጽሁፍ ቁመት መሰረት ፎንቶችን ማስተካከል
                font_name = ImageFont.truetype(FONT_PATH, 35) # ለስም
                font_data = ImageFont.truetype(FONT_PATH, 28) # ለቀን
                
                # --- በለካነው የፒክሰል ልኬት (Coordinates) መሰረት ማሳረፍ ---
                # ማሳሰቢያ፦ በአዲሱ ባክግራውንድ ስፋት መሰረት X እና Y ተስተካክለዋል
                
                # 1. ስም (አማርኛና እንግሊዝኛ) - X=415, Y=130 አካባቢ
                draw.text((415, 130), name, font=font_name, fill="black")
                
                # 2. የልደት ቀን - X=415, Y=250 አካባቢ
                draw.text((415, 250), dob, font=font_data, fill="black")
                
                # 3. ፎቶ መቁረጥ እና ማሳረፍ (Precision Crop)
                # ኦሪጅናል ምስሉ ላይ በለካነው ልክ (X=140, Y=320 አካባቢ)
                photo_crop = image_cv[int(h*0.18):int(h*0.48), int(w*0.15):int(w*0.50)]
                photo_pil = Image.fromarray(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2RGB)).resize((260, 310))
                bg.paste(photo_pil, (65, 180)) # አዲሱ ባክግራውንድ ላይ ፎቶው የሚቀመጥበት ቦታ
                
                # 4. የፋይዳ ቁጥር (FAN) ሳጥን - X=480, Y=750 አካባቢ የነበረውን መቁረጥ
                fan_crop = image_cv[int(h*0.78):int(h*0.93), int(w*0.25):int(w*0.80)]
                fan_pil = Image.fromarray(cv2.cvtColor(fan_crop, cv2.COLOR_BGR2RGB)).resize((380, 80))
                bg.paste(fan_pil, (100, 520)) # አዲሱ ባክግራውንድ ላይ FAN የሚቀመጥበት ቦታ

                st.image(bg, caption="በተፈለገው ልኬት የተዘጋጀ መታወቂያ", use_column_width=True)
                
                # ማውረጃ
                buf = io.BytesIO()
                bg.save(buf, format="PNG")
                st.download_button("የተዘጋጀውን PNG አውርድ", buf.getvalue(), f"fayda_final.png")
                
            except Exception as e:
                st.error(f"ስህተት ተከስቷል፦ {e}")
