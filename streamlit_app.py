import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd
import requests
import json

FONT_AMH    = "AbyssinicaSIL-Regular.ttf"
FONT_ENG    = "Inter_18pt-Bold.ttf"
BG_PATH      = "20260319_215211.jpg"
BG_PATH_BACK = "20260319_211337.jpg"
FIREBASE_URL = "https://fayda-b365f-default-rtdb.firebaseio.com/settings.json"

st.set_page_config(page_title="Fayda ID Converter", layout="wide", page_icon="🪪")

# ══════════════════════════════════════════════════════════════════
# Firebase helpers
# ══════════════════════════════════════════════════════════════════
def firebase_save(data: dict):
    try:
        r = requests.put(FIREBASE_URL, json=data, timeout=8)
        return r.status_code == 200
    except Exception as e:
        st.error(f"Firebase save error: {e}")
        return False

def firebase_load() -> dict | None:
    try:
        r = requests.get(FIREBASE_URL, timeout=8)
        if r.status_code == 200 and r.text != "null":
            return r.json()
    except Exception as e:
        st.warning(f"Firebase load error: {e}")
    return None

# ══════════════════════════════════════════════════════════════════
# Smart dual-font rendering
# ══════════════════════════════════════════════════════════════════
def is_ethiopic(char):
    cp = ord(char)
    return 0x1200 <= cp <= 0x137F or 0xAB00 <= cp <= 0xAB2F or 0x2D80 <= cp <= 0x2DDF

def draw_smart_text(draw, pos, text, size_amh=32, size_eng=28, fill=(45, 25, 5)):
    try:
        f_amh = ImageFont.truetype(FONT_AMH, size_amh)
        f_eng = ImageFont.truetype(FONT_ENG, size_eng)
    except:
        f_amh = f_eng = ImageFont.load_default()

    x, y = pos
    if not text:
        return
    cur_script = 'amh' if is_ethiopic(text[0]) else 'eng'
    cur_seg = text[0]
    segments = []
    for ch in text[1:]:
        script = 'amh' if is_ethiopic(ch) else 'eng'
        if script == cur_script:
            cur_seg += ch
        else:
            segments.append((cur_script, cur_seg))
            cur_script, cur_seg = script, ch
    segments.append((cur_script, cur_seg))

    for script, seg in segments:
        font = f_amh if script == 'amh' else f_eng
        draw.text((x, y), seg, font=font, fill=fill)
        bbox = font.getbbox(seg)
        x += bbox[2] - bbox[0]

# ══════════════════════════════════════════════════════════════════
# Defaults — Front
# ══════════════════════════════════════════════════════════════════
DEFAULT_SETTINGS = {
    'pos': {
        'amh_x': 620, 'amh_y': 235,
        'eng_x': 620, 'eng_y': 268,
        'dob_x': 700, 'dob_y': 390,
        'sex_x': 620, 'sex_y': 470,
        'exp_x': 710, 'exp_y': 555,
    },
    'size': {
        'amh': 32, 'eng': 32,
        'dob': 28, 'sex': 28, 'exp': 28,
    }
}

# Defaults — Back
DEFAULT_SETTINGS_BACK = {
    'pos': {
        'amh_x': 620, 'amh_y': 235,
        'eng_x': 620, 'eng_y': 268,
        'dob_x': 700, 'dob_y': 390,
        'sex_x': 620, 'sex_y': 470,
        'exp_x': 710, 'exp_y': 555,
    },
    'size': {
        'amh': 32, 'eng': 32,
        'dob': 28, 'sex': 28, 'exp': 28,
    }
}

# ── Session State init ──────────────────────────────────────────
def init_state():
    # Front settings
    if 'pos' not in st.session_state:
        st.session_state.pos  = DEFAULT_SETTINGS['pos'].copy()
    if 'size' not in st.session_state:
        st.session_state.size = DEFAULT_SETTINGS['size'].copy()
    # Back settings
    if 'pos_back' not in st.session_state:
        st.session_state.pos_back  = DEFAULT_SETTINGS_BACK['pos'].copy()
    if 'size_back' not in st.session_state:
        st.session_state.size_back = DEFAULT_SETTINGS_BACK['size'].copy()
    # OCR / detection
    if 'ocr_lines' not in st.session_state:
        st.session_state.ocr_lines = []
    if 'auto_detected' not in st.session_state:
        st.session_state.auto_detected = {}
    if 'selected_field' not in st.session_state:
        st.session_state.selected_field = 'amh'
    if 'selected_field_back' not in st.session_state:
        st.session_state.selected_field_back = 'amh'
    if 'firebase_loaded' not in st.session_state:
        st.session_state.firebase_loaded = False

