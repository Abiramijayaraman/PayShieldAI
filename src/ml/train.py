# src/ml/train.py
"""Training pipeline for PayShield AI fraud detection.

Workflow:
- Load the dataset
- Detect and validate the binary fraud target
- Build and fit the preprocessing pipeline
- Split the data into training and test sets
- Apply SMOTE only to the training data
- Train several classification models
- Evaluate models using fraud-detection metrics
- Select the best model based on F1 score
- Calculate the optimal classification threshold
- Save the trained model, preprocessor, and metadata
"""

import json
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
import xgboost as xgb

from imblearn.over_sampling import SMOTE

from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

from src.logging.logger import get_logger
from src.ml.data_loader import (
    generate_validation_report,
    load_dataset,
    save_report,
)
from src.ml.preprocessing import build_preprocessor


logger = get_logger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(parents=True, exist_ok=True)


def evaluate_model(
    y_true: pd.Series,
    y_pred: Any,
    y_proba: Any,
) -> dict[str, Any]:
    """Calculate binary-classification metrics."""
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(
            precision_score(
                y_true,
                y_pred,
                average="binary",
                pos_label=1,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y_true,
                y_pred,
                average="binary",
                pos_label=1,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y_true,
                y_pred,
                average="binary",
                pos_label=1,
                zero_division=0,
            )
        ),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "confusion_matrix": confusion_matrix(
            y_true,
            y_pred,
            labels=[0, 1],
        ).tolist(),
        "classification_report": classification_report(
            y_true,
            y_pred,
            labels=[0, 1],
            target_names=["genuine", "fraud"],
            output_dict=True,
            zero_division=0,
        ),
    }


def find_optimal_threshold(
    y_true: pd.Series,
    y_proba: Any,
) -> float:
    """Calculate the optimal threshold using Youden's J statistic."""
    false_positive_rate, true_positive_rate, thresholds = roc_curve(
        y_true,
        y_proba,
        pos_label=1,
    )

    youden_j = true_positive_rate - false_positive_rate
    best_index = int(youden_j.argmax())
    threshold = float(thresholds[best_index])

    if threshold < 0.0 or threshold > 1.0:
        return 0.5

    return threshold


def detect_target_column(
    df: pd.DataFrame,
    validation_report: dict[str, Any],
) -> str:
    """Detect the most likely binary fraud target column."""
    preferred_columns = [
        "is_fraud",
        "fraud",
        "fraud_label",
        "is_fraudulent",
        "fraudulent",
        "class",
        "label",
        "target",
    ]

    lowercase_lookup = {
        str(column).strip().lower(): column
        for column in df.columns
    }

    for preferred_name in preferred_columns:
        if preferred_name in lowercase_lookup:
            return lowercase_lookup[preferred_name]

    detected_column = validation_report.get("target_column")

    if detected_column and detected_column in df.columns:
        return detected_column

    raise ValueError(
        "A fraud target column could not be detected. "
        f"Available columns: {list(df.columns)}"
    )


