"""Dashboard & Analytics page for PayShield AI.

Combines the KPI view from the original dashboard with the
interactive analytics visualisations.
"""

import pandas as pd
# pyrefly: ignore [missing-import]
import plotly.express as px
import altair as alt
from datetime import datetime, timedelta

import streamlit as st

from src.security.auth import require_auth
from src.db.session import SessionLocal
from src.db.models import Transaction, Prediction, Alert
from src.logging.logger import get_logger

logger = get_logger(__name__)


# ----------------------------------------------------------------------
# KPI helpers (from 2_Dashboard.py)
# ----------------------------------------------------------------------
def _load_metrics(db):
    """Collect high‑level counters used for the KPI cards."""
    total_tx = db.query(Transaction).count()
    total_fraud = db.query(Prediction).filter(Prediction.prediction.is_(True)).count()
    total_legit = db.query(Prediction).filter(Prediction.prediction.is_(False)).count()
    fraud_pct = (total_fraud / total_tx * 100) if total_tx else 0

    # average risk of fraudulent predictions
    avg_risk_vals = (
        db.query(Prediction.risk_score)
        .filter(Prediction.prediction.is_(True))
        .all()
    )
    avg_risk_score = (
        sum(v[0] for v in avg_risk_vals) / len(avg_risk_vals)
        if avg_risk_vals else 0
    )
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
    """Hourly transaction / fraud count for the last 24 h (used by the dashboard)."""
    df = pd.read_sql_query(
        "SELECT created_at, prediction FROM predictions",
        con=db.bind,
    )
    if df.empty:
        return None, None

    df["hour"] = pd.to_datetime(df["created_at"]).dt.floor("H")
    tx_by_hour = (
        df.groupby("hour")
        .size()
        .reset_index(name="transactions")
    )
    fraud_by_hour = (
        df[df["prediction"]]
        .groupby("hour")
        .size()
        .reset_index(name="frauds")
    )
    return tx_by_hour, fraud_by_hour


