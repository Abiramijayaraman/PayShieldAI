import json
import os
from datetime import datetime

import pandas as pd
import streamlit as st
import altair as alt

from src.security.auth import require_auth, get_current_user
from src.ml.inference import predict_transaction, predict_batch
from src.ml.explain import get_explanation, get_batch_summary
from src.db.services import save_transaction, save_prediction, create_alert


def _load_feature_schema():
    """Load the feature schema from ``models/metadata.json``."""
    # Resolve the project root: src/ui/pages/transaction_analysis.py -> PayShieldAI
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    metadata_path = os.path.join(base_dir, "models", "metadata.json")
    try:
        with open(metadata_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("feature_schema", {})
    except Exception as e:
        st.error(f"Unable to load feature schema: {e}")
        return {}


def _render_single_transaction(schema):
    """UI for a single transaction analysis."""
    st.subheader("🔎 Single Transaction")

    categorical = schema.get("categorical", [])
    numerical = schema.get("numerical", [])
    # Optional extra option dictionaries (may be missing)
    cat_options = schema.get("categorical_options", {})
    num_options = schema.get("numerical_options", {})

    with st.form(key="single_tx_form"):
        tx_input = {}

        for field in categorical:
            options = cat_options.get(field, [])
            if options:
                tx_input[field] = st.selectbox(
                    label=field.replace("_", " ").title(),
                    options=options,
                    key=f"cat_{field}",
                )
            else:
                tx_input[field] = st.text_input(
                    label=field.replace("_", " ").title(),
                    key=f"cat_{field}",
                )

        for field in numerical:
            opts = num_options.get(field, {})
            min_val = opts.get("min", 0.0)
            max_val = opts.get("max", 1e9)
            step = opts.get("step", 0.01)
            tx_input[field] = st.number_input(
                label=field.replace("_", " ").title(),
                min_value=min_val,
                max_value=max_val,
                step=step,
                key=f"num_{field}",
            )

        submitted = st.form_submit_button("Run Prediction")
        if submitted:
            st.session_state["single_tx_input"] = tx_input

    if "single_tx_input" not in st.session_state:
        return

    transaction = st.session_state["single_tx_input"]
    try:
        pred = predict_transaction(transaction)
        explanation = get_explanation(transaction, pred)
    except Exception as e:
        st.error(f"Prediction failed: {e}")
        return

    st.success("✅ Prediction completed")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric("Prediction", "Fraud" if pred.get("prediction") else "Legit")
        st.metric(
            "Fraud Probability",
            f"{pred.get('fraud_probability', 0):.2%}",
        )
        st.metric(
            "Risk Score",
            f"{pred.get('risk_score', 0):.2f}",
        )
    with col_b:
        st.metric(
            "Confidence",
            f"{pred.get('confidence', 0):.2%}",
        )
        st.metric(
            "Fraud Category",
            pred.get("fraud_category", "N/A"),
        )

    st.subheader("AI Explanation")
    st.write(explanation)

    if st.button("Save Result"):
        try:
            user = get_current_user()
            txn_obj = save_transaction(transaction)
            pred_obj = save_prediction(
                user_id=user.id,
                transaction_id=txn_obj.id,
                fraud_probability=pred.get("fraud_probability", 0.0),
                risk_score=pred.get("risk_score", 0.0),
                prediction=bool(pred.get("prediction")),
                confidence=pred.get("confidence", 0.0),
                fraud_category=pred.get("fraud_category"),
                explanation=explanation,
            )
            if pred.get("risk_score", 0) >= 80:
                create_alert(
                    user_id=user.id,
                    prediction_id=pred_obj.id,
                    risk_score=pred.get("risk_score", 0.0),
                    reason="High‑risk transaction detected",
                )
            st.success("Result saved successfully.")
        except Exception as e:
            st.error(f"Failed to save result: {e}")


def _validate_batch_columns(df: pd.DataFrame, schema: dict):
    required = set(schema.get("categorical", [])) | set(schema.get("numerical", []))
    uploaded = set(df.columns.astype(str))
    missing = required - uploaded
    extra = uploaded - required
    return missing, extra


def _render_batch_dataset(schema):
    """UI for batch dataset analysis."""
    st.subheader("📂 Batch Dataset")

    uploaded_file = st.file_uploader(
        "Upload CSV file with transactions",
        type=["csv"],
        key="batch_file",
    )
    if uploaded_file is None:
        return

    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"Could not read CSV: {e}")
        return

    missing, extra = _validate_batch_columns(df, schema)
    if missing or extra:
        st.error("Column validation failed.")
        if missing:
            st.write("❌ Missing columns:", ", ".join(sorted(missing)))
        if extra:
            st.write("⚠️ Extra columns:", ", ".join(sorted(extra)))
        return
    else:
        st.success("✅ All required columns present.")

    try:
        results_df = predict_batch(df)
    except Exception as e:
        st.error(f"Batch prediction failed: {e}")
        return

    st.subheader("Prediction Results")
    st.dataframe(results_df)

    # KPI cards
    total = len(results_df)
    fraud_cnt = int(results_df["prediction"].sum())
    legit_cnt = total - fraud_cnt
    fraud_pct = (fraud_cnt / total * 100) if total else 0
    avg_risk = results_df["risk_score"].mean() if "risk_score" in results_df else 0

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Transactions", f"{total:,}")
    k2.metric("Fraud Count", f"{fraud_cnt:,}")
    k3.metric("Legit Count", f"{legit_cnt:,}")
    k4.metric("Fraud %", f"{fraud_pct:.2f}%")
    k5.metric("Avg Risk Score", f"{avg_risk:.2f}")

    # Fraud vs Legit chart
    st.subheader("Fraud vs Legit Count")
    chart_data = pd.DataFrame(
        {"Category": ["Fraud", "Legit"], "Count": [fraud_cnt, legit_cnt]}
    )
    bar = (
        alt.Chart(chart_data)
        .mark_bar()
        .encode(
            x=alt.X("Category:N", title="Prediction"),
            y=alt.Y("Count:Q", title="Count"),
            color=alt.Color("Category:N"),
        )
    )
    st.altair_chart(bar, use_container_width=True)

    # Risk score distribution
    if "risk_score" in results_df:
        st.subheader("Risk Score Distribution")
        risk_chart = (
            alt.Chart(results_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "risk_score:Q",
                    bin=alt.Bin(maxbins=30),
                    title="Risk Score",
                ),
                y=alt.Y("count():Q", title="Transactions"),
                tooltip=[alt.Tooltip("risk_score:Q", bin=True, title="Risk Score")],
            )
            .interactive()
        )
        st.altair_chart(risk_chart, use_container_width=True)

    # AI summary
    try:
        summary = get_batch_summary(results_df.to_dict(orient="records"))
        st.subheader("AI Summary")
        st.write(summary)
    except Exception as e:
        st.warning(f"Failed to generate AI summary: {e}")

    # Download button
    csv_bytes = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="Download Report",
        data=csv_bytes,
        file_name="batch_analysis_report.csv",
        mime="text/csv",
        key="download_report",
    )


def render():
    """Entry point for the Transaction Analysis page."""
    require_auth()
    st.title("🔎 Transaction Analysis")
    schema = _load_feature_schema()
    if not schema:
        st.stop()

    tabs = st.tabs(["Single Transaction", "Batch Dataset"])
    with tabs[0]:
        _render_single_transaction(schema)
    with tabs[1]:
        _render_batch_dataset(schema)