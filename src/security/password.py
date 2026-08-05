# src/security/password.py
"""Utility functions for password hashing and verification using bcrypt."""
import bcrypt
from typing import Union

def hash_password(password: Union[str, bytes]) -> str:
    """Hash a plain‑text password.
    Returns the hashed password as a UTF‑8 string.
    """
    if isinstance(password, str):
        password = password.encode("utf-8")
    hashed = bcrypt.hashpw(password, bcrypt.gensalt())
    return hashed.decode("utf-8")

def verify_password(plain_password: Union[str, bytes], hashed_password: str) -> bool:
    """Verify a plain‑text password against the stored hash.
    """
    if isinstance(plain_password, str):
        plain_password = plain_password.encode("utf-8")
    return bcrypt.checkpw(plain_password, hashed_password.encode("utf-8"))
