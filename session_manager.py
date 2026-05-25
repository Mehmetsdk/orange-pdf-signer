"""
session_manager.py — Local session persistence and Streamlit session-state defaults.

Files written to disk:
    uploads/last_pdf.pdf       — most recently uploaded PDF
    uploads/last_signature.png — most recently used signature image
    uploads/meta.json          — file names + timestamps for the restore banner
"""

import json
import shutil
import streamlit as st
from pathlib import Path
from datetime import datetime
from PIL import Image

# ── Disk paths ────────────────────────────────────────────────────────────────
UPLOAD_DIR    = Path("uploads")
LAST_PDF_PATH = UPLOAD_DIR / "last_pdf.pdf"
LAST_SIG_PATH = UPLOAD_DIR / "last_signature.png"
META_PATH     = UPLOAD_DIR / "meta.json"

UPLOAD_DIR.mkdir(exist_ok=True)

# ── Session-state defaults ────────────────────────────────────────────────────
SESSION_DEFAULTS: dict = {
    "pdf_bytes":       None,
    "sig_img_raw":     None,
    "page_number":     0,
    "sig_w_pt":        150,
    "sig_h_pt":        60,
    "remove_bg":       False,
    "use_rembg":       True,
    "white_threshold": 245,
    "opacity":         1.0,
    "rotation":        0.0,
    "trim_edges":      True,
    "preserve_aspect": True,
    "canvas_version":  0,
}


def init_session() -> None:
    """Populate missing session-state keys and restore the last session from disk (once per browser tab)."""
    for key, default in SESSION_DEFAULTS.items():
        if key not in st.session_state:
            st.session_state[key] = default

    if "session_loaded" not in st.session_state:
        st.session_state.session_loaded = True
        st.session_state._restored = load_session()


# ── Persistence helpers ───────────────────────────────────────────────────────

def save_session(pdf_bytes=None, sig_img=None, pdf_name: str = "", sig_name: str = "") -> None:
    """Save PDF bytes and/or signature image to disk and update metadata."""
    meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}

    if pdf_bytes is not None:
        LAST_PDF_PATH.write_bytes(pdf_bytes)
        meta["pdf_name"]  = pdf_name
        meta["pdf_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    if sig_img is not None:
        sig_img.convert("RGBA").save(LAST_SIG_PATH, format="PNG")
        meta["sig_name"]  = sig_name
        meta["sig_saved"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    META_PATH.write_text(json.dumps(meta, ensure_ascii=False))


def load_session() -> dict:
    """Restore PDF and signature from disk into session state. Returns a dict describing what was restored."""
    restored: dict = {}

    if st.session_state.pdf_bytes is None and LAST_PDF_PATH.exists():
        st.session_state.pdf_bytes = LAST_PDF_PATH.read_bytes()
        restored["pdf"] = True

    if st.session_state.sig_img_raw is None and LAST_SIG_PATH.exists():
        st.session_state.sig_img_raw = Image.open(LAST_SIG_PATH).convert("RGBA")
        restored["sig"] = True

    if restored and META_PATH.exists():
        restored["meta"] = json.loads(META_PATH.read_text())

    return restored


def clear_session() -> None:
    """Wipe session state and delete all files saved to disk."""
    st.session_state.pdf_bytes    = None
    st.session_state.sig_img_raw  = None
    st.session_state._restored    = {}

    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(exist_ok=True)
