# src/ui/pages/9_Chatbot.py
"""Chatbot page.
Provides an interactive chat interface powered by OpenRouter.
The bot is constrained to answer questions about model predictions and PayShield AI functionality only.
"""

import os
import json
import streamlit as st
import requests
from datetime import datetime
from src.security.auth import require_auth
from src.logging.logger import get_logger

logger = get_logger(__name__)

# Load API key from environment (will be masked in UI)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# Simple system prompt to restrict the bot's domain
SYSTEM_PROMPT = (
    "You are a helpful assistant for the PayShield AI system. "
    "Answer only questions related to fraud detection model predictions, "
    "system functionality, and usage. If the user asks about unrelated topics, "
    "politely decline to answer."
)

def _call_openrouter(messages: list) -> str:
    """Send a chat completion request to OpenRouter and return the assistant reply.
    Uses the default model configured by the user (model selection is omitted for simplicity).
    """
    if not OPENROUTER_API_KEY:
        logger.error("OpenRouter API key missing in environment")
        return "Error: OpenRouter API key not configured."

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/your-repo/PayShieldAI",
        "X-Title": "PayShield AI Chatbot",
    }
    payload = {
        "model": "openai/gpt-4o-mini",  # generic model; can be changed via env if needed
        "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
        "temperature": 0.7,
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
        return reply.strip()
    except Exception as e:
        logger.error(f"OpenRouter request failed: {e}")
        return f"Error contacting language model: {e}"

def render():
    require_auth()
    st.title("💬 PayShield AI Chatbot")
    st.caption("Ask the assistant about predictions, risk scores, or how PayShield works.")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []  # list of dicts {role, content}

    # Display chat history
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"**You:** {msg['content']}")
        else:
            st.markdown(f"**Assistant:** {msg['content']}")
        st.markdown("---")

    # Input box
    user_input = st.text_input("Your question", key="chat_input")
    if st.button("Send") and user_input:
        # Append user message
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        # Call model
        with st.spinner("Thinking…"):
            reply = _call_openrouter([{"role": "user", "content": user_input}])
        st.session_state.chat_history.append({"role": "assistant", "content": reply})
        # Rerun to display updated history
        st.rerun()

    st.caption(f"Session started at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("Rendered Chatbot page – total messages: %d", len(st.session_state.chat_history))
