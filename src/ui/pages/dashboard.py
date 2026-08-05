"""
Dashboard & Analytics page for PayShield AI.

Combines the KPI view from the original dashboard with the
interactive analytics visualisations.
"""

from datetime import datetime, timedelta

import altair as alt
import pandas as pd
# pyrefly: ignore [missing-import]
import plotly.express as px
import streamlit as st

from src.db.models import Alert, Prediction, Transaction
from src.db.session import SessionLocal
from src.logging.logger import get_logger
from src.security.auth import require_auth


logger = get_logger(__name__)


# ----------------------------------------------------------------------
# UI colours
# ----------------------------------------------------------------------
PRIMARY_COLOR = "#8B5CF6"
SECONDARY_COLOR = "#14B8A6"
FRAUD_COLOR = "#E11D48"
LEGIT_COLOR = "#38BDF8"
WARNING_COLOR = "#F59E0B"
GRID_COLOR = "rgba(148, 163, 184, 0.20)"


# ----------------------------------------------------------------------
# KPI helpers
# ----------------------------------------------------------------------
def _load_metrics(db):
    """Collect high-level counters used for the KPI cards."""
    total_tx = db.query(Transaction).count()

    total_fraud = (
        db.query(Prediction)
        .filter(Prediction.prediction.is_(True))
        .count()
    )

    total_legit = (
        db.query(Prediction)
        .filter(Prediction.prediction.is_(False))
        .count()
    )

    fraud_pct = (
        total_fraud / total_tx * 100
        if total_tx
        else 0
    )

    avg_risk_vals = (
        db.query(Prediction.risk_score)
        .filter(Prediction.prediction.is_(True))
        .all()
    )

    avg_risk_score = (
        sum(value[0] for value in avg_risk_vals)
        / len(avg_risk_vals)
        if avg_risk_vals
        else 0
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
    """Load hourly transaction and fraud counts."""
    df = pd.read_sql_query(
        "SELECT created_at, prediction FROM predictions",
        con=db.bind,
    )

    if df.empty:
        return None, None

    df["hour"] = pd.to_datetime(
        df["created_at"]
    ).dt.floor("H")

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
# Analytics helpers
# ----------------------------------------------------------------------
def _load_data(db, days: int = 30):
    """Load predictions and transactions for the selected period."""
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
    """Extract a numeric transaction amount safely."""
    if not isinstance(raw_data, dict):
        return 0.0

    try:
        return float(
            raw_data.get("transaction_amount", 0.0)
        )
    except (TypeError, ValueError):
        return 0.0


def _safe_category(raw_data: dict) -> str:
    """Extract the merchant category safely."""
    if not isinstance(raw_data, dict):
        return "Unknown"

    category = raw_data.get("merchant_category")

    return str(category) if category else "Unknown"


# ----------------------------------------------------------------------
# Plotly styling helper
# ----------------------------------------------------------------------
def _style_plotly_chart(
    figure,
    *,
    height: int = 350,
    show_legend: bool = False,
):
    """Apply consistent dashboard styling to a Plotly figure."""
    figure.update_layout(
        height=height,
        margin=dict(l=20, r=20, t=55, b=20),
        showlegend=show_legend,
        hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(
            family="Arial, sans-serif",
            size=13,
        ),
    )

    figure.update_xaxes(
        showgrid=False,
        zeroline=False,
        title_font=dict(size=13),
    )

    figure.update_yaxes(
        gridcolor=GRID_COLOR,
        zeroline=False,
        title_font=dict(size=13),
    )

    return figure


# ----------------------------------------------------------------------
# KPI section
# ----------------------------------------------------------------------
def _render_primary_metrics(metrics):
    """Render the five main dashboard KPI cards."""
    st.markdown("### Executive overview")
    st.caption(
        "A high-level view of transaction activity, fraud exposure, "
        "risk scores, and generated alerts."
    )

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="💳 Total transactions",
            value=f"{metrics['total_tx']:,}",
        )

    with col2:
        st.metric(
            label="🚨 Fraud transactions",
            value=f"{metrics['total_fraud']:,}",
        )

    with col3:
        st.metric(
            label="📈 Fraud rate",
            value=metrics["fraud_pct"],
        )

    with col4:
        st.metric(
            label="🎯 Average fraud risk",
            value=metrics["avg_risk_score"],
        )

    with col5:
        st.metric(
            label="🔔 High-risk alerts",
            value=f"{metrics['high_risk']:,}",
        )