init_state()

# ── Load from Firebase once on first run ───────────────────────
if not st.session_state.firebase_loaded:
    saved = firebase_load()
    if saved:
        if 'pos' in saved:
            st.session_state.pos  = {**DEFAULT_SETTINGS['pos'],  **saved['pos']}
        if 'size' in saved:
            st.session_state.size = {**DEFAULT_SETTINGS['size'], **saved['size']}
        if 'pos_back' in saved:
            st.session_state.pos_back  = {**DEFAULT_SETTINGS_BACK['pos'],  **saved['pos_back']}
        if 'size_back' in saved:
            st.session_state.size_back = {**DEFAULT_SETTINGS_BACK['size'], **saved['size_back']}
    st.session_state.firebase_loaded = True

# ══════════════════════════════════════════════════════════════════
# Auto-detection
# ══════════════════════════════════════════════════════════════════
def auto_detect_fields(lines):
    LABEL_KEYWORDS = {
        'full_name':   ['full name', 'ሙሉ ስም', 'fullname'],
        'date_birth':  ['date of birth', 'date of berth', 'የትውልድ ቀን'],
        'sex':         ['sex', 'ፆታ'],
        'date_expiry': ['date of expiry', 'date of expire', 'የሚያበቃበት ቀን', 'expiry'],
    }
    found = {}
    for i, line in enumerate(lines):
        ll = line.lower().strip()
        for field, kws in LABEL_KEYWORDS.items():
            if field in found:
                continue
            for kw in kws:
                if kw in ll:
                    nxt = i + 2
                    if nxt <= len(lines):
                        found[field] = nxt
                    break
    return found

# ══════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════
st.title("🪪 ፋይዳ ስማርት አንባቢ")
st.caption("የቁም መታወቂያን ወደ አግድም ቅርጸት የሚቀይር መሳሪያ")

# ── Firebase settings bar ───────────────────────────────────────
with st.container():
    col_fb1, col_fb2, col_fb3 = st.columns([3, 1, 1])
    with col_fb1:
        st.caption(f"🔗 Firebase: `{FIREBASE_URL}`")
    with col_fb2:
        if st.button("💾 Settings Save", type="primary", use_container_width=True):
            payload = {
                'pos':       st.session_state.pos,
                'size':      st.session_state.size,
                'pos_back':  st.session_state.pos_back,
                'size_back': st.session_state.size_back,
            }
            if firebase_save(payload):
                st.success("✅ Saved!")
            else:
                st.error("❌ Failed")
    with col_fb3:
        if st.button("🔄 Settings Load", use_container_width=True):
            saved = firebase_load()
            if saved:
                if 'pos'       in saved: st.session_state.pos       = {**DEFAULT_SETTINGS['pos'],      **saved['pos']}
                if 'size'      in saved: st.session_state.size      = {**DEFAULT_SETTINGS['size'],     **saved['size']}
                if 'pos_back'  in saved: st.session_state.pos_back  = {**DEFAULT_SETTINGS_BACK['pos'], **saved['pos_back']}
                if 'size_back' in saved: st.session_state.size_back = {**DEFAULT_SETTINGS_BACK['size'],**saved['size_back']}
                st.success("✅ Loaded!")
                st.rerun()
            else:
                st.warning("Firebase ላይ settings አልተገኘም")

st.divider()

# ══════════════════════════════════════════════════════════════════
# 3 Upload Boxes
# ══════════════════════════════════════════════════════════════════
up_col1, up_col2, up_col3 = st.columns(3)

with up_col1:
    st.markdown("#### 🪪 ID Front")
    uploaded_file = st.file_uploader(
        "ID Front ምስል ያስገቡ",
        type=['jpg', 'jpeg', 'png'],
        key="upload_front",
        label_visibility="collapsed"
    )

with up_col2:
    st.markdown("#### 🪪 ID Back")
    uploaded_back = st.file_uploader(
        "ID Back ምስል ያስገቡ",
        type=['jpg', 'jpeg', 'png'],
        key="upload_back",
        label_visibility="collapsed"
    )

with up_col3:
    st.markdown("#### 📷 Profile & QR Code")
    uploaded_profile = st.file_uploader(
        "Profile & QR Code ምስል ያስገቡ",
        type=['jpg', 'jpeg', 'png'],
        key="upload_profile",
        label_visibility="collapsed"
    )

