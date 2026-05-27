"""
auth.py — User authentication helpers (register, login, session, remember-me).
Uses PostgreSQL via psycopg2 and bcrypt for password hashing.
Remember-me uses a signed cookie via extra-streamlit-components.
"""

import os
import hmac
import hashlib
import base64
import time
import bcrypt
import psycopg2
import streamlit as st
from datetime import datetime, timedelta, timezone

try:
    import extra_streamlit_components as stx
    _COOKIES_AVAILABLE = True
except ImportError:
    _COOKIES_AVAILABLE = False

# ── Cookie config ─────────────────────────────────────────────────────────────
_COOKIE_NAME   = "pdf_signer_remember"
_COOKIE_DAYS   = 30
_SECRET        = os.environ.get("SECRET_KEY", "pdf-signer-secret-key-change-me")


@st.cache_resource
def _cookie_manager():
    """Return a singleton CookieManager (cached to avoid re-instantiation)."""
    if not _COOKIES_AVAILABLE:
        return None
    return stx.CookieManager()


def _make_token(username: str) -> str:
    """Create a signed remember-me token: base64(username:expiry:signature)."""
    expiry  = str(int(time.time()) + _COOKIE_DAYS * 86400)
    payload = f"{username}:{expiry}"
    sig     = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}:{sig}".encode()).decode()


def _verify_token(token: str) -> str | None:
    """Verify a remember-me token. Returns username if valid, else None."""
    try:
        decoded  = base64.urlsafe_b64decode(token.encode()).decode()
        username, expiry, sig = decoded.rsplit(":", 2)
        payload  = f"{username}:{expiry}"
        expected = hmac.new(_SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(sig, expected) and int(expiry) > time.time():
            return username
    except Exception:
        pass
    return None


# ── Database helpers ──────────────────────────────────────────────────────────

def get_connection():
    """Open a database connection using the DATABASE_URL environment variable."""
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("DATABASE_URL environment variable is not set.")
    return psycopg2.connect(db_url)


def register_user(username: str, email: str, password: str) -> tuple[bool, str]:
    """Register a new user. Returns (success, message)."""
    if not username or not email or not password:
        return False, "All fields are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."
    try:
        password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username.strip(), email.strip().lower(), password_hash),
        )
        conn.commit()
        cur.close()
        conn.close()
        return True, "Account created successfully."
    except psycopg2.errors.UniqueViolation:
        return False, "Username or email already exists."
    except Exception as e:
        return False, f"Database error: {e}"


def login_user(username: str, password: str) -> tuple[bool, str]:
    """Verify credentials. Returns (success, message)."""
    if not username or not password:
        return False, "Username and password are required."
    try:
        conn = get_connection()
        cur  = conn.cursor()
        cur.execute(
            "SELECT password_hash FROM users WHERE username = %s",
            (username.strip(),),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row is None:
            return False, "User not found."
        if bcrypt.checkpw(password.encode(), row[0].encode()):
            return True, "Login successful."
        return False, "Incorrect password."
    except Exception as e:
        return False, f"Database error: {e}"


# ── Auth UI ───────────────────────────────────────────────────────────────────

def render_auth_ui() -> bool:
    """
    Render login / register UI in the sidebar.
    Returns True if the user is logged in, False otherwise.
    """
    cm = _cookie_manager()

    # ── Auto-login from cookie ─────────────────────────────────────────────
    if cm and not st.session_state.get("logged_in"):
        if not st.session_state.get("_cookie_checked"):
            st.session_state._cookie_checked = True
            try:
                token = cm.get(_COOKIE_NAME)
                if token:
                    username = _verify_token(token)
                    if username:
                        st.session_state.logged_in = True
                        st.session_state.username  = username
                        st.rerun()
            except Exception:
                pass

    # ── Already logged in ──────────────────────────────────────────────────
    if st.session_state.get("logged_in"):
        st.sidebar.markdown(
            f'<span class="sidebar-label">👤 {st.session_state.get("username", "")}</span>',
            unsafe_allow_html=True,
        )
        if st.sidebar.button("🚪 Log out", key="auth_logout"):
            # Clear remember-me cookie
            if cm:
                try:
                    cm.delete(_COOKIE_NAME)
                except Exception:
                    pass
            st.session_state.logged_in      = False
            st.session_state.username       = ""
            st.session_state._cookie_checked = False
            st.rerun()
        return True

    tab = st.sidebar.radio("", ["Login", "Register"], label_visibility="collapsed", key="auth_tab")

    if tab == "Login":
        st.sidebar.caption("Username")
        uname = st.sidebar.text_input("Username", label_visibility="collapsed", key="login_username")
        st.sidebar.caption("Password")
        pwd   = st.sidebar.text_input("Password", type="password", label_visibility="collapsed", key="login_password")
        remember = st.sidebar.checkbox("🔐 Remember me", value=False, key="login_remember")

        if st.sidebar.button("→ Login", key="auth_login_btn"):
            ok, msg = login_user(uname, pwd)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username  = uname.strip()
                # Set remember-me cookie
                if remember and cm:
                    try:
                        token   = _make_token(uname.strip())
                        expires = datetime.now(timezone.utc) + timedelta(days=_COOKIE_DAYS)
                        cm.set(_COOKIE_NAME, token, expires=expires)
                    except Exception:
                        pass
                st.rerun()
            else:
                st.sidebar.error(msg)

    else:
        st.sidebar.caption("Username")
        uname = st.sidebar.text_input("Username", label_visibility="collapsed", key="reg_username")
        st.sidebar.caption("Email")
        email = st.sidebar.text_input("Email", label_visibility="collapsed", key="reg_email")
        st.sidebar.caption("Password")
        pwd   = st.sidebar.text_input("Password", type="password", label_visibility="collapsed", key="reg_password")
        if st.sidebar.button("→ Register", key="auth_register_btn"):
            ok, msg = register_user(uname, email, pwd)
            if ok:
                st.sidebar.success(msg)
            else:
                st.sidebar.error(msg)

    return False
