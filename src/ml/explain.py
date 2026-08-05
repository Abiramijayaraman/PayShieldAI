# src/ml/explain.py
"""Generate AI explanations for fraud-model predictions using OpenRouter.

The generative AI layer explains an existing machine-learning prediction.
It must never independently classify a transaction as fraudulent or genuine.
"""

import os
from typing import Any, List, Dict

import requests

from src.config import settings

SYSTEM_PROMPT = (
    "You are an AI assistant that explains an existing fraud-detection model "
    "prediction. Use only the information provided in the user message, such as "
    "the model prediction, fraud probability, risk score, transaction features, "
    "and feature-importance values when available. Do not independently classify "
    "the transaction. Do not change, override, or contradict the machine-learning "
    "prediction. Do not invent information. Provide a concise explanation in clear, "
    "professional language."
)


def _build_fallback_explanation(prediction_dict: dict[str, Any]) -> str:
    """Create a local explanation when the OpenRouter call is unavailable."""
    prediction = prediction_dict.get("prediction", "unknown")
    fraud_probability = prediction_dict.get("fraud_probability")
    risk_score = prediction_dict.get("risk_score")

    probability_text = (
        f"{float(fraud_probability):.2%}" if fraud_probability is not None else "unavailable"
    )
    risk_text = (
        f"{float(risk_score):.1f}" if risk_score is not None else "unavailable"
    )
    return (
        f"The machine-learning model produced a prediction of '{prediction}' "
        f"with a fraud probability of {probability_text} and a risk score of "
        f"{risk_text}. The AI explanation service is currently unavailable, so "
        "this summary is based only on the model output."
    )


def get_explanation(
    transaction_dict: dict[str, Any],
    prediction_dict: dict[str, Any],
) -> str:
    """Generate a natural-language explanation through OpenRouter.

    Args:
        transaction_dict:
            Raw transaction data represented as feature-name/value pairs.
        prediction_dict:
            Output produced by the fraud-model inference function.

    Returns:
        A concise explanation of the existing machine-learning prediction.
    """
    api_key = getattr(settings, "OPENROUTER_API_KEY", None) or os.getenv(
        "OPENROUTER_API_KEY"
    )

    model_name = getattr(settings, "OPENROUTER_MODEL", None) or os.getenv(
        "OPENROUTER_MODEL",
        "openai/gpt-4o-mini",
    )

    prediction = prediction_dict.get("prediction", "unknown")
    fraud_probability = prediction_dict.get("fraud_probability")
    risk_score = prediction_dict.get("risk_score")

    probability_text = (
        f"{float(fraud_probability):.2%}" if fraud_probability is not None else "unavailable"
    )
    risk_text = (
        f"{float(risk_score):.2f}" if risk_score is not None else "unavailable"
    )

    user_message = (
        f"Machine-learning prediction: {prediction}\n"
        f"Fraud probability: {probability_text}\n"
        f"Risk score: {risk_text}\n"
        f"Transaction features: {transaction_dict}\n\n"
        "Explain the likely factors that contributed to this existing model "
        "output. Do not independently classify the transaction. Keep the "
        "explanation concise and under 150 words."
    )

    if not api_key:
        return _build_fallback_explanation(prediction_dict)

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8501",
                "X-OpenRouter-Title": "PayShield AI",
            },
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.2,
                "max_tokens": 300,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        explanation = data["choices"][0]["message"]["content"]
        if not isinstance(explanation, str) or not explanation.strip():
            return _build_fallback_explanation(prediction_dict)
        return explanation.strip()
    except (
        requests.RequestException,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ):
        return _build_fallback_explanation(prediction_dict)


def get_batch_summary(predictions: List[Dict[str, Any]]) -> str:
    """Create a concise summary for a batch of prediction results.

    The summary includes counts per fraud category, average fraud probability,
    and overall risk score statistics. It is intended for quick overview
    without invoking the external AI service.
    """
    if not predictions:
        return "No predictions to summarize."

    total = len(predictions)
    category_counts: Dict[str, int] = {}
    prob_sum = 0.0
    risk_sum = 0.0
    for p in predictions:
        cat = p.get("fraud_category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1
        prob_sum += float(p.get("fraud_probability", 0))
        risk_sum += float(p.get("risk_score", 0))
    avg_prob = prob_sum / total
    avg_risk = risk_sum / total
    # Build readable counts string
    counts_str = ", ".join([f"{cat}: {cnt}" for cat, cnt in category_counts.items()])
    summary = (
        f"Batch of {total} predictions – categories distribution: {counts_str}. "
        f"Average fraud probability: {avg_prob:.2%}, average risk score: {avg_risk:.1f}."
    )
    return summary
