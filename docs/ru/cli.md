# Руководство по CLI

## Команда

Пакетная обработка CSV/Parquet:

```bash
lightanon <input_file> <output_file> -c <schema.yaml> [--engine pandas|polars]
```

RAG-обезличивание текста:

```bash
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --scope-file <scope.json>
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --ttl-seconds 3600
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --profile ru_152
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --profile ru_152 --business-mode company
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --business-mode company_and_counterparties
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules EMAIL,PHONE,INN
lightanon rag sanitize <input.txt> <output.txt> --vault <vault.json> --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan <input.txt> --profile ru_152 --business-mode company
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> # по умолчанию маскирует
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy restore --scope-file <scope.json>
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy mask
lightanon rag restore <input.txt> <output.txt> --vault <vault.json> --policy restore_allowed_only --allowed-types EMAIL --scope-file <scope.json>
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
- `--vault-key-env`: переменная окружения с ключом Fernet для зашифрованного vault,
- `--scope-file`: записывает token scope при `sanitize`; обязателен для `restore` и `restore_allowed_only`,
- `--ttl-seconds`: срок жизни новых vault-маппингов в секундах,
- `--profile`: профиль правил для `sanitize`: `basic`, `ru_152`, `ru_152_strict`,
- `--business-mode`: дополнительная защита реквизитов организаций для `sanitize` и `scan`: `none`, `company`, `company_and_counterparties`,
- `--rules`: список встроенных правил для `sanitize`, разделенный запятыми,
- `--policy`: политика вывода для `restore`, по умолчанию `mask`: `restore`, `no_personal_data`, `mask`, `restore_allowed_only`,
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

## Поведение во время выполнения
- YAML-схема должна содержать хотя бы одно известное правило и корректные параметры; ошибка прерывает запуск до записи output,
- `input_file`, `output_file` и `config` должны указывать на разные файлы,
- ошибка применения правила затирает соответствующую колонку в выходном файле и завершает CLI с кодом `1`,
- в конце печатается отчет.

Для RAG CLI:
- `sanitize` создает или дополняет `vault.json`,
- `sanitize --scope-file` записывает разрешенные вхождения токенов для связанного ответа,
- `--vault-key-env` шифрует или расшифровывает vault ключом Fernet из указанной переменной окружения,
- `restore` по умолчанию маскирует токены; для явных политик восстановления нужен `--scope-file`, и токены вне его области не раскрываются,
- `--profile` выбирает готовый набор правил; `--rules` имеет более высокий приоритет,
- `--business-mode` добавляет правила реквизитов компании или компании и контрагентов поверх выбранного профиля,
- `--rules` включает только указанные правила; доступные значения: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`, `BUSINESS_REQUISITES`, `COUNTERPARTY_REQUISITES`, `ORGANIZATION_NAME`, `COMPANY_INN`, `KPP`, `OGRN`, `OKPO`, `LEGAL_ADDRESS`, `BANK_ACCOUNT`, `CORRESPONDENT_ACCOUNT`, `BIK`,
- повторный `sanitize` с тем же vault переиспользует уже созданные токены,
- `restore` требует тот же vault, который использовался при `sanitize`,
- поврежденный или неверно структурированный vault завершает команду ошибкой.
- в командах `sanitize` и `restore` входной файл, output, vault и scope-file должны быть разными; пересечение путей отклоняется до записи файлов.
