# CLI Guide

## Command

Batch CSV/Parquet processing:

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

RAG text sanitization:

```bash
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json>
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --profile ru_152
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules EMAIL,PHONE,INN
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag restore <input.txt> <output.txt> --vault <vault.json>
lightanon rag inspect-vault <vault.json>
```

## Parameters

### CSV/Parquet
- `input_file`: `.csv` or `.parquet`
- `output_file`: `.csv` or `.parquet`
- `--config`, `-c`: YAML schema path
- `--engine`: `pandas` (default) or `polars`

### RAG
- `sanitize`: replace sensitive values with reversible tokens,
- `restore`: restore original values from tokens,
- `inspect-vault`: print vault statistics without revealing original values,
- `--vault`: JSON token-mapping file,
- `--profile`: rule profile for `sanitize`: `basic`, `ru_152`, `ru_152_strict`,
- `--rules`: comma-separated built-in rule list for `sanitize`,
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
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --profile ru_152
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag inspect-vault vault.json
```

## Runtime Behavior
- unknown rule in YAML: skipped with warning,
- invalid YAML item format: skipped with warning,
- empty schema: input is copied to output,
- report is printed at the end.

For RAG CLI:
- `sanitize` creates or updates `vault.json`,
- `--profile` selects a built-in rule set; `--rules` has higher priority,
- `--rules` enables only the listed rules; available values: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`,
- repeated `sanitize` with the same vault reuses existing tokens,
- `restore` requires the same vault used during `sanitize`,
- corrupted or incorrectly structured vault files fail the command.
