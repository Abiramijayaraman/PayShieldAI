# src/ui/pages/2_Dashboard.py
"""Dashboard page for PayShield AI.
Shows key KPIs and interactive Plotly charts.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
from src.security.auth import require_auth
from src.db.session import SessionLocal
from src.db.models import Transaction, Prediction, Alert

def _load_metrics(db):
    total_tx = db.query(Transaction).count()
    total_fraud = db.query(Prediction).filter(Prediction.prediction == True).count()
    total_legit = db.query(Prediction).filter(Prediction.prediction == False).count()
    fraud_pct = (total_fraud / total_tx * 100) if total_tx else 0
    avg_risk = db.query(Prediction.risk_score).filter(Prediction.prediction == True).order_by().all()
    avg_risk_score = sum([r[0] for r in avg_risk]) / len(avg_risk) if avg_risk else 0
    high_risk = db.query(Alert).count()
    return {
        "total_tx": total_tx,
        "total_fraud": total_fraud,
        "total_legit": total_legit,
        "fraud_pct": f"{fraud_pct:.2f}%",
        "avg_risk_score": f"{avg_risk_score:.2f}",
        "high_risk": high_risk,
    }

def _load_time_series(db):
    # Return hourly transaction count and fraud count for last 24h (if timestamp present)
    df = pd.read_sql_query(
        "SELECT p.created_at, p.prediction FROM predictions p",
        con=db.bind,
    )
    if df.empty:
        return None, None
    df["hour"] = pd.to_datetime(df["created_at"]).dt.floor("H")
    tx_by_hour = df.groupby("hour").size().reset_index(name="transactions")
    fraud_by_hour = df[df["prediction"]].groupby("hour").size().reset_index(name="frauds")
    return tx_by_hour, fraud_by_hour

def render():
    require_auth()
    st.title("📊 Dashboard")
    db = SessionLocal()
    try:
        metrics = _load_metrics(db)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(label="Total Transactions", value=metrics["total_tx"])
        with col2:
            st.metric(label="Fraud Transactions", value=metrics["total_fraud"])
        with col3:
            st.metric(label="Fraud %", value=metrics["fraud_pct"])
        col4, col5 = st.columns(2)
        with col4:
            st.metric(label="Avg Risk Score (Fraud)", value=metrics["avg_risk_score"])
        with col5:
            st.metric(label="High‑Risk Alerts", value=metrics["high_risk"])
        # Time series charts
        tx_hour, fraud_hour = _load_time_series(db)
        if tx_hour is not None:
            fig_tx = px.line(tx_hour, x="hour", y="transactions", title="Transactions per Hour")
            st.plotly_chart(fig_tx, use_container_width=True)
            fig_fraud = px.line(fraud_hour, x="hour", y="frauds", title="Fraud Transactions per Hour")
            st.plotly_chart(fig_fraud, use_container_width=True)
    finally:
        db.close()
