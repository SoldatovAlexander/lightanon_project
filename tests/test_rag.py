import json
import re

import pytest

from lightanon.rag import BaseVault, FileVault, MemoryVault, Patterns, TextSanitizer


def test_rag_public_api_exports():
    assert TextSanitizer
    assert Patterns
    assert MemoryVault
    assert FileVault
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


def test_custom_rule_wins_over_overlapping_builtin_rule():
    sanitizer = TextSanitizer()
    sanitizer.add_rule("WORK_EMAIL", r"ivan@example\.com")

    clean = sanitizer.sanitize("Email: ivan@example.com")

    assert re.search(r"\[WORK_EMAIL_[a-f0-9]{8}\]", clean)
    assert "[EMAIL_" not in clean


def test_builtin_rules_can_be_selected():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])

    clean = sanitizer.sanitize("Email ivan@example.com, phone +7 900 123-45-67.")

    assert "ivan@example.com" not in clean
    assert "+7 900 123-45-67" in clean
    assert re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean)


def test_inn_is_opt_in_and_does_not_conflict_with_passport():
    default_sanitizer = TextSanitizer()
    default_clean = default_sanitizer.sanitize("ИНН 7707083893.")
    assert default_clean == "ИНН 7707083893."

    inn_sanitizer = TextSanitizer(enabled_rules=["INN"])
    inn_clean = inn_sanitizer.sanitize("ИНН 7707083893.")
    assert "7707083893" not in inn_clean
    assert re.search(r"\[INN_[a-f0-9]{8}\]", inn_clean)

    passport_clean = TextSanitizer().sanitize("Паспорт 4500 123456.")
    assert "4500 123456" not in passport_clean
    assert re.search(r"\[PASSPORT_[a-f0-9]{8}\]", passport_clean)


def test_online_account_pair_is_tokenized_as_single_entity():
    sanitizer = TextSanitizer(enabled_rules=["ONLINE_ACCOUNT", "USERNAME"])

    clean = sanitizer.sanitize("Публикация: никнейм ivan_dev на Habr.")

    assert "ivan_dev" not in clean
    assert "Habr" not in clean
    assert re.search(r"\[ONLINE_ACCOUNT_[a-f0-9]{8}\]", clean)
    assert "[USERNAME_" not in clean


def test_resource_account_is_tokenized_as_single_entity():
    sanitizer = TextSanitizer(enabled_rules=["ONLINE_ACCOUNT", "SOCIAL_HANDLE"])

    clean = sanitizer.sanitize("Контакт: Telegram: @ivanov_dev.")

    assert "Telegram" not in clean
    assert "@ivanov_dev" not in clean
    assert re.search(r"\[ONLINE_ACCOUNT_[a-f0-9]{8}\]", clean)
    assert "[SOCIAL_HANDLE_" not in clean


def test_profile_url_and_social_handle_are_detected():
    sanitizer = TextSanitizer(enabled_rules=["PROFILE_URL", "SOCIAL_HANDLE"])

    clean = sanitizer.sanitize("Профили: github.com/ivan_dev и @petrov_dev.")

    assert "github.com/ivan_dev" not in clean
    assert "@petrov_dev" not in clean
    assert re.search(r"\[PROFILE_URL_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[SOCIAL_HANDLE_[a-f0-9]{8}\]", clean)


def test_online_identifier_rules_do_not_break_email_detection():
    sanitizer = TextSanitizer(enabled_rules=["ONLINE_ACCOUNT", "SOCIAL_HANDLE", "EMAIL"])

    clean = sanitizer.sanitize("Email ivan@example.com, handle @ivan_dev.")

    assert "ivan@example.com" not in clean
    assert "@ivan_dev" not in clean
    assert re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[SOCIAL_HANDLE_[a-f0-9]{8}\]", clean)


