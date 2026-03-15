import streamlit as st
import os
import io
import time
import requests
from dotenv import load_dotenv
from google import genai

# ── doc parsers ──
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
# PAGE CONFIG — must be FIRST Streamlit call
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="SuperChat · SRIN AI",
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    st.error("⚠️ GEMINI_API_KEY not found in .env")
    st.stop()

client = genai.Client(api_key=api_key)
IDLE_TIMEOUT_SECONDS = 15 * 60   # 15 minutes

# ══════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════
defaults = {
    "theme":        "Dark",
    "messages":     [],
    "mode":         "General",
    "doc_context":  None,
    "doc_name":     None,
    "url_context":  None,
    "url_loaded":   None,
    "is_mobile":    False,
    "last_active":  time.time(),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Server-side idle check ──
now = time.time()
idle_secs = now - st.session_state.last_active
if idle_secs > IDLE_TIMEOUT_SECONDS:
    # Clear all session data
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()

# Update last active on every interaction
st.session_state.last_active = now

# ── Query params ──
qp = st.query_params
if "mobile" in qp:
    st.session_state.is_mobile = (qp["mobile"] == "1")
if "mode" in qp and qp["mode"] in ["General", "Document", "URL"]:
    st.session_state.mode = qp["mode"]

is_mobile  = st.session_state.is_mobile
max_width  = "520px" if is_mobile else "800px"

# ══════════════════════════════════════════════
# THEME COLOURS
# ══════════════════════════════════════════════
DARK = {
    "bg":            "#050c1a",
    "bg_grad":       "linear-gradient(160deg,#040a14 0%,#071020 25%,#091528 55%,#0c1c38 80%,#0e2040 100%)",
    "surface":       "#0c1a30",
    "card":          "#0f2040",
    "card2":         "#152848",
    "border":        "#1a3060",
    "border2":       "#234080",
    "text":          "#e8f2ff",
    "text2":         "#c8d8f0",
    "muted":         "#6888b0",
    "accent":        "#3b9eff",
    "accent2":       "#00d4ff",
    "accent3":       "#00c9a7",
    "user_bubble_bg":"linear-gradient(135deg,#1a3a70 0%,#1e4888 100%)",
    "user_border":   "#2a5aaa",
    "ai_bubble_bg":  "linear-gradient(135deg,#0a1e3a 0%,#0e2448 100%)",
    "ai_border":     "#1a3060",
    "input_bg":      "linear-gradient(135deg,#0c1a30,#0f2040)",
    "input_border":  "#234080",
    "chat_bg":       "linear-gradient(180deg,#050c1a 0%,#081528 50%,#0a1a35 100%)",
}
LIGHT = {
    "bg":            "#f0f6ff",
    "bg_grad":       "linear-gradient(160deg,#f0f6ff 0%,#e8f0fc 40%,#dce8f8 100%)",
    "surface":       "#ffffff",
    "card":          "#ffffff",
    "card2":         "#e8f0ff",
    "border":        "#c0d0e8",
    "border2":       "#a0bcdc",
    "text":          "#0a1628",
    "text2":         "#1a3050",
    "muted":         "#4a6080",
    "accent":        "#1a56db",
    "accent2":       "#0891b2",
    "accent3":       "#059669",
    "user_bubble_bg":"linear-gradient(135deg,#dbeafe 0%,#bfdbfe 100%)",
    "user_border":   "#93c5fd",
    "ai_bubble_bg":  "linear-gradient(135deg,#ffffff 0%,#f0f6ff 100%)",
    "ai_border":     "#c0d0e8",
    "input_bg":      "linear-gradient(135deg,#ffffff,#f0f6ff)",
    "input_border":  "#a0bcdc",
    "chat_bg":       "linear-gradient(180deg,#f0f6ff 0%,#e8f0fc 50%,#dce8f8 100%)",
}

T = DARK if st.session_state.theme == "Dark" else LIGHT

# ══════════════════════════════════════════════
# GLOBAL CSS
# ══════════════════════════════════════════════
fs_sm  = "12px" if is_mobile else "13px"
fs_md  = "13px" if is_mobile else "15px"
fs_lg  = "16px" if is_mobile else "20px"
pad_sm = "6px 10px" if is_mobile else "10px 16px"
br_md  = "10px" if is_mobile else "14px"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

*, *::before, *::after {{ box-sizing: border-box; }}

/* ── APP BACKGROUND — rich deep navy gradient ── */
.stApp {{
    background: {T["bg_grad"]} !important;
    font-family: 'Outfit', sans-serif !important;
    min-height: 100vh;
}}

/* Subtle dot grid overlay for depth */
.stApp::before {{
    content: '';
    position: fixed;
    inset: 0;
    background-image: {"radial-gradient(circle,rgba(59,158,255,0.05) 1px,transparent 1px)" if st.session_state.theme == "Dark" else "radial-gradient(circle,rgba(26,86,219,0.04) 1px,transparent 1px)"};
    background-size: 30px 30px;
    pointer-events: none;
    z-index: 0;
}}

/* Radial glow spots for atmosphere */
.stApp::after {{
    content: '';
    position: fixed;
    inset: 0;
    background:
        {"radial-gradient(ellipse 60% 40% at 70% 20%,rgba(37,99,255,0.07) 0%,transparent 60%), radial-gradient(ellipse 40% 40% at 20% 80%,rgba(0,212,255,0.05) 0%,transparent 55%)" if st.session_state.theme == "Dark" else "radial-gradient(ellipse 60% 40% at 70% 20%,rgba(37,99,255,0.04) 0%,transparent 60%)"};
    pointer-events: none;
    z-index: 0;
}}

.block-container {{
    max-width: {max_width} !important;
    margin: 0 auto !important;
    padding: {"0.5rem 0.75rem 5.5rem" if is_mobile else "1rem 1.5rem 5.5rem"} !important;
    background: transparent !important;
}}

#MainMenu, footer, header,
[data-testid="stToolbar"],
.stDeployButton {{ display: none !important; }}

::-webkit-scrollbar {{ width: 4px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: {T["border2"]}; border-radius: 4px; }}

/* ── CHAT AREA BACKGROUND ── */
[data-testid="stVerticalBlock"] {{
    background: transparent !important;
}}

/* ── USER MESSAGES — gradient blue bubble ── */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {{
    background: {T["user_bubble_bg"]} !important;
    border: 1px solid {T["user_border"]} !important;
    border-radius: {br_md} !important;
    padding: {pad_sm} !important;
    margin-left: {"5%" if is_mobile else "10%"} !important;
    margin-bottom: {"5px" if is_mobile else "8px"} !important;
    box-shadow: 0 2px 12px {T["accent"]}20, inset 0 1px 0 rgba(255,255,255,0.08) !important;
    backdrop-filter: blur(8px);
}}

/* ── AI MESSAGES — deep dark bubble ── */
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {{
    background: {T["ai_bubble_bg"]} !important;
    border: 1px solid {T["ai_border"]} !important;
    border-radius: {br_md} !important;
    padding: {pad_sm} !important;
    margin-right: {"5%" if is_mobile else "10%"} !important;
    margin-bottom: {"5px" if is_mobile else "8px"} !important;
    box-shadow: 0 2px 16px rgba(0,0,0,0.25), inset 0 1px 0 rgba(59,158,255,0.06) !important;
    backdrop-filter: blur(8px);
}}

[data-testid="stChatMessage"] p {{
    color: {T["text"]} !important;
    font-size: {fs_md} !important;
    line-height: {"1.55" if is_mobile else "1.72"} !important;
    margin: 0 !important;
    font-family: 'Outfit', sans-serif !important;
}}

[data-testid="stChatMessage"] li {{
    color: {T["text2"]} !important;
    font-size: {fs_md} !important;
    font-family: 'Outfit', sans-serif !important;
}}

[data-testid="stChatMessage"] code {{
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 11px !important;
    background: rgba(59,158,255,0.12) !important;
    border: 1px solid {T["border"]} !important;
    padding: 1px 6px !important;
    border-radius: 4px !important;
    color: {T["accent2"]} !important;
}}

[data-testid="stChatMessage"] pre {{
    background: {T["card"]} !important;
    border: 1px solid {T["border2"]} !important;
    border-radius: 8px !important;
    padding: 10px !important;
    overflow-x: auto !important;
}}

/* ── CHAT INPUT — stylish floating bar ── */
[data-testid="stBottom"] {{
    background: transparent !important;
    padding: 0 !important;
}}

/* Outer wrapper */
[data-testid="stChatInput"] {{
    background: {"#0c1a32" if st.session_state.theme == "Dark" else "#ffffff"} !important;
    border: 1.5px solid {T["input_border"]} !important;
    border-radius: {"14px" if is_mobile else "18px"} !important;
    box-shadow: 0 4px 28px rgba(0,0,0,0.4),
                0 0 0 1px rgba(59,158,255,0.15),
                inset 0 1px 0 rgba(255,255,255,0.05) !important;
    backdrop-filter: blur(20px) !important;
    padding: {"4px 6px" if is_mobile else "6px 8px"} !important;
    transition: all 0.3s ease !important;
}}

[data-testid="stChatInput"]:focus-within {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 4px 32px rgba(59,158,255,0.25),
                0 0 0 2px {T["accent"]}40 !important;
}}

