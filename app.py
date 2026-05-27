"""
app.py — PDF Signer · Streamlit entry point.

Only contains UI wiring. Logic lives in:
  styles.py         — CSS
  session_manager.py — persistence + session defaults
  helpers.py         — pure computation helpers
  pdf_backend.py     — PDF rendering & signature placement engine
"""

import numpy as np
import streamlit as st
from PIL import Image
from streamlit_drawable_canvas import st_canvas
from streamlit_image_coordinates import streamlit_image_coordinates

from pdf_backend import (
    render_page,
    find_signature_areas,
    get_page_count,
    pt_to_px,
    rembg_is_available,
    display_click_to_signature_top_left_pt,
)
from styles import APP_CSS
from session_manager import init_session, save_session, clear_session
from auth import render_auth_ui
from storage import upload_signature, upload_signed_pdf, upload_pdf, r2_is_configured, list_user_files, download_file
from helpers import (
    validate_pdf,
    validate_image,
    checkerboard_background,
    get_processed_signature,
    render_with_preview,
    place_signature_from_bytes,
    default_manual_placement,
    ensure_manual_placement,
    set_manual_placement,
)

# ── Constants ─────────────────────────────────────────────────────────────────
DPI           = 150
DISPLAY_WIDTH = 700
NUDGE_PT      = 5.0

# ── App bootstrap ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PDF Signer",
    page_icon="✍️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(APP_CSS, unsafe_allow_html=True)
init_session()


# ── Auth check ────────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""

with st.sidebar:
    st.markdown('<span class="sidebar-label">00 · Account</span>', unsafe_allow_html=True)
    is_logged_in = render_auth_ui()
    st.markdown('<hr class="divider">', unsafe_allow_html=True)

