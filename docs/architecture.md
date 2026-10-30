# Pipeline architecture

```mermaid
flowchart LR
A[Source CSV files] --> B[Schema validation]
B --> C[Duplicate and referential checks]
C --> D[Reject / quarantine]
C --> E[Sensitive field profiling]
E --> F[Mask and tokenize columns]
F --> G[Minimized analytics dataset]
D --> H[Audit log and rejects report]
G --> I[Operator review]
```

## Notes

- Validation happens before masking so malformed records never reach the published dataset.
- The same deterministic hashing strategy is used for reruns, which keeps tokenization stable.
- The reject report contains source metadata and failure reasons for traceability.
