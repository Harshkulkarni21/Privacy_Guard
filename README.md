# Privacy Guard

Privacy Guard is a small data-engineering pipeline that profiles sensitive fields, validates source rows, applies deterministic masking/tokenization, and publishes a minimized analytical dataset with an audit trail.

## Architecture

The project has a simple batch pipeline:

1. Read customer and order CSV files.
2. Validate schema, required fields, duplicate keys, nulls, and referential integrity.
3. Build field profiles for sensitive columns and record data-quality findings.
4. Mask or tokenize sensitive values using stable hashes.
5. Aggregate valid orders by customer and publish a minimized analytical dataset.
6. Write a JSON audit trail and rejection report.

## Data model

### Customer source

| Column | Type | Rule |
| --- | --- | --- |
| customer_id | string | required, unique |
| email | string | required, valid email |
| first_name | string | required |
| last_name | string | required |
| dob | date | required, ISO-8601 |
| phone | string | required |
| ssn | string | required |
| address | string | required |
| city | string | required |
| state | string | required |
| signup_date | date | required |
| customer_tier | string | required |

### Order source

| Column | Type | Rule |
| --- | --- | --- |
| order_id | string | required, unique |
| customer_id | string | required, must exist in customer dataset |
| order_date | date | required |
| order_total | number | required, positive |
| channel | string | required |
| status | string | required |

## Processing rules

- Deterministic hashing is used for tokenization to keep reruns idempotent.
- Reject records are written to `rejects.csv` with source file and reason.
- Duplicate keys and invalid foreign keys are quarantined rather than silently overwritten.
- Example sensitive columns are detected using common field names such as `email`, `phone`, `ssn`, `dob`, `address`, and `first_name`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e .
python -m privacy_guard.cli generate-sample --output-dir data
python -m privacy_guard.cli process --customers data/customers.csv --orders data/orders.csv --output-dir outputs
pytest -q
```

## Output files

After processing, the outputs folder includes:

- `customer_analytics.csv`: minimized analytic dataset
- `customer_masked.csv`: masked customer view
- `field_profile.json`: sensitive-field profile summary
- `audit_log.json`: run metadata and output metrics
- `rejects.csv`: quarantined invalid records
- `manifest.json`: reference file for the current successful run

## Reproducibility and retry

The pipeline computes a deterministic run ID from the input content and schema configuration. Re-running the same input produces the same run ID and overwrites the same output folder safely. This keeps reruns idempotent without silently duplicating source records.

## Performance measurement

A sample end-to-end run with 20 customers and 60 orders completed in 0.05 seconds in the local environment, and the resulting analytics file contained 20 rows. For larger batches, the main bottleneck is row-by-row CSV validation; a sensible optimization is streaming reads in chunks and materializing only valid rows to avoid full in-memory copies.

## Design notes and trade-offs

The solution validates source rows early and preserves rejected records with source metadata so the operator can investigate failures. The trade-off is that the pipeline is intentionally simple and file-based rather than streaming to a distributed platform; this makes the project easier to run and test locally while still covering the required data-quality checks.

## Known limitations

- This is a batch pipeline, not a real-time streaming system.
- The sample data is synthetic and intentionally small for local reproducibility.
- Production replacements would likely add Parquet storage, orchestration, and richer policy controls.
