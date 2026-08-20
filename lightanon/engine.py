import pandas as pd
import polars as pl
from typing import Dict, Union
from .rules import BaseRule


class Engine:
    def __init__(self, schema: Dict[str, BaseRule]):
        self.schema = schema
        self.audit_log = []

    def run(self, df: Union[pd.DataFrame, pl.DataFrame]) -> Union[pd.DataFrame, pl.DataFrame]:
        self.audit_log = []

        if isinstance(df, pl.DataFrame):
            return self._run_polars(df)
        if isinstance(df, pd.DataFrame):
            return self._run_pandas(df)
        raise ValueError("Unsupported DataFrame type. Use Pandas or Polars.")

    def _run_pandas(self, df: pd.DataFrame) -> pd.DataFrame:
        df_clean = df.copy()

        for column, rule in self.schema.items():
            if column not in df.columns:
                self.audit_log.append(
                    {
                        "column": column,
                        "rule": rule.name,
                        "legal_basis": rule.legal_method,
                        "status": "Missing column",
                    }
                )
                continue

            try:
                df_clean[column] = rule.apply(df[column])
                self.audit_log.append(
                    {
                        "column": column,
                        "rule": rule.name,
                        "legal_basis": rule.legal_method,
                        "status": "Success",
                    }
                )
            except Exception as exc:
                df_clean[column] = pd.NA
                self.audit_log.append(
                    {
                        "column": column,
                        "rule": rule.name,
                        "legal_basis": rule.legal_method,
                        "status": f"Error: {exc}",
                    }
                )

        return df_clean

    def _run_polars(self, df: pl.DataFrame) -> pl.DataFrame:
        expressions = []

        for column, rule in self.schema.items():
            if column not in df.columns:
                self.audit_log.append(
                    {
                        "column": column,
                        "rule": rule.name,
                        "legal_basis": rule.legal_method,
                        "status": "Missing column",
                    }
                )
                continue

            try:
                expressions.append(rule.apply_polars(column).alias(column))
                self.audit_log.append(
                    {
                        "column": column,
                        "rule": rule.name,
                        "legal_basis": rule.legal_method,
                        "status": "Success",
                    }
                )
            except Exception as exc:
                expressions.append(pl.lit(None).alias(column))
                self.audit_log.append(
                    {
                        "column": column,
                        "rule": rule.name,
                        "legal_basis": rule.legal_method,
                        "status": f"Error: {exc}",
                    }
                )

        if not expressions:
            return df.clone()
        return df.with_columns(expressions)

    def generate_report(self) -> str:
        report = ["ANONYMIZATION PROCESSING REPORT", "=" * 60]
        methods_used = set()

        if not self.audit_log:
            report.append("No columns were processed.")

        for entry in self.audit_log:
            status = entry["status"]
            if status == "Success":
                report.append(
                    f"[PASS] Column '{entry['column']}': Applied {entry['rule']}\n"
                    f"       -> Declared method: {entry['legal_basis']}"
                )
                methods_used.add(entry["legal_basis"])
            else:
                report.append(f"[FAIL] Column '{entry['column']}': {status}")

        report.append("-" * 60)
        report.append("SUMMARY:")
        report.append(f"Total Columns Processed: {len(self.audit_log)}")
        report.append("Declared Methods:")
        if methods_used:
            for method in sorted(methods_used):
                report.append(f" - {method}")
        else:
            report.append(" - None")

        report.append("This technical report is not a legal compliance determination.")
        return "\n".join(report)
