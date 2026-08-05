# src/ui/pages/reports_history.py
"""
Reports and Prediction History page for PayShield AI.

Features:
1. Prediction History
2. Report Generation

Authentication, database access, filtering, report generation,
and CSV export behavior are preserved.
"""

from datetime import datetime

import pandas as pd
import streamlit as st

from src.db.models import Prediction, Transaction
from src.db.session import SessionLocal
from src.logging.logger import get_logger
from src.security.auth import require_auth


logger = get_logger(__name__)


# ----------------------------------------------------------------------
# Prediction history helpers
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
        .join(
            Transaction,
            Prediction.transaction_id == Transaction.id,
        )
    )

    if start_date:
        query = query.filter(
            Prediction.created_at >= start_date
        )

    if end_date:
        query = query.filter(
            Prediction.created_at <= end_date
        )

    if min_risk is not None:
        query = query.filter(
            Prediction.risk_score >= min_risk
        )

    if max_risk is not None:
        query = query.filter(
            Prediction.risk_score <= max_risk
        )

    if pred_type == "Fraud":
        query = query.filter(
            Prediction.prediction.is_(True)
        )

    elif pred_type == "Legit":
        query = query.filter(
            Prediction.prediction.is_(False)
        )

    return (
        query.order_by(
            Prediction.created_at.desc()
        )
        .all()
    )


# ----------------------------------------------------------------------
# Report helpers
# ----------------------------------------------------------------------
def _safe_amount(raw_data: dict) -> float:
    """Extract a numeric transaction amount safely."""
    if not isinstance(raw_data, dict):
        return 0.0

    value = raw_data.get(
        "transaction_amount",
        0.0,
    )

    try:
        return float(value)

    except (TypeError, ValueError):
        return 0.0


def _safe_category(raw_data: dict) -> str:
    """Extract the merchant category safely."""
    if not isinstance(raw_data, dict):
        return "Unknown"

    value = raw_data.get(
        "merchant_category",
        "Unknown",
    )

    return (
        "Unknown"
        if value is None
        else str(value)
    )


def _fetch_report_data(
    db,
    start_date=None,
    end_date=None,
):
    """Fetch predictions and transaction data for reports."""
    query = (
        db.query(Prediction, Transaction)
        .join(
            Transaction,
            Prediction.transaction_id == Transaction.id,
        )
        .order_by(
            Prediction.created_at.desc()
        )
    )

    if start_date is not None:
        query = query.filter(
            Prediction.created_at >= start_date
        )

    if end_date is not None:
        query = query.filter(
            Prediction.created_at <= end_date
        )

    return query.all()


# ----------------------------------------------------------------------
# Filter helpers
# ----------------------------------------------------------------------
def _render_filters():
    """Render report and history filters."""
    st.markdown("### 🔎 Filters")

    st.caption(
        "Use the controls below to narrow prediction history "
        "and generated report data."
    )

    date_col_1, date_col_2 = st.columns(2)

    with date_col_1:
        start = st.date_input(
            "Start date",
            value=None,
            key="reports_start_date",
        )

    with date_col_2:
        end = st.date_input(
            "End date",
            value=None,
            key="reports_end_date",
        )

    risk_col_1, risk_col_2, type_col = st.columns(3)

    with risk_col_1:
        min_risk = st.slider(
            "Minimum risk score",
            min_value=0,
            max_value=100,
            value=0,
            key="reports_min_risk",
        )

    with risk_col_2:
        max_risk = st.slider(
            "Maximum risk score",
            min_value=0,
            max_value=100,
            value=100,
            key="reports_max_risk",
        )

    with type_col:
        prediction_type = st.selectbox(
            "Prediction type",
            options=[
                "All",
                "Fraud",
                "Legit",
            ],
            index=0,
            key="reports_prediction_type",
        )

    return (
        start,
        end,
        min_risk,
        max_risk,
        prediction_type,
    )


def _convert_filters(
    start,
    end,
    min_risk,
    max_risk,
    prediction_type,
):
    """Convert UI filter values into query parameters."""
    start_datetime = (
        datetime.combine(
            start,
            datetime.min.time(),
        )
        if start
        else None
    )

    end_datetime = (
        datetime.combine(
            end,
            datetime.max.time(),
        )
        if end
        else None
    )

    minimum_risk = (
        min_risk
        if min_risk != 0
        else None
    )

    maximum_risk = (
        max_risk
        if max_risk != 100
        else None
    )

    prediction_filter = (
        None
        if prediction_type == "All"
        else prediction_type
    )

    return (
        start_datetime,
        end_datetime,
        minimum_risk,
        maximum_risk,
        prediction_filter,
    )


