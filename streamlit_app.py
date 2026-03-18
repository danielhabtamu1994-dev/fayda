import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd
import json
import base64

FONT_PATH = "sabaean.ttf"
BG_PATH = "IMG_20260318_085131_234.jpg"

st.set_page_config(page_title="Fayda ID Converter", layout="wide", page_icon="🪪")

# ---- Default correct positions (calibrated to the real template) ----
DEFAULT_POS = {
    'amh_x': 620, 'amh_y': 235,   # Amharic name
    'eng_x': 620, 'eng_y': 265,   # English name
    'dob_x': 700, 'dob_y': 390,   # Date of birth
    'sex_x': 620, 'sex_y': 470,   # Sex
    'exp_x': 710, 'exp_y': 555,   # Expiry date
}

if 'pos' not in st.session_state:
    st.session_state.pos = DEFAULT_POS.copy()
if 'ocr_lines' not in st.session_state:
    st.session_state.ocr_lines = []
if 'selected_field' not in st.session_state:
    st.session_state.selected_field = 'amh'

st.title("🪪 ፋይዳ ስማርት አንባቢ")
st.caption("የቁም መታወቂያን ወደ አግድም ቅርጸት የሚቀይር መሳሪያ")

uploaded_file = st.file_uploader("📷 የቁም ፋይዳ መታወቂያ ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]
    id_only = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

    # --- Step 1: OCR ---
    with st.expander("📋 ደረጃ 1: OCR - ጽሁፍ ማውጣት", expanded=True):
        if st.button("🔍 መረጃውን አውጣ", type="primary"):
            with st.spinner("OCR እየሰራ ነው..."):
                gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
                full_text = pytesseract.image_to_string(gray, lang='amh+eng')
                lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 1]
                st.session_state.ocr_lines = lines
        
        if st.session_state.ocr_lines:
            df = pd.DataFrame([{"ቁጥር": i+1, "ጽሁፍ": l} for i, l in enumerate(st.session_state.ocr_lines)])
            st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # --- Step 2: Field Selection ---
    with st.expander("🔢 ደረጃ 2: የጽሁፍ ቁጥሮች ምረጥ", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            amh_n = st.number_input("አማርኛ ስም ቁጥር:", value=5, min_value=1)
            eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር:", value=6, min_value=1)
        with col2:
            dob_n = st.number_input("የትውልድ ቀን ቁጥር:", value=8, min_value=1)
            sex_n = st.number_input("ፆታ ቁጥር:", value=10, min_value=1)
        with col3:
            exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር:", value=12, min_value=1)

    st.divider()

    # --- Step 3: Manual Position Adjustment ---
    st.markdown("### 🕹️ ደረጃ 3: ጽሁፎችን ማስተካከያ")
    
    field_labels = {
        'amh': 'አማርኛ ስም',
        'eng': 'እንግሊዝኛ ስም', 
        'dob': 'የትውልድ ቀን',
        'sex': 'ፆታ',
        'exp': 'ቀን ማብቂያ'
    }

    def move(key, axis, delta):
        st.session_state.pos[f"{key}_{axis}"] += delta

    # Field selector
    sel = st.radio(
        "ማስተካከያ ጽሁፍ ምረጥ:",
        options=list(field_labels.keys()),
        format_func=lambda k: field_labels[k],
        horizontal=True,
        key="selected_field"
    )

    # Direction buttons with larger step options
    step = st.select_slider("የእርምጃ መጠን (px):", options=[1, 2, 5, 10, 20], value=5)
    
    col_pad, col_ctrl, col_pad2 = st.columns([2, 1, 2])
    with col_ctrl:
        # Up
        c1, c2, c3 = st.columns(3)
        with c2:
            st.button("▲", on_click=move, args=(sel, 'y', -step), key="up", use_container_width=True)
        # Left / Right
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("◄", on_click=move, args=(sel, 'x', -step), key="left", use_container_width=True)
        with c2:
            pos_display = f"({st.session_state.pos[f'{sel}_x']}, {st.session_state.pos[f'{sel}_y']})"
            st.markdown(f"<div style='text-align:center;padding:6px;font-size:11px;color:#666'>{pos_display}</div>", unsafe_allow_html=True)
        with c3:
            st.button("►", on_click=move, args=(sel, 'x', step), key="right", use_container_width=True)
        # Down
        c1, c2, c3 = st.columns(3)
        with c2:
            st.button("▼", on_click=move, args=(sel, 'y', step), key="down", use_container_width=True)

    # Fine-tune with sliders
    with st.expander("🎛️ Slider ማስተካከያ"):
        for key, label in field_labels.items():
            c1, c2 = st.columns(2)
            with c1:
                new_x = st.slider(f"{label} - X", 100, 1200, 
                                  st.session_state.pos[f'{key}_x'], key=f"sx_{key}")
                st.session_state.pos[f'{key}_x'] = new_x
            with c2:
                new_y = st.slider(f"{label} - Y", 150, 750, 
                                  st.session_state.pos[f'{key}_y'], key=f"sy_{key}")
                st.session_state.pos[f'{key}_y'] = new_y

    if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ"):
        st.session_state.pos = DEFAULT_POS.copy()
        st.rerun()

    st.divider()

    # --- Step 4: Generate Output ---
    st.markdown("### 🖼️ ደረጃ 4: መታወቂያ አዘጋጅ")
    
    if st.button("✅ መታወቂያውን አዘጋጅ / አድስ", type="primary", use_container_width=True):
        if not st.session_state.ocr_lines:
            st.warning("⚠️ መጀመሪያ OCR ሂደቱን ያካሂዱ (ደረጃ 1)")
        else:
            lines = st.session_state.ocr_lines
            max_n = len(lines)
            
            try:
                bg = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg)
                
                try:
                    f_name = ImageFont.truetype(FONT_PATH, 32)
                    f_data = ImageFont.truetype(FONT_PATH, 28)
                except:
                    f_name = ImageFont.load_default()
                    f_data = f_name

                p = st.session_state.pos
                text_color = (45, 25, 5)  # Dark brown to match template

                def safe_line(n):
                    idx = int(n) - 1
                    if 0 <= idx < len(lines):
                        return lines[idx]
                    return f"[ቁጥር {n} አልተገኘም]"

                # Write text fields
                draw.text((p['amh_x'], p['amh_y']), safe_line(amh_n), font=f_name, fill=text_color)
                draw.text((p['eng_x'], p['eng_y']), safe_line(eng_n), font=f_name, fill=text_color)
                draw.text((p['dob_x'], p['dob_y']), safe_line(dob_n), font=f_data, fill=text_color)
                draw.text((p['sex_x'], p['sex_y']), safe_line(sex_n), font=f_data, fill=text_color)
                draw.text((p['exp_x'], p['exp_y']), safe_line(exp_n), font=f_data, fill=text_color)

                # ---- Photo extraction ----
                h_id, w_id = id_only.shape[:2]
                # Photo is typically top-left of the ID content area
                photo = id_only[int(h_id*0.02):int(h_id*0.40), int(w_id*0.02):int(w_id*0.55)]
                photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB))
                # Resize to fit the photo placeholder on template (~190x240 area at x=100, y=165)
                photo_pil = photo_pil.resize((190, 240))
                bg.paste(photo_pil, (105, 165))

                # ---- FAN barcode area ----
                fan_box = id_only[int(h_id*0.82):int(h_id*0.99), int(w_id*0.05):int(w_id*0.95)]
                if fan_box.size > 0:
                    fan_pil = Image.fromarray(cv2.cvtColor(fan_box, cv2.COLOR_BGR2RGB))
                    fan_pil = fan_pil.resize((480, 65))
                    bg.paste(fan_pil, (575, 648))

                # Show result
                st.image(bg, caption="✅ የተዘጋጀ ፋይዳ መታወቂያ", use_container_width=True)
                
                # Download
                buf = io.BytesIO()
                bg.save(buf, format="PNG", dpi=(300, 300))
                st.download_button(
                    "⬇️ PNG አውርድ",
                    buf.getvalue(),
                    "fayda_landscape.png",
                    "image/png",
                    type="primary",
                    use_container_width=True
                )

            except FileNotFoundError as e:
                st.error(f"❌ ፋይሉ አልተገኘም: {e}\n\nፋይሉ '{BG_PATH}' እና '{FONT_PATH}' ከ app.py ጋር ተቀምጠዋል?")
            except IndexError as e:
                st.error(f"❌ የቁጥር ስህተት: {e}. ያስገቡት ቁጥር ከ OCR መስመሮች ቁጥር አይበልጥ።")
            except Exception as e:
                st.error(f"❌ ስህተት: {e}")

else:
    st.info("👆 ፋይዳ መታወቂያ ፎቶ ያስገቡ ለመጀመር")
    
    # Show sample of template
    try:
        bg_sample = Image.open(BG_PATH)
        st.image(bg_sample, caption="የ Template ምስል", use_container_width=True)
    except:
        st.warning("Template ምስል (1000123189.jpg) አልተገኘም")
