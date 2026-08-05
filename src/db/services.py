import logging
from typing import Optional

from src.db.session import SessionLocal
from src.db import models


def save_transaction(raw_data: dict) -> models.Transaction:
    """Persist a transaction's raw JSON data and return the ORM instance."""

    db = SessionLocal()

    try:
        transaction = models.Transaction(
            raw_data=raw_data
        )

        db.add(transaction)
        db.commit()
        db.refresh(transaction)

        return transaction

    finally:
        db.close()



def save_prediction(
    user_id: int,
    transaction_id: int,
    fraud_probability: float,
    risk_score: float,
    prediction: bool,
    confidence: float,
    fraud_category: Optional[str] = None,
    explanation: Optional[str] = None,
) -> models.Prediction:
    """Create a Prediction record linked to a user and transaction.

    Converts ML numeric outputs (numpy.float64 etc.)
    into native Python types before PostgreSQL insertion.
    """

    db = SessionLocal()

    try:
        # Convert ML outputs to PostgreSQL-safe Python types
        user_id = int(user_id)
        transaction_id = int(transaction_id)

        fraud_probability = float(fraud_probability)
        risk_score = float(risk_score)
        confidence = float(confidence)

        prediction = bool(prediction)

        pred = models.Prediction(
            user_id=user_id,
            transaction_id=transaction_id,
            fraud_probability=fraud_probability,
            risk_score=risk_score,
            prediction=prediction,
            confidence=confidence,
            fraud_category=fraud_category,
            explanation=explanation,
        )

        db.add(pred)
        db.commit()
        db.refresh(pred)

        return pred

    finally:
        db.close()



def create_alert(
    user_id: int,
    prediction_id: int,
    risk_score: float,
    reason: str,
) -> models.Alert:
    """Create an alert record tied to a user and prediction.

    Converts ML numeric outputs before database insertion.
    """

    db = SessionLocal()

    try:
        user_id = int(user_id)
        prediction_id = int(prediction_id)
        risk_score = float(risk_score)

        alert = models.Alert(
            user_id=user_id,
            prediction_id=prediction_id,
            risk_score=risk_score,
            reason=reason,
        )

        db.add(alert)
        db.commit()
        db.refresh(alert)

        return alert

    finally:
        db.close()