def normalize_binary_target(
    target: pd.Series,
) -> pd.Series:
    """Convert common fraud-label formats into integer labels 0 and 1."""
    if target.isna().any():
        missing_count = int(target.isna().sum())
        raise ValueError(
            f"The target column contains {missing_count} missing values. "
            "Remove or fill them before training."
        )

    if pd.api.types.is_bool_dtype(target):
        normalized = target.astype(int)

    elif pd.api.types.is_numeric_dtype(target):
        numeric_target = pd.to_numeric(target, errors="coerce")

        if numeric_target.isna().any():
            raise ValueError(
                "The numeric target column contains invalid values."
            )

        unique_values = sorted(
            numeric_target.dropna().unique().tolist()
        )

        if set(unique_values).issubset({0, 1, 0.0, 1.0}):
            normalized = numeric_target.astype(int)

        elif len(unique_values) == 2:
            lower_value = unique_values[0]
            higher_value = unique_values[1]

            print(
                "Target contains two numeric classes "
                f"{unique_values}. Mapping {lower_value} -> 0 "
                f"and {higher_value} -> 1."
            )

            normalized = numeric_target.map(
                {
                    lower_value: 0,
                    higher_value: 1,
                }
            ).astype(int)

        else:
            raise ValueError(
                "The target column is multiclass. "
                f"Found numeric labels: {unique_values}. "
                "PayShield AI requires a binary target where "
                "0 means genuine and 1 means fraud."
            )

    else:
        cleaned_target = (
            target.astype(str)
            .str.strip()
            .str.lower()
        )

        label_mapping = {
            "0": 0,
            "false": 0,
            "no": 0,
            "n": 0,
            "genuine": 0,
            "legitimate": 0,
            "legit": 0,
            "normal": 0,
            "non-fraud": 0,
            "non fraud": 0,
            "not fraud": 0,
            "safe": 0,
            "approved": 0,

            "1": 1,
            "true": 1,
            "yes": 1,
            "y": 1,
            "fraud": 1,
            "fraudulent": 1,
            "suspicious": 1,
            "high-risk": 1,
            "high risk": 1,
            "blocked": 1,
        }

        normalized = cleaned_target.map(label_mapping)

        if normalized.isna().any():
            unsupported_values = sorted(
                cleaned_target[normalized.isna()]
                .dropna()
                .unique()
                .tolist()
            )

            raise ValueError(
                "The target column contains unsupported or multiclass "
                f"labels: {unsupported_values}. "
                "Convert the target to binary values before training."
            )

        normalized = normalized.astype(int)

    final_labels = sorted(normalized.unique().tolist())

    if final_labels != [0, 1]:
        raise ValueError(
            "The target column must contain both binary classes 0 and 1. "
            f"Found labels: {final_labels}"
        )

    return normalized


