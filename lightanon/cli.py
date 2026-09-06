import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml
import pandas as pd
import polars as pl
import lightanon as la

RULE_REGISTRY = {
    "Hash": la.rules.Hash,
    "Mask": la.rules.Mask,
    "GaussianNoise": la.rules.GaussianNoise,
    "Generalize": la.rules.Generalize,
    "MultiplicativeNoise": la.financial.MultiplicativeNoise,
    "TopCoding": la.financial.TopCoding,
    "CreditCardMask": la.financial.CreditCardMask,
    "TopCodingFixed": la.financial.TopCodingFixed,
}


def load_schema(config_path: str):
    """Parse a complete, valid YAML schema into rule instances."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict) or not config:
        raise ValueError("Schema config must be a mapping: {column: {method, params}}")

    schema = {}
    for col, rule_def in config.items():
        if not isinstance(col, str) or not col:
            raise ValueError("Schema column names must be non-empty strings")
        if not isinstance(rule_def, dict):
            raise ValueError(f"Schema for column '{col}' must be a mapping")

        method_name = rule_def.get("method")
        params = rule_def.get("params", {})
        if not isinstance(method_name, str) or method_name not in RULE_REGISTRY:
            raise ValueError(f"Unknown or missing rule for column '{col}'")
        if not isinstance(params, dict):
            raise ValueError(f"Parameters for column '{col}' must be a mapping")

        try:
            schema[col] = RULE_REGISTRY[method_name](**params)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid parameters for rule '{method_name}' in column '{col}'") from exc

    return schema


def _read_dataframe(path: str, engine_name: str):
    ext = Path(path).suffix.lower()
    if engine_name == "polars":
        if ext == ".csv":
            return pl.read_csv(path)
        if ext == ".parquet":
            return pl.read_parquet(path)
    else:
        if ext == ".csv":
            return pd.read_csv(path)
        if ext == ".parquet":
            return pd.read_parquet(path)
    raise ValueError(f"Unsupported input format '{ext}'. Use .csv or .parquet")


def _write_dataframe_to_path(df, path: str, engine_name: str):
    ext = Path(path).suffix.lower()
    if engine_name == "polars":
        if ext == ".csv":
            df.write_csv(path)
            return
        if ext == ".parquet":
            df.write_parquet(path)
            return
    else:
        if ext == ".csv":
            df.to_csv(path, index=False)
            return
        if ext == ".parquet":
            df.to_parquet(path, index=False)
            return
    raise ValueError(f"Unsupported output format '{ext}'. Use .csv or .parquet")


def _atomic_write(path: str, writer) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_name = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False,
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=output_path.suffix,
        ) as temp_file:
            temp_name = temp_file.name
        writer(temp_name)
        os.replace(temp_name, output_path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_dataframe(df, path: str, engine_name: str):
    _atomic_write(path, lambda temp_path: _write_dataframe_to_path(df, temp_path, engine_name))


def _read_text(path: str, encoding: str) -> str:
    return Path(path).read_text(encoding=encoding)


def _write_text(path: str, text: str, encoding: str) -> None:
    _atomic_write(path, lambda temp_path: Path(temp_path).write_text(text, encoding=encoding))


def _read_token_scope(path: str) -> dict:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read token scope '{path}': {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("tokens"), dict):
        raise ValueError("Token scope must be a version 1 JSON object with a tokens mapping")
    return payload["tokens"]


def _write_token_scope(path: str, tokens: dict) -> None:
    _write_text(
        path,
        json.dumps({"version": 1, "tokens": tokens}, ensure_ascii=False, indent=2) + "\n",
        "utf-8",
    )


def _parse_rule_names(value: str):
    return [item.strip() for item in value.split(",") if item.strip()]


def _paths_refer_to_same_file(first: str, second: str) -> bool:
    first_path = Path(first)
    second_path = Path(second)
    if first_path.resolve(strict=False) == second_path.resolve(strict=False):
        return True
    if first_path.exists() and second_path.exists():
        return os.path.samefile(first_path, second_path)
    return False


def _validate_distinct_paths(**paths: str) -> None:
    named_paths = [(name, path) for name, path in paths.items() if path is not None]
    for index, (first_name, first_path) in enumerate(named_paths):
        for second_name, second_path in named_paths[index + 1 :]:
            if _paths_refer_to_same_file(first_path, second_path):
                raise ValueError(f"{first_name} and {second_name} must refer to different files")


def _add_vault_key_option(parser) -> None:
    parser.add_argument(
        "--vault-key-env",
        help="Environment variable containing a Fernet key for encrypted FileVault storage",
    )


def _file_vault(path: str, args, default_ttl_seconds=None):
    encryption_key = None
    if args.vault_key_env:
        encryption_key = os.environ.get(args.vault_key_env)
        if encryption_key is None:
            raise ValueError(f"Environment variable '{args.vault_key_env}' is not set")
    return la.rag.FileVault(path, default_ttl_seconds=default_ttl_seconds, encryption_key=encryption_key)


def _run_rag_cli(argv):
    parser = argparse.ArgumentParser(description="LightAnon RAG text sanitization")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sanitize_parser = subparsers.add_parser("sanitize", help="Replace sensitive text with reversible tokens")
    sanitize_parser.add_argument("input_file", help="Path to input text file")
    sanitize_parser.add_argument("output_file", help="Path to output text file")
    sanitize_parser.add_argument("--vault", required=True, help="Path to JSON token vault")
    _add_vault_key_option(sanitize_parser)
    sanitize_parser.add_argument(
        "--scope-file",
        help="Write a token restoration scope for a later explicit restore operation",
    )
    sanitize_parser.add_argument("--encoding", default="utf-8", help="Text encoding")
    sanitize_parser.add_argument("--ttl-seconds", type=int, help="Default TTL for newly created vault mappings")
    sanitize_parser.add_argument(
        "--business-mode",
        choices=la.rag.TextSanitizer.BUSINESS_MODES,
        default="none",
        help="Organization requisites protection mode",
    )
    sanitize_parser.add_argument("--rules", help="Comma-separated built-in rules, for example EMAIL,PHONE,INN")
    sanitize_parser.add_argument(
        "--profile",
        choices=sorted(la.rag.TextSanitizer.PROFILES),
        default="basic",
        help="Built-in RAG rule profile",
    )

    restore_parser = subparsers.add_parser("restore", help="Restore original values from reversible tokens")
    restore_parser.add_argument("input_file", help="Path to input text file")
    restore_parser.add_argument("output_file", help="Path to output text file")
    restore_parser.add_argument("--vault", required=True, help="Path to JSON token vault")
    _add_vault_key_option(restore_parser)
    restore_parser.add_argument("--encoding", default="utf-8", help="Text encoding")
    restore_parser.add_argument(
        "--policy",
        choices=["restore", "no_personal_data", "mask", "restore_allowed_only"],
        default="mask",
        help="Deanonymization policy (default: mask)",
    )
    restore_parser.add_argument("--allowed-types", help="Comma-separated entity types for restore_allowed_only")
    restore_parser.add_argument(
        "--scope-file",
        help="Token scope created by rag sanitize; required by restoration policies",
    )

    scan_parser = subparsers.add_parser("scan", help="Detect RAG entities without writing a vault")
    scan_parser.add_argument("input_file", help="Path to input text file")
    scan_parser.add_argument("--encoding", default="utf-8", help="Text encoding")
    scan_parser.add_argument(
        "--business-mode",
        choices=la.rag.TextSanitizer.BUSINESS_MODES,
        default="none",
        help="Organization requisites protection mode",
    )
    scan_parser.add_argument(
        "--profile",
        choices=sorted(la.rag.TextSanitizer.PROFILES),
        default="basic",
        help="Built-in RAG rule profile",
    )
    scan_parser.add_argument("--rules", help="Comma-separated built-in rules, for example EMAIL,PHONE,INN")

    inspect_parser = subparsers.add_parser("inspect-vault", help="Print vault statistics without revealing values")
    inspect_parser.add_argument("vault_file", help="Path to JSON token vault")
    _add_vault_key_option(inspect_parser)

    delete_token_parser = subparsers.add_parser("delete-token", help="Delete one vault mapping by token")
    delete_token_parser.add_argument("vault_file", help="Path to JSON token vault")
    delete_token_parser.add_argument("token", help="Token to delete")
    _add_vault_key_option(delete_token_parser)

    delete_value_parser = subparsers.add_parser("delete-value", help="Delete one vault mapping by original value")
    delete_value_parser.add_argument("vault_file", help="Path to JSON token vault")
    delete_value_parser.add_argument("value", help="Original value to delete")
    _add_vault_key_option(delete_value_parser)

    clear_vault_parser = subparsers.add_parser("clear-vault", help="Delete all vault mappings")
    clear_vault_parser.add_argument("vault_file", help="Path to JSON token vault")
    _add_vault_key_option(clear_vault_parser)

    purge_parser = subparsers.add_parser("purge-expired", help="Delete expired vault mappings")
    purge_parser.add_argument("vault_file", help="Path to JSON token vault")
    _add_vault_key_option(purge_parser)

    args = parser.parse_args(argv)

    if args.command in {"sanitize", "restore"}:
        _validate_distinct_paths(
            input_file=args.input_file,
            output_file=args.output_file,
            vault=args.vault,
            scope_file=args.scope_file,
        )

    if args.command == "inspect-vault":
        vault = _file_vault(args.vault_file, args)
        stats = vault.stats()
        print(f"Vault: {stats['path']}")
        print(f"Total mappings: {stats['total']}")
        by_type = stats["by_type"]
        if by_type:
            print("Types:")
            for entity_type, count in sorted(by_type.items()):
                print(f" - {entity_type}: {count}")
        else:
            print("Types: none")
        return

    if args.command == "delete-token":
        vault = _file_vault(args.vault_file, args)
        deleted = vault.delete_token(args.token)
        print("Deleted: yes" if deleted else "Deleted: no")
        return

    if args.command == "delete-value":
        vault = _file_vault(args.vault_file, args)
        deleted = vault.delete_value(args.value)
        print("Deleted: yes" if deleted else "Deleted: no")
        return

    if args.command == "clear-vault":
        vault = _file_vault(args.vault_file, args)
        vault.clear()
        print("Vault cleared")
        return

    if args.command == "purge-expired":
        vault = _file_vault(args.vault_file, args)
        deleted = vault.purge_expired()
        print(f"Expired mappings deleted: {deleted}")
        return

    if args.command == "scan":
        enabled_rules = _parse_rule_names(args.rules) if args.rules else None
        sanitizer = la.rag.TextSanitizer(
            enabled_rules=enabled_rules,
            profile=args.profile,
            business_mode=args.business_mode,
        )
        text = _read_text(args.input_file, args.encoding)
        print(json.dumps(sanitizer.scan(text), ensure_ascii=False, indent=2))
        return

    text = _read_text(args.input_file, args.encoding)
    if args.command == "restore":
        vault = _file_vault(args.vault, args)
        sanitizer = la.rag.TextSanitizer(vault=vault)
        allowed_types = _parse_rule_names(args.allowed_types) if args.allowed_types else None
        token_scope = _read_token_scope(args.scope_file) if args.scope_file else None
        result = sanitizer.deanonymize(
            text,
            policy=args.policy,
            allowed_entity_types=allowed_types,
            token_scope=token_scope,
        )
    else:
        enabled_rules = _parse_rule_names(args.rules) if args.rules else None
        vault = _file_vault(args.vault, args, default_ttl_seconds=args.ttl_seconds)
        sanitizer = la.rag.TextSanitizer(
            vault=vault,
            enabled_rules=enabled_rules,
            profile=args.profile,
            business_mode=args.business_mode,
        )
        result, token_scope = sanitizer.sanitize_with_scope(text)
        if args.scope_file:
            _write_token_scope(args.scope_file, token_scope)

    _write_text(args.output_file, result, args.encoding)
    print(f"Saved to {args.output_file}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if argv and argv[0] == "rag":
        return _run_rag_cli(argv[1:])

    parser = argparse.ArgumentParser(description="LightAnon CLI Tool")
    parser.add_argument("input_file", help="Path to input CSV/Parquet")
    parser.add_argument("output_file", help="Path to output file")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config schema")
    parser.add_argument("--engine", choices=["pandas", "polars"], default="pandas", help="Processing engine")

    args = parser.parse_args(argv)

    _validate_distinct_paths(
        input_file=args.input_file,
        output_file=args.output_file,
        config_file=args.config,
    )

    print(f"Loading schema from {args.config}...")
    schema = load_schema(args.config)

    print(f"Reading {args.input_file} using {args.engine}...")
    df = _read_dataframe(args.input_file, args.engine)

    engine = la.Engine(schema)
    clean_df = engine.run(df)

    print(f"Saving to {args.output_file}...")
    _write_dataframe(clean_df, args.output_file, args.engine)

    print("Done!")
    print(engine.generate_report())
    if any(entry["status"] != "success" for entry in engine.audit_log):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
