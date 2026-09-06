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
sanitized, token_scope = sanitizer.sanitize_with_scope(original)

# Simulated LLM output
response = f"Confirmed: {sanitized}"
restored = sanitizer.deanonymize(response, policy="restore", token_scope=token_scope)

print(sanitized)
print(restored)
```

For safer output, control restoration with policies:

```python
sanitizer.deanonymize(response, policy="no_personal_data")
sanitizer.deanonymize(response, policy="mask")
sanitizer.deanonymize(response, policy="restore_allowed_only", allowed_entity_types=["EMAIL"], token_scope=token_scope)
```

The default policy is `mask`. Explicit restoration requires the token scope returned by `sanitize_with_scope(...)`; it permits only tokens from that sanitized input and only up to their original occurrence count.

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

For corporate RAG workflows, you can additionally enable organization-requisites protection. It composes with personal-data profiles:

```python
sanitizer = TextSanitizer(profile="ru_152", business_mode="company")
```

`business_mode` values:
- `none`: do not add organization requisites rules;
- `company`: hides company requisites such as INN, KPP, OGRN, OKPO, BIK, settlement and correspondent accounts, legal address, full names, and short names;
- `company_and_counterparties`: additionally hides compact requisites blocks for counterparties, suppliers, contractors, buyers, customers, performers, and clients.

If an explicit `rules` list is passed through the Python API, it fully defines the active rules.

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

For symmetric metadata restoration, use the same policies as for text:

```python
masked_metadata = sanitizer.deanonymize_metadata(clean_metadata)
masked_metadata = sanitizer.deanonymize_metadata(clean_metadata, policy="mask")
```

To process a whole RAG document, use document-level methods:

```python
clean_text, clean_metadata = sanitizer.sanitize_document(text, metadata)
restored_text, restored_metadata = sanitizer.deanonymize_document(clean_text, clean_metadata)

result = sanitizer.sanitize_document_with_scope(text, metadata)
restored_text, restored_metadata = sanitizer.deanonymize_document(
    result.text, result.metadata, policy="restore", token_scope=result.token_scope
)
```

Text and metadata share one vault, so repeated values receive the same tokens.

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
    "active_rules": ["EMAIL", "PHONE", "PASSPORT", "SNILS", "INN", "CARD", "PERSON"],
    "coverage": "heuristic",
}
```

`sanitize_with_report(...)` returns sanitized text and a report with entities found before processing and residual entities after processing. `coverage="heuristic"` means that zero matches are not a guarantee that the input contains no personal data.

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
- `get_token(entity_type: str, value: str, namespace="default")`,
- `save(token: str, entity_type: str, value: str, namespace="default", ttl_seconds=None)`,
- `delete_token(token: str)`,
- `delete_value(entity_type: str, value: str, namespace="default")`,
- `clear()`,
- `purge_expired()`.

`FileVault` stores mappings in a JSON file and is useful for local CLI workflows:

```python
import os

from lightanon.rag import FileVault, TextSanitizer

sanitizer = TextSanitizer(vault=FileVault("vault.json", encryption_key=os.environ["LIGHTANON_VAULT_KEY"]))
```

`FileVault` v2 validates JSON structure, stores a typed `(namespace, entity_type, value)` mapping, uses a lock file for every read-modify-write operation, and writes through a `0600` temporary file followed by atomic replacement. New entries include `created_at`, `last_used_at`, and `expires_at` when TTL is configured. `stats()` returns counters only, without original values.

Pass a Fernet key as `encryption_key` to create an encrypted v2 vault. Once a key is supplied, plaintext and legacy files are rejected, preventing a ciphertext replacement from silently downgrading protection. Migrate legacy plaintext files explicitly: `lightanon rag migrate-vault legacy.json vault.v2 --vault-key-env LIGHTANON_VAULT_KEY`. The source is retained. Production vaults should use encryption, managed keys, and access control.

## CLI

RAG commands work with plain text files and require `--vault` so restoration can happen in a separate run:

```bash
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --scope-file scope.json
export LIGHTANON_VAULT_KEY='...'
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --vault-key-env LIGHTANON_VAULT_KEY
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --ttl-seconds 3600
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --profile ru_152
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --profile ru_152 --business-mode company
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --business-mode company_and_counterparties
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan input.txt --profile ru_152 --business-mode company
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy restore --scope-file scope.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy mask
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy restore_allowed_only --allowed-types EMAIL --scope-file scope.json
lightanon rag inspect-vault vault.json
lightanon rag delete-token vault.json '[EMAIL_aaaaaaaa]'
lightanon rag delete-value vault.json EMAIL 'ivan@example.com'
lightanon rag purge-expired vault.json
lightanon rag clear-vault vault.json
lightanon rag migrate-vault legacy.json vault.v2 --vault-key-env LIGHTANON_VAULT_KEY
```

`sanitize --scope-file` writes a non-sensitive token scope alongside the vault. `restore` defaults to `mask`; explicit `restore` and `restore_allowed_only` require `--scope-file` and cannot restore tokens outside that scope or beyond its occurrence counts.
`--vault-key-env` reads a Fernet key from an environment variable and encrypts/decrypts the local vault without exposing the key in command history.
`scan` prints a JSON report without writing to the vault and without revealing original values.
`inspect-vault` prints saved mapping counts and token-type distribution without revealing stored values.
`delete-token`, `delete-value`, and `clear-vault` manage saved mapping lifecycle. `delete-value` requires an entity type because the same value may intentionally exist under several types.
`--ttl-seconds` sets lifetime for new mappings, and `purge-expired` deletes expired entries.
`--profile` enables a built-in rule profile. Available profiles: `basic`, `ru_152`, `ru_152_strict`.
`--business-mode` adds organization-requisites protection on top of the selected profile. Available modes: `none`, `company`, `company_and_counterparties`.
`--rules` enables only the listed built-in rules and is useful when you need to disable the broad name heuristic, explicitly enable `INN`, or process online identifiers.
