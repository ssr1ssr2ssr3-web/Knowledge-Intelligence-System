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

# ── SESSION STATE ──
defaults = {
    "theme": "Dark", "messages": [], "mode": "General",
    "doc_context": None, "doc_name": None,
    "url_context": None, "url_loaded": None,
    "device": "desktop", "last_active": time.time(),
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

now = time.time()
if now - st.session_state.last_active > IDLE_TIMEOUT:
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.rerun()
st.session_state.last_active = now

qp = st.query_params
if "device" in qp and qp["device"] in ["mobile","tablet","desktop"]:
    st.session_state.device = qp["device"]
if "mode" in qp and qp["mode"] in ["General","Document","URL"]:
    st.session_state.mode = qp["mode"]
if "theme" in qp:
    st.session_state.theme = "Light" if qp["theme"] == "light" else "Dark"
if qp.get("clear") == "1":
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.query_params.clear()
    st.rerun()

device       = st.session_state.device
is_mobile    = device == "mobile"
is_tablet    = device == "tablet"
is_desktop   = device == "desktop"
current_mode = st.session_state.mode

# ── COLOURS ──
DARK = {
    "chat_bg":    "#0a1628",
    "card":       "#0f2040",
    "card2":      "#152848",
    "border":     "#1a3060",
    "border2":    "#234080",
    "text":       "#e8f2ff",
    "text2":      "#b8d0f0",
    "muted":      "#6888b0",
    "accent":     "#3b9eff",
    "accent2":    "#00d4ff",
    "accent3":    "#00c9a7",
    "user_bg":    "linear-gradient(135deg,#1a3a70,#1e4888)",
    "user_border":"#2a5aaa",
    "ai_bg":      "linear-gradient(135deg,#0a1e3a,#0e2448)",
    "ai_border":  "#1a3060",
    "footer_bg":  "#1565c0",
    "side_bg":    "linear-gradient(160deg,#040a14 0%,#071020 25%,#091528 55%,#0c1c38 80%,#0e2040 100%)",
}
LIGHT = {
    "chat_bg":    "#dce8f8",
    "card":       "#ffffff",
    "card2":      "#e8f0ff",
    "border":     "#c0d0e8",
    "border2":    "#a0bcdc",
    "text":       "#0a1628",
    "text2":      "#1a3050",
    "muted":      "#4a6080",
    "accent":     "#1a56db",
    "accent2":    "#0891b2",
    "accent3":    "#059669",
    "user_bg":    "linear-gradient(135deg,#dbeafe,#bfdbfe)",
    "user_border":"#93c5fd",
    "ai_bg":      "linear-gradient(135deg,#ffffff,#f0f6ff)",
    "ai_border":  "#c0d0e8",
    "footer_bg":  "#1976d2",
    "side_bg":    "linear-gradient(160deg,#c8d8f0 0%,#b8ccec 40%,#a8c0e8 100%)",
}
T = DARK if st.session_state.theme == "Dark" else LIGHT

# ══════════════════════════════════════════════
# CSS — three device layouts
# ══════════════════════════════════════════════
def shared_message_css():
    return f"""
[data-testid="stChatMessage"]{{border-radius:14px !important;padding:10px 14px !important;margin-bottom:8px !important;}}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]){{
    background:{T["user_bg"]} !important;border:1px solid {T["user_border"]} !important;margin-left:8% !important;}}
[data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]){{
    background:{T["ai_bg"]} !important;border:1px solid {T["ai_border"]} !important;margin-right:8% !important;}}
[data-testid="stChatMessage"] p{{color:{T["text"]} !important;font-size:{"13px" if is_mobile else "14px"} !important;
    line-height:1.65 !important;margin:0 !important;font-family:'Outfit',sans-serif !important;}}
[data-testid="stChatMessage"] li{{color:{T["text2"]} !important;font-size:13px !important;}}
[data-testid="stChatMessage"] code{{font-family:'JetBrains Mono',monospace !important;font-size:11px !important;
    background:rgba(59,158,255,0.15) !important;color:{T["accent2"]} !important;
    padding:1px 5px !important;border-radius:4px !important;}}
"""

def bottom_input_css():
    """Clean white input bar — no border, no shadow, no rounded div wrapper."""
    return f"""
/* ── Force ALL stBottom children to be blue ── */
[data-testid="stBottom"]{{
    position:fixed !important;bottom:0 !important;left:0 !important;right:0 !important;
    height:68px !important;
    background:{T["footer_bg"]} !important;
    z-index:999999 !important;
    padding:9px 10px !important;
    box-shadow:none !important;border:none !important;border-top:none !important;
    display:flex !important;align-items:center !important;
}}
[data-testid="stBottom"] *:not(textarea):not(button):not(svg):not(path){{
    background:{T["footer_bg"]} !important;
    border:none !important;box-shadow:none !important;
    padding:0 !important;margin:0 !important;
}}
[data-testid="stBottom"]>div{{
    width:100% !important;display:flex !important;align-items:center !important;
}}

/* INPUT WRAPPER — transparent so blue shows through */
[data-testid="stChatInput"]{{
    background:transparent !important;
    border:none !important;box-shadow:none !important;outline:none !important;
    padding:0 !important;width:100% !important;
    display:flex !important;align-items:center !important;
}}

/* WHITE TEXTAREA — subtle rounded corners, no border */
[data-testid="stChatInput"] textarea{{
    background:#ffffff !important;
    color:#0a1628 !important;
    -webkit-text-fill-color:#0a1628 !important;
    border:none !important;
    border-radius:12px !important;
    font-family:'Outfit',sans-serif !important;
    font-size:15px !important;
    font-weight:400 !important;
    padding:12px 16px !important;
    line-height:1.3 !important;
    caret-color:#1565c0 !important;
    outline:none !important;
    resize:none !important;
    box-shadow:none !important;
    width:100% !important;
    min-height:50px !important;
    max-height:50px !important;
    flex:1 !important;
}}
[data-testid="stChatInput"] textarea::placeholder{{
    color:#8fa8c8 !important;
    -webkit-text-fill-color:#8fa8c8 !important;
    font-style:italic !important;opacity:1 !important;
}}
[data-testid="stChatInput"] textarea:focus{{
    outline:none !important;box-shadow:none !important;border:none !important;
}}

/* SEND BUTTON — gradient glowing circle */
[data-testid="stChatInput"] button{{
    background:linear-gradient(135deg,#3b9eff,#00d4ff) !important;
    border:none !important;border-radius:50% !important;
    width:46px !important;height:46px !important;min-width:46px !important;
    box-shadow:0 0 16px rgba(59,158,255,0.8) !important;
    flex-shrink:0 !important;cursor:pointer !important;transition:all 0.2s !important;
    margin-left:8px !important;
}}
[data-testid="stChatInput"] button:hover{{
    transform:scale(1.08) !important;box-shadow:0 0 24px rgba(59,158,255,1) !important;
}}
[data-testid="stChatInput"] button svg{{
    fill:#ffffff !important;stroke:#ffffff !important;width:20px !important;height:20px !important;
}}
"""

# ─────────────────────────────
# MOBILE CSS
# ─────────────────────────────
if is_mobile:
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}

