import numpy as np
import pandas as pd
from .rules import BaseRule


class MultiplicativeNoise(BaseRule):
    """
    Умножение на случайный коэффициент.
    Идеально для транзакций разного масштаба (от копеек до миллионов).
    Сохраняет тренды, но скрывает точные суммы.
    """

    def __init__(self, std_dev_percent: float = 0.05):
        """
        std_dev_percent: 0.05 означает отклонение примерно на 5%
        """
        super().__init__()
        self.std = std_dev_percent
        self.legal_method = "Change of Composition (Method 2) - Perturbation"

    def apply(self, series: pd.Series) -> pd.Series:
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError("MultiplicativeNoise can only be applied to numeric columns")

        # Генерируем коэффициенты вокруг 1.0 (например, от 0.95 до 1.05)
        # abs() нужен, чтобы случайно не сменить знак транзакции (если это не разрешено)
        noise = np.random.normal(1.0, self.std, size=len(series))

        return series * noise


class TopCoding(BaseRule):
    """
    Ограничение выбросов (Winsorization/Clipping).
    Все значения выше порога (quantile) заменяются на этот порог.
    Защищает от идентификации по уникально большим суммам.
    """

    def __init__(self, quantile: float = 0.99):
        super().__init__()
        self.quantile = quantile
        self.legal_method = "Change of Composition (Method 2) - Generalization"

    def apply(self, series: pd.Series) -> pd.Series:
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError("TopCoding can only be applied to numeric columns")

        # Вычисляем порог (например, 99-й перцентиль)
        cap_value = series.quantile(self.quantile)

        # Заменяем все, что выше, на cap_value
        return series.clip(upper=cap_value)


class CreditCardMask(BaseRule):
    """
    Маскирование по стандарту PCI DSS (оставляем последние 4 цифры).
    """

    def __init__(self):
        super().__init__()
        self.legal_method = "Introduction of Identifiers (Method 1)"

    def _mask_cc(self, val):
        s = str(val).replace(" ", "").replace("-", "")
        if len(s) < 4:
            return "*" * len(s)
        return "**** **** **** " + s[-4:]

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._mask_cc)