def test_basic_profile_keeps_previous_default_rules():
    sanitizer = TextSanitizer(profile="basic")

    clean = sanitizer.sanitize("Email ivan@example.com, ИНН 7707083893, Telegram: @ivanov_dev.")

    assert "ivan@example.com" not in clean
    assert "7707083893" in clean
    assert "Telegram: @ivanov_dev" in clean
    assert re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean)


def test_ru_152_profile_includes_inn_and_online_identifiers():
    sanitizer = TextSanitizer(profile="ru_152")

    clean = sanitizer.sanitize("ИНН 7707083893, никнейм ivan_dev на Habr.")

    assert "7707083893" not in clean
    assert "ivan_dev" not in clean
    assert "Habr" not in clean
    assert re.search(r"\[INN_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[ONLINE_ACCOUNT_[a-f0-9]{8}\]", clean)


def test_ru_152_strict_profile_includes_technical_identifiers():
    sanitizer = TextSanitizer(profile="ru_152_strict")

    clean = sanitizer.sanitize(
        "IP 192.168.1.10, session_id=abc123456, device_id: dev-12345678, user_id: 123456."
    )

    assert "192.168.1.10" not in clean
    assert "session_id=abc123456" not in clean
    assert "device_id: dev-12345678" not in clean
    assert "user_id: 123456" not in clean
    assert re.search(r"\[IP_ADDRESS_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[COOKIE_ID_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[DEVICE_ID_[a-f0-9]{8}\]", clean)
    assert re.search(r"\[USER_ID_[a-f0-9]{8}\]", clean)


def test_enabled_rules_override_profile():
    sanitizer = TextSanitizer(profile="ru_152_strict", enabled_rules=["EMAIL"])

    clean = sanitizer.sanitize("Email ivan@example.com, IP 192.168.1.10.")

    assert "ivan@example.com" not in clean
    assert "192.168.1.10" in clean
    assert re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean)


def test_unknown_profile_fails_fast():
    with pytest.raises(ValueError, match="Unknown RAG profile"):
        TextSanitizer(profile="unknown")


def test_unknown_builtin_rule_fails_fast():
    with pytest.raises(ValueError, match="Unknown built-in RAG rule"):
        TextSanitizer(enabled_rules=["EMAIL", "UNKNOWN"])


def test_unknown_token_is_left_unchanged():
    sanitizer = TextSanitizer()

    assert sanitizer.deanonymize("Hello [EMAIL_aaaaaaaa]") == "Hello [EMAIL_aaaaaaaa]"


def test_sanitize_metadata_recursively_sanitizes_strings():
    sanitizer = TextSanitizer(profile="ru_152")
    metadata = {
        "source_url": "https://github.com/ivan_dev",
        "author": "Telegram: @ivanov_dev",
        "tags": ["client", "ivan@example.com"],
        "nested": {
            "inn": "ИНН 7707083893",
            "score": 10,
            "active": True,
            "empty": None,
        },
    }

    clean = sanitizer.sanitize_metadata(metadata)

    assert metadata["source_url"] == "https://github.com/ivan_dev"
    assert "github.com/ivan_dev" not in clean["source_url"]
    assert "Telegram" not in clean["author"]
    assert "@ivanov_dev" not in clean["author"]
    assert "ivan@example.com" not in clean["tags"][1]
    assert "7707083893" not in clean["nested"]["inn"]
    assert clean["nested"]["score"] == 10
    assert clean["nested"]["active"] is True
    assert clean["nested"]["empty"] is None
    assert re.search(r"\[PROFILE_URL_[a-f0-9]{8}\]", clean["source_url"])
    assert re.search(r"\[ONLINE_ACCOUNT_[a-f0-9]{8}\]", clean["author"])
    assert re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean["tags"][1])
    assert re.search(r"\[INN_[a-f0-9]{8}\]", clean["nested"]["inn"])


