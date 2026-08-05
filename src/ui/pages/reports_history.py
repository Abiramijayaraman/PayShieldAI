# src/ui/pages/reports_history.py
"""
Combined Report & Prediction History page.

Features:
1️⃣ Prediction History – searchable, filterable table of past predictions with
   download capability.
2️⃣ Reports – date‑range filtering, summary metrics, and CSV export for both
   predictions and their underlying transactions.

All authentication, database access, and logging are retained from the original
pages.
"""

import pandas as pd
import streamlit as st
from datetime import datetime

from src.security.auth import require_auth
from src.db.session import SessionLocal
from src.db.models import Prediction, Transaction, Alert
from src.logging.logger import get_logger

logger = get_logger(__name__)


# ----------------------------------------------------------------------
# Helpers – Prediction History (from 5_PredictionHistory.py)
# ----------------------------------------------------------------------
def _fetch_history(
    db,
    start_date=None,
    end_date=None,
    min_risk=None,
    max_risk=None,
    pred_type=None,
):
    """Retrieve past predictions with optional filtering."""
    query = (
        db.query(Prediction, Transaction)
        .join(Transaction, Prediction.transaction_id == Transaction.id)
    )
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


# ----------------------------------------------------------------------
# Helpers – Report Generation (from 7_Reports.py)
# ----------------------------------------------------------------------
def _safe_amount(raw_data: dict) -> float:
    """Extract a numeric transaction amount safely."""
    if not isinstance(raw_data, dict):
        return 0.0
    value = raw_data.get("transaction_amount", 0.0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_category(raw_data: dict) -> str:
    """Extract the merchant category safely."""
    if not isinstance(raw_data, dict):
        return "Unknown"
    value = raw_data.get("merchant_category", "Unknown")
    return "Unknown" if value is None else str(value)


def _fetch_report_data(db, start_date=None, end_date=None):
    """Fetch predictions together with transaction data for report generation."""
    query = (
        db.query(Prediction, Transaction)
        .join(Transaction, Prediction.transaction_id == Transaction.id)
        .order_by(Prediction.created_at.desc())
    )
    if start_date is not None:
        query = query.filter(Prediction.created_at >= start_date)
    if end_date is not None:
        query = query.filter(Prediction.created_at <= end_date)
    return query.all()


# ----------------------------------------------------------------------
# UI Rendering
# ----------------------------------------------------------------------
def render() -> None:
    """Render the unified Reports & History page."""
    require_auth()
    st.title("📊 Reports & Prediction History")
    st.caption(
        "Explore past predictions, generate CSV reports, and download data."
    )

    # --------------------------------------------------------------
    # Sidebar – Shared filters
    # --------------------------------------------------------------
    with st.sidebar:
        st.header("Filters")
        start = st.date_input("Start date", value=None)
        end = st.date_input("End date", value=None)
        min_risk = st.slider("Min risk score", 0, 100, 0)
        max_risk = st.slider("Max risk score", 0, 100, 100)
        pred_type = st.selectbox(
            "Prediction type", ["All", "Fraud", "Legit"], index=0
        )

    # Convert sidebar inputs to query parameters
    start_dt = (
        datetime.combine(start, datetime.min.time())
        if start
        else None
    )
    end_dt = (
        datetime.combine(end, datetime.max.time())
        if end
        else None
    )
    min_risk_val = min_risk if min_risk != 0 else None
    max_risk_val = max_risk if max_risk != 100 else None
    pred_filter = None if pred_type == "All" else pred_type

    db = SessionLocal()
    try:
        # --------------------------------------------------------------
        # Section 1 – Prediction History
        # --------------------------------------------------------------
        st.subheader("🔎 Prediction History")
        history_records = _fetch_history(
            db,
            start_date=start_dt,
            end_date=end_dt,
            min_risk=min_risk_val,
            max_risk=max_risk_val,
            pred_type=pred_filter,
        )

        history_rows = []
        for pred, txn in history_records:
            history_rows.append(
                {
                    "Timestamp": pred.created_at,
                    "Risk Score": pred.risk_score,
                    "Prediction": "Fraud" if pred.prediction else "Legit",
                    "Probability": f"{pred.fraud_probability:.4%}",
                    "Category": pred.fraud_category or "—",
                    "Explanation": pred.explanation or "—",
                    "Transaction ID": txn.id,
                    "Transaction Data": txn.raw_data,
                }
            )
        df_history = pd.DataFrame(history_rows)

        if not df_history.empty:
            st.dataframe(df_history, use_container_width=True)
            csv_hist = df_history.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Download Prediction History CSV",
                data=csv_hist,
                file_name="prediction_history.csv",
                mime="text/csv",
            )
        else:
            st.info("No predictions match the selected filters.")

        # --------------------------------------------------------------
        # Section 2 – Reports
        # --------------------------------------------------------------
        st.subheader("📄 Generate Report")
        # Validate date range
        if start and end and start > end:
            st.error("Start date cannot be after end date.")
            return

        report_records = _fetch_report_data(
            db,
            start_date=start_dt,
            end_date=end_dt,
        )

        report_rows = []
        for pred, txn in report_records:
            raw = txn.raw_data if isinstance(txn.raw_data, dict) else {}
            report_rows.append(
                {
                    "prediction_id": pred.id,
                    "created_at": pred.created_at,
                    "risk_score": float(pred.risk_score or 0.0),
                    "prediction": "Fraud" if pred.prediction else "Legit",
                    "fraud_probability": float(pred.fraud_probability or 0.0),
                    "confidence": float(pred.confidence or 0.0),
                    "fraud_category": pred.fraud_category or "Unknown",
                    "explanation": pred.explanation or "",
                    "transaction_id": txn.id,
                    "transaction_timestamp": txn.created_at,
                    "amount": _safe_amount(raw),
                    "category": _safe_category(raw),
                    "raw_data": raw,
                }
            )
        df_report = pd.DataFrame(report_rows)

        if df_report.empty:
            st.info("No data available for the selected period.")
        else:
            # Summary metrics
            total = len(df_report)
            fraud_cnt = int((df_report["prediction"] == "Fraud").sum())
            avg_risk = float(df_report["risk_score"].mean())

            col1, col2, col3 = st.columns(3)
            col1.metric("Report Rows", f"{total:,}")
            col2.metric("Fraud Records", f"{fraud_cnt:,}")
            col3.metric("Average Risk Score", f"{avg_risk:.2f}")

            st.dataframe(df_report, use_container_width=True)

            csv_report = df_report.to_csv(index=False).encode("utf-8")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label="Download CSV Report",
                data=csv_report,
                file_name=f"payshield_report_{timestamp}.csv",
                mime="text/csv",
            )
            st.success("Report generated successfully.")

        logger.info(
            "Rendered Reports & History page (filters: %s – %s)",
            start_dt,
            end_dt,
        )
    finally:
        db.close()