import streamlit as st
import os
import io
import time
import requests
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

# ══════════════════════════════════════════════
# PAGE CONFIG — must be FIRST
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="SuperChat · SRIN AI",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ GEMINI_API_KEY not found in .env")
    st.stop()

client = genai.Client(api_key=api_key)
IDLE_TIMEOUT = 15 * 60

# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
defaults = {
    "theme":       "Dark",
    "messages":    [],
    "mode":        "General",
    "doc_context": None,
    "doc_name":    None,
    "url_context": None,
    "url_loaded":  None,
    "is_mobile":   False,
    "last_active": time.time(),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# Idle timeout
now = time.time()
if now - st.session_state.last_active > IDLE_TIMEOUT:
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
st.session_state.last_active = now

# Query params
qp = st.query_params
if "mobile" in qp:
    st.session_state.is_mobile = (qp["mobile"] == "1")
if "mode" in qp and qp["mode"] in ["General","Document","URL"]:
    st.session_state.mode = qp["mode"]
if qp.get("clear") == "1":
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.query_params.clear()
    st.rerun()

is_mobile = st.session_state.is_mobile

# ══════════════════════════════════════════════
# THEME
# ══════════════════════════════════════════════
DARK = {
    "bg":           "#07112a",
    "chat_bg":      "#0a1628",
    "card":         "#0f2040",
    "card2":        "#152848",
    "border":       "#1a3060",
    "border2":      "#234080",
    "text":         "#e8f2ff",
    "text2":        "#b8d0f0",
    "muted":        "#6888b0",
    "accent":       "#3b9eff",
    "accent2":      "#00d4ff",
    "accent3":      "#00c9a7",
    "user_bg":      "linear-gradient(135deg,#1a3a70,#1e4888)",
    "user_border":  "#2a5aaa",
    "ai_bg":        "linear-gradient(135deg,#0a1e3a,#0e2448)",
    "ai_border":    "#1a3060",
    "input_bg":     "#ffffff",
    "input_text":   "#0a1628",
    "input_border": "#c8d8f0",
    "footer_bg":    "#ffffff",
}
LIGHT = {
    "bg":           "#e8f2ff",
    "chat_bg":      "#dce8f8",
    "card":         "#ffffff",
    "card2":        "#e8f0ff",
    "border":       "#c0d0e8",
    "border2":      "#a0bcdc",
    "text":         "#0a1628",
    "text2":        "#1a3050",
    "muted":        "#4a6080",
    "accent":       "#1a56db",
    "accent2":      "#0891b2",
    "accent3":      "#059669",
    "user_bg":      "linear-gradient(135deg,#dbeafe,#bfdbfe)",
    "user_border":  "#93c5fd",
    "ai_bg":        "linear-gradient(135deg,#ffffff,#f0f6ff)",
    "ai_border":    "#c0d0e8",
    "input_bg":     "#ffffff",
    "input_text":   "#0a1628",
    "input_border": "#a0bcdc",
    "footer_bg":    "#ffffff",
}
T = DARK if st.session_state.theme == "Dark" else LIGHT

# ══════════════════════════════════════════════
# CSS
# ══════════════════════════════════════════════
if is_mobile:
    # ── MOBILE LAYOUT: fixed header + fixed footer, scrollable middle ──
    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}
html, body {{ height: 100%; overflow: hidden; margin: 0; padding: 0; }}

/* Hide ALL Streamlit chrome */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
.stDeployButton,
[data-testid="collapsedControl"] {{ display: none !important; }}

/* Full screen app */
.stApp {{
    background: {T["chat_bg"]} !important;
    font-family: 'Outfit', sans-serif !important;
    height: 100vh !important;
    overflow: hidden !important;
    display: flex !important;
    flex-direction: column !important;
}}

/* Remove ALL streamlit padding */
.main, .block-container {{
    padding: 0 !important;
    margin: 0 !important;
    max-width: 100% !important;
    width: 100% !important;
    height: 100% !important;
}}

