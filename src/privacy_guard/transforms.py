from __future__ import annotations

import hashlib
import hmac

import pandas as pd


def tokenize_hmac(value: str, secret: str) -> str:
    if value is None or value == "":
        return ""
    digest = hmac.new(secret.encode("utf-8"), str(value).encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def mask_name(value: str) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    if len(text) <= 2:
        return "**"
    return text[0] + "*" * (len(text) - 2) + text[-1]


def generalize_city(value: str) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip().lower()


def generalize_age(age: object) -> str:
    if pd.isna(age):
        return "unknown"
    try:
        age_num = int(age)
    except (TypeError, ValueError):
        return "unknown"
    if age_num < 25:
        return "18-24"
    if age_num < 35:
        return "25-34"
    if age_num < 45:
        return "35-44"
    if age_num < 55:
        return "45-54"
    if age_num < 65:
        return "55-64"
    return "65+"


def apply_privacy_policy(df: pd.DataFrame, policy: dict, secret: str) -> pd.DataFrame:
    transformed = df.copy()
    for column, action in (policy or {}).items():
        if column not in transformed.columns:
            continue
        if action == "drop":
            transformed = transformed.drop(columns=[column])
            continue
        if action == "mask" and column == "full_name":
            transformed[column] = transformed[column].map(mask_name)
        elif action == "tokenize" and column in {"email", "phone"}:
            transformed[f"{column}_token"] = transformed[column].map(lambda v: tokenize_hmac(v, secret))
            transformed[column] = "[REDACTED]"
        elif action == "generalize" and column == "city":
            transformed["city_generalized"] = transformed[column].map(generalize_city)
            transformed[column] = transformed["city_generalized"]
        elif action == "generalize" and column == "age":
            transformed["age_band"] = transformed[column].map(generalize_age)
            transformed[column] = transformed["age_band"]
    return transformed
