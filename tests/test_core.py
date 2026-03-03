import pytest
import pandas as pd
import numpy as np
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


def test_masking():
    """Проверка: Маскирование скрывает часть строки."""
    rule = la.rules.Mask(visible_chars=1)
    s = pd.Series(["Ivanov", "A", None])
    res = rule.apply(s)

    assert res[0] == "I*****"
    assert res[1] == "A"  # Если длина <= visible, оставляем как есть или * (зависит от логики, тут проверка на crash)
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
        "email": la.rules.Hash(),
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


def test_report_generation(sample_df):
    """Проверка: Отчет генерируется и содержит ключевые слова."""
    schema = {"email": la.rules.Hash()}
    engine = la.Engine(schema)
    engine.run(sample_df)
    report = engine.generate_report()

    assert "COMPLIANCE AUDIT REPORT" in report
    assert "Introduction of Identifiers" in report  # Метод из 152-ФЗ