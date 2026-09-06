import json

import pandas as pd
import pytest
from cryptography.fernet import Fernet

from lightanon import cli
from lightanon.rag import FileVault


def test_rag_cli_sanitize_and_restore(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    restored_path = tmp_path / "restored.txt"
    vault_path = tmp_path / "vault.json"
    scope_path = tmp_path / "scope.json"

    original = "Напишите Иванов Иван на ivan@example.com или +7 900 123-45-67."
    input_path.write_text(original, encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--scope-file",
            str(scope_path),
        ]
    )

    sanitized = sanitized_path.read_text(encoding="utf-8")
    assert "ivan@example.com" not in sanitized
    assert "[EMAIL_" in sanitized
    assert vault_path.exists()

    cli.main(
        [
            "rag",
            "restore",
            str(sanitized_path),
            str(restored_path),
            "--vault",
            str(vault_path),
            "--policy",
            "restore",
            "--scope-file",
            str(scope_path),
        ]
    )

    assert restored_path.read_text(encoding="utf-8") == original
    assert json.loads(scope_path.read_text(encoding="utf-8"))["version"] == 1


def test_rag_cli_restore_defaults_to_mask_and_requires_scope_for_restore(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    restored_path = tmp_path / "restored.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(["rag", "sanitize", str(input_path), str(sanitized_path), "--vault", str(vault_path)])
    cli.main(["rag", "restore", str(sanitized_path), str(restored_path), "--vault", str(vault_path)])
    assert restored_path.read_text(encoding="utf-8") == "Email: [EMAIL]"

    with pytest.raises(ValueError, match="token_scope is required"):
        cli.main(
            [
                "rag",
                "restore",
                str(sanitized_path),
                str(restored_path),
                "--vault",
                str(vault_path),
                "--policy",
                "restore",
            ]
        )


def test_rag_cli_uses_encryption_key_from_environment(tmp_path, monkeypatch):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    monkeypatch.setenv("LIGHTANON_TEST_VAULT_KEY", Fernet.generate_key().decode("utf-8"))
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--vault-key-env",
            "LIGHTANON_TEST_VAULT_KEY",
        ]
    )

    assert "ivan@example.com" not in vault_path.read_text(encoding="utf-8")


