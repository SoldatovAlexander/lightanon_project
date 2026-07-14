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

Публичный класс `Patterns` можно использовать при настройке собственных правил.

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

## CLI

RAG-команды работают с обычными текстовыми файлами и требуют `--vault`, чтобы восстановление можно было выполнить отдельным запуском:

```bash
lightanon rag sanitize input.txt sanitized.txt --vault vault.json
lightanon rag restore llm_response.txt restored.txt --vault vault.json
```

`sanitize` записывает токены в vault. `restore` использует тот же vault для замены токенов исходными значениями.
