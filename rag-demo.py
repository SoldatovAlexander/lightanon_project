from lightanon.rag import TextSanitizer


def test_rag_flow():
    rag = TextSanitizer()

    # 1. Исходный текст (ПДн)
    original = "Заявитель Иванов Иван, паспорт 4500 123456, телефон +7 900 123-45-67."
    print(f"ORIGINAL: {original}")

    # 2. Обезличивание (Sanitize)
    clean = rag.sanitize(original)
    print(f"SANITIZED (To LLM): {clean}")

    # Проверка: ПДн не должны остаться
    assert "Иванов Иван" not in clean
    assert "4500 123456" not in clean
    assert "[PERSON_" in clean
    assert "[PASSPORT_" in clean

    # 3. Симуляция ответа LLM (RAG)
    # Представим, что LLM проанализировала токены и дала ответ
    llm_response = f"Подтверждаю, {clean.split(',')[0].replace('Заявитель ', '')} имеет валидные документы."
    print(f"LLM RESPONSE: {llm_response}")

    # 4. Восстановление (Deanonymize)
    final = rag.deanonymize(llm_response)
    print(f"FINAL (To User): {final}")

    # Проверка: данные вернулись
    assert "Иванов Иван" in final


if __name__ == "__main__":
    test_rag_flow()