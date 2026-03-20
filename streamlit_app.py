import streamlit as st
import pytesseract
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd
import requests
import json
import barcode
from barcode.writer import ImageWriter

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
        'fan_x': 575, 'fan_y': 648,
        'fan_bc_x': 575, 'fan_bc_y': 600,
        'fan_bc_w': 300,
        'photo_x': 105, 'photo_y': 165,
        'photo_w': 190, 'photo_h': 240,
    },
    'size': {
        'amh': 32, 'eng': 32,
        'dob': 28, 'sex': 28, 'exp': 28,
        'fan': 28,
        'fan_bc': 120,
    }
}

# Defaults — Back
DEFAULT_SETTINGS_BACK = {
    'pos': {
        'phone_x': 620,  'phone_y': 200,
        'fin_x':   620,  'fin_y':   250,
        'addr_amh_x': 620, 'addr_amh_y': 300,
        'addr_eng_x': 620, 'addr_eng_y': 340,
        'zone_amh_x': 620, 'zone_amh_y': 380,
        'zone_eng_x': 620, 'zone_eng_y': 420,
        'woreda_amh_x': 620, 'woreda_amh_y': 460,
        'woreda_amh_num_x': 750, 'woreda_amh_num_y': 460,
        'woreda_eng_x': 620, 'woreda_eng_y': 500,
        'qr_x': 100, 'qr_y': 150,
        'qr_w': 200, 'qr_h': 200,
    },
    'size': {
        'phone': 28, 'fin': 28,
        'addr_amh': 28, 'addr_eng': 28,
        'zone_amh': 28, 'zone_eng': 28,
        'woreda_amh': 28, 'woreda_amh_num': 28, 'woreda_eng': 28,
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
    if 'ocr_lines_back' not in st.session_state:
        st.session_state.ocr_lines_back = []
    if 'auto_detected_back' not in st.session_state:
        st.session_state.auto_detected_back = {}
    if 'fan_manual' not in st.session_state:
        st.session_state.fan_manual = ''
    if 'fin_manual' not in st.session_state:
        st.session_state.fin_manual = ''
    if 'photo_cropped' not in st.session_state:
        st.session_state.photo_cropped = None
    if 'qr_cropped' not in st.session_state:
        st.session_state.qr_cropped = None
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
# Barcode generator helper
# ══════════════════════════════════════════════════════════════════
def generate_barcode_image(data: str, height_px: int = 120) -> Image.Image | None:
    """Generate a Code128 barcode PIL image from data string."""
    try:
        CODE128 = barcode.get_barcode_class('code128')
        writer  = ImageWriter()
        buf     = io.BytesIO()
        bc      = CODE128(data, writer=writer)
        options = {
            'write_text': False,
            'module_height': max(5, height_px / 10),
            'module_width':  0.5,
            'quiet_zone':    1.0,
            'dpi':           200,
        }
        bc.write(buf, options=options)
        buf.seek(0)
        img = Image.open(buf).convert("RGB")
        # scale to exact height keeping aspect
        w, h = img.size
        new_w = int(w * height_px / h)
        return img.resize((new_w, height_px), Image.LANCZOS)
    except Exception as e:
        return None

# ══════════════════════════════════════════════════════════════════
# Auto-detection — Front
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
        # FAN — 16-digit number
        if 'fan' not in found:
            digits = ''.join(c for c in line.strip() if c.isdigit())
            if len(digits) == 16:
                found['fan'] = i + 1
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
# Auto-detection — Back
# Rules:
#   - 10-digit number  → phone
#   - 12-digit number  → FIN
#   - 'address' keyword → next line=skip(label), +2=addr_amh, +3=addr_eng,
#                         +4=zone_amh, +5=zone_eng, +6=woreda_amh, +7=woreda_eng
# ══════════════════════════════════════════════════════════════════
def auto_detect_fields_back(lines):
    found = {}
    addr_anchor = None  # line index (0-based) where 'address' label found

    for i, line in enumerate(lines):
        stripped = line.strip()
        ll       = stripped.lower()

        # ── Phone: 10-digit number ──────────────────────────────
        if 'phone' not in found:
            digits = ''.join(c for c in stripped if c.isdigit())
            if len(digits) == 10:
                found['phone'] = i + 1   # 1-based index

        # ── FIN: 12-digit number ────────────────────────────────
        if 'fin' not in found:
            digits = ''.join(c for c in stripped if c.isdigit())
            if len(digits) == 12:
                found['fin'] = i + 1

        # ── Address anchor ──────────────────────────────────────
        if addr_anchor is None:
            if 'address' in ll or 'አድራሻ' in stripped:
                addr_anchor = i

    # Derive address fields from anchor
    if addr_anchor is not None:
        base = addr_anchor  # 0-based
        # layout: label(base), skip(base+1), addr_amh(base+2), addr_eng(base+3),
        #         zone_amh(base+4), zone_eng(base+5), woreda_amh(base+6), woreda_eng(base+7)
        def safe_idx(offset):
            idx = base + offset
            return idx + 1 if idx < len(lines) else None  # convert to 1-based

        found['addr_amh']    = safe_idx(2)
        found['addr_eng']    = safe_idx(3)
        found['zone_amh']    = safe_idx(4)
        found['zone_eng']    = safe_idx(5)
        found['woreda_amh']  = safe_idx(6)
        found['woreda_eng']  = safe_idx(7)

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
                # sync number_input keys
                for fk in ['amh','eng','dob','sex','exp','fan','fan_bc']:
                    st.session_state[f"fx_{fk}"] = st.session_state.pos[f"{fk}_x"]
                    st.session_state[f"fy_{fk}"] = st.session_state.pos[f"{fk}_y"]
                    st.session_state[f"fs_{fk}"] = st.session_state.size[fk]
                st.session_state["inp_fan_bc_w"] = st.session_state.pos.get('fan_bc_w', DEFAULT_SETTINGS['pos']['fan_bc_w'])
                for fk in ['phone','fin','addr_amh','addr_eng','zone_amh','zone_eng','woreda_amh','woreda_amh_num','woreda_eng']:
                    st.session_state[f"bx_{fk}"] = st.session_state.pos_back[f"{fk}_x"]
                    st.session_state[f"by_{fk}"] = st.session_state.pos_back[f"{fk}_y"]
                    st.session_state[f"bs_{fk}"] = st.session_state.size_back[fk]
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
# Profile & QR — Auto Crop
# ══════════════════════════════════════════════════════════════════
if uploaded_profile:
    prof_bytes = uploaded_profile.read()
    prof_cv    = cv2.imdecode(np.frombuffer(prof_bytes, np.uint8), cv2.IMREAD_COLOR)
    ph, pw     = prof_cv.shape[:2]

    # ══ ትልቁ ነጭ ሳጥን ፈልጎ ያወጣ ══
    def extract_white_card(img_bgr):
        gray    = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        # ነጭ ቦታ mask — brightness > 200
        _, white_mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        # noise ያስወግዳል
        kernel = np.ones((15, 15), np.uint8)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_CLOSE, kernel)
        white_mask = cv2.morphologyEx(white_mask, cv2.MORPH_OPEN,  kernel)
        cnts, _ = cv2.findContours(white_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not cnts:
            return None, None, None
        # ትልቁ ነጭ contour
        biggest = max(cnts, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(biggest)
        card = img_bgr[y:y+h, x:x+w]
        return card, (x, y, w, h), img_bgr

    card, bbox, _ = extract_white_card(prof_cv)

    if card is not None:
        ch, cw = card.shape[:2]

        # ══ ካርዱ ውስጥ ፎቶ ክፍል ፈልጎ ያወጣ (ላይ ክፍል — non-white content) ══
        def find_photo_in_card(card_bgr):
            gray_c  = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2GRAY)
            ch, cw  = card_bgr.shape[:2]
            row_means = np.mean(gray_c, axis=1)
            content_rows = np.where(row_means < 220)[0]
            if len(content_rows) == 0:
                return card_bgr[:ch//2, :]
            gaps = np.diff(content_rows)
            if len(gaps) > 0 and np.max(gaps) > 10:
                split_idx     = np.argmax(gaps)
                photo_end_row = content_rows[split_idx]
                pad    = 5
                top    = max(0, content_rows[0] - pad)
                bottom = min(ch, photo_end_row + pad)
                photo_crop = card_bgr[top:bottom, :]
                col_means  = np.mean(cv2.cvtColor(photo_crop, cv2.COLOR_BGR2GRAY), axis=0)
                left_col   = next((j for j in range(len(col_means)) if col_means[j] < 220), 0)
                right_col  = next((j for j in range(len(col_means)-1, -1, -1) if col_means[j] < 220), len(col_means)-1)
                photo_crop = photo_crop[:, left_col:right_col+1]
            else:
                photo_crop = card_bgr[:ch//2, :]

            # ── Background removal — GrabCut ──────────────────────
            ph2, pw2 = photo_crop.shape[:2]
            mask_gc  = np.zeros((ph2, pw2), np.uint8)
            rect     = (int(pw2*0.05), int(ph2*0.05), int(pw2*0.90), int(ph2*0.90))
            bgd_model = np.zeros((1,65), np.float64)
            fgd_model = np.zeros((1,65), np.float64)
            try:
                cv2.grabCut(photo_crop, mask_gc, rect, bgd_model, fgd_model, 5, cv2.GC_INIT_WITH_RECT)
                fg_mask = np.where((mask_gc==2)|(mask_gc==0), 0, 255).astype(np.uint8)
                # ── Black & White (grayscale) ──────────────────────
                gray_photo = cv2.cvtColor(photo_crop, cv2.COLOR_BGR2GRAY)
                bw_photo   = cv2.cvtColor(gray_photo, cv2.COLOR_GRAY2BGR)
                # background → ነጭ
                bw_photo[fg_mask == 0] = [255, 255, 255]
                return bw_photo
            except Exception:
                # fallback — ቀጥታ BW ብቻ
                gray_photo = cv2.cvtColor(photo_crop, cv2.COLOR_BGR2GRAY)
                return cv2.cvtColor(gray_photo, cv2.COLOR_GRAY2BGR)

        def find_qr_in_card(card_bgr, margin=18):
            gray_c  = cv2.cvtColor(card_bgr, cv2.COLOR_BGR2GRAY)
            ch, cw  = card_bgr.shape[:2]
            row_means = np.mean(gray_c, axis=1)
            content_rows = np.where(row_means < 220)[0]
            if len(content_rows) == 0:
                return card_bgr[ch//2:, :]
            gaps = np.diff(content_rows)
            if len(gaps) > 0 and np.max(gaps) > 10:
                split_idx    = np.argmax(gaps)
                qr_start_row = content_rows[split_idx + 1]
                pad = 5
                top    = max(0, qr_start_row - pad)
                bottom = min(ch, content_rows[-1] + pad)
                qr_crop   = card_bgr[top:bottom, :]
                col_means = np.mean(cv2.cvtColor(qr_crop, cv2.COLOR_BGR2GRAY), axis=0)
                left_col  = next((j for j in range(len(col_means)) if col_means[j] < 220), 0)
                right_col = next((j for j in range(len(col_means)-1, -1, -1) if col_means[j] < 220), len(col_means)-1)
                tight = qr_crop[:, left_col:right_col+1]
                # 4 ጎን ነጭ margin ይጨምራል
                th, tw = tight.shape[:2]
                canvas = np.ones((th + margin*2, tw + margin*2, 3), dtype=np.uint8) * 255
                canvas[margin:margin+th, margin:margin+tw] = tight
                return canvas
            return card_bgr[ch//2:, :]

        photo_result = find_photo_in_card(card)
        qr_result    = find_qr_in_card(card)
    else:
        # fallback
        photo_result = prof_cv[0:int(ph*0.48), :]
        qr_result    = prof_cv[int(ph*0.52):ph, :]

    st.session_state.photo_cropped = photo_result
    st.session_state.qr_cropped    = qr_result

    pc1, pc2 = st.columns(2)
    with pc1:
        st.markdown("**✂️ ፎቶ (Front ID ይሄዳል)**")
        st.image(cv2.cvtColor(photo_result, cv2.COLOR_BGR2RGB), use_container_width=True)
    with pc2:
        st.markdown("**✂️ QR Code (Back ID ይሄዳል)**")
        st.image(cv2.cvtColor(qr_result, cv2.COLOR_BGR2RGB), use_container_width=True)
    st.divider()
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
                    # FAN auto-fill
                    fan_idx = st.session_state.auto_detected.get('fan')
                    if fan_idx:
                        raw = lines[fan_idx - 1]
                        digits = ''.join(c for c in raw if c.isdigit())
                        st.session_state.fan_manual = digits

            if st.session_state.ocr_lines:
                lines    = st.session_state.ocr_lines
                detected = st.session_state.auto_detected
                tag_map  = {'fan':'← FAN','full_name':'← ስም','date_birth':'← ልደት ቀን','sex':'← ፆታ','date_expiry':'← ቀን ማብቂያ'}
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
            fn_idx = detected.get('full_name', None)

            # Auto-detect ሲሳካ session_state field indices ያዘምናል
            if detected:
                if 'f_amh_n' not in st.session_state or st.session_state.get('f_last_detected') != detected:
                    st.session_state.f_amh_n = int(fn_idx) if fn_idx else 5
                    st.session_state.f_eng_n = int(fn_idx)+1 if fn_idx else 6
                    st.session_state.f_dob_n = int(detected.get('date_birth', 8))
                    st.session_state.f_sex_n = int(detected.get('sex', 10))
                    st.session_state.f_exp_n = int(detected.get('date_expiry', 12))
                    st.session_state.f_last_detected = detected
            else:
                for k, v in [('f_amh_n',5),('f_eng_n',6),('f_dob_n',8),('f_sex_n',10),('f_exp_n',12)]:
                    if k not in st.session_state:
                        st.session_state[k] = v

            c1, c2, c3 = st.columns(3)
            with c1:
                amh_n = st.number_input("አማርኛ ስም ቁጥር:",     min_value=1, key="f_amh_n")
                eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር:",   min_value=1, key="f_eng_n")
            with c2:
                dob_n = st.number_input("የትውልድ ቀን ቁጥር:",    min_value=1, key="f_dob_n")
                sex_n = st.number_input("ፆታ ቁጥር:",           min_value=1, key="f_sex_n")
            with c3:
                exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር:",  min_value=1, key="f_exp_n")

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

        # ── FAN ሳጥን ──────────────────────────────────────────────
        st.markdown("### 🔖 FAN")
        fan_col1, fan_col2 = st.columns([3, 1])
        with fan_col1:
            fan_value = st.text_input(
                "FAN (16 ዲጂት) — OCR ካልተሳካ manually ያስገቡ:",
                value=st.session_state.fan_manual,
                key="fan_manual",
                placeholder="ምሳሌ: 1234567890123456",
                label_visibility="visible"
            )
        with fan_col2:
            st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
            fan_digits_only = ''.join(c for c in fan_value if c.isdigit())
            st.markdown(f"**{len(fan_digits_only)}/16 ዲጂት**")

        st.divider()

        # ── ደረጃ 3: Position + Size controls ──────────────────────
        st.markdown("### 🕹️ ደረጃ 3: ቦታ እና ፊደል መጠን ማስተካከያ")

        field_labels = {
            'amh':    'አማርኛ ስም',
            'eng':    'እንግሊዝኛ ስም',
            'dob':    'የትውልድ ቀን',
            'sex':    'ፆታ',
            'exp':    'ቀን ማብቂያ',
            'fan':    '🔖 FAN (ጽሁፍ)',
            'fan_bc': '📊 FAN Barcode',
        }

        # init pos/size into individual session_state keys for number_input
        for fk in field_labels:
            if f"fx_{fk}" not in st.session_state:
                st.session_state[f"fx_{fk}"] = st.session_state.pos[f"{fk}_x"]
            if f"fy_{fk}" not in st.session_state:
                st.session_state[f"fy_{fk}"] = st.session_state.pos[f"{fk}_y"]
            if f"fs_{fk}" not in st.session_state:
                st.session_state[f"fs_{fk}"] = st.session_state.size[fk]

        hdr_c0, hdr_c1, hdr_c2, hdr_c3 = st.columns([2, 1, 1, 1])
        hdr_c1.markdown("**X**")
        hdr_c2.markdown("**Y**")
        hdr_c3.markdown("**Size**")

        for fk, label in field_labels.items():
            if fk == 'fan_bc':
                # Barcode — X, Y, ቁመት (Height), ስፋት (Width)
                if "fan_bc_w" not in st.session_state:
                    st.session_state["fan_bc_w"] = DEFAULT_SETTINGS['pos']['fan_bc_w']
                st.markdown(f"**{label}**")
                bc_c1, bc_c2, bc_c3, bc_c4 = st.columns(4)
                with bc_c1:
                    st.caption("X")
                    vx = st.number_input("", key="fx_fan_bc", label_visibility="collapsed", step=1)
                    st.session_state.pos['fan_bc_x'] = int(vx)
                with bc_c2:
                    st.caption("Y")
                    vy = st.number_input("", key="fy_fan_bc", label_visibility="collapsed", step=1)
                    st.session_state.pos['fan_bc_y'] = int(vy)
                with bc_c3:
                    st.caption("ቁመት (Height)")
                    vh = st.number_input("", key="fs_fan_bc", label_visibility="collapsed", step=1, min_value=10)
                    st.session_state.size['fan_bc'] = int(vh)
                with bc_c4:
                    st.caption("ስፋት (Width)")
                    # ሁሌም pos['fan_bc_w'] ከ Firebase load ጋር sync ይሁን
                    st.session_state["inp_fan_bc_w"] = st.session_state.pos.get('fan_bc_w', DEFAULT_SETTINGS['pos']['fan_bc_w'])
                    vw = st.number_input("", key="inp_fan_bc_w", label_visibility="collapsed", step=1, min_value=50)
                    st.session_state.pos['fan_bc_w'] = int(vw)
            else:
                col0, col1, col2, col3 = st.columns([2, 1, 1, 1])
                with col0:
                    st.markdown(f"**{label}**")
                with col1:
                    vx = st.number_input("", key=f"fx_{fk}", label_visibility="collapsed", step=1)
                    st.session_state.pos[f"{fk}_x"] = int(vx)
                with col2:
                    vy = st.number_input("", key=f"fy_{fk}", label_visibility="collapsed", step=1)
                    st.session_state.pos[f"{fk}_y"] = int(vy)
                with col3:
                    vs = st.number_input("", key=f"fs_{fk}", label_visibility="collapsed", step=1, min_value=1)
                    st.session_state.size[fk] = int(vs)

        # ── Photo ቦታ ──────────────────────────────────────────────
        st.markdown("**📸 ፎቶ (Profile ምስል)**")
        for pk in ['photo_x','photo_y','photo_w','photo_h']:
            if f"fp_{pk}" not in st.session_state:
                st.session_state[f"fp_{pk}"] = DEFAULT_SETTINGS['pos'][pk]
        ph_c1, ph_c2, ph_c3, ph_c4 = st.columns(4)
        with ph_c1:
            st.caption("X")
            st.session_state.pos['photo_x'] = int(st.number_input("", key="fp_photo_x", label_visibility="collapsed", step=1))
        with ph_c2:
            st.caption("Y")
            st.session_state.pos['photo_y'] = int(st.number_input("", key="fp_photo_y", label_visibility="collapsed", step=1))
        with ph_c3:
            st.caption("ስፋት (W)")
            st.session_state.pos['photo_w'] = int(st.number_input("", key="fp_photo_w", label_visibility="collapsed", step=1, min_value=10))
        with ph_c4:
            st.caption("ቁመት (H)")
            st.session_state.pos['photo_h'] = int(st.number_input("", key="fp_photo_h", label_visibility="collapsed", step=1, min_value=10))

        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ", use_container_width=True, key="reset_front"):
                st.session_state.pos  = DEFAULT_SETTINGS['pos'].copy()
                st.session_state.size = DEFAULT_SETTINGS['size'].copy()
                for fk in ['amh','eng','dob','sex','exp','fan','fan_bc']:
                    st.session_state[f"fx_{fk}"] = DEFAULT_SETTINGS['pos'][f"{fk}_x"]
                    st.session_state[f"fy_{fk}"] = DEFAULT_SETTINGS['pos'][f"{fk}_y"]
                    st.session_state[f"fs_{fk}"] = DEFAULT_SETTINGS['size'][fk]
                st.session_state["inp_fan_bc_w"] = DEFAULT_SETTINGS['pos']['fan_bc_w']
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

                    # FAN — manual ሳጥን ወይም OCR ከ session_state
                    fan_digits_gen = ''.join(c for c in st.session_state.get('fan_manual','') if c.isdigit())
                    if fan_digits_gen:
                        fan_formatted = ' '.join(fan_digits_gen[i:i+4] for i in range(0, len(fan_digits_gen), 4))
                        draw_smart_text(draw, (p['fan_x'], p['fan_y']), fan_formatted, sz['fan'], sz['fan'], tc)

                    # FAN Barcode
                    if fan_digits_gen:
                        bc_h = int(sz['fan_bc'])
                        bc_w = int(p.get('fan_bc_w', 300))
                        bc_img = generate_barcode_image(fan_digits_gen, height_px=bc_h)
                        if bc_img:
                            bc_img = bc_img.resize((bc_w, bc_h), Image.LANCZOS)
                            bg.paste(bc_img, (int(p['fan_bc_x']), int(p['fan_bc_y'])))

                    # Photo — Profile ምስል ከ session_state
                    if st.session_state.photo_cropped is not None:
                        ph_img = Image.fromarray(cv2.cvtColor(st.session_state.photo_cropped, cv2.COLOR_BGR2RGB))
                        pw = int(st.session_state.pos.get('photo_w', 190))
                        ph = int(st.session_state.pos.get('photo_h', 240))
                        px = int(st.session_state.pos.get('photo_x', 105))
                        py = int(st.session_state.pos.get('photo_y', 165))
                        bg.paste(ph_img.resize((pw, ph), Image.LANCZOS), (px, py))

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
# BACK TAB
# ─────────────────────────────────────────────────────────────────
with tab_back:
    if uploaded_back:
        file_bytes_b = uploaded_back.read()
        image_cv_b   = cv2.imdecode(np.frombuffer(file_bytes_b, np.uint8), cv2.IMREAD_COLOR)
        h_b, w_b     = image_cv_b.shape[:2]
        id_only_b    = image_cv_b[int(h_b*0.18):int(h_b*0.85), int(w_b*0.10):int(w_b*0.90)]

        # ── ደረጃ 1: OCR ────────────────────────────────────────────
        with st.expander("📋 ደረጃ 1: OCR — ጽሁፍ ማውጣት (Back)", expanded=True):
            if st.button("🔍 መረጃውን አውጣ (Back)", type="primary", key="ocr_back"):
                with st.spinner("OCR እየሰራ ነው..."):
                    gray_b      = cv2.cvtColor(id_only_b, cv2.COLOR_BGR2GRAY)
                    full_text_b = pytesseract.image_to_string(gray_b, lang='amh+eng')
                    lines_b     = [l.strip() for l in full_text_b.split('\n') if len(l.strip()) > 1]
                    st.session_state.ocr_lines_back    = lines_b
                    st.session_state.auto_detected_back = auto_detect_fields_back(lines_b)
                    # FIN auto-fill
                    fin_idx = st.session_state.auto_detected_back.get('fin')
                    if fin_idx:
                        raw_fin = lines_b[fin_idx - 1]
                        digits_fin = ''.join(c for c in raw_fin if c.isdigit())
                        st.session_state.fin_manual = digits_fin

            if st.session_state.get('ocr_lines_back'):
                lines_b    = st.session_state.ocr_lines_back
                detected_b = st.session_state.auto_detected_back
                tag_map_b  = {
                    'phone':      '← ስልክ ቁጥር',
                    'fin':        '← FIN',
                    'addr_amh':   '← አድራሻ (አማርኛ)',
                    'addr_eng':   '← አድራሻ (English)',
                    'zone_amh':   '← ዞን (አማርኛ)',
                    'zone_eng':   '← ዞን (English)',
                    'woreda_amh': '← ወረዳ (አማርኛ)',
                    'woreda_eng': '← ወረዳ (English)',
                }
                rows_b = [{"ቁጥር": i+1, "ጽሁፍ": l,
                           "": next((tag_map_b[f] for f,idx in detected_b.items() if idx==i+1), "")}
                          for i, l in enumerate(lines_b)]
                st.dataframe(pd.DataFrame(rows_b), use_container_width=True, hide_index=True)
                n_found = sum(1 for v in detected_b.values() if v is not None)
                if detected_b:
                    st.success(f"✅ Auto-detection ተሳካ: {n_found}/8 fields")
                else:
                    st.warning("⚠️ Auto-detection አልተሳካም — ቁጥሮቹን በራስዎ ይምረጡ")

        st.divider()

        # ── ደረጃ 2: Field Numbers ──────────────────────────────────
        with st.expander("🔢 ደረጃ 2: የጽሁፍ ቁጥሮች (Back)", expanded=True):
            detected_b = st.session_state.get('auto_detected_back', {})

            def _b(key, default):
                v = detected_b.get(key, None)
                return int(v) if v else default

            # Auto-detect ሲሳካ session_state keys ያዘምናል
            if detected_b:
                if st.session_state.get('b_last_detected') != detected_b:
                    st.session_state.b_phone_n      = _b('phone',      3)
                    st.session_state.b_fin_n        = _b('fin',        5)
                    st.session_state.b_addr_amh_n   = _b('addr_amh',   7)
                    st.session_state.b_addr_eng_n   = _b('addr_eng',   8)
                    st.session_state.b_zone_amh_n   = _b('zone_amh',   9)
                    st.session_state.b_zone_eng_n   = _b('zone_eng',  10)
                    st.session_state.b_woreda_amh_n = _b('woreda_amh',11)
                    st.session_state.b_woreda_eng_n = _b('woreda_eng',12)
                    st.session_state.b_last_detected = detected_b
            else:
                for k, v in [('b_phone_n',3),('b_fin_n',5),('b_addr_amh_n',7),('b_addr_eng_n',8),
                             ('b_zone_amh_n',9),('b_zone_eng_n',10),('b_woreda_amh_n',11),('b_woreda_eng_n',12)]:
                    if k not in st.session_state:
                        st.session_state[k] = v

            bc1, bc2, bc3, bc4 = st.columns(4)
            with bc1:
                phone_n_b     = st.number_input("📞 ስልክ ቁጥር:",       min_value=1, key="b_phone_n")
                fin_n_b       = st.number_input("🔢 FIN:",             min_value=1, key="b_fin_n")
            with bc2:
                addr_amh_n_b  = st.number_input("🏠 አድራሻ (አማርኛ):",  min_value=1, key="b_addr_amh_n")
                addr_eng_n_b  = st.number_input("🏠 አድራሻ (English):", min_value=1, key="b_addr_eng_n")
            with bc3:
                zone_amh_n_b  = st.number_input("🗺️ ዞን (አማርኛ):",    min_value=1, key="b_zone_amh_n")
                zone_eng_n_b  = st.number_input("🗺️ ዞን (English):",   min_value=1, key="b_zone_eng_n")
            with bc4:
                woreda_amh_n_b = st.number_input("📍 ወረዳ (አማርኛ):",   min_value=1, key="b_woreda_amh_n")
                woreda_eng_n_b = st.number_input("📍 ወረዳ (English):",  min_value=1, key="b_woreda_eng_n")

            if st.session_state.get('ocr_lines_back'):
                lines_b = st.session_state.ocr_lines_back
                def pv_b(n):
                    idx = int(n)-1
                    return lines_b[idx] if 0 <= idx < len(lines_b) else "—"
                st.markdown("**ቅድመ ዕይታ:**")
                for lbl, n in [
                    ("ስልክ ቁጥር",       phone_n_b),
                    ("FIN",            fin_n_b),
                    ("አድራሻ (አማርኛ)",  addr_amh_n_b),
                    ("አድራሻ (English)", addr_eng_n_b),
                    ("ዞን (አማርኛ)",    zone_amh_n_b),
                    ("ዞን (English)",   zone_eng_n_b),
                    ("ወረዳ (አማርኛ)",   woreda_amh_n_b),
                    ("ወረዳ (English)",  woreda_eng_n_b),
                ]:
                    st.markdown(f"- **{lbl}:** `{pv_b(n)}`")

        st.divider()

        # ── FIN ሳጥን ──────────────────────────────────────────────
        st.markdown("### 🔢 FIN")
        fin_col1, fin_col2 = st.columns([3, 1])
        with fin_col1:
            fin_value = st.text_input(
                "FIN (12 ዲጂት) — OCR ካልተሳካ manually ያስገቡ:",
                value=st.session_state.fin_manual,
                key="fin_manual",
                placeholder="ምሳሌ: 123456789012",
                label_visibility="visible"
            )
        with fin_col2:
            st.markdown("<div style='padding-top:28px'></div>", unsafe_allow_html=True)
            fin_digits_only = ''.join(c for c in fin_value if c.isdigit())
            fin_formatted_preview = '-'.join(fin_digits_only[i:i+4] for i in range(0, len(fin_digits_only), 4))
            st.markdown(f"**{len(fin_digits_only)}/12 ዲጂት**")
            if fin_digits_only:
                st.caption(fin_formatted_preview)

        st.divider()

        # ── ደረጃ 3: Position + Size controls ──────────────────────
        st.markdown("### 🕹️ ደረጃ 3: ቦታ እና ፊደል መጠን ማስተካከያ (Back)")

        field_labels_back = {
            'phone':          '📞 ስልክ ቁጥር',
            'fin':            '🔢 FIN',
            'addr_amh':       '🏠 አድራሻ (አማርኛ)',
            'addr_eng':       '🏠 አድራሻ (English)',
            'zone_amh':       '🗺️ ዞን (አማርኛ)',
            'zone_eng':       '🗺️ ዞን (English)',
            'woreda_amh':     '📍 ወረዳ (አማርኛ ጽሁፍ)',
            'woreda_amh_num': '📍 ወረዳ (ቁጥር)',
            'woreda_eng':     '📍 ወረዳ (English)',
        }

        # init pos/size into individual session_state keys for number_input
        for fk in field_labels_back:
            if f"bx_{fk}" not in st.session_state:
                st.session_state[f"bx_{fk}"] = st.session_state.pos_back[f"{fk}_x"]
            if f"by_{fk}" not in st.session_state:
                st.session_state[f"by_{fk}"] = st.session_state.pos_back[f"{fk}_y"]
            if f"bs_{fk}" not in st.session_state:
                st.session_state[f"bs_{fk}"] = st.session_state.size_back[fk]

        bhdr_c0, bhdr_c1, bhdr_c2, bhdr_c3 = st.columns([2, 1, 1, 1])
        bhdr_c1.markdown("**X**")
        bhdr_c2.markdown("**Y**")
        bhdr_c3.markdown("**Size**")

        for fk, label in field_labels_back.items():
            bcol0, bcol1, bcol2, bcol3 = st.columns([2, 1, 1, 1])
            with bcol0:
                st.markdown(f"**{label}**")
            with bcol1:
                vx = st.number_input("", key=f"bx_{fk}", label_visibility="collapsed", step=1)
                st.session_state.pos_back[f"{fk}_x"] = int(vx)
            with bcol2:
                vy = st.number_input("", key=f"by_{fk}", label_visibility="collapsed", step=1)
                st.session_state.pos_back[f"{fk}_y"] = int(vy)
            with bcol3:
                vs = st.number_input("", key=f"bs_{fk}", label_visibility="collapsed", step=1, min_value=1)
                st.session_state.size_back[fk] = int(vs)

        # ── QR Code ቦታ ────────────────────────────────────────────
        st.markdown("**📷 QR Code (Profile ምስል)**")
        for qk in ['qr_x','qr_y','qr_w','qr_h']:
            if f"bp_{qk}" not in st.session_state:
                st.session_state[f"bp_{qk}"] = DEFAULT_SETTINGS_BACK['pos'][qk]
        qr_c1, qr_c2, qr_c3, qr_c4 = st.columns(4)
        with qr_c1:
            st.caption("X")
            st.session_state.pos_back['qr_x'] = int(st.number_input("", key="bp_qr_x", label_visibility="collapsed", step=1))
        with qr_c2:
            st.caption("Y")
            st.session_state.pos_back['qr_y'] = int(st.number_input("", key="bp_qr_y", label_visibility="collapsed", step=1))
        with qr_c3:
            st.caption("ስፋት (W)")
            st.session_state.pos_back['qr_w'] = int(st.number_input("", key="bp_qr_w", label_visibility="collapsed", step=1, min_value=10))
        with qr_c4:
            st.caption("ቁመት (H)")
            st.session_state.pos_back['qr_h'] = int(st.number_input("", key="bp_qr_h", label_visibility="collapsed", step=1, min_value=10))

        col_rb1, col_rb2 = st.columns(2)
        with col_rb1:
            if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ (Back)", use_container_width=True, key="reset_back"):
                st.session_state.pos_back  = DEFAULT_SETTINGS_BACK['pos'].copy()
                st.session_state.size_back = DEFAULT_SETTINGS_BACK['size'].copy()
                for fk in ['phone','fin','addr_amh','addr_eng','zone_amh','zone_eng','woreda_amh','woreda_amh_num','woreda_eng']:
                    st.session_state[f"bx_{fk}"] = DEFAULT_SETTINGS_BACK['pos'][f"{fk}_x"]
                    st.session_state[f"by_{fk}"] = DEFAULT_SETTINGS_BACK['pos'][f"{fk}_y"]
                    st.session_state[f"bs_{fk}"] = DEFAULT_SETTINGS_BACK['size'][fk]
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

        # ── ደረጃ 4: Generate ───────────────────────────────────────
        st.markdown("### 🖼️ ደረጃ 4: Back መታወቂያ አዘጋጅ")

        if st.button("✅ Back መታወቂያውን አዘጋጅ / አድስ", type="primary", use_container_width=True, key="gen_back"):
            if not st.session_state.get('ocr_lines_back'):
                st.warning("⚠️ መጀመሪያ OCR ሂደቱን ያካሂዱ (ደረጃ 1)")
            else:
                lines_b = st.session_state.ocr_lines_back
                try:
                    bg_back = Image.open(BG_PATH_BACK).convert("RGB")
                    draw_b  = ImageDraw.Draw(bg_back)
                    p_b     = st.session_state.pos_back
                    sz_b    = st.session_state.size_back
                    tc      = (45, 25, 5)

                    def safe_line_b(n):
                        idx = int(n) - 1
                        return lines_b[idx] if 0 <= idx < len(lines_b) else f"[{n} አልተገኘም]"

                    # FIN — manual ሳጥን ወይም OCR ከ session_state፣ በየ 4 ዲጂቱ (-) ይጨምር
                    fin_digits_gen = ''.join(c for c in st.session_state.get('fin_manual','') if c.isdigit())
                    if not fin_digits_gen and st.session_state.get('ocr_lines_back'):
                        fin_raw       = safe_line_b(fin_n_b)
                        fin_digits_gen = ''.join(c for c in fin_raw if c.isdigit())
                    fin_formatted = '-'.join(fin_digits_gen[i:i+4] for i in range(0, len(fin_digits_gen), 4))

                    # ወረዳ አማርኛ — ጽሁፍ ለብቻ (non-digit) ቁጥር ለብቻ (digit)
                    woreda_raw     = safe_line_b(woreda_amh_n_b)
                    woreda_text    = ''.join(c for c in woreda_raw if not c.isdigit()).strip()
                    woreda_numpart = ''.join(c for c in woreda_raw if c.isdigit()).strip()

                    draw_smart_text(draw_b, (p_b['phone_x'],          p_b['phone_y']),          safe_line_b(phone_n_b),    sz_b['phone'],          sz_b['phone'],          tc)
                    draw_smart_text(draw_b, (p_b['fin_x'],            p_b['fin_y']),            fin_formatted,             sz_b['fin'],            sz_b['fin'],            tc)
                    draw_smart_text(draw_b, (p_b['addr_amh_x'],       p_b['addr_amh_y']),       safe_line_b(addr_amh_n_b), sz_b['addr_amh'],       sz_b['addr_amh'],       tc)
                    draw_smart_text(draw_b, (p_b['addr_eng_x'],       p_b['addr_eng_y']),       safe_line_b(addr_eng_n_b), sz_b['addr_eng'],       sz_b['addr_eng'],       tc)
                    draw_smart_text(draw_b, (p_b['zone_amh_x'],       p_b['zone_amh_y']),       safe_line_b(zone_amh_n_b), sz_b['zone_amh'],       sz_b['zone_amh'],       tc)
                    draw_smart_text(draw_b, (p_b['zone_eng_x'],       p_b['zone_eng_y']),       safe_line_b(zone_eng_n_b), sz_b['zone_eng'],       sz_b['zone_eng'],       tc)
                    # ወረዳ አማርኛ ጽሁፍ ለብቻ
                    draw_smart_text(draw_b, (p_b['woreda_amh_x'],     p_b['woreda_amh_y']),     woreda_text,               sz_b['woreda_amh'],     sz_b['woreda_amh'],     tc)
                    # ወረዳ ቁጥር ለብቻ
                    draw_smart_text(draw_b, (p_b['woreda_amh_num_x'], p_b['woreda_amh_num_y']), woreda_numpart,            sz_b['woreda_amh_num'], sz_b['woreda_amh_num'], tc)
                    draw_smart_text(draw_b, (p_b['woreda_eng_x'],     p_b['woreda_eng_y']),     safe_line_b(woreda_eng_n_b),sz_b['woreda_eng'],   sz_b['woreda_eng'],     tc)

                    # QR Code — Profile ምስል ከ session_state
                    if st.session_state.qr_cropped is not None:
                        qr_img = Image.fromarray(cv2.cvtColor(st.session_state.qr_cropped, cv2.COLOR_BGR2RGB))
                        qw = int(st.session_state.pos_back.get('qr_w', 200))
                        qh = int(st.session_state.pos_back.get('qr_h', 200))
                        qx = int(st.session_state.pos_back.get('qr_x', 100))
                        qy = int(st.session_state.pos_back.get('qr_y', 150))
                        bg_back.paste(qr_img.resize((qw, qh), Image.LANCZOS), (qx, qy))

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
