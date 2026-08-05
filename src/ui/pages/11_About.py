# src/ui/pages/11_About.py
"""About page.
Provides project information, version, and credits.
"""

import streamlit as st
from datetime import datetime
from src.security.auth import require_auth
from src.logging.logger import get_logger

logger = get_logger(__name__)

def render():
    require_auth()
    st.title("ℹ️ About PayShield AI")
    st.caption("An AI‑powered real‑time financial fraud detection system.")

    st.subheader("Project Overview")
    st.markdown(
        "PayShield AI combines machine learning, streaming simulation, and a conversational "
        "assistant to help financial institutions detect fraudulent transactions in real time. "
        "All components are built with Streamlit for a seamless, single‑page web experience."
    )

    st.subheader("Technical Stack")
    st.table([
        {"Component": "Web UI", "Technology": "Streamlit"},
        {"Component": "ML Engine", "Technology": "Scikit‑learn, OpenAI (explainability)"},
        {"Component": "Database", "Technology": "PostgreSQL via SQLAlchemy"},
        {"Component": "Auth", "Technology": "Email/password with bcrypt"},
        {"Component": "Chatbot", "Technology": "OpenRouter (GPT‑4o‑mini)"},
    ])

    st.subheader("Version & License")
    st.write("**Version:** 1.0.0")
    st.write("**License:** MIT – free for academic and commercial use.")

    st.subheader("Authors & Credits")
    st.markdown(
        "- **Primary Developer:** Your Name (Student, Final‑Year AI Project)\n"
        "- **Mentor:** AI Coach (OpenAI)\n"
        "- **Libraries:** Streamlit, SQLAlchemy, pandas, scikit‑learn, bcrypt, requests"
    )

    st.caption(f"Page generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    logger.info("Rendered About page")