st.divider()

# ══════════════════════════════════════════════════════════════════
# Settings Tabs — Front / Back
# ══════════════════════════════════════════════════════════════════
tab_front, tab_back = st.tabs(["🔵 Front Settings", "🟠 Back Settings"])

# ─────────────────────────────────────────────────────────────────
# FRONT TAB  (unchanged original logic)
# ─────────────────────────────────────────────────────────────────
with tab_front:
    if uploaded_file:
        file_bytes = uploaded_file.read()
        image_cv   = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
        h, w       = image_cv.shape[:2]
        id_only    = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

        # ── ደረጃ 1: OCR ────────────────────────────────────────────
        with st.expander("📋 ደረጃ 1: OCR — ጽሁፍ ማውጣት", expanded=True):
            if st.button("🔍 መረጃውን አውጣ", type="primary", key="ocr_front"):
                with st.spinner("OCR እየሰራ ነው..."):
                    gray      = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)
                    full_text = pytesseract.image_to_string(gray, lang='amh+eng')
                    lines     = [l.strip() for l in full_text.split('\n') if len(l.strip()) > 1]
                    st.session_state.ocr_lines    = lines
                    st.session_state.auto_detected = auto_detect_fields(lines)

            if st.session_state.ocr_lines:
                lines    = st.session_state.ocr_lines
                detected = st.session_state.auto_detected
                tag_map  = {'full_name':'← ስም','date_birth':'← ልደት ቀን','sex':'← ፆታ','date_expiry':'← ቀን ማብቂያ'}
                rows = [{"ቁጥር": i+1, "ጽሁፍ": l,
                         "": next((tag_map[f] for f,idx in detected.items() if idx==i+1), "")}
                        for i, l in enumerate(lines)]
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                if detected:
                    st.success(f"✅ Auto-detection ተሳካ: {len(detected)}/4 fields")
                else:
                    st.warning("⚠️ Auto-detection አልተሳካም — ቁጥሮቹን በራስዎ ይምረጡ")

        st.divider()

        # ── ደረጃ 2: Field Numbers ──────────────────────────────────
        with st.expander("🔢 ደረጃ 2: የጽሁፍ ቁጥሮች", expanded=True):
            detected = st.session_state.auto_detected
            def det(key, default): return int(detected.get(key, default))
            fn_idx = detected.get('full_name', None)

            c1, c2, c3 = st.columns(3)
            with c1:
                amh_n = st.number_input("አማርኛ ስም ቁጥር:",     value=fn_idx if fn_idx else 5,               min_value=1, key="amh_n_f")
                eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር:",   value=(fn_idx+1) if fn_idx else 6,            min_value=1, key="eng_n_f")
            with c2:
                dob_n = st.number_input("የትውልድ ቀን ቁጥር:",    value=det('date_birth', 8),                    min_value=1, key="dob_n_f")
                sex_n = st.number_input("ፆታ ቁጥር:",           value=det('sex', 10),                          min_value=1, key="sex_n_f")
            with c3:
                exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር:",  value=det('date_expiry', 12),                  min_value=1, key="exp_n_f")

            if st.session_state.ocr_lines:
                lines = st.session_state.ocr_lines
                def pv(n):
                    idx = int(n)-1
                    return lines[idx] if 0 <= idx < len(lines) else "—"
                st.markdown("**ቅድመ ዕይታ:**")
                for lbl, n in [("አማርኛ ስም", amh_n),("እንግሊዝኛ ስም", eng_n),
                               ("የትውልድ ቀን", dob_n),("ፆታ", sex_n),("ቀን ማብቂያ", exp_n)]:
                    st.markdown(f"- **{lbl}:** `{pv(n)}`")

        st.divider()

        # ── ደረጃ 3: Position + Size controls ──────────────────────
        st.markdown("### 🕹️ ደረጃ 3: ቦታ እና ፊደል መጠን ማስተካከያ")

        field_labels = {
            'amh': 'አማርኛ ስም',
            'eng': 'እንግሊዝኛ ስም',
            'dob': 'የትውልድ ቀን',
            'sex': 'ፆታ',
            'exp': 'ቀን ማብቂያ',
        }

        def move(key, axis, delta):
            st.session_state.pos[f"{key}_{axis}"] += delta
        def resize(key, delta):
            st.session_state.size[key] = max(10, st.session_state.size[key] + delta)

        sel = st.radio(
            "ማስተካከያ ጽሁፍ ምረጥ:",
            options=list(field_labels.keys()),
            format_func=lambda k: field_labels[k],
            horizontal=True,
            key="selected_field"
        )

        step = st.select_slider("የቦታ እርምጃ (px):", options=[1, 2, 5, 10, 20], value=5, key="step_front")

        col_move, col_size = st.columns([1, 1])

        with col_move:
            st.markdown("**📍 ቦታ ማንቀሳቀሻ**")
            col_pad, col_ctrl, col_pad2 = st.columns([1, 2, 1])
            with col_ctrl:
                r1c1, r1c2, r1c3 = st.columns(3)
                with r1c2:
                    st.button("▲", on_click=move, args=(sel,'y',-step), key="up_f",    use_container_width=True)
                r2c1, r2c2, r2c3 = st.columns(3)
                with r2c1:
                    st.button("◄", on_click=move, args=(sel,'x',-step), key="left_f",  use_container_width=True)
                with r2c2:
                    pos_txt = f"({st.session_state.pos[f'{sel}_x']}, {st.session_state.pos[f'{sel}_y']})"
                    st.markdown(f"<div style='text-align:center;font-size:11px;color:#888;padding:6px'>{pos_txt}</div>",
                                unsafe_allow_html=True)
                with r2c3:
                    st.button("►", on_click=move, args=(sel,'x', step), key="right_f", use_container_width=True)
                r3c1, r3c2, r3c3 = st.columns(3)
                with r3c2:
                    st.button("▼", on_click=move, args=(sel,'y', step), key="down_f",  use_container_width=True)

        with col_size:
            st.markdown("**🔡 ፊደል መጠን**")
            cur_size = st.session_state.size[sel]
            sc1, sc2, sc3 = st.columns([1, 2, 1])
            with sc1:
                st.button("➖", on_click=resize, args=(sel, -1), key="sz_minus_f", use_container_width=True)
            with sc2:
                st.markdown(
                    f"<div style='text-align:center;font-size:28px;font-weight:bold;"
                    f"padding:4px;color:#333'>{cur_size}px</div>",
                    unsafe_allow_html=True
                )
            with sc3:
                st.button("➕", on_click=resize, args=(sel,  1), key="sz_plus_f",  use_container_width=True)

            new_size = st.slider(f"", 10, 72, cur_size, key=f"sz_sl_f_{sel}")
            if new_size != cur_size:
                st.session_state.size[sel] = new_size

        with st.expander("🎛️ Slider ማስተካከያ (ሁሉም fields)"):
            for key, label in field_labels.items():
                st.markdown(f"**{label}**")
                ca, cb, cc = st.columns(3)
                with ca:
                    nx = st.slider(f"X", 100, 1200, st.session_state.pos[f'{key}_x'], key=f"sx_f_{key}")
                    st.session_state.pos[f'{key}_x'] = nx
                with cb:
                    ny = st.slider(f"Y", 150, 780,  st.session_state.pos[f'{key}_y'], key=f"sy_f_{key}")
                    st.session_state.pos[f'{key}_y'] = ny
                with cc:
                    ns = st.slider(f"Size", 10, 72, st.session_state.size[key],        key=f"ss_f_{key}")
                    st.session_state.size[key] = ns

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ", use_container_width=True, key="reset_front"):
                st.session_state.pos  = DEFAULT_SETTINGS['pos'].copy()
                st.session_state.size = DEFAULT_SETTINGS['size'].copy()
                st.rerun()
        with col_r2:
            if st.button("💾 አሁን Save (Firebase)", use_container_width=True, key="save_front"):
                payload = {
                    'pos':       st.session_state.pos,
                    'size':      st.session_state.size,
                    'pos_back':  st.session_state.pos_back,
                    'size_back': st.session_state.size_back,
                }
                if firebase_save(payload):
                    st.success("✅ Settings saved!")
                else:
                    st.error("❌ Save failed")

        st.divider()

        # ── ደረጃ 4: Generate ───────────────────────────────────────
        st.markdown("### 🖼️ ደረጃ 4: መታወቂያ አዘጋጅ")

        if st.button("✅ መታወቂያውን አዘጋጅ / አድስ", type="primary", use_container_width=True, key="gen_front"):
            if not st.session_state.ocr_lines:
                st.warning("⚠️ መጀመሪያ OCR ሂደቱን ያካሂዱ (ደረጃ 1)")
            else:
                lines = st.session_state.ocr_lines
                try:
                    bg   = Image.open(BG_PATH).convert("RGB")
                    draw = ImageDraw.Draw(bg)
                    p    = st.session_state.pos
                    sz   = st.session_state.size
                    tc   = (45, 25, 5)

                    def safe_line(n):
                        idx = int(n) - 1
                        return lines[idx] if 0 <= idx < len(lines) else f"[{n} አልተገኘም]"

                    draw_smart_text(draw, (p['amh_x'], p['amh_y']), safe_line(amh_n), sz['amh'], sz['amh'], tc)
                    draw_smart_text(draw, (p['eng_x'], p['eng_y']), safe_line(eng_n), sz['eng'], sz['eng'], tc)
                    draw_smart_text(draw, (p['dob_x'], p['dob_y']), safe_line(dob_n), sz['dob'], sz['dob'], tc)
                    draw_smart_text(draw, (p['sex_x'], p['sex_y']), safe_line(sex_n), sz['sex'], sz['sex'], tc)
                    draw_smart_text(draw, (p['exp_x'], p['exp_y']), safe_line(exp_n), sz['exp'], sz['exp'], tc)

                    # Photo
                    h_id, w_id = id_only.shape[:2]
                    photo = id_only[int(h_id*0.02):int(h_id*0.40), int(w_id*0.02):int(w_id*0.55)]
                    bg.paste(Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((190, 240)), (105, 165))

                    # FAN
                    fan = id_only[int(h_id*0.82):int(h_id*0.99), int(w_id*0.05):int(w_id*0.95)]
                    if fan.size > 0:
                        bg.paste(Image.fromarray(cv2.cvtColor(fan, cv2.COLOR_BGR2RGB)).resize((480, 65)), (575, 648))

                    st.image(bg, caption="✅ የተዘጋጀ ፋይዳ መታወቂያ (Front)", use_container_width=True)

                    buf = io.BytesIO()
                    bg.save(buf, format="PNG")
                    st.download_button("⬇️ PNG አውርድ", buf.getvalue(),
                                       "fayda_landscape_front.png", "image/png",
                                       type="primary", use_container_width=True)

                except FileNotFoundError as e:
                    st.error(f"❌ ፋይሉ አልተገኘም: {e}")
                except Exception as e:
                    st.error(f"❌ ስህተት: {e}")
    else:
        st.info("👆 ID Front ፋይዳ መታወቂያ ፎቶ ያስገቡ ለመጀመር")
        try:
            st.image(Image.open(BG_PATH), caption="Template", use_container_width=True)
        except:
            st.warning("Template ምስል አልተገኘም")


