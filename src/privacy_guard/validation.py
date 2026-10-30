from __future__ import annotations

import re
from typing import Iterable

import pandas as pd


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_dataframe(df: pd.DataFrame, config: dict) -> tuple[pd.DataFrame, list[dict]]:
    schema_cfg = config.get("schema", {})
    required_cols = schema_cfg.get("required_columns", [])
    primary_key = schema_cfg.get("primary_key", "customer_id")
    validation_cfg = config.get("validation", {})
    rejects: list[dict] = []

    missing_columns = [col for col in required_cols if col not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    unknown_columns = [col for col in df.columns if col not in required_cols]
    if validation_cfg.get("reject_unknown_columns") and unknown_columns:
        for idx, col in enumerate(unknown_columns):
            rejects.append({
                "source_row_number": idx + 1,
                "record_key": None,
                "reject_reason": "unexpected_column",
                "rejection_stage": "validate",
                "field": col,
            })

    working = df.copy()
    for row_index, row in working.iterrows():
        row_no = int(row_index) + 1
        if row.isna().any() and any(col in required_cols for col in row.index):
            for col in required_cols:
                if pd.isna(row[col]):
                    rejects.append({
                        "source_row_number": row_no,
                        "record_key": row.get(primary_key),
                        "reject_reason": "missing_required_field",
                        "rejection_stage": "validate",
                        "field": col,
                    })

        email = row.get("email")
        if pd.notna(email) and not isinstance(email, str):
            email = str(email)
        if pd.notna(email) and not EMAIL_RE.match(str(email)):
            rejects.append({
                "source_row_number": row_no,
                "record_key": row.get(primary_key),
                "reject_reason": "invalid_email",
                "rejection_stage": "validate",
                "field": "email",
            })

        age = row.get("age")
        if pd.notna(age):
            try:
                age_value = int(age)
            except (TypeError, ValueError):
                rejects.append({
                    "source_row_number": row_no,
                    "record_key": row.get(primary_key),
                    "reject_reason": "invalid_age",
                    "rejection_stage": "validate",
                    "field": "age",
                })
                continue
            if age_value < validation_cfg.get("min_age", 18) or age_value > validation_cfg.get("max_age", 100):
                rejects.append({
                    "source_row_number": row_no,
                    "record_key": row.get(primary_key),
                    "reject_reason": "age_out_of_range",
                    "rejection_stage": "validate",
                    "field": "age",
                })

        balance = row.get("account_balance")
        if pd.notna(balance):
            try:
                balance_value = float(balance)
            except (TypeError, ValueError):
                rejects.append({
                    "source_row_number": row_no,
                    "record_key": row.get(primary_key),
                    "reject_reason": "invalid_balance",
                    "rejection_stage": "validate",
                    "field": "account_balance",
                })
            if balance_value < validation_cfg.get("max_negative_balance", 0):
                rejects.append({
                    "source_row_number": row_no,
                    "record_key": row.get(primary_key),
                    "reject_reason": "negative_balance",
                    "rejection_stage": "validate",
                    "field": "account_balance",
                })

        timestamp = row.get("updated_at")
        if pd.notna(timestamp):
            try:
                pd.to_datetime(timestamp)
            except (TypeError, ValueError):
                rejects.append({
                    "source_row_number": row_no,
                    "record_key": row.get(primary_key),
                    "reject_reason": "malformed_timestamp",
                    "rejection_stage": "validate",
                    "field": "updated_at",
                })

    if primary_key in working.columns:
        duplicate_mask = working[primary_key].duplicated(keep=False)
        if duplicate_mask.any():
            idxs = working[duplicate_mask].index.tolist()
            for idx in idxs:
                rejects.append({
                    "source_row_number": int(idx) + 1,
                    "record_key": working.at[idx, primary_key],
                    "reject_reason": "duplicate_primary_key",
                    "rejection_stage": "validate",
                    "field": primary_key,
                })
            working = working[~duplicate_mask].copy()

    return working, rejects
