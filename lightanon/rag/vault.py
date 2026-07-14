import abc
import json
from pathlib import Path
from typing import Dict, Optional

class BaseVault(abc.ABC):
    """
    Abstract base class for Token Storage.
    In production, implement this using Redis or a Database.
    """
    @abc.abstractmethod
    def get_value(self, token: str) -> Optional[str]:
        """Retrieve real value by token."""
        pass

    @abc.abstractmethod
    def get_token(self, value: str) -> Optional[str]:
        """Retrieve existing token by real value (to keep consistency)."""
        pass

    @abc.abstractmethod
    def save(self, token: str, value: str) -> None:
        """Store a new mapping."""
        pass

class MemoryVault(BaseVault):
    """
    Simple in-memory storage (Dict).
    Fast, but non-persistent. Good for single-session RAG.
    """
    def __init__(self):
        self._token_to_val: Dict[str, str] = {}
        self._val_to_token: Dict[str, str] = {}

    def get_value(self, token: str) -> Optional[str]:
        return self._token_to_val.get(token)

    def get_token(self, value: str) -> Optional[str]:
        return self._val_to_token.get(value)

    def save(self, token: str, value: str) -> None:
        self._token_to_val[token] = value
        self._val_to_token[value] = token


class FileVault(BaseVault):
    """
    JSON-backed token storage for CLI and small local RAG workflows.
    """
    def __init__(self, path: str):
        self.path = Path(path)
        self._token_to_val: Dict[str, str] = {}
        self._val_to_token: Dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return

        with self.path.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self._token_to_val = dict(data.get("token_to_value", {}))
        self._val_to_token = dict(data.get("value_to_token", {}))

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "token_to_value": self._token_to_val,
            "value_to_token": self._val_to_token,
        }
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_value(self, token: str) -> Optional[str]:
        return self._token_to_val.get(token)

    def get_token(self, value: str) -> Optional[str]:
        return self._val_to_token.get(value)

    def save(self, token: str, value: str) -> None:
        self._token_to_val[token] = value
        self._val_to_token[value] = token
        self._flush()
