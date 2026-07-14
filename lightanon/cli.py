import argparse
import sys
from pathlib import Path

import yaml
import pandas as pd
import polars as pl
import lightanon as la


def load_schema(config_path: str):
    """Parse YAML config and create rule instances."""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if config is None:
        return {}
    if not isinstance(config, dict):
        raise ValueError("Schema config must be a mapping: {column: {method, params}}")

    schema = {}
    for col, rule_def in config.items():
        if not isinstance(rule_def, dict):
            print(f"Warning: Invalid rule format for column '{col}', skipping")
            continue

        method_name = rule_def.get('method')
        params = rule_def.get('params', {})
        if not method_name:
            print(f"Warning: Missing 'method' for column '{col}', skipping")
            continue

        if hasattr(la.rules, method_name):
            rule_cls = getattr(la.rules, method_name)
        elif hasattr(la.financial, method_name):
            rule_cls = getattr(la.financial, method_name)
        else:
            print(f"Warning: Unknown rule '{method_name}' for column '{col}'")
            continue

        schema[col] = rule_cls(**params)

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


def _write_dataframe(df, path: str, engine_name: str):
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


def _read_text(path: str, encoding: str) -> str:
    return Path(path).read_text(encoding=encoding)


def _write_text(path: str, text: str, encoding: str) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding=encoding)


def _run_rag_cli(argv):
    parser = argparse.ArgumentParser(description="LightAnon RAG text sanitization")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command, help_text in (
        ("sanitize", "Replace sensitive text with reversible tokens"),
        ("restore", "Restore original values from reversible tokens"),
    ):
        subparser = subparsers.add_parser(command, help=help_text)
        subparser.add_argument("input_file", help="Path to input text file")
        subparser.add_argument("output_file", help="Path to output text file")
        subparser.add_argument("--vault", required=True, help="Path to JSON token vault")
        subparser.add_argument("--encoding", default="utf-8", help="Text encoding")

    inspect_parser = subparsers.add_parser("inspect-vault", help="Print vault statistics without revealing values")
    inspect_parser.add_argument("vault_file", help="Path to JSON token vault")

    args = parser.parse_args(argv)

    if args.command == "inspect-vault":
        vault = la.rag.FileVault(args.vault_file)
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

    vault = la.rag.FileVault(args.vault)
    sanitizer = la.rag.TextSanitizer(vault=vault)
    text = _read_text(args.input_file, args.encoding)

    if args.command == "sanitize":
        result = sanitizer.sanitize(text)
    else:
        result = sanitizer.deanonymize(text)

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

    print(f"Loading schema from {args.config}...")
    schema = load_schema(args.config)
    if not schema:
        print("Warning: schema is empty. Output will match input.")

    print(f"Reading {args.input_file} using {args.engine}...")
    df = _read_dataframe(args.input_file, args.engine)

    engine = la.Engine(schema)
    clean_df = engine.run(df)

    print(f"Saving to {args.output_file}...")
    _write_dataframe(clean_df, args.output_file, args.engine)

    print("Done!")
    print(engine.generate_report())


if __name__ == "__main__":
    main()
