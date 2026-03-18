import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd
import re

FONT_AMH = "AbyssinicaSIL-Regular.ttf"   # አማርኛ ቁምፊዎች
FONT_ENG = "Inter_18pt-Medium.ttf"       # English, numbers, symbols
BG_PATH  = "1000123189.jpg"

st.set_page_config(page_title="Fayda ID Converter", layout="wide", page_icon="🪪")

# ─── Smart dual-font text rendering ───────────────────────────────────────────
def is_ethiopic(char):
    """Check if character is Ethiopic (Amharic) script."""
    cp = ord(char)
    return 0x1200 <= cp <= 0x137F or 0xAB00 <= cp <= 0xAB2F or 0x2D80 <= cp <= 0x2DDF

def draw_smart_text(draw, pos, text, size_amh=32, size_eng=28, fill=(45, 25, 5)):
    """
    ጽሁፉን ቁምፊ በቁምፊ ፈትሾ አማርኛ → AbyssinicaSIL, ሌላ → Inter ይጠቀማል።
    Mixed text (e.g. 'ወንድ / Male') ትክክል ያሳያል።
    """
    try:
        f_amh = ImageFont.truetype(FONT_AMH, size_amh)
        f_eng = ImageFont.truetype(FONT_ENG, size_eng)
    except Exception as e:
        f_amh = f_eng = ImageFont.load_default()

    x, y = pos
    # Split text into Ethiopic / non-Ethiopic segments
    segments = []
    if not text:
        return
    cur_script = 'amh' if is_ethiopic(text[0]) else 'eng'
    cur_seg = text[0]

    for ch in text[1:]:
        script = 'amh' if is_ethiopic(ch) else 'eng'
        if script == cur_script:
            cur_seg += ch
        else:
            segments.append((cur_script, cur_seg))
            cur_script = script
            cur_seg = ch
    segments.append((cur_script, cur_seg))

    for script, seg in segments:
        font = f_amh if script == 'amh' else f_eng
        draw.text((x, y), seg, font=font, fill=fill)
        # Advance x by text width
        bbox = font.getbbox(seg)
        x += bbox[2] - bbox[0]
# ──────────────────────────────────────────────────────────────────────────────

# ---- Default positions ----
DEFAULT_POS = {
    'amh_x': 620, 'amh_y': 235,
    'eng_x': 620, 'eng_y': 265,
    'dob_x': 700, 'dob_y': 390,
    'sex_x': 620, 'sex_y': 470,
    'exp_x': 710, 'exp_y': 555,
}

if 'pos' not in st.session_state:
    st.session_state.pos = DEFAULT_POS.copy()
if 'ocr_lines' not in st.session_state:
    st.session_state.ocr_lines = []
if 'selected_field' not in st.session_state:
    st.session_state.selected_field = 'amh'
if 'auto_detected' not in st.session_state:
    st.session_state.auto_detected = {}


# ─────────────────────────────────────────────
# AUTO-DETECTION: keyword labels ከታቸው ያለውን line ማግኘት
# ─────────────────────────────────────────────
def auto_detect_fields(lines):
    """
    OCR lines ውስጥ label keywords ፈልጎ ከታቻቸው ያለውን line index ይመልሳል።
    ሁሉም Fayda ID ዎች እነዚህ labels አላቸው (አማርኛ ወይም እንግሊዝኛ):
      ሙሉ ስም / Full Name  → ስሙ ከታቹ
      የትውልድ ቀን / Date of Birth → ቀኑ ከታቹ
      ፆታ / Sex → ፆታው ከታቹ
      የሚያበቃበት ቀን / Date of Expiry → ቀኑ ከታቹ
    """

    # Keywords ለፍለጋ (አማርኛ + እንግሊዝኛ, lowercase)
    LABEL_KEYWORDS = {
        'full_name':   ['full name', 'ሙሉ ስም', 'fullname'],
        'date_birth':  ['date of birth', 'date of berth', 'የትውልድ ቀን', 'dateofbirth'],
        'sex':         ['sex', 'ፆታ', ' ፆታ'],
        'date_expiry': ['date of expiry', 'date of expire', 'የሚያበቃበት ቀን', 'expiry'],
    }

    found = {}  # key → line index (1-based)

    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        for field, keywords in LABEL_KEYWORDS.items():
            if field in found:
                continue  # already found
            for kw in keywords:
                if kw in line_lower:
                    # ከዚህ label ከታቹ ያለው line (i+2, 1-based)
                    next_idx = i + 2  # 1-based index of next line
                    if next_idx <= len(lines):
                        found[field] = next_idx
                    break

    return found


st.title("🪪 ፋይዳ ስማርት አንባቢ")
st.caption("የቁም መታወቂያን ወደ አግድም ቅርጸት የሚቀይር መሳሪያ")

