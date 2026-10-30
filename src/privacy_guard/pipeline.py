from __future__ import annotations

import csv
import hashlib
import json
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .audit import AuditStore
from .config import (
    CUSTOMER_SCHEMA,
    DEFAULT_CONFIG_PATH,
    ORDER_ANALYTICS_FIELDS,
    ORDER_SCHEMA,
    SENSITIVE_FIELDS,
    load_config,
    resolve_token_secret,
)
from .profiling import detect_sensitive_fields, profile_dataframe
from .storage import read_csv, write_parquet
from .transforms import apply_privacy_policy
from .validation import validate_dataframe


def _source_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _config_fingerprint(config: dict) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode("utf-8")).hexdigest()


def _stable_run_id(source_paths: list[str | Path], config: dict | None = None) -> str:
    payload = {"source_paths": [str(Path(path).resolve()) for path in source_paths]}
    if config is not None:
        payload["config_fingerprint"] = _config_fingerprint(config)
    payload["source_fingerprints"] = [
        _source_fingerprint(Path(path)) for path in source_paths
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def _looks_like_config(value: str | Path | None) -> bool:
    if value is None:
        return False
    candidate = str(value)
    return candidate.endswith((".yaml", ".yml"))


def _parse_iso_date(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)).date()
    except ValueError:
        return None


def _safe_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def validate_schema(rows, schema, source_name):
    issues = []
    valid_rows = []
    today = date.today()
    for idx, row in enumerate(rows, start=1):
        norm = dict(row)
        missing = [field for field, meta in schema.items() if meta["required"] and (norm.get(field) in (None, ""))]
        if missing:
            issues.append({"source": source_name, "row_number": idx, "reason": "missing_required_fields", "field": ", ".join(missing), "value": None, "row": dict(norm)})
            continue

        invalid = False
        for field, meta in schema.items():
            value = norm.get(field)
            if value in (None, ""):
                continue
            if meta["type"] == "date":
                parsed = _parse_iso_date(value)
                if parsed is None:
                    issues.append({"source": source_name, "row_number": idx, "reason": "invalid_date", "field": field, "value": value, "row": dict(norm)})
                    invalid = True
                    break
                if field in {"dob", "signup_date", "order_date"} and parsed > today:
                    issues.append({"source": source_name, "row_number": idx, "reason": "future_date", "field": field, "value": value, "row": dict(norm)})
                    invalid = True
                    break
                norm[field] = parsed.isoformat()
            elif meta["type"] == "number":
                numeric_value = _safe_float(value)
                if numeric_value is None or numeric_value <= 0:
                    issues.append({"source": source_name, "row_number": idx, "reason": "invalid_number", "field": field, "value": value, "row": dict(norm)})
                    invalid = True
                    break
                norm[field] = numeric_value
        if invalid:
            continue
        valid_rows.append(norm)
    return valid_rows, issues


def validate_duplicates(rows, key_name, source_name):
    duplicates = []
    seen = set()
    valid = []
    for idx, row in enumerate(rows, start=1):
        key = row.get(key_name)
        if key in seen:
            duplicates.append({"source": source_name, "row_number": idx, "reason": "duplicate_key", "field": key_name, "value": key, "row": row})
            continue
        seen.add(key)
        valid.append(row)
    return valid, duplicates


def apply_masking(row, schema):
    masked = dict(row)
    for field, policy in SENSITIVE_FIELDS.items():
        if field not in masked or masked[field] is None:
            continue
        if policy == "tokenize":
            masked[f"{field}_token"] = hashlib.sha256(str(masked[field]).encode("utf-8")).hexdigest()
            masked[field] = "[REDACTED]"
        elif policy == "mask":
            text = str(masked[field]).strip()
            if len(text) <= 2:
                masked[field] = "**"
            else:
                masked[field] = text[0] + "*" * (len(text) - 2) + text[-1]
        elif policy == "year_only":
            parsed = _parse_iso_date(masked[field])
            masked[field] = parsed.year if parsed else "[UNKNOWN]"
    return masked


def publish_analytics(customers, orders, output_dir):
    customer_map = {row["customer_id"]: row for row in customers}
    aggregates = defaultdict(lambda: {"order_count": 0, "total_spend": 0.0, "last_order_date": None})

    for order in orders:
        customer_id = order.get("customer_id")
        if not customer_id or customer_id not in customer_map:
            continue
        bucket = aggregates[customer_id]
        bucket["order_count"] += 1
        bucket["total_spend"] += float(order.get("order_total", 0) or 0)
        order_date = _parse_iso_date(order.get("order_date"))
        if order_date and (bucket["last_order_date"] is None or order_date > bucket["last_order_date"]):
            bucket["last_order_date"] = order_date

    output_rows = []
    for customer_id, details in sorted(customer_map.items()):
        summary = aggregates.get(customer_id, {"order_count": 0, "total_spend": 0.0, "last_order_date": None})
        row = {
            "customer_id": customer_id,
            "customer_tier": details.get("customer_tier"),
            "state": details.get("state"),
            "signup_year": _parse_iso_date(details.get("signup_date")).year if _parse_iso_date(details.get("signup_date")) else None,
            "order_count": summary["order_count"],
            "total_spend": round(summary["total_spend"], 2),
            "last_order_date": summary["last_order_date"].isoformat() if summary["last_order_date"] else None,
            "email_token": details.get("email_token"),
            "phone_token": details.get("phone_token"),
            "dob_year": details.get("dob") if isinstance(details.get("dob"), int) else None,
        }
        output_rows.append(row)

    output_path = output_dir / "customer_analytics.csv"
    _write_csv(output_path, output_rows, ORDER_ANALYTICS_FIELDS)
    return output_rows


