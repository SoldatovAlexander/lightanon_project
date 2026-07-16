# RAG Compliance Notes

This page gives engineering guidance for using `lightanon.rag` in workflows that may contain personal data. It is not legal advice; the data controller must define the legal basis, consent model, retention policy, and operational controls.

## Main Principle

For RAG, personal data should be interpreted broadly. It can include not only names, phone numbers, emails, passports, or tax IDs, but also indirect identifiers that point to a specific person.

Practical implications:
- sanitize free text before sending it to an LLM;
- sanitize RAG metadata, not only chunk text;
- do not treat public availability as automatic permission to disclose data in generated answers;
- protect the vault because it stores original values.

## Online Identifiers

Online identifiers can identify a person when combined with a platform or resource. Examples:

```text
nickname ivan_dev on Habr
Telegram: @ivanov
github.com/ivan_dev
vk.com/id123456
```

Use the `ru_152` profile or enable online identifier rules explicitly:

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer(profile="ru_152")
clean = sanitizer.sanitize("Telegram: @ivanov")
```

CLI:

```bash
lightanon rag sanitize input.txt output.txt --vault vault.json --profile ru_152
```

## Recommended Profiles

`basic`:
- baseline default profile;
- useful for demos and lower-risk text;
- does not include `INN` or online identifiers by default.

`ru_152`:
- includes `basic`;
- adds `INN`;
- adds `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`;
- recommended for Russian-language RAG contexts that may contain personal data.

`ru_152_strict`:
- includes `ru_152`;
- adds `IP_ADDRESS`, `COOKIE_ID`, `DEVICE_ID`, `USER_ID`;
- useful for logs, support tickets, analytics exports, and operational systems.

## Metadata

RAG metadata may contain personal data:

```python
metadata = {
    "source_url": "https://github.com/ivan_dev",
    "author": "Telegram: @ivanov",
    "tags": ["client", "ivan@example.com"],
}
```

Sanitize metadata with the same sanitizer and vault:

```python
clean_metadata = sanitizer.sanitize_metadata(metadata)
```

## Pre-LLM Scan

Use `scan` or `sanitize_with_report` before sending context to an LLM:

```python
clean, report = sanitizer.sanitize_with_report(text)
```

CLI:

```bash
lightanon rag scan input.txt --profile ru_152
```

Reports contain counters and risk level, not original values.

## Output Restoration Policy

Generated answers do not always need original values restored. Use restoration policies:

```python
sanitizer.deanonymize(answer, policy="no_personal_data")
sanitizer.deanonymize(answer, policy="mask")
sanitizer.deanonymize(answer, policy="restore_allowed_only", allowed_entity_types=["EMAIL"])
```

CLI:

```bash
lightanon rag restore answer.txt restored.txt --vault vault.json --policy mask
```

Prefer `mask` or `no_personal_data` by default. Use `restore` only when original-value disclosure is necessary and permitted.

## Vault Handling

The vault stores token-to-original mappings, so it contains personal data.

Recommended controls:
- keep vault files out of public artifacts;
- do not commit vault files to source control;
- restrict file access;
- delete mappings when they are no longer needed;
- use `inspect-vault` for counters instead of reading raw vault contents.

Lifecycle commands:

```bash
lightanon rag inspect-vault vault.json
lightanon rag delete-token vault.json '[EMAIL_aaaaaaaa]'
lightanon rag delete-value vault.json 'ivan@example.com'
lightanon rag clear-vault vault.json
```

## Checklist

Before sending RAG context to an LLM:
- choose `ru_152` or `ru_152_strict`;
- sanitize chunk text;
- sanitize metadata;
- scan or generate a report;
- protect the vault;
- choose an output restoration policy.