# ----------------------------------------------------------------------
# Overview tab
# ----------------------------------------------------------------------
def _render_overview_tab(tx_hour, fraud_hour):
    """Render transaction and fraud time-series charts."""
    st.markdown("### Activity during the last 24 hours")
    st.caption(
        "Compare hourly transaction volume with detected fraud activity."
    )

    if tx_hour is None:
        st.info(
            "No hourly prediction data is available yet."
        )
        return

    left_chart, right_chart = st.columns(2)

    with left_chart:
        figure_transactions = px.line(
            tx_hour,
            x="hour",
            y="transactions",
            title="Transaction volume",
            markers=True,
        )

        figure_transactions.update_traces(
            line=dict(
                color=PRIMARY_COLOR,
                width=3,
            ),
            marker=dict(size=7),
        )

        _style_plotly_chart(
            figure_transactions,
            height=340,
        )

        st.plotly_chart(
            figure_transactions,
            use_container_width=True,
        )

    with right_chart:
        if fraud_hour is not None and not fraud_hour.empty:
            figure_fraud = px.line(
                fraud_hour,
                x="hour",
                y="frauds",
                title="Fraud activity",
                markers=True,
            )

            figure_fraud.update_traces(
                line=dict(
                    color=FRAUD_COLOR,
                    width=3,
                ),
                marker=dict(size=7),
            )

            _style_plotly_chart(
                figure_fraud,
                height=340,
            )

            st.plotly_chart(
                figure_fraud,
                use_container_width=True,
            )

        else:
            st.info(
                "No fraudulent transactions were recorded "
                "during the available period."
            )


