import streamlit as st
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io
import os
import tempfile

# ─── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF Signer",
    page_icon="✍️",
    layout="wide",
)

# ─── Custom CSS ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background-color: #0f0f0f;
    color: #e8e8e8;
}

.stApp {
    background-color: #0f0f0f;
}

h1, h2, h3 {
    font-family: 'Space Mono', monospace !important;
}

.block-container {
    padding: 2rem 3rem;
    max-width: 1400px;
}

.stButton > button {
    background: #e8ff00 !important;
    color: #0f0f0f !important;
    border: none !important;
    border-radius: 0px !important;
    font-family: 'Space Mono', monospace !important;
    font-weight: 700 !important;
    font-size: 0.85rem !important;
    letter-spacing: 0.05em !important;
    padding: 0.6rem 1.5rem !important;
    transition: all 0.15s ease !important;
}

.stButton > button:hover {
    background: #ffffff !important;
    transform: translate(-2px, -2px);
    box-shadow: 4px 4px 0px #e8ff00 !important;
}

.stFileUploader {
    border: 1px solid #2a2a2a !important;
    padding: 1rem;
    background: #161616;
}

.stSlider > div > div {
    background: #e8ff00 !important;
}

.sig-area-btn {
    background: #1a1a1a;
    border: 1px solid #333;
    border-radius: 4px;
    padding: 0.75rem 1rem;
    margin-bottom: 0.5rem;
    cursor: pointer;
    transition: all 0.2s;
}

.sig-area-btn:hover {
    border-color: #e8ff00;
    background: #222;
}