#MainMenu,footer,header,[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],
[data-testid="stSidebarNav"],.stDeployButton{{display:none !important;}}

html,body{{height:100vh;overflow:hidden;}}

/* Full screen — no side margins */
.stApp{{
    background:{T["chat_bg"]} !important;
    font-family:'Outfit',sans-serif !important;
    height:100vh !important;overflow:hidden !important;
    width:100vw !important;
}}
.main,section.main{{padding:0 !important;overflow:hidden !important;height:100vh !important;width:100vw !important;}}

/* Scrollable chat — full phone width */
.block-container{{
    padding:0 10px !important;
    padding-top:76px !important;
    padding-bottom:80px !important;
    margin:0 !important;
    max-width:100vw !important;
    width:100vw !important;
    height:100vh !important;
    overflow-y:auto !important;overflow-x:hidden !important;
    -webkit-overflow-scrolling:touch !important;
}}

{shared_message_css()}
{bottom_input_css()}

/* Widgets */
.stButton>button{{background:rgba(255,255,255,0.08) !important;color:{T["muted"]} !important;
    border:1px solid {T["border"]} !important;border-radius:999px !important;
    font-family:'Outfit',sans-serif !important;font-size:11px !important;font-weight:600 !important;padding:3px 10px !important;}}
.stButton>button:hover{{border-color:{T["accent"]} !important;color:{T["accent"]} !important;}}
[data-testid="stFileUploader"]{{background:{T["card"]} !important;
    border:1.5px dashed {T["border2"]} !important;border-radius:10px !important;}}
.stTextInput input{{background:{T["card"]} !important;color:{T["text"]} !important;
    -webkit-text-fill-color:{T["text"]} !important;
    border:1.5px solid {T["border2"]} !important;border-radius:8px !important;font-size:13px !important;}}