uploaded_file = st.file_uploader("📷 የቁም ፋይዳ መታወቂያ ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w = image_cv.shape[:2]
    id_only = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

    # ══════════════════════════════════════════
    # ደረጃ 1: OCR
    # ══════════════════════════════════════════
    with st.expander("📋 ደረጃ 1: OCR — ጽሁፍ ማውጣት", expanded=True):
        if st.button("🔍 መረጃውን አውጣ", type="primary"):
            with st.spinner("OCR እየሰራ ነው..."):
                gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
                full_text = pytesseract.image_to_string(gray, lang='amh+eng')
                lines = [line.strip() for line in full_text.split('\n') if len(line.strip()) > 1]
                st.session_state.ocr_lines = lines

                # Auto-detect ወዲያው
                detected = auto_detect_fields(lines)
                st.session_state.auto_detected = detected

        if st.session_state.ocr_lines:
            lines = st.session_state.ocr_lines
            detected = st.session_state.auto_detected

            # ጠረጴዛ — detected fields highlight
            rows = []
            detected_indices = set(detected.values())
            for i, l in enumerate(lines):
                tag = ""
                for field, idx in detected.items():
                    if idx == i + 1:
                        tag = {
                            'full_name': '← ስም',
                            'date_birth': '← ልደት ቀን',
                            'sex': '← ፆታ',
                            'date_expiry': '← ቀን ማብቂያ',
                        }.get(field, '')
                rows.append({"ቁጥር": i+1, "ጽሁፍ": l, "": tag})

            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            if detected:
                st.success(f"✅ Auto-detection ተሳካ: {len(detected)}/4 fields ተገኙ")
            else:
                st.warning("⚠️ Auto-detection አልተሳካም — እባክዎ ቁጥሮቹን በራስዎ ይምረጡ")

    st.divider()

    # ══════════════════════════════════════════
    # ደረጃ 2: Field Numbers — auto ወይም manual
    # ══════════════════════════════════════════
    with st.expander("🔢 ደረጃ 2: የጽሁፍ ቁጥሮች", expanded=True):
        detected = st.session_state.auto_detected

        # Auto values — fallback to defaults if not detected
        def det(key, default):
            return int(detected.get(key, default))

        # Amharic name = same line as full_name (or +1 if bilingual — try both)
        # The label line is "ሙሉ ስም | Full Name", next line is Amharic name,
        # line after that is English name
        fn_idx = detected.get('full_name', None)

        col1, col2, col3 = st.columns(3)
        with col1:
            amh_default = fn_idx if fn_idx else 5
            amh_n = st.number_input("አማርኛ ስም ቁጥር:", value=amh_default, min_value=1)

            eng_default = (fn_idx + 1) if fn_idx else 6
            eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር:", value=eng_default, min_value=1)

        with col2:
            dob_n = st.number_input("የትውልድ ቀን ቁጥር:", value=det('date_birth', 8), min_value=1)
            sex_n = st.number_input("ፆታ ቁጥር:", value=det('sex', 10), min_value=1)

        with col3:
            exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር:", value=det('date_expiry', 12), min_value=1)

        # Show preview of selected lines
        if st.session_state.ocr_lines:
            lines = st.session_state.ocr_lines
            def pv(n):
                idx = int(n) - 1
                return lines[idx] if 0 <= idx < len(lines) else "—"

            st.markdown("**ቅድመ ዕይታ:**")
            preview_data = {
                "አማርኛ ስም": pv(amh_n),
                "እንግሊዝኛ ስም": pv(eng_n),
                "የትውልድ ቀን": pv(dob_n),
                "ፆታ": pv(sex_n),
                "ቀን ማብቂያ": pv(exp_n),
            }
            for label, val in preview_data.items():
                st.markdown(f"- **{label}:** `{val}`")

    st.divider()

    # ══════════════════════════════════════════
    # ደረጃ 3: Manual Position Adjustment
    # ══════════════════════════════════════════
    st.markdown("### 🕹️ ደረጃ 3: ጽሁፎችን ማስተካከያ")

    field_labels = {
        'amh': 'አማርኛ ስም',
        'eng': 'እንግሊዝኛ ስም',
        'dob': 'የትውልድ ቀን',
        'sex': 'ፆታ',
        'exp': 'ቀን ማብቂያ',
    }

    def move(key, axis, delta):
        st.session_state.pos[f"{key}_{axis}"] += delta

    sel = st.radio(
        "ማስተካከያ ጽሁፍ ምረጥ:",
        options=list(field_labels.keys()),
        format_func=lambda k: field_labels[k],
        horizontal=True,
        key="selected_field"
    )

    step = st.select_slider("የእርምጃ መጠን (px):", options=[1, 2, 5, 10, 20], value=5)

    col_pad, col_ctrl, col_pad2 = st.columns([2, 1, 2])
    with col_ctrl:
        c1, c2, c3 = st.columns(3)
        with c2:
            st.button("▲", on_click=move, args=(sel, 'y', -step), key="up", use_container_width=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.button("◄", on_click=move, args=(sel, 'x', -step), key="left", use_container_width=True)
        with c2:
            pos_display = f"({st.session_state.pos[f'{sel}_x']}, {st.session_state.pos[f'{sel}_y']})"
            st.markdown(f"<div style='text-align:center;padding:6px;font-size:11px;color:#888'>{pos_display}</div>", unsafe_allow_html=True)
        with c3:
            st.button("►", on_click=move, args=(sel, 'x', step), key="right", use_container_width=True)
        c1, c2, c3 = st.columns(3)
        with c2:
            st.button("▼", on_click=move, args=(sel, 'y', step), key="down", use_container_width=True)

    with st.expander("🎛️ Slider ማስተካከያ (ሁሉም fields)"):
        for key, label in field_labels.items():
            c1, c2 = st.columns(2)
            with c1:
                new_x = st.slider(f"{label} X", 100, 1200,
                                  st.session_state.pos[f'{key}_x'], key=f"sx_{key}")
                st.session_state.pos[f'{key}_x'] = new_x
            with c2:
                new_y = st.slider(f"{label} Y", 150, 780,
                                  st.session_state.pos[f'{key}_y'], key=f"sy_{key}")
                st.session_state.pos[f'{key}_y'] = new_y

    if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ"):
        st.session_state.pos = DEFAULT_POS.copy()
        st.rerun()

    st.divider()

    # ══════════════════════════════════════════
    # ደረጃ 4: Generate
    # ══════════════════════════════════════════
    st.markdown("### 🖼️ ደረጃ 4: መታወቂያ አዘጋጅ")

    if st.button("✅ መታወቂያውን አዘጋጅ / አድስ", type="primary", use_container_width=True):
        if not st.session_state.ocr_lines:
            st.warning("⚠️ መጀመሪያ OCR ሂደቱን ያካሂዱ (ደረጃ 1)")
        else:
            lines = st.session_state.ocr_lines
            try:
                bg = Image.open(BG_PATH).convert("RGB")
                draw = ImageDraw.Draw(bg)

                try:
                    f_name = ImageFont.truetype(FONT_AMH, 32)
                    f_data = ImageFont.truetype(FONT_ENG, 28)
                except Exception as fe:
                    st.warning(f"ፎንት ሊጫን አልቻለም ({fe}) — ነባሪ ፎንት ይጠቀማል")
                    f_name = ImageFont.load_default()
                    f_data = f_name

                p = st.session_state.pos
                text_color = (45, 25, 5)

                def safe_line(n):
                    idx = int(n) - 1
                    return lines[idx] if 0 <= idx < len(lines) else f"[{n} አልተገኘም]"

                draw_smart_text(draw, (p['amh_x'], p['amh_y']), safe_line(amh_n), size_amh=32, size_eng=28, fill=text_color)
                draw_smart_text(draw, (p['eng_x'], p['eng_y']), safe_line(eng_n), size_amh=32, size_eng=28, fill=text_color)
                draw_smart_text(draw, (p['dob_x'], p['dob_y']), safe_line(dob_n), size_amh=28, size_eng=26, fill=text_color)
                draw_smart_text(draw, (p['sex_x'], p['sex_y']), safe_line(sex_n), size_amh=28, size_eng=26, fill=text_color)
                draw_smart_text(draw, (p['exp_x'], p['exp_y']), safe_line(exp_n), size_amh=28, size_eng=26, fill=text_color)

                # Photo
                h_id, w_id = id_only.shape[:2]
                photo = id_only[int(h_id*0.02):int(h_id*0.40), int(w_id*0.02):int(w_id*0.55)]
                photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((190, 240))
                bg.paste(photo_pil, (105, 165))

                # FAN
                fan_box = id_only[int(h_id*0.82):int(h_id*0.99), int(w_id*0.05):int(w_id*0.95)]
                if fan_box.size > 0:
                    fan_pil = Image.fromarray(cv2.cvtColor(fan_box, cv2.COLOR_BGR2RGB)).resize((480, 65))
                    bg.paste(fan_pil, (575, 648))

                st.image(bg, caption="✅ የተዘጋጀ ፋይዳ መታወቂያ", use_container_width=True)

                buf = io.BytesIO()
                bg.save(buf, format="PNG")
                st.download_button("⬇️ PNG አውርድ", buf.getvalue(),
                                   "fayda_landscape.png", "image/png",
                                   type="primary", use_container_width=True)

            except FileNotFoundError as e:
                st.error(f"❌ ፋይሉ አልተገኘም: {e}")
            except Exception as e:
                st.error(f"❌ ስህተት: {e}")

else:
    st.info("👆 ፋይዳ መታወቂያ ፎቶ ያስገቡ ለመጀመር")
    try:
        bg_sample = Image.open(BG_PATH)
        st.image(bg_sample, caption="Template", use_container_width=True)
    except:
        st.warning("Template ምስል (1000123189.jpg) አልተገኘም")
