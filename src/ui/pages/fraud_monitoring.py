"""
Combined Fraud Monitoring page for PayShield AI.

Provides:
1. Live Transaction Feed
2. Fraud Alert Center

Authentication, database queries, alert filtering, and stored data
remain unchanged. The page presentation is organized for easier review.
"""

import pandas as pd
import streamlit as st

from src.db.models import Alert, Prediction, Transaction
from src.db.session import SessionLocal
from src.logging.logger import get_logger
from src.security.auth import require_auth


logger = get_logger(__name__)


# ----------------------------------------------------------------------
# Real-time monitoring helpers
# ----------------------------------------------------------------------
def _load_recent_transactions(limit: int = 20):
    """Load the most recent processed transactions."""
    db = SessionLocal()

    try:
        return (
            db.query(Prediction, Transaction)
            .join(
                Transaction,
                Prediction.transaction_id == Transaction.id,
            )
            .order_by(Prediction.created_at.desc())
            .limit(limit)
            .all()
        )
    finally:
        db.close()


def _build_monitoring_dataframe(records):
    """Convert recent prediction records into a display DataFrame."""
    rows = []

    for prediction, transaction in records:
        rows.append(
            {
                "Time": prediction.created_at,
                "Transaction ID": transaction.id,
                "Risk Score": float(
                    prediction.risk_score or 0.0
                ),
                "Prediction": (
                    "Fraud"
                    if prediction.prediction
                    else "Legitimate"
                ),
                "Fraud Probability": float(
                    prediction.fraud_probability or 0.0
                ),
                "Category": (
                    prediction.fraud_category
                    or "Unknown"
                ),
                "AI Explanation": (
                    prediction.explanation
                    or "No explanation available."
                ),
            }
        )

    return pd.DataFrame(rows)


def _render_monitoring_metrics(dataframe):
    """Render summary metrics for the live transaction feed."""
    total_records = len(dataframe)

    fraud_count = int(
        (dataframe["Prediction"] == "Fraud").sum()
    )

    legitimate_count = total_records - fraud_count

    average_risk = (
        float(dataframe["Risk Score"].mean())
        if total_records
        else 0.0
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Transactions shown",
        f"{total_records:,}",
    )

    metric2.metric(
        "Fraud detected",
        f"{fraud_count:,}",
    )

    metric3.metric(
        "Legitimate",
        f"{legitimate_count:,}",
    )

    metric4.metric(
        "Average risk",
        f"{average_risk:.2f}",
    )


def _render_real_time_monitoring() -> None:
    """Render the Live Transaction Feed tab."""
    st.markdown("### 📈 Live Transaction Feed")

    st.caption(
        "Review the latest transactions processed by the "
        "PayShield AI fraud detection engine."
    )

    records = _load_recent_transactions(limit=20)

    if not records:
        st.info(
            "No transactions have been processed yet."
        )
        return

    dataframe = _build_monitoring_dataframe(records)

    _render_monitoring_metrics(dataframe)

    st.divider()

    st.markdown("#### Recent prediction activity")

    st.caption(
        "The table below shows the latest predictions, "
        "risk scores, classifications, and AI explanations."
    )

    display_dataframe = dataframe.copy()

    display_dataframe["Fraud Probability"] = (
        display_dataframe["Fraud Probability"]
        .map(lambda value: f"{value:.2%}")
    )

    display_dataframe["Risk Score"] = (
        display_dataframe["Risk Score"]
        .map(lambda value: f"{value:.2f}")
    )

    st.dataframe(
        display_dataframe,
        use_container_width=True,
        hide_index=True,
    )

    logger.info(
        "Rendered live monitoring feed with %d records",
        len(dataframe),
    )


# ----------------------------------------------------------------------
# Alerts helpers
# ----------------------------------------------------------------------
def _load_alerts(
    db,
    user_id: int | None,
    limit: int = 100,
):
    """Load recent alerts with predictions and transactions."""
    query = (
        db.query(
            Alert,
            Prediction,
            Transaction,
        )
        .join(
            Prediction,
            Alert.prediction_id == Prediction.id,
        )
        .join(
            Transaction,
            Prediction.transaction_id == Transaction.id,
        )
    )

    if user_id is not None:
        query = query.filter(
            Alert.user_id == user_id
        )

    return (
        query.order_by(Alert.created_at.desc())
        .limit(limit)
        .all()
    )


