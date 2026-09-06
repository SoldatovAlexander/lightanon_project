# Справочник API

## Публичные экспорты пакета

```python
import lightanon as la
```

На верхнем уровне доступны:
- `la.Engine`
- `la.StreamEngine`
- `la.rules`
- `la.financial`
- `la.rag`

`la.rules` и `la.financial` содержат правила для `Engine`/`StreamEngine`.
`la.rag` — отдельный stateful-блок для обратимого обезличивания свободного текста перед LLM/RAG.

## `Engine` (пакетная обработка)

Расположение: `lightanon.engine.Engine`

Назначение:
- обработка `pandas.DataFrame` и `polars.DataFrame`,
- применение правил по схеме,
- накопление аудита,
- генерация отчета.

Основные методы:
- `Engine(schema: Dict[str, BaseRule])`
- `run(df)`
- `generate_report() -> str`

Поведение аудита:
- `run(...)` очищает `audit_log`,
- для каждой колонки фиксируется `success` или `error` со стабильным кодом и классом исключения; текст исключения не раскрывается в отчёте,
- если правило падает с ошибкой, исходные значения этой колонки не сохраняются в выходе: для pandas колонка заменяется на `pd.NA`, для polars - на `null`.

## `BaseRule`

Расположение: `lightanon.rules.BaseRule`

Интерфейс:
- `apply(series: pd.Series) -> pd.Series` для batch/pandas,
- `apply_polars(col_name: str) -> pl.Expr` для batch/polars,
- `apply_single(value)` для стриминга.

`apply_single` имеет fallback через `pandas` и может быть медленным.

## Базовые правила (`lightanon.rules`)

### `Hash(salt: str)`
- детерминированный HMAC-SHA-256,
- требует непустой секретный salt,
- удобно для стабильных псевдонимизированных JOIN,
- `None/NaN` -> `None`.

### `Mask(visible_chars: int = 1)`
- оставляет первые `visible_chars`, остальное заменяет на `*`,
- полностью маскирует значения длиной не больше `visible_chars`,
- `None/NaN` -> `None`.

### `GaussianNoise(std: float = 0.1)`
- добавляет аддитивный гауссов шум,
- формула: `x + N(0, x * std)`.

### `Generalize(step: int = 5)`
- преобразует число в интервал,
- пример: `23 -> "20-25"`.

## Финансовые правила (`lightanon.financial`)

### `MultiplicativeNoise(std_dev_percent: float = 0.05)`
- мультипликативный шум,
- формула: `x * N(1.0, std)`.

### `TopCoding(quantile: float = 0.99)`
- обрезка выбросов по перцентилю.

### `CreditCardMask()`
- маскирует номер карты, оставляя последние 4 цифры.

### `TopCodingFixed(cap_value: float)`
- фиксированный предел для streaming-сценариев.

## RAG text sanitization (`lightanon.rag`)

RAG-блок не является набором `BaseRule` для колонок. Это отдельный обратимый пайплайн для свободного текста:
1. `sanitize(text)` заменяет чувствительные значения на токены,
2. внешний LLM/RAG-пайплайн работает только с токенами,
3. `deanonymize(text)` по умолчанию маскирует токены; явное восстановление ограничено очищенным входом.

Публичные экспорты:
- `TextSanitizer`
- `BaseVault`
- `MemoryVault`
- `FileVault`
- `Patterns`

### `TextSanitizer(vault: Optional[BaseVault] = None, enabled_rules=None, rules=None, profile="basic", business_mode="none")`
- использует `MemoryVault` по умолчанию,
- сохраняет соответствие `исходное значение -> токен`,
- переиспользует один и тот же токен для повторяющегося значения,
- поддерживает встроенные regex-паттерны и пользовательские правила,
- умеет включать только выбранные встроенные правила через `enabled_rules`,
- может принять явный список правил через `rules=[("EMAIL", Patterns.EMAIL), ...]`,
- поддерживает профили правил: `basic`, `ru_152`, `ru_152_strict`,
- поддерживает дополнительный режим скрытия реквизитов организаций через `business_mode`.
- принимает явные объекты `OrganizationProfile`, чтобы различать собственную компанию и контрагентов.

Основные методы:
- `sanitize(text: str) -> str`
- `sanitize_with_scope(text: str) -> Tuple[str, Dict[str, int]]`
- `sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]`
- `sanitize_metadata_with_scope(metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]`
- `deanonymize_metadata(metadata: Dict[str, Any], policy: str = "mask", allowed_entity_types=None, token_scope=None) -> Dict[str, Any]`
- `sanitize_document(text: str, metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, Dict[str, Any]]`
- `sanitize_document_with_scope(text: str, metadata: Optional[Dict[str, Any]] = None) -> SanitizedDocument`
- `deanonymize_document(text: str, metadata: Optional[Dict[str, Any]] = None, policy: str = "mask", allowed_entity_types=None, token_scope=None) -> Tuple[str, Dict[str, Any]]`
- `scan(text: str) -> Dict[str, object]`
- `sanitize_with_report(text: str) -> Tuple[str, Dict[str, object]]`
- `deanonymize(text: str, policy: str = "mask", allowed_entity_types=None, token_scope=None) -> str`
- `add_rule(name: str, pattern: str)`

