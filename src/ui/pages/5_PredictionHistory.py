# src/ui/pages/5_PredictionHistory.py
"""Prediction History page.
Shows a searchable, filterable table of past predictions with download capability.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from src.security.auth import require_auth
from src.db.session import SessionLocal
from src.db.models import Prediction, Transaction
from src.logging.logger import get_logger

logger = get_logger(__name__)

def _fetch_history(db, start_date=None, end_date=None, min_risk=None, max_risk=None, pred_type=None):
    query = db.query(Prediction, Transaction).join(Transaction, Prediction.transaction_id == Transaction.id)
    if start_date:
        query = query.filter(Prediction.created_at >= start_date)
    if end_date:
        query = query.filter(Prediction.created_at <= end_date)
    if min_risk is not None:
        query = query.filter(Prediction.risk_score >= min_risk)
    if max_risk is not None:
        query = query.filter(Prediction.risk_score <= max_risk)
    if pred_type == "Fraud":
        query = query.filter(Prediction.prediction.is_(True))
    elif pred_type == "Legit":
        query = query.filter(Prediction.prediction.is_(False))
    return query.all()

def render():
    require_auth()
    st.title("📜 Prediction History")
    st.caption("Filter and explore past model predictions.")

    db = SessionLocal()
    try:
        # Sidebar filters
        with st.sidebar:
            st.header("Filters")
            start = st.date_input("Start date", value=None)
            end = st.date_input("End date", value=None)
            min_risk = st.slider("Min risk score", 0, 100, 0)
            max_risk = st.slider("Max risk score", 0, 100, 100)
            pred_type = st.selectbox("Prediction type", ["All", "Fraud", "Legit"], index=0)

        start_dt = datetime.combine(start, datetime.min.time()) if start else None
        end_dt = datetime.combine(end, datetime.max.time()) if end else None
        min_risk_val = min_risk if min_risk != 0 else None
        max_risk_val = max_risk if max_risk != 100 else None
        pred_filter = None if pred_type == "All" else pred_type

        records = _fetch_history(
            db,
            start_date=start_dt,
            end_date=end_dt,
            min_risk=min_risk_val,
            max_risk=max_risk_val,
            pred_type=pred_filter,
        )

        rows = []
        for pred, txn in records:
            rows.append({
                "Timestamp": pred.created_at,
                "Risk Score": pred.risk_score,
                "Prediction": "Fraud" if pred.prediction else "Legit",
                "Probability": f"{pred.fraud_probability:.4%}",
                "Category": pred.fraud_category,
                "Explanation": pred.explanation or "—",
                "Transaction": txn.raw_data,
            })
        df = pd.DataFrame(rows)
        if not df.empty:
            st.dataframe(df, use_container_width=True)
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(label="Download CSV", data=csv, file_name="prediction_history.csv", mime="text/csv")
        else:
            st.info("No predictions match the selected filters.")
    finally:
        db.close()
        logger.info("Rendered Prediction History page")