[data-testid="stVerticalBlock"] {{
    gap: 0 !important;
    padding: 0 !important;
}}

/* ── FIXED TOP HEADER — 10vh ── */
.mobile-header {{
    position: fixed !important;
    top: 0 !important; left: 0 !important; right: 0 !important;
    height: 10vh !important;
    min-height: 56px !important;
    background: linear-gradient(135deg,{T["card"]} 0%,{T["card2"]} 100%) !important;
    border-bottom: 1px solid {T["border2"]} !important;
    z-index: 1000 !important;
    display: flex !important;
    align-items: center !important;
    padding: 0 14px !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.3) !important;
}}

/* ── SCROLLABLE CHAT AREA — between header and footer ── */
[data-testid="stBottom"] {{
    display: none !important;
}}

.chat-scroll-area {{
    position: fixed !important;
    top: 10vh !important;
    bottom: 10vh !important;
    left: 0 !important; right: 0 !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding: 10px 12px 10px !important;
    background: {T["chat_bg"]} !important;
    -webkit-overflow-scrolling: touch !important;
}}

/* ── FIXED BOTTOM INPUT — 10vh ── */
.mobile-footer {{
    position: fixed !important;
    bottom: 0 !important; left: 0 !important; right: 0 !important;
    height: 10vh !important;
    min-height: 56px !important;
    background: {T["footer_bg"]} !important;
    border-top: 1px solid {T["input_border"]} !important;
    z-index: 1000 !important;
    display: flex !important;
    align-items: center !important;
    padding: 0 10px !important;
    gap: 8px !important;
}}

/* ── CHAT MESSAGES ── */
[data-testid="stChatMessage"] {{
    border-radius: 12px !important;
    padding: 8px 12px !important;
    margin-bottom: 6px !important;
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
    color: {T["text"]} !important;
    font-size: 13px !important;
    line-height: 1.55 !important;
    margin: 0 !important;
    font-family: 'Outfit', sans-serif !important;
}}

[data-testid="stChatMessage"] li {{
    color: {T["text2"]} !important;
    font-size: 13px !important;
}}

[data-testid="stChatMessage"] code {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    background: rgba(59,158,255,0.12) !important;
    color: {T["accent2"]} !important;
    padding: 1px 5px !important;
    border-radius: 4px !important;
}}

/* ── CHAT INPUT — simple clean white box ── */
[data-testid="stChatInput"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    flex: 1 !important;
}}

[data-testid="stChatInput"] textarea {{
    background: {T["input_bg"]} !important;
    color: {T["input_text"]} !important;
    -webkit-text-fill-color: {T["input_text"]} !important;
    border: 1.5px solid {T["input_border"]} !important;
    border-radius: 22px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 14px !important;
    padding: 10px 16px !important;
    line-height: 1.4 !important;
    caret-color: {T["accent"]} !important;
    outline: none !important;
    resize: none !important;
    box-shadow: 0 1px 6px rgba(0,0,0,0.08) !important;
}}

[data-testid="stChatInput"] textarea:focus {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 0 0 2px {T["accent"]}20 !important;
}}

[data-testid="stChatInput"] textarea::placeholder {{
    color: #94a3b8 !important;
    -webkit-text-fill-color: #94a3b8 !important;
    font-style: italic !important;
    font-size: 13px !important;
}}

/* Send button */
[data-testid="stChatInput"] button {{
    background: {T["accent"]} !important;
    border: none !important;
    border-radius: 50% !important;
    width: 36px !important;
    height: 36px !important;
    box-shadow: 0 2px 8px {T["accent"]}40 !important;
    flex-shrink: 0 !important;
}}

[data-testid="stChatInput"] button svg {{
    fill: #ffffff !important;
    stroke: #ffffff !important;
}}

