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
