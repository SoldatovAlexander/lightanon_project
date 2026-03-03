import argparse
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


def main():
    parser = argparse.ArgumentParser(description="LightAnon CLI Tool")
    parser.add_argument("input_file", help="Path to input CSV/Parquet")
    parser.add_argument("output_file", help="Path to output file")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config schema")
    parser.add_argument("--engine", choices=["pandas", "polars"], default="pandas", help="Processing engine")

    args = parser.parse_args()

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
