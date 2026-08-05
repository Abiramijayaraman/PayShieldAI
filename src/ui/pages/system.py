# src/ui/pages/system.py
"""
System page for PayShield AI.

Provides:
1. Account settings and password management.
2. Short project information and technical overview.
"""

from datetime import datetime

import streamlit as st

from src.logging.logger import get_logger
from src.security.auth import (
    get_current_user,
    require_auth,
    update_password,
)


logger = get_logger(__name__)


def _render_settings() -> None:
    """Display profile information and password settings."""
    user = get_current_user()

    if user is None:
        st.error("Unable to load the current user profile.")
        return

    st.markdown("### 👤 Account Profile")
    st.caption(
        "Review your account details and manage your login password."
    )

    created_at = getattr(user, "created_at", None)

    joined_date = (
        created_at.strftime("%Y-%m-%d")
        if created_at
        else "Not available"
    )

    profile_col_1, profile_col_2, profile_col_3 = st.columns(
        [1, 2, 1]
    )

    with profile_col_1:
        st.metric(
            "User ID",
            str(user.id),
        )

    with profile_col_2:
        st.markdown("**Email address**")
        st.code(
            user.email,
            language=None,
        )

    with profile_col_3:
        st.metric(
            "Joined",
            joined_date,
        )

    st.divider()

    st.markdown("### 🔐 Change Password")
    st.caption(
        "Enter your current password and choose a new secure password."
    )

    with st.form(
        "change_password_form",
        clear_on_submit=True,
    ):
        current_password = st.text_input(
            "Current password",
            type="password",
            key="system_current_password",
        )

        password_col_1, password_col_2 = st.columns(2)

        with password_col_1:
            new_password = st.text_input(
                "New password",
                type="password",
                key="system_new_password",
            )

        with password_col_2:
            confirm_password = st.text_input(
                "Confirm new password",
                type="password",
                key="system_confirm_password",
            )

        submitted = st.form_submit_button(
            "🔄 Update Password",
            use_container_width=True,
        )

    if submitted:
        if (
            not current_password
            or not new_password
            or not confirm_password
        ):
            st.error(
                "Please complete all password fields."
            )

        elif len(new_password) < 6:
            st.error(
                "The new password must contain at least 6 characters."
            )

        elif new_password != confirm_password:
            st.error(
                "The new passwords do not match."
            )

        else:
            success, message = update_password(
                user.id,
                current_password,
                new_password,
            )

            if success:
                st.success(
                    "Password updated successfully."
                )

                logger.info(
                    "User %s updated password",
                    user.email,
                )

            else:
                st.error(
                    f"Failed to update password: {message}"
                )

                logger.warning(
                    "Password update failed for user %s: %s",
                    user.email,
                    message,
                )

    st.caption(
        "Account settings loaded at "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )


def _render_about() -> None:
    """Display short project information."""
    st.markdown("### 🛡️ About PayShield AI")

    st.write(
        """
        **PayShield AI** is an AI-powered fraud detection system designed
        to identify suspicious financial transactions using machine learning.

        The application supports single-transaction analysis, batch
        prediction, fraud monitoring, alert investigation, transaction
        simulation, report generation, and AI-assisted explanations.

        PayShield AI demonstrates how machine learning, data analysis,
        and modern web technologies can be combined in one fraud detection
        platform.
        """
    )

    st.divider()

    st.markdown("### 🚀 Key Features")

    feature_col_1, feature_col_2 = st.columns(2)

    with feature_col_1:
        st.markdown(
            """
            - Single transaction analysis
            - Batch transaction analysis
            - Fraud monitoring and alerts
            - Transaction simulation
            """
        )

    with feature_col_2:
        st.markdown(
            """
            - Prediction history
            - CSV report generation
            - AI fraud assistant
            - Secure user authentication
            """
        )

    st.divider()

    st.markdown("### 🛠️ Technology Stack")

    stack_data = [
        {
            "Component": "Frontend",
            "Technology": "Streamlit",
        },
        {
            "Component": "Machine Learning",
            "Technology": "Scikit-learn",
        },
        {
            "Component": "Database",
            "Technology": "PostgreSQL and SQLAlchemy",
        },
        {
            "Component": "Visualisation",
            "Technology": "Altair and Plotly",
        },
        {
            "Component": "Authentication",
            "Technology": "bcrypt",
        },
        {
            "Component": "AI Assistant",
            "Technology": "OpenRouter API",
        },
    ]

    st.dataframe(
        stack_data,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    version_col, application_col = st.columns(2)

    with version_col:
        st.metric(
            "Version",
            "1.0.0",
        )

    with application_col:
        st.metric(
            "Application",
            "PayShield AI",
        )

    st.divider()

    st.markdown("### 👩‍💻 Developer")

    st.write(
        "**Developer:** Abirami Jayaraman"
    )

    st.write(
        "**Application:** PayShield AI"
    )

    st.write(
        "**Description:** AI-Powered Fraud Detection System"
    )

    st.caption(
        "Project information displayed at "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC"
    )

    logger.info(
        "Rendered About section"
    )


def render() -> None:
    """Render the combined System page."""
    require_auth()

    st.title("⚙️ System & Account")

    st.caption(
        "Manage your account settings and review information "
        "about the PayShield AI project."
    )

    settings_tab, about_tab = st.tabs(
        [
            "⚙️ Account Settings",
            "ℹ️ About PayShield AI",
        ]
    )

    with settings_tab:
        _render_settings()

    with about_tab:
        _render_about()