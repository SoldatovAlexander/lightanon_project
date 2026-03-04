# Решение проблем

## `ImportError: pyarrow is required for parquet support`
Причина:
- отсутствуют зависимости для parquet.

Решение:
```bash
pip install -r requirements.txt
```

## `Warning: Unknown rule '...'`
Причина:
- в YAML указано правило, которого нет в `lightanon.rules` или `lightanon.financial`.

Решение:
- проверить имя класса и параметры конструктора.

## Колонка не меняется в `polars`
Причина:
- правило не реализует `apply_polars`.

Решение:
- посмотреть `[FAIL]` в `engine.generate_report()`,
- добавить `apply_polars` в правило.

## Медленная обработка в `StreamEngine`
Причина:
- правило использует fallback в `apply_single`.

Решение:
- реализовать оптимизированный `apply_single` в используемых правилах.
