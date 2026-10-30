import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from privacy_guard.pipeline import run_pipeline
from privacy_guard.storage import write_parquet


def write_csv(path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_happy_path_pipeline(tmp_path):
    customers = [
        {
            "customer_id": "CUST-00001",
            "email": "alice@example.com",
            "first_name": "Alice",
            "last_name": "Jones",
            "dob": "1990-01-05",
            "phone": "415-555-0101",
            "ssn": "123-45-6789",
            "address": "1 Market St",
            "city": "San Francisco",
            "state": "CA",
            "signup_date": "2023-01-10",
            "customer_tier": "gold",
        },
        {
            "customer_id": "CUST-00002",
            "email": "bob@example.com",
            "first_name": "Bob",
            "last_name": "Smith",
            "dob": "1987-09-21",
            "phone": "212-555-0202",
            "ssn": "987-65-4321",
            "address": "2 Broad Ave",
            "city": "New York",
            "state": "NY",
            "signup_date": "2022-07-04",
            "customer_tier": "silver",
        },
    ]
    orders = [
        {
            "order_id": "ORD-00001",
            "customer_id": "CUST-00001",
            "order_date": "2024-02-01",
            "order_total": "120.50",
            "channel": "web",
            "status": "paid",
        },
        {
            "order_id": "ORD-00002",
            "customer_id": "CUST-00002",
            "order_date": "2024-02-03",
            "order_total": "95.00",
            "channel": "mobile",
            "status": "shipped",
        },
    ]
    customer_path = tmp_path / "customers.csv"
    order_path = tmp_path / "orders.csv"
    output_dir = tmp_path / "outputs"
    write_csv(customer_path, list(customers[0].keys()), customers)
    write_csv(order_path, list(orders[0].keys()), orders)

    result = run_pipeline(customer_path, order_path, output_dir)

    assert result["audit"]["rejected_count"] == 0
    assert len(result["analytics_rows"]) == 2
    assert (output_dir / "customer_analytics.csv").exists()
    assert (output_dir / "customer_masked.csv").exists()
    assert (output_dir / "audit_log.json").exists()


def test_empty_input_is_handled_gracefully(tmp_path):
    customer_path = tmp_path / "customers.csv"
    order_path = tmp_path / "orders.csv"
    output_dir = tmp_path / "outputs"
    write_csv(customer_path, ["customer_id", "email", "first_name", "last_name", "dob", "phone", "ssn", "address", "city", "state", "signup_date", "customer_tier"], [])
    write_csv(order_path, ["order_id", "customer_id", "order_date", "order_total", "channel", "status"], [])

    result = run_pipeline(customer_path, order_path, output_dir)

    assert result["audit"]["valid_counts"]["customers"] == 0
    assert result["audit"]["valid_counts"]["orders"] == 0
    assert result["audit"]["rejected_count"] == 0
    assert (output_dir / "customer_analytics.csv").exists()


def test_malformed_and_duplicate_records_are_quarantined(tmp_path):
    customers = [
        {
            "customer_id": "CUST-00004",
            "email": "dupe@example.com",
            "first_name": "Dana",
            "last_name": "Grey",
            "dob": "1992-02-04",
            "phone": "555-222-3333",
            "ssn": "222-22-2222",
            "address": "99 Oak Rd",
            "city": "Austin",
            "state": "TX",
            "signup_date": "2021-08-09",
            "customer_tier": "gold",
        },
        {
            "customer_id": "CUST-00004",
            "email": "dupe@example.com",
            "first_name": "Dana",
            "last_name": "Grey",
            "dob": "1992-02-04",
            "phone": "555-222-3333",
            "ssn": "222-22-2222",
            "address": "99 Oak Rd",
            "city": "Austin",
            "state": "TX",
            "signup_date": "2021-08-09",
            "customer_tier": "gold",
        },
        {
            "customer_id": "CUST-00005",
            "email": "bad-email",
            "first_name": "Eve",
            "last_name": "Rivers",
            "dob": "not-a-date",
            "phone": "",
            "ssn": "111-11-1111",
            "address": "77 Pine St",
            "city": "Denver",
            "state": "CO",
            "signup_date": "2020-04-01",
            "customer_tier": "silver",
        },
    ]
    orders = [
        {
            "order_id": "ORD-00010",
            "customer_id": "CUST-00004",
            "order_date": "2024-02-11",
            "order_total": "abc",
            "channel": "web",
            "status": "paid",
        },
        {
            "order_id": "ORD-00010",
            "customer_id": "CUST-00004",
            "order_date": "2024-02-11",
            "order_total": "23.11",
            "channel": "web",
            "status": "paid",
        },
        {
            "order_id": "ORD-00011",
            "customer_id": "CUST-99999",
            "order_date": "2024-02-12",
            "order_total": "15.00",
            "channel": "web",
            "status": "paid",
        },
    ]
    customer_path = tmp_path / "customers.csv"
    order_path = tmp_path / "orders.csv"
    output_dir = tmp_path / "outputs"
    write_csv(customer_path, list(customers[0].keys()), customers)
    write_csv(order_path, list(orders[0].keys()), orders)

    result = run_pipeline(customer_path, order_path, output_dir)

    reasons = {item["reason"] for item in result["rejections"]}
    assert "duplicate_key" in reasons or "invalid_reference_customer_id" in reasons or "invalid_number" in reasons
    assert (output_dir / "rejects.csv").exists()


def test_missing_required_fields_covered(tmp_path):
    customers = [{
        "customer_id": "CUST-00009",
        "email": "",
        "first_name": "Frank",
        "last_name": "Bell",
        "dob": "1994-03-04",
        "phone": "",
        "ssn": "000-11-0000",
        "address": "41 River Way",
        "city": "Boston",
        "state": "MA",
        "signup_date": "2022-01-02",
        "customer_tier": "bronze",
    }]
    orders = [{
        "order_id": "ORD-00020",
        "customer_id": "CUST-00009",
        "order_date": "2024-03-07",
        "order_total": "99.99",
        "channel": "web",
        "status": "paid",
    }]
    customer_path = tmp_path / "customers.csv"
    order_path = tmp_path / "orders.csv"
    output_dir = tmp_path / "outputs"
    write_csv(customer_path, list(customers[0].keys()), customers)
    write_csv(order_path, list(orders[0].keys()), orders)

    result = run_pipeline(customer_path, order_path, output_dir)

    assert result["audit"]["rejected_count"] >= 1
    assert any(item["reason"] == "missing_required_fields" for item in result["rejections"])


def test_domain_specific_edge_cases_for_weak_customer_reference_and_future_date(tmp_path):
    customers = [{
        "customer_id": "CUST-00023",
        "email": "grace@example.com",
        "first_name": "Grace",
        "last_name": "Miller",
        "dob": "1998-11-18",
        "phone": "555-111-0000",
        "ssn": "321-11-9999",
        "address": "37 Cedar Dr",
        "city": "Portland",
        "state": "OR",
        "signup_date": "2024-01-10",
        "customer_tier": "gold",
    }]
    orders = [{
        "order_id": "ORD-00050",
        "customer_id": "MISSING-001",
        "order_date": "2025-03-01",
        "order_total": "50.00",
        "channel": "partner",
        "status": "pending",
    }]
    customer_path = tmp_path / "customers.csv"
    order_path = tmp_path / "orders.csv"
    output_dir = tmp_path / "outputs"
    write_csv(customer_path, list(customers[0].keys()), customers)
    write_csv(order_path, list(orders[0].keys()), orders)

    result = run_pipeline(customer_path, order_path, output_dir)

    assert any(item["reason"] == "invalid_reference_customer_id" for item in result["rejections"])
    assert result["audit"]["valid_counts"]["customers"] == 1
    assert result["audit"]["valid_counts"]["orders"] == 0


def test_run_ids_are_stable_for_the_same_input(tmp_path):
    customers = [{
        "customer_id": "CUST-00009",
        "email": "frank@example.com",
        "first_name": "Frank",
        "last_name": "Bell",
        "dob": "1994-03-04",
        "phone": "555-111-2345",
        "ssn": "000-11-0000",
        "address": "41 River Way",
        "city": "Boston",
        "state": "MA",
        "signup_date": "2022-01-02",
        "customer_tier": "bronze",
    }]
    orders = [{
        "order_id": "ORD-00020",
        "customer_id": "CUST-00009",
        "order_date": "2024-03-07",
        "order_total": "99.99",
        "channel": "web",
        "status": "paid",
    }]
    customer_path = tmp_path / "customers.csv"
    order_path = tmp_path / "orders.csv"
    output_dir = tmp_path / "outputs"
    write_csv(customer_path, list(customers[0].keys()), customers)
    write_csv(order_path, list(orders[0].keys()), orders)

    first = run_pipeline(customer_path, order_path, output_dir)
    second = run_pipeline(customer_path, order_path, output_dir)

    assert first["run_id"] == second["run_id"]


def test_parquet_write_failure_keeps_previous_output_intact(tmp_path, monkeypatch):
    output_path = tmp_path / "customer_analytics.parquet"
    output_path.write_bytes(b"previous-good-output")
    df = pd.DataFrame({"customer_id": ["CUST-00001"], "email_token": ["abc123"]})

    def boom(self, *args, **kwargs):
        target = Path(args[0]) if args else Path(kwargs.get("path"))
        target.write_bytes(b"partial-write")
        raise OSError("simulated disk write failure")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", boom)

    with pytest.raises(OSError, match="simulated disk write failure"):
        write_parquet(df, output_path)

    assert output_path.read_bytes() == b"previous-good-output"
    assert not any(path.name.endswith(".tmp") for path in output_path.parent.iterdir())
