"""
helpers.py — Pure helper functions with no Streamlit UI calls.

Covers:
  - File validation (PDF / image)
  - Signature image rendering helpers
  - PDF signing (temp-file wrapper)
  - Manual-placement coordinate utilities
"""

import os
import tempfile

import fitz
import streamlit as st
from PIL import Image, ImageDraw, UnidentifiedImageError

from pdf_backend import (
    process_signature_image,
    resize_signature_to_box,
    place_signature,
    clamp_signature_position,
)


# ── Validation ────────────────────────────────────────────────────────────────

def validate_pdf(pdf_bytes: bytes) -> tuple[bool, str | None]:
    """Return (True, None) if pdf_bytes is a valid non-empty PDF, else (False, error_message)."""
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc) == 0:
            doc.close()
            return False, "The PDF file is empty (0 pages)."
        doc.close()
        return True, None
    except Exception:
        return False, "Invalid or corrupted PDF file."


def validate_image(img_file) -> tuple[bool, Image.Image | None, str | None]:
    """Return (True, image, None) for a valid image file, else (False, None, error_message)."""
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


# ── Image rendering ───────────────────────────────────────────────────────────

def checkerboard_background(img: Image.Image, cell: int = 8) -> Image.Image:
    """Composite an RGBA image onto a dark checkerboard for transparent-area visibility."""
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


def get_processed_signature() -> tuple[Image.Image, dict]:
    """Apply all processing options (bg removal, opacity, rotation…) to the raw signature in session state."""
    info: dict = {}
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


def render_with_preview(
    page_img: Image.Image,
    sig_img: Image.Image,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    preserve_aspect: bool = True,
) -> Image.Image:
    """Return a composited RGB page image with the signature overlaid at pixel coordinates."""
    preview = page_img.copy().convert("RGBA")
    sig = resize_signature_to_box(
        sig_img, max(1, int(w_px)), max(1, int(h_px)),
        preserve_aspect_ratio=preserve_aspect,
    )
    preview.paste(sig, (int(x_px), int(y_px)), sig)
    return preview.convert("RGB")


# ── PDF signing ───────────────────────────────────────────────────────────────

def place_signature_from_bytes(
    pdf_bytes: bytes,
    page_number: int,
    x_pt: float,
    y_pt: float,
    sig_img: Image.Image,
    width_pt: float = 150,
    height_pt: float = 60,
    preserve_aspect_ratio: bool = True,
) -> bytes:
    """Write the signature onto the PDF and return the signed PDF as bytes."""
    with tempfile.TemporaryDirectory() as tmp:
        pdf_path = os.path.join(tmp, "input.pdf")
        sig_path = os.path.join(tmp, "signature.png")
        out_path = os.path.join(tmp, "signed.pdf")

        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        sig_img.convert("RGBA").save(sig_path, format="PNG")

        place_signature(
            pdf_path, page_number, x_pt, y_pt, sig_path,
            width=width_pt, height=height_pt,
            preserve_aspect_ratio=preserve_aspect_ratio,
            output_path=out_path,
        )

        with open(out_path, "rb") as f:
            return f.read()


# ── Manual placement utilities ────────────────────────────────────────────────

def default_manual_placement(page_width_pt: float, page_height_pt: float) -> tuple[float, float]:
    """Return a sensible default placement (lower-left area of the page)."""
    return page_width_pt * 0.1, page_height_pt * 0.7


def ensure_manual_placement(
    page_width_pt: float,
    page_height_pt: float,
    sig_w_pt: float,
    sig_h_pt: float,
) -> None:
    """Initialise manual_x_pt / manual_y_pt in session state if not yet set, then clamp them."""
    if "manual_x_pt" not in st.session_state or "manual_y_pt" not in st.session_state:
        dx, dy = default_manual_placement(page_width_pt, page_height_pt)
        st.session_state.manual_x_pt = dx
        st.session_state.manual_y_pt = dy

    x_pt, y_pt = clamp_signature_position(
        st.session_state.manual_x_pt, st.session_state.manual_y_pt,
        page_width_pt, page_height_pt, sig_w_pt, sig_h_pt,
    )
    st.session_state.manual_x_pt = x_pt
    st.session_state.manual_y_pt = y_pt


def set_manual_placement(
    x_pt: float,
    y_pt: float,
    page_width_pt: float,
    page_height_pt: float,
    sig_w_pt: float,
    sig_h_pt: float,
) -> None:
    """Update manual position in session state, clamping to page bounds."""
    x_pt, y_pt = clamp_signature_position(
        x_pt, y_pt, page_width_pt, page_height_pt, sig_w_pt, sig_h_pt,
    )
    st.session_state.manual_x_pt = x_pt
    st.session_state.manual_y_pt = y_pt
