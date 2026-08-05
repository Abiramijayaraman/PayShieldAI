# src/ml/inference.py
"""Inference utilities for PayShield AI.
Loads the serialized model and preprocessing pipeline, and exposes a
``predict_transaction`` function that returns a dictionary with all required
fields (probability, risk score, prediction, confidence, category).
"""
import json
from pathlib import Path
import numpy as np
import joblib
import pandas as pd

# Paths are resolved relative to this file
BASE_DIR = Path(__file__).resolve().parents[2]
MODEL_DIR = BASE_DIR / "models"
METADATA_PATH = MODEL_DIR / "metadata.json"

def load_artifacts():
    """Load the model, preprocessor and metadata.
    Returns a tuple (model, preprocessor, metadata_dict).
    """
    model_path = MODEL_DIR / "fraud_model.pkl"
    prep_path = MODEL_DIR / "preprocessing.pkl"
    if not model_path.is_file() or not prep_path.is_file() or not METADATA_PATH.is_file():
        raise FileNotFoundError("Model artifacts not found. Please run the training script first.")
    model = joblib.load(model_path)
    preprocessor = joblib.load(prep_path)
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        metadata = json.load(f)
    return model, preprocessor, metadata

def _risk_score(probability: float) -> float:
    """Convert a fraud probability (0‑1) to a risk score (0‑100)."""
    return round(probability * 100, 2)

def predict_transaction(raw_transaction: pd.Series) -> dict:
    """Predict fraud for a single transaction.
    Args:
        raw_transaction: pandas Series containing the raw transaction features
                        (must contain the same columns used during training
                        *excluding* the target column).
    Returns:
        dict with keys: ``prediction`` (bool), ``fraud_probability`` (float),
        ``risk_score`` (float), ``confidence`` (float, same as probability),
        ``fraud_category`` (str, optional).
    """
    model, preprocessor, metadata = load_artifacts()
    # The preprocessing pipeline expects a DataFrame
    df = pd.DataFrame([raw_transaction])
    X = preprocessor.transform(df)
    proba = model.predict_proba(X)[0, 1]
    threshold = metadata.get("optimal_threshold", 0.5)
    pred = bool(proba >= threshold)
    # Simple category based on risk score ranges
    risk = _risk_score(proba)
    if risk >= 80:
        category = "High"
    elif risk >= 50:
        category = "Medium"
    else:
        category = "Low"
    return {
        "prediction": pred,
        "fraud_probability": round(proba, 4),
        "risk_score": risk,
        "confidence": round(proba, 4),
        "fraud_category": category,
    }

def predict_batch(df: pd.DataFrame) -> pd.DataFrame:
    """Predict fraud for a batch of transactions.

    Args:
        df: DataFrame where each row is a transaction (features matching training).

    Returns:
        DataFrame with original columns plus prediction results:
        ``prediction``, ``fraud_probability``, ``risk_score``, ``confidence``, ``fraud_category``.
    """
    model, preprocessor, metadata = load_artifacts()
    X = preprocessor.transform(df)
    probs = model.predict_proba(X)[:, 1]
    threshold = metadata.get("optimal_threshold", 0.5)
    preds = probs >= threshold
    risk_scores = [_risk_score(p) for p in probs]
    categories = [
        "High" if rs >= 80 else "Medium" if rs >= 50 else "Low"
        for rs in risk_scores
    ]
    result = df.copy()
    result["prediction"] = preds
    result["fraud_probability"] = probs.round(4)
    result["risk_score"] = risk_scores
    result["confidence"] = probs.round(4)
    result["fraud_category"] = categories
    return result
