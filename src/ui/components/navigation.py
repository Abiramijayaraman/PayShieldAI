"""
Sidebar navigation component for PayShield AI.
"""

import os

import streamlit as st


BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo.png")


PAGE_ICONS = {
    "Login": "🔐",
    "Dashboard": "📊",
    "Transaction Analysis": "🔎",
    "Fraud Monitoring": "🛡️",
    "Simulation Lab": "🚀",
    "Reports & History": "📄",
    "AI Fraud Assistant": "🤖",
    "System": "⚙️",
}


def render_sidebar(pages: list):
    """Render the application sidebar and return the selected page."""

    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center; padding-top:0.4rem;">
                <div style="
                    font-size:1.65rem;
                    font-weight:800;
                    color:#0F172A;
                    letter-spacing:-0.02em;
                ">
                    PayShield AI
                </div>
                <div style="
                    font-size:0.82rem;
                    color:#64748B;
                    margin-top:0.2rem;
                    margin-bottom:0.8rem;
                ">
                    AI-Powered Fraud Detection
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if os.path.exists(LOGO_PATH):
            logo_left, logo_center, logo_right = st.columns([1, 3, 1])

            with logo_center:
                st.image(LOGO_PATH, width=180)
        else:
            st.warning("Logo not found")

        st.markdown("---")

        display_pages = [
            f"{PAGE_ICONS.get(page, '•')} {page}"
            for page in pages
        ]

        selected_display = st.radio(
            "Navigation",
            display_pages,
            label_visibility="collapsed",
        )

        st.markdown("---")

        st.caption(
            "Secure transaction monitoring, fraud analytics, "
            "alerts, and AI-assisted investigation."
        )

    selected_index = display_pages.index(selected_display)
    return pages[selected_index]