# Переход на 0.3.0

Версия 0.3.0 содержит изменения API, связанные с безопасностью. До развёртывания обновите код приложения и сохранённые FileVault.

## Правила для таблиц

- `Hash` теперь требует непустой секретный `salt` и использует HMAC-SHA-256. Старые значения SHA-256 несовместимы.
- `Mask` больше не оставляет короткие значения без изменений.
- При ошибке Engine очищает выходной столбец и записывает безопасный код ошибки в отчёт. Любая запись аудита со статусом, отличным от success, означает ошибку batch-обработки.

## Восстановление в RAG

`deanonymize()` теперь по умолчанию маскирует токены. Для раскрытия сохраните scope, полученный при обезличивании, и передайте его явно:

```python
clean, token_scope = sanitizer.sanitize_with_scope(text)
restored = sanitizer.deanonymize(answer, policy="restore", token_scope=token_scope)
```

Храните scope в доверенном серверном контексте запроса. Это ограничение одной операции восстановления, а не пользовательский токен авторизации.

## FileVault v2

API vault стал типизированным:

```python
vault.save(token, "EMAIL", "person@example.com")
vault.get_token("EMAIL", "person@example.com")
```

Одинаковый текст для разных типов сущностей больше не получает общий токен. FileVault v2 использует версионированный payload, неизменяемые маппинги и lock-файл. При ключе Fernet он принимает только зашифрованный v2-envelope; legacy plaintext-файл отклоняется, а не читается неявно.

Перенесите legacy plaintext vault в новый файл. Исходный файл сохраняется:

```bash
export LIGHTANON_VAULT_KEY='...'
lightanon rag migrate-vault legacy-vault.json vault.v2 --vault-key-env LIGHTANON_VAULT_KEY
```

В lifecycle-командах указывайте тип сущности:

```bash
lightanon rag delete-value vault.v2 EMAIL 'person@example.com'
```

## Проверка перехода

1. Запустите тесты и RAG regression corpus.
2. Перенесите копию каждого legacy vault и проверьте восстановление вне production.
3. Убедитесь, что код хранит scope на сервере и передаёт его только при разрешённом восстановлении.
4. Разверните новый пакет с управляемым ключом Fernet и храните legacy vault до окончания проверки.