def make_json_serializable(value: Any) -> Any:
    """Convert common NumPy and pandas values into JSON-safe values."""
    if isinstance(value, dict):
        return {
            str(key): make_json_serializable(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [
            make_json_serializable(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            make_json_serializable(item)
            for item in value
        ]

    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, Path):
        return str(value)

    return value


def train() -> dict[str, Any]:
    """Run the complete fraud-model training pipeline."""
    print("Loading dataset...")
    logger.info("Loading dataset.")

    df = load_dataset()

    if df.empty:
        raise ValueError("The loaded dataset is empty.")

    print(f"Dataset loaded: {len(df):,} rows, {len(df.columns)} columns")

    validation_report = generate_validation_report(df)
    save_report(validation_report)

    target_column = detect_target_column(
        df,
        validation_report,
    )

    print(f"Detected target column: {target_column}")
    print("Original target value counts:")
    print(df[target_column].value_counts(dropna=False))

    y = normalize_binary_target(df[target_column])

    print("Normalized target value counts:")
    print(y.value_counts().sort_index())

    drop_columns = [
        column
        for column in [
            target_column,
            "fraud_reason",
            "fraud_score",
        ]
        if column in df.columns
    ]

    X = df.drop(columns=drop_columns)

    if X.empty:
        raise ValueError(
            "No feature columns remain after removing the target column."
        )

    print("Splitting dataset...")

    (
        X_train_raw,
        X_test_raw,
        y_train,
        y_test,
    ) = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=42,
    )

    print(
        f"Training rows: {len(X_train_raw):,} | "
        f"Test rows: {len(X_test_raw):,}"
    )

    print("Building and fitting preprocessor...")
    preprocessor = build_preprocessor(X_train_raw)

    preprocessor.fit(X_train_raw)

    print("Transforming training data...")
    X_train = preprocessor.transform(X_train_raw)

    print("Transforming test data...")
    X_test = preprocessor.transform(X_test_raw)

    print("Applying SMOTE to training data...")
    smote = SMOTE(
        random_state=42,
        k_neighbors=5,
    )

    X_train_resampled, y_train_resampled = smote.fit_resample(
        X_train,
        y_train,
    )

    print(
        "SMOTE completed. "
        f"Training rows increased from {len(y_train):,} "
        f"to {len(y_train_resampled):,}."
    )

    positive_count = int((y_train_resampled == 1).sum())
    negative_count = int((y_train_resampled == 0).sum())

    scale_pos_weight = (
        negative_count / positive_count
        if positive_count > 0
        else 1.0
    )

    models = {
        "RandomForest": RandomForestClassifier(
            n_estimators=50,
            max_depth=None,
            n_jobs=-1,
            random_state=42,
            class_weight="balanced",
        ),
        "XGBoost": xgb.XGBClassifier(
            n_estimators=50,
            max_depth=6,
            learning_rate=0.1,
            subsample=0.9,
            colsample_bytree=0.9,
            eval_metric="logloss",
            n_jobs=-1,
            random_state=42,
            scale_pos_weight=scale_pos_weight,
        ),
        "ExtraTrees": ExtraTreesClassifier(
            n_estimators=50,
            n_jobs=-1,
            random_state=42,
            class_weight="balanced",
        ),
        "DecisionTree": DecisionTreeClassifier(
            random_state=42,
            class_weight="balanced",
        ),
        "LogisticRegression": LogisticRegression(
            max_iter=1000,
            solver="liblinear",
            class_weight="balanced",
            random_state=42,
        ),
    }

    results: dict[str, Any] = {}

    best_f1 = -1.0
    best_name = ""
    best_model = None
    best_metrics = None

    for model_name, model in models.items():
        print(f"\nTraining {model_name}...")
        logger.info("Training model: %s", model_name)

        model.fit(
            X_train_resampled,
            y_train_resampled,
        )

        print(f"Evaluating {model_name}...")

        probabilities = model.predict_proba(X_test)[:, 1]
        predictions = (probabilities >= 0.5).astype(int)

        metrics = evaluate_model(
            y_test,
            predictions,
            probabilities,
        )

        results[model_name] = metrics

        print(
            f"{model_name} results | "
            f"Accuracy: {metrics['accuracy']:.4f} | "
            f"Precision: {metrics['precision']:.4f} | "
            f"Recall: {metrics['recall']:.4f} | "
            f"F1: {metrics['f1']:.4f} | "
            f"ROC-AUC: {metrics['roc_auc']:.4f}"
        )

        if metrics["f1"] > best_f1:
            best_f1 = metrics["f1"]
            best_name = model_name
            best_model = model
            best_metrics = metrics

    if best_model is None or best_metrics is None:
        raise RuntimeError(
            "Training completed without selecting a valid model."
        )

    print(f"\nBest model selected: {best_name}")

    best_probabilities = best_model.predict_proba(X_test)[:, 1]

    optimal_threshold = find_optimal_threshold(
        y_test,
        best_probabilities,
    )

    model_path = MODEL_DIR / "fraud_model.pkl"
    preprocessing_path = MODEL_DIR / "preprocessing.pkl"
    metadata_path = MODEL_DIR / "metadata.json"

    print("Saving model artifacts...")

    joblib.dump(best_model, model_path)
    joblib.dump(preprocessor, preprocessing_path)

    numerical_features = []
    categorical_features = []

    for transformer_name, _, columns in preprocessor.transformers_:
        column_list = (
            list(columns)
            if not isinstance(columns, str)
            else [columns]
        )

        if transformer_name == "num":
            numerical_features = column_list
        elif transformer_name == "cat":
            categorical_features = column_list

    metadata = {
        "selected_model": best_name,
        "optimal_threshold": optimal_threshold,
        "metrics": best_metrics,
        "all_model_metrics": results,
        "feature_schema": {
            "categorical": categorical_features,
            "numerical": numerical_features,
        },
        "target_column": target_column,
        "target_mapping": {
            "0": "genuine",
            "1": "fraud",
        },
        "training_rows": int(len(X_train_raw)),
        "test_rows": int(len(X_test_raw)),
        "resampled_training_rows": int(
            len(y_train_resampled)
        ),
        "model_path": str(model_path),
        "preprocessing_path": str(preprocessing_path),
        "trained_at": pd.Timestamp.now(
            tz="UTC"
        ).isoformat(),
    }

    metadata = make_json_serializable(metadata)

    with metadata_path.open(
        "w",
        encoding="utf-8",
    ) as metadata_file:
        json.dump(
            metadata,
            metadata_file,
            indent=4,
        )

    print("\nTraining complete.")
    print(f"Best model: {best_name}")
    print(f"Best F1 score: {best_f1:.4f}")
    print(f"Optimal fraud threshold: {optimal_threshold:.4f}")
    print(f"Model saved to: {model_path}")
    print(f"Preprocessor saved to: {preprocessing_path}")
    print(f"Metadata saved to: {metadata_path}")

    logger.info(
        "Training completed. Best model: %s, F1: %.4f",
        best_name,
        best_f1,
    )

    return metadata


if __name__ == "__main__":
    train()