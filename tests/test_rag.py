import json
import re
import stat

import pytest
from cryptography.fernet import Fernet

from lightanon.rag import (
    BaseVault,
    FileVault,
    MappingConflict,
    MemoryVault,
    OrganizationProfile,
    Patterns,
    TextSanitizer,
    migrate_legacy_file_vault,
)
from lightanon.rag import sanitizer as sanitizer_module


def _token_scope(*values):
    scope = {}
    for value in values:
        for token in re.findall(r"\[[A-Z][A-Z0-9_]*_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", str(value)):
            scope[token] = scope.get(token, 0) + 1
    return scope


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
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[PHONE_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[PASSPORT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[SNILS_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[CARD_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_deanonymize_restores_original_values():
    sanitizer = TextSanitizer()
    original = "Напишите Иванов Иван на ivan@example.com или +7 900 123-45-67."

    clean, token_scope = sanitizer.sanitize_with_scope(original)
    answer = f"Подтверждаю: {clean}"
    restored = sanitizer.deanonymize(answer, policy="restore", token_scope=token_scope)

    assert restored == f"Подтверждаю: {original}"


def test_deanonymize_no_personal_data_policy_leaves_tokens():
    sanitizer = TextSanitizer()
    clean = sanitizer.sanitize("Email: ivan@example.com")

    restored = sanitizer.deanonymize(clean, policy="no_personal_data")

    assert restored == clean
    assert "ivan@example.com" not in restored


def test_deanonymize_mask_policy_replaces_tokens_with_entity_labels():
    sanitizer = TextSanitizer()
    clean = sanitizer.sanitize("Email: ivan@example.com")

    restored = sanitizer.deanonymize(clean, policy="mask")

    assert restored == "Email: [EMAIL]"
    assert "ivan@example.com" not in restored


def test_deanonymize_restore_allowed_only_policy():
    sanitizer = TextSanitizer(profile="ru_152")
    clean, token_scope = sanitizer.sanitize_with_scope("Email: ivan@example.com. ИНН 7707083893.")

    restored = sanitizer.deanonymize(
        clean,
        policy="restore_allowed_only",
        allowed_entity_types=["EMAIL"],
        token_scope=token_scope,
    )

    assert "ivan@example.com" in restored
    assert "7707083893" not in restored
    assert re.search(r"\[INN_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", restored)


def test_deanonymize_unknown_policy_fails_fast():
    sanitizer = TextSanitizer()

    with pytest.raises(ValueError, match="Unknown deanonymization policy"):
        sanitizer.deanonymize("[EMAIL_aaaaaaaa]", policy="unknown")


def test_same_value_reuses_same_token():
    sanitizer = TextSanitizer()

    first = sanitizer.sanitize("Email: ivan@example.com")
    second = sanitizer.sanitize("Repeat: ivan@example.com")

    first_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", first).group()
    second_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", second).group()
    assert first_token == second_token


def test_new_tokens_use_128_bits_of_randomness():
    clean = TextSanitizer(enabled_rules=["EMAIL"]).sanitize("Email: ivan@example.com")

    token = re.search(r"\[EMAIL_[a-f0-9]{32}\]", clean)
    assert token is not None


def test_token_collision_is_regenerated(monkeypatch):
    vault = MemoryVault()
    collision = f"[EMAIL_{'a' * 32}]"
    replacement = f"[EMAIL_{'b' * 32}]"
    vault.save(collision, "EMAIL", "existing@example.com")
    generated_ids = iter(["a" * 32, "b" * 32])
    monkeypatch.setattr(sanitizer_module.secrets, "token_hex", lambda _: next(generated_ids))

    clean = TextSanitizer(vault=vault, enabled_rules=["EMAIL"]).sanitize("Email: new@example.com")

    assert replacement in clean
    assert vault.get_value(collision) == "existing@example.com"
    assert vault.get_value(replacement) == "new@example.com"


def test_custom_rule_has_priority_and_can_be_restored():
    sanitizer = TextSanitizer()
    sanitizer.add_rule("contract-id", r"\b\d{2}-\d{4}/\d{2}\b")

    clean, token_scope = sanitizer.sanitize_with_scope("Договор 12-3456/78 подписан.")

    assert "12-3456/78" not in clean
    assert re.search(r"\[CONTRACT_ID_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert sanitizer.deanonymize(clean, policy="restore", token_scope=token_scope) == "Договор 12-3456/78 подписан."


def test_custom_rule_wins_over_overlapping_builtin_rule():
    sanitizer = TextSanitizer()
    sanitizer.add_rule("WORK_EMAIL", r"ivan@example\.com")

    clean = sanitizer.sanitize("Email: ivan@example.com")

    assert re.search(r"\[WORK_EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert "[EMAIL_" not in clean


def test_builtin_rules_can_be_selected():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])

    clean = sanitizer.sanitize("Email ivan@example.com, phone +7 900 123-45-67.")

    assert "ivan@example.com" not in clean
    assert "+7 900 123-45-67" in clean
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_inn_is_opt_in_and_does_not_conflict_with_passport():
    default_sanitizer = TextSanitizer()
    default_clean = default_sanitizer.sanitize("ИНН 7707083893.")
    assert default_clean == "ИНН 7707083893."

    inn_sanitizer = TextSanitizer(enabled_rules=["INN"])
    inn_clean = inn_sanitizer.sanitize("ИНН 7707083893.")
    assert "7707083893" not in inn_clean
    assert re.search(r"\[INN_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", inn_clean)

    passport_clean = TextSanitizer().sanitize("Паспорт 4500 123456.")
    assert "4500 123456" not in passport_clean
    assert re.search(r"\[PASSPORT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", passport_clean)


def test_passport_label_and_name_initials_are_sanitized():
    sanitizer = TextSanitizer()

    clean = sanitizer.sanitize("Паспорт серия 4500 № 123456 выдан Иванову И.И.")

    assert "4500" not in clean
    assert "123456" not in clean
    assert "Иванову И.И." not in clean
    assert re.search(r"\[PASSPORT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[PERSON_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_phone_pattern_does_not_match_inside_a_longer_number():
    sanitizer = TextSanitizer(enabled_rules=["PHONE"])

    assert sanitizer.sanitize("ID 180099912345670") == "ID 180099912345670"


def test_online_account_pair_is_tokenized_as_single_entity():
    sanitizer = TextSanitizer(enabled_rules=["ONLINE_ACCOUNT", "USERNAME"])

    clean = sanitizer.sanitize("Публикация: никнейм ivan_dev на Habr.")

    assert "ivan_dev" not in clean
    assert "Habr" not in clean
    assert re.search(r"\[ONLINE_ACCOUNT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert "[USERNAME_" not in clean


def test_resource_account_is_tokenized_as_single_entity():
    sanitizer = TextSanitizer(enabled_rules=["ONLINE_ACCOUNT", "SOCIAL_HANDLE"])

    clean = sanitizer.sanitize("Контакт: Telegram: @ivanov_dev.")

    assert "Telegram" not in clean
    assert "@ivanov_dev" not in clean
    assert re.search(r"\[ONLINE_ACCOUNT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert "[SOCIAL_HANDLE_" not in clean


def test_profile_url_and_social_handle_are_detected():
    sanitizer = TextSanitizer(enabled_rules=["PROFILE_URL", "SOCIAL_HANDLE"])

    clean = sanitizer.sanitize("Профили: github.com/ivan_dev и @petrov_dev.")

    assert "github.com/ivan_dev" not in clean
    assert "@petrov_dev" not in clean
    assert re.search(r"\[PROFILE_URL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[SOCIAL_HANDLE_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_online_identifier_rules_do_not_break_email_detection():
    sanitizer = TextSanitizer(enabled_rules=["ONLINE_ACCOUNT", "SOCIAL_HANDLE", "EMAIL"])

    clean = sanitizer.sanitize("Email ivan@example.com, handle @ivan_dev.")

    assert "ivan@example.com" not in clean
    assert "@ivan_dev" not in clean
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[SOCIAL_HANDLE_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_basic_profile_keeps_previous_default_rules():
    sanitizer = TextSanitizer(profile="basic")

    clean = sanitizer.sanitize("Email ivan@example.com, ИНН 7707083893, Telegram: @ivanov_dev.")

    assert "ivan@example.com" not in clean
    assert "7707083893" in clean
    assert "Telegram: @ivanov_dev" in clean
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_ru_152_profile_includes_inn_and_online_identifiers():
    sanitizer = TextSanitizer(profile="ru_152")

    clean = sanitizer.sanitize("ИНН 7707083893, никнейм ivan_dev на Habr.")

    assert "7707083893" not in clean
    assert "ivan_dev" not in clean
    assert "Habr" not in clean
    assert re.search(r"\[INN_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[ONLINE_ACCOUNT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_ru_152_strict_profile_includes_technical_identifiers():
    sanitizer = TextSanitizer(profile="ru_152_strict")

    clean = sanitizer.sanitize(
        "IP 192.168.1.10, session_id=abc123456, device_id: dev-12345678, user_id: 123456."
    )

    assert "192.168.1.10" not in clean
    assert "session_id=abc123456" not in clean
    assert "device_id: dev-12345678" not in clean
    assert "user_id: 123456" not in clean
    assert re.search(r"\[IP_ADDRESS_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[COOKIE_ID_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[DEVICE_ID_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[USER_ID_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_enabled_rules_override_profile():
    sanitizer = TextSanitizer(profile="ru_152_strict", enabled_rules=["EMAIL"])

    clean = sanitizer.sanitize("Email ivan@example.com, IP 192.168.1.10.")

    assert "ivan@example.com" not in clean
    assert "192.168.1.10" in clean
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_unknown_profile_fails_fast():
    with pytest.raises(ValueError, match="Unknown RAG profile"):
        TextSanitizer(profile="unknown")


def test_business_mode_is_opt_in():
    sanitizer = TextSanitizer()

    clean = sanitizer.sanitize('Реквизиты ООО "Ромашка": ИНН 7707083893, КПП 770701001.')

    assert clean == 'Реквизиты ООО "Ромашка": ИНН 7707083893, КПП 770701001.'


def test_company_business_mode_sanitizes_company_requisites():
    sanitizer = TextSanitizer(business_mode="company")
    text = (
        'Реквизиты ООО "Ромашка": ИНН 7707083893, КПП 770701001, '
        'ОГРН 1027700132195, БИК 044525225, р/с 40702810900000000001.'
    )

    clean = sanitizer.sanitize(text)

    assert 'ООО "Ромашка"' not in clean
    assert "7707083893" not in clean
    assert "770701001" not in clean
    assert "1027700132195" not in clean
    assert "044525225" not in clean
    assert "40702810900000000001" not in clean
    assert re.search(r"\[BUSINESS_REQUISITES_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_company_business_mode_sanitizes_legal_address_and_bank_details():
    sanitizer = TextSanitizer(business_mode="company")
    text = (
        'Юридический адрес: 125009, г. Москва, ул. Тверская, д. 1; '
        'к/с 30101810400000000225, ОКПО 12345678.'
    )

    clean = sanitizer.sanitize(text)

    assert "Тверская" not in clean
    assert "30101810400000000225" not in clean
    assert "12345678" not in clean
    assert re.search(r"\[LEGAL_ADDRESS_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[CORRESPONDENT_ACCOUNT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[OKPO_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_company_and_counterparties_mode_prioritizes_counterparty_block():
    sanitizer = TextSanitizer(business_mode="company_and_counterparties")

    clean = sanitizer.sanitize('Контрагент: АО "Вектор", ИНН 7708123456, КПП 770801001.')

    assert "Вектор" not in clean
    assert "7708123456" not in clean
    assert "770801001" not in clean
    assert re.search(r"\[COUNTERPARTY_REQUISITES_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert "[ORGANIZATION_NAME_" not in clean


def test_business_mode_combines_with_ru_152_profile():
    sanitizer = TextSanitizer(profile="ru_152", business_mode="company")

    clean = sanitizer.sanitize('Email: ivan@example.com. Компания ООО "Ромашка", ИНН 7707083893.')

    assert "ivan@example.com" not in clean
    assert "Ромашка" not in clean
    assert "7707083893" not in clean
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert re.search(r"\[(BUSINESS_REQUISITES|ORGANIZATION_NAME|COMPANY_INN)_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)


def test_business_mode_sanitizes_metadata():
    sanitizer = TextSanitizer(business_mode="company")

    clean = sanitizer.sanitize_metadata({"company": 'ООО "Ромашка"', "inn": "ИНН 7707083893"})

    assert "Ромашка" not in clean["company"]
    assert "7707083893" not in clean["inn"]
    assert re.search(r"\[ORGANIZATION_NAME_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean["company"])
    assert re.search(r"\[COMPANY_INN_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean["inn"])


def test_organization_profiles_distinguish_company_from_counterparty():
    company = OrganizationProfile(
        role="company",
        full_name='ООО "Ромашка"',
        short_names=("Ромашка",),
        inn="7707083893",
    )
    counterparty = OrganizationProfile(
        role="counterparty",
        full_name='АО "Вектор"',
        aliases=("Вектор",),
        inn="7708123456",
    )
    text = 'ООО "Ромашка", ИНН 7707083893; контрагент АО "Вектор", ИНН 7708123456.'

    company_only = TextSanitizer(
        business_mode="company",
        organization_profiles=[company, counterparty],
    ).sanitize(text)
    all_organizations = TextSanitizer(
        business_mode="company_and_counterparties",
        organization_profiles=[company, counterparty],
    ).sanitize(text)

    assert 'ООО "Ромашка"' not in company_only
    assert "7707083893" not in company_only
    assert 'АО "Вектор"' in company_only
    assert "7708123456" in company_only
    assert re.search(r"\[ORGANIZATION_COMPANY_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", company_only)
    assert 'ООО "Ромашка"' not in all_organizations
    assert 'АО "Вектор"' not in all_organizations
    assert re.search(r"\[ORGANIZATION_COUNTERPARTY_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", all_organizations)


def test_organization_profile_alias_is_sanitized_with_the_same_role():
    profile = OrganizationProfile(role="company", full_name='ООО "Ромашка"', aliases=("Ромашка",))
    sanitizer = TextSanitizer(business_mode="company", organization_profiles=[profile])

    clean = sanitizer.sanitize('ООО "Ромашка" (Ромашка)')

    tokens = re.findall(r"\[ORGANIZATION_COMPANY_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean)
    assert len(tokens) == 2
    assert tokens[0] != tokens[1]


def test_unknown_organization_policies_are_explicit():
    profile = OrganizationProfile(role="company", full_name='ООО "Ромашка"')
    text = 'ООО "Незнакомая", ИНН 7708123456.'

    report_sanitizer = TextSanitizer(
        business_mode="company",
        organization_profiles=[profile],
        unknown_organization_policy="report",
    )
    assert report_sanitizer.sanitize(text) == text
    assert report_sanitizer.scan(text)["unknown_organizations"] > 0

    masked = TextSanitizer(
        business_mode="company",
        organization_profiles=[profile],
        unknown_organization_policy="mask",
    ).sanitize(text)
    assert "Незнакомая" not in masked
    assert "7708123456" not in masked

    with pytest.raises(ValueError, match="Unknown organization detected"):
        TextSanitizer(
            business_mode="company",
            organization_profiles=[profile],
            unknown_organization_policy="reject",
        ).sanitize(text)


def test_organization_profile_validates_role_and_policy():
    with pytest.raises(ValueError, match="role"):
        OrganizationProfile(role="vendor", full_name="Example")
    with pytest.raises(ValueError, match="Unknown organization policy"):
        TextSanitizer(unknown_organization_policy="ignore")


def test_organization_profile_is_inactive_without_business_mode():
    profile = OrganizationProfile(role="company", full_name='ООО "Ромашка"', aliases=["Ромашка"])
    sanitizer = TextSanitizer(organization_profiles=[profile])

    assert sanitizer.sanitize('ООО "Ромашка"') == 'ООО "Ромашка"'
    assert "unknown_organizations" not in sanitizer.scan('ООО "Незнакомая"')


def test_unknown_business_mode_fails_fast():
    with pytest.raises(ValueError, match="Unknown business mode"):
        TextSanitizer(business_mode="unknown")


def test_unknown_builtin_rule_fails_fast():
    with pytest.raises(ValueError, match="Unknown built-in RAG rule"):
        TextSanitizer(enabled_rules=["EMAIL", "UNKNOWN"])


def test_deanonymize_defaults_to_masking_tokens():
    sanitizer = TextSanitizer()

    assert sanitizer.deanonymize("Hello [EMAIL_aaaaaaaa]") == "Hello [EMAIL]"


def test_legacy_eight_hex_token_remains_restorable():
    sanitizer = TextSanitizer()
    token = "[EMAIL_aaaaaaaa]"
    sanitizer.vault.save(token, "EMAIL", "ivan@example.com")

    assert sanitizer.deanonymize(token, policy="restore", token_scope={token: 1}) == "ivan@example.com"


def test_restoration_requires_scope_and_respects_token_occurrence_count():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])
    clean, token_scope = sanitizer.sanitize_with_scope("Email: ivan@example.com")
    token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean).group()

    with pytest.raises(ValueError, match="token_scope is required"):
        sanitizer.deanonymize(clean, policy="restore")

    restored = sanitizer.deanonymize(f"{token} {token}", policy="restore", token_scope=token_scope)
    assert restored == f"ivan@example.com {token}"


def test_restoration_scope_cannot_disclose_tokens_from_another_input():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])
    first_clean, first_scope = sanitizer.sanitize_with_scope("Email: ivan@example.com")
    second_clean, _ = sanitizer.sanitize_with_scope("Email: maria@example.com")

    restored = sanitizer.deanonymize(
        f"{first_clean} {second_clean}",
        policy="restore",
        token_scope=first_scope,
    )

    assert "ivan@example.com" in restored
    assert "maria@example.com" not in restored
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", restored)


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
    assert re.search(r"\[PROFILE_URL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean["source_url"])
    assert re.search(r"\[ONLINE_ACCOUNT_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean["author"])
    assert re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean["tags"][1])
    assert re.search(r"\[INN_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean["nested"]["inn"])


def test_sanitize_metadata_reuses_tokens_with_text_sanitize():
    sanitizer = TextSanitizer(profile="ru_152")

    clean_text = sanitizer.sanitize("Email: ivan@example.com")
    clean_metadata = sanitizer.sanitize_metadata({"email": "ivan@example.com"})

    text_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean_text).group()
    metadata_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean_metadata["email"]).group()
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


def test_deanonymize_metadata_restores_nested_tokens():
    sanitizer = TextSanitizer(profile="ru_152")
    clean_metadata = sanitizer.sanitize_metadata(
        {
            "author": "Telegram: @ivanov_dev",
            "tags": ["ivan@example.com"],
            "nested": {"inn": "ИНН 7707083893"},
        }
    )

    restored_metadata = sanitizer.deanonymize_metadata(
        clean_metadata,
        policy="restore",
        token_scope=_token_scope(clean_metadata),
    )

    assert restored_metadata["author"] == "Telegram: @ivanov_dev"
    assert restored_metadata["tags"] == ["ivan@example.com"]
    assert restored_metadata["nested"]["inn"] == "ИНН 7707083893"


def test_deanonymize_metadata_honors_policy():
    sanitizer = TextSanitizer(profile="ru_152")
    clean_metadata = sanitizer.sanitize_metadata({"email": "ivan@example.com", "inn": "ИНН 7707083893"})

    masked = sanitizer.deanonymize_metadata(clean_metadata, policy="mask")
    restored_allowed = sanitizer.deanonymize_metadata(
        clean_metadata,
        policy="restore_allowed_only",
        allowed_entity_types=["EMAIL"],
        token_scope=_token_scope(clean_metadata),
    )

    assert masked["email"] == "[EMAIL]"
    assert masked["inn"] == "[INN]"
    assert restored_allowed["email"] == "ivan@example.com"
    assert "7707083893" not in restored_allowed["inn"]
    assert re.search(r"\[INN_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", restored_allowed["inn"])


def test_deanonymize_metadata_requires_dict():
    sanitizer = TextSanitizer()

    with pytest.raises(ValueError, match="metadata must be a dictionary"):
        sanitizer.deanonymize_metadata(["[EMAIL_aaaaaaaa]"])


def test_sanitize_document_sanitizes_text_and_metadata_with_same_vault():
    sanitizer = TextSanitizer(profile="ru_152")

    clean_text, clean_metadata = sanitizer.sanitize_document(
        "Email: ivan@example.com",
        {"contact": "ivan@example.com", "source_url": "github.com/ivan_dev"},
    )

    text_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean_text).group()
    metadata_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean_metadata["contact"]).group()
    assert text_token == metadata_token
    assert "github.com/ivan_dev" not in clean_metadata["source_url"]
    assert re.search(r"\[PROFILE_URL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", clean_metadata["source_url"])


def test_sanitize_metadata_with_scope_excludes_existing_tokens():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])
    original_token = "[EMAIL_aaaaaaaa]"

    clean_metadata, scope = sanitizer.sanitize_metadata_with_scope(
        {"existing": original_token, "email": "ivan@example.com"}
    )

    assert clean_metadata["existing"] == original_token
    assert original_token not in scope
    assert sum(scope.values()) == 1


def test_sanitize_document_with_scope_combines_text_and_metadata_occurrences():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])
    result = sanitizer.sanitize_document_with_scope(
        "Email: ivan@example.com",
        {"contact": "ivan@example.com", "existing": "[EMAIL_aaaaaaaa]"},
    )

    token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", result.text).group()
    assert result.metadata["contact"] == token
    assert result.metadata["existing"] == "[EMAIL_aaaaaaaa]"
    assert result.token_scope == {token: 2}
    restored_text, restored_metadata = sanitizer.deanonymize_document(
        result.text,
        result.metadata,
        policy="restore",
        token_scope=result.token_scope,
    )
    assert restored_text == "Email: ivan@example.com"
    assert restored_metadata["contact"] == "ivan@example.com"
    assert restored_metadata["existing"] == "[EMAIL_aaaaaaaa]"


@pytest.mark.parametrize(
    ("rule", "text", "entity_type"),
    [
        ("PERSON", "Контакт: Анна-Мария Иванова", "PERSON"),
        ("PERSON", "Ответственный: И.И. Петров", "PERSON"),
        ("PASSPORT", "Паспорт 4500 123456", "PASSPORT"),
        ("PHONE", "Телефон +7 (900) 123-45-67", "PHONE"),
        ("SNILS", "СНИЛС 123-456-789 00", "SNILS"),
        ("CARD", "Карта 4222222222222", "CARD"),
        ("CARD", "Карта 4222-2222-2222-2222-222", "CARD"),
        ("INN", "ИНН 7707 083 893", "INN"),
        ("USERNAME", "Логин: Ivan.Dev", "USERNAME"),
        ("PROFILE_URL", "https://github.com/Ivan.Dev", "PROFILE_URL"),
        ("SOCIAL_HANDLE", "@Ivan_Dev", "SOCIAL_HANDLE"),
    ],
)
def test_rag_detection_corpus_positive_examples(rule, text, entity_type):
    clean = TextSanitizer(enabled_rules=[rule]).sanitize(text)

    assert text not in clean
    assert re.search(rf"\[{entity_type}_(?:[a-f0-9]{{8}}|[a-f0-9]{{32}})\]", clean)


@pytest.mark.parametrize(
    ("rule", "text"),
    [
        ("PASSPORT", "ИНН 7707083893"),
        ("CARD", "Код 123456789012"),
        ("CARD", "Код 12345678901234567890"),
        ("PHONE", "Версия 899912345678"),
        ("SOCIAL_HANDLE", "Email person@example.com"),
        ("USERNAME", "Свободный текст без метки ivan_dev"),
    ],
)
def test_rag_detection_corpus_negative_examples(rule, text):
    assert TextSanitizer(enabled_rules=[rule]).sanitize(text) == text


def test_deanonymize_document_restores_text_and_metadata():
    sanitizer = TextSanitizer(profile="ru_152")
    original_text = "Email: ivan@example.com"
    original_metadata = {"author": "Telegram: @ivanov_dev"}
    clean_text, clean_metadata = sanitizer.sanitize_document(original_text, original_metadata)

    restored_text, restored_metadata = sanitizer.deanonymize_document(
        clean_text,
        clean_metadata,
        policy="restore",
        token_scope=_token_scope(clean_text, clean_metadata),
    )

    assert restored_text == original_text
    assert restored_metadata == original_metadata


def test_deanonymize_document_honors_policy():
    sanitizer = TextSanitizer(profile="ru_152")
    clean_text, clean_metadata = sanitizer.sanitize_document(
        "Email: ivan@example.com",
        {"author": "Telegram: @ivanov_dev"},
    )

    masked_text, masked_metadata = sanitizer.deanonymize_document(clean_text, clean_metadata, policy="mask")

    assert masked_text == "Email: [EMAIL]"
    assert masked_metadata["author"] == "[ONLINE_ACCOUNT]"


def test_scan_reports_entity_counts_without_values():
    sanitizer = TextSanitizer(profile="ru_152")

    report = sanitizer.scan("Email ivan@example.com, ИНН 7707083893, Telegram: @ivanov_dev.")

    assert report["entities"] == {"ONLINE_ACCOUNT": 1, "EMAIL": 1, "INN": 1}
    assert report["total"] == 3
    assert report["coverage"] == "heuristic"
    assert "ONLINE_ACCOUNT" in report["active_rules"]
    assert "ivan@example.com" not in str(report)
    assert "7707083893" not in str(report)


def test_scan_does_not_write_to_vault():
    vault = MemoryVault()
    sanitizer = TextSanitizer(vault=vault, enabled_rules=["EMAIL"])

    sanitizer.scan("Email ivan@example.com")

    assert vault.get_token("EMAIL", "ivan@example.com") is None


def test_sanitize_with_report_includes_residual_scan():
    sanitizer = TextSanitizer(enabled_rules=["EMAIL"])

    clean, report = sanitizer.sanitize_with_report("Email ivan@example.com, phone +7 900 123-45-67.")

    assert "ivan@example.com" not in clean
    assert "+7 900 123-45-67" in clean
    assert report["entities"] == {"EMAIL": 1}
    assert report["total"] == 1
    assert report["residual_entities"] == {}
    assert report["residual_total"] == 0
    assert report["coverage"] == "heuristic"
    assert report["residual_coverage"] == "heuristic"


def test_file_vault_persists_mappings(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    restored_vault = FileVault(str(vault_path))

    assert restored_vault.get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"
    assert restored_vault.get_token("EMAIL", "ivan@example.com") == "[EMAIL_aaaaaaaa]"


def test_memory_vault_lifecycle_methods():
    vault = MemoryVault()
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    assert vault.delete_value("EMAIL", "ivan@example.com") is True
    assert vault.get_value("[EMAIL_aaaaaaaa]") is None
    assert vault.delete_value("EMAIL", "ivan@example.com") is False

    vault.save("[PHONE_bbbbbbbb]", "PHONE", "+7 900 123-45-67")
    assert vault.delete_token("[PHONE_bbbbbbbb]") is True
    assert vault.get_token("PHONE", "+7 900 123-45-67") is None

    vault.save("[EMAIL_cccccccc]", "EMAIL", "anna@example.com")
    vault.clear()
    assert vault.get_token("EMAIL", "anna@example.com") is None


def test_memory_vault_ttl_expiration():
    vault = MemoryVault(default_ttl_seconds=0)
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    assert vault.get_value("[EMAIL_aaaaaaaa]") is None
    assert vault.get_token("EMAIL", "ivan@example.com") is None


def test_file_vault_lifecycle_methods_persist(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    vault.save("[PHONE_bbbbbbbb]", "PHONE", "+7 900 123-45-67")

    assert vault.delete_value("EMAIL", "ivan@example.com") is True
    assert vault.delete_token("[PHONE_bbbbbbbb]") is True

    restored_vault = FileVault(str(vault_path))
    assert restored_vault.get_token("EMAIL", "ivan@example.com") is None
    assert restored_vault.get_value("[PHONE_bbbbbbbb]") is None

    restored_vault.save("[EMAIL_cccccccc]", "EMAIL", "anna@example.com")
    restored_vault.clear()
    assert FileVault(str(vault_path)).stats()["total"] == 0


def test_file_vault_ttl_expiration_and_purge(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path), default_ttl_seconds=0)
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    assert FileVault(str(vault_path)).purge_expired() == 1
    restored_vault = FileVault(str(vault_path))
    assert restored_vault.get_value("[EMAIL_aaaaaaaa]") is None
    assert restored_vault.get_token("EMAIL", "ivan@example.com") is None


def test_file_vault_future_ttl_remains_active(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path), default_ttl_seconds=3600)
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    restored_vault = FileVault(str(vault_path))

    assert restored_vault.get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"
    assert restored_vault.purge_expired() == 0
    assert restored_vault.stats()["has_expiration"] is True


def test_file_vault_rejects_legacy_format(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault_path.write_text(
        json.dumps(
            {
                "entries": {
                    "[EMAIL_aaaaaaaa]": {
                        "value": "ivan@example.com",
                        "created_at": "2026-01-01T00:00:00",
                        "last_used_at": "2026-01-01T00:00:00",
                        "expires_at": "2099-01-01T00:00:00",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="migrate legacy vault"):
        FileVault(str(vault_path))


def test_file_vault_reads_do_not_rewrite_file_and_uses_private_permissions(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    before = vault_path.read_text(encoding="utf-8")

    assert vault.get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"
    assert vault.get_token("EMAIL", "ivan@example.com") == "[EMAIL_aaaaaaaa]"
    assert vault_path.read_text(encoding="utf-8") == before
    assert stat.S_IMODE(vault_path.stat().st_mode) & 0o077 == 0


def test_file_vault_writes_entries_with_timestamps(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    data = json.loads(vault_path.read_text(encoding="utf-8"))

    assert data["format"] == "lightanon.file-vault"
    assert data["version"] == 2
    assert data["entries"]["[EMAIL_aaaaaaaa]"]["entity_type"] == "EMAIL"
    assert data["entries"]["[EMAIL_aaaaaaaa]"]["namespace"] == "default"
    assert data["entries"]["[EMAIL_aaaaaaaa]"]["value"] == "ivan@example.com"
    assert data["entries"]["[EMAIL_aaaaaaaa]"]["created_at"]
    assert data["entries"]["[EMAIL_aaaaaaaa]"]["last_used_at"]
    assert FileVault(str(vault_path)).stats()["has_timestamps"] is True


def test_file_vault_encrypts_values_with_fernet_key(tmp_path):
    vault_path = tmp_path / "vault.json"
    key = Fernet.generate_key()
    vault = FileVault(str(vault_path), encryption_key=key)
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")

    assert "ivan@example.com" not in vault_path.read_text(encoding="utf-8")
    assert FileVault(str(vault_path), encryption_key=key).get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"
    with pytest.raises(ValueError, match="Vault is encrypted"):
        FileVault(str(vault_path))
    with pytest.raises(ValueError, match="Unable to decrypt"):
        FileVault(str(vault_path), encryption_key=Fernet.generate_key())


def test_file_vault_reuses_token_across_sanitizer_instances(tmp_path):
    vault_path = tmp_path / "vault.json"

    first = TextSanitizer(vault=FileVault(str(vault_path))).sanitize("Email: ivan@example.com")
    second = TextSanitizer(vault=FileVault(str(vault_path))).sanitize("Repeat: ivan@example.com")

    first_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", first).group()
    second_token = re.search(r"\[EMAIL_(?:[a-f0-9]{8}|[a-f0-9]{32})\]", second).group()
    assert first_token == second_token


def test_file_vault_rejects_legacy_reverse_mapping(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault_path.write_text(
        json.dumps({"token_to_value": {"[EMAIL_aaaaaaaa]": "ivan@example.com"}}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="migrate legacy vault"):
        FileVault(str(vault_path))


def test_file_vault_rejects_invalid_json(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault_path.write_text("{bad json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid vault JSON"):
        FileVault(str(vault_path))


def test_file_vault_stats_do_not_include_values(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    vault.save("[CONTRACT_ID_bbbbbbbb]", "CONTRACT_ID", "12-3456/78")

    stats = vault.stats()

    assert stats["total"] == 2
    assert stats["by_type"] == {"EMAIL": 1, "CONTRACT_ID": 1}
    assert "ivan@example.com" not in str(stats)


def test_typed_values_do_not_share_tokens_between_entity_types():
    vault = MemoryVault()
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "same-value")
    vault.save("[PUBLIC_ID_bbbbbbbb]", "PUBLIC_ID", "same-value")

    assert vault.get_token("EMAIL", "same-value") == "[EMAIL_aaaaaaaa]"
    assert vault.get_token("PUBLIC_ID", "same-value") == "[PUBLIC_ID_bbbbbbbb]"


def test_mapping_conflicts_do_not_mutate_file_vault(tmp_path):
    vault_path = tmp_path / "vault.json"
    vault = FileVault(str(vault_path))
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    before = vault_path.read_bytes()

    with pytest.raises(MappingConflict, match="Token is already bound"):
        vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "anna@example.com")
    with pytest.raises(MappingConflict, match="Typed value is already bound"):
        vault.save("[EMAIL_bbbbbbbb]", "EMAIL", "ivan@example.com")

    assert vault_path.read_bytes() == before
    assert vault.get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"
    assert vault.get_value("[EMAIL_bbbbbbbb]") is None


def test_file_vault_reloads_state_for_multiple_instances(tmp_path):
    vault_path = tmp_path / "vault.json"
    first = FileVault(str(vault_path))
    second = FileVault(str(vault_path))

    first.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    second.save("[PHONE_bbbbbbbb]", "PHONE", "+7 900 123-45-67")

    assert first.get_value("[PHONE_bbbbbbbb]") == "+7 900 123-45-67"
    assert second.get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"


def test_file_vault_rejects_plaintext_substitution_when_key_is_supplied(tmp_path):
    vault_path = tmp_path / "vault.json"
    plain_path = tmp_path / "plain.json"
    key = Fernet.generate_key()
    FileVault(str(vault_path), encryption_key=key).save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    FileVault(str(plain_path)).save("[EMAIL_bbbbbbbb]", "EMAIL", "attacker@example.com")
    vault_path.write_bytes(plain_path.read_bytes())

    with pytest.raises(ValueError, match="requires an encrypted v2 vault"):
        FileVault(str(vault_path), encryption_key=key)


def test_file_vault_rejects_modified_encrypted_ciphertext(tmp_path):
    vault_path = tmp_path / "vault.json"
    key = Fernet.generate_key()
    vault = FileVault(str(vault_path), encryption_key=key)
    vault.save("[EMAIL_aaaaaaaa]", "EMAIL", "ivan@example.com")
    envelope = json.loads(vault_path.read_text(encoding="utf-8"))
    envelope["ciphertext"] = "not-a-fernet-token"
    vault_path.write_text(json.dumps(envelope), encoding="utf-8")

    with pytest.raises(ValueError, match="Unable to decrypt"):
        FileVault(str(vault_path), encryption_key=key)


def test_migrate_legacy_file_vault_preserves_source_and_encrypts_destination(tmp_path):
    source = tmp_path / "legacy.json"
    destination = tmp_path / "vault.v2"
    legacy = {"token_to_value": {"[EMAIL_aaaaaaaa]": "ivan@example.com"}}
    source.write_text(json.dumps(legacy), encoding="utf-8")
    key = Fernet.generate_key()

    assert migrate_legacy_file_vault(str(source), str(destination), key) == 1
    assert json.loads(source.read_text(encoding="utf-8")) == legacy
    assert "ivan@example.com" not in destination.read_text(encoding="utf-8")
    assert FileVault(str(destination), encryption_key=key).get_token("EMAIL", "ivan@example.com") == "[EMAIL_aaaaaaaa]"


def test_migrate_legacy_file_vault_rejects_existing_destination(tmp_path):
    source = tmp_path / "legacy.json"
    destination = tmp_path / "vault.v2"
    source.write_text(json.dumps({"token_to_value": {}}), encoding="utf-8")
    destination.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="destination already exists"):
        migrate_legacy_file_vault(str(source), str(destination), Fernet.generate_key())
    assert destination.read_text(encoding="utf-8") == "keep"