.header-tag {
    font-family: 'Space Mono', monospace;
    font-size: 0.7rem;
    letter-spacing: 0.15em;
    color: #e8ff00;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}

.divider {
    border: none;
    border-top: 1px solid #222;
    margin: 1.5rem 0;
}

.info-box {
    background: #161616;
    border-left: 3px solid #e8ff00;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #aaa;
    margin-bottom: 1rem;
}

.success-box {
    background: #0d1f0d;
    border-left: 3px solid #4caf50;
    padding: 0.75rem 1rem;
    font-size: 0.85rem;
    color: #81c784;
}

section[data-testid="stSidebar"] {
    background: #111 !important;
    border-right: 1px solid #1e1e1e;
}
</style>
""", unsafe_allow_html=True)


# ─── Utility functions (from teammate's code) ─────────────────────────────

SIGNATURE_KEYWORDS = [
    "signature", "imza", "sign here", "buraya imza",
    "authorized signature", "yetkili imza", "imzası"
]


def render_page(doc: fitz.Document, page_number: int, dpi: int = 150) -> Image.Image:
    page = doc[page_number]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("png")
    return Image.open(io.BytesIO(img_bytes))


def find_signature_areas(doc: fitz.Document, page_number: int) -> list:
    page = doc[page_number]
    found = []

    for keyword in SIGNATURE_KEYWORDS:
        instances = page.search_for(keyword)
        for rect in instances:
            area = {
                "x": rect.x0,
                "y": rect.y1 + 2,
                "w": max(rect.width * 3, 150),
                "h": 40,
                "reason": f"Keyword: '{keyword}'"
            }
            found.append(area)

    paths = page.get_drawings()
    page_width = page.rect.width

    for path in paths:
        rect = path["rect"]
        width = rect.x1 - rect.x0
        height = rect.y1 - rect.y0
        if width > page_width * 0.2 and height < 5:
            area = {
                "x": rect.x0,
                "y": rect.y0 - 35,
                "w": width,
                "h": 35,
                "reason": "Signature line (horizontal)"
            }
            found.append(area)

    return found


def pt_to_px(pt_value: float, dpi: int = 150) -> float:
    return pt_value * (dpi / 72)


def px_to_pt(px_value: float, dpi: int = 150) -> float:
    return px_value * (72 / dpi)


def place_signature_on_doc(pdf_bytes, page_number, x_pt, y_pt,
                           sig_img: Image.Image, width_pt=150, height_pt=60):
    """Place signature and return signed PDF as bytes."""
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[page_number]

    sig_img = sig_img.convert("RGBA")
    sig_img = sig_img.resize((int(width_pt * 2), int(height_pt * 2)), Image.LANCZOS)

    img_bytes = io.BytesIO()
    sig_img.save(img_bytes, format="PNG")
    img_bytes.seek(0)

    rect = fitz.Rect(x_pt, y_pt, x_pt + width_pt, y_pt + height_pt)
    page.insert_image(rect, stream=img_bytes.read(), overlay=True)

    out = io.BytesIO()
    doc.save(out)
    doc.close()
    return out.getvalue()


def render_page_with_preview(page_img: Image.Image, sig_img: Image.Image,
                              x_px, y_px, w_px, h_px, dpi=150) -> Image.Image:
    """Overlay signature preview on rendered page image."""
    preview = page_img.copy().convert("RGBA")
    sig_resized = sig_img.convert("RGBA").resize((int(w_px), int(h_px)), Image.LANCZOS)
    preview.paste(sig_resized, (int(x_px), int(y_px)), sig_resized)
    return preview.convert("RGB")


def render_page_with_click_marker(page_img: Image.Image, x_px, y_px) -> Image.Image:
    """Draw a yellow crosshair at the click position."""
    preview = page_img.copy().convert("RGB")
    draw = ImageDraw.Draw(preview)
    r = 18
    draw.ellipse([x_px - r, y_px - r, x_px + r, y_px + r],
                 outline=(232, 255, 0), width=3)
    draw.line([x_px - r, y_px, x_px + r, y_px], fill=(232, 255, 0), width=2)
    draw.line([x_px, y_px - r, x_px, y_px + r], fill=(232, 255, 0), width=2)
    return preview


# ─── Session state init ───────────────────────────────────────────────────
for key, default in {
    "pdf_bytes": None,
    "sig_img": None,
    "page_number": 0,
    "sig_x_pt": None,
    "sig_y_pt": None,
    "sig_w_pt": 150,
    "sig_h_pt": 60,
    "placement_mode": "auto",   # "auto" | "manual"
    "selected_area_idx": None,
    "click_x_px": None,
    "click_y_px": None,
    "dpi": 150,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ─── Header ───────────────────────────────────────────────────────────────
st.markdown('<p class="header-tag">ATA Builders Lab · PDF Signer</p>', unsafe_allow_html=True)
st.markdown("# ✍️ PDF Signer")
st.markdown('<hr class="divider">', unsafe_allow_html=True)

# ─── Layout: Sidebar + Main ───────────────────────────────────────────────
with st.sidebar:
    st.markdown('<p class="header-tag">01 · Upload Files</p>', unsafe_allow_html=True)

    pdf_file = st.file_uploader("PDF Document", type=["pdf"], key="pdf_upload")
    if pdf_file:
        st.session_state.pdf_bytes = pdf_file.read()
        st.session_state.page_number = 0
        st.session_state.sig_x_pt = None
        st.session_state.sig_y_pt = None

    sig_file = st.file_uploader("Signature Image (PNG/JPG)", type=["png", "jpg", "jpeg"], key="sig_upload")
    if sig_file:
        st.session_state.sig_img = Image.open(sig_file)

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<p class="header-tag">02 · Placement Mode</p>', unsafe_allow_html=True)

    mode = st.radio(
        "",
        options=["Auto-detect", "Manual click"],
        index=0 if st.session_state.placement_mode == "auto" else 1,
        label_visibility="collapsed"
    )
    st.session_state.placement_mode = "auto" if mode == "Auto-detect" else "manual"

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<p class="header-tag">03 · Signature Size</p>', unsafe_allow_html=True)

    st.session_state.sig_w_pt = st.slider("Width (pt)", 80, 300, st.session_state.sig_w_pt)
    st.session_state.sig_h_pt = st.slider("Height (pt)", 30, 120, st.session_state.sig_h_pt)


# ─── Main content ─────────────────────────────────────────────────────────
if not st.session_state.pdf_bytes:
    st.markdown("""
    <div class="info-box">
    ⬅️  Upload a PDF file from the sidebar to get started.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

if not st.session_state.sig_img:
    st.markdown("""
    <div class="info-box">
    ⬅️  Upload a signature image from the sidebar to continue.
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# Load PDF
doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
total_pages = len(doc)
dpi = st.session_state.dpi

col_main, col_right = st.columns([3, 1])

with col_right:
    st.markdown('<p class="header-tag">Page Navigation</p>', unsafe_allow_html=True)
    page_num = st.number_input(
        "Page", min_value=1, max_value=total_pages,
        value=st.session_state.page_number + 1, step=1
    ) - 1
    st.session_state.page_number = page_num
    st.caption(f"Total: {total_pages} page(s)")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<p class="header-tag">Signature Preview</p>', unsafe_allow_html=True)
    preview_w = 200
    preview_h = int(preview_w * st.session_state.sig_h_pt / st.session_state.sig_w_pt)
    sig_preview = st.session_state.sig_img.copy().convert("RGBA")
    sig_preview.thumbnail((preview_w, preview_h))
    # White bg for preview
    bg = Image.new("RGB", sig_preview.size, (30, 30, 30))
    if sig_preview.mode == "RGBA":
        bg.paste(sig_preview, mask=sig_preview.split()[3])
    else:
        bg.paste(sig_preview)
    st.image(bg, use_container_width=True)

# Render current page
page_img = render_page(doc, st.session_state.page_number, dpi=dpi)
page_w_px, page_h_px = page_img.size
page_rect = doc[st.session_state.page_number].rect

with col_main:
    st.markdown('<p class="header-tag">PDF Preview</p>', unsafe_allow_html=True)

    # ── AUTO-DETECT MODE ─────────────────────────────────────────────────
    if st.session_state.placement_mode == "auto":
        areas = find_signature_areas(doc, st.session_state.page_number)

        if areas:
            st.markdown(f'<div class="info-box">🔍 Found <strong>{len(areas)}</strong> signature area(s). Select one below.</div>', unsafe_allow_html=True)

            for i, area in enumerate(areas):
                label = f"Area {i+1}: {area['reason']}  (x={area['x']:.0f}, y={area['y']:.0f})"
                if st.button(label, key=f"area_{i}"):
                    st.session_state.sig_x_pt = area["x"]
                    st.session_state.sig_y_pt = area["y"]
                    st.session_state.selected_area_idx = i
                    st.rerun()

        else:
            st.markdown('<div class="info-box">⚠️ No signature areas auto-detected. Switch to <strong>Manual click</strong> mode.</div>', unsafe_allow_html=True)

        # Show preview if area selected
        if st.session_state.sig_x_pt is not None:
            x_px = pt_to_px(st.session_state.sig_x_pt, dpi)
            y_px = pt_to_px(st.session_state.sig_y_pt, dpi)
            w_px = pt_to_px(st.session_state.sig_w_pt, dpi)
            h_px = pt_to_px(st.session_state.sig_h_pt, dpi)
            display_img = render_page_with_preview(
                page_img, st.session_state.sig_img,
                x_px, y_px, w_px, h_px, dpi
            )
            st.image(display_img, caption="Preview — signature placed", use_container_width=True)
        else:
            st.image(page_img, use_container_width=True)

    # ── MANUAL CLICK MODE ────────────────────────────────────────────────
    else:
        st.markdown('<div class="info-box">🖱️ Enter X/Y coordinates (in PDF points) where you want the signature placed. <br>Tip: Use the rulers on the preview image to estimate position.</div>', unsafe_allow_html=True)

        # Show the page image first
        if st.session_state.sig_x_pt is not None:
            x_px = pt_to_px(st.session_state.sig_x_pt, dpi)
            y_px = pt_to_px(st.session_state.sig_y_pt, dpi)
            w_px = pt_to_px(st.session_state.sig_w_pt, dpi)
            h_px = pt_to_px(st.session_state.sig_h_pt, dpi)
            display_img = render_page_with_preview(
                page_img, st.session_state.sig_img,
                x_px, y_px, w_px, h_px, dpi
            )
            st.image(display_img, caption="Preview — click position", use_container_width=True)
        else:
            st.image(page_img, caption="PDF page", use_container_width=True)

        page_w_pt = page_rect.width
        page_h_pt = page_rect.height

        mc1, mc2 = st.columns(2)
        with mc1:
            x_val = st.number_input("X position (pt)", 0.0, float(page_w_pt),
                                     float(st.session_state.sig_x_pt or page_w_pt * 0.1),
                                     step=5.0)
        with mc2:
            y_val = st.number_input("Y position (pt)", 0.0, float(page_h_pt),
                                     float(st.session_state.sig_y_pt or page_h_pt * 0.7),
                                     step=5.0)

        if st.button("📌 Set Position"):
            st.session_state.sig_x_pt = x_val
            st.session_state.sig_y_pt = y_val
            st.rerun()

    doc.close()

    # ── DOWNLOAD SECTION ─────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

    if st.session_state.sig_x_pt is not None:
        st.markdown('<p class="header-tag">Ready to Sign</p>', unsafe_allow_html=True)

        if st.button("✅ SIGN & DOWNLOAD PDF"):
            with st.spinner("Placing signature..."):
                doc2 = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                signed_bytes = place_signature_on_doc(
                    st.session_state.pdf_bytes,
                    st.session_state.page_number,
                    st.session_state.sig_x_pt,
                    st.session_state.sig_y_pt,
                    st.session_state.sig_img,
                    st.session_state.sig_w_pt,
                    st.session_state.sig_h_pt,
                )
                doc2.close()

            st.markdown('<div class="success-box">✔ Signature placed successfully! Download below.</div>', unsafe_allow_html=True)
            st.download_button(
                label="⬇️ DOWNLOAD SIGNED PDF",
                data=signed_bytes,
                file_name="signed_document.pdf",
                mime="application/pdf",
            )
    else:
        st.markdown('<div class="info-box">Select a signature position above to enable signing.</div>', unsafe_allow_html=True)
