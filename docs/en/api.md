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

`la.rules` and `la.financial` contain rules for `Engine`/`StreamEngine`.
`la.rag` is a separate stateful block for reversible free-text sanitization before LLM/RAG calls.

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

## RAG Text Sanitization (`lightanon.rag`)

The RAG block is not a set of column-level `BaseRule` classes. It is a separate reversible pipeline for free text:
1. `sanitize(text)` replaces sensitive values with tokens,
2. the external LLM/RAG pipeline sees only tokens,
3. `deanonymize(text)` restores original values in the final answer.

Public exports:
- `TextSanitizer`
- `BaseVault`
- `MemoryVault`
- `FileVault`
- `Patterns`

### `TextSanitizer(vault: Optional[BaseVault] = None)`
- uses `MemoryVault` by default,
- stores `original value -> token` mappings,
- reuses the same token for repeated values,
- supports built-in regex patterns and custom rules.

Main methods:
- `sanitize(text: str) -> str`
- `deanonymize(text: str) -> str`
- `add_rule(name: str, pattern: str)`

Example:

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer()
clean = sanitizer.sanitize("Ivan Ivanov, email ivan@example.com")
answer = f"Contact: {clean}"
restored = sanitizer.deanonymize(answer)
```

### `BaseVault`
Abstract token-storage interface:
- `get_value(token: str)`
- `get_token(value: str)`
- `save(token: str, value: str)`

### `MemoryVault`
In-memory `BaseVault` implementation.
Useful for a single process/session, but does not persist data across restarts.

### `FileVault(path: str)`
JSON-backed `BaseVault` implementation for CLI and local RAG workflows.
Persists tokens to disk, so `sanitize` and `restore` can run in different processes.

### `Patterns`
Built-in regex patterns for email, RU phones, RU passport numbers, SNILS, INN, card numbers, and a broad RU full-name heuristic.

## `polars` Compatibility Note

In current implementation, `Engine` with `polars` requires rule-specific `apply_polars`.
At the moment, `Hash` includes explicit `apply_polars`; other rules may report `Error` in audit unless extended.
