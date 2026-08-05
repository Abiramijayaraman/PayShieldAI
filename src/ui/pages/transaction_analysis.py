import json
import os

import altair as alt
import pandas as pd
import streamlit as st

from src.db.services import create_alert, save_prediction, save_transaction
from src.ml.explain import get_batch_summary, get_explanation
from src.ml.inference import predict_batch, predict_transaction
from src.security.auth import get_current_user, require_auth


PRIMARY_COLOR = "#8B5CF6"
SECONDARY_COLOR = "#14B8A6"
FRAUD_COLOR = "#E11D48"
LEGIT_COLOR = "#10B981"


def _load_feature_schema():
    """Load the feature schema from models/metadata.json."""
    base_dir = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "..",
        )
    )

    metadata_path = os.path.join(
        base_dir,
        "models",
        "metadata.json",
    )

    try:
        with open(
            metadata_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        return data.get("feature_schema", {})

    except Exception as exc:
        st.error(
            f"Unable to load feature schema: {exc}"
        )
        return {}


def _field_label(field):
    """Convert a feature name into a readable label."""
    return field.replace("_", " ").title()


def _render_categorical_field(
    field,
    cat_options,
    tx_input,
):
    """Render one categorical feature input."""
    options = cat_options.get(field, [])

    if options:
        tx_input[field] = st.selectbox(
            label=_field_label(field),
            options=options,
            key=f"cat_{field}",
        )
    else:
        tx_input[field] = st.text_input(
            label=_field_label(field),
            key=f"cat_{field}",
        )


def _render_numerical_field(
    field,
    num_options,
    tx_input,
):
    """Render one numerical feature input."""
    options = num_options.get(field, {})

    min_value = options.get("min", 0.0)
    max_value = options.get("max", 1e9)
    step = options.get("step", 0.01)

    tx_input[field] = st.number_input(
        label=_field_label(field),
        min_value=min_value,
        max_value=max_value,
        step=step,
        key=f"num_{field}",
    )


def _render_field_group(
    title,
    fields,
    categorical_fields,
    numerical_fields,
    cat_options,
    num_options,
    tx_input,
):
    """Render a feature group using a two-column layout."""
    if not fields:
        return

    st.markdown(f"#### {title}")

    left_column, right_column = st.columns(2)

    for index, field in enumerate(fields):
        target_column = (
            left_column
            if index % 2 == 0
            else right_column
        )

        with target_column:
            if field in categorical_fields:
                _render_categorical_field(
                    field,
                    cat_options,
                    tx_input,
                )

            elif field in numerical_fields:
                _render_numerical_field(
                    field,
                    num_options,
                    tx_input,
                )

    st.markdown("")


def _group_fields(
    categorical_fields,
    numerical_fields,
):
    """Organize model features into readable UI sections."""
    all_fields = (
        list(categorical_fields)
        + list(numerical_fields)
    )

    group_keywords = {
        "Transaction details": [
            "transaction_id",
            "transaction_datetime",
            "payment_method",
            "payment_channel",
            "merchant_name",
            "merchant_category",
            "transaction_amount",
            "hour_of_day",
            "day_of_week",
            "is_weekend",
        ],
        "Customer information": [
            "customer_id",
            "customer_segment",
            "customer_age",
            "account_age_days",
            "previous_transactions_24h",
            "avg_transaction_amount_30d",
        ],
        "Location and device": [
            "transaction_city",
            "transaction_state",
            "device_type",
            "network_type",
            "is_new_device",
            "is_new_location",
            "distance_from_home_km",
            "is_international",
        ],
        "Risk and behaviour": [
            "merchant_risk_score",
            "failed_login_attempts",
            "amount_deviation_ratio",
            "velocity_score",
        ],
    }

    grouped_fields = {}
    used_fields = set()

    for group_name, preferred_fields in group_keywords.items():
        matched_fields = [
            field
            for field in preferred_fields
            if field in all_fields
        ]

        if matched_fields:
            grouped_fields[group_name] = matched_fields
            used_fields.update(matched_fields)

    remaining_fields = [
        field
        for field in all_fields
        if field not in used_fields
    ]

    if remaining_fields:
        grouped_fields["Additional features"] = (
            remaining_fields
        )

    return grouped_fields


def _render_prediction_results(
    transaction,
    prediction,
    explanation,
):
    """Render single-transaction prediction results."""
    st.divider()

    prediction_value = bool(
        prediction.get("prediction")
    )

    prediction_label = (
        "Fraud"
        if prediction_value
        else "Legitimate"
    )

    if prediction_value:
        st.error(
            "🚨 Potential fraudulent transaction detected."
        )
    else:
        st.success(
            "✅ Transaction classified as legitimate."
        )

    st.markdown("### Prediction summary")

    metric_columns = st.columns(5)

    metric_columns[0].metric(
        "Prediction",
        prediction_label,
    )

    metric_columns[1].metric(
        "Fraud probability",
        (
            f"{float(prediction.get('fraud_probability', 0.0)):.2%}"
        ),
    )

    metric_columns[2].metric(
        "Risk score",
        (
            f"{float(prediction.get('risk_score', 0.0)):.2f}"
        ),
    )

    metric_columns[3].metric(
        "Confidence",
        (
            f"{float(prediction.get('confidence', 0.0)):.2%}"
        ),
    )

    metric_columns[4].metric(
        "Fraud category",
        prediction.get(
            "fraud_category",
            "N/A",
        ),
    )

    st.markdown("### AI investigation summary")

    with st.container():
        st.info(explanation)

    save_left, save_center, save_right = st.columns(
        [1, 2, 1]
    )

    with save_center:
        if st.button(
            "💾 Save Result",
            use_container_width=True,
            key="save_single_result",
        ):
            try:
                user = get_current_user()

                if user is None:
                    st.error(
                        "Unable to identify the current user."
                    )
                    return

                transaction_object = save_transaction(
                    transaction
                )

                prediction_object = save_prediction(
                    user_id=user.id,
                    transaction_id=transaction_object.id,
                    fraud_probability=float(
                        prediction.get(
                            "fraud_probability",
                            0.0,
                        )
                    ),
                    risk_score=float(
                        prediction.get(
                            "risk_score",
                            0.0,
                        )
                    ),
                    prediction=prediction_value,
                    confidence=float(
                        prediction.get(
                            "confidence",
                            0.0,
                        )
                    ),
                    fraud_category=prediction.get(
                        "fraud_category"
                    ),
                    explanation=explanation,
                )

                if float(
                    prediction.get(
                        "risk_score",
                        0.0,
                    )
                ) >= 80:
                    create_alert(
                        user_id=user.id,
                        prediction_id=prediction_object.id,
                        risk_score=float(
                            prediction.get(
                                "risk_score",
                                0.0,
                            )
                        ),
                        reason=(
                            "High-risk transaction detected"
                        ),
                    )

                st.success(
                    "Result saved successfully."
                )

            except Exception as exc:
                st.error(
                    f"Failed to save result: {exc}"
                )


def _render_single_transaction(schema):
    """Render the single-transaction analysis interface."""
    st.markdown("### 🔎 Single Transaction")
    st.caption(
        "Enter the transaction details below to generate "
        "a fraud prediction, risk score, and AI explanation."
    )

    categorical_fields = schema.get(
        "categorical",
        [],
    )

    numerical_fields = schema.get(
        "numerical",
        [],
    )

    categorical_options = schema.get(
        "categorical_options",
        {},
    )

    numerical_options = schema.get(
        "numerical_options",
        {},
    )

    grouped_fields = _group_fields(
        categorical_fields,
        numerical_fields,
    )

    with st.form(
        key="single_tx_form",
    ):
        transaction_input = {}

        for group_name, fields in grouped_fields.items():
            with st.container():
                _render_field_group(
                    title=group_name,
                    fields=fields,
                    categorical_fields=categorical_fields,
                    numerical_fields=numerical_fields,
                    cat_options=categorical_options,
                    num_options=numerical_options,
                    tx_input=transaction_input,
                )

        submitted = st.form_submit_button(
            "🔍 Analyze Transaction",
            use_container_width=True,
        )

        if submitted:
            st.session_state[
                "single_tx_input"
            ] = transaction_input

    if "single_tx_input" not in st.session_state:
        st.info(
            "Complete the form and select "
            "'Analyze Transaction' to view the result."
        )
        return

    transaction = st.session_state[
        "single_tx_input"
    ]

    try:
        prediction = predict_transaction(
            transaction
        )

        explanation = get_explanation(
            transaction,
            prediction,
        )

    except Exception as exc:
        st.error(
            f"Prediction failed: {exc}"
        )
        return

    _render_prediction_results(
        transaction,
        prediction,
        explanation,
    )


def _validate_batch_columns(
    dataframe,
    schema,
):
    """Validate uploaded CSV columns against the feature schema."""
    required = (
        set(
            schema.get(
                "categorical",
                [],
            )
        )
        | set(
            schema.get(
                "numerical",
                [],
            )
        )
    )

    uploaded = set(
        dataframe.columns.astype(str)
    )

    missing = required - uploaded
    extra = uploaded - required

    return missing, extra


def _render_batch_metrics(results_df):
    """Render summary metrics for a batch prediction."""
    total = len(results_df)

    fraud_count = int(
        results_df["prediction"].sum()
    )

    legitimate_count = total - fraud_count

    fraud_percentage = (
        fraud_count / total * 100
        if total
        else 0
    )

    average_risk = (
        results_df["risk_score"].mean()
        if "risk_score" in results_df
        else 0
    )

    metric_columns = st.columns(5)

    metric_columns[0].metric(
        "Total transactions",
        f"{total:,}",
    )

    metric_columns[1].metric(
        "Fraud count",
        f"{fraud_count:,}",
    )

    metric_columns[2].metric(
        "Legitimate count",
        f"{legitimate_count:,}",
    )

    metric_columns[3].metric(
        "Fraud rate",
        f"{fraud_percentage:.2f}%",
    )

    metric_columns[4].metric(
        "Average risk",
        f"{average_risk:.2f}",
    )

    return (
        fraud_count,
        legitimate_count,
    )


def _render_batch_charts(
    results_df,
    fraud_count,
    legitimate_count,
):
    """Render batch prediction charts."""
    left_chart, right_chart = st.columns(2)

    with left_chart:
        st.markdown("#### Fraud vs legitimate")

        chart_data = pd.DataFrame(
            {
                "Category": [
                    "Fraud",
                    "Legitimate",
                ],
                "Count": [
                    fraud_count,
                    legitimate_count,
                ],
            }
        )

        classification_chart = (
            alt.Chart(chart_data)
            .mark_bar(
                cornerRadiusTopLeft=5,
                cornerRadiusTopRight=5,
            )
            .encode(
                x=alt.X(
                    "Category:N",
                    title=None,
                ),
                y=alt.Y(
                    "Count:Q",
                    title="Transactions",
                ),
                color=alt.Color(
                    "Category:N",
                    scale=alt.Scale(
                        domain=[
                            "Fraud",
                            "Legitimate",
                        ],
                        range=[
                            FRAUD_COLOR,
                            LEGIT_COLOR,
                        ],
                    ),
                    legend=None,
                ),
                tooltip=[
                    alt.Tooltip(
                        "Category:N",
                        title="Classification",
                    ),
                    alt.Tooltip(
                        "Count:Q",
                        title="Transactions",
                    ),
                ],
            )
            .properties(height=330)
        )

        st.altair_chart(
            classification_chart,
            use_container_width=True,
        )

    with right_chart:
        st.markdown("#### Risk score distribution")

        if "risk_score" not in results_df:
            st.info(
                "Risk score data is not available."
            )
        else:
            risk_chart = (
                alt.Chart(results_df)
                .mark_bar(
                    color=PRIMARY_COLOR,
                    cornerRadiusTopLeft=5,
                    cornerRadiusTopRight=5,
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
                            title="Transactions",
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


def _render_batch_dataset(schema):
    """Render the batch dataset analysis interface."""
    st.markdown("### 📂 Batch Dataset")
    st.caption(
        "Upload a CSV file containing multiple transactions "
        "to run batch fraud predictions and generate a report."
    )

    categorical_fields = schema.get(
        "categorical",
        [],
    )

    numerical_fields = schema.get(
        "numerical",
        [],
    )

    required_fields = (
        categorical_fields
        + numerical_fields
    )

    with st.expander(
        "View required CSV columns",
        expanded=False,
    ):
        if required_fields:
            st.code(
                ", ".join(required_fields),
                language=None,
            )
        else:
            st.info(
                "No feature columns were found "
                "in the model metadata."
            )

    uploaded_file = st.file_uploader(
        "Upload CSV file with transactions",
        type=["csv"],
        key="batch_file",
        help=(
            "The CSV must contain all model feature columns."
        ),
    )

    if uploaded_file is None:
        st.info(
            "Upload a CSV file to begin batch analysis."
        )
        return

    try:
        dataframe = pd.read_csv(
            uploaded_file
        )

    except Exception as exc:
        st.error(
            f"Could not read CSV: {exc}"
        )
        return

    file_metric_1, file_metric_2 = st.columns(2)

    file_metric_1.metric(
        "Rows detected",
        f"{len(dataframe):,}",
    )

    file_metric_2.metric(
        "Columns detected",
        f"{len(dataframe.columns):,}",
    )

    missing, extra = _validate_batch_columns(
        dataframe,
        schema,
    )

    if missing:
        st.error(
            "The uploaded dataset is missing required columns."
        )

        st.write(
            "Missing columns:",
            ", ".join(sorted(missing)),
        )

        return

    if extra:
        st.warning(
            "Extra columns were detected and will be ignored."
        )

        st.write(
            "Extra columns:",
            ", ".join(sorted(extra)),
        )

    st.success(
        "✅ Dataset validation completed successfully."
    )

    ordered_columns = (
        categorical_fields
        + numerical_fields
    )

    dataframe = dataframe[
        ordered_columns
    ]

    try:
        results_df = predict_batch(
            dataframe
        )

    except Exception as exc:
        st.error(
            f"Batch prediction failed: {exc}"
        )
        return

    st.divider()

    st.markdown("### Batch analysis summary")

    fraud_count, legitimate_count = (
        _render_batch_metrics(
            results_df
        )
    )

    st.divider()

    _render_batch_charts(
        results_df,
        fraud_count,
        legitimate_count,
    )

    st.divider()

    with st.expander(
        "📋 View prediction results",
        expanded=False,
    ):
        st.dataframe(
            results_df,
            use_container_width=True,
        )

    try:
        summary = get_batch_summary(
            results_df.to_dict(
                orient="records"
            )
        )

        st.markdown("### AI batch summary")
        st.info(summary)

    except Exception as exc:
        st.warning(
            f"Failed to generate AI summary: {exc}"
        )

    csv_bytes = results_df.to_csv(
        index=False
    ).encode("utf-8")

    download_left, download_center, download_right = (
        st.columns([1, 2, 1])
    )

    with download_center:
        st.download_button(
            label="⬇️ Download Batch Report",
            data=csv_bytes,
            file_name="batch_analysis_report.csv",
            mime="text/csv",
            key="download_report",
            use_container_width=True,
        )


def render():
    """Render the Transaction Intelligence page."""
    require_auth()

    st.title("🔎 Transaction Intelligence")
    st.caption(
        "Analyze individual transactions or evaluate complete "
        "datasets using AI-powered fraud detection and risk scoring."
    )

    schema = _load_feature_schema()

    if not schema:
        st.stop()

    single_tab, batch_tab = st.tabs(
        [
            "🔍 Single Transaction",
            "📂 Batch Analysis",
        ]
    )

    with single_tab:
        _render_single_transaction(
            schema
        )

    with batch_tab:
        _render_batch_dataset(
            schema
        )