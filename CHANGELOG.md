# Changelog

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
