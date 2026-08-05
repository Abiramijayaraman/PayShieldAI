# src/ui/pages/1_Login.py
"""Login / Registration page for PayShield AI.
Provides a ``render()`` function that Streamlit calls.
"""
import streamlit as st
from src.security.auth import register_user, login_user, logout_user


def render():
    st.title("🔐 PayShield AI – Login / Register")
    # Show logout if already logged in
    if st.session_state.get("user_id"):
        st.success(f"Logged in as {st.session_state.get('user_email')}")
        if st.button("Logout"):
            logout_user()
        st.stop()
    # Tabs for login and register
    tab1, tab2 = st.tabs(["Login", "Register"])
    with tab1:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in")
            if submitted:
                if login_user(email, password):
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    with tab2:
        with st.form("register_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            password_confirm = st.text_input("Confirm password", type="password")
            submitted = st.form_submit_button("Create account")
            if submitted:
                if password != password_confirm:
                    st.error("Passwords do not match.")
                elif len(password) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    if register_user(email, password):
                        st.success("Account created! You can now log in.")
                    else:
                        st.error("An account with this email already exists.")
