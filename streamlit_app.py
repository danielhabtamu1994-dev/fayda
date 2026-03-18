import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import cv2
import numpy as np
import io
import pandas as pd
import requests
import json
import re

FONT_AMH    = "AbyssinicaSIL-Regular.ttf"
FONT_ENG    = "Inter_18pt-Bold.ttf"
BG_PATH     = "IMG_20260318_085131_234.jpg"
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
# Smart FAN / Barcode white-box detection
# ══════════════════════════════════════════════════════════════════
def _expand_white_box(id_only, bx, by, bx2, by2):
    """
    barcode bounding box ካገኘ በኋላ 4 አቅጣጫ ያስፋፋል።
    """
    ih, iw = id_only.shape[:2]
    img_f    = id_only.astype(np.int16)
    chroma   = img_f.max(axis=2) - img_f.min(axis=2)
    bright   = img_f.max(axis=2)
    is_white = (chroma < 30) & (bright > 180)

    THRESH = 0.38

    y1 = by
    for y in range(by - 1, -1, -1):
        if is_white[y, max(0,bx):min(iw,bx2)].mean() >= THRESH: y1 = y
        else: break

    y2 = by2
    for y in range(by2 + 1, ih):
        if is_white[y, max(0,bx):min(iw,bx2)].mean() >= THRESH: y2 = y
        else: break

    x1 = bx
    for x in range(bx - 1, -1, -1):
        if is_white[y1:y2+1, x].mean() >= THRESH: x1 = x
        else: break

    x2 = bx2
    for x in range(bx2 + 1, iw):
        if is_white[y1:y2+1, x].mean() >= THRESH: x2 = x
        else: break

    return x1, y1, x2, y2


def _find_barcode_by_stripes(id_only):
    """
    Fallback: pyzbar ካልሰራ strict white fraction range ተጠቅሞ FAN ሳጥን ያፈልጋል።

    ምልከታ:
      FAN box rows  → strict white 0.25–0.85  (barcode bars ስላሉ ሙሉ ነጭ አይደለም)
      Phone UI rows → strict white > 0.85      (ሙሉ ነጭ)
      Card BG rows  → strict white < 0.20      (colored pattern)

    ስለዚህ 0.25–0.85 range ያሉ rows = FAN box
    """
    ih, iw = id_only.shape[:2]

    img_f  = id_only.astype(np.int16)
    chroma = img_f.max(axis=2) - img_f.min(axis=2)
    bright = img_f.max(axis=2)
    is_strict_white = (chroma < 15) & (bright > 210)
    row_frac = is_strict_white.mean(axis=1)

    # Search bottom 50% only
    search_top = int(ih * 0.50)

    # FAN box: moderate strict white (not phone UI, not card BG)
    FAN_MIN = 0.25
    FAN_MAX = 0.85

    white_rows = [y for y in range(search_top, ih)
                  if FAN_MIN <= row_frac[y] <= FAN_MAX]
    if len(white_rows) < 5:
        return None

    # Find largest continuous band
    wbr  = np.array(white_rows)
    gaps = np.where(np.diff(wbr) > 12)[0]
    if len(gaps) == 0:
        bands = [(wbr[0], wbr[-1])]
    else:
        starts = [0] + list(gaps + 1)
        ends   = list(gaps) + [len(wbr) - 1]
        bands  = [(wbr[s], wbr[e]) for s, e in zip(starts, ends)]

    y1, y2 = max(bands, key=lambda b: b[1] - b[0])

    # Column range
    col_frac   = is_strict_white[y1:y2 + 1, :].mean(axis=0)
    white_cols = np.where(col_frac >= 0.20)[0]
    if len(white_cols) < 10:
        return None

    return int(white_cols[0]), y1, int(white_cols[-1]), y2


