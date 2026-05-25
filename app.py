import streamlit as st
import fitz
from PIL import Image, ImageDraw, UnidentifiedImageError
import io
import tempfile
import os
import json
import shutil
from pathlib import Path
from datetime import datetime

from streamlit_image_coordinates import streamlit_image_coordinates

from pdf_backend import (
    render_page,
    find_signature_areas,
    place_signature,
    pt_to_px,
    px_to_pt,
    get_page_count,
    process_signature_image,
    resize_signature_to_box,
    rembg_is_available,
    clamp_signature_position,
    display_click_to_signature_top_left_pt,
)

st.set_page_config(page_title="PDF Signer", page_icon="✍️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #f0f0f0; }
.stApp { background: #0a0a0a; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }

.app-header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 2.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid #1e1e1e; }
.app-logo { font-family: 'Syne', sans-serif; font-size: 2.2rem; font-weight: 800; color: #fff; letter-spacing: -0.03em; line-height: 1; }
.app-logo span { color: #c8ff00; }
.app-subtitle { font-size: 0.75rem; font-weight: 400; color: #555; letter-spacing: 0.12em; text-transform: uppercase; }

section[data-testid="stSidebar"] { background: #0f0f0f !important; border-right: 1px solid #1a1a1a !important; padding-top: 1rem; }
section[data-testid="stSidebar"] .block-container { padding: 1.5rem 1.2rem !important; }
.sidebar-label { font-family: 'Syne', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: #c8ff00; margin-bottom: 0.6rem; display: block; }

.stButton > button { background: #c8ff00 !important; color: #0a0a0a !important; border: none !important; border-radius: 2px !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; font-size: 0.8rem !important; letter-spacing: 0.08em !important; padding: 0.65rem 1.4rem !important; text-transform: uppercase !important; width: 100% !important; }
.stButton > button:hover { background: #fff !important; transform: translateY(-1px) !important; box-shadow: 0 4px 20px rgba(200,255,0,0.2) !important; }
.stDownloadButton > button { background: transparent !important; color: #c8ff00 !important; border: 1px solid #c8ff00 !important; border-radius: 2px !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; font-size: 0.8rem !important; text-transform: uppercase !important; width: 100% !important; }
.stDownloadButton > button:hover { background: #c8ff00 !important; color: #0a0a0a !important; }

.msg { padding: 0.8rem 1rem; border-radius: 2px; font-size: 0.82rem; margin-bottom: 1rem; line-height: 1.5; }
.msg-info    { background: #111; border-left: 3px solid #c8ff00; color: #888; }
.msg-success { background: #0d1a00; border-left: 3px solid #c8ff00; color: #a8d400; }
.msg-error   { background: #1a0000; border-left: 3px solid #ff4444; color: #ff8888; }
.msg-warning { background: #1a1000; border-left: 3px solid #ff9900; color: #ffbb55; }

.section-title { font-family: 'Syne', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: #c8ff00; margin-bottom: 0.8rem; }
.divider { border: none; border-top: 1px solid #1a1a1a; margin: 1.5rem 0; }
.stSlider > div > div > div { background: #c8ff00 !important; }
.stNumberInput input { background: #111 !important; border: 1px solid #222 !important; color: #f0f0f0 !important; border-radius: 2px !important; }
.stRadio > div { gap: 0.4rem; }
.stRadio label { font-size: 0.85rem !important; color: #ccc !important; }
#MainMenu, footer, header { visibility: hidden; }
button[kind="headerNoPadding"], [data-testid="collapsedControl"] { display: flex !important; visibility: visible !important; opacity: 1 !important; color: #c8ff00 !important; }
[data-testid="stTickBarMin"], [data-testid="stTickBarMax"] { display: none !important; }
.arrow-btn button { padding: 0.3rem 0.1rem !important; font-size: 0.9rem !important; min-width: 0 !important; }
</style>
""", unsafe_allow_html=True)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)
LAST_PDF_PATH  = UPLOAD_DIR / "last_pdf.pdf"
LAST_SIG_PATH  = UPLOAD_DIR / "last_signature.png"
META_PATH      = UPLOAD_DIR / "meta.json"


def save_session(pdf_bytes=None, sig_img=None, pdf_name="", sig_name=""):
    meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    if pdf_bytes is not None:
        LAST_PDF_PATH.write_bytes(pdf_bytes)
        meta["pdf_name"] = pdf_name
        meta["pdf_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    if sig_img is not None:
        sig_img.convert("RGBA").save(LAST_SIG_PATH, format="PNG")
        meta["sig_name"] = sig_name
        meta["sig_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False))


def clear_session():
    st.session_state.pdf_bytes = None
    st.session_state.sig_img_raw = None
    st.session_state._restored = {}
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(exist_ok=True)


def load_session():
    restored = {}
    if st.session_state.pdf_bytes is None and LAST_PDF_PATH.exists():
        st.session_state.pdf_bytes = LAST_PDF_PATH.read_bytes()
        restored["pdf"] = True
    if st.session_state.sig_img_raw is None and LAST_SIG_PATH.exists():
        st.session_state.sig_img_raw = Image.open(LAST_SIG_PATH).convert("RGBA")
        restored["sig"] = True
    if restored and META_PATH.exists():
        restored["meta"] = json.loads(META_PATH.read_text())
    return restored


DPI = 150
DISPLAY_WIDTH = 700
NUDGE_PT = 5.0

_SESSION_DEFAULTS = {
    "pdf_bytes": None,
    "sig_img_raw": None,
    "page_number": 0,
    "sig_w_pt": 150,
    "sig_h_pt": 60,
    "remove_bg": False,
    "use_rembg": True,
    "white_threshold": 245,
    "opacity": 1.0,
    "rotation": 0.0,
    "trim_edges": True,
    "preserve_aspect": True,
}
for k, v in _SESSION_DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

if "session_loaded" not in st.session_state:
    st.session_state.session_loaded = True
    st.session_state._restored = load_session()


def validate_pdf(pdf_bytes):
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return False, "The PDF file is empty (0 pages)."
        doc.close()
        return True, None
    except Exception:
        return False, "Invalid or corrupted PDF file."


def validate_image(img_file):
    try:
        img = Image.open(img_file)
        img.verify()
        img_file.seek(0)
        img = Image.open(img_file)
        return True, img, None
    except UnidentifiedImageError:
        return False, None, "Invalid image file."
    except Exception:
        return False, None, "Corrupted image file."


def checkerboard_background(img, cell=8):
    img = img.convert("RGBA")
    w, h = img.size
    bg = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(bg)
    for y in range(0, h, cell):
        for x in range(0, w, cell):
            shade = 55 if ((x // cell) + (y // cell)) % 2 == 0 else 35
            draw.rectangle([x, y, x + cell, y + cell], fill=(shade, shade, shade))
    bg.paste(img, (0, 0), img)
    return bg


def get_processed_signature():
    info = {}
    processed = process_signature_image(
        st.session_state.sig_img_raw,
        remove_background=st.session_state.remove_bg,
        use_rembg=st.session_state.use_rembg,
        white_threshold=int(st.session_state.white_threshold),
        opacity=float(st.session_state.opacity),
        rotation_degrees=float(st.session_state.rotation),
        trim_transparent=st.session_state.trim_edges,
        info=info,
    )
    return processed, info


def render_with_preview(page_img, sig_img, x_px, y_px, w_px, h_px, preserve_aspect=True):
    preview = page_img.copy().convert("RGBA")
    sig = resize_signature_to_box(sig_img, max(1, int(w_px)), max(1, int(h_px)), preserve_aspect_ratio=preserve_aspect)
    preview.paste(sig, (int(x_px), int(y_px)), sig)
    return preview.convert("RGB")


def place_signature_from_bytes(pdf_bytes, page_number, x_pt, y_pt, sig_img, width_pt=150, height_pt=60, preserve_aspect_ratio=True):
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        sig_path = os.path.join(tmp, "signature.png")
        out_path = os.path.join(tmp, "signed.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        sig_img.convert("RGBA").save(sig_path, format="PNG")
        place_signature(pdf_path, page_number, x_pt, y_pt, sig_path,
                        width=width_pt, height=height_pt,
                        preserve_aspect_ratio=preserve_aspect_ratio, output_path=out_path)
        with open(out_path, "rb") as f:
            return f.read()


def default_manual_placement(page_width_pt, page_height_pt):
    return page_width_pt * 0.1, page_height_pt * 0.7


def ensure_manual_placement(page_width_pt, page_height_pt, sig_w_pt, sig_h_pt):
    if "manual_x_pt" not in st.session_state or "manual_y_pt" not in st.session_state:
        dx, dy = default_manual_placement(page_width_pt, page_height_pt)
        st.session_state.manual_x_pt, st.session_state.manual_y_pt = dx, dy
    x_pt, y_pt = clamp_signature_position(
        st.session_state.manual_x_pt, st.session_state.manual_y_pt,
        page_width_pt, page_height_pt, sig_w_pt, sig_h_pt)
    st.session_state.manual_x_pt = x_pt
    st.session_state.manual_y_pt = y_pt


def set_manual_placement(x_pt, y_pt, page_width_pt, page_height_pt, sig_w_pt, sig_h_pt):
    x_pt, y_pt = clamp_signature_position(x_pt, y_pt, page_width_pt, page_height_pt, sig_w_pt, sig_h_pt)
    st.session_state.manual_x_pt = x_pt
    st.session_state.manual_y_pt = y_pt


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="sidebar-label">01 · Files</span>', unsafe_allow_html=True)

    st.caption("📄 PDF Document")
    pdf_file = st.file_uploader("PDF Document", type=["pdf"], label_visibility="collapsed")
    if pdf_file:
        pdf_bytes = pdf_file.read()
        is_valid, err = validate_pdf(pdf_bytes)
        if not is_valid:
            st.markdown(f'<div class="msg msg-error">❌ {err}</div>', unsafe_allow_html=True)
            st.session_state.pdf_bytes = None
        else:
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.page_number = 0
            save_session(pdf_bytes=pdf_bytes, pdf_name=pdf_file.name)

    st.caption("✍️ Signature Image")
    sig_file = st.file_uploader("Signature Image (PNG/JPG)", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
    if sig_file:
        is_valid, img, err = validate_image(sig_file)
        if not is_valid:
            st.markdown(f'<div class="msg msg-error">❌ {err}</div>', unsafe_allow_html=True)
            st.session_state.sig_img_raw = None
        else:
            st.session_state.sig_img_raw = img
            save_session(sig_img=img, sig_name=sig_file.name)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    if st.button("🗑 Clear Files"):
        clear_session()
        st.rerun()

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">02 · Signature Processing</span>', unsafe_allow_html=True)
    st.session_state.remove_bg = st.checkbox("Remove background", value=st.session_state.remove_bg)
    st.session_state.use_rembg = st.checkbox("Use rembg when available", value=st.session_state.use_rembg, disabled=not st.session_state.remove_bg)
    _bg_dis = not st.session_state.remove_bg
    st.caption("Background threshold")
    _bl, _bm, _br = st.columns([3, 4, 3])
    with _bl:
        if st.button("◀", key="bg_l", disabled=_bg_dis):
            st.session_state.white_threshold = max(200, int(st.session_state.white_threshold) - 5)
            st.rerun()
    with _bm:
        _thr_color = "#555" if _bg_dis else "#c8ff00"
        st.markdown(f'<p style="text-align:center;color:{_thr_color};font-size:1rem;font-weight:700;margin:0.55rem 0;">{int(st.session_state.white_threshold)}</p>', unsafe_allow_html=True)
    with _br:
        if st.button("▶", key="bg_r", disabled=_bg_dis):
            st.session_state.white_threshold = min(255, int(st.session_state.white_threshold) + 5)
            st.rerun()
    st.caption("Opacity")
    _ol, _om, _or_ = st.columns([3, 4, 3])
    with _ol:
        if st.button("◀", key="op_l"):
            st.session_state.opacity = max(0.1, round(float(st.session_state.opacity) - 0.05, 2))
            st.rerun()
    with _om:
        st.markdown(f'<p style="text-align:center;color:#c8ff00;font-size:1rem;font-weight:700;margin:0.55rem 0;">{st.session_state.opacity:.2f}</p>', unsafe_allow_html=True)
    with _or_:
        if st.button("▶", key="op_r"):
            st.session_state.opacity = min(1.0, round(float(st.session_state.opacity) + 0.05, 2))
            st.rerun()

    st.caption("Rotation (degrees)")
    _rl, _rm, _rr = st.columns([3, 4, 3])
    with _rl:
        if st.button("◀", key="rot_l"):
            st.session_state.rotation = max(-45, int(st.session_state.rotation) - 1)
            st.rerun()
    with _rm:
        st.markdown(f'<p style="text-align:center;color:#c8ff00;font-size:1rem;font-weight:700;margin:0.55rem 0;">{int(st.session_state.rotation)}°</p>', unsafe_allow_html=True)
    with _rr:
        if st.button("▶", key="rot_r"):
            st.session_state.rotation = min(45, int(st.session_state.rotation) + 1)
            st.rerun()
    st.session_state.trim_edges = st.checkbox("Trim empty edges", value=st.session_state.trim_edges)
    st.session_state.preserve_aspect = st.checkbox("Preserve aspect ratio", value=st.session_state.preserve_aspect)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">03 · Placement Mode</span>', unsafe_allow_html=True)
    mode = st.radio("", ["Auto-detect", "Manual"], label_visibility="collapsed")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">04 · Signature Size</span>', unsafe_allow_html=True)
    st.caption("Width (pt)")
    st.session_state.sig_w_pt = st.slider("W", 80, 300, int(st.session_state.sig_w_pt), label_visibility="collapsed")
    st.caption("Height (pt)")
    st.session_state.sig_h_pt = st.slider("H", 30, 120, int(st.session_state.sig_h_pt), label_visibility="collapsed")

    if st.session_state.sig_img_raw:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown('<span class="sidebar-label">Signature Preview</span>', unsafe_allow_html=True)
        raw_thumb = st.session_state.sig_img_raw.copy().convert("RGBA")
        raw_thumb.thumbnail((200, 100))
        st.image(checkerboard_background(raw_thumb), width=200)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div>
        <div class="app-logo">PDF <span>Signer</span></div>
    </div>
    <div class="app-subtitle">ATA Builders Lab &nbsp;·&nbsp; Document Signing Tool</div>
</div>
""", unsafe_allow_html=True)

_restored = st.session_state.get("_restored", {})
if _restored:
    meta = _restored.get("meta", {})
    parts = []
    if _restored.get("pdf") and meta.get("pdf_name"):
        parts.append(f"📄 {meta['pdf_name']} ({meta.get('pdf_saved', '')})")
    if _restored.get("sig") and meta.get("sig_name"):
        parts.append(f"✍️ {meta['sig_name']} ({meta.get('sig_saved', '')})")
    if parts:
        st.markdown(f'<div class="msg msg-info">📂 Restored from last session: {" · ".join(parts)}</div>', unsafe_allow_html=True)

if not st.session_state.pdf_bytes:
    st.markdown('<div class="msg msg-info">⬅ Upload a PDF document from the sidebar to get started.</div>', unsafe_allow_html=True)
    st.stop()

if not st.session_state.sig_img_raw:
    st.markdown('<div class="msg msg-info">⬅ Upload a signature image from the sidebar to continue.</div>', unsafe_allow_html=True)
    st.stop()

try:
    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
    total_pages = get_page_count(doc)
except Exception:
    st.markdown('<div class="msg msg-error">❌ Failed to open PDF.</div>', unsafe_allow_html=True)
    st.stop()

w_pt = st.session_state.sig_w_pt
h_pt = st.session_state.sig_h_pt
preserve = st.session_state.preserve_aspect

try:
    processed_sig, process_info = get_processed_signature()
except Exception as exc:
    st.error(f"Could not process signature image: {exc}")
    doc.close()
    st.stop()

if st.session_state.remove_bg:
    if (st.session_state.use_rembg and not rembg_is_available()) or process_info.get("rembg_failed"):
        st.markdown('<div class="msg msg-warning">rembg is not installed; using Pillow fallback.</div>', unsafe_allow_html=True)

col_main, col_right = st.columns([3, 1], gap="large")

with col_right:
    st.markdown('<div class="section-title">Navigation</div>', unsafe_allow_html=True)
    page_num = st.number_input("Go to page", 1, total_pages, st.session_state.page_number + 1, step=1, label_visibility="collapsed") - 1
    st.session_state.page_number = page_num
    st.caption(f"Page {st.session_state.page_number + 1} of {total_pages}")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Processed Signature</div>', unsafe_allow_html=True)
    proc_thumb = processed_sig.copy()
    proc_thumb.thumbnail((200, 100))
    st.image(checkerboard_background(proc_thumb), width=200)

try:
    page_img = render_page(doc, st.session_state.page_number, dpi=DPI)
except Exception:
    st.markdown('<div class="msg msg-error">❌ Failed to render page.</div>', unsafe_allow_html=True)
    doc.close()
    st.stop()

page_rect = doc[st.session_state.page_number].rect

with col_main:
    st.markdown('<div class="section-title">PDF Preview</div>', unsafe_allow_html=True)

    if mode == "Auto-detect":
        try:
            areas = find_signature_areas(doc, st.session_state.page_number)
        except Exception:
            areas = []

        if not areas:
            st.markdown('<div class="msg msg-warning">⚠ No signature areas detected. Switch to Manual mode.</div>', unsafe_allow_html=True)
            st.image(page_img, width=DISPLAY_WIDTH)
        else:
            st.markdown(f'<div class="msg msg-info">🔍 Found <strong>{len(areas)}</strong> signature area(s). Select one:</div>', unsafe_allow_html=True)
            area_labels = [f"Area {i+1} — {a['reason']}" for i, a in enumerate(areas)]
            selected = st.radio("", area_labels, label_visibility="collapsed")
            idx = area_labels.index(selected)
            area = areas[idx]
            x_pt_val = float(area["x"])
            y_pt_val = float(area["y"])

            try:
                preview = render_with_preview(page_img, processed_sig,
                                              pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                                              pt_to_px(w_pt, DPI), pt_to_px(h_pt, DPI),
                                              preserve_aspect=preserve)
                st.image(preview, width=DISPLAY_WIDTH)
            except Exception:
                st.image(page_img, width=DISPLAY_WIDTH)

            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            if st.button("✦ SIGN & DOWNLOAD PDF"):
                try:
                    with st.spinner("Signing..."):
                        signed = place_signature_from_bytes(
                            st.session_state.pdf_bytes, st.session_state.page_number,
                            x_pt_val, y_pt_val, processed_sig, w_pt, h_pt,
                            preserve_aspect_ratio=preserve)
                    st.markdown('<div class="msg msg-success">✔ Signature placed successfully.</div>', unsafe_allow_html=True)
                    st.download_button("⬇ DOWNLOAD SIGNED PDF", data=signed, file_name="signed_document.pdf", mime="application/pdf")
                except Exception as exc:
                    st.markdown(f'<div class="msg msg-error">❌ Failed to sign PDF: {exc}</div>', unsafe_allow_html=True)

    else:
        page_w = float(page_rect.width)
        page_h = float(page_rect.height)
        ensure_manual_placement(page_w, page_h, w_pt, h_pt)

        st.markdown('<div class="msg msg-info">Click on the PDF preview to place the signature, or use X/Y inputs below.</div>', unsafe_allow_html=True)

        x_pt_val = float(st.session_state.manual_x_pt)
        y_pt_val = float(st.session_state.manual_y_pt)

        try:
            preview = render_with_preview(page_img, processed_sig,
                                          pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                                          pt_to_px(w_pt, DPI), pt_to_px(h_pt, DPI),
                                          preserve_aspect=preserve)
        except Exception:
            preview = page_img

        display_height = int(page_img.height * DISPLAY_WIDTH / page_img.width)
        click = streamlit_image_coordinates(preview, width=DISPLAY_WIDTH, key="manual_preview_click")

        if click is not None and click.get("x") is not None and click.get("y") is not None:
            click_key = (int(click["x"]), int(click["y"]), st.session_state.page_number)
            if st.session_state.get("manual_last_click") != click_key:
                st.session_state.manual_last_click = click_key
                new_x, new_y = display_click_to_signature_top_left_pt(
                    float(click["x"]), float(click["y"]),
                    DISPLAY_WIDTH, display_height,
                    page_img.width, page_img.height,
                    w_pt, h_pt, page_w, page_h, dpi=DPI)
                set_manual_placement(new_x, new_y, page_w, page_h, w_pt, h_pt)
                st.rerun()

        c1, c2 = st.columns(2)
        with c1:
            st.caption("X position (pt)")
            new_x = st.number_input("X", 0.0, page_w, float(st.session_state.manual_x_pt), step=5.0, label_visibility="collapsed")
        with c2:
            st.caption("Y position (pt)")
            new_y = st.number_input("Y", 0.0, page_h, float(st.session_state.manual_y_pt), step=5.0, label_visibility="collapsed")

        if new_x != st.session_state.manual_x_pt or new_y != st.session_state.manual_y_pt:
            set_manual_placement(new_x, new_y, page_w, page_h, w_pt, h_pt)
            st.rerun()

        x_pt_val = float(st.session_state.manual_x_pt)
        y_pt_val = float(st.session_state.manual_y_pt)

        n1, n2, n3, n4, n5 = st.columns(5)
        with n1:
            if st.button("← Left"):
                set_manual_placement(x_pt_val - NUDGE_PT, y_pt_val, page_w, page_h, w_pt, h_pt)
                st.rerun()
        with n2:
            if st.button("Right →"):
                set_manual_placement(x_pt_val + NUDGE_PT, y_pt_val, page_w, page_h, w_pt, h_pt)
                st.rerun()
        with n3:
            if st.button("↑ Up"):
                set_manual_placement(x_pt_val, y_pt_val - NUDGE_PT, page_w, page_h, w_pt, h_pt)
                st.rerun()
        with n4:
            if st.button("Down ↓"):
                set_manual_placement(x_pt_val, y_pt_val + NUDGE_PT, page_w, page_h, w_pt, h_pt)
                st.rerun()
        with n5:
            if st.button("Reset"):
                dx, dy = default_manual_placement(page_w, page_h)
                set_manual_placement(dx, dy, page_w, page_h, w_pt, h_pt)
                st.session_state.manual_last_click = None
                st.rerun()

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        if st.button("✦ SIGN & DOWNLOAD PDF"):
            try:
                with st.spinner("Signing..."):
                    signed = place_signature_from_bytes(
                        st.session_state.pdf_bytes, st.session_state.page_number,
                        x_pt_val, y_pt_val, processed_sig, w_pt, h_pt,
                        preserve_aspect_ratio=preserve)
                st.markdown('<div class="msg msg-success">✔ Signature placed successfully.</div>', unsafe_allow_html=True)
                st.download_button("⬇ DOWNLOAD SIGNED PDF", data=signed, file_name="signed_document.pdf", mime="application/pdf")
            except Exception as exc:
                st.markdown(f'<div class="msg msg-error">❌ Failed to sign PDF: {exc}</div>', unsafe_allow_html=True)

doc.close()