def _severity_label(risk_score: float) -> str:
    """Convert a risk score into a severity label."""
    if risk_score >= 90:
        return "Critical"

    if risk_score >= 80:
        return "High"

    if risk_score >= 60:
        return "Medium"

    return "Low"


def _build_alert_dataframe(records):
    """Build the alert summary DataFrame."""
    rows = []

    for alert, prediction, transaction in records:
        risk_score = float(
            alert.risk_score or 0.0
        )

        rows.append(
            {
                "Alert ID": alert.id,
                "Created At": alert.created_at,
                "Transaction ID": transaction.id,
                "Risk Score": risk_score,
                "Severity": _severity_label(
                    risk_score
                ),
                "Reason": (
                    alert.reason
                    or "High-risk transaction detected"
                ),
                "Fraud Probability": float(
                    prediction.fraud_probability or 0.0
                ),
                "Fraud Category": (
                    prediction.fraud_category
                    or "Unknown"
                ),
            }
        )

    return pd.DataFrame(rows)


def _render_alert_metrics(dataframe):
    """Render alert summary metrics."""
    total_alerts = len(dataframe)

    critical_alerts = int(
        (dataframe["Severity"] == "Critical").sum()
    )

    high_alerts = int(
        (dataframe["Severity"] == "High").sum()
    )

    average_risk = (
        float(dataframe["Risk Score"].mean())
        if total_alerts
        else 0.0
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Total alerts",
        f"{total_alerts:,}",
    )

    metric2.metric(
        "Critical",
        f"{critical_alerts:,}",
    )

    metric3.metric(
        "High",
        f"{high_alerts:,}",
    )

    metric4.metric(
        "Average risk",
        f"{average_risk:.2f}",
    )


def _render_alert_header(
    severity,
    risk_score,
    transaction_id,
):
    """Render a severity-based alert message."""
    message = (
        f"{severity} Alert | "
        f"Risk: {risk_score:.0f} | "
        f"Transaction ID: {transaction_id}"
    )

    if severity == "Critical":
        st.error(f"🚨 {message}")

    elif severity == "High":
        st.warning(f"⚠️ {message}")

    else:
        st.info(f"ℹ️ {message}")


def _filter_alert_records(
    records,
    severity_filter,
):
    """Filter alert records by selected severity."""
    if severity_filter == "All":
        return records

    filtered_records = []

    for alert, prediction, transaction in records:
        risk_score = float(
            alert.risk_score or 0.0
        )

        if _severity_label(risk_score) == severity_filter:
            filtered_records.append(
                (
                    alert,
                    prediction,
                    transaction,
                )
            )

    return filtered_records


def _format_alert_option(record):
    """Create a readable label for the alert selector."""
    alert, prediction, transaction = record

    risk_score = float(
        alert.risk_score or 0.0
    )

    severity = _severity_label(
        risk_score
    )

    created_at = (
        alert.created_at.strftime(
            "%Y-%m-%d %H:%M"
        )
        if alert.created_at
        else "Unknown time"
    )

    return (
        f"{severity} — "
        f"Transaction {transaction.id} — "
        f"Risk {risk_score:.0f} — "
        f"{created_at}"
    )


def _render_selected_alert(
    alert,
    prediction,
    transaction,
):
    """Render the selected alert investigation panel."""
    risk_score = float(
        alert.risk_score or 0.0
    )

    severity = _severity_label(
        risk_score
    )

    probability = float(
        prediction.fraud_probability or 0.0
    )

    confidence = float(
        prediction.confidence or 0.0
    )

    category = (
        prediction.fraud_category
        or "Unknown"
    )

    created_at = (
        alert.created_at.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        if alert.created_at
        else "Unknown"
    )

    reason = (
        alert.reason
        or "High-risk transaction detected"
    )

    explanation = (
        prediction.explanation
        or "No explanation available."
    )

    raw_data = (
        transaction.raw_data
        if isinstance(
            transaction.raw_data,
            dict,
        )
        else {}
    )

    _render_alert_header(
        severity,
        risk_score,
        transaction.id,
    )

    st.markdown("#### Alert overview")

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Risk score",
        f"{risk_score:.2f}",
    )

    metric2.metric(
        "Fraud probability",
        f"{probability:.2%}",
    )

    metric3.metric(
        "Confidence",
        f"{confidence:.2%}",
    )

    metric4.metric(
        "Fraud category",
        category,
    )

    st.divider()

    details_left, details_right = st.columns(2)

    with details_left:
        st.markdown("#### Investigation details")
        st.write(
            f"**Transaction ID:** {transaction.id}"
        )
        st.write(
            f"**Severity:** {severity}"
        )
        st.write(
            f"**Created at:** {created_at}"
        )
        st.write(
            f"**Reason:** {reason}"
        )

    with details_right:
        st.markdown("#### Prediction details")
        st.write(
            f"**Prediction:** "
            f"{'Fraud' if prediction.prediction else 'Legitimate'}"
        )
        st.write(
            f"**Risk score:** {risk_score:.2f}"
        )
        st.write(
            f"**Fraud probability:** {probability:.2%}"
        )
        st.write(
            f"**Category:** {category}"
        )

    st.divider()

    st.markdown("#### 🧠 AI explanation")
    st.info(explanation)

    st.markdown("#### 📋 Original transaction data")

    if raw_data:
        st.json(raw_data)
    else:
        st.info(
            "No raw transaction data is available."
        )


