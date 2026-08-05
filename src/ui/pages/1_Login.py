# src/ui/pages/1_Login.py
"""Login / Registration page for PayShield AI.

Provides a ``render()`` function that Streamlit calls.
"""

import streamlit as st

from src.security.auth import register_user, login_user, logout_user


def render():
    """Render the Login / Register page."""

    st.title("🔐 PayShield AI – Login / Register")
    st.caption(
        "Secure access to fraud detection, transaction monitoring, "
        "analytics, alerts, and reports."
    )

    # Show logged-in state
    if st.session_state.get("user_id"):
        left, center, right = st.columns([1, 2, 1])

        with center:
            st.success(
                f"Logged in as {st.session_state.get('user_email')}"
            )

            if st.button(
                "Logout",
                use_container_width=True,
                key="logout_button",
            ):
                logout_user()

        st.stop()

    # Center the authentication area
    left, center, right = st.columns([1, 2, 1])

    with center:
        tab_login, tab_register = st.tabs(
            ["🔐 Login", "📝 Register"]
        )

        with tab_login:
            st.subheader("Welcome back")
            st.caption(
                "Enter your account details to continue to PayShield AI."
            )

            with st.form("login_form"):
                email = st.text_input(
                    "Email",
                    placeholder="name@example.com",
                    key="login_email",
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Enter your password",
                    key="login_password",
                )

                submitted = st.form_submit_button(
                    "Log in",
                    use_container_width=True,
                )

                if submitted:
                    if not email or not password:
                        st.warning("Please enter both email and password.")
                    elif login_user(email, password):
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error("Invalid credentials.")

        with tab_register:
            st.subheader("Create an account")
            st.caption(
                "Register securely to access PayShield AI features."
            )

            with st.form("register_form"):
                email = st.text_input(
                    "Email",
                    placeholder="name@example.com",
                    key="register_email",
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Create a password",
                    key="register_password",
                )

                password_confirm = st.text_input(
                    "Confirm password",
                    type="password",
                    placeholder="Re-enter your password",
                    key="register_password_confirm",
                )

                submitted = st.form_submit_button(
                    "Create account",
                    use_container_width=True,
                )

                if submitted:
                    if not email or not password or not password_confirm:
                        st.warning("Please complete all registration fields.")
                    elif password != password_confirm:
                        st.error("Passwords do not match.")
                    elif len(password) < 6:
                        st.error(
                            "Password must be at least 6 characters."
                        )
                    elif register_user(email, password):
                        st.success(
                            "Account created! You can now log in."
                        )
                    else:
                        st.error(
                            "An account with this email already exists."
                        )