if not st.session_state.logged_in:
    st.markdown("""
    <div class="app-header">
        <div><div class="app-logo">PDF <span>Signer</span></div></div>
        <div class="app-subtitle">ATA Builders Lab &nbsp;·&nbsp; Document Signing Tool</div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="msg msg-info">⬅ Please log in or register from the sidebar to use the app.</div>', unsafe_allow_html=True)
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:

    # ── 01 · Files ────────────────────────────────────────────────────────────
    st.markdown('<span class="sidebar-label">01 · Files</span>', unsafe_allow_html=True)

    st.caption("📄 PDF Document")
    pdf_file = st.file_uploader("PDF Document", type=["pdf"], label_visibility="collapsed",
                                key=f"pdf_uploader_{st.session_state.uploader_version}")
    if pdf_file:
        raw = pdf_file.read()
        is_valid, err = validate_pdf(raw)
        if not is_valid:
            st.markdown(f'<div class="msg msg-error">❌ {err}</div>', unsafe_allow_html=True)
            st.session_state.pdf_bytes = None
        else:
            st.session_state.pdf_bytes = raw
            st.session_state.page_number = 0
            save_session(pdf_bytes=raw, pdf_name=pdf_file.name)
            if r2_is_configured():
                upload_pdf(
                    st.session_state.get("username", "anonymous"),
                    raw,
                    pdf_file.name,
                )

    st.caption("✍️ Signature Image")
    sig_file = st.file_uploader("Signature Image (PNG/JPG)", type=["png", "jpg", "jpeg"], label_visibility="collapsed",
                                key=f"sig_uploader_{st.session_state.uploader_version}")
    if sig_file:
        import io as _io
        sig_bytes = sig_file.read()
        is_valid, img, err = validate_image(_io.BytesIO(sig_bytes))
        if not is_valid:
            st.markdown(f'<div class="msg msg-error">❌ {err}</div>', unsafe_allow_html=True)
            st.session_state.sig_img_raw = None
        else:
            st.session_state.sig_img_raw = img
            save_session(sig_img=img, sig_name=sig_file.name)
            if r2_is_configured():
                ok, msg = upload_signature(
                    st.session_state.get("username", "anonymous"),
                    sig_bytes,
                    sig_file.name,
                )
                if not ok:
                    st.sidebar.warning(f"R2 upload: {msg}")

    # ── Draw your signature ───────────────────────────────────────────────────
    with st.expander("✏️ Draw your signature"):
        st.caption("Draw with your mouse, then click Use.")
        canvas_result = st_canvas(
            fill_color="rgba(0,0,0,0)",
            stroke_width=3,
            stroke_color="#000000",
            background_color="#ffffff",
            height=120,
            width=240,
            drawing_mode="freedraw",
            key=f"signature_canvas_{st.session_state.canvas_version}",
        )
        _ca, _cb = st.columns(2)
        with _ca:
            if st.button("🗑 Clear", key="canvas_clear"):
                # Increment version → forces a fresh canvas widget on next render
                st.session_state.canvas_version += 1
                st.rerun()
        with _cb:
            if st.button("✔ Use", key="canvas_use"):
                if canvas_result.image_data is not None:
                    arr = canvas_result.image_data.astype("uint8")
                    if arr[:, :, :3].min() < 250:           # not blank
                        drawn = Image.fromarray(arr, "RGBA")
                        st.session_state.sig_img_raw = drawn
                        save_session(sig_img=drawn, sig_name="drawn_signature.png")
                        st.rerun()
                    else:
                        st.warning("Canvas is empty — draw first.")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    if st.button("🗑 Clear Files"):
        clear_session()
        st.rerun()

    # ── 02 · Signature Processing ─────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">02 · Signature Processing</span>', unsafe_allow_html=True)

    st.session_state.remove_bg  = st.checkbox("Remove background",        value=st.session_state.remove_bg)
    st.session_state.use_rembg  = st.checkbox("Use rembg when available", value=st.session_state.use_rembg,
                                               disabled=not st.session_state.remove_bg)
    _bg_dis = not st.session_state.remove_bg

    def _arrow_row(label, key_l, key_r, state_key, mn, mx, step, fmt):
        """Render a ◀ value ▶ row and apply changes to session state."""
        st.caption(label)
        col_l, col_m, col_r = st.columns([3, 4, 3])
        color = "#555" if _bg_dis and "threshold" in state_key else "#c8ff00"
        with col_l:
            if st.button("◀", key=key_l, disabled=(_bg_dis and "threshold" in state_key)):
                st.session_state[state_key] = max(mn, round(st.session_state[state_key] - step, 2))
                st.rerun()
        with col_m:
            st.markdown(
                f'<p style="text-align:center;color:{color};font-size:1rem;font-weight:700;margin:0.55rem 0;">'
                f'{fmt.format(st.session_state[state_key])}</p>',
                unsafe_allow_html=True,
            )
        with col_r:
            if st.button("▶", key=key_r, disabled=(_bg_dis and "threshold" in state_key)):
                st.session_state[state_key] = min(mx, round(st.session_state[state_key] + step, 2))
                st.rerun()

    _arrow_row("Background threshold", "bg_l",  "bg_r",  "white_threshold", 200,   255,  5,    "{:.0f}")
    _arrow_row("Opacity",              "op_l",  "op_r",  "opacity",          0.1,   1.0,  0.05, "{:.2f}")
    _arrow_row("Rotation (degrees)",   "rot_l", "rot_r", "rotation",        -45,    45,   1,    "{:.0f}°")

    st.session_state.trim_edges     = st.checkbox("Trim empty edges",      value=st.session_state.trim_edges)
    st.session_state.preserve_aspect = st.checkbox("Preserve aspect ratio", value=st.session_state.preserve_aspect)

    # ── 03 · Placement Mode ───────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">03 · Placement Mode</span>', unsafe_allow_html=True)
    mode = st.radio("", ["Auto-detect", "Manual"], label_visibility="collapsed")

    # ── 04 · Signature Size ───────────────────────────────────────────────────
    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<span class="sidebar-label">04 · Signature Size</span>', unsafe_allow_html=True)
    st.caption("Width (pt)")
    st.session_state.sig_w_pt = st.slider("W", 80, 300, int(st.session_state.sig_w_pt), label_visibility="collapsed")
    st.caption("Height (pt)")
    st.session_state.sig_h_pt = st.slider("H", 30, 120, int(st.session_state.sig_h_pt), label_visibility="collapsed")

    # ── Signature thumbnail ───────────────────────────────────────────────────
    if st.session_state.sig_img_raw:
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown('<span class="sidebar-label">Signature Preview</span>', unsafe_allow_html=True)
        thumb = st.session_state.sig_img_raw.copy().convert("RGBA")
        thumb.thumbnail((200, 100))
        st.image(checkerboard_background(thumb), width=200)


# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
    <div><div class="app-logo">PDF <span>Signer</span></div></div>
    <div class="app-subtitle">ATA Builders Lab &nbsp;·&nbsp; Document Signing Tool</div>
</div>
""", unsafe_allow_html=True)

# Restore banner
_restored = st.session_state.get("_restored", {})
if _restored:
    meta  = _restored.get("meta", {})
    parts = []
    if _restored.get("pdf") and meta.get("pdf_name"):
        parts.append(f"📄 {meta['pdf_name']} ({meta.get('pdf_saved', '')})")
    if _restored.get("sig") and meta.get("sig_name"):
        parts.append(f"✍️ {meta['sig_name']} ({meta.get('sig_saved', '')})")
    if parts:
        st.markdown(
            f'<div class="msg msg-info">📂 Restored from last session: {" · ".join(parts)}</div>',
            unsafe_allow_html=True,
        )

