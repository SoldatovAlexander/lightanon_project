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
