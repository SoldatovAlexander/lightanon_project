import pandas as pd
import polars as pl
from typing import Dict, Union
from .rules import BaseRule


class Engine:
    def __init__(self, schema: Dict[str, BaseRule]):
        self.schema = schema
        self.audit_log = []

    def run(self, df: Union[pd.DataFrame, pl.DataFrame]) -> Union[pd.DataFrame, pl.DataFrame]:
        # 1. Если это Polars
        if isinstance(df, pl.DataFrame):
            print("🚀 Polars Engine Detected: Switching to Turbo Mode")
            expressions = []

            for col, rule in self.schema.items():
                if col in df.columns:
                    try:
                        # Собираем выражения для ленивого выполнения
                        expressions.append(rule.apply_polars(col).alias(col))
                        self.audit_log.append({"column": col, "rule": rule.name, "status": "Success (Polars)"})
                    except Exception as e:
                        print(f"Error in Polars rule for {col}: {e}")

            # Выполняем всё разом (параллельно)
            return df.with_columns(expressions)

        # 2. Если это Pandas (старый код)
        elif isinstance(df, pd.DataFrame):
            # ... (твой старый код для Pandas)
            df_clean = df.copy()
            for col, rule in self.schema.items():
                # ...
                df_clean[col] = rule.apply(df[col])
            return df_clean

        else:
            raise ValueError("Unsupported DataFrame type. Use Pandas or Polars.")