/* ── BUTTONS ── */
.stButton > button {{
    background: transparent !important;
    color: {T["muted"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 999px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 11px !important;
    font-weight: 600 !important;
    padding: 3px 10px !important;
}}

.stButton > button:hover {{
    border-color: {T["accent"]} !important;
    color: {T["accent"]} !important;
}}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {{
    background: {T["card"]} !important;
    border: 1.5px dashed {T["border2"]} !important;
    border-radius: 10px !important;
}}

/* ── TEXT INPUT ── */
.stTextInput input {{
    background: {T["input_bg"]} !important;
    color: {T["input_text"]} !important;
    -webkit-text-fill-color: {T["input_text"]} !important;
    border: 1.5px solid {T["border2"]} !important;
    border-radius: 8px !important;
    font-size: 12px !important;
}}

::-webkit-scrollbar {{ width: 3px; }}
::-webkit-scrollbar-thumb {{ background: {T["border2"]}; border-radius: 2px; }}

iframe[height="0"] {{
    position: absolute !important; width: 0 !important;
    height: 0 !important; border: none !important;
    pointer-events: none !important;
}}
</style>
"""
else:
    # ── DESKTOP LAYOUT ──
    css = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

.stApp {{
    background: linear-gradient(160deg,#040a14 0%,#071020 25%,#091528 55%,#0c1c38 80%,#0e2040 100%) !important;
    font-family: 'Outfit', sans-serif !important;
    min-height: 100vh;
}}

.stApp::before {{
    content: '';
    position: fixed; inset: 0;
    background-image: radial-gradient(circle,rgba(59,158,255,0.05) 1px,transparent 1px);
    background-size: 30px 30px;
    pointer-events: none; z-index: 0;
}}

.block-container {{
    max-width: 800px !important;
    margin: 0 auto !important;
    padding: 1rem 1.5rem 5.5rem !important;
}}

#MainMenu, footer, header,
[data-testid="stToolbar"],
.stDeployButton {{ display: none !important; }}

::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-thumb {{ background: {T["border2"]}; border-radius: 4px; }}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
    background: {T["user_bg"]} !important;
    border: 1px solid {T["user_border"]} !important;
    border-radius: 14px !important;
    padding: 10px 16px !important;
    margin-left: 10% !important;
    margin-bottom: 8px !important;
    box-shadow: 0 2px 12px rgba(59,158,255,0.15) !important;
}}

[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
    background: {T["ai_bg"]} !important;
    border: 1px solid {T["ai_border"]} !important;
    border-radius: 14px !important;
    padding: 10px 16px !important;
    margin-right: 10% !important;
    margin-bottom: 8px !important;
}}

[data-testid="stChatMessage"] p {{
    color: {T["text"]} !important;
    font-size: 15px !important;
    line-height: 1.72 !important;
    margin: 0 !important;
    font-family: 'Outfit', sans-serif !important;
}}

[data-testid="stChatMessage"] code {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 12px !important;
    background: rgba(59,158,255,0.12) !important;
    color: {T["accent2"]} !important;
    padding: 1px 6px !important; border-radius: 4px !important;
}}

[data-testid="stChatInput"] {{
    background: #0c1a32 !important;
    border: 1.5px solid {T["border2"]} !important;
    border-radius: 18px !important;
    box-shadow: 0 4px 28px rgba(0,0,0,0.4),0 0 0 1px rgba(59,158,255,0.1) !important;
    backdrop-filter: blur(20px) !important;
    padding: 6px 8px !important;
}}

[data-testid="stChatInput"]:focus-within {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 4px 32px rgba(59,158,255,0.25),0 0 0 2px {T["accent"]}40 !important;
}}

[data-testid="stChatInput"] textarea {{
    background: #0c1a32 !important;
    color: #e8f2ff !important;
    -webkit-text-fill-color: #e8f2ff !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 15px !important;
    caret-color: {T["accent"]} !important;
    border: none !important; outline: none !important;
    resize: none !important;
    padding: 10px 14px !important;
    line-height: 1.5 !important;
}}

[data-testid="stChatInput"] textarea::placeholder {{
    color: {T["muted"]} !important;
    -webkit-text-fill-color: {T["muted"]} !important;
    font-style: italic !important;
}}

[data-testid="stChatInput"] button {{
    background: linear-gradient(135deg,{T["accent"]},{T["accent2"]}) !important;
    border: none !important; border-radius: 12px !important;
    width: 38px !important; height: 38px !important;
    box-shadow: 0 2px 10px {T["accent"]}50 !important;
}}

[data-testid="stChatInput"] button:hover {{
    transform: scale(1.08) !important;
}}

[data-testid="stChatInput"] button svg {{
    fill: #ffffff !important; stroke: #ffffff !important;
}}

.stButton > button {{
    background: {T["card"]} !important;
    color: {T["muted"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 999px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: 13px !important; font-weight: 600 !important;
    padding: 5px 14px !important;
}}

.stButton > button:hover {{
    background: {T["card2"]} !important;
    border-color: {T["accent"]} !important;
    color: {T["accent"]} !important;
    transform: translateY(-1px) !important;
}}

[data-testid="stFileUploader"] {{
    background: {T["card"]} !important;
    border: 1.5px dashed {T["border2"]} !important;
    border-radius: 12px !important;
}}

.stTextInput input {{
    background: #0c1a32 !important;
    color: #e8f2ff !important;
    -webkit-text-fill-color: #e8f2ff !important;
    border: 1.5px solid {T["border2"]} !important;
    border-radius: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
}}

.stTextInput input:focus {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 0 0 2px {T["accent"]}25 !important;
}}

.stTextInput label {{ color: {T["muted"]} !important; font-size: 11px !important; }}
[data-testid="stToggle"] label {{ color: {T["muted"]} !important; font-size: 11px !important; }}
.stAlert {{ border-radius: 10px !important; font-family: 'Outfit', sans-serif !important; }}

iframe[height="0"] {{
    position: absolute !important; width: 0 !important;
    height: 0 !important; border: none !important;
    pointer-events: none !important;
}}
</style>
"""

st.markdown(css, unsafe_allow_html=True)

# ══════════════════════════════════════════════
# JS — mobile detect + idle timeout
# ══════════════════════════════════════════════
st.components.v1.html("""
<script>
(function(){
  try {
    var w = window.parent.innerWidth || window.innerWidth || screen.width;
    var val = (w < 768) ? '1' : '0';
    var url = new URL(window.parent.location.href);
    if(url.searchParams.get('mobile') !== val){
      url.searchParams.set('mobile', val);
      window.parent.location.replace(url.toString());
    }
  } catch(e){}
})();
</script>
""", height=0, scrolling=False)

st.components.v1.html(f"""
<script>
(function(){{
  var IDLE = {IDLE_TIMEOUT * 1000};
  var t;
  function reset(){{
    clearTimeout(t);
    t = setTimeout(function(){{
      try {{
        var url = new URL(window.parent.location.href);
        url.searchParams.set('clear','1');
        window.parent.location.replace(url.toString());
      }} catch(e){{}}
    }}, IDLE);
  }}
  ['mousemove','keydown','click','scroll','touchstart','touchmove']
    .forEach(function(e){{ window.parent.addEventListener(e, reset, true); }});
  reset();
}})();
</script>
""", height=0, scrolling=False)

# ══════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════
mode_icons  = {"General":"💬","Document":"📄","URL":"🔗"}
mode_colors = {"General":T["accent"],"Document":T["accent3"],"URL":T["accent2"]}
active_color = mode_colors[st.session_state.mode]
# Build mode pills HTML for mobile header
mode_pills_html = ""
for _m in ["General", "Document", "URL"]:
    _active = st.session_state.mode == _m
    _bg     = T["accent"] if _active else "rgba(255,255,255,0.08)"
    _col    = "#ffffff"   if _active else T["muted"]
    _bord   = T["accent"] if _active else T["border"]
    mode_pills_html += (
        f'<a href="?mode={_m}&mobile=1" style="' +
        f'background:{_bg};color:{_col};border:1px solid {_bord};' +
        f'border-radius:999px;padding:3px 8px;font-size:10px;font-weight:600;' +
        f'text-decoration:none;font-family:Outfit,sans-serif;white-space:nowrap;">' +
        f'{mode_icons[_m]}</a>'
    )

if is_mobile:
    # Fixed mobile header rendered as HTML
    st.markdown(f"""
<div class="mobile-header">
    <div style="display:flex;align-items:center;gap:10px;flex:1;min-width:0;">
        <div style="
            width:36px;height:36px;border-radius:10px;flex-shrink:0;
            background:linear-gradient(135deg,{T['accent']},{T['accent2']});
            display:flex;align-items:center;justify-content:center;
            font-size:18px;box-shadow:0 0 12px {T['accent']}40;
        ">💬</div>
        <div style="min-width:0;">
            <div style="font-size:16px;font-weight:800;color:{T['text']};
                letter-spacing:-0.3px;line-height:1.1;white-space:nowrap;">
                SuperChat <span style="color:{T['accent']};">AI</span>
            </div>
            <div style="font-size:9px;color:{T['muted']};letter-spacing:1px;
                text-transform:uppercase;font-weight:600;">SRIN AI Solutions</div>
        </div>
    </div>
    <!-- Mode pills -->\n    <div style="display:flex;gap:4px;flex-shrink:0;">\n        {mode_pills_html}
    </div>
    <!-- Theme toggle -->
    <div style="margin-left:6px;flex-shrink:0;">
        <a href="?mode={st.session_state.mode}&mobile=1&theme={'light' if st.session_state.theme=='Dark' else 'dark'}"
            style="font-size:16px;text-decoration:none;">
            {'🌙' if st.session_state.theme=='Dark' else '☀️'}
        </a>
    </div>
</div>
<div style="height:10vh;min-height:56px;"></div>
""", unsafe_allow_html=True)

    # Handle theme toggle via query param
    if qp.get("theme") == "light" and st.session_state.theme == "Dark":
        st.session_state.theme = "Light"
        st.rerun()
    elif qp.get("theme") == "dark" and st.session_state.theme == "Light":
        st.session_state.theme = "Dark"
        st.rerun()

else:
    # Desktop header
    st.markdown(f"""
<div style="
    background:linear-gradient(135deg,{T['card']} 0%,{T['card2']} 100%);
    border:1px solid {T['border2']};border-radius:16px;
    padding:14px 22px;margin-bottom:12px;position:relative;overflow:hidden;
    box-shadow:0 4px 28px rgba(59,158,255,0.12);
">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;
        background:linear-gradient(90deg,transparent,{T['accent']},{T['accent2']},transparent);">
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
        <div style="display:flex;align-items:center;gap:12px;">
            <div style="
                width:46px;height:46px;border-radius:13px;
                background:linear-gradient(135deg,{T['accent']},{T['accent2']});
                display:flex;align-items:center;justify-content:center;
                font-size:23px;box-shadow:0 0 18px {T['accent']}50;flex-shrink:0;
            ">💬</div>
            <div>
                <div style="font-family:'Outfit',sans-serif;font-size:21px;
                    font-weight:800;color:{T['text']};letter-spacing:-0.5px;line-height:1.1;">
                    SuperChat&nbsp;<span style="color:{T['accent']};">AI</span>
                </div>
                <div style="font-size:10px;color:{T['muted']};letter-spacing:1.5px;
                    text-transform:uppercase;font-weight:600;">
                    🖥 SRIN AI Solutions
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="background:{T['accent']}18;border:1px solid {T['accent']}45;
                border-radius:999px;padding:3px 11px;font-size:9px;
                color:{T['accent']};font-weight:700;letter-spacing:1px;text-transform:uppercase;">
                gemini-2.5-flash
            </div>
            <div style="background:#00c9a720;border:1px solid #00c9a750;
                border-radius:999px;padding:3px 9px;font-size:9px;
                color:#00c9a7;font-weight:700;">● LIVE
            </div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

    # Desktop: mode pills + theme toggle
    col_modes, col_toggle = st.columns([5,1])
    with col_toggle:
        tog = st.toggle("🌙", value=(st.session_state.theme=="Dark"),
                        key="theme_tog", label_visibility="collapsed")
        nt = "Dark" if tog else "Light"
        if nt != st.session_state.theme:
            st.session_state.theme = nt
            st.rerun()
    with col_modes:
        mc = st.columns(3)
        for i, m in enumerate(["General","Document","URL"]):
            with mc[i]:
                active = st.session_state.mode == m
                lbl = f"{'● ' if active else ''}{mode_icons[m]} {m}"
                if st.button(lbl, key=f"mbtn_{m}", use_container_width=True):
                    if st.session_state.mode != m:
                        st.session_state.mode = m
                        st.session_state.messages = []
                        if m == "Document":
                            st.session_state.doc_context = None
                            st.session_state.doc_name = None
                        elif m == "URL":
                            st.session_state.url_context = None
                            st.session_state.url_loaded = None
                        st.rerun()

    st.markdown(f"""
<div style="height:2px;border-radius:1px;margin-bottom:12px;
    background:linear-gradient(90deg,transparent,{active_color}99,{active_color},transparent);">
</div>""", unsafe_allow_html=True)

current_mode = st.session_state.mode

# ══════════════════════════════════════════════
# DOCUMENT / URL PANELS
# ══════════════════════════════════════════════
if current_mode == "Document":
    st.markdown(f"""
<div style="background:{T['card']};border:1px solid {T['border2']};
    border-left:3px solid {T['accent3']};
    border-radius:{'10px' if is_mobile else '12px'};
    padding:{'8px 12px' if is_mobile else '10px 16px'};
    margin-bottom:{'6px' if is_mobile else '10px'};">
    <div style="font-size:{'11px' if is_mobile else '12px'};color:{T['accent3']};
        font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">
        📄 Upload Document
    </div>
    <div style="font-size:{'10px' if is_mobile else '11px'};color:{T['muted']};">
        PDF · DOCX · TXT &nbsp;·&nbsp;
        <span style="color:{T['accent']};">Session only — never stored.</span>
    </div>
</div>""", unsafe_allow_html=True)

    uploaded = st.file_uploader("upload", type=["pdf","docx","txt"],
                                key="doc_upload", label_visibility="collapsed")
    if uploaded and uploaded.name != st.session_state.doc_name:
        text = ""
        try:
            if uploaded.type == "application/pdf":
                if pdfplumber:
                    with pdfplumber.open(io.BytesIO(uploaded.read())) as pdf:
                        text = "\n\n".join(p.extract_text() or "" for p in pdf.pages)
                else:
                    st.warning("Run: uv pip install pdfplumber")
            elif "wordprocessingml" in (uploaded.type or "") or uploaded.name.endswith(".docx"):
                if DocxDocument:
                    d = DocxDocument(io.BytesIO(uploaded.read()))
                    text = "\n".join(p.text for p in d.paragraphs if p.text.strip())
                else:
                    st.warning("Run: uv pip install python-docx")
            else:
                text = uploaded.read().decode("utf-8", errors="ignore")
            if text.strip():
                mc = 6000 if is_mobile else 12000
                st.session_state.doc_context = text[:mc]
                st.session_state.doc_name    = uploaded.name
                st.session_state.messages    = []
                st.success(f"✅ Loaded **{uploaded.name}** ({len(text):,} chars)")
            else:
                st.error("Could not extract text.")
        except Exception as e:
            st.error(f"Error: {e}")
    elif uploaded and uploaded.name == st.session_state.doc_name:
        st.info(f"📄 Active: **{st.session_state.doc_name}**")

elif current_mode == "URL":
    st.markdown(f"""
<div style="background:{T['card']};border:1px solid {T['border2']};
    border-left:3px solid {T['accent2']};
    border-radius:{'10px' if is_mobile else '12px'};
    padding:{'8px 12px' if is_mobile else '10px 16px'};
    margin-bottom:{'6px' if is_mobile else '10px'};">
    <div style="font-size:{'11px' if is_mobile else '12px'};color:{T['accent2']};
        font-weight:700;letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">
        🔗 Load a URL
    </div>
    <div style="font-size:{'10px' if is_mobile else '11px'};color:{T['muted']};">
        Any public page · docs · blogs · knowledge bases.&nbsp;
        <span style="color:{T['accent']};">Session only — never stored.</span>
    </div>
</div>""", unsafe_allow_html=True)

    url_val = st.text_input("url", placeholder="https://docs.aws.amazon.com/...",
                            key="url_box", label_visibility="collapsed")
    c1, c2 = st.columns([4,1])
    with c1:
        load_btn = st.button("⚡ Load", key="load_url", use_container_width=True)
    with c2:
        if st.button("✕", key="clr_url", use_container_width=True):
            st.session_state.url_context = None
            st.session_state.url_loaded  = None
            st.session_state.messages    = []
            st.rerun()
    if load_btn and url_val:
        with st.spinner("Fetching..."):
            try:
                r = requests.get(url_val,
                    headers={"User-Agent":"Mozilla/5.0 SuperChatBot/1.0"}, timeout=12)
                r.raise_for_status()
                if BeautifulSoup:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for tag in soup(["script","style","nav","footer","header","aside","iframe"]):
                        tag.decompose()
                    raw = soup.get_text(separator="\n", strip=True)
                else:
                    raw = r.text
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                clean = "\n".join(lines)
                mc = 6000 if is_mobile else 12000
                st.session_state.url_context = clean[:mc]
                st.session_state.url_loaded  = url_val
                st.session_state.messages    = []
                st.success(f"✅ Loaded ({len(clean):,} chars)")
            except requests.exceptions.Timeout:
                st.error("⏱ Timed out.")
            except Exception as e:
                st.error(f"Error: {e}")
    if st.session_state.url_loaded:
        st.info(f"🔗 `{st.session_state.url_loaded[:60]}`")

# ══════════════════════════════════════════════
# EMPTY STATE
# ══════════════════════════════════════════════
doc_missing = current_mode == "Document" and not st.session_state.doc_context
url_missing = current_mode == "URL"      and not st.session_state.url_context

if not st.session_state.messages and not doc_missing and not url_missing:
    hints = {
        "General":  ("💬","Ask me anything","Try: What is LangChain?"),
        "Document": ("📄","Ready","Ask: Summarise this document"),
        "URL":      ("🔗","Page loaded","Ask: What is this page about?"),
    }
    ico, title, hint = hints[current_mode]
    st.markdown(f"""
<div style="text-align:center;padding:{'20px 10px' if is_mobile else '44px 20px'};color:{T['muted']};">
    <div style="font-size:{'32px' if is_mobile else '44px'};margin-bottom:10px;">{ico}</div>
    <div style="font-size:{'14px' if is_mobile else '17px'};font-weight:700;
        color:{T['text']};margin-bottom:8px;">{title}</div>
    <div style="font-size:{'11px' if is_mobile else '12px'};color:{T['muted']};
        font-style:italic;background:{T['card']};border:1px solid {T['border']};
        border-radius:8px;padding:6px 12px;display:inline-block;">{hint}</div>
</div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CHAT HISTORY
# ══════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ══════════════════════════════════════════════
# PROMPT BUILDER
# ══════════════════════════════════════════════
def build_prompt(user_input):
    mob = ("IMPORTANT: User is on mobile. "
           "Max 120 words. Use bullet points. No long intros.\n\n") if is_mobile else ""
    m = st.session_state.mode
    if m == "Document" and st.session_state.doc_context:
        return (f"{mob}Answer ONLY from the document. If not found say so.\n\n"
                f"=== DOCUMENT ===\n{st.session_state.doc_context}\n=== END ===\n\n"
                f"Question: {user_input}")
    elif m == "URL" and st.session_state.url_context:
        return (f"{mob}Answer ONLY from the webpage. Source: {st.session_state.url_loaded}\n"
                f"If not found say so.\n\n"
                f"=== PAGE ===\n{st.session_state.url_context}\n=== END ===\n\n"
                f"Question: {user_input}")
    return f"{mob}{user_input}"

# ══════════════════════════════════════════════
# CHAT INPUT
# ══════════════════════════════════════════════
ph = {
    "General":  "✦  Ask me anything...",
    "Document": "✦  Ask about the document..." if not doc_missing else "Upload a document first...",
    "URL":      "✦  Ask about the page..."     if not url_missing else "Load a URL first...",
}

if is_mobile:
    # Spacer so content doesn't hide behind fixed footer
    st.markdown('<div style="height:10vh;min-height:56px;"></div>', unsafe_allow_html=True)
    # Render chat input inside the fixed footer div
    st.markdown('<div class="mobile-footer">', unsafe_allow_html=True)

if prompt := st.chat_input(ph[current_mode], disabled=(doc_missing or url_missing)):
    st.session_state.last_active = time.time()
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("..." if is_mobile else "Thinking..."):
            try:
                reply = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=build_prompt(prompt)
                ).text
                st.markdown(reply)
                st.session_state.messages.append({"role":"assistant","content":reply})
            except Exception as e:
                err = f"⚠️ {e}"
                st.error(err)
                st.session_state.messages.append({"role":"assistant","content":err})

if is_mobile:
    st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════
# DESKTOP FOOTER STATUS BAR (desktop only)
# ══════════════════════════════════════════════
if not is_mobile:
    status = {
        "General":  "💬 General AI",
        "Document": f"📄 {st.session_state.doc_name}" if st.session_state.doc_name else "📄 No document",
        "URL":      f"🔗 {(st.session_state.url_loaded or '')[:45]}" if st.session_state.url_loaded else "🔗 No URL",
    }[current_mode]
    msg_count = len([m for m in st.session_state.messages if m["role"] == "user"])
    idle_elapsed = now - st.session_state.last_active
    idle_pct = min(100, int(idle_elapsed / IDLE_TIMEOUT * 100))

    st.markdown(f"""
<div style="
    position:fixed;bottom:0;left:50%;transform:translateX(-50%);
    width:min(800px,98vw);background:{T['card']};
    border-top:1px solid {T['border']};
    padding:5px 16px;
    display:flex;align-items:center;justify-content:space-between;
    z-index:9999;font-family:'Outfit',sans-serif;
    backdrop-filter:blur(16px);box-shadow:0 -4px 20px rgba(0,0,0,0.2);
">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;background:{T['border']};">
        <div style="height:2px;width:{idle_pct}%;
            background:linear-gradient(90deg,{T['accent']},{T['accent2']});
            {'background:linear-gradient(90deg,#ff8800,#ff4444)' if idle_pct > 80 else ''};
        "></div>
    </div>
    <div style="display:flex;align-items:center;gap:6px;">
        <div style="width:7px;height:7px;border-radius:50%;
            background:{active_color};box-shadow:0 0 6px {active_color}80;"></div>
        <span style="font-size:11px;color:{T['muted']};">{status}</span>
    </div>
    <div style="font-size:10px;color:{T['muted']};display:flex;align-items:center;gap:8px;">
        <span>🖥 Desktop</span>
        <span>·</span>
        <span>{msg_count} msg{"s" if msg_count!=1 else ""}</span>
        <span>·</span>
        <span style="color:{'#ff8800' if idle_pct>70 else T['muted']};">
            ⏱ {int((IDLE_TIMEOUT-idle_elapsed)/60)}m left
        </span>
    </div>
</div>
""", unsafe_allow_html=True)
