# src/security/auth.py
"""Authentication helpers for Streamlit using PostgreSQL and bcrypt.
All user data is stored in the PostgreSQL database.
Session state keys:
    - "user_id"   : integer primary key of the logged‑in user
    - "user_email": email address (optional convenience)
"""
import streamlit as st
from sqlalchemy.exc import IntegrityError
from src.db.session import SessionLocal
from src.db.models import User
import logging
from src.logging.logger import get_logger
logger = get_logger(__name__)
from src.security.password import hash_password, verify_password
from typing import Optional

def get_db():
    """Utility to get a DB session for the current request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def register_user(email: str, password: str) -> bool:
    """Create a new user.
    Returns True on success, False if the email already exists.
    """
    db = SessionLocal()
    try:
        if db.query(User).filter(User.email == email).first():
            return False
        new_user = User(email=email, hashed_password=hash_password(password))
        db.add(new_user)
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False
    finally:
        db.close()

def login_user(email: str, password: str) -> bool:
    """Validate credentials and set Streamlit session state.
    Returns True if login succeeded.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user and verify_password(password, user.hashed_password):
            st.session_state["user_id"] = user.id
            st.session_state["user_email"] = user.email
            return True
        return False
    finally:
        db.close()

def logout_user() -> None:
    """Clear authentication information from the session."""
    for key in ["user_id", "user_email"]:
        if key in st.session_state:
            del st.session_state[key]
    st.rerun()

def get_current_user() -> Optional[User]:
    """Return the User ORM object for the logged‑in user, or None."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return None
    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == user_id).first()
    finally:
        db.close()

def require_auth():
    """Call at the top of any page that requires authentication.
    If the user is not logged in, show a warning and stop execution.
    """
    if st.session_state.get("user_id") is None:
        st.warning("🔒 Please log in to access this page.")
        st.stop()

def update_password(user_id: int, current_pw: str, new_pw: str) -> tuple:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False, "User not found."
        if not verify_password(current_pw, user.hashed_password):
            return False, "Current password incorrect."
        user.hashed_password = hash_password(new_pw)
        db.commit()
        return True, "Password updated."
    except Exception as e:
        db.rollback()
        return False, str(e)
    finally:
        db.close()
