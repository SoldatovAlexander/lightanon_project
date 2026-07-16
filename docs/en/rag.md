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

For safer output, control restoration with policies:

```python
sanitizer.deanonymize(response, policy="no_personal_data")
sanitizer.deanonymize(response, policy="mask")
sanitizer.deanonymize(response, policy="restore_allowed_only", allowed_entity_types=["EMAIL"])
```

The default `restore` policy preserves existing behavior and restores all known tokens.

## Built-in Patterns
Default `TextSanitizer` rules include:
- email,
- RU phone,
- RU passport,
- SNILS,
- card numbers,
- broad RU full-name pattern.

Rule profiles:
- `basic`: current default baseline;
- `ru_152`: `basic` + `INN` + online identifiers;
- `ru_152_strict`: `ru_152` + IP addresses, cookie/session IDs, device/client IDs, and user IDs.

```python
sanitizer = TextSanitizer(profile="ru_152")
```

Configuration priority: `rules` > `enabled_rules` > `profile`.

The built-in `INN` rule is also available, but disabled by default: bare 10/12 digit numbers can easily conflict with other document patterns without context. Enable it explicitly:

```python
sanitizer = TextSanitizer(enabled_rules=["EMAIL", "PHONE", "INN"])
```

Online identifier rules are available:
- `ONLINE_ACCOUNT`: combined pairs such as `nickname ivan_dev on Habr`, `Telegram: @ivanov`;
- `PROFILE_URL`: profile links such as `github.com/ivan_dev`, `vk.com/id123456`, `t.me/ivanov`;
- `SOCIAL_HANDLE`: handles such as `@ivan_dev`;
- `USERNAME`: explicitly labelled logins such as `login: petrov`.

The `nickname/login + resource` pair is tokenized as one entity because the combination of identifier and platform can point to a specific person.

The public `Patterns` class can be reused when configuring custom rules.

For full control, pass an explicit rule list:

```python
from lightanon.rag import Patterns, TextSanitizer

sanitizer = TextSanitizer(rules=[("EMAIL", Patterns.EMAIL)])
```

## Metadata

In RAG workflows, personal data often appears outside chunk text, in metadata such as `source_url`, `author`, `tags`, `file_path`, profile links, and account identifiers.

```python
sanitizer = TextSanitizer(profile="ru_152")

metadata = {
    "source_url": "https://github.com/ivan_dev",
    "author": "Telegram: @ivanov_dev",
    "tags": ["client", "ivan@example.com"],
}

clean_metadata = sanitizer.sanitize_metadata(metadata)
```

`sanitize_metadata(...)` recursively sanitizes string values inside `dict`, `list`, `tuple`, and `set` containers. Non-string values are preserved.

## Scan and Report

`scan(...)` checks text without replacement and without writing to the vault:

```python
sanitizer = TextSanitizer(profile="ru_152")
report = sanitizer.scan("Email ivan@example.com, INN 7707083893")
```

Example report:

```python
{
    "entities": {"EMAIL": 1, "INN": 1},
    "total": 2,
    "residual_risk": "medium",
}
```

`sanitize_with_report(...)` returns sanitized text and a report with entities found before processing and residual entities after processing.

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
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --profile ru_152
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan input.txt --profile ru_152
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy mask
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy restore_allowed_only --allowed-types EMAIL
lightanon rag inspect-vault vault.json
```

`sanitize` writes tokens to the vault. `restore` uses the same vault to replace tokens with original values.
`restore --policy` controls value disclosure in the final answer: `restore`, `no_personal_data`, `mask`, `restore_allowed_only`.
`scan` prints a JSON report without writing to the vault and without revealing original values.
`inspect-vault` prints saved mapping counts and token-type distribution without revealing stored values.
`--profile` enables a built-in rule profile. Available profiles: `basic`, `ru_152`, `ru_152_strict`.
`--rules` enables only the listed built-in rules and is useful when you need to disable the broad name heuristic, explicitly enable `INN`, or process online identifiers.
