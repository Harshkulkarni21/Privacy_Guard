# Performance report

Measured on the local sample dataset in the active workspace:

- elapsed_seconds: 0.0141
- customer_count: 20
- order_count: 60
- analytics_rows: 20
- rejected_rows: 0
- run_id: 5b285f73cebc

## Optimization note

This batch implementation is intentionally simple and file-based. For a 100k+ record workload, the next improvement would be to process rows in chunks and validate them incrementally so memory usage stays low while keeping deterministic masking behavior intact.