# ----------------------------------------------------------------------
# Prediction history UI
# ----------------------------------------------------------------------
def _build_history_dataframe(records):
    """Build the prediction-history DataFrame."""
    rows = []

    for prediction, transaction in records:
        rows.append(
            {
                "Timestamp": prediction.created_at,
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
                "Explanation": (
                    prediction.explanation
                    or "No explanation available."
                ),
                "Transaction Data": transaction.raw_data,
            }
        )

    return pd.DataFrame(rows)


def _render_history_metrics(dataframe):
    """Render summary metrics for prediction history."""
    total_records = len(dataframe)

    fraud_records = int(
        (
            dataframe["Prediction"]
            == "Fraud"
        ).sum()
    )

    legitimate_records = (
        total_records - fraud_records
    )

    average_risk = (
        float(
            dataframe["Risk Score"].mean()
        )
        if total_records
        else 0.0
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "History records",
        f"{total_records:,}",
    )

    metric2.metric(
        "Fraud predictions",
        f"{fraud_records:,}",
    )

    metric3.metric(
        "Legitimate predictions",
        f"{legitimate_records:,}",
    )

    metric4.metric(
        "Average risk",
        f"{average_risk:.2f}",
    )


def _render_prediction_history(
    db,
    start_datetime,
    end_datetime,
    minimum_risk,
    maximum_risk,
    prediction_filter,
):
    """Render the Prediction History tab."""
    st.markdown("### 🔎 Prediction History")

    st.caption(
        "Review past fraud predictions, risk scores, "
        "probabilities, categories, and AI explanations."
    )

    records = _fetch_history(
        db,
        start_date=start_datetime,
        end_date=end_datetime,
        min_risk=minimum_risk,
        max_risk=maximum_risk,
        pred_type=prediction_filter,
    )

    dataframe = _build_history_dataframe(
        records
    )

    if dataframe.empty:
        st.info(
            "No predictions match the selected filters."
        )
        return

    _render_history_metrics(
        dataframe
    )

    st.divider()

    display_dataframe = dataframe.copy()

    display_dataframe[
        "Risk Score"
    ] = display_dataframe[
        "Risk Score"
    ].map(
        lambda value: f"{value:.2f}"
    )

    display_dataframe[
        "Fraud Probability"
    ] = display_dataframe[
        "Fraud Probability"
    ].map(
        lambda value: f"{value:.2%}"
    )

    with st.expander(
        "📋 View prediction history table",
        expanded=True,
    ):
        st.dataframe(
            display_dataframe,
            use_container_width=True,
            hide_index=True,
        )

    csv_history = dataframe.to_csv(
        index=False
    ).encode("utf-8")

    download_left, download_center, download_right = (
        st.columns([1, 2, 1])
    )

    with download_center:
        st.download_button(
            label="⬇️ Download Prediction History",
            data=csv_history,
            file_name="prediction_history.csv",
            mime="text/csv",
            key="download_prediction_history",
            use_container_width=True,
        )


# ----------------------------------------------------------------------
# Report UI
# ----------------------------------------------------------------------
def _build_report_dataframe(records):
    """Build the report DataFrame."""
    rows = []

    for prediction, transaction in records:
        raw_data = (
            transaction.raw_data
            if isinstance(
                transaction.raw_data,
                dict,
            )
            else {}
        )

        rows.append(
            {
                "Prediction ID": prediction.id,
                "Created At": prediction.created_at,
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
                "Confidence": float(
                    prediction.confidence or 0.0
                ),
                "Fraud Category": (
                    prediction.fraud_category
                    or "Unknown"
                ),
                "Explanation": (
                    prediction.explanation or ""
                ),
                "Transaction ID": transaction.id,
                "Transaction Timestamp": (
                    transaction.created_at
                ),
                "Amount": _safe_amount(
                    raw_data
                ),
                "Merchant Category": _safe_category(
                    raw_data
                ),
                "Raw Data": raw_data,
            }
        )

    return pd.DataFrame(rows)


