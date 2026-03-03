import argparse
import yaml
import pandas as pd
import polars as pl
import lightanon as la
import os


def load_schema(config_path):
    """Парсинг YAML конфига и превращение его в объекты правил."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    schema = {}
    for col, rule_def in config.items():
        # rule_def пример: {'method': 'Hash', 'params': {'salt': 'xyz'}}
        method_name = rule_def.get('method')
        params = rule_def.get('params', {})

        # Динамический поиск класса правила
        # Сначала ищем в core rules
        if hasattr(la.rules, method_name):
            rule_cls = getattr(la.rules, method_name)
        # Потом в financial
        elif hasattr(la.financial, method_name):
            rule_cls = getattr(la.financial, method_name)
        else:
            print(f"Warning: Unknown rule '{method_name}' for column '{col}'")
            continue

        schema[col] = rule_cls(**params)

    return schema


def main():
    parser = argparse.ArgumentParser(description="LightAnon CLI Tool")
    parser.add_argument("input_file", help="Path to input CSV/Parquet")
    parser.add_argument("output_file", help="Path to output file")
    parser.add_argument("--config", "-c", required=True, help="Path to YAML config schema")
    parser.add_argument("--engine", choices=["pandas", "polars"], default="pandas", help="Processing engine")

    args = parser.parse_args()

    # 1. Загрузка схемы
    print(f"Loading schema from {args.config}...")
    schema = load_schema(args.config)

    # 2. Чтение данных
    print(f"Reading {args.input_file} using {args.engine}...")
    if args.engine == "polars":
        # Polars умеет scan_csv (лениво), но для начала сделаем read_csv
        df = pl.read_csv(args.input_file) if args.input_file.endswith('.csv') else pl.read_parquet(args.input_file)
    else:
        df = pd.read_csv(args.input_file) if args.input_file.endswith('.csv') else pd.read_parquet(args.input_file)

    # 3. Обработка
    engine = la.Engine(schema)
    clean_df = engine.run(df)

    # 4. Сохранение
    print(f"Saving to {args.output_file}...")
    if args.engine == "polars":
        clean_df.write_csv(args.output_file)
    else:
        clean_df.to_csv(args.output_file, index=False)

    print("Done!")
    print(engine.generate_report())


if __name__ == "__main__":
    main()