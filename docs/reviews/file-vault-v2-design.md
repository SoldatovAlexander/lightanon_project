# FileVault v2: формат, целостность и миграция

Статус: proposed. Документ определяет контракт для волны 2 из [release review](./release-review-2026-09-05.md). Цель — устранить подмену plaintext при ключе, потерю данных между экземплярами, смешение типов сущностей и противоречивые индексы в одном согласованном изменении.

## Решения

1. API vault становится типизированным. Поиск и сохранение используют `entity_type`, `value` и необязательный `namespace`. Sanitizer всегда передаёт тип, из которого создаётся токен.
2. Запись является единственным источником истины. Отдельный сериализованный `value_to_token` не хранится; обратный индекс строится из entries и проверяется при загрузке.
3. Пары неизменяемы. Повторная запись точно такой же пары идемпотентна. Конфликт token или обратного ключа вызывает `MappingConflict` без частичного изменения состояния.
4. Файловый backend использует lock-файл на весь цикл read-modify-write. Каждый read и mutation загружает актуальное состояние внутри блокировки; экземпляр не доверяет снимку, созданному при `__init__`.
5. При ключе разрешён только зашифрованный формат v2. Plain JSON и legacy-файлы с ключом отклоняются. Legacy переносится отдельной командой миграции.

## API

```python
class BaseVault:
    def get_value(self, token: str) -> str | None: ...
    def get_token(
        self,
        entity_type: str,
        value: str,
        namespace: str = "default",
    ) -> str | None: ...
    def save(
        self,
        token: str,
        entity_type: str,
        value: str,
        namespace: str = "default",
        ttl_seconds: int | None = None,
    ) -> None: ...
```

`entity_type` соответствует `^[A-Z][A-Z0-9_]*$`. `namespace` — непустая строка, по умолчанию `default`. Версия v2 не делает старый двухаргументный `save(token, value)` безопасным, поэтому он не сохраняется как скрытый fallback. Для внешних реализаций `BaseVault` будет понятная ошибка о несовместимом методе и migration guide.

`MappingConflict` — отдельное исключение vault. Оно возникает, когда:

- token уже связан с другим `(namespace, entity_type, value)`;
- `(namespace, entity_type, value)` уже связан с другим token;
- entries при загрузке содержат две записи с одинаковым обратным ключом.

## Формат v2

Внутренний payload, который валидируется до построения индекса:

```json
{
  "format": "lightanon.file-vault",
  "version": 2,
  "entries": {
    "[EMAIL_0123...]": {
      "entity_type": "EMAIL",
      "namespace": "default",
      "value": "user@example.com",
      "created_at": "2026-09-06T10:00:00+00:00",
      "last_used_at": "2026-09-06T10:00:00+00:00",
      "expires_at": null
    }
  }
}
```

Plaintext FileVault v2 сохраняет этот payload напрямую. Encrypted FileVault v2 сохраняет JSON-envelope:

```json
{
  "format": "lightanon.file-vault",
  "version": 2,
  "encrypted": true,
  "ciphertext": "Fernet token"
}
```

Fernet шифрует весь payload. При переданном ключе код принимает только envelope с `encrypted: true`, расшифровывает ciphertext и проверяет format/version payload. При отсутствии ключа encrypted envelope отклоняется. Plaintext v2 с ключом также отклоняется. Поэтому замена ciphertext JSON-файлом не переводит процесс в менее защищённый режим.

## Конкурентный доступ

Для FileVault добавить кроссплатформенную межпроцессную блокировку, например `filelock`. Путь блокировки: `<vault-path>.lock`. Под блокировкой выполняются:

1. чтение и валидация текущего файла;
2. построение обратного индекса;
3. проверка конфликтов, TTL и изменение состояния;
4. сериализация, шифрование и атомарная замена файла.

Операции чтения также берут lock и перезагружают состояние, чтобы не возвращать устаревший token после удаления другим процессом. Для небольшого локального FileVault это разумная цена за корректность. Для высоконагруженного сервиса рекомендуемый backend — транзакционная БД или Redis; FileVault не обещает высокую пропускную способность.

## Миграция

Новая команда:

```bash
lightanon rag migrate-vault <source.json> <destination.vault> \
  --vault-key-env LIGHTANON_VAULT_KEY
```

Ограничения:

- source и destination должны быть разными файлами;
- source читается только как legacy plaintext vault без ключа;
- тип каждой legacy-записи извлекается из токена; невалидный token завершает миграцию ошибкой;
- destination создаётся атомарно, затем повторно открывается с ключом и сравнивается по количеству и записям;
- source никогда не удаляется автоматически; команда печатает путь, который можно удалить после отдельной проверки.

Новый `sanitize` не выполняет миграцию неявно. При попытке открыть legacy vault с ключом он сообщает, что нужно запустить `migrate-vault`.

## Порядок реализации

1. Добавить типы, `MappingConflict`, валидацию формата и unit-тесты MemoryVault.
2. Реализовать v2 read/write, encrypted envelope и тесты подмены plaintext/ciphertext.
3. Добавить lock и тесты с двумя экземплярами и двумя процессами для plaintext/encrypted vault.
4. Подключить sanitizer к typed lookup/save, добавить namespace в API и тест межтипового значения.
5. Добавить CLI-migration, документацию и migration guide.

## Критерии готовности

- plaintext не читается с ключом;
- неверный ключ и изменённый ciphertext не проходят проверку;
- два процесса не теряют изменения и не возвращают удалённые значения;
- один value под EMAIL и PUBLIC не переиспользует token;
- конфликт не меняет файл и обратный индекс;
- миграция создаёт читаемый encrypted v2 vault и не изменяет source;
- полный набор unit- и CLI-тестов проходит, а README и RU/EN-документация описывают новый контракт.
