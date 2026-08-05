# src/ui/pages/system.py
"""
System page – combines Settings and About sections.

Provides:
1️⃣ Settings – user profile information and password‑change form.
2️⃣ About – project description, technical stack, version, and credits.

All authentication, session handling, and logging are reused from the original
pages.
"""

import streamlit as st
from datetime import datetime

from src.security.auth import require_auth, get_current_user, update_password
from src.logging.logger import get_logger

logger = get_logger(__name__)


def _render_settings() -> None:
    """Display the Settings UI (profile + password update)."""
    require_auth()
    user = get_current_user()

    st.subheader("Profile")
    st.write(f"**User ID:** {user.id}")
    st.write(f"**Email:** {user.email}")
    created = (
        user.created_at.strftime("%Y-%m-%d")
        if hasattr(user, "created_at")
        else "N/A"
    )
    st.write(f"**Joined:** {created}")

    st.subheader("Change Password")
    current_pw = st.text_input("Current password", type="password")
    new_pw = st.text_input("New password", type="password")
    confirm_pw = st.text_input("Confirm new password", type="password")

    if st.button("Update Password"):
        if not current_pw or not new_pw or not confirm_pw:
            st.error("Please fill in all fields.")
        elif new_pw != confirm_pw:
            st.error("New passwords do not match.")
        else:
            success, msg = update_password(user.id, current_pw, new_pw)
            if success:
                st.success("Password updated successfully.")
                logger.info("User %s updated password", user.email)
            else:
                st.error(f"Failed to update password: {msg}")
                logger.warning(
                    "Password update failed for user %s: %s", user.email, msg
                )

    st.caption(
        f"Settings loaded at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )


def _render_about() -> None:
    """Display the About UI."""
    require_auth()
    st.subheader("Project Overview")
    st.markdown(
        "PayShield AI combines machine learning, streaming simulation, and a "
        "conversational assistant to help financial institutions detect "
        "fraudulent transactions in real time. All components are built with "
        "Streamlit for a seamless, single‑page web experience."
    )

    st.subheader("Technical Stack")
    st.table(
        [
            {"Component": "Web UI", "Technology": "Streamlit"},
            {
                "Component": "ML Engine",
                "Technology": "Scikit‑learn, OpenAI (explainability)",
            },
            {"Component": "Database", "Technology": "PostgreSQL via SQLAlchemy"},
            {"Component": "Auth", "Technology": "Email/password with bcrypt"},
            {"Component": "Chatbot", "Technology": "OpenRouter (GPT‑4o‑mini)"},
        ]
    )

    st.subheader("Version & License")
    st.write("**Version:** 1.0.0")
    st.write("**License:** MIT – free for academic and commercial use.")

    st.subheader("Authors & Credits")
    st.markdown(
        "- **Primary Developer:** Your Name (Student, Final‑Year AI Project)\n"
        "- **Mentor:** AI Coach (OpenAI)\n"
        "- **Libraries:** Streamlit, SQLAlchemy, pandas, scikit‑learn, bcrypt, requests"
    )

    st.caption(
        f"About page generated on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )
    logger.info("Rendered About section")


def render() -> None:
    """Render the combined System page with Settings and About sections."""
    require_auth()
    st.title("🖥️ System")
    st.caption("Manage account settings and view project information.")

    # Use tabs to separate the two logical sections
    tab_settings, tab_about = st.tabs(["Settings", "About"])

    with tab_settings:
        _render_settings()

    with tab_about:
        _render_about()