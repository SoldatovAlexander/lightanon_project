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

### `TextSanitizer(vault: Optional[BaseVault] = None, enabled_rules=None, rules=None, profile="basic")`
- uses `MemoryVault` by default,
- stores `original value -> token` mappings,
- reuses the same token for repeated values,
- supports built-in regex patterns and custom rules,
- can enable only selected built-in rules with `enabled_rules`,
- can accept an explicit rule list with `rules=[("EMAIL", Patterns.EMAIL), ...]`,
- supports rule profiles: `basic`, `ru_152`, `ru_152_strict`.

Main methods:
- `sanitize(text: str) -> str`
- `sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]`
- `deanonymize_metadata(metadata: Dict[str, Any], policy: str = "restore", allowed_entity_types=None) -> Dict[str, Any]`
- `sanitize_document(text: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]`
- `deanonymize_document(text: str, metadata: Optional[Dict[str, Any]] = None, policy: str = "restore", allowed_entity_types=None) -> Tuple[str, Dict[str, Any]]`
- `scan(text: str) -> Dict[str, object]`
- `sanitize_with_report(text: str) -> Tuple[str, Dict[str, object]]`
- `deanonymize(text: str, policy: str = "restore", allowed_entity_types=None) -> str`
- `add_rule(name: str, pattern: str)`

Built-in rules: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`.
`INN` is disabled by default so bare 10/12 digit numbers do not conflict with document patterns without context.
`ONLINE_ACCOUNT` targets combined online identifiers such as `nickname ivan_dev on Habr` or `Telegram: @ivanov` and tokenizes the pair as one entity.
Configuration priority: `rules` > `enabled_rules` > `profile`.

Example:

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer()
clean = sanitizer.sanitize("Ivan Ivanov, email ivan@example.com")
answer = f"Contact: {clean}"
restored = sanitizer.deanonymize(answer)
```

`sanitize_metadata(...)` recursively sanitizes string values in `dict`, `list`, `tuple`, and `set` containers while preserving non-string values. This is useful for RAG documents where personal data may live in `source_url`, `author`, `tags`, `file_path`, and other metadata fields.
`deanonymize_metadata(...)` performs symmetric metadata restoration with the same policies as `deanonymize(...)`.
`sanitize_document(...)` and `deanonymize_document(...)` process text and metadata in one operation with a shared vault.

`scan(...)` detects entities without replacing text or writing to the vault. The report contains type counters and risk level, but not original values.
`sanitize_with_report(...)` returns sanitized text plus a report with entities before processing and residual entities after processing.
`deanonymize(...)` supports restoration policies: `restore` restores all values, `no_personal_data` leaves tokens unchanged, `mask` replaces tokens with `[TYPE]`, and `restore_allowed_only` restores only types listed in `allowed_entity_types`.

### `BaseVault`
Abstract token-storage interface:
- `get_value(token: str)`
- `get_token(value: str)`
- `save(token: str, value: str, ttl_seconds: Optional[int] = None)`
- `delete_token(token: str) -> bool`
- `delete_value(value: str) -> bool`
- `clear() -> None`
- `purge_expired() -> int`

### `MemoryVault`
In-memory `BaseVault` implementation.
Useful for a single process/session, but does not persist data across restarts.

### `FileVault(path: str, default_ttl_seconds: Optional[int] = None)`
JSON-backed `BaseVault` implementation for CLI and local RAG workflows.
Persists tokens to disk, so `sanitize` and `restore` can run in different processes.
Writes use a temporary file followed by atomic replacement.
Invalid JSON or invalid vault structure raises `ValueError`.
New entries store `created_at`, `last_used_at`, and `expires_at` when TTL is configured; older vault format is read automatically.

Additional method:
- `stats() -> Dict[str, object]`: returns path, total mappings, token-type counters, and timestamp/expiration availability without original values.

### `Patterns`
Built-in regex patterns for email, RU phones, RU passport numbers, SNILS, INN, card numbers, online identifiers, and a broad RU full-name heuristic.
The passport pattern requires a separator before the 6-digit number, for example `4500 123456`, to avoid classifying a 10-digit INN as a passport.

## `polars` Compatibility Note

In current implementation, `Engine` with `polars` requires rule-specific `apply_polars`.
At the moment, `Hash` includes explicit `apply_polars`; other rules may report `Error` in audit unless extended.
