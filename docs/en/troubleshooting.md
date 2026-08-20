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

## A column becomes empty after processing
Cause:
- the rule failed;
- for fail-closed behavior, LightAnon does not leave original values in the output file.

Fix:
- inspect `engine.generate_report()` for `[FAIL]` entries,
- fix rule parameters or the column data type,
- for `polars`, implement `apply_polars` for your custom rule if it is missing.

## Stream processing is too slow
Cause:
- rules rely on fallback `apply_single` logic.

Fix:
- implement optimized `apply_single` in each rule used by `StreamEngine`.