def _render_report_metrics(dataframe):
    """Render report summary metrics."""
    total_records = len(dataframe)

    fraud_records = int(
        (
            dataframe["Prediction"]
            == "Fraud"
        ).sum()
    )

    legitimate_records = (
        total_records - fraud_records
    )

    average_risk = (
        float(
            dataframe["Risk Score"].mean()
        )
        if total_records
        else 0.0
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Report rows",
        f"{total_records:,}",
    )

    metric2.metric(
        "Fraud records",
        f"{fraud_records:,}",
    )

    metric3.metric(
        "Legitimate records",
        f"{legitimate_records:,}",
    )

    metric4.metric(
        "Average risk",
        f"{average_risk:.2f}",
    )


def _render_report_generation(
    db,
    start_datetime,
    end_datetime,
):
    """Render the Report Generation tab."""
    st.markdown("### 📄 Generate Report")

    st.caption(
        "Generate a detailed CSV report containing predictions, "
        "risk scores, probabilities, and transaction information."
    )

    records = _fetch_report_data(
        db,
        start_date=start_datetime,
        end_date=end_datetime,
    )

    dataframe = _build_report_dataframe(
        records
    )

    if dataframe.empty:
        st.info(
            "No data is available for the selected period."
        )
        return

    _render_report_metrics(
        dataframe
    )

    st.divider()

    display_dataframe = dataframe.copy()

    display_dataframe[
        "Risk Score"
    ] = display_dataframe[
        "Risk Score"
    ].map(
        lambda value: f"{value:.2f}"
    )

    display_dataframe[
        "Fraud Probability"
    ] = display_dataframe[
        "Fraud Probability"
    ].map(
        lambda value: f"{value:.2%}"
    )

    display_dataframe[
        "Confidence"
    ] = display_dataframe[
        "Confidence"
    ].map(
        lambda value: f"{value:.2%}"
    )

    display_dataframe[
        "Amount"
    ] = display_dataframe[
        "Amount"
    ].map(
        lambda value: f"{value:,.2f}"
    )

    with st.expander(
        "📋 Preview generated report",
        expanded=True,
    ):
        st.dataframe(
            display_dataframe,
            use_container_width=True,
            hide_index=True,
        )

    csv_report = dataframe.to_csv(
        index=False
    ).encode("utf-8")

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    download_left, download_center, download_right = (
        st.columns([1, 2, 1])
    )

    with download_center:
        st.download_button(
            label="⬇️ Download CSV Report",
            data=csv_report,
            file_name=(
                f"payshield_report_{timestamp}.csv"
            ),
            mime="text/csv",
            key="download_generated_report",
            use_container_width=True,
        )

    st.success(
        "Report generated successfully."
    )


# ----------------------------------------------------------------------
# Main page
# ----------------------------------------------------------------------
def render() -> None:
    """Render the Reports and Prediction History page."""
    require_auth()

    st.title(
        "📊 Reports & Prediction History"
    )

    st.caption(
        "Review past fraud predictions, apply filters, "
        "generate detailed reports, and export data as CSV."
    )

    with st.expander(
        "⚙️ Report filters",
        expanded=False,
    ):
        (
            start,
            end,
            min_risk,
            max_risk,
            prediction_type,
        ) = _render_filters()

    if start and end and start > end:
        st.error(
            "Start date cannot be after end date."
        )
        return

    if min_risk > max_risk:
        st.error(
            "Minimum risk score cannot be greater "
            "than maximum risk score."
        )
        return

    (
        start_datetime,
        end_datetime,
        minimum_risk,
        maximum_risk,
        prediction_filter,
    ) = _convert_filters(
        start,
        end,
        min_risk,
        max_risk,
        prediction_type,
    )

    history_tab, report_tab = st.tabs(
        [
            "🔎 Prediction History",
            "📄 Report Generator",
        ]
    )

    db = SessionLocal()

    try:
        with history_tab:
            _render_prediction_history(
                db,
                start_datetime,
                end_datetime,
                minimum_risk,
                maximum_risk,
                prediction_filter,
            )

        with report_tab:
            _render_report_generation(
                db,
                start_datetime,
                end_datetime,
            )

        logger.info(
            "Rendered Reports & History page "
            "(filters: %s - %s)",
            start_datetime,
            end_datetime,
        )

    finally:
        db.close()