# CLI Guide

## Command

Batch CSV/Parquet processing:

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

RAG text sanitization:

```bash
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --scope-file <scope.json>
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --ttl-seconds 3600
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --profile ru_152
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --profile ru_152 --business-mode company
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --business-mode company_and_counterparties
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules EMAIL,PHONE,INN
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan <input.txt> --profile ru_152 --business-mode company
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> # masks by default
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy restore --scope-file <scope.json>
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy mask
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy restore_allowed_only --allowed-types EMAIL --scope-file <scope.json>
lightanon rag inspect-vault <vault.json>
lightanon rag delete-token <vault.json> <token>
lightanon rag delete-value <vault.json> <entity_type> <value> [--namespace default]
lightanon rag purge-expired <vault.json>
lightanon rag clear-vault <vault.json>
lightanon rag migrate-vault <legacy.json> <vault.v2> --vault-key-env LIGHTANON_VAULT_KEY
```

## Parameters

### CSV/Parquet
- `input_file`: `.csv` or `.parquet`
- `output_file`: `.csv` or `.parquet`
- `--config`, `-c`: YAML schema path
- `--engine`: `pandas` (default) or `polars`

### RAG
- `sanitize`: replace sensitive values with reversible tokens,
- `scan`: print a JSON report for detected entities without writing to a vault,
- `restore`: restore original values from tokens,
- `inspect-vault`: print vault statistics without revealing original values,
- `delete-token`: delete one mapping by token,
- `delete-value`: delete one mapping by typed original value,
- `migrate-vault`: convert a legacy plaintext vault to encrypted FileVault v2 while retaining the source,
- `purge-expired`: delete expired mappings,
- `clear-vault`: delete all mappings,
- `--vault`: JSON token-mapping file,
- `--vault-key-env`: environment variable containing the Fernet key for encrypted vault operations,
- `--scope-file`: write a token scope during `sanitize`; required for `restore` and `restore_allowed_only`,
- `--ttl-seconds`: lifetime for newly created vault mappings, in seconds,
- `--profile`: rule profile for `sanitize`: `basic`, `ru_152`, `ru_152_strict`,
- `--business-mode`: additional organization-requisites protection for `sanitize` and `scan`: `none`, `company`, `company_and_counterparties`,
- `--rules`: comma-separated built-in rule list for `sanitize`,
- `--policy`: output policy for `restore`, defaults to `mask`: `restore`, `no_personal_data`, `mask`, `restore_allowed_only`,
- `--allowed-types`: comma-separated type list for `restore_allowed_only`,
- `--encoding`: text-file encoding, defaults to `utf-8`.

## YAML Schema Format

```yaml
full_name:
  method: Mask
  params:
    visible_chars: 2

email:
  method: Hash
  params:
    salt: "my_production_salt_2026"

salary:
  method: GaussianNoise
  params:
    std: 0.1
```

## Examples

```bash
# CSV -> Parquet (pandas)
lightanon data/input.csv data/output.parquet -c schema.yaml --engine pandas

# Parquet -> CSV (polars)
lightanon data/input.parquet data/output.csv -c schema.yaml --engine polars

# RAG sanitize -> restore
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --scope-file scope.json
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --vault-key-env LIGHTANON_VAULT_KEY
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --ttl-seconds 3600
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --profile ru_152
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --profile ru_152 --business-mode company
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --business-mode company_and_counterparties
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan prompt.txt --profile ru_152 --business-mode company
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy restore --scope-file scope.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy mask
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy restore_allowed_only --allowed-types EMAIL --scope-file scope.json
lightanon rag inspect-vault vault.json
lightanon rag delete-token vault.json '[EMAIL_aaaaaaaa]'
lightanon rag purge-expired vault.json
lightanon rag clear-vault vault.json
```

## Runtime Behavior
- the YAML schema must contain at least one known rule with valid parameters; an error stops the command before output is written,
- `input_file`, `output_file`, and `config` must refer to different files,
- rule application errors replace the affected output column and make the CLI exit with code `1`,
- report is printed at the end.

For RAG CLI:
- `sanitize` creates or updates `vault.json`,
- `sanitize --scope-file` writes the allowed token occurrences for an associated response,
- `--vault-key-env` encrypts or decrypts the vault with a Fernet key read from the named environment variable,
- `restore` masks tokens by default; explicit restoration policies require `--scope-file` and cannot reveal tokens outside that scope,
- `--profile` selects a built-in rule set; `--rules` has higher priority,
- `--business-mode` adds company or company-and-counterparty requisites rules on top of the selected profile,
- `--rules` enables only the listed rules; available values: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`, `BUSINESS_REQUISITES`, `COUNTERPARTY_REQUISITES`, `ORGANIZATION_NAME`, `COMPANY_INN`, `KPP`, `OGRN`, `OKPO`, `LEGAL_ADDRESS`, `BANK_ACCOUNT`, `CORRESPONDENT_ACCOUNT`, `BIK`,
- repeated `sanitize` with the same vault reuses existing tokens,
- `restore` requires the same vault used during `sanitize`,
- corrupted or incorrectly structured vault files fail the command.
- `sanitize` and `restore` require distinct input, output, vault, and scope files; overlapping paths are rejected before a file is written.