def test_cli_exits_nonzero_and_writes_fail_closed_output(tmp_path, capsys):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    schema_path = tmp_path / "schema.yaml"
    input_path.write_text("salary,name\n100.0,Ivan\n-50.0,Petr\n3000.0,Anna\n", encoding="utf-8")
    schema_path.write_text(
        "salary:\n"
        "  method: GaussianNoise\n"
        "  params:\n"
        "    std: 0.1\n",
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc:
        cli.main([str(input_path), str(output_path), "-c", str(schema_path)])

    assert exc.value.code == 1
    clean_df = pd.read_csv(output_path)
    assert clean_df["salary"].isna().all()
    assert clean_df["name"].tolist() == ["Ivan", "Petr", "Anna"]

    output = capsys.readouterr().out
    assert "[FAIL] Column 'salary': rule_execution_failed (ValueError)" in output


@pytest.mark.parametrize(
    "schema_text",
    [
        "email:\n  method: Hahs\n",
        "email:\n  params:\n    salt: secret\n",
        "email: Hash\n",
        "email:\n  method: Hash\n  params: secret\n",
    ],
)
def test_cli_rejects_invalid_schema_before_writing_output(tmp_path, schema_text):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    schema_path = tmp_path / "schema.yaml"
    input_path.write_text("email\nreview@example.com\n", encoding="utf-8")
    output_path.write_text("existing-output\n", encoding="utf-8")
    schema_path.write_text(schema_text, encoding="utf-8")

    with pytest.raises(ValueError):
        cli.main([str(input_path), str(output_path), "-c", str(schema_path)])

    assert output_path.read_text(encoding="utf-8") == "existing-output\n"


def test_cli_rejects_empty_schema_before_writing_output(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "output.csv"
    schema_path = tmp_path / "schema.yaml"
    input_path.write_text("email\nreview@example.com\n", encoding="utf-8")
    output_path.write_text("existing-output\n", encoding="utf-8")
    schema_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Schema config"):
        cli.main([str(input_path), str(output_path), "-c", str(schema_path)])

    assert output_path.read_text(encoding="utf-8") == "existing-output\n"


def test_rag_cli_rejects_overlapping_output_vault_and_scope_paths(tmp_path):
    input_path = tmp_path / "input.txt"
    output_path = tmp_path / "output.txt"
    vault_path = tmp_path / "vault.json"
    scope_path = tmp_path / "scope.json"
    input_path.write_text("Email: review@example.com", encoding="utf-8")
    output_path.write_text("existing-output", encoding="utf-8")
    vault_path.write_text("existing-vault", encoding="utf-8")
    scope_path.write_text("existing-scope", encoding="utf-8")

    for extra_args in (
        ["--vault", str(output_path)],
        ["--vault", str(vault_path), "--scope-file", str(vault_path)],
        ["--vault", str(vault_path), "--scope-file", str(output_path)],
    ):
        with pytest.raises(ValueError, match="must refer to different files"):
            cli.main(["rag", "sanitize", str(input_path), str(output_path), *extra_args])

    assert output_path.read_text(encoding="utf-8") == "existing-output"
    assert vault_path.read_text(encoding="utf-8") == "existing-vault"
    assert scope_path.read_text(encoding="utf-8") == "existing-scope"


def test_cli_rejects_output_path_that_is_config_file(tmp_path):
    input_path = tmp_path / "input.csv"
    config_path = tmp_path / "schema.yaml"
    input_path.write_text("email\nreview@example.com\n", encoding="utf-8")
    config_path.write_text("email:\n  method: Hash\n  params:\n    salt: secret\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must refer to different files"):
        cli.main([str(input_path), str(config_path), "-c", str(config_path)])

    assert "method: Hash" in config_path.read_text(encoding="utf-8")


def test_rag_cli_restore_mask_policy(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    restored_path = tmp_path / "restored.txt"
    vault_path = tmp_path / "vault.json"
    scope_path = tmp_path / "scope.json"
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--scope-file",
            str(scope_path),
        ]
    )
    cli.main(
        [
            "rag",
            "restore",
            str(sanitized_path),
            str(restored_path),
            "--vault",
            str(vault_path),
            "--policy",
            "mask",
        ]
    )

    assert restored_path.read_text(encoding="utf-8") == "Email: [EMAIL]"


def test_rag_cli_restore_allowed_types_policy(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    restored_path = tmp_path / "restored.txt"
    vault_path = tmp_path / "vault.json"
    scope_path = tmp_path / "scope.json"
    input_path.write_text("Email: ivan@example.com. ИНН 7707083893.", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--profile",
            "ru_152",
            "--scope-file",
            str(scope_path),
        ]
    )
    cli.main(
        [
            "rag",
            "restore",
            str(sanitized_path),
            str(restored_path),
            "--vault",
            str(vault_path),
            "--policy",
            "restore_allowed_only",
            "--allowed-types",
            "EMAIL",
            "--scope-file",
            str(scope_path),
        ]
    )

    restored = restored_path.read_text(encoding="utf-8")
    assert "ivan@example.com" in restored
    assert "7707083893" not in restored
    assert "[INN_" in restored


def test_rag_cli_inspect_vault_hides_values(tmp_path, capsys):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
        ]
    )
    capsys.readouterr()

    cli.main(["rag", "inspect-vault", str(vault_path)])

    output = capsys.readouterr().out
    assert "Total mappings: 1" in output
    assert "EMAIL: 1" in output
    assert "ivan@example.com" not in output


def test_rag_cli_vault_lifecycle_commands(tmp_path, capsys):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(["rag", "sanitize", str(input_path), str(sanitized_path), "--vault", str(vault_path)])
    capsys.readouterr()

    data = json.loads(vault_path.read_text(encoding="utf-8"))
    token = next(iter(data["entries"]))

    cli.main(["rag", "delete-token", str(vault_path), token])
    assert "Deleted: yes" in capsys.readouterr().out
    assert json.loads(vault_path.read_text(encoding="utf-8"))["entries"] == {}

    cli.main(["rag", "sanitize", str(input_path), str(sanitized_path), "--vault", str(vault_path)])
    capsys.readouterr()
    cli.main(["rag", "clear-vault", str(vault_path)])
    assert "Vault cleared" in capsys.readouterr().out
    assert json.loads(vault_path.read_text(encoding="utf-8"))["entries"] == {}