def _render_alerts() -> None:
    """Render the Fraud Alert Center tab."""
    st.markdown("### 🚨 Fraud Alert Center")

    st.caption(
        "Review generated fraud alerts, inspect risk scores, "
        "and investigate suspicious transactions."
    )

    db = SessionLocal()

    try:
        filter_column, limit_column = st.columns(2)

        with filter_column:
            severity_filter = st.selectbox(
                "Severity filter",
                options=[
                    "All",
                    "Critical",
                    "High",
                    "Medium",
                    "Low",
                ],
                index=0,
                key="fraud_monitoring_severity_filter",
            )

        with limit_column:
            limit = st.selectbox(
                "Number of alerts",
                options=[
                    10,
                    25,
                    50,
                    100,
                ],
                index=1,
                key="fraud_monitoring_alert_limit",
            )

        user_id = st.session_state.get(
            "user_id"
        )

        records = _load_alerts(
            db,
            user_id=user_id,
            limit=limit,
        )

        if not records:
            st.info(
                "No fraud alerts are available."
            )
            return

        alerts_dataframe = _build_alert_dataframe(
            records
        )

        _render_alert_metrics(
            alerts_dataframe
        )

        st.divider()

        with st.expander(
            "📋 View alert summary table",
            expanded=False,
        ):
            display_dataframe = (
                alerts_dataframe.copy()
            )

            display_dataframe["Risk Score"] = (
                display_dataframe["Risk Score"]
                .map(lambda value: f"{value:.2f}")
            )

            display_dataframe[
                "Fraud Probability"
            ] = (
                display_dataframe[
                    "Fraud Probability"
                ]
                .map(lambda value: f"{value:.2%}")
            )

            st.dataframe(
                display_dataframe,
                use_container_width=True,
                hide_index=True,
            )

        st.divider()

        st.markdown("### Alert Investigation")

        st.caption(
            "Select one alert to review its prediction, "
            "AI explanation, and original transaction data."
        )

        filtered_records = _filter_alert_records(
            records,
            severity_filter,
        )

        if not filtered_records:
            st.info(
                "No alerts match the selected severity."
            )
            return

        alert_labels = [
            _format_alert_option(record)
            for record in filtered_records
        ]

        selected_label = st.selectbox(
            "Select alert",
            options=alert_labels,
            key="fraud_monitoring_selected_alert",
        )

        selected_index = alert_labels.index(
            selected_label
        )

        selected_alert, selected_prediction, selected_transaction = (
            filtered_records[selected_index]
        )

        st.divider()

        _render_selected_alert(
            selected_alert,
            selected_prediction,
            selected_transaction,
        )

        logger.info(
            "Rendered Alerts tab with %d alerts",
            len(alerts_dataframe),
        )

    finally:
        db.close()


# ----------------------------------------------------------------------
# Public entry point
# ----------------------------------------------------------------------
def render() -> None:
    """Render the combined Fraud Monitoring page."""
    require_auth()

    st.title("🛡️ Fraud Monitoring Center")

    st.caption(
        "Track recent predictions, review high-risk activity, "
        "and investigate generated fraud alerts from one workspace."
    )

    monitor_tab, alerts_tab = st.tabs(
        [
            "📈 Live Transaction Feed",
            "🚨 Fraud Alert Center",
        ]
    )

    with monitor_tab:
        _render_real_time_monitoring()

    with alerts_tab:
        _render_alerts()