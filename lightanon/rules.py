import hashlib
import numpy as np
import pandas as pd
import polars as pl  # <-- Импортируем Polars
from typing import Union


class BaseRule:
    def __init__(self):
        self.name = self.__class__.__name__
        self.legal_method = "Unknown"

    def apply(self, series: pd.Series) -> pd.Series:
        """Pandas implementation"""
        raise NotImplementedError

    def apply_polars(self, col_name: str) -> pl.Expr:
        """
        Polars implementation.
        Возвращает Expression, который движок подставит в .with_columns()
        """
        raise NotImplementedError(f"Rule {self.name} does not support Polars yet")


class Hash(BaseRule):
    def __init__(self, salt: str = ""):
        super().__init__()
        self.salt = salt
        self.legal_method = "Introduction of Identifiers (Method 1)"

    def _hash_val(self, val) -> str:
        # (Тот же код хеширования для Pandas)
        if pd.isna(val): return val
        s = f"{str(val)}{self.salt}".encode('utf-8')
        return hashlib.sha256(s).hexdigest()

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._hash_val)

    def apply_polars(self, col_name: str) -> pl.Expr:
        # В Polars для кастомных питоновских функций (SHA256) используем map_elements
        # Это не супер-быстро, но работает. Для скорости можно использовать встроенный hash() (не криптостойкий)
        return pl.col(col_name).map_elements(lambda x: self._hash_val(x), return_dtype=pl.Utf8)


class GaussianNoise(BaseRule):
    def __init__(self, std: float = 0.1):
        super().__init__()
        self.std = std
        self.legal_method = "Change of Composition (Method 2)"

    def apply(self, series: pd.Series) -> pd.Series:
        noise = np.random.normal(0, series * self.std, size=len(series))
        return series + noise

    def apply_polars(self, col_name: str) -> pl.Expr:
        # В Polars мы используем нативные выражения -> ЭТО ОЧЕНЬ БЫСТРО
        # Генерируем случайный множитель: 1 + random_noise
        # (Упрощение: Polars пока сложен с random state, используем apply для точного матча с numpy или native random)

        # Вариант Native (быстрый):
        return pl.col(col_name) * pl.lit(1.0 + np.random.normal(0, self.std))
        # Примечание: для честного row-wise random в Polars нужен map_batches или плагин,
        # но для MVP можно использовать apply с numpy для точности.

        # Вариант через map_batches (компромисс):
        return pl.col(col_name).map_batches(lambda s: s + np.random.normal(0, s * self.std, size=len(s)))


class Generalize(BaseRule):
    def __init__(self, step: int = 5):
        super().__init__()
        self.step = step
        self.legal_method = "Change of Composition (Method 2)"

    def apply(self, series: pd.Series) -> pd.Series:
        floored = (series // self.step) * self.step
        return floored.astype(str) + "-" + (floored + self.step).astype(str)

    def apply_polars(self, col_name: str) -> pl.Expr:
        # Чистый Polars Expression!
        floored = (pl.col(col_name) // self.step) * self.step
        return (floored.cast(pl.Utf8) + "-" + (floored + self.step).cast(pl.Utf8))