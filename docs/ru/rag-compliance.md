# RAG и 152-ФЗ

Этот раздел описывает инженерные настройки `lightanon.rag` для сценариев, где текст или metadata могут содержать персональные данные по 152-ФЗ. Это не юридическое заключение; финальную модель обработки, основания и согласия должен определять оператор персональных данных.

## Основной принцип

Для RAG важно считать персональными не только очевидные поля вроде ФИО, телефона, email, паспорта или СНИЛС. По 152-ФЗ персональные данные могут включать любую информацию, относящуюся к прямо или косвенно определенному физическому лицу.

Практический вывод для RAG:
- обрабатывать свободный текст до отправки в LLM;
- обрабатывать metadata чанков;
- не считать публичный источник автоматическим разрешением на раскрытие данных в ответе;
- хранить vault как объект, содержащий исходные персональные данные.

## Никнеймы, логины и ресурсы

Для RAG особенно важны интернет-идентификаторы. Связка `никнейм/логин + ресурс`, например `никнейм ivan_dev на Habr` или `Telegram: @ivanov`, может указывать на конкретного человека.

Используйте профиль `ru_152` или явно включайте правила:

```python
from lightanon.rag import TextSanitizer

sanitizer = TextSanitizer(profile="ru_152")
clean = sanitizer.sanitize("Публикация: никнейм ivan_dev на Habr")
```

Через CLI:

```bash
lightanon rag sanitize input.txt output.txt --vault vault.json --profile ru_152
```

Для точечного режима:

```bash
lightanon rag sanitize input.txt output.txt --vault vault.json --rules ONLINE_ACCOUNT,PROFILE_URL,SOCIAL_HANDLE,USERNAME
```

## Рекомендуемые профили

`basic`:
- минимальный базовый набор;
- подходит для общих демо и низкорисковых текстов;
- не включает `INN` и интернет-идентификаторы по умолчанию.

`ru_152`:
- включает базовые правила;
- добавляет `INN`;
- добавляет интернет-идентификаторы: `ONLINE_ACCOUNT`, `PROFILE_URL`, `SOCIAL_HANDLE`, `USERNAME`;
- рекомендуемый профиль для русскоязычных RAG-сценариев с потенциальными ПД.

`ru_152_strict`:
- включает `ru_152`;
- добавляет технические идентификаторы: `IP_ADDRESS`, `COOKIE_ID`, `DEVICE_ID`, `USER_ID`;
- полезен для логов, тикетов поддержки, веб-аналитики и выгрузок из систем.

## Metadata RAG-документов

Персональные данные часто находятся не в тексте чанка, а в metadata:

```python
metadata = {
    "source_url": "https://github.com/ivan_dev",
    "author": "Telegram: @ivanov",
    "file_path": "/users/petrov/contracts/a.txt",
    "tags": ["client", "ivan@example.com"],
}
```

Обрабатывайте metadata тем же sanitizer и тем же vault:

```python
clean_metadata = sanitizer.sanitize_metadata(metadata)
```

Это сохраняет консистентность токенов между текстом и metadata.

Для обработки RAG-документа одной операцией:

```python
clean_text, clean_metadata = sanitizer.sanitize_document(text, metadata)
restored_text, restored_metadata = sanitizer.deanonymize_document(
    clean_text,
    clean_metadata,
    policy="mask",
)
```

## Проверка перед отправкой в LLM

Перед отправкой текста во внешний LLM используйте `scan` или `sanitize_with_report`:

```python
clean, report = sanitizer.sanitize_with_report(text)
```

CLI:

```bash
lightanon rag scan input.txt --profile ru_152
```

Отчет не раскрывает исходные значения, но показывает типы и количество найденных сущностей.

## Политика восстановления ответа

Не всегда нужно восстанавливать ПД в финальном ответе LLM. Для безопасного вывода используйте политики:

```python
sanitizer.deanonymize(answer, policy="no_personal_data")
sanitizer.deanonymize(answer, policy="mask")
sanitizer.deanonymize(answer, policy="restore_allowed_only", allowed_entity_types=["EMAIL"])
```

CLI:

```bash
lightanon rag restore answer.txt restored.txt --vault vault.json --policy mask
```

Рекомендуемая практика: по умолчанию использовать `mask` или `no_personal_data`, а `restore` включать только там, где восстановление действительно нужно и допустимо.

## Vault

Vault хранит соответствие токенов исходным значениям. Это значит, что vault содержит персональные данные и должен защищаться как соответствующий объект обработки.

Рекомендуемые меры:
- хранить vault отдельно от публичных артефактов;
- не коммитить vault в репозиторий;
- ограничивать доступ к файлу;
- задавать TTL для временных RAG-сессий;
- удалять маппинги после завершения сценария;
- использовать `inspect-vault`, а не просмотр файла, если нужны только счетчики.

Команды жизненного цикла:

```bash
lightanon rag inspect-vault vault.json
lightanon rag delete-token vault.json '[EMAIL_aaaaaaaa]'
lightanon rag delete-value vault.json 'ivan@example.com'
lightanon rag purge-expired vault.json
lightanon rag clear-vault vault.json
```

## Практический чеклист

Перед отправкой RAG-контекста в LLM:
- выбрать профиль `ru_152` или `ru_152_strict`;
- обработать текст через `sanitize`;
- обработать metadata через `sanitize_metadata`;
- проверить результат через `scan` или `sanitize_with_report`;
- хранить vault как защищаемый файл;
- выбрать безопасную политику `deanonymize` для ответа.
