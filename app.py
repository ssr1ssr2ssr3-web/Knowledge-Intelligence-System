import streamlit as st
import os, io, time, requests
from dotenv import load_dotenv
from google import genai

try:
    import pdfplumber
except ImportError:
    pdfplumber = None
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None
try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

st.set_page_config(page_title="SuperChat · SRIN AI", page_icon="💬",
                   layout="centered", initial_sidebar_state="collapsed")

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ GEMINI_API_KEY not found"); st.stop()

client = genai.Client(api_key=api_key)
IDLE_TIMEOUT = 15 * 60

# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
defaults = {
    "theme": "Dark", "messages": [], "mode": "General",
    "doc_context": None, "doc_name": None,
    "url_context": None, "url_loaded": None,
    "fs": False, "last_active": time.time(),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

now = time.time()
if now - st.session_state.last_active > IDLE_TIMEOUT:
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()
st.session_state.last_active = now

qp = st.query_params
if "mode"  in qp and qp["mode"]  in ["General","Document","URL"]: st.session_state.mode  = qp["mode"]
if "theme" in qp: st.session_state.theme = "Light" if qp["theme"]=="light" else "Dark"
if "fs"    in qp: st.session_state.fs    = qp["fs"] == "1"
if qp.get("clear") == "1":
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.query_params.clear(); st.rerun()

current_mode = st.session_state.mode
is_fs        = st.session_state.fs

# ══════════════════════════════════════════════
# COLOURS
# ══════════════════════════════════════════════
DARK = {
    "chat_bg": "#0a1628", "card": "#0f2040", "card2": "#152848",
    "border": "#1a3060", "border2": "#234080",
    "text": "#e8f2ff", "text2": "#b8d0f0", "muted": "#6888b0",
    "accent": "#3b9eff", "accent2": "#00d4ff", "accent3": "#00c9a7",
    "user_bg": "linear-gradient(135deg,#1a3a70,#1e4888)", "user_border": "#2a5aaa",
    "ai_bg": "linear-gradient(135deg,#0a1e3a,#0e2448)", "ai_border": "#1a3060",
    "footer_bg": "#1565c0",
}
LIGHT = {
    "chat_bg": "#dce8f8", "card": "#ffffff", "card2": "#e8f0ff",
    "border": "#c0d0e8", "border2": "#a0bcdc",
    "text": "#0a1628", "text2": "#1a3050", "muted": "#4a6080",
    "accent": "#1a56db", "accent2": "#0891b2", "accent3": "#059669",
    "user_bg": "linear-gradient(135deg,#dbeafe,#bfdbfe)", "user_border": "#93c5fd",
    "ai_bg": "linear-gradient(135deg,#ffffff,#f0f6ff)", "ai_border": "#c0d0e8",
    "footer_bg": "#1976d2",
}
T = DARK if st.session_state.theme == "Dark" else LIGHT

SIDE_GRAD = "linear-gradient(160deg,#040a14 0%,#071020 25%,#091528 55%,#0c1c38 80%,#0e2040 100%)"

# ══════════════════════════════════════════════
# CSS — single stylesheet, media queries handle mobile/tablet/desktop
# NO JavaScript navigation — all device detection via CSS media queries
# ══════════════════════════════════════════════
top_offset = "0px" if is_fs else "68px"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── RESET ── */
html, body {{ margin:0; padding:0; box-sizing:border-box; height:100vh; overflow:hidden; }}
*, *::before, *::after {{ box-sizing:border-box; }}

/* ── HIDE CHROME ── */
#MainMenu, footer, header, [data-testid="stToolbar"],
[data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stSidebarNav"], .stDeployButton {{ display:none !important; }}

/* ══════════════════════════════════════════════
   MOBILE  <768px
   Full screen, header fixed top, input fixed bottom
   Chat area scrolls in between
   ══════════════════════════════════════════════ */
@media (max-width: 767px) {{
    .stApp {{
        background: {T["chat_bg"]} !important;
        font-family: 'Outfit', sans-serif !important;
        height: 100vh !important;
        overflow: hidden !important;
    }}
    .main, section.main {{
        padding: 0 !important;
        overflow: hidden !important;
        height: 100vh !important;
        width: 100vw !important;
        background: {T["chat_bg"]} !important;
    }}
    /* Chat scroll area — pinned between fixed header and footer */
    .block-container {{
        position: fixed !important;
        top: {top_offset} !important;
        bottom: 68px !important;
        left: 0 !important;
        right: 0 !important;
        padding: 10px !important;
        margin: 0 !important;
        width: 100vw !important;
        max-width: 100vw !important;
        overflow-y: auto !important;
        overflow-x: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        background: {T["chat_bg"]} !important;
        z-index: 10 !important;
    }}
    /* Message bubbles */
    [data-testid="stChatMessage"] {{
        border-radius: 14px !important;
        padding: 10px 14px !important;
        margin-bottom: 8px !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
        background: {T["user_bg"]} !important;
        border: 1px solid {T["user_border"]} !important;
        margin-left: 6% !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
        background: {T["ai_bg"]} !important;
        border: 1px solid {T["ai_border"]} !important;
        margin-right: 6% !important;
    }}
    [data-testid="stChatMessage"] p {{
        color: {T["text"]} !important; font-size: 14px !important;
        line-height: 1.6 !important; margin: 0 !important;
        font-family: 'Outfit', sans-serif !important;
    }}
    /* Bottom input bar */
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottom"] > div > div,
    [data-testid="stBottom"] > div > div > div {{
        background: {T["footer_bg"]} !important;
        border: none !important; box-shadow: none !important;
        padding: 0 !important; margin: 0 !important;
    }}
    [data-testid="stBottom"] {{
        position: fixed !important;
        bottom: 0 !important; left: 0 !important; right: 0 !important;
        height: 68px !important;
        z-index: 99999 !important;
        display: flex !important;
        align-items: center !important;
        padding: 9px 12px !important;
    }}
    [data-testid="stBottom"] > div {{
        width: 100% !important;
        display: flex !important; align-items: center !important;
    }}
    [data-testid="stChatInput"] {{
        width: 100% !important; background: transparent !important;
        border: none !important; box-shadow: none !important; padding: 0 !important;
        display: flex !important; align-items: center !important;
    }}
    [data-testid="stChatInput"] textarea {{
        background: #ffffff !important;
        color: #0a1628 !important; -webkit-text-fill-color: #0a1628 !important;
        border: none !important; border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important; font-size: 15px !important;
        padding: 12px 16px !important; line-height: 1.3 !important;
        caret-color: #1565c0 !important; outline: none !important;
        resize: none !important; box-shadow: none !important;
        width: 100% !important; min-height: 50px !important; max-height: 50px !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: #8fa8c8 !important; -webkit-text-fill-color: #8fa8c8 !important;
        font-style: italic !important; opacity: 1 !important;
    }}
    [data-testid="stChatInput"] button {{
        background: linear-gradient(135deg,#3b9eff,#00d4ff) !important;
        border: none !important; border-radius: 50% !important;
        width: 46px !important; height: 46px !important; min-width: 46px !important;
        box-shadow: 0 0 16px rgba(59,158,255,0.8) !important;
        flex-shrink: 0 !important; margin-left: 8px !important;
        cursor: pointer !important; transition: all 0.2s !important;
    }}
    [data-testid="stChatInput"] button svg {{
        fill: #ffffff !important; stroke: #ffffff !important;
        width: 20px !important; height: 20px !important;
    }}
}}

/* ══════════════════════════════════════════════
   TABLET  768px – 1099px
   Landing page gradient fills full .stApp (visible on sides)
   Centred chat panel 620px floats above it
   ══════════════════════════════════════════════ */
@media (min-width: 768px) and (max-width: 1099px) {{
    .stApp {{
        background: {SIDE_GRAD} !important;
        font-family: 'Outfit', sans-serif !important;
        height: 100vh !important;
        overflow: hidden !important;
    }}
    .stApp::before {{
        content: '';
        position: fixed; inset: 0;
        background-image: radial-gradient(circle, rgba(59,158,255,0.06) 1px, transparent 1px);
        background-size: 30px 30px;
        pointer-events: none; z-index: 0;
    }}
    .main, section.main {{
        padding: 0 !important; overflow: hidden !important;
        height: 100vh !important; background: transparent !important;
    }}
    /* Centred panel — dark navy, floating above gradient sides */
    .block-container {{
        position: fixed !important;
        top: 68px !important;
        bottom: 68px !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 620px !important;
        max-width: 94vw !important;
        padding: 12px 18px !important;
        margin: 0 !important;
        overflow-y: auto !important; overflow-x: hidden !important;
        -webkit-overflow-scrolling: touch !important;
        background: {T["chat_bg"]} !important;
        box-shadow: -60px 0 80px rgba(0,0,0,0.85), 60px 0 80px rgba(0,0,0,0.85),
                    0 0 0 1px rgba(59,158,255,0.1) !important;
        z-index: 10 !important;
    }}
    /* Message bubbles */
    [data-testid="stChatMessage"] {{
        border-radius: 14px !important;
        padding: 10px 14px !important;
        margin-bottom: 8px !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
        background: {T["user_bg"]} !important;
        border: 1px solid {T["user_border"]} !important;
        margin-left: 8% !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
        background: {T["ai_bg"]} !important;
        border: 1px solid {T["ai_border"]} !important;
        margin-right: 8% !important;
    }}
    [data-testid="stChatMessage"] p {{
        color: {T["text"]} !important; font-size: 14px !important;
        line-height: 1.65 !important; margin: 0 !important;
        font-family: 'Outfit', sans-serif !important;
    }}
    /* Tablet bottom bar — centred to match panel */
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div,
    [data-testid="stBottom"] > div > div,
    [data-testid="stBottom"] > div > div > div {{
        background: {T["footer_bg"]} !important;
        border: none !important; box-shadow: none !important;
        padding: 0 !important; margin: 0 !important;
    }}
    [data-testid="stBottom"] {{
        position: fixed !important;
        bottom: 0 !important;
        left: 50% !important;
        transform: translateX(-50%) !important;
        width: 620px !important;
        max-width: 94vw !important;
        height: 68px !important;
        z-index: 99999 !important;
        display: flex !important;
        align-items: center !important;
        padding: 9px 12px !important;
    }}
    [data-testid="stBottom"] > div {{
        width: 100% !important; display: flex !important; align-items: center !important;
    }}
    [data-testid="stChatInput"] {{
        width: 100% !important; background: transparent !important;
        border: none !important; box-shadow: none !important; padding: 0 !important;
        display: flex !important; align-items: center !important;
    }}
    [data-testid="stChatInput"] textarea {{
        background: #ffffff !important;
        color: #0a1628 !important; -webkit-text-fill-color: #0a1628 !important;
        border: none !important; border-radius: 12px !important;
        font-family: 'Outfit', sans-serif !important; font-size: 15px !important;
        padding: 12px 16px !important; line-height: 1.3 !important;
        caret-color: #1565c0 !important; outline: none !important;
        resize: none !important; box-shadow: none !important;
        width: 100% !important; min-height: 50px !important; max-height: 50px !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: #8fa8c8 !important; -webkit-text-fill-color: #8fa8c8 !important;
        font-style: italic !important; opacity: 1 !important;
    }}
    [data-testid="stChatInput"] button {{
        background: linear-gradient(135deg,#3b9eff,#00d4ff) !important;
        border: none !important; border-radius: 50% !important;
        width: 46px !important; height: 46px !important; min-width: 46px !important;
        box-shadow: 0 0 16px rgba(59,158,255,0.8) !important;
        flex-shrink: 0 !important; margin-left: 8px !important;
        cursor: pointer !important; transition: all 0.2s !important;
    }}
    [data-testid="stChatInput"] button svg {{
        fill: #ffffff !important; stroke: #ffffff !important;
        width: 20px !important; height: 20px !important;
    }}
}}

/* ══════════════════════════════════════════════
   DESKTOP  ≥1100px
   ══════════════════════════════════════════════ */
@media (min-width: 1100px) {{
    .stApp {{
        background: {SIDE_GRAD} !important;
        font-family: 'Outfit', sans-serif !important;
        min-height: 100vh;
    }}
    .stApp::before {{
        content: ''; position: fixed; inset: 0;
        background-image: radial-gradient(circle, rgba(59,158,255,0.05) 1px, transparent 1px);
        background-size: 30px 30px; pointer-events: none; z-index: 0;
    }}
    .block-container {{
        max-width: 800px !important; margin: 0 auto !important;
        padding: 1rem 1.5rem 5.5rem !important;
    }}
    [data-testid="stChatMessage"] {{
        border-radius: 14px !important;
        padding: 10px 16px !important;
        margin-bottom: 8px !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
        background: {T["user_bg"]} !important;
        border: 1px solid {T["user_border"]} !important;
        margin-left: 10% !important;
        box-shadow: 0 2px 12px rgba(59,158,255,0.15) !important;
    }}
    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
        background: {T["ai_bg"]} !important;
        border: 1px solid {T["ai_border"]} !important;
        margin-right: 10% !important;
    }}
    [data-testid="stChatMessage"] p {{
        color: {T["text"]} !important; font-size: 15px !important;
        line-height: 1.72 !important; margin: 0 !important;
        font-family: 'Outfit', sans-serif !important;
    }}
    [data-testid="stChatInput"] {{
        background: #0c1a32 !important; border: 1.5px solid {T["border2"]} !important;
        border-radius: 18px !important;
        box-shadow: 0 4px 28px rgba(0,0,0,0.4), 0 0 0 1px rgba(59,158,255,0.1) !important;
        backdrop-filter: blur(20px) !important; padding: 6px 8px !important;
    }}
    [data-testid="stChatInput"]:focus-within {{
        border-color: {T["accent"]} !important;
        box-shadow: 0 4px 32px rgba(59,158,255,0.25), 0 0 0 2px {T["accent"]}40 !important;
    }}
    [data-testid="stChatInput"] textarea {{
        background: #0c1a32 !important; color: #e8f2ff !important;
        -webkit-text-fill-color: #e8f2ff !important;
        font-family: 'Outfit', sans-serif !important; font-size: 15px !important;
        caret-color: {T["accent"]} !important; border: none !important;
        outline: none !important; resize: none !important;
        padding: 10px 14px !important; line-height: 1.5 !important;
    }}
    [data-testid="stChatInput"] textarea::placeholder {{
        color: {T["muted"]} !important; -webkit-text-fill-color: {T["muted"]} !important;
        font-style: italic !important;
    }}
    [data-testid="stChatInput"] button {{
        background: linear-gradient(135deg,{T["accent"]},{T["accent2"]}) !important;
        border: none !important; border-radius: 12px !important;
        width: 38px !important; height: 38px !important;
        box-shadow: 0 2px 10px {T["accent"]}50 !important;
    }}
    [data-testid="stChatInput"] button:hover {{ transform: scale(1.08) !important; }}
    [data-testid="stChatInput"] button svg {{ fill: #ffffff !important; stroke: #ffffff !important; }}
}}

/* ── SHARED across all sizes ── */
[data-testid="stChatMessage"] li {{
    color: {T["text2"]} !important; font-size: 13px !important;
}}
[data-testid="stChatMessage"] code {{
    font-family: 'JetBrains Mono', monospace !important; font-size: 11px !important;
    background: rgba(59,158,255,0.15) !important; color: {T["accent2"]} !important;
    padding: 1px 5px !important; border-radius: 4px !important;
}}
.stButton > button {{
    background: {T["card"]} !important; color: {T["muted"]} !important;
    border: 1px solid {T["border"]} !important; border-radius: 999px !important;
    font-family: 'Outfit', sans-serif !important; font-size: 12px !important;
    font-weight: 600 !important; padding: 4px 12px !important;
}}
.stButton > button:hover {{
    background: {T["card2"]} !important; border-color: {T["accent"]} !important;
    color: {T["accent"]} !important;
}}
[data-testid="stFileUploader"] {{
    background: {T["card"]} !important;
    border: 1.5px dashed {T["border2"]} !important; border-radius: 10px !important;
}}
.stTextInput input {{
    background: {T["card"]} !important; color: {T["text"]} !important;
    -webkit-text-fill-color: {T["text"]} !important;
    border: 1.5px solid {T["border2"]} !important;
    border-radius: 8px !important; font-size: 13px !important;
}}
.stAlert {{ border-radius: 10px !important; font-family: 'Outfit', sans-serif !important; }}
[data-testid="stToggle"] label {{ color: {T["muted"]} !important; font-size: 11px !important; }}
::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-thumb {{ background: {T["border2"]}; border-radius: 2px; }}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# IDLE TIMEOUT — using Streamlit's streamlit-js-eval workaround
# Since st.components navigation is blocked, we use meta refresh instead
# ══════════════════════════════════════════════
idle_elapsed = now - st.session_state.last_active
if idle_elapsed > IDLE_TIMEOUT:
    for k in list(st.session_state.keys()): del st.session_state[k]
    st.rerun()

# Warn at 12 min
if idle_elapsed > 12 * 60:
    remaining = int((IDLE_TIMEOUT - idle_elapsed) / 60)
    st.warning(f"⏱ Session expires in ~{remaining} min due to inactivity.")

# ══════════════════════════════════════════════
# DEVICE DETECTION — pure CSS media queries (no JS navigation)
# We detect device from the browser width using a hidden sentinel element
# JS postMessage to Streamlit sets the query param safely
# ══════════════════════════════════════════════
# Determine device from existing query param or default desktop
device = qp.get("device", "desktop")
if device not in ["mobile","tablet","desktop"]:
    device = "desktop"

# Device layout handled entirely by CSS media queries — no JS needed
# device variable kept for prompt optimization only (mobile = shorter answers)
is_mobile  = device == "mobile"
is_tablet  = device == "tablet"
is_desktop = device == "desktop"

# ══════════════════════════════════════════════
# HEADER — injected via st.markdown HTML (not JS)
# Mobile/tablet: fixed via CSS class + JS-free HTML link pills
# ══════════════════════════════════════════════
mode_colors = {"General":T["accent"],"Document":T["accent3"],"URL":T["accent2"]}
active_color = mode_colors[current_mode]
m_icons = {"General":"💬","Document":"📄","URL":"🔗"}

# Build mode pills as plain HTML links (no JS needed)
pills_html = ""
for m in ["General","Document","URL"]:
    active = current_mode == m
    col    = mode_colors[m]
    pbg    = col if active else "rgba(255,255,255,0.1)"
    pbrd   = col if active else "rgba(255,255,255,0.2)"
    pglow  = f"0 0 10px {col}90" if active else "none"
    pills_html += (
        f'<a href="?mode={m}" style="'
        f'background:{pbg};border:1.5px solid {pbrd};border-radius:999px;'
        f'padding:5px 12px;font-size:12px;font-weight:700;color:#fff;'
        f'text-decoration:none;white-space:nowrap;box-shadow:{pglow};'
        f'display:inline-flex;align-items:center;gap:4px;">'
        f'{m_icons[m]}</a>'
    )

theme_link = "light" if st.session_state.theme=="Dark" else "dark"
theme_icon = "☀️"   if st.session_state.theme=="Dark" else "🌙"
fs_icon    = "←"    if is_fs else "⛶"
fs_label   = " Back" if is_fs else " Full"
fs_next    = "0"    if is_fs else "1"

# Mobile/tablet header (fixed position via CSS)
if True:  # always show — CSS media query hides on desktop
    st.markdown(f"""
<style>
/* Fixed header for mobile and tablet */
@media (max-width: 1099px) {{
    .srin-hdr {{
        position: fixed !important;
        top: 0 !important; left: 0 !important; right: 0 !important;
        height: 68px !important;
        background: linear-gradient(135deg,{T["card"]},{T["card2"]}) !important;
        border-bottom: 1px solid {T["border2"]} !important;
        z-index: 999999 !important;
        display: flex !important;
        align-items: center !important;
        padding: 0 14px !important;
        gap: 0 !important;
        box-shadow: 0 2px 20px rgba(0,0,0,0.5) !important;
        font-family: 'Outfit', sans-serif !important;
    }}
}}
@media (min-width: 1100px) {{
    .srin-hdr {{ display: none !important; }}
}}
</style>
<div class="srin-hdr">
    <div style="display:flex;align-items:center;gap:10px;flex-shrink:0;">
        <div style="width:40px;height:40px;border-radius:11px;
            background:linear-gradient(135deg,{T["accent"]},{T["accent2"]});
            display:flex;align-items:center;justify-content:center;
            font-size:20px;box-shadow:0 0 14px {T["accent"]}50;flex-shrink:0;">💬</div>
        <div>
            <div style="font-size:16px;font-weight:800;color:{T["text"]};
                letter-spacing:-0.3px;line-height:1.1;white-space:nowrap;">
                SuperChat <span style="color:{T["accent"]};">AI</span></div>
            <div style="font-size:9px;color:{T["muted"]};letter-spacing:1.2px;
                text-transform:uppercase;font-weight:600;">SRIN AI Solutions</div>
        </div>
    </div>
    <div style="flex:1;min-width:8px;"></div>
    <div style="display:flex;gap:6px;align-items:center;flex-shrink:0;">
        {pills_html}
        <a href="?mode={current_mode}&fs={fs_next}" style="
            background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.2);
            border-radius:999px;padding:5px 10px;font-size:12px;font-weight:700;
            color:#fff;text-decoration:none;white-space:nowrap;">{fs_icon}{fs_label}</a>
    </div>
    <a href="?mode={current_mode}&theme={theme_link}" style="
        font-size:20px;text-decoration:none;flex-shrink:0;margin-left:10px;
        display:flex;align-items:center;justify-content:center;
        width:34px;height:34px;border-radius:50%;
        background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);">
        {theme_icon}</a>
</div>
""", unsafe_allow_html=True)

# Desktop header
st.markdown(f"""
<style>
@media (max-width: 1099px) {{ .srin-desktop-hdr {{ display: none !important; }} }}
</style>
<div class="srin-desktop-hdr" style="
    background:linear-gradient(135deg,{T['card']} 0%,{T['card2']} 100%);
    border:1px solid {T['border2']};border-radius:16px;
    padding:14px 22px;margin-bottom:12px;position:relative;overflow:hidden;
    box-shadow:0 4px 28px rgba(59,158,255,0.12);">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;
        background:linear-gradient(90deg,transparent,{T['accent']},{T['accent2']},transparent);"></div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
        <div style="display:flex;align-items:center;gap:12px;">
            <div style="width:46px;height:46px;border-radius:13px;
                background:linear-gradient(135deg,{T['accent']},{T['accent2']});
                display:flex;align-items:center;justify-content:center;
                font-size:23px;box-shadow:0 0 18px {T['accent']}50;flex-shrink:0;">💬</div>
            <div>
                <div style="font-size:21px;font-weight:800;color:{T['text']};letter-spacing:-0.5px;line-height:1.1;">
                    SuperChat&nbsp;<span style="color:{T['accent']};">AI</span></div>
                <div style="font-size:10px;color:{T['muted']};letter-spacing:1.5px;text-transform:uppercase;font-weight:600;">
                    🖥 SRIN AI Solutions</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="background:{T['accent']}18;border:1px solid {T['accent']}45;
                border-radius:999px;padding:3px 11px;font-size:9px;
                color:{T['accent']};font-weight:700;letter-spacing:1px;text-transform:uppercase;">
                gemini-2.5-flash</div>
            <div style="background:#00c9a720;border:1px solid #00c9a750;
                border-radius:999px;padding:3px 9px;font-size:9px;color:#00c9a7;font-weight:700;">● LIVE</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# Desktop mode buttons + theme toggle
col_m, col_t = st.columns([5,1])
with col_t:
    tog = st.toggle("🌙",value=(st.session_state.theme=="Dark"),key="ttog",label_visibility="collapsed")
    nt = "Dark" if tog else "Light"
    if nt != st.session_state.theme:
        st.session_state.theme = nt; st.rerun()
with col_m:
    mc = st.columns(3)
    for i,m in enumerate(["General","Document","URL"]):
        with mc[i]:
            active = current_mode == m
            if st.button(f"{'● ' if active else ''}{m_icons[m]} {m}",key=f"mb_{m}",use_container_width=True):
                if current_mode != m:
                    st.session_state.mode = m
                    st.session_state.messages = []
                    if m=="Document": st.session_state.doc_context=None; st.session_state.doc_name=None
                    elif m=="URL":    st.session_state.url_context=None; st.session_state.url_loaded=None
                    st.rerun()

st.markdown(f"""<div style="height:2px;border-radius:1px;margin-bottom:12px;
    background:linear-gradient(90deg,transparent,{active_color}99,{active_color},transparent);"></div>""",
    unsafe_allow_html=True)

# ══════════════════════════════════════════════
# DOCUMENT / URL PANELS
# ══════════════════════════════════════════════
if current_mode=="Document":
    st.markdown(f"""<div style="background:{T['card']};border:1px solid {T['border2']};
        border-left:3px solid {T['accent3']};border-radius:12px;padding:10px 16px;margin-bottom:8px;">
      <div style="font-size:12px;color:{T['accent3']};font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">
        📄 Upload Document</div>
      <div style="font-size:11px;color:{T['muted']};">PDF · DOCX · TXT&nbsp;·&nbsp;
        <span style="color:{T['accent']};">Session only.</span></div>
    </div>""", unsafe_allow_html=True)
    uploaded=st.file_uploader("upload",type=["pdf","docx","txt"],key="doc_upload",label_visibility="collapsed")
    if uploaded and uploaded.name!=st.session_state.doc_name:
        text=""
        try:
            if uploaded.type=="application/pdf":
                if pdfplumber:
                    with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                        text="\n\n".join(p.extract_text() or "" for p in pdf.pages)
            elif "wordprocessingml" in (uploaded.type or "") or uploaded.name.endswith(".docx"):
                if DocxDocument:
                    d=DocxDocument(io.BytesIO(uploaded.read()))
                    text="\n".join(p.text for p in d.paragraphs if p.text.strip())
            else:
                text=uploaded.read().decode("utf-8",errors="ignore")
            if text.strip():
                st.session_state.doc_context=text[:12000]; st.session_state.doc_name=uploaded.name
                st.session_state.messages=[]; st.success(f"✅ Loaded **{uploaded.name}** ({len(text):,} chars)")
            else: st.error("Could not extract text.")
        except Exception as e: st.error(f"Error: {e}")
    elif uploaded and uploaded.name==st.session_state.doc_name:
        st.info(f"📄 Active: **{st.session_state.doc_name}**")

elif current_mode=="URL":
    st.markdown(f"""<div style="background:{T['card']};border:1px solid {T['border2']};
        border-left:3px solid {T['accent2']};border-radius:12px;padding:10px 16px;margin-bottom:8px;">
      <div style="font-size:12px;color:{T['accent2']};font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">
        🔗 Load a URL</div>
      <div style="font-size:11px;color:{T['muted']};">Any public page · docs · blogs.&nbsp;
        <span style="color:{T['accent']};">Session only.</span></div>
    </div>""", unsafe_allow_html=True)
    url_val=st.text_input("url",placeholder="https://docs.aws.amazon.com/...",key="url_box",label_visibility="collapsed")
    c1,c2=st.columns([4,1])
    with c1: load_btn=st.button("⚡ Load",key="load_url",use_container_width=True)
    with c2:
        if st.button("✕",key="clr_url",use_container_width=True):
            st.session_state.url_context=None; st.session_state.url_loaded=None
            st.session_state.messages=[]; st.rerun()
    if load_btn and url_val:
        with st.spinner("Fetching..."):
            try:
                r=requests.get(url_val,headers={"User-Agent":"Mozilla/5.0 SuperChatBot/1.0"},timeout=12)
                r.raise_for_status()
                if BeautifulSoup:
                    soup=BeautifulSoup(r.text,"html.parser")
                    for tag in soup(["script","style","nav","footer","header","aside","iframe"]): tag.decompose()
                    raw=soup.get_text(separator="\n",strip=True)
                else: raw=r.text
                lines=[l.strip() for l in raw.splitlines() if l.strip()]
                clean="\n".join(lines)
                st.session_state.url_context=clean[:12000]; st.session_state.url_loaded=url_val
                st.session_state.messages=[]; st.success(f"✅ Loaded ({len(clean):,} chars)")
            except requests.exceptions.Timeout: st.error("⏱ Timed out.")
            except Exception as e: st.error(f"Error: {e}")
    if st.session_state.url_loaded: st.info(f"🔗 `{st.session_state.url_loaded[:60]}`")

# ══════════════════════════════════════════════
# EMPTY STATE
# ══════════════════════════════════════════════
doc_missing = current_mode=="Document" and not st.session_state.doc_context
url_missing = current_mode=="URL"      and not st.session_state.url_context

if not st.session_state.messages and not doc_missing and not url_missing:
    hints={"General":("💬","Ask me anything","Try: What is LangChain?"),
           "Document":("📄","Ready","Ask: Summarise this document"),
           "URL":("🔗","Page loaded","Ask: What is this page about?")}
    ico,title,hint=hints[current_mode]
    st.markdown(f"""<div style="text-align:center;padding:44px 20px;color:{T['muted']};">
      <div style="font-size:44px;margin-bottom:10px;">{ico}</div>
      <div style="font-size:17px;font-weight:700;color:{T['text']};margin-bottom:8px;">{title}</div>
      <div style="font-size:12px;color:{T['muted']};font-style:italic;
        background:{T['card']};border:1px solid {T['border']};
        border-radius:8px;padding:6px 14px;display:inline-block;">{hint}</div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CHAT HISTORY
# ══════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]): st.markdown(msg["content"])

# ══════════════════════════════════════════════
# PROMPT + INPUT
# ══════════════════════════════════════════════
def build_prompt(u):
    mob = "IMPORTANT: Mobile user. Max 120 words. Bullet points.\n\n" if is_mobile else ""
    m = st.session_state.mode
    if m=="Document" and st.session_state.doc_context:
        return f"{mob}Answer ONLY from the document.\n\n=== DOC ===\n{st.session_state.doc_context}\n=== END ===\n\nQ: {u}"
    if m=="URL" and st.session_state.url_context:
        return f"{mob}Answer ONLY from the page. Source:{st.session_state.url_loaded}\n\n=== PAGE ===\n{st.session_state.url_context}\n=== END ===\n\nQ: {u}"
    return f"{mob}{u}"

ph={"General":"✦  Ask me anything...",
    "Document":"✦  Ask about the document..." if not doc_missing else "Upload a document first...",
    "URL":"✦  Ask about the page..." if not url_missing else "Load a URL first..."}

if prompt:=st.chat_input(ph[current_mode],disabled=(doc_missing or url_missing)):
    st.session_state.last_active=time.time()
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"): st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                reply=client.models.generate_content(model="gemini-2.5-flash",contents=build_prompt(prompt)).text
                st.markdown(reply)
                st.session_state.messages.append({"role":"assistant","content":reply})
            except Exception as e:
                err=f"⚠️ {e}"; st.error(err)
                st.session_state.messages.append({"role":"assistant","content":err})

# ══════════════════════════════════════════════
# DESKTOP STATUS BAR
# ══════════════════════════════════════════════
mc2=len([m for m in st.session_state.messages if m["role"]=="user"])
ie=now-st.session_state.last_active; ip=min(100,int(ie/IDLE_TIMEOUT*100))
st.markdown(f"""
<style>
@media (max-width: 1099px) {{ .srin-status {{ display: none !important; }} }}
</style>
<div class="srin-status" style="position:fixed;bottom:0;left:50%;transform:translateX(-50%);
    width:min(800px,98vw);background:{T['card']};border-top:1px solid {T['border']};
    padding:5px 16px;display:flex;align-items:center;justify-content:space-between;
    z-index:9999;font-family:'Outfit',sans-serif;backdrop-filter:blur(16px);">
  <div style="position:absolute;top:0;left:0;right:0;height:2px;background:{T['border']};">
    <div style="height:2px;width:{ip}%;background:{'linear-gradient(90deg,#ff8800,#ff4444)' if ip>80 else f'linear-gradient(90deg,{T["accent"]},{T["accent2"]})'};">
    </div></div>
  <div style="display:flex;align-items:center;gap:6px;">
    <div style="width:7px;height:7px;border-radius:50%;background:{active_color};box-shadow:0 0 6px {active_color}80;"></div>
    <span style="font-size:11px;color:{T['muted']};">💬 {current_mode}</span>
  </div>
  <div style="font-size:10px;color:{T['muted']};display:flex;align-items:center;gap:8px;">
    <span>🖥 Desktop</span><span>·</span><span>{mc2} msg{"s" if mc2!=1 else ""}</span><span>·</span>
    <span>⏱ {int((IDLE_TIMEOUT-ie)/60)}m left</span>
  </div>
</div>""",unsafe_allow_html=True)