# ─────────────────────────────────────────────────────────────────
# BACK TAB  (same position/size controls style as Front)
# ─────────────────────────────────────────────────────────────────
with tab_back:
    if uploaded_back:
        st.markdown("### 🕹️ Back — ቦታ እና ፊደል መጠን ማስተካከያ")

        field_labels_back = {
            'amh': 'አማርኛ ስም',
            'eng': 'እንግሊዝኛ ስም',
            'dob': 'የትውልድ ቀን',
            'sex': 'ፆታ',
            'exp': 'ቀን ማብቂያ',
        }

        def move_back(key, axis, delta):
            st.session_state.pos_back[f"{key}_{axis}"] += delta
        def resize_back(key, delta):
            st.session_state.size_back[key] = max(10, st.session_state.size_back[key] + delta)

        sel_back = st.radio(
            "ማስተካከያ ጽሁፍ ምረጥ (Back):",
            options=list(field_labels_back.keys()),
            format_func=lambda k: field_labels_back[k],
            horizontal=True,
            key="selected_field_back"
        )

        step_back = st.select_slider("የቦታ እርምጃ (px):", options=[1, 2, 5, 10, 20], value=5, key="step_back")

        col_move_b, col_size_b = st.columns([1, 1])

        with col_move_b:
            st.markdown("**📍 ቦታ ማንቀሳቀሻ**")
            col_pad_b, col_ctrl_b, col_pad2_b = st.columns([1, 2, 1])
            with col_ctrl_b:
                rb1c1, rb1c2, rb1c3 = st.columns(3)
                with rb1c2:
                    st.button("▲", on_click=move_back, args=(sel_back,'y',-step_back), key="up_b",    use_container_width=True)
                rb2c1, rb2c2, rb2c3 = st.columns(3)
                with rb2c1:
                    st.button("◄", on_click=move_back, args=(sel_back,'x',-step_back), key="left_b",  use_container_width=True)
                with rb2c2:
                    pos_txt_b = f"({st.session_state.pos_back[f'{sel_back}_x']}, {st.session_state.pos_back[f'{sel_back}_y']})"
                    st.markdown(f"<div style='text-align:center;font-size:11px;color:#888;padding:6px'>{pos_txt_b}</div>",
                                unsafe_allow_html=True)
                with rb2c3:
                    st.button("►", on_click=move_back, args=(sel_back,'x', step_back), key="right_b", use_container_width=True)
                rb3c1, rb3c2, rb3c3 = st.columns(3)
                with rb3c2:
                    st.button("▼", on_click=move_back, args=(sel_back,'y', step_back), key="down_b",  use_container_width=True)

        with col_size_b:
            st.markdown("**🔡 ፊደል መጠን**")
            cur_size_b = st.session_state.size_back[sel_back]
            sb1, sb2, sb3 = st.columns([1, 2, 1])
            with sb1:
                st.button("➖", on_click=resize_back, args=(sel_back, -1), key="sz_minus_b", use_container_width=True)
            with sb2:
                st.markdown(
                    f"<div style='text-align:center;font-size:28px;font-weight:bold;"
                    f"padding:4px;color:#333'>{cur_size_b}px</div>",
                    unsafe_allow_html=True
                )
            with sb3:
                st.button("➕", on_click=resize_back, args=(sel_back, 1), key="sz_plus_b",  use_container_width=True)

            new_size_b = st.slider("", 10, 72, cur_size_b, key=f"sz_sl_b_{sel_back}")
            if new_size_b != cur_size_b:
                st.session_state.size_back[sel_back] = new_size_b

        with st.expander("🎛️ Slider ማስተካከያ (ሁሉም fields — Back)"):
            for key, label in field_labels_back.items():
                st.markdown(f"**{label}**")
                ca, cb, cc = st.columns(3)
                with ca:
                    nx = st.slider(f"X", 100, 1200, st.session_state.pos_back[f'{key}_x'], key=f"sx_b_{key}")
                    st.session_state.pos_back[f'{key}_x'] = nx
                with cb:
                    ny = st.slider(f"Y", 150, 780,  st.session_state.pos_back[f'{key}_y'], key=f"sy_b_{key}")
                    st.session_state.pos_back[f'{key}_y'] = ny
                with cc:
                    ns = st.slider(f"Size", 10, 72, st.session_state.size_back[key], key=f"ss_b_{key}")
                    st.session_state.size_back[key] = ns

        col_rb1, col_rb2 = st.columns(2)
        with col_rb1:
            if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ (Back)", use_container_width=True, key="reset_back"):
                st.session_state.pos_back  = DEFAULT_SETTINGS_BACK['pos'].copy()
                st.session_state.size_back = DEFAULT_SETTINGS_BACK['size'].copy()
                st.rerun()
        with col_rb2:
            if st.button("💾 አሁን Save (Firebase)", use_container_width=True, key="save_back"):
                payload = {
                    'pos':       st.session_state.pos,
                    'size':      st.session_state.size,
                    'pos_back':  st.session_state.pos_back,
                    'size_back': st.session_state.size_back,
                }
                if firebase_save(payload):
                    st.success("✅ Settings saved!")
                else:
                    st.error("❌ Save failed")

        st.divider()

        # ── Back Generate ──────────────────────────────────────────
        st.markdown("### 🖼️ Back — መታወቂያ አዘጋጅ")

        if st.button("✅ Back መታወቂያውን አዘጋጅ / አድስ", type="primary", use_container_width=True, key="gen_back"):
            try:
                bg_back = Image.open(BG_PATH_BACK).convert("RGB")
                st.image(bg_back, caption="✅ የተዘጋጀ ፋይዳ መታወቂያ (Back)", use_container_width=True)

                buf_back = io.BytesIO()
                bg_back.save(buf_back, format="PNG")
                st.download_button("⬇️ PNG አውርድ (Back)", buf_back.getvalue(),
                                   "fayda_landscape_back.png", "image/png",
                                   type="primary", use_container_width=True, key="dl_back")

            except FileNotFoundError as e:
                st.error(f"❌ ፋይሉ አልተገኘም: {e}")
            except Exception as e:
                st.error(f"❌ ስህተት: {e}")

    else:
        st.info("👆 ID Back ፋይዳ መታወቂያ ፎቶ ያስገቡ ለመጀመር")
        try:
            st.image(Image.open(BG_PATH_BACK), caption="Back Template", use_container_width=True)
        except:
            st.warning("Back Template ምስል (20260319_211337.jpg) አልተገኘም")
