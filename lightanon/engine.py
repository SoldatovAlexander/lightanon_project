import pandas as pd
from typing import Dict
from .rules import BaseRule


class Engine:
    def __init__(self, schema: Dict[str, BaseRule]):
        """
        schema: Словарь, где ключ - имя колонки, значение - экземпляр правила.
        """
        self.schema = schema
        self.audit_log = []

    def run(self, df: pd.DataFrame) -> pd.DataFrame:
        """Основной метод запуска пайплайна."""
        df_clean = df.copy()

        print(f"Starting anonymization on {len(df)} rows...")

        for column, rule in self.schema.items():
            if column not in df.columns:
                print(f"Warning: Column '{column}' not found in DataFrame.")
                continue

            # Применяем правило
            try:
                original_sample = df[column].iloc[0] if len(df) > 0 else "N/A"
                df_clean[column] = rule.apply(df[column])

                # Логируем успех для аудита
                self.audit_log.append({
                    "column": column,
                    "rule": rule.name,
                    "legal_basis": rule.legal_method,
                    "status": "Success"
                })
            except Exception as e:
                self.audit_log.append({
                    "column": column,
                    "rule": rule.name,
                    "status": f"Error: {str(e)}"
                })

        return df_clean

    def generate_report(self) -> str:
        """Генерация отчета для Compliance (152-ФЗ)."""
        report = ["COMPLIANCE AUDIT REPORT (Roskomnadzor Order No. 996)", "=" * 60]

        methods_used = set()

        for entry in self.audit_log:
            if entry["status"] == "Success":
                line = f"[PASS] Column '{entry['column']}': Applied {entry['rule']}"
                line += f"\n       -> Compliance: {entry['legal_basis']}"
                report.append(line)
                methods_used.add(entry['legal_basis'])
            else:
                report.append(f"[FAIL] Column '{entry['column']}': {entry['status']}")

        report.append("-" * 60)
        report.append("SUMMARY:")
        report.append(f"Total Columns Processed: {len(self.audit_log)}")
        report.append("Legal Methods Utilized:")
        for m in methods_used:
            report.append(f" - {m}")

        return "\n".join(report)