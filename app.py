import streamlit as st
import os
from dotenv import load_dotenv
from google import genai

# Load local .env if it exists
load_dotenv()

# The client uses the GEMINI_API_KEY environment variable automatically
# This additional comment is to validate whether it is syncing properly in the Github environment
# This additional comment is to ensure CI CD isworking properly in the Github environment
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("API Key not found! Ensure GEMINI_API_KEY is set.")
    st.stop()

# Initialize the new Google GenAI client
client = genai.Client(api_key=api_key)

st.title("Gemini 2.5 Chatbot")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask Gemini 2.5..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        st.markdown(response.text)
        st.session_state.messages.append({"role": "assistant", "content": response.text})