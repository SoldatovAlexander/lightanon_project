# Руководство по RAG

`lightanon.rag` нужен для обратимого обезличивания текста:
1. скрыть чувствительные данные перед отправкой в LLM,
2. восстановить данные в итоговом ответе для пользователя.

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

## Кастомное правило

```python
sanitizer.add_rule("CONTRACT", r"\b\d{2}-\d{4}/\d{2}\b")
```

## Vault
Бэкенд по умолчанию: `MemoryVault`.
- быстрый,
- хранит данные только в памяти,
- не сохраняется между перезапусками.

Для production лучше реализовать собственный `BaseVault` (например Redis/PostgreSQL).
