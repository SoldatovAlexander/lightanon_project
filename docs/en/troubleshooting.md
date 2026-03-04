# Troubleshooting

## `ImportError: pyarrow is required for parquet support`
Cause:
- parquet dependency is missing.

Fix:
```bash
pip install -r requirements.txt
```

## `Warning: Unknown rule '...'`
Cause:
- YAML references a class not present in `lightanon.rules` or `lightanon.financial`.

Fix:
- verify class name and constructor parameters.

## A column is not transformed in `polars` mode
Cause:
- rule does not implement `apply_polars`.

Fix:
- inspect `engine.generate_report()` for `[FAIL]` entries,
- implement `apply_polars` for your custom rule.

## Stream processing is too slow
Cause:
- rules rely on fallback `apply_single` logic.

Fix:
- implement optimized `apply_single` in each rule used by `StreamEngine`.