def find_fan_box(id_only):
    """
    FAN ነጭ ሳጥን ፈልጎ ይቆርጣል — ካርድ ቁጥር/ቀጥሮ/FAN labels ጨምሮ ሙሉ ሳጥን።

    ዘዴ 1 (pyzbar):  ባርኮዱን directly ያነባል — fastest & most accurate
    ዘዴ 2 (stripes): vertical edge pattern ይፈልጋል — blurry/angled images ላይ
    ሁለቱም ካልሰሩ:    None ይመልሳል
    """
    ih, iw = id_only.shape[:2]

    # ── Method 1: pyzbar ──────────────────────────────────────────
    coords = None
    try:
        from pyzbar import pyzbar
        gray = cv2.cvtColor(id_only, cv2.COLOR_BGR2GRAY)

        barcodes = pyzbar.decode(gray)

        # retry with enhanced contrast
        if not barcodes:
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
            barcodes = pyzbar.decode(clahe.apply(gray))

        # retry with upscaled image
        if not barcodes:
            big = cv2.resize(gray, (iw*2, ih*2), interpolation=cv2.INTER_CUBIC)
            found = pyzbar.decode(big)
            if found:
                bc  = found[0]
                pts = bc.polygon
                bx  = min(p.x for p in pts) // 2
                by  = min(p.y for p in pts) // 2
                bx2 = max(p.x for p in pts) // 2
                by2 = max(p.y for p in pts) // 2
                coords = (bx, by, bx2, by2)

        if not coords and barcodes:
            bc  = barcodes[0]
            pts = bc.polygon
            coords = (
                min(p.x for p in pts), min(p.y for p in pts),
                max(p.x for p in pts), max(p.y for p in pts),
            )

    except ImportError:
        pass

    # ── Method 2: vertical stripe fallback ───────────────────────
    if coords is None:
        result = _find_barcode_by_stripes(id_only)
        if result:
            coords = result

    if coords is None:
        return None

    bx, by, bx2, by2 = coords

    # ── Expand to full white box ──────────────────────────────────
    x1, y1, x2, y2 = _expand_white_box(id_only, bx, by, bx2, by2)

    fw, fh = x2 - x1, y2 - y1
    if fw < 30 or fh < 10:
        return None

    return id_only[y1:y2 + 1, x1:x2 + 1]

# ══════════════════════════════════════════════════════════════════
# Claude Vision OCR — Tesseract ምትክ
# ══════════════════════════════════════════════════════════════════
def run_claude_ocr(id_only):
    """
    ምስሉን Claude Vision API ላይ ልኮ ሁሉም ጽሁፍ ያወጣል።
    Tesseract ከሚሰጠው የተሻለ accuracy — አማርኛ፣ እንግሊዝኛ፣ ቁጥሮች ሁሉ ትክክል።

    Returns: list of text lines (same format as before)
    """
    import base64

    # id_only (numpy BGR) → JPEG bytes → base64
    success, buf = cv2.imencode('.jpg', id_only, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not success:
        return []
    img_b64 = base64.standard_b64encode(buf.tobytes()).decode('utf-8')

    prompt = """ይህ የኢትዮጵያ ፋይዳ ዲጂታል መታወቂያ ካርድ ምስል ነው።
በምስሉ ውስጥ ያሉትን ሁሉም ጽሁፎች ያለምንም ለውጥ ያንብቡ።

በትክክል እንዲህ format አድርገህ JSON ብቻ መልስ (ሌላ ጽሁፍ አትጨምር):
{
  "lines": [
    "line1 text here",
    "line2 text here",
    ...
  ]
}

አስፈላጊ ህጎች:
- እያንዳንዱ የጽሁፍ መስመር የራሱ item ይሁን
- ሁሉም ቁጥሮች ሙሉ በሙሉ ይነበቡ (ምንም digit አይጥፋ)
- አማርኛ ፊደሎች ትክክለኛ Unicode ይሁኑ
- Labels (ሙሉ ስም, Date of Birth, Sex, Date of Expiry) ጨምሮ ሁሉም ይነበቡ
- background noise/watermark አትጨምር"""

    try:
        # API key — Streamlit secrets ወይም environment variable
        import os
        api_key = ""
        try:
            api_key = st.secrets["ANTHROPIC_API_KEY"]
        except Exception:
            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return ["[Error: ANTHROPIC_API_KEY secret አልተቀመጠም። Streamlit Cloud → Settings → Secrets ውስጥ ያስገቡ]"]

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type": "application/json",
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": img_b64
                            }
                        },
                        {"type": "text", "text": prompt}
                    ]
                }]
            },
            timeout=30
        )

        if resp.status_code != 200:
            return [f"[API Error {resp.status_code}]"]

        content = resp.json()["content"][0]["text"].strip()

        # Parse JSON response
        # Strip markdown code fences if present
        content = re.sub(r'^```[a-z]*\n?', '', content)
        content = re.sub(r'\n?```$', '', content)

        data  = json.loads(content)
        lines = [l.strip() for l in data.get("lines", []) if l.strip()]
        return lines

    except json.JSONDecodeError:
        # Fallback: extract lines from raw text
        lines = [l.strip() for l in content.split('\n') if len(l.strip()) > 1]
        return lines
    except Exception as e:
        return [f"[OCR Error: {e}]"]


