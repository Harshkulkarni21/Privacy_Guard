from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd


class AuditStore:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.db_path))
        self._create_tables()

    def _create_tables(self):
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_runs (
                run_id VARCHAR PRIMARY KEY,
                source_file VARCHAR,
                source_fingerprint VARCHAR,
                pipeline_version VARCHAR,
                config_fingerprint VARCHAR,
                started_at TIMESTAMP,
                ended_at TIMESTAMP,
                status VARCHAR,
                input_rows BIGINT,
                valid_rows BIGINT,
                rejected_rows BIGINT,
                duplicates_removed BIGINT,
                output_rows BIGINT,
                error_code VARCHAR,
                sanitized_error_message VARCHAR,
                output_artifact VARCHAR
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_rejects (
                run_id VARCHAR,
                source_file VARCHAR,
                source_row_number BIGINT,
                record_key VARCHAR,
                reject_reason VARCHAR,
                rejection_stage VARCHAR
            );
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_quality_metrics (
                run_id VARCHAR,
                metric_name VARCHAR,
                metric_value VARCHAR,
                metric_status VARCHAR
            );
            """
        )

    def record_run(self, record: dict):
        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                run_id, source_file, source_fingerprint, pipeline_version, config_fingerprint,
                started_at, ended_at, status, input_rows, valid_rows, rejected_rows,
                duplicates_removed, output_rows, error_code, sanitized_error_message, output_artifact
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                record.get("run_id"),
                record.get("source_file"),
                record.get("source_fingerprint"),
                record.get("pipeline_version"),
                record.get("config_fingerprint"),
                record.get("started_at"),
                record.get("ended_at"),
                record.get("status"),
                record.get("input_rows"),
                record.get("valid_rows"),
                record.get("rejected_rows"),
                record.get("duplicates_removed"),
                record.get("output_rows"),
                record.get("error_code"),
                record.get("sanitized_error_message"),
                record.get("output_artifact"),
            ],
        )

    def record_rejects(self, rows: list[dict]):
        if not rows:
            return
        frame = pd.DataFrame(rows)
        self.conn.execute(
            "INSERT INTO pipeline_rejects (run_id, source_file, source_row_number, record_key, reject_reason, rejection_stage) VALUES (?, ?, ?, ?, ?, ?)",
            list(frame.itertuples(index=False, name=None)),
        )

    def record_metrics(self, run_id: str, metrics: dict):
        for name, payload in metrics.items():
            status = payload.get("status", "pass")
            value = payload.get("value")
            self.conn.execute(
                "INSERT INTO pipeline_quality_metrics (run_id, metric_name, metric_value, metric_status) VALUES (?, ?, ?, ?)",
                [run_id, name, json.dumps(value) if isinstance(value, (dict, list)) else str(value), status],
            )

    def close(self):
        self.conn.close()
