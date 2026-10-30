from __future__ import annotations

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

from faker import Faker


DEFAULT_FIELDS = [
    "customer_id",
    "full_name",
    "email",
    "phone",
    "age",
    "city",
    "account_balance",
    "updated_at",
]


def _make_invalid_row(index: int, customer_id: str) -> dict:
    invalids = [
        {"customer_id": customer_id, "full_name": "", "email": "bad-email", "phone": "999", "age": 17, "city": "Paris", "account_balance": -5, "updated_at": "not-a-date"},
        {"customer_id": customer_id, "full_name": "Jane Doe", "email": "jane@example.com", "phone": "555-123-4567", "age": 150, "city": "Berlin", "account_balance": "NaN", "updated_at": "2024-13-01"},
        {"customer_id": customer_id, "full_name": None, "email": "", "phone": "", "age": None, "city": "Rome", "account_balance": 0, "updated_at": "2024-02-30"},
    ]
    return invalids[index % len(invalids)]


def generate_customer_dataset(path: str | Path, record_count: int = 100, seed: int = 42, invalid_ratio: float = 0.1):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    fake = Faker()
    Faker.seed(seed)

    rows: list[dict] = []
    for idx in range(record_count):
        customer_id = f"CUST-{idx + 1:05d}"
        if invalid_ratio and idx % max(1, int(1 / invalid_ratio)) == 0:
            rows.append(_make_invalid_row(idx, customer_id))
            continue
        rows.append(
            {
                "customer_id": customer_id,
                "full_name": fake.name(),
                "email": fake.email(),
                "phone": fake.phone_number(),
                "age": random.randint(18, 90),
                "city": random.choice(["Seattle", "Austin", "Boston", "Denver", "Chicago", "Miami"]),
                "account_balance": round(random.uniform(25.0, 5000.0), 2),
                "updated_at": (datetime(2023, 1, 1) + timedelta(days=random.randint(0, 365))).strftime("%Y-%m-%d"),
            }
        )

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEFAULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def generate_sample_dataset(path: str | Path = "data/raw/customers.csv", seed: int = 42):
    generate_customer_dataset(path, record_count=100, seed=seed, invalid_ratio=0.1)


def generate_medium_dataset(path: str | Path = "data/raw/customers_medium.csv", seed: int = 42):
    generate_customer_dataset(path, record_count=10000, seed=seed, invalid_ratio=0.08)


def generate_large_dataset(path: str | Path = "data/raw/customers_large.csv", seed: int = 42):
    generate_customer_dataset(path, record_count=100000, seed=seed, invalid_ratio=0.05)
