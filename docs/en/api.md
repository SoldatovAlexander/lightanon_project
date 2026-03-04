# API Reference

## Public Package Exports

```python
import lightanon as la
```

Available at top level:
- `la.Engine`
- `la.StreamEngine`
- `la.rules`
- `la.financial`
- `la.rag`

## `Engine` (Batch Processing)

Location: `lightanon.engine.Engine`

Purpose:
- process `pandas.DataFrame` or `polars.DataFrame`,
- apply schema rules by column,
- store audit information,
- produce compliance-like report.

Main methods:
- `Engine(schema: Dict[str, BaseRule])`
- `run(df)`
- `generate_report() -> str`

Audit behavior:
- `run(...)` resets `audit_log`,
- each schema column is marked with `Success`, `Missing column`, or `Error: ...`.

## `BaseRule`

Location: `lightanon.rules.BaseRule`

Interface methods:
- `apply(series: pd.Series) -> pd.Series` for batch/pandas.
- `apply_polars(col_name: str) -> pl.Expr` for batch/polars.
- `apply_single(value)` for stream events.

`apply_single` has a fallback implementation via `pandas` and may be slow.

## Core Rules (`lightanon.rules`)

### `Hash(salt: str = "")`
- deterministic SHA-256 hash,
- good for pseudonymous joins,
- handles `None/NaN` as `None`.

### `Mask(visible_chars: int = 1)`
- keeps first `visible_chars` chars and masks the rest with `*`,
- returns `None` for `None/NaN`.

### `GaussianNoise(std: float = 0.1)`
- adds additive Gaussian noise,
- formula per value: `x + N(0, x * std)`.

### `Generalize(step: int = 5)`
- converts numeric values to interval strings,
- example: `23 -> "20-25"`.

## Financial Rules (`lightanon.financial`)

### `MultiplicativeNoise(std_dev_percent: float = 0.05)`
- multiplicative perturbation,
- formula: `x * N(1.0, std)`.

### `TopCoding(quantile: float = 0.99)`
- clips values above quantile threshold.

### `CreditCardMask()`
- masks card number leaving last 4 digits.

### `TopCodingFixed(cap_value: float)`
- fixed cap for stream/event mode.

## `polars` Compatibility Note

In current implementation, `Engine` with `polars` requires rule-specific `apply_polars`.
At the moment, `Hash` includes explicit `apply_polars`; other rules may report `Error` in audit unless extended.
