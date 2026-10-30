from __future__ import annotations

from typing import Iterable

import pandas as pd


def detect_sensitive_fields(columns: Iterable[str]) -> dict[str, str]:
    sensitive_map = {
        "full_name": "mask",
        "email": "tokenize",
        "phone": "tokenize",
        "city": "generalize",
        "age": "generalize",
        "account_balance": "drop",
    }
    return {name: sensitive_map.get(name, "retain") for name in columns if name in sensitive_map}


def profile_dataframe(df: pd.DataFrame) -> dict:
    profile = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "columns": {},
    }
    for column in df.columns:
        series = df[column]
        non_null = series.dropna()
        profile["columns"][column] = {
            "null_count": int(series.isna().sum()),
            "null_rate": float(series.isna().mean()) if len(series) else 0.0,
            "distinct_count": int(non_null.nunique()),
            "distinct_rate": float(non_null.nunique() / len(series)) if len(series) else 0.0,
            "sample_values": non_null.head(5).tolist(),
        }
    return profile