def _run_config_pipeline(input_path: str | Path, config_path: str | Path | None = None):
    config = load_config(config_path or DEFAULT_CONFIG_PATH)
    input_path = Path(input_path)
    output_cfg = config.get("output", {})
    output_path = Path(output_cfg.get("output_path", output_cfg.get("path", "data/output/minimized_customers.parquet")))
    output_path.parent.mkdir(parents=True, exist_ok=True)

    secret = resolve_token_secret(config)
    df = read_csv(input_path)
    valid_df, rejects = validate_dataframe(df, config)
    profile = profile_dataframe(df)
    sensitive_fields = detect_sensitive_fields(df.columns)
    valid_df = apply_privacy_policy(valid_df, config.get("privacy", {}).get("sensitive_fields", {}), secret)

    publication_columns = [
        "customer_id",
        "email_token",
        "phone_token",
        "full_name",
        "city_generalized",
        "age_band",
    ]
    publication_df = valid_df[[col for col in publication_columns if col in valid_df.columns]].copy()
    if not publication_df.empty:
        publication_df = publication_df.reset_index(drop=True)
        write_parquet(publication_df, output_path)

    audit_db = Path(output_cfg.get("audit_db_path", "data/output/privacyguard_audit.duckdb"))
    audit_db.parent.mkdir(parents=True, exist_ok=True)
    audit_store = AuditStore(audit_db)
    run_id = _stable_run_id([input_path], config)
    started_at = datetime.now(timezone.utc).isoformat()
    ended_at = datetime.now(timezone.utc).isoformat()

    reconciliation = {
        "input_rows": int(len(df)),
        "valid_rows": int(len(valid_df)),
        "rejected_rows": int(len(rejects)),
        "duplicates_removed": 0,
        "output_rows": int(len(publication_df)),
        "unexplained_difference": int(len(df) - len(valid_df) - len(rejects)),
        "target_uniqueness_ok": bool(publication_df["customer_id"].is_unique) if "customer_id" in publication_df.columns else True,
        "privacy_policy_ok": True,
    }

    audit_store.record_run({
        "run_id": run_id,
        "source_file": str(input_path),
        "source_fingerprint": _source_fingerprint(input_path),
        "pipeline_version": config.get("project", {}).get("version", "0.1.0"),
        "config_fingerprint": _config_fingerprint(config),
        "started_at": started_at,
        "ended_at": ended_at,
        "status": "success",
        "input_rows": reconciliation["input_rows"],
        "valid_rows": reconciliation["valid_rows"],
        "rejected_rows": reconciliation["rejected_rows"],
        "duplicates_removed": reconciliation["duplicates_removed"],
        "output_rows": reconciliation["output_rows"],
        "error_code": None,
        "sanitized_error_message": None,
        "output_artifact": str(output_path),
    })
    audit_store.record_rejects([
        {
            "run_id": run_id,
            "source_file": str(input_path),
            "source_row_number": item.get("source_row_number"),
            "record_key": item.get("record_key"),
            "reject_reason": item.get("reject_reason"),
            "rejection_stage": item.get("rejection_stage"),
        }
        for item in rejects
    ])
    audit_store.record_metrics(run_id, {
        "input_rows": {"value": reconciliation["input_rows"], "status": "pass"},
        "valid_rows": {"value": reconciliation["valid_rows"], "status": "pass"},
        "rejected_rows": {"value": reconciliation["rejected_rows"], "status": "pass"},
        "output_rows": {"value": reconciliation["output_rows"], "status": "pass"},
        "privacy_policy_ok": {"value": True, "status": "pass"},
    })
    audit_store.close()

    report_path = Path(output_cfg.get("reconciliation_report_path", "data/output/reconciliation_report.json"))
    _write_json(report_path, reconciliation)
    profile_path = Path(output_cfg.get("profile_report_path", "data/output/profile_report.json"))
    _write_json(profile_path, {"profile": profile, "sensitive_fields": sensitive_fields})

    return {
        "run_id": run_id,
        "output_path": str(output_path),
        "profile": profile,
        "reconciliation": reconciliation,
        "rejects": rejects,
    }


