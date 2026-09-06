import pytest
import pandas as pd
import numpy as np
import polars as pl
import lightanon as la


# Фикстура данных (создается перед каждым тестом)
@pytest.fixture
def sample_df():
    return pd.DataFrame({
        "name": ["Alice", "Bob", "Charlie", None],
        "email": ["alice@mail.com", "bob@corp.org", "charlie@ya.ru", None],
        "age": [23, 45, 31, 28],
        "salary": [100.0, 200.0, 300.0, 400.0]
    })


def test_hash_determinism():
    """Проверка: Один и тот же ввод дает одинаковый хэш (важно для JOIN)."""
    rule = la.rules.Hash(salt="salty")

    s1 = pd.Series(["test", "test"])
    res = rule.apply(s1)

    assert res[0] == res[1]  # Хэши совпадают
    assert res[0] != "test"  # Значение изменилось
    assert len(res[0]) == 64  # SHA-256 длина


def test_hash_salting():
    """Проверка: Разная соль дает разные хэши."""
    r1 = la.rules.Hash(salt="A")
    r2 = la.rules.Hash(salt="B")

    val = pd.Series(["secret"])
    assert r1.apply(val)[0] != r2.apply(val)[0]


def test_hash_requires_non_empty_secret_salt():
    with pytest.raises(ValueError, match="non-empty secret salt"):
        la.rules.Hash("")


def test_mask_hides_values_not_longer_than_visible_prefix():
    rule = la.rules.Mask(visible_chars=2)

    assert rule.apply(pd.Series(["A", "AB", "ABC"])).tolist() == ["*", "**", "AB*"]


def test_masking():
    """Проверка: Маскирование скрывает часть строки."""
    rule = la.rules.Mask(visible_chars=1)
    s = pd.Series(["Ivanov", "A", None])
    res = rule.apply(s)

    assert res[0] == "I*****"
    assert res[1] == "*"
    assert pd.isna(res[2])  # None остается None


def test_generalize_age():
    """Проверка: Возраст 23 превращается в интервал 20-25."""
    rule = la.rules.Generalize(step=5)
    s = pd.Series([23, 20, 29])
    res = rule.apply(s)

    assert res[0] == "20-25"
    assert res[1] == "20-25"
    assert res[2] == "25-30"


def test_gaussian_noise_stats():
    """Проверка: Шум не смещает среднее значение слишком сильно (Law of Large Numbers)."""
    np.random.seed(42)  # Фиксируем рандом для воспроизводимости

    # 10 000 значений по 100
    data = pd.Series(np.ones(10000) * 100)
    rule = la.rules.GaussianNoise(std=0.1)  # 10% шум

    res = rule.apply(data)

    # Среднее должно остаться около 100 (допустим погрешность 1%)
    assert 99 < res.mean() < 101
    # Дисперсия должна появиться (была 0, стала > 0)
    assert res.std() > 0


def test_engine_integration(sample_df):
    """Проверка: Движок корректно обрабатывает DataFrame."""
    schema = {
        "email": la.rules.Hash(salt="test_salt"),
        "age": la.rules.Generalize(step=10)
    }
    engine = la.Engine(schema)
    clean_df = engine.run(sample_df)

    # Проверяем, что email изменился
    assert clean_df["email"][0] != sample_df["email"][0]
    # Проверяем, что age стал строкой (интервалом)
    assert isinstance(clean_df["age"][0], str)
    # Проверяем, что salary НЕ изменилась (ее нет в схеме)
    assert clean_df["salary"][0] == sample_df["salary"][0]


def test_engine_replaces_failed_pandas_column_with_na():
    """Rule errors must not leave raw source values in the output."""
    df = pd.DataFrame({"salary": [100.0, -50.0, 3000.0]})
    engine = la.Engine({"salary": la.rules.GaussianNoise(std=0.1)})

    clean_df = engine.run(df)

    assert clean_df["salary"].isna().all()
    assert engine.audit_log[0]["status"] == "error"
    assert engine.audit_log[0]["error_code"] == "rule_execution_failed"


def test_engine_replaces_failed_financial_column_with_na():
    df = pd.DataFrame({"amount": ["100", "200", "300"]})
    engine = la.Engine({"amount": la.financial.MultiplicativeNoise()})

    clean_df = engine.run(df)

    assert clean_df["amount"].isna().all()
    assert engine.audit_log[0]["status"] == "error"


def test_engine_replaces_failed_top_coding_fixed_batch_column_with_na():
    df = pd.DataFrame({"amount": [100.0, 20000.0, 300.0]})
    engine = la.Engine({"amount": la.financial.TopCodingFixed(cap_value=10000.0)})

    clean_df = engine.run(df)

    assert clean_df["amount"].isna().all()
    assert engine.audit_log[0]["status"] == "error"


def test_engine_replaces_failed_polars_column_with_null():
    df = pl.DataFrame({"amount": ["100", "200", "300"]})
    engine = la.Engine({"amount": la.financial.MultiplicativeNoise()})

    clean_df = engine.run(df)

    assert clean_df["amount"].null_count() == clean_df.height
    assert engine.audit_log[0]["status"] == "error"


def test_polars_runtime_error_is_fail_closed_and_audited():
    class FailingPolarsRule(la.rules.BaseRule):
        def apply_polars(self, col_name):
            return pl.col(col_name).cast(pl.Int64)

    engine = la.Engine({"email": FailingPolarsRule()})
    clean_df = engine.run(pl.DataFrame({"email": ["review@example.com"]}))

    assert clean_df["email"].null_count() == 1
    assert engine.audit_log == [
        {
            "column": "email",
            "rule": "FailingPolarsRule",
            "legal_basis": "Unknown",
            "status": "error",
            "error_code": "rule_execution_failed",
            "exception_type": "InvalidOperationError",
        }
    ]


def test_audit_report_does_not_include_exception_message_or_source_value():
    class LeakyRule(la.rules.BaseRule):
        def apply(self, series):
            raise ValueError(f"untrusted input: {series.iloc[0]}")

    engine = la.Engine({"email": LeakyRule()})
    engine.run(pd.DataFrame({"email": ["review@example.com"]}))
    report = engine.generate_report()

    assert "review@example.com" not in report
    assert "untrusted input" not in report
    assert "rule_execution_failed (ValueError)" in report


def test_report_generation(sample_df):
    """Проверка: Отчет генерируется и содержит ключевые слова."""
    schema = {"email": la.rules.Hash(salt="test_salt")}
    engine = la.Engine(schema)
    engine.run(sample_df)
    report = engine.generate_report()

    assert "ANONYMIZATION PROCESSING REPORT" in report
    assert "Introduction of Identifiers" in report  # Метод из 152-ФЗ
    assert "not a legal compliance determination" in report
