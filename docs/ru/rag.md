# Руководство по RAG

`lightanon.rag` нужен для обратимого обезличивания текста:
1. скрыть чувствительные данные перед отправкой в LLM,
2. восстановить данные в итоговом ответе для пользователя.

Это отдельный stateful-блок, а не правило для `Engine`: он хранит соответствия между исходными значениями и токенами в `Vault`.

## Быстрый пример

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer()

original = "Заявитель Иванов Иван, паспорт 4500 123456, телефон +7 900 123-45-67."
sanitized = sanitizer.sanitize(original)

# Симуляция ответа LLM
response = f"Подтверждаю: {sanitized}"
restored = sanitizer.deanonymize(response)

print(sanitized)
print(restored)
```

## Встроенные паттерны
По умолчанию используются регулярные выражения для:
- email,
- телефон РФ,
- паспорт РФ,
- СНИЛС,
- номер карты,
- широкая эвристика ФИО.

Профили правил:
- `basic`: текущий базовый набор по умолчанию;
- `ru_152`: `basic` + `INN` + интернет-идентификаторы;
- `ru_152_strict`: `ru_152` + IP-адреса, cookie/session ID, device/client ID и user ID.

```python
sanitizer = TextSanitizer(profile="ru_152")
```

Приоритет настройки: `rules` > `enabled_rules` > `profile`.

Также доступно встроенное правило `INN`, но оно выключено по умолчанию: 10/12 цифр без контекста легко конфликтуют с другими документами. Его можно включить явно:

```python
sanitizer = TextSanitizer(enabled_rules=["EMAIL", "PHONE", "INN"])
```

Для интернет-идентификаторов доступны правила:
- `ONLINE_ACCOUNT`: составные связки вроде `никнейм ivan_dev на Habr`, `Telegram: @ivanov`;
- `PROFILE_URL`: ссылки на профили вроде `github.com/ivan_dev`, `vk.com/id123456`, `t.me/ivanov`;
- `SOCIAL_HANDLE`: handles вида `@ivan_dev`;
- `USERNAME`: явно подписанные логины вида `логин: petrov`.

Связка `никнейм/логин + ресурс` токенизируется целиком, потому что именно комбинация идентификатора и площадки может указывать на конкретного человека.

Публичный класс `Patterns` можно использовать при настройке собственных правил.

Для полного контроля можно передать явный список правил:

```python
from lightanon.rag import Patterns, TextSanitizer

sanitizer = TextSanitizer(rules=[("EMAIL", Patterns.EMAIL)])
```

## Metadata

В RAG персональные данные часто находятся не только в тексте чанка, но и в metadata: `source_url`, `author`, `tags`, `file_path`, ссылках на профили и идентификаторах аккаунтов.

```python
sanitizer = TextSanitizer(profile="ru_152")

metadata = {
    "source_url": "https://github.com/ivan_dev",
    "author": "Telegram: @ivanov_dev",
    "tags": ["client", "ivan@example.com"],
}

clean_metadata = sanitizer.sanitize_metadata(metadata)
```

`sanitize_metadata(...)` рекурсивно обрабатывает строковые значения внутри `dict`, `list`, `tuple` и `set`. Нестроковые значения сохраняются.

## Scan и отчет

`scan(...)` проверяет текст без замены и без записи в vault:

```python
sanitizer = TextSanitizer(profile="ru_152")
report = sanitizer.scan("Email ivan@example.com, ИНН 7707083893")
```

Пример отчета:

```python
{
    "entities": {"EMAIL": 1, "INN": 1},
    "total": 2,
    "residual_risk": "medium",
}
```

`sanitize_with_report(...)` возвращает очищенный текст и отчет, где отдельно показаны найденные сущности до обработки и остаточные сущности после обработки.

## Кастомное правило

```python
sanitizer.add_rule("CONTRACT", r"\b\d{2}-\d{4}/\d{2}\b")
```

Пользовательские правила добавляются с более высоким приоритетом, чем встроенные.

## Vault
Бэкенд по умолчанию: `MemoryVault`.
- быстрый,
- хранит данные только в памяти,
- не сохраняется между перезапусками.

Для production лучше реализовать собственный `BaseVault` (например Redis/PostgreSQL).

Минимальный интерфейс `BaseVault`:
- `get_value(token: str)`,
- `get_token(value: str)`,
- `save(token: str, value: str)`.

`FileVault` сохраняет соответствия в JSON-файл и подходит для локального CLI:

```python
from lightanon.rag import FileVault, TextSanitizer

sanitizer = TextSanitizer(vault=FileVault("vault.json"))
```

`FileVault` валидирует структуру JSON при чтении и записывает изменения через временный файл с атомарной заменой. Метод `stats()` возвращает только счетчики, без исходных значений.

## CLI

RAG-команды работают с обычными текстовыми файлами и требуют `--vault`, чтобы восстановление можно было выполнить отдельным запуском:

```bash
lightanon rag sanitize input.txt sanitized.txt --vault vault.json
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --profile ru_152
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag sanitize input.txt sanitized.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE
lightanon rag scan input.txt --profile ru_152
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag inspect-vault vault.json
```

`sanitize` записывает токены в vault. `restore` использует тот же vault для замены токенов исходными значениями.
`scan` печатает JSON-отчет без записи в vault и без раскрытия исходных значений.
`inspect-vault` показывает количество сохраненных маппингов и распределение по типам токенов, не раскрывая сохраненные значения.
`--profile` включает готовый профиль правил. Доступные профили: `basic`, `ru_152`, `ru_152_strict`.
`--rules` включает только указанные встроенные правила и полезен, когда нужно отключить широкую эвристику ФИО, явно включить `INN` или обработать интернет-идентификаторы.