def test_rag_cli_ttl_and_purge_expired(tmp_path, capsys):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--ttl-seconds",
            "0",
        ]
    )
    capsys.readouterr()

    cli.main(["rag", "purge-expired", str(vault_path)])

    assert "Expired mappings deleted: 1" in capsys.readouterr().out
    assert json.loads(vault_path.read_text(encoding="utf-8"))["entries"] == {}


def test_rag_cli_migrates_legacy_vault_to_encrypted_v2(tmp_path, capsys, monkeypatch):
    source_path = tmp_path / "legacy.json"
    destination_path = tmp_path / "vault.v2"
    key = Fernet.generate_key().decode("utf-8")
    source_path.write_text(
        json.dumps({"token_to_value": {"[EMAIL_aaaaaaaa]": "ivan@example.com"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("LIGHTANON_VAULT_KEY", key)

    cli.main(
        [
            "rag",
            "migrate-vault",
            str(source_path),
            str(destination_path),
            "--vault-key-env",
            "LIGHTANON_VAULT_KEY",
        ]
    )

    assert "Migrated mappings: 1" in capsys.readouterr().out
    assert FileVault(str(destination_path), encryption_key=key).get_value("[EMAIL_aaaaaaaa]") == "ivan@example.com"


def test_rag_cli_sanitize_with_selected_rules(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text(
        "Email: ivan@example.com. Phone: +7 900 123-45-67. ИНН 7707083893.",
        encoding="utf-8",
    )

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--rules",
            "EMAIL,INN",
        ]
    )

    sanitized = sanitized_path.read_text(encoding="utf-8")
    assert "ivan@example.com" not in sanitized
    assert "7707083893" not in sanitized
    assert "+7 900 123-45-67" in sanitized
    assert "[EMAIL_" in sanitized
    assert "[INN_" in sanitized


def test_rag_cli_sanitize_with_ru_152_profile(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("ИНН 7707083893, Telegram: @ivanov_dev.", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--profile",
            "ru_152",
        ]
    )

    sanitized = sanitized_path.read_text(encoding="utf-8")
    assert "7707083893" not in sanitized
    assert "Telegram" not in sanitized
    assert "@ivanov_dev" not in sanitized
    assert "[INN_" in sanitized
    assert "[ONLINE_ACCOUNT_" in sanitized


def test_rag_cli_sanitize_with_business_mode(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text('Компания ООО "Ромашка", ИНН 7707083893.', encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--business-mode",
            "company",
        ]
    )

    sanitized = sanitized_path.read_text(encoding="utf-8")
    assert "Ромашка" not in sanitized
    assert "7707083893" not in sanitized
    assert "[ORGANIZATION_NAME_" in sanitized or "[BUSINESS_REQUISITES_" in sanitized


def test_rag_cli_scan_with_business_mode(tmp_path, capsys):
    input_path = tmp_path / "input.txt"
    input_path.write_text('Контрагент: АО "Вектор", ИНН 7708123456, КПП 770801001.', encoding="utf-8")

    cli.main(["rag", "scan", str(input_path), "--business-mode", "company_and_counterparties"])

    report = json.loads(capsys.readouterr().out)
    assert report["entities"] == {"COUNTERPARTY_REQUISITES": 1}
    assert report["total"] == 1


def test_rag_cli_rules_override_profile(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("Email: ivan@example.com. ИНН 7707083893.", encoding="utf-8")

    cli.main(
        [
            "rag",
            "sanitize",
            str(input_path),
            str(sanitized_path),
            "--vault",
            str(vault_path),
            "--profile",
            "ru_152",
            "--rules",
            "EMAIL",
        ]
    )

    sanitized = sanitized_path.read_text(encoding="utf-8")
    assert "ivan@example.com" not in sanitized
    assert "7707083893" in sanitized
    assert "[EMAIL_" in sanitized
    assert "[INN_" not in sanitized


def test_rag_cli_scan_prints_report_without_values(tmp_path, capsys):
    input_path = tmp_path / "input.txt"
    input_path.write_text("Email: ivan@example.com. ИНН 7707083893.", encoding="utf-8")

    cli.main(["rag", "scan", str(input_path), "--profile", "ru_152"])

    output = capsys.readouterr().out
    report = json.loads(output)
    assert report["entities"] == {"EMAIL": 1, "INN": 1}
    assert report["total"] == 2
    assert "ivan@example.com" not in output
    assert "7707083893" not in output