def test_sanitize_metadata_reuses_tokens_with_text_sanitize():
    sanitizer = TextSanitizer(profile="ru_152")

    clean_text = sanitizer.sanitize("Email: ivan@example.com")
    clean_metadata = sanitizer.sanitize_metadata({"email": "ivan@example.com"})

    text_token = re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean_text).group()
    metadata_token = re.search(r"\[EMAIL_[a-f0-9]{8}\]", clean_metadata["email"]).group()
    assert text_token == metadata_token


def test_sanitize_metadata_preserves_container_types():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])
    metadata = {
        "tuple": ("ivan@example.com", 1),
        "set": {"ivan@example.com", "public"},
    }

    clean = sanitizer.sanitize_metadata(metadata)

    assert isinstance(clean["tuple"], tuple)
    assert isinstance(clean["set"], set)
    assert "ivan@example.com" not in str(clean)


def test_sanitize_metadata_requires_dict():
    sanitizer = TextSanitizer()

    with pytest.raises(ValueError, match="metadata must be a dictionary"):
        sanitizer.sanitize_metadata(["ivan@example.com"])


def test_scan_reports_entity_counts_without_values():
    sanitizer = TextSanitizer(profile="ru_152")

    report = sanitizer.scan("Email ivan@example.com, ИНН 7707083893, Telegram: @ivanov_dev.")

    assert report["entities"] == {"ONLINE_ACCOUNT": 1, "EMAIL": 1, "INN": 1}
    assert report["total"] == 3
    assert report["residual_risk"] == "high"
    assert "ivan@example.com" not in str(report)
    assert "7707083893" not in str(report)


def test_scan_does_not_write_to_vault():
    vault = MemoryVault()
    sanitizer = TextSanitizer(vault=vault, enabled_rules=["EMAIL"])

    sanitizer.scan("Email ivan@example.com")

    assert vault.get_token("ivan@example.com") is None


def test_sanitize_with_report_includes_residual_scan():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])

    clean, report = sanitizer.sanitize_with_report("Email ivan@example.com, phone +7 900 123-45-67.")

    assert "ivan@example.com" not in clean
    assert "+7 900 123-45-67" in clean
    assert report["entities"] == {"EMAIL": 1}
    assert report["total"] == 1
    assert report["residual_entities"] == {}
    assert report["residual_total"] == 0
    assert report["residual_risk"] == "low"


def test_file_vault_persists_mappings(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "ivan@example.com")

    restored_vault = FileVault(str(vault_path))

    assert restored_vault.get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"
    assert restored_vault.get_token("ivan@example.com") == "[EMAIL_aaaaaaaa]"


def test_file_vault_reuses_token_across_sanitizer_instances(tmp_path):
    vault_path = tmp_path / "vault.json"

    first = TextSanitizer(vault=FileVault(str(vault_path))).sanitize("Email: ivan@example.com")
    second = TextSanitizer(vault=FileVault(str(vault_path))).sanitize("Repeat: ivan@example.com")

    first_token = re.search(r"\[EMAIL_[a-f0-9]{8}\]", first).group()
    second_token = re.search(r"\[EMAIL_[a-f0-9]{8}\]", second).group()
    assert first_token == second_token


def test_file_vault_rebuilds_reverse_mapping(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault_path.write_text(
        json.dumps({"token_to_value": {"[EMAIL_aaaaaaaa]": "ivan@example.com"}}),
        encoding="utf-8",
    )

    vault = FileVault(str(vault_path))

    assert vault.get_token("ivan@example.com") == "[EMAIL_aaaaaaaa]"


def test_file_vault_rejects_invalid_json(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid vault JSON"):
        FileVault(str(vault_path))


def test_file_vault_stats_do_not_include_values(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "ivan@example.com")
    vault.save("[CONTRACT_ID_bbbbbbbb]", "12-3456/78")

    stats = vault.stats()

    assert stats["total"] == 2
    assert stats["by_type"] == {"EMAIL": 1, "CONTRACT_ID": 1}
    assert "ivan@example.com" not in str(stats)