# ══════════════════════════════════════════════════════════════════
# Defaults
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

# ── Session State init ──────────────────────────────────────────
def init_state():
    if 'pos' not in st.session_state:
        st.session_state.pos  = DEFAULT_SETTINGS['pos'].copy()
    if 'size' not in st.session_state:
        st.session_state.size = DEFAULT_SETTINGS['size'].copy()
    if 'ocr_lines' not in st.session_state:
        st.session_state.ocr_lines = []
    if 'auto_detected' not in st.session_state:
        st.session_state.auto_detected = {}
    if 'selected_field' not in st.session_state:
        st.session_state.selected_field = 'amh'
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
                'pos':  st.session_state.pos,
                'size': st.session_state.size,
            }
            if firebase_save(payload):
                st.success("✅ Saved!")
            else:
                st.error("❌ Failed")
    with col_fb3:
        if st.button("🔄 Settings Load", use_container_width=True):
            saved = firebase_load()
            if saved:
                if 'pos'  in saved: st.session_state.pos  = {**DEFAULT_SETTINGS['pos'],  **saved['pos']}
                if 'size' in saved: st.session_state.size = {**DEFAULT_SETTINGS['size'], **saved['size']}
                st.success("✅ Loaded!")
                st.rerun()
            else:
                st.warning("Firebase ላይ settings አልተገኘም")

st.divider()

uploaded_file = st.file_uploader("📷 የቁም ፋይዳ መታወቂያ ያስገቡ", type=['jpg', 'jpeg', 'png'])

