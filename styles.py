"""
styles.py — App-wide CSS injected once at startup.
"""

APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=Inter:wght@300;400;500&display=swap');

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif; background: #0a0a0a; color: #f0f0f0; }
.stApp { background: #0a0a0a; }
.block-container { padding: 2rem 2.5rem !important; max-width: 1400px !important; }

/* Header */
.app-header { display: flex; align-items: baseline; gap: 1rem; margin-bottom: 2.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid #1e1e1e; }
.app-logo { font-family: 'Syne', sans-serif; font-size: 2.2rem; font-weight: 800; color: #fff; letter-spacing: -0.03em; line-height: 1; }
.app-logo span { color: #c8ff00; }
.app-subtitle { font-size: 0.75rem; font-weight: 400; color: #555; letter-spacing: 0.12em; text-transform: uppercase; }

/* Sidebar */
section[data-testid="stSidebar"] { background: #0f0f0f !important; border-right: 1px solid #1a1a1a !important; padding-top: 1rem; }
section[data-testid="stSidebar"] .block-container { padding: 1.5rem 1.2rem !important; }
.sidebar-label { font-family: 'Syne', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: #c8ff00; margin-bottom: 0.6rem; display: block; }

/* Buttons */
.stButton > button { background: #c8ff00 !important; color: #0a0a0a !important; border: none !important; border-radius: 2px !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; font-size: 0.8rem !important; letter-spacing: 0.08em !important; padding: 0.65rem 1.4rem !important; text-transform: uppercase !important; width: 100% !important; }
.stButton > button:hover { background: #fff !important; transform: translateY(-1px) !important; box-shadow: 0 4px 20px rgba(200,255,0,0.2) !important; }
.stDownloadButton > button { background: transparent !important; color: #c8ff00 !important; border: 1px solid #c8ff00 !important; border-radius: 2px !important; font-family: 'Syne', sans-serif !important; font-weight: 700 !important; font-size: 0.8rem !important; text-transform: uppercase !important; width: 100% !important; }
.stDownloadButton > button:hover { background: #c8ff00 !important; color: #0a0a0a !important; }

/* Message boxes */
.msg { padding: 0.8rem 1rem; border-radius: 2px; font-size: 0.82rem; margin-bottom: 1rem; line-height: 1.5; }
.msg-info    { background: #111; border-left: 3px solid #c8ff00; color: #888; }
.msg-success { background: #0d1a00; border-left: 3px solid #c8ff00; color: #a8d400; }
.msg-error   { background: #1a0000; border-left: 3px solid #ff4444; color: #ff8888; }
.msg-warning { background: #1a1000; border-left: 3px solid #ff9900; color: #ffbb55; }

/* Misc */
.section-title { font-family: 'Syne', sans-serif; font-size: 0.65rem; font-weight: 700; letter-spacing: 0.2em; text-transform: uppercase; color: #c8ff00; margin-bottom: 0.8rem; }
.divider { border: none; border-top: 1px solid #1a1a1a; margin: 1.5rem 0; }
.stSlider > div > div > div { background: #c8ff00 !important; }
.stNumberInput input { background: #111 !important; border: 1px solid #222 !important; color: #f0f0f0 !important; border-radius: 2px !important; }
.stRadio > div { gap: 0.4rem; }
.stRadio label { font-size: 0.85rem !important; color: #ccc !important; }
#MainMenu, footer, header { visibility: hidden; }
button[kind="headerNoPadding"], [data-testid="collapsedControl"] { display: flex !important; visibility: visible !important; opacity: 1 !important; color: #c8ff00 !important; }
[data-testid="stTickBarMin"], [data-testid="stTickBarMax"] { display: none !important; }
</style>
"""
