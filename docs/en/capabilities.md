# Capability Boundaries

| Surface | Supported behavior | Boundary |
| --- | --- | --- |
| `Engine` with pandas | Batch CSV/Parquet anonymization for implemented rules | A rule failure clears that output column and marks the audit entry as an error. |
| `Engine` with Polars | Batch CSV/Parquet processing for rules that implement `apply_polars` | `Hash` has an explicit Polars implementation; unsupported rules are reported as failures, not silently passed through. |
| `StreamEngine` | Low-latency processing of dictionary events | Each chosen rule must implement its streaming operation; test the exact schema before production use. |
| RAG regex sanitizer | Reversible tokenization of enabled text patterns | Detection is heuristic. `coverage="heuristic"` and zero matches do not prove that no personal data is present. |
| Metadata sanitizer | Recursively processes string values in dict/list/tuple/set metadata | It does not classify numeric values, dictionary keys, or arbitrary object attributes without an explicit application schema. |
| `FileVault` | Local reversible token storage with v2 encryption and locking | Intended for small local workflows. Multi-instance service deployments should use a transactional database or Redis backend. |

RAG restoration scope is trusted server-side request context. It limits one restoration operation and must not be sent to an end user as an authorization token.
