# RAG Guide

`lightanon.rag` is for reversible text sanitization:
1. sanitize sensitive text before LLM call,
2. de-anonymize model output for the end user.

It is a separate stateful block, not an `Engine` rule: it stores mappings between original values and tokens in a `Vault`.

## Quick Example

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer()

original = "Applicant Ivan Ivanov, passport 4500 123456, phone +7 900 123-45-67."
sanitized = sanitizer.sanitize(original)

# Simulated LLM output
response = f"Confirmed: {sanitized}"
restored = sanitizer.deanonymize(response)

print(sanitized)
print(restored)
```

## Built-in Patterns
Default `TextSanitizer` rules include:
- email,
- RU phone,
- RU passport,
- SNILS,
- card numbers,
- broad RU full-name pattern.

The built-in `INN` rule is also available, but disabled by default: bare 10/12 digit numbers can easily conflict with other document patterns without context. Enable it explicitly:

```python
sanitizer = TextSanitizer(enabled_rules=["EMAIL", "PHONE", "INN"])
```

The public `Patterns` class can be reused when configuring custom rules.

For full control, pass an explicit rule list:

```python
from lightanon.rag import Patterns, TextSanitizer

sanitizer = TextSanitizer(rules=[("EMAIL", Patterns.EMAIL)])
```

## Custom Pattern

```python
sanitizer.add_rule("CONTRACT", r"\b\d{2}-\d{4}/\d{2}\b")
```

Custom rules are inserted with higher priority than built-in rules.

## Vault
Default backend: `MemoryVault`.
- fast,
- in-memory only,
- not persistent across restarts.

For production, implement your own `BaseVault` backend.

Minimum `BaseVault` interface:
- `get_value(token: str)`,
- `get_token(value: str)`,
- `save(token: str, value: str)`.

`FileVault` stores mappings in a JSON file and is useful for local CLI workflows:

```python
from lightanon.rag import FileVault, TextSanitizer

sanitizer = TextSanitizer(vault=FileVault("vault.json"))
```

`FileVault` validates JSON structure on read and writes changes through a temporary file followed by atomic replacement. `stats()` returns counters only, without original values.

## CLI

RAG commands work with plain text files and require `--vault` so restoration can happen in a separate run:

```bash
lightanon rag sanitize input.txt sanitized.txt --vault vault.json
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag inspect-vault vault.json
```

`sanitize` writes tokens to the vault. `restore` uses the same vault to replace tokens with original values.
`inspect-vault` prints saved mapping counts and token-type distribution without revealing stored values.
`--rules` enables only the listed built-in rules and is useful when you need to disable the broad name heuristic or explicitly enable `INN`.