# Guard rails — stop early if files are missing
if not st.session_state.pdf_bytes:
    st.markdown('<div class="msg msg-info">⬅ Upload a PDF document from the sidebar to get started.</div>', unsafe_allow_html=True)
    st.stop()

if not st.session_state.sig_img_raw:
    st.markdown('<div class="msg msg-info">⬅ Upload a signature image from the sidebar to continue.</div>', unsafe_allow_html=True)
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ══════════════════════════════════════════════════════════════════════════════
import fitz  # noqa: E402  (imported late to keep top-level imports clean)

try:
    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
    total_pages = get_page_count(doc)
except Exception:
    st.markdown('<div class="msg msg-error">❌ Failed to open PDF.</div>', unsafe_allow_html=True)
    st.stop()

w_pt     = st.session_state.sig_w_pt
h_pt     = st.session_state.sig_h_pt
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

# ── Right panel: navigation + processed signature preview ─────────────────────
with col_right:
    st.markdown('<div class="section-title">Navigation</div>', unsafe_allow_html=True)
    page_num = st.number_input(
        "Go to page", 1, total_pages,
        st.session_state.page_number + 1,
        step=1, label_visibility="collapsed",
    ) - 1
    st.session_state.page_number = page_num
    st.caption(f"Page {st.session_state.page_number + 1} of {total_pages}")

    st.markdown('<hr class="divider">', unsafe_allow_html=True)
    st.markdown('<div class="section-title">Processed Signature</div>', unsafe_allow_html=True)
    proc_thumb = processed_sig.copy()
    proc_thumb.thumbnail((200, 100))
    st.image(checkerboard_background(proc_thumb), width=200)

    # ── My Files (R2) ─────────────────────────────────────────────────────────
    if r2_is_configured():
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        st.markdown('<div class="section-title">My Files</div>', unsafe_allow_html=True)
        _username = st.session_state.get("username", "anonymous")

        _tab_sig, _tab_pdf, _tab_signed = st.tabs(["✍️ Signatures", "📄 PDFs", "✅ Signed"])

        def _file_list(tab, category, mime):
            with tab:
                files = list_user_files(_username, category)
                if not files:
                    st.caption("No files yet.")
                else:
                    for f in files:
                        size_kb = f["size"] // 1024 or 1
                        col_a, col_b = st.columns([3, 2])
                        with col_a:
                            st.caption(f["name"])
                            st.markdown(f'<span style="font-size:0.7rem;color:#555;">{size_kb} KB</span>', unsafe_allow_html=True)
                        with col_b:
                            if st.button("⬇", key=f"dl_{f['key']}"):
                                data = download_file(f["key"])
                                if data:
                                    st.download_button(
                                        "Save",
                                        data=data,
                                        file_name=f["name"],
                                        mime=mime,
                                        key=f"save_{f['key']}",
                                    )

        _file_list(_tab_sig,    "signatures",  "image/png")
        _file_list(_tab_pdf,    "pdfs",        "application/pdf")
        _file_list(_tab_signed, "signed_pdfs", "application/pdf")

# ── Render current page ───────────────────────────────────────────────────────
try:
    page_img = render_page(doc, st.session_state.page_number, dpi=DPI)
except Exception:
    st.markdown('<div class="msg msg-error">❌ Failed to render page.</div>', unsafe_allow_html=True)
    doc.close()
    st.stop()

page_rect = doc[st.session_state.page_number].rect

