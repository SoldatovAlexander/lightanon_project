# Руководство по CLI

## Команда

Пакетная обработка CSV/Parquet:

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

RAG-обезличивание текста:

```bash
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json>
lightanon rag restore <input.txt> <output.txt> --vault <vault.json>
```

## Параметры

### CSV/Parquet
- `input_file`: `.csv` или `.parquet`
- `output_file`: `.csv` или `.parquet`
- `--config`, `-c`: путь к YAML-схеме
- `--engine`: `pandas` (по умолчанию) или `polars`

### RAG
- `sanitize`: заменить чувствительные данные на обратимые токены,
- `restore`: восстановить исходные значения по токенам,
- `--vault`: JSON-файл с соответствиями токенов,
- `--encoding`: кодировка текстовых файлов, по умолчанию `utf-8`.

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

# RAG sanitize -> restore
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json
```

## Поведение во время выполнения
- неизвестное правило: пропускается с warning,
- некорректный элемент YAML: пропускается с warning,
- пустая схема: вход копируется в выход,
- в конце печатается отчет.
