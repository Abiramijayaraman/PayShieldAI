# src/db/__init__.py
"""Convenient imports for the DB package."""
from src.db.base import Base
from src.db.models import User, Transaction, Prediction, Alert, Report, ChatMessage, TrainingMetadata
from src.db.session import SessionLocal, engine, get_db

# Ensure tables are created on import (safe for Streamlit re‑runs)
Base.metadata.create_all(bind=engine)