# ----------------------------------------------------------------------
# Analytics helpers (from 6_Analytics.py)
# ----------------------------------------------------------------------
def _load_data(db, days: int = 30):
    """Load predictions and linked transactions for the given time window."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(Prediction, Transaction)
        .join(Transaction, Prediction.transaction_id == Transaction.id)
        .filter(Prediction.created_at >= cutoff)
        .order_by(Prediction.created_at.asc())
        .all()
    )


def _safe_amount(raw_data: dict) -> float:
    """Extract a numeric transaction amount safely."""
    if not isinstance(raw_data, dict):
        return 0.0
    try:
        return float(raw_data.get("transaction_amount", 0.0))
    except (TypeError, ValueError):
        return 0.0


def _safe_category(raw_data: dict) -> str:
    """Extract a merchant category safely."""
    if not isinstance(raw_data, dict):
        return "Unknown"
    cat = raw_data.get("merchant_category")
    return str(cat) if cat else "Unknown"


# ----------------------------------------------------------------------
# Render function
# ----------------------------------------------------------------------
def render():
    """Render the combined Dashboard & Analytics page."""
    require_auth()
    st.title("📊 Dashboard & Analytics")
    db = SessionLocal()

    try:
        # --------------------------------------------------------------
        # KPI cards
        # --------------------------------------------------------------
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

        # --------------------------------------------------------------
        # Time‑series charts (Dashboard)
        # --------------------------------------------------------------
        tx_hour, fraud_hour = _load_time_series(db)
        if tx_hour is not None:
            fig_tx = px.line(
                tx_hour,
                x="hour",
                y="transactions",
                title="Transactions per Hour (last 24 h)",
            )
            st.plotly_chart(fig_tx, use_container_width=True)

            fig_fraud = px.line(
                fraud_hour,
                x="hour",
                y="frauds",
                title="Fraud Transactions per Hour (last 24 h)",
            )
            st.plotly_chart(fig_fraud, use_container_width=True)

        st.divider()

        # --------------------------------------------------------------
        # Analytics section
        # --------------------------------------------------------------
        st.subheader("Analytics")
        days = st.slider(
            "Days back",
            min_value=7,
            max_value=180,
            value=30,
            help="Select the time window for the analytics view.",
        )

        records = _load_data(db, days=days)

        if not records:
            st.info("No data available for the selected period.")
            return

        # Build DataFrames
        df_pred = pd.DataFrame(
            [
                {
                    "timestamp": pred.created_at,
                    "risk_score": float(pred.risk_score or 0.0),
                    "prediction": bool(pred.prediction),
                    "fraud_prob": float(pred.fraud_probability or 0.0),
                }
                for pred, _ in records
            ]
        )
        df_txn = pd.DataFrame(
            [
                {
                    "timestamp": txn.created_at,
                    "amount": _safe_amount(txn.raw_data),
                    "category": _safe_category(txn.raw_data),
                }
                for _, txn in records
            ]
        )
        # Normalise timestamps
        df_pred["timestamp"] = pd.to_datetime(df_pred["timestamp"], errors="coerce")
        df_txn["timestamp"] = pd.to_datetime(df_txn["timestamp"], errors="coerce")
        df_pred.dropna(subset=["timestamp"], inplace=True)
        df_txn.dropna(subset=["timestamp"], inplace=True)

        if df_pred.empty:
            st.info("No valid prediction timestamps are available.")
            return

        # --------------------------------------------------------------
        # Summary metrics (Analytics)
        # --------------------------------------------------------------
        total_transactions = len(df_pred)
        fraud_transactions = int(df_pred["prediction"].sum())
        fraud_rate = (
            fraud_transactions / total_transactions * 100
            if total_transactions
            else 0.0
        )
        avg_risk = float(df_pred["risk_score"].mean())

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Transactions", f"{total_transactions:,}")
        c2.metric("Fraud Predictions", f"{fraud_transactions:,}")
        c3.metric("Fraud Rate", f"{fraud_rate:.2f}%")
        c4.metric("Average Risk Score", f"{avg_risk:.2f}")

        # --------------------------------------------------------------
        # Risk Score Distribution
        # --------------------------------------------------------------
        st.subheader("Risk Score Distribution")
        risk_chart = (
            alt.Chart(df_pred)
            .mark_bar()
            .encode(
                x=alt.X(
                    "risk_score:Q",
                    bin=alt.Bin(maxbins=30),
                    title="Risk Score",
                ),
                y=alt.Y("count():Q", title="Transactions"),
                tooltip=[
                    alt.Tooltip("risk_score:Q", bin=True, title="Risk Score range"),
                    alt.Tooltip("count():Q", title="Count"),
                ],
            )
            .interactive()
        )
        st.altair_chart(risk_chart, use_container_width=True)

        # --------------------------------------------------------------
        # Fraud vs Legit timeline + risk line
        # --------------------------------------------------------------
        st.subheader("Fraud vs Legit Across Processed Transactions")
        timeline = df_pred.copy()
        timeline["transaction_number"] = range(1, len(timeline) + 1)
        timeline["prediction_label"] = timeline["prediction"].map({True: "Fraud", False: "Legit"})
        timeline["prediction_value"] = timeline["prediction"].astype(int)

        scatter = (
            alt.Chart(timeline)
            .mark_circle(size=90)
            .encode(
                x=alt.X("transaction_number:Q", title="Processed Transaction #"),
                y=alt.Y(
                    "prediction_value:Q",
                    title="Prediction",
                    scale=alt.Scale(domain=[-0.2, 1.2]),
                    axis=alt.Axis(
                        values=[0, 1],
                        labelExpr="datum.value == 1 ? 'Fraud' : 'Legit'",
                    ),
                ),
                color=alt.Color("prediction_label:N", title="Prediction"),
                tooltip=[
                    alt.Tooltip("transaction_number:Q", title="Transaction #"),
                    alt.Tooltip("timestamp:T", title="Processed At"),
                    alt.Tooltip("prediction_label:N", title="Prediction"),
                    alt.Tooltip("risk_score:Q", title="Risk Score", format=".2f"),
                    alt.Tooltip("fraud_prob:Q", title="Fraud Probability", format=".2%"),
                ],
            )
            .interactive()
        )
        risk_line = (
            alt.Chart(timeline)
            .mark_line(opacity=0.35)
            .encode(
                x=alt.X("transaction_number:Q", title="Processed Transaction #"),
                y=alt.Y("risk_score:Q", title="Risk Score", scale=alt.Scale(domain=[0, 100])),
            )
        )
        st.altair_chart(scatter & risk_line, use_container_width=True)

        # --------------------------------------------------------------
        # Transaction Amount Histogram
        # --------------------------------------------------------------
        st.subheader("Transaction Amounts")
        if df_txn.empty:
            st.info("No transaction amount data available.")
        else:
            amount_chart = (
                alt.Chart(df_txn)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "amount:Q",
                        bin=alt.Bin(maxbins=30),
                        title="Transaction Amount",
                    ),
                    y=alt.Y("count():Q", title="Transactions"),
                    tooltip=[
                        alt.Tooltip("amount:Q", bin=True, title="Amount range"),
                        alt.Tooltip("count():Q", title="Count"),
                    ],
                )
                .interactive()
            )
            st.altair_chart(amount_chart, use_container_width=True)

        # --------------------------------------------------------------
        # Merchant Category Distribution
        # --------------------------------------------------------------
        st.subheader("Merchant Categories")
        category_counts = (
            df_txn["category"]
            .value_counts()
            .head(10)
            .rename_axis("category")
            .reset_index(name="count")
        )
        if category_counts.empty:
            st.info("No merchant category data available.")
        else:
            cat_chart = (
                alt.Chart(category_counts)
                .mark_bar()
                .encode(
                    y=alt.Y("category:N", sort="-x", title="Category"),
                    x=alt.X("count:Q", title="Transactions"),
                    tooltip=[alt.Tooltip("category:N"), alt.Tooltip("count:Q")],
                )
            )
            st.altair_chart(cat_chart, use_container_width=True)

        logger.info("Rendered merged Dashboard & Analytics page for %d days", days)

    finally:
        db.close()
