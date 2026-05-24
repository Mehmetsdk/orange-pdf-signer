import streamlit as st
import fitz
from PIL import Image, UnidentifiedImageError
import io
import tempfile
import os

from pdf_backend import (
    render_page,
    find_signature_areas,
    place_signature,
    pt_to_px,
    px_to_pt,
    get_page_count,
)

st.set_page_config(page_title="PDF Signer", page_icon="✍️", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #0a0a0a;
    color: #f0f0f0;
}

.stApp { background: #0a0a0a; }

.block-container {
    padding: 2rem 2.5rem !important;
    max-width: 1400px !important;
}

/* ── HEADER ── */
.app-header {
    display: flex;
    align-items: baseline;
    gap: 1rem;
    margin-bottom: 2.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid #1e1e1e;
}
.app-logo {
    font-family: 'Syne', sans-serif;
    font-size: 2.2rem;
    font-weight: 800;
    color: #fff;
    letter-spacing: -0.03em;
    line-height: 1;
}
.app-logo span { color: #c8ff00; }
.app-subtitle {
    font-size: 0.75rem;
    font-weight: 400;
    color: #555;
    letter-spacing: 0.12em;
    text-transform: uppercase;
}

/* ── SIDEBAR ── */
section[data-testid="stSidebar"] {
    background: #0f0f0f !important;
    border-right: 1px solid #1a1a1a !important;
    padding-top: 1rem;
}
section[data-testid="stSidebar"] .block-container {
    padding: 1.5rem 1.2rem !important;
}

.sidebar-section {
    margin-bottom: 1.5rem;
}
.sidebar-label {
    font-family: 'Syne', sans-serif;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #c8ff00;
    margin-bottom: 0.6rem;
    display: block;
}

/* ── BUTTONS ── */
.stButton > button {
    background: #c8ff00 !important;
    color: #0a0a0a !important;
    border: none !important;
    border-radius: 2px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.08em !important;
    padding: 0.65rem 1.4rem !important;
    transition: all 0.15s !important;
    text-transform: uppercase !important;
    width: 100% !important;
}
.stButton > button:hover {
    background: #fff !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px rgba(200,255,0,0.2) !important;
}

/* ── DOWNLOAD BUTTON ── */
.stDownloadButton > button {
    background: transparent !important;
    color: #c8ff00 !important;
    border: 1px solid #c8ff00 !important;
    border-radius: 2px !important;
    font-family: 'Syne', sans-serif !important;
    font-weight: 700 !important;
    font-size: 0.8rem !important;
    letter-spacing: 0.08em !important;
    padding: 0.65rem 1.4rem !important;
    text-transform: uppercase !important;
    width: 100% !important;
}
.stDownloadButton > button:hover {
    background: #c8ff00 !important;
    color: #0a0a0a !important;
}

/* ── MESSAGES ── */
.msg {
    padding: 0.8rem 1rem;
    border-radius: 2px;
    font-size: 0.82rem;
    margin-bottom: 1rem;
    line-height: 1.5;
}
.msg-info    { background: #111; border-left: 3px solid #c8ff00; color: #888; }
.msg-success { background: #0d1a00; border-left: 3px solid #c8ff00; color: #a8d400; }
.msg-error   { background: #1a0000; border-left: 3px solid #ff4444; color: #ff8888; }
.msg-warning { background: #1a1000; border-left: 3px solid #ff9900; color: #ffbb55; }

/* ── SECTION TITLE ── */
.section-title {
    font-family: 'Syne', sans-serif;
    font-size: 0.65rem;
    font-weight: 700;
    letter-spacing: 0.2em;
    text-transform: uppercase;
    color: #c8ff00;
    margin-bottom: 0.8rem;
}

/* ── DIVIDER ── */
.divider { border: none; border-top: 1px solid #1a1a1a; margin: 1.5rem 0; }

/* ── RADIO ── */
.stRadio > div { gap: 0.4rem; }
.stRadio label { font-size: 0.85rem !important; color: #ccc !important; }

/* ── SLIDER ── */
.stSlider > div > div > div { background: #c8ff00 !important; }

/* ── NUMBER INPUT ── */
.stNumberInput input {
    background: #111 !important;
    border: 1px solid #222 !important;
    color: #f0f0f0 !important;
    border-radius: 2px !important;
}

/* ── FILE UPLOADER ── */
.stFileUploader {
    background: #111 !important;
    border: 1px dashed #222 !important;
    border-radius: 4px !important;
}

/* ── STATS ROW ── */
.stats-row {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.stat-card {
    background: #111;
    border: 1px solid #1e1e1e;
    border-radius: 4px;
    padding: 0.8rem 1rem;
    flex: 1;
}
.stat-label { font-size: 0.65rem; color: #555; text-transform: uppercase; letter-spacing: 0.1em; }
.stat-value { font-family: 'Syne', sans-serif; font-size: 1.2rem; font-weight: 700; color: #fff; margin-top: 0.2rem; }

/* ── AREA SELECTOR ── */
.area-label {
    background: #111;
    border: 1px solid #1e1e1e;
    border-radius: 3px;
    padding: 0.5rem 0.8rem;
    font-size: 0.8rem;
    color: #aaa;
    margin-bottom: 0.4rem;
    cursor: pointer;
    transition: all 0.15s;
}
.area-label:hover { border-color: #c8ff00; color: #fff; }

/* hide streamlit branding */
#MainMenu, footer, header { visibility: hidden; }

/* hide slider min/max labels */
.stSlider [data-testid="stTickBarMin"],
.stSlider [data-testid="stTickBarMax"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)


# ── Helpers ──────────────────────────────────────────────────────────────────

def place_signature_from_bytes(pdf_bytes, page_number, x_pt, y_pt, sig_img, width_pt=150, height_pt=60):
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        sig_path = os.path.join(tmp, "sig.png")
        out_path = os.path.join(tmp, "signed.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        sig_img.convert("RGBA").save(sig_path, format="PNG")
        place_signature(pdf_path, page_number, x_pt, y_pt, sig_path,
                        width=width_pt, height=height_pt, output_path=out_path)
        with open(out_path, "rb") as f:
            return f.read()


def render_with_preview(page_img, sig_img, x_px, y_px, w_px, h_px):
    preview = page_img.copy().convert("RGBA")
    sig = sig_img.convert("RGBA").resize((max(1, int(w_px)), max(1, int(h_px))), Image.LANCZOS)
    preview.paste(sig, (int(x_px), int(y_px)), sig)
    return preview.convert("RGB")


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


# ── Session state ─────────────────────────────────────────────────────────────
for k, v in {"pdf_bytes": None, "sig_img": None, "page_number": 0,
              "sig_w_pt": 150, "sig_h_pt": 60}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<span class="sidebar-label">01 · Files</span>', unsafe_allow_html=True)

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

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    sig_file = st.file_uploader("Signature Image", type=["png", "jpg", "jpeg"], label_visibility="collapsed")
    if sig_file:
        is_valid, img, err = validate_image(sig_file)
        if not is_valid:
            st.markdown(f'<div class="msg msg-error">❌ {err}</div>', unsafe_allow_html=True)
            st.session_state.sig_img = None
        else:
            st.session_state.sig_img = img

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">02 · Mode</span>', unsafe_allow_html=True)
    mode = st.radio("", ["Auto-detect", "Manual"], label_visibility="collapsed")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">03 · Size</span>', unsafe_allow_html=True)
    st.caption("Width (pt)")
    st.session_state.sig_w_pt = st.slider("W", 80, 300, st.session_state.sig_w_pt, label_visibility="collapsed")
    st.caption("Height (pt)")
    st.session_state.sig_h_pt = st.slider("H", 30, 120, st.session_state.sig_h_pt, label_visibility="collapsed")

    if st.session_state.sig_img:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown('<span class="sidebar-label">Signature</span>', unsafe_allow_html=True)
        thumb = st.session_state.sig_img.copy().convert("RGBA")
        thumb.thumbnail((220, 90))
        bg = Image.new("RGB", thumb.size, (17, 17, 17))
        bg.paste(thumb, mask=thumb.split()[3])
        st.image(bg, use_container_width=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <div>
        <div class="app-logo">PDF <span>Signer</span></div>
    </div>
    <div class="app-subtitle">ATA Builders Lab &nbsp;·&nbsp; Document Signing Tool</div>
</div>
""", unsafe_allow_html=True)

# ── Guards ────────────────────────────────────────────────────────────────────
if not st.session_state.pdf_bytes:
    st.markdown('<div class="msg msg-info">⬅ Upload a PDF document from the sidebar to get started.</div>', unsafe_allow_html=True)
    st.stop()
if not st.session_state.sig_img:
    st.markdown('<div class="msg msg-info">⬅ Upload a signature image from the sidebar to continue.</div>', unsafe_allow_html=True)
    st.stop()

# ── Load PDF ──────────────────────────────────────────────────────────────────
try:
    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
    total_pages = get_page_count(doc)
except Exception:
    st.markdown('<div class="msg msg-error">❌ Failed to open PDF.</div>', unsafe_allow_html=True)
    st.stop()

DPI = 150
col_main, col_right = st.columns([3, 1], gap="large")

with col_right:
    st.markdown('<div class="section-title">Navigation</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="stats-row">
        <div class="stat-card">
            <div class="stat-label">Page</div>
            <div class="stat-value">{st.session_state.page_number + 1} / {total_pages}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    page_num = st.number_input("Go to page", 1, total_pages,
                               st.session_state.page_number + 1, step=1,
                               label_visibility="collapsed") - 1
    st.session_state.page_number = page_num

# ── Render page ───────────────────────────────────────────────────────────────
try:
    page_img = render_page(doc, st.session_state.page_number, dpi=DPI)
except Exception:
    st.markdown('<div class="msg msg-error">❌ Failed to render page.</div>', unsafe_allow_html=True)
    doc.close()
    st.stop()

page_rect = doc[st.session_state.page_number].rect
w_pt = st.session_state.sig_w_pt
h_pt = st.session_state.sig_h_pt

with col_main:
    st.markdown('<div class="section-title">PDF Preview</div>', unsafe_allow_html=True)

    # ── AUTO-DETECT ───────────────────────────────────────────────────────────
    if mode == "Auto-detect":
        try:
            areas = find_signature_areas(doc, st.session_state.page_number)
        except Exception:
            areas = []

        if not areas:
            st.markdown('<div class="msg msg-warning">⚠ No signature areas detected. Switch to Manual mode.</div>', unsafe_allow_html=True)
            st.image(page_img, width=700)
        else:
            st.markdown(f'<div class="msg msg-info">🔍 Found <strong>{len(areas)}</strong> signature area(s). Select one:</div>', unsafe_allow_html=True)
            area_labels = [f"Area {i+1} — {a['reason']}"
                           for i, a in enumerate(areas)]
            selected = st.radio("", area_labels, label_visibility="collapsed")
            idx = area_labels.index(selected)
            area = areas[idx]
            x_pt_val = float(area["x"])
            y_pt_val = float(area["y"])

            try:
                preview = render_with_preview(page_img, st.session_state.sig_img,
                                              pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                                              pt_to_px(w_pt, DPI), pt_to_px(h_pt, DPI))
                st.image(preview, width=700)
            except Exception:
                st.image(page_img, width=700)

            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            if st.button("✦ SIGN & DOWNLOAD PDF"):
                try:
                    with st.spinner("Signing..."):
                        signed = place_signature_from_bytes(
                            st.session_state.pdf_bytes, st.session_state.page_number,
                            x_pt_val, y_pt_val, st.session_state.sig_img, w_pt, h_pt)
                    st.markdown('<div class="msg msg-success">✔ Signature placed successfully.</div>', unsafe_allow_html=True)
                    st.download_button("⬇ DOWNLOAD SIGNED PDF", data=signed,
                                       file_name="signed_document.pdf", mime="application/pdf")
                except Exception:
                    st.markdown('<div class="msg msg-error">❌ Failed to sign PDF.</div>', unsafe_allow_html=True)

    # ── MANUAL ────────────────────────────────────────────────────────────────
    else:
        st.markdown('<div class="msg msg-info">Enter X/Y coordinates to place the signature.</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.caption("X position (pt)")
            x_pt_val = st.number_input("X", 0.0, float(page_rect.width),
                                       float(page_rect.width * 0.1), step=5.0,
                                       label_visibility="collapsed")
        with c2:
            st.caption("Y position (pt)")
            y_pt_val = st.number_input("Y", 0.0, float(page_rect.height),
                                       float(page_rect.height * 0.7), step=5.0,
                                       label_visibility="collapsed")
        try:
            preview = render_with_preview(page_img, st.session_state.sig_img,
                                          pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                                          pt_to_px(w_pt, DPI), pt_to_px(h_pt, DPI))
            st.image(preview, width=700)
        except Exception:
            st.image(page_img, width=700)

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        if st.button("✦ SIGN & DOWNLOAD PDF"):
            try:
                with st.spinner("Signing..."):
                    signed = place_signature_from_bytes(
                        st.session_state.pdf_bytes, st.session_state.page_number,
                        x_pt_val, y_pt_val, st.session_state.sig_img, w_pt, h_pt)
                st.markdown('<div class="msg msg-success">✔ Signature placed successfully.</div>', unsafe_allow_html=True)
                st.download_button("⬇ DOWNLOAD SIGNED PDF", data=signed,
                                   file_name="signed_document.pdf", mime="application/pdf")
            except Exception:
                st.markdown('<div class="msg msg-error">❌ Failed to sign PDF.</div>', unsafe_allow_html=True)

doc.close()
