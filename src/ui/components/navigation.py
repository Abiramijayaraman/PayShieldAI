"""
Sidebar navigation component for PayShield AI.
"""

import os
import streamlit as st


# Project root
BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

LOGO_PATH = os.path.join(BASE_DIR, "assets", "logo.png")


def render_sidebar(pages: list):
    """Render the application sidebar."""

    st.sidebar.title("PayShield AI")

    if os.path.exists(LOGO_PATH):
        st.sidebar.image(LOGO_PATH, width=180)
    else:
        st.sidebar.warning("Logo not found")

    selection = st.sidebar.radio(
        "Navigate",
        pages,
    )

    return selection