# ----------------------------------------------------------------------
# Risk analytics tab
# ----------------------------------------------------------------------
def _render_risk_analytics_tab(df_pred):
    """Render risk-focused charts and summary metrics."""
    total_transactions = len(df_pred)
    fraud_transactions = int(
        df_pred["prediction"].sum()
    )

    fraud_rate = (
        fraud_transactions / total_transactions * 100
        if total_transactions
        else 0.0
    )

    avg_risk = float(
        df_pred["risk_score"].mean()
    )

    st.markdown("### Risk summary")
    st.caption(
        "Key fraud and risk indicators for the selected analytics period."
    )

    metric1, metric2, metric3, metric4 = st.columns(4)

    metric1.metric(
        "Transactions",
        f"{total_transactions:,}",
    )

    metric2.metric(
        "Fraud predictions",
        f"{fraud_transactions:,}",
    )

    metric3.metric(
        "Fraud rate",
        f"{fraud_rate:.2f}%",
    )

    metric4.metric(
        "Average risk score",
        f"{avg_risk:.2f}",
    )

    st.divider()

    st.markdown("### Risk score distribution")
    st.caption(
        "Distribution of model-generated risk scores "
        "across processed transactions."
    )

    risk_chart = (
        alt.Chart(df_pred)
        .mark_bar(
            color=PRIMARY_COLOR,
            cornerRadiusTopLeft=4,
            cornerRadiusTopRight=4,
        )
        .encode(
            x=alt.X(
                "risk_score:Q",
                bin=alt.Bin(maxbins=30),
                title="Risk score",
            ),
            y=alt.Y(
                "count():Q",
                title="Transactions",
            ),
            tooltip=[
                alt.Tooltip(
                    "risk_score:Q",
                    bin=True,
                    title="Risk score range",
                ),
                alt.Tooltip(
                    "count():Q",
                    title="Transaction count",
                ),
            ],
        )
        .properties(height=330)
        .interactive()
    )

    st.altair_chart(
        risk_chart,
        use_container_width=True,
    )

    st.divider()

    st.markdown(
        "### Fraud classification across processed transactions"
    )
    st.caption(
        "Fraud and legitimate classifications shown together "
        "with their corresponding risk scores."
    )

    timeline = df_pred.copy()

    timeline["transaction_number"] = range(
        1,
        len(timeline) + 1,
    )

    timeline["prediction_label"] = (
        timeline["prediction"]
        .map(
            {
                True: "Fraud",
                False: "Legit",
            }
        )
    )

    timeline["prediction_value"] = (
        timeline["prediction"].astype(int)
    )

    scatter = (
        alt.Chart(timeline)
        .mark_circle(size=100)
        .encode(
            x=alt.X(
                "transaction_number:Q",
                title="Processed transaction number",
            ),
            y=alt.Y(
                "prediction_value:Q",
                title="Classification",
                scale=alt.Scale(
                    domain=[-0.2, 1.2]
                ),
                axis=alt.Axis(
                    values=[0, 1],
                    labelExpr=(
                        "datum.value == 1 "
                        "? 'Fraud' : 'Legit'"
                    ),
                ),
            ),
            color=alt.Color(
                "prediction_label:N",
                title="Prediction",
                scale=alt.Scale(
                    domain=["Fraud", "Legit"],
                    range=[
                        FRAUD_COLOR,
                        LEGIT_COLOR,
                    ],
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "transaction_number:Q",
                    title="Transaction number",
                ),
                alt.Tooltip(
                    "timestamp:T",
                    title="Processed at",
                ),
                alt.Tooltip(
                    "prediction_label:N",
                    title="Prediction",
                ),
                alt.Tooltip(
                    "risk_score:Q",
                    title="Risk score",
                    format=".2f",
                ),
                alt.Tooltip(
                    "fraud_prob:Q",
                    title="Fraud probability",
                    format=".2%",
                ),
            ],
        )
        .properties(height=230)
        .interactive()
    )

    risk_line = (
        alt.Chart(timeline)
        .mark_line(
            color=PRIMARY_COLOR,
            opacity=0.70,
            strokeWidth=2,
        )
        .encode(
            x=alt.X(
                "transaction_number:Q",
                title="Processed transaction number",
            ),
            y=alt.Y(
                "risk_score:Q",
                title="Risk score",
                scale=alt.Scale(
                    domain=[0, 100]
                ),
            ),
            tooltip=[
                alt.Tooltip(
                    "transaction_number:Q",
                    title="Transaction number",
                ),
                alt.Tooltip(
                    "risk_score:Q",
                    title="Risk score",
                    format=".2f",
                ),
            ],
        )
        .properties(height=230)
        .interactive()
    )

    st.altair_chart(
        scatter & risk_line,
        use_container_width=True,
    )


