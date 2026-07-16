# Руководство по CLI

## Команда

Пакетная обработка CSV/Parquet:

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

RAG-обезличивание текста:

```bash
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json>
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --ttl-seconds 3600
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --profile ru_152
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules EMAIL,PHONE,INN
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan <input.txt> --profile ru_152
lightanon rag restore <input.txt> <output.txt> --vault <vault.json>
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy mask
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy restore_allowed_only --allowed-types EMAIL
lightanon rag inspect-vault <vault.json>
lightanon rag delete-token <vault.json> <token>
lightanon rag delete-value <vault.json> <value>
lightanon rag purge-expired <vault.json>
lightanon rag clear-vault <vault.json>
```

## Параметры

### CSV/Parquet
- `input_file`: `.csv` или `.parquet`
- `output_file`: `.csv` или `.parquet`
- `--config`, `-c`: путь к YAML-схеме
- `--engine`: `pandas` (по умолчанию) или `polars`

### RAG
- `sanitize`: заменить чувствительные данные на обратимые токены,
- `scan`: вывести JSON-отчет по найденным сущностям без записи в vault,
- `restore`: восстановить исходные значения по токенам,
- `inspect-vault`: показать статистику vault без раскрытия исходных значений,
- `delete-token`: удалить один маппинг по токену,
- `delete-value`: удалить один маппинг по исходному значению,
- `purge-expired`: удалить истекшие маппинги,
- `clear-vault`: удалить все маппинги,
- `--vault`: JSON-файл с соответствиями токенов,
- `--ttl-seconds`: срок жизни новых vault-маппингов в секундах,
- `--profile`: профиль правил для `sanitize`: `basic`, `ru_152`, `ru_152_strict`,
- `--rules`: список встроенных правил для `sanitize`, разделенный запятыми,
- `--policy`: политика восстановления для `restore`: `restore`, `no_personal_data`, `mask`, `restore_allowed_only`,
- `--allowed-types`: список типов для `restore_allowed_only`, разделенный запятыми,
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
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --ttl-seconds 3600
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --profile ru_152
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan prompt.txt --profile ru_152
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy mask
lightanon rag restore llm_response.txt restored.txt --vault vault.json --policy restore_allowed_only --allowed-types EMAIL
lightanon rag inspect-vault vault.json
lightanon rag delete-token vault.json '[EMAIL_aaaaaaaa]'
lightanon rag purge-expired vault.json
lightanon rag clear-vault vault.json
```

## Поведение во время выполнения
- неизвестное правило: пропускается с warning,
- некорректный элемент YAML: пропускается с warning,
- пустая схема: вход копируется в выход,
- в конце печатается отчет.

Для RAG CLI:
- `sanitize` создает или дополняет `vault.json`,
- `--profile` выбирает готовый набор правил; `--rules` имеет более высокий приоритет,
- `--rules` включает только указанные правила; доступные значения: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`,
- повторный `sanitize` с тем же vault переиспользует уже созданные токены,
- `restore` требует тот же vault, который использовался при `sanitize`,
- поврежденный или неверно структурированный vault завершает команду ошибкой.
