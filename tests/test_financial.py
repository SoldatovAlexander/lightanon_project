import pytest
import pandas as pd
import numpy as np
import lightanon as la


def test_top_coding_winsorization():
    """
    Проверка: Значения выше перцентиля обрезаются.
    Это критично для скрытия VIP-клиентов.
    """
    # Создаем данные: 99 человек с 10 рублями и 1 "кит" с 1000 рублей
    data = [10] * 99 + [1000]
    s = pd.Series(data)

    # Обрезаем по 99%
    rule = la.financial.TopCoding(quantile=0.99)
    res = rule.apply(s)

    # Максимальное значение должно стать 10 (или близко к тому, зависит от интерполяции квантиля),
    # но точно МЕНЬШЕ 1000.
    # В pandas quantile(0.99) для такого ряда будет ~19.9

    assert res.max() < 1000
    assert res.max() == s.quantile(0.99)
    # Обычные юзеры не пострадали
    assert res[0] == 10


def test_multiplicative_noise_trend():
    """
    Проверка: Шум мультипликативный, а не аддитивный.
    Для 100 шум 5% -> +/- 5.
    Для 1 000 000 шум 5% -> +/- 50 000.
    """
    np.random.seed(42)
    s = pd.Series([100.0, 1000000.0])
    rule = la.financial.MultiplicativeNoise(std_dev_percent=0.05)

    res = rule.apply(s)

    diff_small = abs(res[0] - 100)
    diff_large = abs(res[1] - 1000000)

    # Отклонение большого числа должно быть значительно больше отклонения малого
    assert diff_large > diff_small * 1000


def test_credit_card_mask():
    """Проверка PCI DSS маскирования."""
    rule = la.financial.CreditCardMask()

    # Тест разных форматов
    cards = pd.Series([
        "4444-5555-6666-7777",
        "4444555566667777",
        "1234"  # Короткая
    ])
    res = rule.apply(cards)

    assert res[0].endswith("7777")
    assert res[0].startswith("****")
    assert "5555" not in res[0]  # Середина скрыта

    assert res[1].endswith("7777")
    assert res[2] == "****"  # Короткая скрывается полностью или частично