# ── Left panel: PDF preview + sign button ────────────────────────────────────
with col_main:
    st.markdown('<div class="section-title">PDF Preview</div>', unsafe_allow_html=True)

    # ── Auto-detect mode ──────────────────────────────────────────────────────
    if mode == "Auto-detect":
        try:
            areas = find_signature_areas(doc, st.session_state.page_number)
        except Exception:
            areas = []

        if not areas:
            st.markdown('<div class="msg msg-warning">⚠ No signature areas detected. Switch to Manual mode.</div>', unsafe_allow_html=True)
            st.image(page_img, width=DISPLAY_WIDTH)
        else:
            st.markdown(
                f'<div class="msg msg-info">🔍 Found <strong>{len(areas)}</strong> signature area(s). Select one:</div>',
                unsafe_allow_html=True,
            )
            area_labels = [f"Area {i+1} — {a['reason']}" for i, a in enumerate(areas)]
            selected    = st.radio("", area_labels, label_visibility="collapsed")
            area        = areas[area_labels.index(selected)]
            x_pt_val    = float(area["x"])
            y_pt_val    = float(area["y"])

            try:
                preview = render_with_preview(
                    page_img, processed_sig,
                    pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                    pt_to_px(w_pt, DPI),     pt_to_px(h_pt, DPI),
                    preserve_aspect=preserve,
                )
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
                            preserve_aspect_ratio=preserve,
                        )
                    st.markdown('<div class="msg msg-success">✔ Signature placed successfully.</div>', unsafe_allow_html=True)
                    if r2_is_configured():
                        pdf_name = st.session_state.get("_meta", {}).get("pdf_name", "signed_document.pdf")
                        ok, r2_key = upload_signed_pdf(
                            st.session_state.get("username", "anonymous"),
                            signed,
                            f"signed_{pdf_name}",
                        )
                        if ok:
                            st.markdown(f'<div class="msg msg-info">☁ Saved to cloud: {r2_key}</div>', unsafe_allow_html=True)
                        else:
                            st.warning(f"R2 upload: {r2_key}")
                    st.download_button("⬇ DOWNLOAD SIGNED PDF", data=signed, file_name="signed_document.pdf", mime="application/pdf")
                except Exception as exc:
                    st.markdown(f'<div class="msg msg-error">❌ Failed to sign PDF: {exc}</div>', unsafe_allow_html=True)

    # ── Manual mode ───────────────────────────────────────────────────────────
    else:
        page_w = float(page_rect.width)
        page_h = float(page_rect.height)
        ensure_manual_placement(page_w, page_h, w_pt, h_pt)

        st.markdown('<div class="msg msg-info">Click on the PDF preview to place the signature, or use X/Y inputs below.</div>', unsafe_allow_html=True)

        x_pt_val = float(st.session_state.manual_x_pt)
        y_pt_val = float(st.session_state.manual_y_pt)

        try:
            preview = render_with_preview(
                page_img, processed_sig,
                pt_to_px(x_pt_val, DPI), pt_to_px(y_pt_val, DPI),
                pt_to_px(w_pt, DPI),     pt_to_px(h_pt, DPI),
                preserve_aspect=preserve,
            )
        except Exception:
            preview = page_img

        display_height = int(page_img.height * DISPLAY_WIDTH / page_img.width)
        click = streamlit_image_coordinates(preview, width=DISPLAY_WIDTH, key="manual_preview_click")

        if click and click.get("x") is not None and click.get("y") is not None:
            click_key = (int(click["x"]), int(click["y"]), st.session_state.page_number)
            if st.session_state.get("manual_last_click") != click_key:
                st.session_state.manual_last_click = click_key
                new_x, new_y = display_click_to_signature_top_left_pt(
                    float(click["x"]), float(click["y"]),
                    DISPLAY_WIDTH, display_height,
                    page_img.width, page_img.height,
                    w_pt, h_pt, page_w, page_h, dpi=DPI,
                )
                set_manual_placement(new_x, new_y, page_w, page_h, w_pt, h_pt)
                st.rerun()

        # X / Y number inputs
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

        # Nudge buttons
        n1, n2, n3, n4, n5 = st.columns(5)
        with n1:
            if st.button("← Left"):
                set_manual_placement(x_pt_val - NUDGE_PT, y_pt_val, page_w, page_h, w_pt, h_pt); st.rerun()
        with n2:
            if st.button("Right →"):
                set_manual_placement(x_pt_val + NUDGE_PT, y_pt_val, page_w, page_h, w_pt, h_pt); st.rerun()
        with n3:
            if st.button("↑ Up"):
                set_manual_placement(x_pt_val, y_pt_val - NUDGE_PT, page_w, page_h, w_pt, h_pt); st.rerun()
        with n4:
            if st.button("Down ↓"):
                set_manual_placement(x_pt_val, y_pt_val + NUDGE_PT, page_w, page_h, w_pt, h_pt); st.rerun()
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
                        preserve_aspect_ratio=preserve,
                    )
                st.markdown('<div class="msg msg-success">✔ Signature placed successfully.</div>', unsafe_allow_html=True)
                if r2_is_configured():
                    pdf_name = st.session_state.get("_meta", {}).get("pdf_name", "signed_document.pdf")
                    ok, r2_key = upload_signed_pdf(
                        st.session_state.get("username", "anonymous"),
                        signed,
                        f"signed_{pdf_name}",
                    )
                    if ok:
                        st.markdown(f'<div class="msg msg-info">☁ Saved to cloud: {r2_key}</div>', unsafe_allow_html=True)
                    else:
                        st.warning(f"R2 upload: {r2_key}")
                st.download_button("⬇ DOWNLOAD SIGNED PDF", data=signed, file_name="signed_document.pdf", mime="application/pdf")
            except Exception as exc:
                st.markdown(f'<div class="msg msg-error">❌ Failed to sign PDF: {exc}</div>', unsafe_allow_html=True)

doc.close()
