# src/db/session.py
"""SQLAlchemy session factory.
Creates an engine from the DATABASE_URL environment variable and provides a scoped Session.
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from src.config import settings

# Create engine with pool_pre_ping to handle disconnects
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, echo=False)

# Scoped session for thread‑safe usage in Streamlit
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def get_db():
    """Yield a new DB session for dependency injection.
    Usage:
        with get_db() as db:
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