/* THE KEY FIX: textarea must have explicit dark bg and light text */
[data-testid="stChatInput"] textarea {{
    background: {"#0c1a32" if st.session_state.theme == "Dark" else "#ffffff"} !important;
    color: {"#e8f2ff" if st.session_state.theme == "Dark" else "#0a1628"} !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: {fs_md} !important;
    font-weight: 400 !important;
    caret-color: {T["accent"]} !important;
    border: none !important;
    outline: none !important;
    resize: none !important;
    padding: {"8px 10px" if is_mobile else "10px 14px"} !important;
    line-height: 1.5 !important;
    -webkit-text-fill-color: {"#e8f2ff" if st.session_state.theme == "Dark" else "#0a1628"} !important;
}}

[data-testid="stChatInput"] textarea::placeholder {{
    color: {T["muted"]} !important;
    -webkit-text-fill-color: {T["muted"]} !important;
    font-size: {fs_sm} !important;
    font-style: italic !important;
    font-family: 'Outfit', sans-serif !important;
    opacity: 1 !important;
}}

/* Send button */
[data-testid="stChatInput"] button {{
    background: linear-gradient(135deg,{T["accent"]},{T["accent2"]}) !important;
    border: none !important;
    border-radius: {"9px" if is_mobile else "12px"} !important;
    width: {"32px" if is_mobile else "38px"} !important;
    height: {"32px" if is_mobile else "38px"} !important;
    transition: all 0.2s !important;
    box-shadow: 0 2px 10px {T["accent"]}50 !important;
    flex-shrink: 0 !important;
}}

