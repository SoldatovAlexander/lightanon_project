# Migration to 0.3.0

Version 0.3.0 contains security-oriented API changes. Update application code and persisted FileVault files before deploying it.

## Table rules

- `Hash` now requires a non-empty secret `salt` and produces HMAC-SHA-256 values. Existing SHA-256 outputs are not compatible.
- `Mask` no longer exposes short values unchanged.
- Engine failures clear the affected output column and report a safe error code. Treat a non-success audit entry as a failed batch.

## RAG restoration

`deanonymize()` now masks tokens by default. To reveal values, retain the scope returned by the sanitization request and pass it explicitly:

```python
clean, token_scope = sanitizer.sanitize_with_scope(text)
restored = sanitizer.deanonymize(answer, policy="restore", token_scope=token_scope)
```

Keep the scope in trusted server-side request context. It is a bound for one restoration operation, not a user-held authorization token.

## FileVault v2

The vault API is typed:

```python
vault.save(token, "EMAIL", "person@example.com")
vault.get_token("EMAIL", "person@example.com")
```

The same text under different entity types no longer shares a token. `FileVault` v2 uses a versioned payload, immutable mappings and a lock file. With a Fernet key it accepts only encrypted v2 envelopes; a legacy plaintext file is rejected instead of being silently read.

Migrate a legacy plaintext vault to a new destination. The source is retained:

```bash
export LIGHTANON_VAULT_KEY='...'
lightanon rag migrate-vault legacy-vault.json vault.v2 --vault-key-env LIGHTANON_VAULT_KEY
```

Update lifecycle calls to include the entity type:

```bash
lightanon rag delete-value vault.v2 EMAIL 'person@example.com'
```

## Verify the upgrade

1. Run tests and RAG regression corpus.
2. Migrate a copy of each legacy vault and verify restore in a non-production environment.
3. Confirm that application code stores scope server-side and supplies it only for permitted restoration.
4. Deploy the new package with a managed Fernet key and retain the legacy vault until validation is complete.
