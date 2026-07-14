import abc
import json
import os
import tempfile
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

        try:
            with self.path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid vault JSON: {self.path}") from exc

        if not isinstance(data, dict):
            raise ValueError("Vault JSON must be an object")

        token_to_value = data.get("token_to_value", {})
        value_to_token = data.get("value_to_token")
        if not isinstance(token_to_value, dict):
            raise ValueError("Vault field 'token_to_value' must be an object")
        if value_to_token is not None and not isinstance(value_to_token, dict):
            raise ValueError("Vault field 'value_to_token' must be an object")

        self._token_to_val = self._validate_mapping(token_to_value, "token_to_value")
        if value_to_token is None:
            self._val_to_token = {value: token for token, value in self._token_to_val.items()}
        else:
            self._val_to_token = self._validate_mapping(value_to_token, "value_to_token")

    def _validate_mapping(self, mapping: Dict[str, str], field_name: str) -> Dict[str, str]:
        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"Vault field '{field_name}' must contain only string keys and values")
        return dict(mapping)

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "token_to_value": self._token_to_val,
            "value_to_token": self._val_to_token,
        }
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                delete=False,
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
            ) as f:
                tmp_name = f.name
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp_name, self.path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def get_value(self, token: str) -> Optional[str]:
        return self._token_to_val.get(token)

    def get_token(self, value: str) -> Optional[str]:
        return self._val_to_token.get(value)

    def save(self, token: str, value: str) -> None:
        self._token_to_val[token] = value
        self._val_to_token[value] = token
        self._flush()

    def stats(self) -> Dict[str, object]:
        by_type: Dict[str, int] = {}
        for token in self._token_to_val:
            if token.startswith("[") and token.endswith("]") and "_" in token:
                entity_type = token[1:-1].rsplit("_", 1)[0]
            else:
                entity_type = "UNKNOWN"
            by_type[entity_type] = by_type.get(entity_type, 0) + 1
        return {
            "path": str(self.path),
            "total": len(self._token_to_val),
            "by_type": by_type,
        }
