# src/ui/pages/3_RealTimeMonitoring.py
"""Live transaction feed page.
Displays the most recent processed transactions in real time.
"""
import streamlit as st
from src.security.auth import require_auth
from src.db.session import SessionLocal
from src.db.models import Prediction, Transaction
import pandas as pd

def render():
    require_auth()
    st.title("📈 Real‑Time Monitoring")
    st.caption("Shows the latest processed transactions with predictions.")
    # Placeholder table – will be refreshed by simulation.run_loop which updates DB
    db = SessionLocal()
    try:
        recent = (
            db.query(Prediction, Transaction)
            .join(Transaction, Prediction.transaction_id == Transaction.id)
            .order_by(Prediction.created_at.desc())
            .limit(20)
            .all()
        )
        if recent:
            rows = []
            for pred, txn in recent:
                rows.append({
                    "time": pred.created_at,
                    "risk": pred.risk_score,
                    "prediction": "Fraud" if pred.prediction else "Legit",
                    "explanation": pred.explanation or "—",
                })
            df = pd.DataFrame(rows)
            st.dataframe(df)
        else:
            st.info("No transactions processed yet.")
    finally:
        db.close()