.stAlert{{border-radius:10px !important;font-family:'Outfit',sans-serif !important;font-size:13px !important;}}
::-webkit-scrollbar{{width:3px;}}
::-webkit-scrollbar-thumb{{background:{T["border2"]};border-radius:2px;}}
iframe[height="0"]{{position:absolute !important;width:0 !important;height:0 !important;
    border:none !important;pointer-events:none !important;}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────
# TABLET CSS
# ─────────────────────────────
elif is_tablet:
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0;}}

#MainMenu,footer,header,[data-testid="stToolbar"],
[data-testid="stDecoration"],[data-testid="stStatusWidget"],
[data-testid="stSidebarNav"],.stDeployButton{{display:none !important;}}

html,body{{height:100vh;overflow:hidden;}}

/* Full screen background — landing page gradient on sides */
.stApp{{
    background:{T["side_bg"]} !important;
    font-family:'Outfit',sans-serif !important;
    height:100vh !important;overflow:hidden !important;
}}
/* Dot grid overlay — same as landing page */
.stApp::before{{
    content:'';position:fixed;inset:0;
    background-image:radial-gradient(circle,rgba(59,158,255,0.05) 1px,transparent 1px);
    background-size:30px 30px;pointer-events:none;z-index:0;
}}

.main,section.main{{
    padding:0 !important;overflow:hidden !important;height:100vh !important;
    /* Side panels show the side_bg through the gap */
    background:transparent !important;
}}

/* Centred chat panel with its own background */
.block-container{{
    max-width:640px !important;
    margin:0 auto !important;
    padding:0 16px !important;
    padding-top:80px !important;
    padding-bottom:84px !important;
    height:100vh !important;
    overflow-y:auto !important;overflow-x:hidden !important;
    -webkit-overflow-scrolling:touch !important;
    background:{T["chat_bg"]} !important;
    /* Side shadow so panel looks elevated */
    box-shadow:0 0 60px rgba(0,0,0,0.5) !important;
    position:relative !important;
}}

{shared_message_css()}
{bottom_input_css()}

/* On tablet, stBottom should only span the content width */
[data-testid="stBottom"]{{
    left:50% !important;
    transform:translateX(-50%) !important;
    width:640px !important;
    max-width:100vw !important;
}}

/* Tablet widgets */
.stButton>button{{background:{T["card"]} !important;color:{T["muted"]} !important;
    border:1px solid {T["border"]} !important;border-radius:999px !important;
    font-family:'Outfit',sans-serif !important;font-size:12px !important;font-weight:600 !important;padding:4px 12px !important;}}
.stButton>button:hover{{background:{T["card2"]} !important;border-color:{T["accent"]} !important;color:{T["accent"]} !important;}}
[data-testid="stFileUploader"]{{background:{T["card"]} !important;
    border:1.5px dashed {T["border2"]} !important;border-radius:12px !important;}}
.stTextInput input{{background:{T["card"]} !important;color:{T["text"]} !important;
    -webkit-text-fill-color:{T["text"]} !important;
    border:1.5px solid {T["border2"]} !important;border-radius:10px !important;font-size:13px !important;}}
.stAlert{{border-radius:10px !important;font-family:'Outfit',sans-serif !important;}}
[data-testid="stToggle"] label{{color:{T["muted"]} !important;font-size:11px !important;}}
::-webkit-scrollbar{{width:4px;}}
::-webkit-scrollbar-thumb{{background:{T["border2"]};border-radius:2px;}}
iframe[height="0"]{{position:absolute !important;width:0 !important;height:0 !important;
    border:none !important;pointer-events:none !important;}}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────
