# src/ml/data_loader.py
"""Data loading and validation utilities.
The dataset is expected at one of the following locations:
1. Uploaded file in the Antigravity workspace (``data/transactions.csv``)
2. Local path ``C:\\Users\\ADMIN\\Desktop\\transactions.csv``
The module loads the CSV with pandas, inspects the schema, and produces a
validation report saved as ``data/validation_report.json``.
"""
import os
import json
from pathlib import Path
import pandas as pd

DATASET_PATHS = [
    Path(__file__).resolve().parents[2] / "data" / "transactions.csv",
    Path(r"C:\\Users\\ADMIN\\Desktop\\transactions.csv"),
]

def locate_dataset() -> Path:
    """Return the first existing dataset path, or raise FileNotFoundError."""
    for p in DATASET_PATHS:
        if p.is_file():
            return p
    raise FileNotFoundError("Transaction dataset not found in expected locations.")

def load_dataset() -> pd.DataFrame:
    path = locate_dataset()
    df = pd.read_csv(path)
    return df

def generate_validation_report(df: pd.DataFrame) -> dict:
    """Inspect the DataFrame and return a dictionary report.
    The report includes column names, dtypes, missing values, duplicate rows,
    class imbalance, categorical vs numeric columns, outliers, and potential
    target leakage.
    """
    report = {}
    report["num_rows"] = int(df.shape[0])
    report["num_columns"] = int(df.shape[1])
    report["columns"] = {col: str(dtype) for col, dtype in df.dtypes.items()}
    # Missing values
    report["missing_values"] = df.isnull().sum().to_dict()
    # Duplicates
    report["duplicate_rows"] = int(df.duplicated().sum())
    # Identify target column (assume column named 'is_fraud' or similar)
    target_candidates = [c for c in df.columns if any(h in c.lower() for h in ["fraud", "label", "target"])]
    target = target_candidates[0] if target_candidates else None
    report["target_column"] = target
    # Class imbalance if target exists
    if target and target in df.columns:
        class_counts = df[target].value_counts().to_dict()
        report["class_counts"] = class_counts
        report["class_imbalance_ratio"] = max(class_counts.values()) / min(class_counts.values()) if min(class_counts.values()) > 0 else None
    # Categorical vs numerical
    categorical = [c for c, t in df.dtypes.items() if pd.api.types.is_object_dtype(t) or pd.api.types.is_categorical_dtype(t)]
    numerical = [c for c in df.columns if c not in categorical]
    report["categorical_features"] = categorical
    report["numerical_features"] = numerical
    # Simple outlier detection (IQR) for numeric columns
    outliers = {}
    for col in numerical:
        q1 = df[col].quantile(0.25)
        q3 = df[col].quantile(0.75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outlier_count = df[(df[col] < lower) | (df[col] > upper)].shape[0]
        outliers[col] = int(outlier_count)
    report["numeric_outliers"] = outliers
    # Potential leakage: check if any feature is identical to target
    leakage = []
    if target:
        for col in df.columns:
            if col == target:
                continue
            if df[col].equals(df[target]):
                leakage.append(col)
    report["potential_target_leakage"] = leakage
    return report

def save_report(report: dict, output_path: Path = None) -> Path:
    if output_path is None:
        output_path = Path(__file__).resolve().parents[2] / "data" / "validation_report.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
    return output_path
