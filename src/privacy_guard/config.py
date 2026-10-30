from __future__ import annotations

import os
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "pipeline.yaml"

CUSTOMER_SCHEMA = {
    "customer_id": {"required": True, "type": "string"},
    "email": {"required": True, "type": "string"},
    "first_name": {"required": True, "type": "string"},
    "last_name": {"required": True, "type": "string"},
    "dob": {"required": True, "type": "date"},
    "phone": {"required": True, "type": "string"},
    "ssn": {"required": True, "type": "string"},
    "address": {"required": True, "type": "string"},
    "city": {"required": True, "type": "string"},
    "state": {"required": True, "type": "string"},
    "signup_date": {"required": True, "type": "date"},
    "customer_tier": {"required": True, "type": "string"},
}

ORDER_SCHEMA = {
    "order_id": {"required": True, "type": "string"},
    "customer_id": {"required": True, "type": "string"},
    "order_date": {"required": True, "type": "date"},
    "order_total": {"required": True, "type": "number"},
    "channel": {"required": True, "type": "string"},
    "status": {"required": True, "type": "string"},
}

SENSITIVE_FIELDS = {
    "email": "tokenize",
    "phone": "tokenize",
    "ssn": "tokenize",
    "dob": "year_only",
    "first_name": "mask",
    "last_name": "mask",
    "address": "tokenize",
}

ORDER_ANALYTICS_FIELDS = [
    "customer_id",
    "customer_tier",
    "state",
    "signup_year",
    "order_count",
    "total_spend",
    "last_order_date",
    "email_token",
    "phone_token",
    "dob_year",
]


def load_config(path: str | Path | None = None) -> dict:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with config_path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    return loaded


def resolve_token_secret(config: dict) -> str:
    env_name = config.get("privacy", {}).get("token_secret_env", "PRIVACY_GUARD_TOKEN_SECRET")
    secret = os.getenv(env_name)
    if not secret:
        raise RuntimeError(f"Missing required environment variable: {env_name}")
    return secret
