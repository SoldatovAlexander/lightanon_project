# CLI Guide

## Command

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

## Parameters
- `input_file`: `.csv` or `.parquet`
- `output_file`: `.csv` or `.parquet`
- `--config`, `-c`: YAML schema path
- `--engine`: `pandas` (default) or `polars`

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
```

## Runtime Behavior
- unknown rule in YAML: skipped with warning,
- invalid YAML item format: skipped with warning,
- empty schema: input is copied to output,
- report is printed at the end.