# DESKTOP CSS
# ─────────────────────────────
else:
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');
*,*::before,*::after{{box-sizing:border-box;}}
.stApp{{
    background:linear-gradient(160deg,#040a14 0%,#071020 25%,#091528 55%,#0c1c38 80%,#0e2040 100%) !important;
    font-family:'Outfit',sans-serif !important;min-height:100vh;
}}
.stApp::before{{content:'';position:fixed;inset:0;
    background-image:radial-gradient(circle,rgba(59,158,255,0.05) 1px,transparent 1px);
    background-size:30px 30px;pointer-events:none;z-index:0;}}
.block-container{{max-width:800px !important;margin:0 auto !important;padding:1rem 1.5rem 5.5rem !important;}}
#MainMenu,footer,header,[data-testid="stToolbar"],.stDeployButton{{display:none !important;}}
::-webkit-scrollbar{{width:4px;}}
::-webkit-scrollbar-thumb{{background:{T["border2"]};border-radius:4px;}}
{shared_message_css()}
[data-testid="stChatInput"]{{background:#0c1a32 !important;border:1.5px solid {T["border2"]} !important;
    border-radius:18px !important;
    box-shadow:0 4px 28px rgba(0,0,0,0.4),0 0 0 1px rgba(59,158,255,0.1) !important;
    backdrop-filter:blur(20px) !important;padding:6px 8px !important;}}
[data-testid="stChatInput"]:focus-within{{border-color:{T["accent"]} !important;
    box-shadow:0 4px 32px rgba(59,158,255,0.25),0 0 0 2px {T["accent"]}40 !important;}}
[data-testid="stChatInput"] textarea{{background:#0c1a32 !important;color:#e8f2ff !important;
    -webkit-text-fill-color:#e8f2ff !important;font-family:'Outfit',sans-serif !important;
    font-size:15px !important;caret-color:{T["accent"]} !important;
    border:none !important;outline:none !important;resize:none !important;
    padding:10px 14px !important;line-height:1.5 !important;}}
[data-testid="stChatInput"] textarea::placeholder{{color:{T["muted"]} !important;
    -webkit-text-fill-color:{T["muted"]} !important;font-style:italic !important;}}
[data-testid="stChatInput"] button{{background:linear-gradient(135deg,{T["accent"]},{T["accent2"]}) !important;
    border:none !important;border-radius:12px !important;
    width:38px !important;height:38px !important;box-shadow:0 2px 10px {T["accent"]}50 !important;}}
[data-testid="stChatInput"] button:hover{{transform:scale(1.08) !important;}}
[data-testid="stChatInput"] button svg{{fill:#ffffff !important;stroke:#ffffff !important;}}
.stButton>button{{background:{T["card"]} !important;color:{T["muted"]} !important;
    border:1px solid {T["border"]} !important;border-radius:999px !important;
    font-family:'Outfit',sans-serif !important;font-size:13px !important;font-weight:600 !important;padding:5px 14px !important;}}
.stButton>button:hover{{background:{T["card2"]} !important;border-color:{T["accent"]} !important;
    color:{T["accent"]} !important;transform:translateY(-1px) !important;}}
[data-testid="stFileUploader"]{{background:{T["card"]} !important;
    border:1.5px dashed {T["border2"]} !important;border-radius:12px !important;}}
.stTextInput input{{background:#0c1a32 !important;color:#e8f2ff !important;
    -webkit-text-fill-color:#e8f2ff !important;border:1.5px solid {T["border2"]} !important;
    border-radius:10px !important;font-size:13px !important;}}
.stTextInput input:focus{{border-color:{T["accent"]} !important;}}
.stTextInput label,[data-testid="stToggle"] label{{color:{T["muted"]} !important;font-size:11px !important;}}
.stAlert{{border-radius:10px !important;font-family:'Outfit',sans-serif !important;}}
iframe[height="0"]{{position:absolute !important;width:0 !important;height:0 !important;
    border:none !important;pointer-events:none !important;}}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# JS — device detection (mobile/tablet/desktop)
# ══════════════════════════════════════════════
st.components.v1.html("""
<script>
(function(){
  try{
    var w = window.parent.innerWidth || window.innerWidth || screen.width;
    var d = w < 768 ? 'mobile' : (w < 1100 ? 'tablet' : 'desktop');
    var url = new URL(window.parent.location.href);
    if(url.searchParams.get('device') !== d){
      url.searchParams.set('device', d);
      window.parent.location.replace(url.toString());
    }
  }catch(e){}
})();
</script>
""", height=0, scrolling=False)

# ── Idle timeout JS ──
st.components.v1.html(f"""
<script>
(function(){{
  var IDLE={IDLE_TIMEOUT*1000};var t;
  function reset(){{
    clearTimeout(t);
    t=setTimeout(function(){{
      try{{
        var url=new URL(window.parent.location.href);
        url.searchParams.set('clear','1');
        window.parent.location.replace(url.toString());
      }}catch(e){{}}
    }},IDLE);
  }}
  ['mousemove','keydown','click','scroll','touchstart','touchmove']
    .forEach(function(e){{window.parent.addEventListener(e,reset,true);}});
  reset();
}})();
</script>
""", height=0, scrolling=False)

# ══════════════════════════════════════════════
# HEADER — injected via JS for mobile/tablet
# ══════════════════════════════════════════════
mode_colors  = {"General": T["accent"], "Document": T["accent3"], "URL": T["accent2"]}
active_color = mode_colors[current_mode]
m_icons      = {"General": "💬", "Document": "📄", "URL": "🔗"}

if is_mobile or is_tablet:
    theme_link = "light" if st.session_state.theme == "Dark" else "dark"
    theme_icon = "☀️"   if st.session_state.theme == "Dark" else "🌙"
    hdr_width  = "100%" if is_mobile else "640px"
    hdr_left   = "0"    if is_mobile else "50%"
    hdr_transform = "none" if is_mobile else "translateX(-50%)"

    pills_html = ""
    for m in ["General","Document","URL"]:
        active   = current_mode == m
        col      = mode_colors[m]
        pill_bg  = col if active else "rgba(255,255,255,0.1)"
        pill_brd = col if active else "rgba(255,255,255,0.2)"
        glow     = f"0 0 10px {col}90" if active else "none"
        pills_html += (
            f'<a href="?mode={m}&device={device}" style="'
            f'background:{pill_bg};border:1.5px solid {pill_brd};'
            f'border-radius:999px;padding:5px 12px;font-size:12px;font-weight:700;'
            f'color:#ffffff;text-decoration:none;white-space:nowrap;'
            f'box-shadow:{glow};display:inline-flex;align-items:center;gap:4px;">'
            f'{m_icons[m]}</a>'
        )

    st.components.v1.html(f"""
<script>
(function(){{
  try{{
    var ex=window.parent.document.getElementById('srin-hdr');
    if(ex) ex.remove();
    var hdr=window.parent.document.createElement('div');
    hdr.id='srin-hdr';
    hdr.style.cssText='position:fixed;top:0;left:{hdr_left};'
      +'transform:{hdr_transform};width:{hdr_width};height:68px;'
      +'background:linear-gradient(135deg,{T["card"]},{T["card2"]});'
      +'border-bottom:1px solid {T["border2"]};'
      +'z-index:999999;display:flex;align-items:center;'
      +'padding:0 14px;gap:0;'
      +'box-shadow:0 2px 20px rgba(0,0,0,0.5);'
      +'font-family:Outfit,sans-serif;';
    hdr.innerHTML=`
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
      <div style="flex:1;"></div>
      <div style="display:flex;gap:6px;align-items:center;">
        {pills_html}
      </div>
      <a href="?mode={current_mode}&device={device}&theme={theme_link}"
        style="font-size:20px;text-decoration:none;flex-shrink:0;margin-left:10px;
          display:flex;align-items:center;justify-content:center;
          width:34px;height:34px;border-radius:50%;
          background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.15);">
        {theme_icon}
      </a>`;
    window.parent.document.body.prepend(hdr);
  }}catch(e){{console.log(e);}}
}})();
</script>
""", height=0, scrolling=False)

else:
    # ── DESKTOP HEADER ──
    st.markdown(f"""
<div style="background:linear-gradient(135deg,{T['card']} 0%,{T['card2']} 100%);
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
</div>""", unsafe_allow_html=True)

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
                active = current_mode == m
                if st.button(f"{'● ' if active else ''}{m_icons[m]} {m}",
                             key=f"mbtn_{m}", use_container_width=True):
                    if current_mode != m:
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

# ══════════════════════════════════════════════
# DOCUMENT / URL PANELS
# ══════════════════════════════════════════════
pad = "8px 12px" if is_mobile else "10px 16px"
fs1 = "11px"     if is_mobile else "12px"
fs2 = "10px"     if is_mobile else "11px"
br  = "10px"     if is_mobile else "12px"

if current_mode == "Document":
    st.markdown(f"""
<div style="background:{T['card']};border:1px solid {T['border2']};
    border-left:3px solid {T['accent3']};border-radius:{br};
    padding:{pad};margin-bottom:8px;">
  <div style="font-size:{fs1};color:{T['accent3']};font-weight:700;
    letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">📄 Upload Document</div>
  <div style="font-size:{fs2};color:{T['muted']};">PDF · DOCX · TXT &nbsp;·&nbsp;
    <span style="color:{T['accent']};">Session only.</span></div>
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
                mc2 = 6000 if is_mobile else 12000
                st.session_state.doc_context = text[:mc2]
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
    border-left:3px solid {T['accent2']};border-radius:{br};
    padding:{pad};margin-bottom:8px;">
  <div style="font-size:{fs1};color:{T['accent2']};font-weight:700;
    letter-spacing:1px;text-transform:uppercase;margin-bottom:3px;">🔗 Load a URL</div>
  <div style="font-size:{fs2};color:{T['muted']};">Any public page · docs · blogs.&nbsp;
    <span style="color:{T['accent']};">Session only.</span></div>
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
                mc2 = 6000 if is_mobile else 12000
                st.session_state.url_context = clean[:mc2]
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
        "General":  ("💬","Ask me anything",  "Try: What is LangChain?"),
        "Document": ("📄","Ready",             "Ask: Summarise this document"),
        "URL":      ("🔗","Page loaded",        "Ask: What is this page about?"),
    }
    ico, title, hint = hints[current_mode]
    st.markdown(f"""
<div style="text-align:center;padding:{'20px 10px' if is_mobile else '44px 20px'};color:{T['muted']};">
  <div style="font-size:{'36px' if is_mobile else '44px'};margin-bottom:10px;">{ico}</div>
  <div style="font-size:{'15px' if is_mobile else '17px'};font-weight:700;
    color:{T['text']};margin-bottom:8px;">{title}</div>
  <div style="font-size:{'11px' if is_mobile else '12px'};color:{T['muted']};
    font-style:italic;background:{T['card']};border:1px solid {T['border']};
    border-radius:8px;padding:6px 14px;display:inline-block;">{hint}</div>
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
    mob = ("IMPORTANT: User is on mobile. Max 120 words. "
           "Bullet points preferred. No long intros.\n\n") if is_mobile else ""
    m = st.session_state.mode
    if m == "Document" and st.session_state.doc_context:
        return (f"{mob}Answer ONLY from the document. If not found say so.\n\n"
                f"=== DOCUMENT ===\n{st.session_state.doc_context}\n=== END ===\n\n"
                f"Question: {user_input}")
    elif m == "URL" and st.session_state.url_context:
        return (f"{mob}Answer ONLY from the webpage. "
                f"Source: {st.session_state.url_loaded}\nIf not found say so.\n\n"
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

# ══════════════════════════════════════════════
# DESKTOP STATUS BAR
# ══════════════════════════════════════════════
if is_desktop:
    status = {
        "General":  "💬 General AI",
        "Document": f"📄 {st.session_state.doc_name}" if st.session_state.doc_name else "📄 No document",
        "URL":      f"🔗 {(st.session_state.url_loaded or '')[:45]}" if st.session_state.url_loaded else "🔗 No URL",
    }[current_mode]
    msg_count    = len([m for m in st.session_state.messages if m["role"]=="user"])
    idle_elapsed = now - st.session_state.last_active
    idle_pct     = min(100, int(idle_elapsed/IDLE_TIMEOUT*100))
    st.markdown(f"""
<div style="position:fixed;bottom:0;left:50%;transform:translateX(-50%);
    width:min(800px,98vw);background:{T['card']};
    border-top:1px solid {T['border']};padding:5px 16px;
    display:flex;align-items:center;justify-content:space-between;
    z-index:9999;font-family:'Outfit',sans-serif;
    backdrop-filter:blur(16px);box-shadow:0 -4px 20px rgba(0,0,0,0.2);">
  <div style="position:absolute;top:0;left:0;right:0;height:2px;background:{T['border']};">
    <div style="height:2px;width:{idle_pct}%;
      background:{'linear-gradient(90deg,#ff8800,#ff4444)' if idle_pct>80 else f'linear-gradient(90deg,{T["accent"]},{T["accent2"]})'};">
    </div></div>
  <div style="display:flex;align-items:center;gap:6px;">
    <div style="width:7px;height:7px;border-radius:50%;
      background:{active_color};box-shadow:0 0 6px {active_color}80;"></div>
    <span style="font-size:11px;color:{T['muted']};">{status}</span>
  </div>
  <div style="font-size:10px;color:{T['muted']};display:flex;align-items:center;gap:8px;">
    <span>🖥 Desktop</span><span>·</span>
    <span>{msg_count} msg{"s" if msg_count!=1 else ""}</span><span>·</span>
    <span style="color:{'#ff8800' if idle_pct>70 else T['muted']};">
      ⏱ {int((IDLE_TIMEOUT-idle_elapsed)/60)}m left</span>
  </div>
</div>""", unsafe_allow_html=True)
