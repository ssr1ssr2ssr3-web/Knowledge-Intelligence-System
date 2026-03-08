import streamlit as st
import os
from dotenv import load_dotenv
from google import genai

# Configuration
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("API Key not found! Ensure GEMINI_API_KEY is set.")
    st.stop()

client = genai.Client(api_key=api_key)

# Page Configuration
st.set_page_config(page_title="SuperChat AI.2", page_icon="💬", layout="centered")

# --- THEME SWITCHER LOGIC ---
if "theme" not in st.session_state:
    st.session_state.theme = "Light"

theme_toggle = st.toggle("Dark Mode", value=(st.session_state.theme == "Dark"))
st.session_state.theme = "Dark" if theme_toggle else "Light"

# --- DYNAMIC CSS STYLING ---
bg_color = "#e5ddd5" if st.session_state.theme == "Light" else "#0b141a"
chat_bg = "#ffffff" if st.session_state.theme == "Light" else "#202c33"
text_color = "#000000" if st.session_state.theme == "Light" else "#ffffff"
border_color = "#d1d1d1" if st.session_state.theme == "Light" else "#3e5263"
input_bg = "linear-gradient(90deg, #ffffff, #f0f2f6)" if st.session_state.theme == "Light" else "linear-gradient(90deg, #202c33, #111b21)"

st.markdown(f"""
    <style>
    /* Global background */
    .stApp {{ background-color: {bg_color}; }}
    
    /* Compact layout - remove excessive gaps */
    .block-container {{
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }}
    
    /* Message Boxes - Tightened */
    [data-testid="stChatMessage"] {{
        background-color: {chat_bg} !important;
        border: 1px solid {border_color};
        border-radius: 12px;
        padding: 8px 12px !important;
        margin-bottom: 5px !important;
    }}
    
    /* Text adjustment */
    [data-testid="stChatMessage"] p {{
        color: {text_color} !important;
        margin: 0 !important;
    }}
    
    /* Chat Input Styling */
    div[data-testid="stChatInput"] {{
        background: {input_bg} !important;
        border-radius: 25px;
        padding: 2px 10px;
        border: 2px solid #25d366;
    }}
    </style>
    """, unsafe_allow_html=True)

st.title("💬 SuperChat AI.2")

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display Messages
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat Input
if prompt := st.chat_input("Type a message..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("SuperChat AI.2 is thinking..."):
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt
            )
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})