# src/ui/pages/9_Chatbot.py
"""PayShield AI Assistant page.

Provides a chat-style interface powered by OpenRouter.
The assistant is restricted to fraud detection, model predictions,
PayShield AI functionality, and application usage.
"""

from datetime import datetime
import os

import requests
import streamlit as st

from src.logging.logger import get_logger
from src.security.auth import require_auth


logger = get_logger(__name__)


OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


SYSTEM_PROMPT = (
    "You are a helpful assistant for the PayShield AI system. "
    "Answer only questions related to fraud detection model predictions, "
    "system functionality, and usage. If the user asks about unrelated topics, "
    "politely decline to answer."
)


def _call_openrouter(messages: list) -> str:
    """Send a chat completion request to OpenRouter."""
    if not OPENROUTER_API_KEY:
        logger.error(
            "OpenRouter API key missing in environment"
        )
        return (
            "OpenRouter API key is not configured. "
            "Add OPENROUTER_API_KEY to your environment file."
        )

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": (
            "https://github.com/your-repo/PayShieldAI"
        ),
        "X-Title": "PayShield AI Assistant",
    }

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            }
        ]
        + messages,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        reply = data["choices"][0]["message"]["content"]

        return reply.strip()

    except Exception as exc:
        logger.error(
            "OpenRouter request failed: %s",
            exc,
        )

        return (
            "I could not contact the AI service. "
            f"Technical details: {exc}"
        )


def _initialise_chat_state() -> None:
    """Initialise chat-related session-state values."""
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    if "chat_session_started_at" not in st.session_state:
        st.session_state.chat_session_started_at = (
            datetime.utcnow()
        )


def _clear_conversation() -> None:
    """Clear the current conversation."""
    st.session_state.chat_history = []
    st.session_state.chat_session_started_at = (
        datetime.utcnow()
    )


def _render_welcome_message() -> None:
    """Render the empty-chat welcome panel."""
    st.info(
        "Ask PayShield AI about fraud predictions, risk scores, "
        "alert severity, transaction analysis, reports, or how to "
        "use the application."
    )

    st.markdown("#### Example questions")

    example_1, example_2 = st.columns(2)

    with example_1:
        st.markdown(
            "- What does a risk score of 90 mean?\n"
            "- Why was a transaction classified as fraud?\n"
            "- How does the alert severity work?"
        )

    with example_2:
        st.markdown(
            "- How do I run batch analysis?\n"
            "- What is fraud probability?\n"
            "- How do I download a report?"
        )


def _render_chat_history() -> None:
    """Render chat history using Streamlit chat messages."""
    for message in st.session_state.chat_history:
        role = message.get(
            "role",
            "assistant",
        )

        content = message.get(
            "content",
            "",
        )

        avatar = "👤" if role == "user" else "🛡️"

        with st.chat_message(
            role,
            avatar=avatar,
        ):
            st.markdown(content)


def _submit_message(user_input: str) -> None:
    """Store a user message, call OpenRouter, and store the reply."""
    cleaned_input = user_input.strip()

    if not cleaned_input:
        return

    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": cleaned_input,
        }
    )

    request_messages = [
        {
            "role": message["role"],
            "content": message["content"],
        }
        for message in st.session_state.chat_history
    ]

    with st.spinner(
        "PayShield AI is analyzing your question..."
    ):
        reply = _call_openrouter(
            request_messages
        )

    st.session_state.chat_history.append(
        {
            "role": "assistant",
            "content": reply,
        }
    )


def render():
    """Render the PayShield AI Assistant page."""
    require_auth()
    _initialise_chat_state()

    st.title("🤖 PayShield AI Assistant")

    st.caption(
        "Ask questions about fraud predictions, risk scores, "
        "alerts, reports, and PayShield AI functionality."
    )

    header_left, header_right = st.columns(
        [3, 1]
    )

    with header_left:
        message_count = len(
            st.session_state.chat_history
        )

        st.caption(
            f"Conversation messages: {message_count}"
        )

    with header_right:
        if st.button(
            "🗑️ Clear conversation",
            use_container_width=True,
            key="clear_chat_button",
        ):
            _clear_conversation()
            st.rerun()

    st.divider()

    if not st.session_state.chat_history:
        _render_welcome_message()
    else:
        _render_chat_history()

    user_input = st.chat_input(
        "Ask PayShield AI a question..."
    )

    if user_input:
        _submit_message(user_input)
        st.rerun()

    st.divider()

    session_started = (
        st.session_state.chat_session_started_at
    )

    st.caption(
        "Session started at "
        f"{session_started.strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    logger.info(
        "Rendered AI Assistant page - total messages: %d",
        len(st.session_state.chat_history),
    )