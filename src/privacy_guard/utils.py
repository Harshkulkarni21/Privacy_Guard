import csv
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def parse_iso_date(value):
    if value in (None, ""):
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"true", "1", "yes"}:
            return True
        if text in {"false", "0", "no"}:
            return False
    return None


def stable_token(value, salt="privacy-guard"):
    if value is None:
        return None
    return hashlib.sha256(f"{salt}:{value}".encode("utf-8")).hexdigest()[:24]


def mask_value(value, preserve_chars=2):
    if value is None:
        return None
    text = str(value).strip()
    if len(text) <= preserve_chars * 2:
        return "*" * len(text)
    return text[:preserve_chars] + ("*" * max(len(text) - preserve_chars * 2, 1)) + text[-preserve_chars:]


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def read_csv_rows(path):
    with path.open("r", newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")


def count_occurrences(rows, key_name):
    return Counter(row.get(key_name) for row in rows)
