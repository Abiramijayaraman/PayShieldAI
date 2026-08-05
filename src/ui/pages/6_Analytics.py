# src/ui/pages/6_Analytics.py
"""Analytics page.

Provides visual analytics for:
- Risk score distribution
- Fraud vs legitimate predictions over processed transactions
- Transaction amount distribution
- Merchant category distribution
"""

from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from src.db.models import Prediction, Transaction
from src.db.session import SessionLocal
from src.logging.logger import get_logger
from src.security.auth import require_auth


logger = get_logger(__name__)


def _load_data(db, days: int = 30):
    """Load predictions and their related transactions."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    return (
        db.query(Prediction, Transaction)
        .join(
            Transaction,
            Prediction.transaction_id == Transaction.id,
        )
        .filter(Prediction.created_at >= cutoff)
        .order_by(Prediction.created_at.asc())
        .all()
    )


def _safe_amount(raw_data: dict) -> float:
    """Safely extract transaction amount from raw transaction data."""
    if not isinstance(raw_data, dict):
        return 0.0

    value = raw_data.get("transaction_amount", 0.0)

    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_category(raw_data: dict) -> str:
    """Safely extract merchant category."""
    if not isinstance(raw_data, dict):
        return "Unknown"

    value = raw_data.get("merchant_category", "Unknown")

    if value is None:
        return "Unknown"

    return str(value)


def render():
    """Render the Analytics page."""
    require_auth()

    st.title("📊 Analytics")
    st.caption("Explore transaction trends and model performance.")

    db = SessionLocal()

    try:
        days = st.slider(
            "Days back",
            min_value=7,
            max_value=180,
            value=30,
        )

        records = _load_data(db, days=days)

        if not records:
            st.info("No data available for the selected period.")
            return

        df_pred = pd.DataFrame(
            [
                {
                    "timestamp": pred.created_at,
                    "risk_score": float(pred.risk_score or 0.0),
                    "prediction": bool(pred.prediction),
                    "fraud_prob": float(
                        pred.fraud_probability or 0.0
                    ),
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

        df_pred["timestamp"] = pd.to_datetime(
            df_pred["timestamp"],
            errors="coerce",
        )

        df_txn["timestamp"] = pd.to_datetime(
            df_txn["timestamp"],
            errors="coerce",
        )

        df_pred = df_pred.dropna(subset=["timestamp"])
        df_txn = df_txn.dropna(subset=["timestamp"])

        if df_pred.empty:
            st.info("No valid prediction timestamps are available.")
            return

        # Summary metrics
        total_transactions = len(df_pred)
        fraud_transactions = int(df_pred["prediction"].sum())

        fraud_percentage = (
            fraud_transactions / total_transactions * 100
            if total_transactions
            else 0.0
        )

        average_risk = float(df_pred["risk_score"].mean())

        metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)

        metric_col1.metric(
            "Transactions",
            f"{total_transactions:,}",
        )

        metric_col2.metric(
            "Fraud Predictions",
            f"{fraud_transactions:,}",
        )

        metric_col3.metric(
            "Fraud Rate",
            f"{fraud_percentage:.2f}%",
        )

        metric_col4.metric(
            "Average Risk Score",
            f"{average_risk:.2f}",
        )

        # Risk score distribution
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
                y=alt.Y(
                    "count():Q",
                    title="Transactions",
                ),
                tooltip=[
                    alt.Tooltip(
                        "risk_score:Q",
                        bin=True,
                        title="Risk Score Range",
                    ),
                    alt.Tooltip(
                        "count():Q",
                        title="Transactions",
                    ),
                ],
            )
            .interactive()
        )

        st.altair_chart(
            risk_chart,
            use_container_width=True,
        )

        # Fraud vs Legit over processed transactions
        st.subheader("Fraud vs Legit Across Processed Transactions")

        timeline = df_pred.copy()

        timeline["transaction_number"] = range(
            1,
            len(timeline) + 1,
        )

        timeline["prediction_label"] = timeline["prediction"].map(
            {
                True: "Fraud",
                False: "Legit",
            }
        )

        timeline["prediction_value"] = timeline["prediction"].map(
            {
                True: 1,
                False: 0,
            }
        )

        transaction_chart = (
            alt.Chart(timeline)
            .mark_circle(size=90)
            .encode(
                x=alt.X(
                    "transaction_number:Q",
                    title="Processed Transaction Number",
                ),
                y=alt.Y(
                    "prediction_value:Q",
                    title="Prediction",
                    scale=alt.Scale(
                        domain=[-0.2, 1.2],
                    ),
                    axis=alt.Axis(
                        values=[0, 1],
                        labelExpr=(
                            "datum.value == 1 ? 'Fraud' : 'Legit'"
                        ),
                    ),
                ),
                color=alt.Color(
                    "prediction_label:N",
                    title="Prediction",
                ),
                tooltip=[
                    alt.Tooltip(
                        "transaction_number:Q",
                        title="Transaction Number",
                    ),
                    alt.Tooltip(
                        "timestamp:T",
                        title="Processed At",
                    ),
                    alt.Tooltip(
                        "prediction_label:N",
                        title="Prediction",
                    ),
                    alt.Tooltip(
                        "risk_score:Q",
                        title="Risk Score",
                        format=".2f",
                    ),
                    alt.Tooltip(
                        "fraud_prob:Q",
                        title="Fraud Probability",
                        format=".2%",
                    ),
                ],
            )
            .interactive()
        )

        risk_line = (
            alt.Chart(timeline)
            .mark_line(opacity=0.35)
            .encode(
                x=alt.X(
                    "transaction_number:Q",
                    title="Processed Transaction Number",
                ),
                y=alt.Y(
                    "risk_score:Q",
                    title="Risk Score",
                    scale=alt.Scale(
                        domain=[0, 100],
                    ),
                ),
            )
        )

        st.altair_chart(
            transaction_chart,
            use_container_width=True,
        )

        st.subheader("Risk Score Trend")

        st.altair_chart(
            risk_line,
            use_container_width=True,
        )

        # Transaction amount histogram
        st.subheader("Transaction Amounts")

        if df_txn.empty:
            st.info("No valid transaction amounts are available.")
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
                    y=alt.Y(
                        "count():Q",
                        title="Transactions",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "amount:Q",
                            bin=True,
                            title="Amount Range",
                        ),
                        alt.Tooltip(
                            "count():Q",
                            title="Transactions",
                        ),
                    ],
                )
                .interactive()
            )

            st.altair_chart(
                amount_chart,
                use_container_width=True,
            )

        # Merchant category distribution
        st.subheader("Merchant Categories")

        category_counts = (
            df_txn["category"]
            .value_counts()
            .head(10)
            .rename_axis("category")
            .reset_index(name="count")
        )

        if category_counts.empty:
            st.info("No merchant category data is available.")
        else:
            category_chart = (
                alt.Chart(category_counts)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "count:Q",
                        title="Transactions",
                    ),
                    y=alt.Y(
                        "category:N",
                        sort="-x",
                        title="Merchant Category",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "category:N",
                            title="Category",
                        ),
                        alt.Tooltip(
                            "count:Q",
                            title="Transactions",
                        ),
                    ],
                )
            )

            st.altair_chart(
                category_chart,
                use_container_width=True,
            )

        logger.info(
            "Rendered Analytics page with %d days of data",
            days,
        )

    finally:
        db.close()