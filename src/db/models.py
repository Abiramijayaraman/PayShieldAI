# src/db/models.py
"""SQLAlchemy ORM models for PayShield AI.
All tables are created automatically via Base.metadata.create_all().
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from src.db.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    # Relationships
    predictions = relationship("Prediction", back_populates="user", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    chats = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    # Store raw JSON of the transaction for reference
    raw_data = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # One‑to‑many relationship to predictions (a transaction may be processed multiple times in simulation)
    predictions = relationship("Prediction", back_populates="transaction", cascade="all, delete-orphan")

class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=False)
    fraud_probability = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    prediction = Column(Boolean, nullable=False)  # True = fraud, False = legit
    confidence = Column(Float, nullable=False)   # Model confidence (e.g., 0‑1)
    fraud_category = Column(String(100), nullable=True)
    explanation = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    user = relationship("User", back_populates="predictions")
    transaction = relationship("Transaction", back_populates="predictions")

class Alert(Base):
    __tablename__ = "alerts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    risk_score = Column(Float, nullable=False)
    reason = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Relationships
    user = relationship("User", back_populates="alerts")
    prediction = relationship("Prediction")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    report_type = Column(String(50), nullable=False)  # daily, weekly, monthly
    generated_at = Column(DateTime, default=datetime.utcnow)
    file_path = Column(String(500), nullable=False)   # Path to generated CSV
    report_metadata = Column("metadata", JSON, nullable=True)
    user = relationship("User", back_populates="reports")

class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(10), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="chats")

class TrainingMetadata(Base):
    __tablename__ = "training_metadata"
    id = Column(Integer, primary_key=True, index=True)
    model_name = Column(String(100), nullable=False)
    version = Column(String(50), nullable=False)
    trained_at = Column(DateTime, default=datetime.utcnow)
    metrics = Column(JSON, nullable=False)  # store full metrics dict
    feature_schema = Column(JSON, nullable=False)
    preprocessing_path = Column(String(500), nullable=False)
    model_path = Column(String(500), nullable=False)
