"""
auth.py — User authentication helpers (register, login, session).
Uses PostgreSQL via psycopg2 and bcrypt for password hashing.
"""

import os
import bcrypt
import psycopg2
import streamlit as st


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
        cur = conn.cursor()
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
        cur = conn.cursor()
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


def render_auth_ui() -> bool:
    """
    Render login / register UI in the sidebar.
    Returns True if the user is logged in, False otherwise.
    """
    if st.session_state.get("logged_in"):
        st.sidebar.markdown(
            f'<span class="sidebar-label">👤 {st.session_state.get("username", "")}</span>',
            unsafe_allow_html=True,
        )
        if st.sidebar.button("🚪 Log out", key="auth_logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()
        return True

    tab = st.sidebar.radio("", ["Login", "Register"], label_visibility="collapsed", key="auth_tab")

    if tab == "Login":
        st.sidebar.caption("Username")
        uname = st.sidebar.text_input("Username", label_visibility="collapsed", key="login_username")
        st.sidebar.caption("Password")
        pwd = st.sidebar.text_input("Password", type="password", label_visibility="collapsed", key="login_password")
        if st.sidebar.button("→ Login", key="auth_login_btn"):
            ok, msg = login_user(uname, pwd)
            if ok:
                st.session_state.logged_in = True
                st.session_state.username = uname.strip()
                st.rerun()
            else:
                st.sidebar.error(msg)

    else:
        st.sidebar.caption("Username")
        uname = st.sidebar.text_input("Username", label_visibility="collapsed", key="reg_username")
        st.sidebar.caption("Email")
        email = st.sidebar.text_input("Email", label_visibility="collapsed", key="reg_email")
        st.sidebar.caption("Password")
        pwd = st.sidebar.text_input("Password", type="password", label_visibility="collapsed", key="reg_password")
        if st.sidebar.button("→ Register", key="auth_register_btn"):
            ok, msg = register_user(uname, email, pwd)
            if ok:
                st.sidebar.success(msg)
            else:
                st.sidebar.error(msg)

    return False
