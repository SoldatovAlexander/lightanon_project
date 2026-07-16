import abc
import json
import os
import tempfile
from datetime import datetime, timezone
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

    @abc.abstractmethod
    def delete_token(self, token: str) -> bool:
        """Delete mapping by token."""
        pass

    @abc.abstractmethod
    def delete_value(self, value: str) -> bool:
        """Delete mapping by real value."""
        pass

    @abc.abstractmethod
    def clear(self) -> None:
        """Delete all mappings."""
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

    def delete_token(self, token: str) -> bool:
        value = self._token_to_val.pop(token, None)
        if value is None:
            return False
        self._val_to_token.pop(value, None)
        return True

    def delete_value(self, value: str) -> bool:
        token = self._val_to_token.pop(value, None)
        if token is None:
            return False
        self._token_to_val.pop(token, None)
        return True

    def clear(self) -> None:
        self._token_to_val.clear()
        self._val_to_token.clear()


class FileVault(BaseVault):
    """
    JSON-backed token storage for CLI and small local RAG workflows.
    """
    def __init__(self, path: str):
        self.path = Path(path)
        self._token_to_val: Dict[str, str] = {}
        self._val_to_token: Dict[str, str] = {}
        self._token_metadata: Dict[str, Dict[str, str]] = {}
        self._load()

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

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

        entries = data.get("entries")
        if entries is not None:
            self._load_entries(entries)
            return

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
        now = self._now()
        self._token_metadata = {
            token: {"created_at": now, "last_used_at": now}
            for token in self._token_to_val
        }

    def _load_entries(self, entries: Dict[str, object]) -> None:
        if not isinstance(entries, dict):
            raise ValueError("Vault field 'entries' must be an object")

        for token, entry in entries.items():
            if not isinstance(token, str) or not isinstance(entry, dict):
                raise ValueError("Vault field 'entries' must map string tokens to objects")
            value = entry.get("value")
            created_at = entry.get("created_at")
            last_used_at = entry.get("last_used_at")
            if not isinstance(value, str):
                raise ValueError("Vault entry value must be a string")
            if created_at is not None and not isinstance(created_at, str):
                raise ValueError("Vault entry created_at must be a string")
            if last_used_at is not None and not isinstance(last_used_at, str):
                raise ValueError("Vault entry last_used_at must be a string")

            now = self._now()
            self._token_to_val[token] = value
            self._val_to_token[value] = token
            self._token_metadata[token] = {
                "created_at": created_at or now,
                "last_used_at": last_used_at or created_at or now,
            }

    def _validate_mapping(self, mapping: Dict[str, str], field_name: str) -> Dict[str, str]:
        for key, value in mapping.items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise ValueError(f"Vault field '{field_name}' must contain only string keys and values")
        return dict(mapping)

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        entries = {
            token: {
                "value": value,
                **self._token_metadata.get(token, {}),
            }
            for token, value in self._token_to_val.items()
        }
        data = {
            "token_to_value": self._token_to_val,
            "value_to_token": self._val_to_token,
            "entries": entries,
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
        value = self._token_to_val.get(token)
        if value is not None:
            self._touch(token)
        return value

    def get_token(self, value: str) -> Optional[str]:
        token = self._val_to_token.get(value)
        if token is not None:
            self._touch(token)
        return token

    def save(self, token: str, value: str) -> None:
        now = self._now()
        self._token_to_val[token] = value
        self._val_to_token[value] = token
        self._token_metadata.setdefault(token, {"created_at": now})
        self._token_metadata[token]["last_used_at"] = now
        self._flush()

    def _touch(self, token: str) -> None:
        if token not in self._token_metadata:
            now = self._now()
            self._token_metadata[token] = {"created_at": now, "last_used_at": now}
        else:
            self._token_metadata[token]["last_used_at"] = self._now()
        self._flush()

    def delete_token(self, token: str) -> bool:
        value = self._token_to_val.pop(token, None)
        if value is None:
            return False
        self._val_to_token.pop(value, None)
        self._token_metadata.pop(token, None)
        self._flush()
        return True

    def delete_value(self, value: str) -> bool:
        token = self._val_to_token.pop(value, None)
        if token is None:
            return False
        self._token_to_val.pop(token, None)
        self._token_metadata.pop(token, None)
        self._flush()
        return True

    def clear(self) -> None:
        self._token_to_val.clear()
        self._val_to_token.clear()
        self._token_metadata.clear()
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
            "has_timestamps": bool(self._token_metadata),
        }
