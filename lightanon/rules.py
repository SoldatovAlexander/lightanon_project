import hashlib
import numpy as np
import pandas as pd
import polars as pl


class BaseRule:
    def __init__(self):
        self.name = self.__class__.__name__
        self.legal_method = "Unknown"

    def apply(self, series: pd.Series) -> pd.Series:
        raise NotImplementedError

    def apply_polars(self, col_name: str) -> pl.Expr:
        raise NotImplementedError(f"Rule {self.name} does not support Polars yet")


class Hash(BaseRule):
    def __init__(self, salt: str = ""):
        super().__init__()
        self.salt = salt
        self.legal_method = "Introduction of Identifiers (Method 1)"

    def _hash_val(self, val):
        if pd.isna(val):
            return val
        source = f"{val}{self.salt}".encode("utf-8")
        return hashlib.sha256(source).hexdigest()

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._hash_val)

    def apply_polars(self, col_name: str) -> pl.Expr:
        return pl.col(col_name).map_elements(self._hash_val, return_dtype=pl.Utf8)


class Mask(BaseRule):
    def __init__(self, visible_chars: int = 1):
        super().__init__()
        self.visible_chars = visible_chars
        self.legal_method = "Introduction of Identifiers (Method 1)"

    def _mask_val(self, val):
        if pd.isna(val):
            return val

        text = str(val)
        if len(text) <= self.visible_chars:
            return text

        hidden = "*" * (len(text) - self.visible_chars)
        return f"{text[:self.visible_chars]}{hidden}"

    def apply(self, series: pd.Series) -> pd.Series:
        return series.apply(self._mask_val)

    def apply_polars(self, col_name: str) -> pl.Expr:
        return pl.col(col_name).map_elements(self._mask_val, return_dtype=pl.Utf8)


class GaussianNoise(BaseRule):
    def __init__(self, std: float = 0.1):
        super().__init__()
        self.std = std
        self.legal_method = "Change of Composition (Method 2)"

    def apply(self, series: pd.Series) -> pd.Series:
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError("GaussianNoise can only be applied to numeric columns")

        noise = np.random.normal(0, series * self.std, size=len(series))
        return series + noise

    def apply_polars(self, col_name: str) -> pl.Expr:
        return pl.col(col_name).map_batches(
            lambda s: s + np.random.normal(0, s.to_numpy() * self.std, size=len(s)),
            return_dtype=pl.Float64,
        )


class Generalize(BaseRule):
    def __init__(self, step: int = 5):
        super().__init__()
        self.step = step
        self.legal_method = "Change of Composition (Method 2)"

    def apply(self, series: pd.Series) -> pd.Series:
        if not pd.api.types.is_numeric_dtype(series):
            raise ValueError("Generalize can only be applied to numeric columns")

        floored = (series // self.step) * self.step
        return floored.astype(str) + "-" + (floored + self.step).astype(str)

    def apply_polars(self, col_name: str) -> pl.Expr:
        floored = (pl.col(col_name) // self.step) * self.step
        return floored.cast(pl.Utf8) + "-" + (floored + self.step).cast(pl.Utf8)
