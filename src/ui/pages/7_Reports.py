# src/ui/pages/7_Reports.py
"""Reports page.

Generates and downloads CSV reports for predictions and transactions.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from src.db.models import Prediction, Transaction
from src.db.session import SessionLocal
from src.logging.logger import get_logger
from src.security.auth import require_auth


logger = get_logger(__name__)


def _fetch_data(db, start_date=None, end_date=None):
    """Fetch prediction and transaction records for an optional date range."""
    query = (
        db.query(Prediction, Transaction)
        .join(
            Transaction,
            Prediction.transaction_id == Transaction.id,
        )
        .order_by(Prediction.created_at.desc())
    )

    if start_date is not None:
        query = query.filter(Prediction.created_at >= start_date)

    if end_date is not None:
        query = query.filter(Prediction.created_at <= end_date)

    return query.all()


def _safe_amount(raw_data: dict) -> float:
    """Safely extract the transaction amount."""
    if not isinstance(raw_data, dict):
        return 0.0

    value = raw_data.get("transaction_amount", 0.0)

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_category(raw_data: dict) -> str:
    """Safely extract the merchant category."""
    if not isinstance(raw_data, dict):
        return "Unknown"

    value = raw_data.get("merchant_category", "Unknown")

    if value is None:
        return "Unknown"

    return str(value)


def render():
    """Render the Reports page."""
    require_auth()

    st.title("📄 Reports")
    st.caption(
        "Generate CSV reports for model predictions and transaction data."
    )

    db = SessionLocal()

    try:
        with st.sidebar:
            st.header("Date Range")

            start = st.date_input(
                "Start date",
                value=None,
            )

            end = st.date_input(
                "End date",
                value=None,
            )

        if start and end and start > end:
            st.error("Start date cannot be after end date.")
            return

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

        records = _fetch_data(
            db,
            start_date=start_dt,
            end_date=end_dt,
        )

        rows = []

        for pred, txn in records:
            raw_data = (
                txn.raw_data
                if isinstance(txn.raw_data, dict)
                else {}
            )

            rows.append(
                {
                    "prediction_id": pred.id,
                    "created_at": pred.created_at,
                    "risk_score": float(pred.risk_score or 0.0),
                    "prediction": (
                        "Fraud" if pred.prediction else "Legit"
                    ),
                    "fraud_probability": float(
                        pred.fraud_probability or 0.0
                    ),
                    "confidence": float(pred.confidence or 0.0),
                    "fraud_category": (
                        pred.fraud_category or "Unknown"
                    ),
                    "explanation": pred.explanation or "",
                    "transaction_id": txn.id,
                    "transaction_timestamp": txn.created_at,
                    "amount": _safe_amount(raw_data),
                    "category": _safe_category(raw_data),
                    "raw_data": raw_data,
                }
            )

        df = pd.DataFrame(rows)

        if df.empty:
            st.info("No data available for the selected period.")
            return

        total_records = len(df)
        fraud_records = int(
            (df["prediction"] == "Fraud").sum()
        )
        average_risk = float(df["risk_score"].mean())

        metric_col1, metric_col2, metric_col3 = st.columns(3)

        metric_col1.metric(
            "Report Rows",
            f"{total_records:,}",
        )

        metric_col2.metric(
            "Fraud Records",
            f"{fraud_records:,}",
        )

        metric_col3.metric(
            "Average Risk Score",
            f"{average_risk:.2f}",
        )

        st.dataframe(
            df,
            use_container_width=True,
        )

        csv_data = df.to_csv(index=False).encode("utf-8")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        st.download_button(
            label="Download CSV Report",
            data=csv_data,
            file_name=f"payshield_report_{timestamp}.csv",
            mime="text/csv",
        )

        st.success("Report generated successfully.")

        logger.info(
            "User generated a CSV report with %d rows",
            len(df),
        )

    finally:
        db.close()