# Changelog

## Unreleased

### Added
- RAG `business_mode` for optional company and counterparty requisites protection before cloud LLM calls.
- Built-in RAG business rules for organization names, INN/KPP/OGRN/OKPO, legal addresses, bank accounts, BIK, and compact counterparty requisites blocks.
- CLI `--business-mode` option for `lightanon rag sanitize` and `lightanon rag scan`.

### Security
- Table anonymization now fails closed: rule errors replace the affected output column instead of leaving raw source values.
- Batch CLI exits with code `1` when any schema column fails or is missing.
- RAG restoration now masks tokens by default and requires a bounded token scope for explicit value disclosure.
- Newly generated RAG tokens now use 128 bits of cryptographic randomness and are checked for vault collisions.
- RAG vault handles legacy timezone-less timestamps as UTC, avoids writes on reads, uses private local-file permissions, and supports Fernet encryption through API and CLI environment keys.
- `Hash` now requires a non-empty secret salt and uses HMAC-SHA-256; `Mask` no longer exposes short values.
- Financial multiplicative noise preserves the original transaction sign.
- Processing reports no longer present technical rule execution as a legal compliance determination.

## 0.2.0

### Added
- RAG online identifier detection for profile URLs, handles, usernames, and combined nickname/login + resource pairs.
- RAG rule profiles: `basic`, `ru_152`, and `ru_152_strict`.
- RAG metadata and document helpers: `sanitize_metadata`, `deanonymize_metadata`, `sanitize_document`, and `deanonymize_document`.
- RAG scan/report API and `lightanon rag scan`.
- Deanonymization policies: `restore`, `no_personal_data`, `mask`, and `restore_allowed_only`.
- File vault lifecycle controls: delete by token, delete by value, clear vault, timestamps, TTL, and purge expired mappings.
- RAG compliance documentation for 152-FZ-oriented workflows.

### Changed
- RAG sanitization now supports span-based replacement to avoid overlapping-rule corruption.
- `FileVault` keeps backward compatibility with the previous JSON shape while adding structured `entries`.

### Verified
- Test suite passes: `67 passed`.

## 0.1.0

Initial release with core anonymization rules, financial rules, batch/stream engines, CLI, and base RAG text sanitization.
