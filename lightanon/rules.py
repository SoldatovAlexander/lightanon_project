import hashlib
import numpy as np
import pandas as pd
from typing import Union, Optional, List


class BaseRule:
    """Базовый класс для всех правил анонимизации."""

    def __init__(self):
        self.name = self.__class__.__name__
        self.legal_method = "Unknown"  # Для отчета по 152-ФЗ

    def apply(self, series: pd.Series) -> pd.Series:
        raise NotImplementedError


class Hash(BaseRule):
    """Детерминированное хэширование (Метод введения идентификаторов)."""

    def __init__(self, salt: str = ""):
        super().__init__()
        self.salt = salt
        self.legal_method = "Introduction of Identifiers (Method 1)"

    def _hash_val(self, val) -> str:
        if pd.isna(val): return val
        # sha256 работает быстро и надежно
        s = f"{str(val)}{self.salt}".encode('utf-8')
        return hashlib.sha256(s).hexdigest()

    def apply(self, series: pd.Series) -> pd.Series:
        # Используем map/apply, так как хеширование строковое
        return series.apply(self._hash_val)


class Mask(BaseRule):
    """Маскирование части строки (Метод введения идентификаторов)."""

    def __init__(self, visible_chars: int = 1, position: str = 'start'):
        super().__init__()
        self.visible_chars = visible_chars
        self.legal_method = "Introduction of Identifiers (Method 1)"

    def _mask_val(self, val) -> str:
        if pd.isna(val): return val
        s = str(val)
        if len(s) <= self.visible_chars:
            return "*" * len(s)

        # Простая логика: показать первые N символов
        return s[:self.visible_chars] + "*" * (len(s) - self.visible_chars)

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._mask_val)


class GaussianNoise(BaseRule):
    """Добавление шума (Метод изменения состава). Сохраняет среднее."""

    def __init__(self, std: float = 0.1):
        super().__init__()
        self.std = std  # Доля стандартного отклонения (0.1 = 10% от значения)
        self.legal_method = "Change of Composition/Semantics (Method 2)"

    def apply(self, series: pd.Series) -> pd.Series:
        # ВЕКТОРИЗАЦИЯ: Это работает очень быстро
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError("GaussianNoise can only be applied to numeric columns")

        noise = np.random.normal(0, series * self.std, size=len(series))
        return series + noise


class Generalize(BaseRule):
    """Обобщение/Баккетинг (Метод изменения состава)."""

    def __init__(self, step: int = 5):
        super().__init__()
        self.step = step
        self.legal_method = "Change of Composition/Semantics (Method 2)"

    def apply(self, series: pd.Series) -> pd.Series:
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError("Generalize can only be applied to numeric columns")

        # Используем математику для округления вниз до шага
        # Пример: step=5, val=23 -> (23 // 5) * 5 = 20 -> "20-25"
        floored = (series // self.step) * self.step
        return floored.astype(str) + "-" + (floored + self.step).astype(str)