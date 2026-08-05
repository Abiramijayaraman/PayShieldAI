# src/simulation/runner.py
"""Real-time transaction simulation engine.

The runner reads the dataset row-by-row, applies the preprocessing pipeline,
predicts fraud, generates an explanation, stores results in PostgreSQL, and
updates Streamlit state.

Streamlit session-state keys:
    - sim_running: bool
    - sim_paused: bool
    - sim_speed: float
    - sim_index: int
    - sim_generator: generator
"""

import time
from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from src.db.models import Alert, Prediction, Transaction
from src.db.session import SessionLocal
from src.ml.data_loader import load_dataset
from src.ml.explain import get_explanation
from src.ml.inference import predict_transaction


BASE_DELAY_SECONDS = 1.0


def _to_python_value(value: Any) -> Any:
    """Convert NumPy and pandas scalar values to native Python values."""
    if isinstance(value, np.generic):
        return value.item()

    if value is pd.NA:
        return None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime()

    if isinstance(value, dict):
        return {
            str(key): _to_python_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [_to_python_value(item) for item in value]

    if isinstance(value, tuple):
        return tuple(_to_python_value(item) for item in value)

    return value


def _clean_transaction_dict(row: pd.Series) -> dict[str, Any]:
    """Convert a pandas row into a JSON-safe Python dictionary."""
    raw_dict = row.to_dict()

    return {
        str(key): _to_python_value(value)
        for key, value in raw_dict.items()
    }


def _normalize_prediction_value(value: Any) -> bool:
    """Convert model prediction output into a native Python boolean."""
    value = _to_python_value(value)

    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "fraud",
            "fraudulent",
            "suspicious",
        }

    return bool(value)


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a model output value into a native float."""
    value = _to_python_value(value)

    if value is None:
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int | None = None) -> int | None:
    """Convert a value into a native integer."""
    value = _to_python_value(value)

    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _init_simulation_state() -> None:
    """Initialize all required Streamlit session-state values."""
    defaults = {
        "sim_running": False,
        "sim_paused": False,
        "sim_speed": 1.0,
        "sim_index": 0,
        "sim_generator": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def start_simulation() -> None:
    """Initialize and start the simulation."""
    _init_simulation_state()

    if st.session_state["sim_running"]:
        st.warning("Simulation is already running.")
        return

    df = load_dataset()

    if df.empty:
        st.error("The transaction dataset is empty.")
        return

    st.session_state["sim_generator"] = (
        row for _, row in df.iterrows()
    )
    st.session_state["sim_index"] = 0
    st.session_state["sim_running"] = True
    st.session_state["sim_paused"] = False


def pause_simulation() -> None:
    """Pause the simulation."""
    if st.session_state.get("sim_running"):
        st.session_state["sim_paused"] = True


def resume_simulation() -> None:
    """Resume a paused simulation."""
    if st.session_state.get("sim_running"):
        st.session_state["sim_paused"] = False


def stop_simulation() -> None:
    """Stop and reset the simulation."""
    st.session_state["sim_running"] = False
    st.session_state["sim_paused"] = False
    st.session_state["sim_generator"] = None
    st.session_state["sim_index"] = 0


def set_speed(multiplier: float) -> None:
    """Set simulation speed between 0.1x and 5.0x."""
    st.session_state["sim_speed"] = max(
        0.1,
        min(float(multiplier), 5.0),
    )


def _process_next_row() -> bool:
    """Process and persist the next transaction.

    Returns:
        True when a row was processed.
        False when the generator is exhausted or unavailable.
    """
    generator = st.session_state.get("sim_generator")

    if generator is None:
        return False

    try:
        row = next(generator)
    except StopIteration:
        return False

    transaction_dict = _clean_transaction_dict(row)
    db = SessionLocal()

    try:
        transaction_record = Transaction(
            raw_data=transaction_dict,
        )

        db.add(transaction_record)
        db.flush()

        raw_prediction = predict_transaction(row)
        prediction_dict = _to_python_value(raw_prediction)

        fraud_probability = _safe_float(
            prediction_dict.get("fraud_probability"),
            0.0,
        )
        risk_score = _safe_float(
            prediction_dict.get("risk_score"),
            fraud_probability * 100.0,
        )
        confidence = _safe_float(
            prediction_dict.get("confidence"),
            max(fraud_probability, 1.0 - fraud_probability),
        )
        prediction_value = _normalize_prediction_value(
            prediction_dict.get("prediction", False)
        )
        fraud_category = str(
            prediction_dict.get("fraud_category", "Unknown")
        )

        explanation = get_explanation(
            transaction_dict,
            prediction_dict,
        )

        prediction_record = Prediction(
            user_id=_safe_int(
                st.session_state.get("user_id")
            ),
            transaction_id=int(transaction_record.id),
            fraud_probability=float(fraud_probability),
            risk_score=float(risk_score),
            prediction=bool(prediction_value),
            confidence=float(confidence),
            fraud_category=fraud_category,
            explanation=str(explanation),
        )

        db.add(prediction_record)
        db.flush()

        if risk_score >= 80.0:
            alert_record = Alert(
                user_id=_safe_int(
                    st.session_state.get("user_id")
                ),
                prediction_id=int(prediction_record.id),
                risk_score=float(risk_score),
                reason="High risk score",
            )

            db.add(alert_record)

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()

    st.session_state["sim_index"] += 1
    return True


def run_loop() -> None:
    """Process one transaction per Streamlit rerun."""
    if not st.session_state.get("sim_running", False):
        return

    if st.session_state.get("sim_paused", False):
        return

    speed = st.session_state.get("sim_speed", 1.0)
    delay = BASE_DELAY_SECONDS / max(float(speed), 0.1)

    processed = _process_next_row()

    if not processed:
        st.success("Simulation completed – no more transactions.")
        stop_simulation()
        return

    time.sleep(delay)

    rerun = getattr(st, "rerun", None)

    if callable(rerun):
        rerun()
    else:
        st.experimental_rerun()