# Руководство по CLI

## Команда

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

## Параметры
- `input_file`: `.csv` или `.parquet`
- `output_file`: `.csv` или `.parquet`
- `--config`, `-c`: путь к YAML-схеме
- `--engine`: `pandas` (по умолчанию) или `polars`

## Формат YAML

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

## Примеры

```bash
# CSV -> Parquet (pandas)
lightanon data/input.csv data/output.parquet -c schema.yaml --engine pandas

# Parquet -> CSV (polars)
lightanon data/input.parquet data/output.csv -c schema.yaml --engine polars
```

## Поведение во время выполнения
- неизвестное правило: пропускается с warning,
- некорректный элемент YAML: пропускается с warning,
- пустая схема: вход копируется в выход,
- в конце печатается отчет.
