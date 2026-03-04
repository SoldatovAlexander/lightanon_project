# lightanon/rules.py

import hashlib
import numpy as np
import pandas as pd
import polars as pl
from typing import Union, Any


class BaseRule:
    def __init__(self):
        self.name = self.__class__.__name__
        self.legal_method = "Unknown"

    def apply(self, series: pd.Series) -> pd.Series:
        raise NotImplementedError

    def apply_polars(self, col_name: str) -> pl.Expr:
        raise NotImplementedError(f"Rule {self.name} does not support Polars")

    def apply_single(self, value: Any) -> Any:
        """
        Обработка одиночного значения (для Streaming).
        Переопределите этот метод для высокой производительности.
        """
        # Fallback: Если метод не переопределен, используем Pandas (медленно!)
        return self.apply(pd.Series([value])).iloc[0]


class Hash(BaseRule):
    def __init__(self, salt: str = ""):
        super().__init__()
        self.salt = salt
        self.legal_method = "Introduction of Identifiers"

    def _hash_val(self, val) -> str:
        if val is None or pd.isna(val): return None
        s = f"{str(val)}{self.salt}".encode('utf-8')
        return hashlib.sha256(s).hexdigest()

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._hash_val)

    def apply_polars(self, col_name: str) -> pl.Expr:
        return pl.col(col_name).map_elements(lambda x: self._hash_val(x), return_dtype=pl.Utf8)

    def apply_single(self, value: Any) -> Any:
        # Быстрая версия для стриминга
        return self._hash_val(value)


class Mask(BaseRule):
    def __init__(self, visible_chars: int = 1):
        super().__init__()
        self.visible_chars = visible_chars
        self.legal_method = "Introduction of Identifiers"

    def _mask_val(self, val) -> str:
        if val is None or pd.isna(val):
            return None
        s = str(val)
        if len(s) <= self.visible_chars:
            return s
        return s[:self.visible_chars] + "*" * (len(s) - self.visible_chars)

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._mask_val)

    def apply_single(self, value: Any) -> Any:
        return self._mask_val(value)


class GaussianNoise(BaseRule):
    def __init__(self, std: float = 0.1):
        super().__init__()
        self.std = std
        self.legal_method = "Change of Composition"

    def apply(self, series: pd.Series) -> pd.Series:
        noise = np.random.normal(0, series * self.std, size=len(series))
        return series + noise

    def apply_single(self, value: Any) -> Any:
        # Чистый Python/Numpy для одного числа
        if value is None: return None
        return value + np.random.normal(0, value * self.std)


class Generalize(BaseRule):
    def __init__(self, step: int = 5):
        super().__init__()
        self.step = step
        self.legal_method = "Change of Composition"

    def apply(self, series: pd.Series) -> pd.Series:
        floored = (series // self.step) * self.step
        return floored.astype(str) + "-" + (floored + self.step).astype(str)

    def apply_single(self, value: Any) -> Any:
        if value is None: return None
        floored = (value // self.step) * self.step
        return f"{floored}-{floored + self.step}"