if uploaded_file:
    file_bytes = uploaded_file.read()
    image_cv   = cv2.imdecode(np.frombuffer(file_bytes, np.uint8), cv2.IMREAD_COLOR)
    h, w       = image_cv.shape[:2]
    id_only    = image_cv[int(h*0.18):int(h*0.85), int(w*0.10):int(w*0.90)]

    # ── ደረጃ 1: OCR ────────────────────────────────────────────
    with st.expander("📋 ደረጃ 1: OCR — ጽሁፍ ማውጣት", expanded=True):
        if st.button("🔍 መረጃውን አውጣ (Claude Vision)", type="primary"):
            with st.spinner("Claude Vision እየሰራ ነው..."):
                lines  = run_claude_ocr(id_only)
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
            amh_n = st.number_input("አማርኛ ስም ቁጥር:",     value=fn_idx if fn_idx else 5,               min_value=1)
            eng_n = st.number_input("እንግሊዝኛ ስም ቁጥር:",   value=(fn_idx+1) if fn_idx else 6,            min_value=1)
        with c2:
            dob_n = st.number_input("የትውልድ ቀን ቁጥር:",    value=det('date_birth', 8),                    min_value=1)
            sex_n = st.number_input("ፆታ ቁጥር:",           value=det('sex', 10),                          min_value=1)
        with c3:
            exp_n = st.number_input("የሚያበቃበት ቀን ቁጥር:",  value=det('date_expiry', 12),                  min_value=1)

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

    step = st.select_slider("የቦታ እርምጃ (px):", options=[1, 2, 5, 10, 20], value=5)

    # Position pad + Size controls side by side
    col_move, col_size = st.columns([1, 1])

    with col_move:
        st.markdown("**📍 ቦታ ማንቀሳቀሻ**")
        col_pad, col_ctrl, col_pad2 = st.columns([1, 2, 1])
        with col_ctrl:
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c2:
                st.button("▲", on_click=move, args=(sel,'y',-step), key="up",    use_container_width=True)
            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1:
                st.button("◄", on_click=move, args=(sel,'x',-step), key="left",  use_container_width=True)
            with r2c2:
                pos_txt = f"({st.session_state.pos[f'{sel}_x']}, {st.session_state.pos[f'{sel}_y']})"
                st.markdown(f"<div style='text-align:center;font-size:11px;color:#888;padding:6px'>{pos_txt}</div>",
                            unsafe_allow_html=True)
            with r2c3:
                st.button("►", on_click=move, args=(sel,'x', step), key="right", use_container_width=True)
            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c2:
                st.button("▼", on_click=move, args=(sel,'y', step), key="down",  use_container_width=True)

    with col_size:
        st.markdown("**🔡 ፊደል መጠን**")
        cur_size = st.session_state.size[sel]
        sc1, sc2, sc3 = st.columns([1, 2, 1])
        with sc1:
            st.button("➖", on_click=resize, args=(sel, -1), key="sz_minus", use_container_width=True)
        with sc2:
            st.markdown(
                f"<div style='text-align:center;font-size:28px;font-weight:bold;"
                f"padding:4px;color:#333'>{cur_size}px</div>",
                unsafe_allow_html=True
            )
        with sc3:
            st.button("➕", on_click=resize, args=(sel,  1), key="sz_plus",  use_container_width=True)

        # Fast size jump
        new_size = st.slider(f"", 10, 72, cur_size, key=f"sz_sl_{sel}")
        if new_size != cur_size:
            st.session_state.size[sel] = new_size

    # Expanded sliders for all fields
    with st.expander("🎛️ Slider ማስተካከያ (ሁሉም fields)"):
        for key, label in field_labels.items():
            st.markdown(f"**{label}**")
            ca, cb, cc = st.columns(3)
            with ca:
                nx = st.slider(f"X", 100, 1200, st.session_state.pos[f'{key}_x'], key=f"sx_{key}")
                st.session_state.pos[f'{key}_x'] = nx
            with cb:
                ny = st.slider(f"Y", 150, 780,  st.session_state.pos[f'{key}_y'], key=f"sy_{key}")
                st.session_state.pos[f'{key}_y'] = ny
            with cc:
                ns = st.slider(f"Size", 10, 72, st.session_state.size[key],        key=f"ss_{key}")
                st.session_state.size[key] = ns

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        if st.button("↩️ ቦታዎችን ወደ ነባሪ መልስ", use_container_width=True):
            st.session_state.pos  = DEFAULT_SETTINGS['pos'].copy()
            st.session_state.size = DEFAULT_SETTINGS['size'].copy()
            st.rerun()
    with col_r2:
        # Quick save shortcut
        if st.button("💾 አሁን Save (Firebase)", use_container_width=True):
            if firebase_save({'pos': st.session_state.pos, 'size': st.session_state.size}):
                st.success("✅ Settings saved!")
            else:
                st.error("❌ Save failed")

    st.divider()

    # ── ደረጃ 4: Generate ───────────────────────────────────────
    st.markdown("### 🖼️ ደረጃ 4: መታወቂያ አዘጋጅ")

    if st.button("✅ መታወቂያውን አዘጋጅ / አድስ", type="primary", use_container_width=True):
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

                # ── Photo ──────────────────────────────────────────
                h_id, w_id = id_only.shape[:2]
                photo = id_only[int(h_id*0.064):int(h_id*0.430),
                                int(w_id*0.240):int(w_id*0.725)]
                photo_pil = Image.fromarray(cv2.cvtColor(photo, cv2.COLOR_BGR2RGB)).resize((190, 240))
                bg.paste(photo_pil, (105, 165))

                # ── FAN / Barcode — smart detection ────────────────
                fan_crop = find_fan_box(id_only)
                if fan_crop is not None and fan_crop.size > 0:
                    fan_pil = Image.fromarray(cv2.cvtColor(fan_crop, cv2.COLOR_BGR2RGB))
                    fan_pil = fan_pil.resize((480, 70))
                    bg.paste(fan_pil, (575, 645))
                else:
                    st.warning("⚠️ ባር ኮዱ ሳጥን ሊገኝ አልቻለም — FAN ሳይቀመጥ ይቀጥላል")

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
        st.image(Image.open(BG_PATH), caption="Template", use_container_width=True)
    except:
        st.warning("Template ምስል (1000123189.jpg) አልተገኘም")