[data-testid="stChatInput"] button:hover {{
    transform: scale(1.08) !important;
    box-shadow: 0 4px 16px {T["accent"]}70 !important;
}}

[data-testid="stChatInput"] button svg {{
    fill: #ffffff !important;
    stroke: #ffffff !important;
}}

/* ── BUTTONS ── */
.stButton > button {{
    background: {T["card"]} !important;
    color: {T["muted"]} !important;
    border: 1px solid {T["border"]} !important;
    border-radius: 999px !important;
    font-family: 'Outfit', sans-serif !important;
    font-size: {fs_sm} !important;
    font-weight: 600 !important;
    padding: {"4px 10px" if is_mobile else "5px 14px"} !important;
    transition: all 0.2s !important;
    letter-spacing: 0.3px !important;
    backdrop-filter: blur(8px) !important;
}}

.stButton > button:hover {{
    background: {T["card2"]} !important;
    border-color: {T["accent"]} !important;
    color: {T["accent"]} !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px {T["accent"]}30 !important;
}}

/* ── FILE UPLOADER ── */
[data-testid="stFileUploader"] {{
    background: {T["card"]} !important;
    border: 1.5px dashed {T["border2"]} !important;
    border-radius: 12px !important;
    backdrop-filter: blur(8px) !important;
}}

