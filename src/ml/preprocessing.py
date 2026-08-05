# src/ml/preprocessing.py
from typing import List
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

def build_preprocessor(feature_df: pd.DataFrame) -> ColumnTransformer:
    categorical_cols: List[str] = [c for c in feature_df.columns if pd.api.types.is_object_dtype(feature_df[c]) or pd.api.types.is_categorical_dtype(feature_df[c])]
    numerical_cols: List[str] = [c for c in feature_df.columns if c not in categorical_cols]

    numeric_pipeline = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='median')),
        ('scaler', StandardScaler())
    ])

    categorical_pipeline = Pipeline(steps=[
        ('imputer', SimpleImputer(strategy='most_frequent')),
        ('onehot', OneHotEncoder(handle_unknown='ignore'))
    ])

    preprocessor = ColumnTransformer(transformers=[
        ('num', numeric_pipeline, numerical_cols),
        ('cat', categorical_pipeline, categorical_cols)
    ])
    return preprocessor