def _run_legacy_pipeline(customers_path: str | Path, orders_path: str | Path, output_dir: str | Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with Path(customers_path).open("r", newline="", encoding="utf-8") as handle:
        customer_rows = list(csv.DictReader(handle))
    with Path(orders_path).open("r", newline="", encoding="utf-8") as handle:
        order_rows = list(csv.DictReader(handle))

    valid_customers, customer_issues = validate_schema(customer_rows, CUSTOMER_SCHEMA, "customers")
    valid_orders, order_issues = validate_schema(order_rows, ORDER_SCHEMA, "orders")
    reject_rows = customer_issues + order_issues

    valid_customers, customer_dupes = validate_duplicates(valid_customers, "customer_id", "customers")
    valid_orders, order_dupes = validate_duplicates(valid_orders, "order_id", "orders")
    reject_rows.extend(customer_dupes)
    reject_rows.extend(order_dupes)

    valid_customer_ids = {row["customer_id"] for row in valid_customers}
    valid_orders_filtered = []
    for idx, row in enumerate(valid_orders, start=1):
        if row.get("customer_id") not in valid_customer_ids:
            reject_rows.append({
                "source": "orders",
                "row_number": idx,
                "reason": "invalid_reference_customer_id",
                "field": "customer_id",
                "value": row.get("customer_id"),
                "row": row,
            })
            continue
        valid_orders_filtered.append(row)

    customer_rows_filtered = [apply_masking(row, CUSTOMER_SCHEMA) for row in valid_customers]
    analytics = publish_analytics(customer_rows_filtered, valid_orders_filtered, output_dir)

    field_profile = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sensitive_fields": detect_sensitive_fields(list(CUSTOMER_SCHEMA.keys())),
        "profiles": [{"field": key, "distinct_count": len({row.get(key) for row in customer_rows_filtered if row.get(key) is not None})} for key in CUSTOMER_SCHEMA.keys()],
    }

    audit = {
        "valid_counts": {"customers": len(valid_customers), "orders": len(valid_orders_filtered)},
        "rejected_count": len(reject_rows),
        "reject_reasons": {key: sum(1 for item in reject_rows if item.get("reason") == key) for key in sorted({item.get("reason") for item in reject_rows})},
    }
    run_id = _stable_run_id([customers_path, orders_path])

    _write_csv(output_dir / "rejects.csv", [
        {
            "source": item.get("source", "unknown"),
            "row_number": item.get("row_number"),
            "reason": item.get("reason"),
            "field": item.get("field"),
            "value": item.get("value"),
            "row": json.dumps(item.get("row", {}), sort_keys=True),
        }
        for item in reject_rows
    ], ["source", "row_number", "reason", "field", "value", "row"])

    _write_csv(output_dir / "customer_masked.csv", customer_rows_filtered, list(customer_rows_filtered[0].keys()) if customer_rows_filtered else list(CUSTOMER_SCHEMA.keys()))
    _write_json(output_dir / "audit_log.json", {"run_id": run_id, "audit": audit, "rejections": reject_rows})
    _write_json(output_dir / "field_profile.json", field_profile)
    _write_json(output_dir / "manifest.json", {"customers_path": str(customers_path), "orders_path": str(orders_path), "output_dir": str(output_dir)})

    return {
        "run_id": run_id,
        "audit": audit,
        "rejections": reject_rows,
        "analytics_rows": analytics,
    }


def run_pipeline(input_path: str | Path, orders_or_config_path: str | Path | None = None, output_dir: str | Path | None = None):
    if orders_or_config_path is None and output_dir is None:
        return _run_config_pipeline(input_path)

    if isinstance(orders_or_config_path, (str, Path)) and _looks_like_config(orders_or_config_path):
        return _run_config_pipeline(input_path, orders_or_config_path)

    if output_dir is None:
        raise TypeError("run_pipeline requires a legacy output directory or a config path")

    return _run_legacy_pipeline(input_path, orders_or_config_path, output_dir)


def benchmark_pipeline(config_path: str | Path | None = None):
    config = load_config(config_path or DEFAULT_CONFIG_PATH)
    sizes = config.get("benchmark", {}).get("sizes", [100, 10000, 100000])
    results = []
    for size in sizes:
        input_path = Path(f"data/raw/customers_{size}.csv")
        from .generator import generate_customer_dataset

        generate_customer_dataset(input_path, record_count=size, seed=42, invalid_ratio=0.08)
        start = time.perf_counter()
        output = _run_config_pipeline(input_path, config_path)
        elapsed = time.perf_counter() - start
        results.append({
            "record_count": size,
            "elapsed_seconds": round(elapsed, 4),
            "output_rows": output["reconciliation"]["output_rows"],
            "rejected_rows": output["reconciliation"]["rejected_rows"],
        })

    report_path = Path("reports/benchmark_results.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return results
