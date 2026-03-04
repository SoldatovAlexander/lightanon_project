# RAG Guide

`lightanon.rag` is for reversible text sanitization:
1. sanitize sensitive text before LLM call,
2. de-anonymize model output for the end user.

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

## Custom Pattern

```python
sanitizer.add_rule("CONTRACT", r"\b\d{2}-\d{4}/\d{2}\b")
```

## Vault
Default backend: `MemoryVault`.
- fast,
- in-memory only,
- not persistent across restarts.

For production, implement your own `BaseVault` backend.
