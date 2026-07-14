import re

from lightanon.rag import BaseVault, MemoryVault, Patterns, TextSanitizer


def test_rag_public_api_exports():
    assert TextSanitizer
    assert Patterns
    assert MemoryVault
    assert BaseVault


def test_sanitize_replaces_builtin_entities():
    sanitizer = TextSanitizer()
    text = (
        "Иванов Иван, email ivan@example.com, phone +7 900 123-45-67, "
        "passport 4500 123456, snils 123-456-789 00, card 4111 1111 1111 1111."
    )

    clean = sanitizer.sanitize(text)

    assert "ivan@example.com" not in clean
    assert "+7 900 123-45-67" not in clean
    assert "4500 123456" not in clean
    assert "123-456-789 00" not in clean
    assert "4111 1111 1111 1111" not in clean
    assert re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[PHONE_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[PASSPORT_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[SNILS_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[CARD_[a-f0-9]{8}\]", clean)


def test_deanonymize_restores_original_values():
    sanitizer = TextSanitizer()
    original = "Напишите Иванов Иван на ivan@example.com или +7 900 123-45-67."

    clean = sanitizer.sanitize(original)
    answer = f"Подтверждаю: {clean}"
    restored = sanitizer.deanonymize(answer)

    assert restored == f"Подтверждаю: {original}"


def test_same_value_reuses_same_token():
    sanitizer = TextSanitizer()

    first = sanitizer.sanitize("Email: ivan@example.com")
    second = sanitizer.sanitize("Repeat: ivan@example.com")

    first_token = re.search(r"\[EMAIL_[a-f0-9]{8}\]", first).group()
    second_token = re.search(r"\[EMAIL_[a-f0-9]{8}\]", second).group()
    assert first_token == second_token


def test_custom_rule_has_priority_and_can_be_restored():
    sanitizer = TextSanitizer()
    sanitizer.add_rule("contract-id", r"\b\d{2}-\d{4}/\d{2}\b")

    clean = sanitizer.sanitize("Договор 12-3456/78 подписан.")

    assert "12-3456/78" not in clean
    assert re.search(r"\[CONTRACT_ID_[a-f0-9]{8}\]", clean)
    assert sanitizer.deanonymize(clean) == "Договор 12-3456/78 подписан."


def test_unknown_token_is_left_unchanged():
    sanitizer = TextSanitizer()

    assert sanitizer.deanonymize("Hello [EMAIL_aaaaaaaa]") == "Hello [EMAIL_aaaaaaaa]"