/* ── TEXT INPUT ── */
.stTextInput input {{
    background: {T["input_bg"]} !important;
    color: {T["text"]} !important;
    border: 1.5px solid {T["border2"]} !important;
    border-radius: 10px !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: {fs_sm} !important;
    backdrop-filter: blur(8px) !important;
}}

.stTextInput input:focus {{
    border-color: {T["accent"]} !important;
    box-shadow: 0 0 0 2px {T["accent"]}25 !important;
}}

.stTextInput label {{ color: {T["muted"]} !important; font-size: 11px !important; }}

/* ── TOGGLE ── */
[data-testid="stToggle"] label {{ color: {T["muted"]} !important; font-size: 11px !important; }}

/* ── ALERTS ── */
.stAlert {{ border-radius: 10px !important; font-size: {fs_sm} !important;
    font-family: 'Outfit', sans-serif !important; backdrop-filter: blur(8px) !important; }}

/* ── SPINNER ── */
[data-testid="stSpinner"] svg {{ stroke: {T["accent"]} !important; }}

/* hide 0-height iframe completely */
iframe[height="0"] {{
    position: absolute !important; width: 0 !important;
    height: 0 !important; border: none !important; display: block !important;
    overflow: hidden !important; pointer-events: none !important;
}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# MOBILE DETECTION JS — hidden at 0 height
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

# ══════════════════════════════════════════════
# IDLE TIMEOUT JS — clears session after 15 min
# Counts down in browser, reloads with ?clear=1
# ══════════════════════════════════════════════
if qp.get("clear") == "1":
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.query_params.clear()
    st.rerun()

st.components.v1.html(f"""
<script>
(function(){{
  var IDLE_MS = {IDLE_TIMEOUT_SECONDS * 1000};
  var timer;
  function reset(){{
    clearTimeout(timer);
    timer = setTimeout(function(){{
      try {{
        var url = new URL(window.parent.location.href);
        url.searchParams.set('clear','1');
        url.searchParams.set('mobile','{1 if is_mobile else 0}');
        window.parent.location.replace(url.toString());
      }} catch(e){{}}
    }}, IDLE_MS);
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
st.markdown(f"""
<div style="
    background:linear-gradient(135deg,{T['card']} 0%,{T['card2']} 100%);
    border:1px solid {T['border2']};
    border-radius:{"12px" if is_mobile else "16px"};
    padding:{"10px 14px" if is_mobile else "14px 22px"};
    margin-bottom:{"8px" if is_mobile else "12px"};
    position:relative;overflow:hidden;
    box-shadow:0 4px 28px rgba(59,158,255,0.12),
               inset 0 1px 0 rgba(255,255,255,0.06);
">
    <div style="position:absolute;top:0;left:0;right:0;height:2px;
        background:linear-gradient(90deg,transparent 0%,{T['accent']} 30%,{T['accent2']} 70%,transparent 100%);">
    </div>
    <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
        <div style="display:flex;align-items:center;gap:12px;">
            <div style="
                width:{"38px" if is_mobile else "46px"};
                height:{"38px" if is_mobile else "46px"};
                border-radius:{"11px" if is_mobile else "13px"};
                background:linear-gradient(135deg,{T['accent']},{T['accent2']});
                display:flex;align-items:center;justify-content:center;
                font-size:{"19px" if is_mobile else "23px"};
                box-shadow:0 0 18px {T['accent']}50;
                flex-shrink:0;
            ">💬</div>
            <div>
                <div style="font-family:'Outfit',sans-serif;
                    font-size:{"17px" if is_mobile else "21px"};
                    font-weight:800;color:{T['text']};
                    letter-spacing:-0.5px;line-height:1.1;">
                    SuperChat&nbsp;<span style="color:{T['accent']};">AI</span>
                </div>
                <div style="font-size:{"9px" if is_mobile else "10px"};
                    color:{T['muted']};letter-spacing:1.5px;
                    text-transform:uppercase;font-weight:600;">
                    {"📱 Mobile" if is_mobile else "🖥 SRIN AI Solutions"}
                </div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
            <div style="
                background:{T['accent']}18;
                border:1px solid {T['accent']}45;
                border-radius:999px;padding:3px 11px;
                font-size:{"8px" if is_mobile else "9px"};
                color:{T['accent']};font-weight:700;
                letter-spacing:1px;text-transform:uppercase;
            ">gemini-2.5-flash</div>
            <div style="
                background:{'#00c9a720' if True else '#ff444420'};
                border:1px solid {'#00c9a750' if True else '#ff444450'};
                border-radius:999px;padding:3px 9px;
                font-size:{"8px" if is_mobile else "9px"};
                color:{'#00c9a7' if True else '#ff4444'};font-weight:700;
            ">● LIVE</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# TOP ROW — mode pills + theme toggle
# ══════════════════════════════════════════════
col_modes, col_toggle = st.columns([5, 1])

with col_toggle:
    tog = st.toggle(
        "🌙", value=(st.session_state.theme == "Dark"),
        key="theme_tog", label_visibility="collapsed"
    )
    new_theme = "Dark" if tog else "Light"
    if new_theme != st.session_state.theme:
        st.session_state.theme = new_theme
        st.rerun()

with col_modes:
    mc = st.columns(3)
    mode_icons = {"General":"💬","Document":"📄","URL":"🔗"}
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
                        st.session_state.doc_name    = None
                    elif m == "URL":
                        st.session_state.url_context = None
                        st.session_state.url_loaded  = None
                    st.rerun()

# Active mode colour strip
mode_colors = {
    "General": T["accent"],
    "Document": T["accent3"],
    "URL": T["accent2"]
}
active_color = mode_colors[st.session_state.mode]

st.markdown(f"""
<div style="height:2px;border-radius:1px;
    margin-bottom:{"8px" if is_mobile else "12px"};
    background:linear-gradient(90deg,transparent,{active_color}99,{active_color},transparent);
"></div>
""", unsafe_allow_html=True)

current_mode = st.session_state.mode

# ══════════════════════════════════════════════
# IDLE WARNING — show at 12 min mark
# ══════════════════════════════════════════════
idle_elapsed = now - st.session_state.last_active
if idle_elapsed > 12 * 60:
    remaining = int((IDLE_TIMEOUT_SECONDS - idle_elapsed) / 60)
    st.warning(f"⏱ Session expires in ~{remaining} minute(s) due to inactivity.")

# ══════════════════════════════════════════════
# DOCUMENT MODE PANEL
# ══════════════════════════════════════════════
if current_mode == "Document":
    st.markdown(f"""
    <div style="
        background:{T['card']};
        border:1px solid {T['border2']};
        border-left:3px solid {T['accent3']};
        border-radius:{"10px" if is_mobile else "12px"};
        padding:{"8px 12px" if is_mobile else "10px 16px"};
        margin-bottom:{"8px" if is_mobile else "10px"};
        backdrop-filter:blur(8px);
    ">
        <div style="font-size:{"11px" if is_mobile else "12px"};
            color:{T['accent3']};font-weight:700;
            letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">
            📄 Upload Document
        </div>
        <div style="font-size:{"10px" if is_mobile else "11px"};color:{T['muted']};">
            PDF &nbsp;·&nbsp; DOCX &nbsp;·&nbsp; TXT &nbsp;·&nbsp;
            <span style="color:{T['accent']};">Session-only — cleared on tab close or idle.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "upload", type=["pdf","docx","txt"],
        key="doc_upload", label_visibility="collapsed"
    )

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
                max_chars = 6000 if is_mobile else 12000
                st.session_state.doc_context = text[:max_chars]
                st.session_state.doc_name    = uploaded.name
                st.session_state.messages    = []
                st.success(f"✅ Loaded **{uploaded.name}** ({len(text):,} chars) — ask anything.")
            else:
                st.error("Could not extract text.")
        except Exception as e:
            st.error(f"Error: {e}")

    elif uploaded and uploaded.name == st.session_state.doc_name:
        st.info(f"📄 Active: **{st.session_state.doc_name}**")

# ══════════════════════════════════════════════
# URL MODE PANEL
# ══════════════════════════════════════════════
elif current_mode == "URL":
    st.markdown(f"""
    <div style="
        background:{T['card']};border:1px solid {T['border2']};
        border-left:3px solid {T['accent2']};
        border-radius:{"10px" if is_mobile else "12px"};
        padding:{"8px 12px" if is_mobile else "10px 16px"};
        margin-bottom:{"8px" if is_mobile else "10px"};
        backdrop-filter:blur(8px);
    ">
        <div style="font-size:{"11px" if is_mobile else "12px"};
            color:{T['accent2']};font-weight:700;
            letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">
            🔗 Load a URL
        </div>
        <div style="font-size:{"10px" if is_mobile else "11px"};color:{T['muted']};">
            Paste any public page — docs, blogs, product pages, knowledge bases.&nbsp;
            <span style="color:{T['accent']};">Stored in session only — never persisted.</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    url_val = st.text_input(
        "url", placeholder="https://docs.aws.amazon.com/bedrock/...",
        key="url_box", label_visibility="collapsed"
    )

    c1, c2 = st.columns([4, 1])
    with c1:
        load_btn = st.button("⚡ Load Page", key="load_url", use_container_width=True)
    with c2:
        if st.button("✕ Clear", key="clr_url", use_container_width=True):
            st.session_state.url_context = None
            st.session_state.url_loaded  = None
            st.session_state.messages    = []
            st.rerun()

    if load_btn and url_val:
        with st.spinner("Fetching..."):
            try:
                r = requests.get(
                    url_val,
                    headers={"User-Agent":"Mozilla/5.0 SuperChatBot/1.0"},
                    timeout=12
                )
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
                max_chars = 6000 if is_mobile else 12000
                st.session_state.url_context = clean[:max_chars]
                st.session_state.url_loaded  = url_val
                st.session_state.messages    = []
                st.success(f"✅ Loaded ({len(clean):,} chars) — ask anything.")
            except requests.exceptions.Timeout:
                st.error("⏱ Timed out.")
            except requests.exceptions.ConnectionError:
                st.error("❌ Cannot connect. Is the URL public?")
            except Exception as e:
                st.error(f"Error: {e}")

    if st.session_state.url_loaded:
        st.info(f"🔗 Active: `{st.session_state.url_loaded[:70]}`")

# ══════════════════════════════════════════════
# EMPTY STATE
# ══════════════════════════════════════════════
doc_missing = current_mode == "Document" and not st.session_state.doc_context
url_missing = current_mode == "URL"      and not st.session_state.url_context

if not st.session_state.messages and not doc_missing and not url_missing:
    hints = {
        "General":  ("💬","Ask me anything","Try: What is LangChain and how does it work?"),
        "Document": ("📄","Ready to answer","Ask: Summarise the key points of this document"),
        "URL":      ("🔗","Page loaded","Ask: What are the main features on this page?"),
    }
    ico, title, hint = hints[current_mode]
    st.markdown(f"""
    <div style="text-align:center;
        padding:{"24px 12px" if is_mobile else "44px 20px"};
        color:{T['muted']};">
        <div style="font-size:{"34px" if is_mobile else "44px"};margin-bottom:12px;">{ico}</div>
        <div style="font-size:{"14px" if is_mobile else "17px"};
            font-weight:700;color:{T['text']};margin-bottom:8px;">{title}</div>
        <div style="font-size:{"11px" if is_mobile else "12px"};
            color:{T['muted']};font-style:italic;
            background:{T['card']};border:1px solid {T['border']};
            border-radius:8px;padding:8px 14px;display:inline-block;">
            {hint}
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════════════════
# CHAT HISTORY
# ══════════════════════════════════════════════
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ══════════════════════════════════════════════
# PROMPT BUILDER
# ══════════════════════════════════════════════
def build_prompt(user_input: str) -> str:
    mobile_note = (
        "IMPORTANT: User is on mobile. "
        "Reply in max 120 words. Use bullet points. No long intros.\n\n"
    ) if is_mobile else ""

    m = st.session_state.mode

    if m == "Document" and st.session_state.doc_context:
        return (
            f"{mobile_note}"
            f"Answer ONLY from the document. "
            f"If not found, say so clearly.\n\n"
            f"=== DOCUMENT ===\n{st.session_state.doc_context}\n=== END ===\n\n"
            f"Question: {user_input}"
        )
    elif m == "URL" and st.session_state.url_context:
        return (
            f"{mobile_note}"
            f"Answer ONLY from the webpage. "
            f"Source: {st.session_state.url_loaded}\n"
            f"If not found, say so clearly.\n\n"
            f"=== PAGE ===\n{st.session_state.url_context}\n=== END ===\n\n"
            f"Question: {user_input}"
        )
    return f"{mobile_note}{user_input}"

# ══════════════════════════════════════════════
# CHAT INPUT
# ══════════════════════════════════════════════
ph = {
    "General":  "✦  Ask me anything...",
    "Document": "✦  Ask about the document..." if not doc_missing else "Upload a document above first...",
    "URL":      "✦  Ask about the page..."     if not url_missing else "Load a URL above first...",
}

if prompt := st.chat_input(ph[current_mode], disabled=(doc_missing or url_missing)):
    st.session_state.last_active = time.time()
    st.session_state.messages.append({"role":"user","content":prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..." if is_mobile else "SuperChat AI is thinking..."):
            try:
                reply = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=build_prompt(prompt)
                ).text
                st.markdown(reply)
                st.session_state.messages.append({"role":"assistant","content":reply})
            except Exception as e:
                err = f"⚠️ Error: {e}"
                st.error(err)
                st.session_state.messages.append({"role":"assistant","content":err})

# ══════════════════════════════════════════════
# FOOTER STATUS BAR
# ══════════════════════════════════════════════
status = {
    "General":  "💬 General AI · No context",
    "Document": f"📄 {st.session_state.doc_name}" if st.session_state.doc_name else "📄 No document",
    "URL":      f"🔗 {(st.session_state.url_loaded or '')[:45]}" if st.session_state.url_loaded else "🔗 No URL",
}[current_mode]

msg_count  = len([m for m in st.session_state.messages if m["role"] == "user"])
device_tag = "📱 Mobile · Crisp" if is_mobile else "🖥 Desktop"
idle_pct   = min(100, int(idle_elapsed / IDLE_TIMEOUT_SECONDS * 100))

st.markdown(f"""
<div style="
    position:fixed;bottom:0;left:50%;transform:translateX(-50%);
    width:min({max_width},98vw);
    background:{T['surface']};
    border-top:1px solid {T['border']};
    padding:{"4px 10px" if is_mobile else "5px 16px"};
    display:flex;align-items:center;justify-content:space-between;
    z-index:9999;font-family:'Outfit',sans-serif;
    backdrop-filter:blur(16px);
    box-shadow:0 -4px 20px rgba(0,0,0,0.2);
">
    <!-- Idle progress bar -->
    <div style="position:absolute;top:0;left:0;right:0;height:2px;
        background:{T['border']};border-radius:1px;">
        <div style="height:2px;width:{idle_pct}%;
            background:linear-gradient(90deg,{T['accent']},{T['accent2']});
            border-radius:1px;transition:width 1s linear;
            {'background:linear-gradient(90deg,#ff8800,#ff4444)' if idle_pct > 80 else ''};
        "></div>
    </div>
    <div style="display:flex;align-items:center;gap:6px;">
        <div style="width:7px;height:7px;border-radius:50%;
            background:{active_color};box-shadow:0 0 6px {active_color}80;">
        </div>
        <span style="font-size:{"10px" if is_mobile else "11px"};color:{T['muted']};">
            {status}
        </span>
    </div>
    <div style="display:flex;align-items:center;gap:8px;
        font-size:{"9px" if is_mobile else "10px"};color:{T['muted']};">
        <span>{device_tag}</span>
        <span style="color:{T['border2']};">·</span>
        <span>{msg_count} msg{"s" if msg_count != 1 else ""}</span>
        <span style="color:{T['border2']};">·</span>
        <span style="color:{'#ff8800' if idle_pct > 70 else T['muted']};">
            ⏱ {int((IDLE_TIMEOUT_SECONDS - idle_elapsed)/60)}m left
        </span>
    </div>
</div>
""", unsafe_allow_html=True)
