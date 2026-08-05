# src/ui/pages/10_Settings.py
"""Settings page.
Allows the authenticated user to update their password and view basic profile info.
"""

import streamlit as st
from datetime import datetime
from src.security.auth import require_auth, get_current_user, update_password
from src.logging.logger import get_logger

logger = get_logger(__name__)

def render():
    require_auth()
    user = get_current_user()
    st.title("⚙️ Settings")
    st.caption("Manage your account settings.")

    st.subheader("Profile")
    st.write(f"**User ID:** {user.id}")
    st.write(f"**Email:** {user.email}")
    st.write(f"**Joined:** {user.created_at.strftime('%Y-%m-%d') if hasattr(user, 'created_at') else 'N/A'}")

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
                logger.warning("Password update failed for user %s: %s", user.email, msg)

    st.caption(f"Settings page loaded at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