Встроенные правила: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`, `BUSINESS_REQUISITES`, `COUNTERPARTY_REQUISITES`, `ORGANIZATION_NAME`, `COMPANY_INN`, `KPP`, `OGRN`, `OKPO`, `LEGAL_ADDRESS`, `BANK_ACCOUNT`, `CORRESPONDENT_ACCOUNT`, `BIK`.
По умолчанию `INN` выключен, чтобы голые 10/12 цифр не конфликтовали с документами без контекста.
Правило `ONLINE_ACCOUNT` предназначено для составных интернет-идентификаторов, например `никнейм ivan_dev на Habr` или `Telegram: @ivanov`, и токенизирует такую связку целиком.
`business_mode="company"` добавляет правила для реквизитов компании поверх выбранного профиля. `business_mode="company_and_counterparties"` дополнительно включает компактные блоки реквизитов контрагентов. Приоритет настройки: `rules` > `enabled_rules` > `profile`; `business_mode` применяется к выбранному набору, если `rules` не передан явно.

Когда важны роли, передайте известные организации явно. `company` скрывает только профиль собственной компании; `company_and_counterparties` скрывает обе роли. Обработка неизвестной организации задана явно: `report` оставляет её без изменения и сообщает счётчик, `mask` использует общие правила организаций, `reject` останавливает обработку.

```python
from lightanon.rag import OrganizationProfile, TextSanitizer

sanitizer = TextSanitizer(
    business_mode="company",
    organization_profiles=[
        OrganizationProfile(role="company", full_name='ООО "Ромашка"', inn="7707083893"),
    ],
    unknown_organization_policy="reject",
)
```

Пример:

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer()
clean, token_scope = sanitizer.sanitize_with_scope("Иванов Иван, email ivan@example.com")
answer = f"Контакт: {clean}"
restored = sanitizer.deanonymize(answer, policy="restore", token_scope=token_scope)
```

`sanitize_metadata(...)` рекурсивно обрабатывает строковые значения в `dict`, `list`, `tuple` и `set`, сохраняя нестроковые значения. Это полезно для RAG-документов, где персональные данные могут находиться в `source_url`, `author`, `tags`, `file_path` и других metadata-полях.
`deanonymize_metadata(...)` выполняет симметричное восстановление metadata с теми же политиками, что и `deanonymize(...)`.
`sanitize_document(...)` и `deanonymize_document(...)` обрабатывают текст и metadata одной операцией с общим vault. `sanitize_document_with_scope(...)` возвращает `SanitizedDocument(text, metadata, token_scope)`; его scope включает только замены, сделанные в этом вызове.

`scan(...)` ищет сущности без замены текста и без записи в vault. Отчет содержит счетчики по типам, активные правила и `coverage="heuristic"`; ноль совпадений не доказывает отсутствие ПД.
`sanitize_with_report(...)` возвращает очищенный текст и ту же информацию о покрытии до и после обработки.
`deanonymize(...)` по умолчанию использует `mask`; `no_personal_data` оставляет токены. Для `restore` и `restore_allowed_only` нужен token scope из `sanitize_with_scope(...)`, поэтому восстанавливаются только токены этого входа и только в количестве исходных вхождений.

### `BaseVault`
Абстрактный интерфейс хранилища токенов:
- `get_value(token: str)`
- `get_token(entity_type: str, value: str, namespace: str = "default")`
- `save(token: str, entity_type: str, value: str, namespace: str = "default", ttl_seconds: Optional[int] = None)`
- `delete_token(token: str) -> bool`
- `delete_value(entity_type: str, value: str, namespace: str = "default") -> bool`
- `clear() -> None`
- `purge_expired() -> int`

### `FileVault(path, default_ttl_seconds=None, encryption_key=None)`
Версионированный локальный vault. Значения разделены по типу сущности и namespace, а конфликтные маппинги вызывают `MappingConflict`. Ключ Fernet создаёт зашифрованный v2-envelope; при ключе plaintext и legacy vault отклоняются. Доступ к файлу защищён lock-файлом и атомарной заменой.

### `MemoryVault`
In-memory реализация `BaseVault`.
Подходит для одного процесса/сессии, но не сохраняет данные между перезапусками.

### `FileVault(path: str, default_ttl_seconds: Optional[int] = None)`
JSON-backed реализация `BaseVault` для CLI и локальных RAG-сценариев.
Сохраняет токены на диск, поэтому `sanitize` и `restore` могут выполняться разными процессами.
Запись выполняется через временный файл с последующей атомарной заменой.
Некорректный JSON или неверная структура vault вызывают `ValueError`.
Новые записи сохраняют `created_at`, `last_used_at` и, если задан TTL, `expires_at`. Legacy vault переносится явно через `migrate_legacy_file_vault(...)` или `lightanon rag migrate-vault`.

Дополнительный метод:
- `stats() -> Dict[str, object]`: возвращает путь, общее число маппингов, счетчики по типам токенов и наличие timestamps/expiration без исходных значений.

### `Patterns`
Набор встроенных regex-паттернов для email, телефонов РФ, паспорта РФ, СНИЛС, ИНН, карт, интернет-идентификаторов и эвристики ФИО.
Паспортный паттерн требует разделитель перед 6-значным номером, например `4500 123456`, чтобы не классифицировать 10-значный ИНН как паспорт.

## Замечание по `polars`

В текущей реализации для работы в `polars` нужен `apply_polars` в конкретном правиле.
Сейчас явная реализация есть у `Hash`; остальные правила могут возвращать `Error` в аудите, если не расширены.
