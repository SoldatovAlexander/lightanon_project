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
                self._record_error(column, rule, "missing_column")
                continue

            try:
                df_clean[column] = rule.apply(df[column])
                self._record_success(column, rule)
            except Exception as exc:
                df_clean[column] = pd.NA
                self._record_error(column, rule, "rule_execution_failed", exc)

        return df_clean

    def _run_polars(self, df: pl.DataFrame) -> pl.DataFrame:
        df_clean = df.clone()

        for column, rule in self.schema.items():
            if column not in df.columns:
                self._record_error(column, rule, "missing_column")
                continue

            try:
                transformed = df.select(rule.apply_polars(column).alias(column)).get_column(column)
                df_clean = df_clean.with_columns(transformed)
                self._record_success(column, rule)
            except Exception as exc:
                df_clean = df_clean.with_columns(pl.lit(None).alias(column))
                self._record_error(column, rule, "rule_execution_failed", exc)

        return df_clean

    def _record_success(self, column: str, rule: BaseRule) -> None:
        self.audit_log.append(
            {
                "column": column,
                "rule": rule.name,
                "legal_basis": rule.legal_method,
                "status": "success",
                "error_code": None,
                "exception_type": None,
            }
        )

    def _record_error(
        self,
        column: str,
        rule: BaseRule,
        error_code: str,
        exc: Exception = None,
    ) -> None:
        self.audit_log.append(
            {
                "column": column,
                "rule": rule.name,
                "legal_basis": rule.legal_method,
                "status": "error",
                "error_code": error_code,
                "exception_type": type(exc).__name__ if exc is not None else None,
            }
        )

    def generate_report(self) -> str:
        report = ["ANONYMIZATION PROCESSING REPORT", "=" * 60]
        methods_used = set()

        if not self.audit_log:
            report.append("No columns were processed.")

        for entry in self.audit_log:
            status = entry["status"]
            if status == "success":
                report.append(
                    f"[PASS] Column '{entry['column']}': Applied {entry['rule']}\n"
                    f"       -> Declared method: {entry['legal_basis']}"
                )
                methods_used.add(entry["legal_basis"])
            else:
                details = entry["error_code"]
                if entry["exception_type"]:
                    details += f" ({entry['exception_type']})"
                report.append(f"[FAIL] Column '{entry['column']}': {details}")

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