# ----------------------------------------------------------------------
# Transaction insights tab
# ----------------------------------------------------------------------
def _render_transaction_insights_tab(df_txn):
    """Render amount and category distribution charts."""
    st.markdown("### Transaction behaviour")
    st.caption(
        "Review transaction value patterns and the most active "
        "merchant categories."
    )

    amount_column, category_column = st.columns(2)

    with amount_column:
        st.markdown("#### Transaction amounts")

        if df_txn.empty:
            st.info(
                "No transaction amount data is available."
            )

        else:
            amount_chart = (
                alt.Chart(df_txn)
                .mark_bar(
                    color=SECONDARY_COLOR,
                    cornerRadiusTopLeft=4,
                    cornerRadiusTopRight=4,
                )
                .encode(
                    x=alt.X(
                        "amount:Q",
                        bin=alt.Bin(maxbins=20),
                        title="Transaction amount",
                    ),
                    y=alt.Y(
                        "count():Q",
                        title="Transactions",
                    ),
                    tooltip=[
                        alt.Tooltip(
                            "amount:Q",
                            bin=True,
                            title="Amount range",
                        ),
                        alt.Tooltip(
                            "count():Q",
                            title="Transaction count",
                        ),
                    ],
                )
                .properties(height=360)
                .interactive()
            )

            st.altair_chart(
                amount_chart,
                use_container_width=True,
            )

    with category_column:
        st.markdown("#### Merchant categories")

        category_counts = (
            df_txn["category"]
            .value_counts()
            .head(10)
            .rename_axis("category")
            .reset_index(name="count")
        )

        if category_counts.empty:
            st.info(
                "No merchant category data is available."
            )

        else:
            category_chart = (
                alt.Chart(category_counts)
                .mark_bar(
                    color=SECONDARY_COLOR,
                    cornerRadiusEnd=4,
                    size=24,
                )
                .encode(
                    y=alt.Y(
                        "category:N",
                        sort="-x",
                        title=None,
                    ),
                    x=alt.X(
                        "count:Q",
                        title="Transactions",
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
                .properties(height=360)
            ) 
            st.altair_chart(
                category_chart,
                use_container_width=True,
            ) 

    

# ----------------------------------------------------------------------
# Main render function
# ----------------------------------------------------------------------
def render():
    """Render the combined Dashboard & Analytics page."""
    require_auth()

    st.title("🛡️ Fraud Intelligence Dashboard")
    st.caption(
        "Monitor transaction activity, fraud exposure, risk patterns, "
        "and merchant behaviour from one central workspace."
    )

    db = SessionLocal()

    try:
        metrics = _load_metrics(db)

        _render_primary_metrics(metrics)

        st.divider()

        tx_hour, fraud_hour = _load_time_series(db)

        with st.expander(
            "⚙️ Analytics period",
            expanded=False,
        ):
            days = st.slider(
                "Days back",
                min_value=7,
                max_value=180,
                value=30,
                help=(
                    "Select the time window used for risk "
                    "and transaction analytics."
                ),
            )

        records = _load_data(
            db,
            days=days,
        )

        overview_tab, risk_tab, transaction_tab = st.tabs(
            [
                "📈 Overview",
                "🛡️ Risk Analytics",
                "💳 Transaction Insights",
            ]
        )

        with overview_tab:
            _render_overview_tab(
                tx_hour,
                fraud_hour,
            )

        if not records:
            with risk_tab:
                st.info(
                    "No analytics data is available for "
                    "the selected period."
                )

            with transaction_tab:
                st.info(
                    "No transaction data is available for "
                    "the selected period."
                )

            return

        df_pred = pd.DataFrame(
            [
                {
                    "timestamp": pred.created_at,
                    "risk_score": float(
                        pred.risk_score or 0.0
                    ),
                    "prediction": bool(
                        pred.prediction
                    ),
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
                    "amount": _safe_amount(
                        txn.raw_data
                    ),
                    "category": _safe_category(
                        txn.raw_data
                    ),
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

        df_pred.dropna(
            subset=["timestamp"],
            inplace=True,
        )

        df_txn.dropna(
            subset=["timestamp"],
            inplace=True,
        )

        if df_pred.empty:
            with risk_tab:
                st.info(
                    "No valid prediction timestamps are available."
                )

            with transaction_tab:
                st.info(
                    "No valid transaction timestamps are available."
                )

            return

        with risk_tab:
            _render_risk_analytics_tab(
                df_pred
            )

        with transaction_tab:
            _render_transaction_insights_tab(
                df_txn
            )

        logger.info(
            "Rendered merged Dashboard & Analytics page for %d days",
            days,
        )

    finally:
        db.close()