import streamlit as st
import fitz
from PIL import Image, ImageDraw
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
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; background:#0f0f0f; color:#e8e8e8; }
.stApp { background:#0f0f0f; }
h1,h2,h3 { font-family:'Space Mono',monospace !important; }
.block-container { padding:2rem 3rem; max-width:1400px; }
.stButton>button { background:#e8ff00 !important; color:#0f0f0f !important; border:none !important;
    border-radius:0 !important; font-family:'Space Mono',monospace !important; font-weight:700 !important;
    font-size:.85rem !important; padding:.6rem 1.5rem !important; }
.header-tag { font-family:'Space Mono',monospace; font-size:.7rem; letter-spacing:.15em; color:#e8ff00; text-transform:uppercase; margin-bottom:.25rem; }
.divider { border:none; border-top:1px solid #222; margin:1.5rem 0; }
.info-box { background:#161616; border-left:3px solid #e8ff00; padding:.75rem 1rem; font-size:.85rem; color:#aaa; margin-bottom:1rem; }
.success-box { background:#0d1f0d; border-left:3px solid #4caf50; padding:.75rem 1rem; font-size:.85rem; color:#81c784; }
section[data-testid="stSidebar"] { background:#111 !important; border-right:1px solid #1e1e1e; }
</style>
""", unsafe_allow_html=True)


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


for k, v in {"pdf_bytes": None, "sig_img": None, "page_number": 0,
              "sig_w_pt": 150, "sig_h_pt": 60}.items():
    if k not in st.session_state:
        st.session_state[k] = v

with st.sidebar:
    st.markdown('<p class="header-tag">01 · Upload Files</p>', unsafe_allow_html=True)
    pdf_file = st.file_uploader("PDF Document", type=["pdf"])
    if pdf_file:
        st.session_state.pdf_bytes = pdf_file.read()
        st.session_state.page_number = 0
    sig_file = st.file_uploader("Signature Image (PNG/JPG)", type=["png", "jpg", "jpeg"])
    if sig_file:
        st.session_state.sig_img = Image.open(sig_file)
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<p class="header-tag">02 · Placement Mode</p>', unsafe_allow_html=True)
    mode = st.radio("", ["Auto-detect", "Manual"], label_visibility="collapsed")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<p class="header-tag">03 · Signature Size</p>', unsafe_allow_html=True)
    st.session_state.sig_w_pt = st.slider("Width (pt)", 80, 300, st.session_state.sig_w_pt)
    st.session_state.sig_h_pt = st.slider("Height (pt)", 30, 120, st.session_state.sig_h_pt)

st.markdown('<p class="header-tag">ATA Builders Lab · PDF Signer</p>', unsafe_allow_html=True)
st.markdown("# ✍️ PDF Signer")
st.markdown('<hr class="divider">', unsafe_allow_html=True)

if not st.session_state.pdf_bytes:
    st.markdown('<div class="info-box">⬅️ Upload a PDF from the sidebar.</div>', unsafe_allow_html=True)
    st.stop()
if not st.session_state.sig_img:
    st.markdown('<div class="info-box">⬅️ Upload a signature image from the sidebar.</div>', unsafe_allow_html=True)
    st.stop()

doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
total_pages = get_page_count(doc)
DPI = 150

col_main, col_right = st.columns([3, 1])

with col_right:
    st.markdown('<p class="header-tag">Page</p>', unsafe_allow_html=True)
    page_num = st.number_input("Page", 1, total_pages, st.session_state.page_number + 1, step=1) - 1
    st.session_state.page_number = page_num
    st.caption(f"Total: {total_pages} page(s)")
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<p class="header-tag">Signature</p>', unsafe_allow_html=True)
    thumb = st.session_state.sig_img.copy().convert("RGBA")
    thumb.thumbnail((200, 80))
    bg = Image.new("RGB", thumb.size, (30, 30, 30))
    bg.paste(thumb, mask=thumb.split()[3])
    st.image(bg, width=200)

page_img = render_page(doc, st.session_state.page_number, dpi=DPI)
page_rect = doc[st.session_state.page_number].rect
w_pt = st.session_state.sig_w_pt
h_pt = st.session_state.sig_h_pt

with col_main:
    st.markdown('<p class="header-tag">PDF Preview</p>', unsafe_allow_html=True)

    if mode == "Auto-detect":
        areas = find_signature_areas(doc, st.session_state.page_number)
        if not areas:
            st.markdown('<div class="info-box">⚠️ No areas found. Switch to Manual mode.</div>', unsafe_allow_html=True)
            st.image(page_img, width=700)
        else:
            st.markdown(f'<div class="info-box">🔍 <strong>{len(areas)}</strong> signature area(s) found.</div>', unsafe_allow_html=True)
            area_labels = [f"Alan {i+1}: {a['reason']} (x={a['x']:.0f}, y={a['y']:.0f})" for i, a in enumerate(areas)]
            secim = st.radio("Select signature area:", area_labels)
            secilen_idx = area_labels.index(secim)
            secilen = areas[secilen_idx]
            x_pt_val = float(secilen["x"])
            y_pt_val = float(secilen["y"])
            x_px = pt_to_px(x_pt_val, DPI)
            y_px = pt_to_px(y_pt_val, DPI)
            preview = render_with_preview(page_img, st.session_state.sig_img,
                                          x_px, y_px, pt_to_px(w_pt, DPI), pt_to_px(h_pt, DPI))
            st.image(preview, caption="Preview — signature placed", width=700)
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            if st.button("✅ SIGN & DOWNLOAD PDF"):
                with st.spinner("Placing signature..."):
                    signed = place_signature_from_bytes(
                        st.session_state.pdf_bytes, st.session_state.page_number,
                        x_pt_val, y_pt_val, st.session_state.sig_img, w_pt, h_pt)
                st.markdown('<div class="success-box">✔ Signature added!</div>', unsafe_allow_html=True)
                st.download_button("⬇️ DOWNLOAD SIGNED PDF", data=signed,
                                   file_name="signed_document.pdf", mime="application/pdf")
    else:
        st.markdown('<div class="info-box">🖱️ Enter X/Y coordinates.</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            x_pt_val = st.number_input("X (pt)", 0.0, float(page_rect.width), float(page_rect.width * 0.1), step=5.0)
        with c2:
            y_pt_val = st.number_input("Y (pt)", 0.0, float(page_rect.height), float(page_rect.height * 0.7), step=5.0)
        preview = render_with_preview(page_img, st.session_state.sig_img,
                                      pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                                      pt_to_px(w_pt, DPI), pt_to_px(h_pt, DPI))
        st.image(preview, caption="Preview", width=700)
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        if st.button("✅ SIGN & DOWNLOAD PDF"):
            with st.spinner("Placing signature..."):
                signed = place_signature_from_bytes(
                    st.session_state.pdf_bytes, st.session_state.page_number,
                    x_pt_val, y_pt_val, st.session_state.sig_img, w_pt, h_pt)
            st.markdown('<div class="success-box">✔ Signature added!</div>', unsafe_allow_html=True)
            st.download_button("⬇️ DOWNLOAD SIGNED PDF", data=signed,
                               file_name="signed_document.pdf", mime="application/pdf")

doc.close()
