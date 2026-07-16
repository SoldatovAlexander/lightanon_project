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
- для каждой колонки фиксируется `Success`, `Missing column` или `Error: ...`.

## `BaseRule`

Расположение: `lightanon.rules.BaseRule`

Интерфейс:
- `apply(series: pd.Series) -> pd.Series` для batch/pandas,
- `apply_polars(col_name: str) -> pl.Expr` для batch/polars,
- `apply_single(value)` для стриминга.

`apply_single` имеет fallback через `pandas` и может быть медленным.

## Базовые правила (`lightanon.rules`)

### `Hash(salt: str = "")`
- детерминированный SHA-256,
- удобно для стабильных псевдонимизированных JOIN,
- `None/NaN` -> `None`.

### `Mask(visible_chars: int = 1)`
- оставляет первые `visible_chars`, остальное заменяет на `*`,
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
3. `deanonymize(text)` восстанавливает исходные значения в финальном ответе.

Публичные экспорты:
- `TextSanitizer`
- `BaseVault`
- `MemoryVault`
- `FileVault`
- `Patterns`

### `TextSanitizer(vault: Optional[BaseVault] = None, enabled_rules=None, rules=None, profile="basic")`
- использует `MemoryVault` по умолчанию,
- сохраняет соответствие `исходное значение -> токен`,
- переиспользует один и тот же токен для повторяющегося значения,
- поддерживает встроенные regex-паттерны и пользовательские правила,
- умеет включать только выбранные встроенные правила через `enabled_rules`,
- может принять явный список правил через `rules=[("EMAIL", Patterns.EMAIL), ...]`,
- поддерживает профили правил: `basic`, `ru_152`, `ru_152_strict`.

Основные методы:
- `sanitize(text: str) -> str`
- `sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]`
- `scan(text: str) -> Dict[str, object]`
- `sanitize_with_report(text: str) -> Tuple[str, Dict[str, object]]`
- `deanonymize(text: str) -> str`
- `add_rule(name: str, pattern: str)`

Встроенные правила: `EMAIL`, `PHONE`, `PASSPORT`, `SNILS`, `INN`, `CARD`, `PERSON`, `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`.
По умолчанию `INN` выключен, чтобы голые 10/12 цифр не конфликтовали с документами без контекста.
Правило `ONLINE_ACCOUNT` предназначено для составных интернет-идентификаторов, например `никнейм ivan_dev на Habr` или `Telegram: @ivanov`, и токенизирует такую связку целиком.
Приоритет настройки: `rules` > `enabled_rules` > `profile`.

Пример:

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer()
clean = sanitizer.sanitize("Иванов Иван, email ivan@example.com")
answer = f"Контакт: {clean}"
restored = sanitizer.deanonymize(answer)
```

`sanitize_metadata(...)` рекурсивно обрабатывает строковые значения в `dict`, `list`, `tuple` и `set`, сохраняя нестроковые значения. Это полезно для RAG-документов, где персональные данные могут находиться в `source_url`, `author`, `tags`, `file_path` и других metadata-полях.

`scan(...)` ищет сущности без замены текста и без записи в vault. Отчет содержит счетчики по типам и уровень риска, но не исходные значения.
`sanitize_with_report(...)` возвращает очищенный текст и отчет с сущностями до обработки и остаточными сущностями после обработки.

### `BaseVault`
Абстрактный интерфейс хранилища токенов:
- `get_value(token: str)`
- `get_token(value: str)`
- `save(token: str, value: str)`

### `MemoryVault`
In-memory реализация `BaseVault`.
Подходит для одного процесса/сессии, но не сохраняет данные между перезапусками.

### `FileVault(path: str)`
JSON-backed реализация `BaseVault` для CLI и локальных RAG-сценариев.
Сохраняет токены на диск, поэтому `sanitize` и `restore` могут выполняться разными процессами.
Запись выполняется через временный файл с последующей атомарной заменой.
Некорректный JSON или неверная структура vault вызывают `ValueError`.

Дополнительный метод:
- `stats() -> Dict[str, object]`: возвращает путь, общее число маппингов и счетчики по типам токенов без исходных значений.

### `Patterns`
Набор встроенных regex-паттернов для email, телефонов РФ, паспорта РФ, СНИЛС, ИНН, карт, интернет-идентификаторов и эвристики ФИО.
Паспортный паттерн требует разделитель перед 6-значным номером, например `4500 123456`, чтобы не классифицировать 10-значный ИНН как паспорт.

## Замечание по `polars`

В текущей реализации для работы в `polars` нужен `apply_polars` в конкретном правиле.
Сейчас явная реализация есть у `Hash`; остальные правила могут возвращать `Error` в аудите, если не расширены.
