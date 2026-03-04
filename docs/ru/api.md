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

## Замечание по `polars`

В текущей реализации для работы в `polars` нужен `apply_polars` в конкретном правиле.
Сейчас явная реализация есть у `Hash`; остальные правила могут возвращать `Error` в аудите, если не расширены.
