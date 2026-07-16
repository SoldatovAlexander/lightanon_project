import json

from lightanon import cli


def test_rag_cli_sanitize_and_restore(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    restored_path = tmp_path / "restored.txt"
    vault_path = tmp_path / "vault.json"

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
        ]
    )

    assert restored_path.read_text(encoding="utf-8") == original


def test_rag_cli_restore_mask_policy(tmp_path):
    input_path = tmp_path / "input.txt"
    sanitized_path = tmp_path / "sanitized.txt"
    restored_path = tmp_path / "restored.txt"
    vault_path = tmp_path / "vault.json"
    input_path.write_text("Email: ivan@example.com", encoding="utf-8")

    cli.main(["rag", "sanitize", str(input_path), str(sanitized_path), "--vault", str(vault_path)])
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
    token = next(iter(data["token_to_value"]))

    cli.main(["rag", "delete-token", str(vault_path), token])
    assert "Deleted: yes" in capsys.readouterr().out
    assert json.loads(vault_path.read_text(encoding="utf-8"))["token_to_value"] == {}

    cli.main(["rag", "sanitize", str(input_path), str(sanitized_path), "--vault", str(vault_path)])
    capsys.readouterr()
    cli.main(["rag", "clear-vault", str(vault_path)])
    assert "Vault cleared" in capsys.readouterr().out
    assert json.loads(vault_path.read_text(encoding="utf-8"))["token_to_value"] == {}


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
    assert json.loads(vault_path.read_text(encoding="utf-8"))["token_to_value"] == {}


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
