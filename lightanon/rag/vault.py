import abc
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from cryptography.fernet import Fernet, InvalidToken
from filelock import FileLock


VAULT_FORMAT = "lightanon.file-vault"
VAULT_VERSION = 2
DEFAULT_NAMESPACE = "default"
ENTITY_TYPE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class MappingConflict(ValueError):
    """A token or typed value is already bound to a different mapping."""


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _validate_entity_type(entity_type: str) -> str:
    if not isinstance(entity_type, str) or not ENTITY_TYPE_PATTERN.fullmatch(entity_type):
        raise ValueError("entity_type must match ^[A-Z][A-Z0-9_]*$")
    return entity_type


def _validate_namespace(namespace: str) -> str:
    if not isinstance(namespace, str) or not namespace:
        raise ValueError("namespace must be a non-empty string")
    return namespace


class BaseVault(abc.ABC):
    """Storage backend for reversible RAG tokens."""

    @abc.abstractmethod
    def get_value(self, token: str) -> Optional[str]:
        """Retrieve a real value by token."""

    @abc.abstractmethod
    def get_token(self, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE) -> Optional[str]:
        """Retrieve an existing token by its typed value."""

    @abc.abstractmethod
    def save(self, token: str, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE, ttl_seconds: Optional[int] = None) -> None:
        """Store an immutable token-to-typed-value mapping."""

    @abc.abstractmethod
    def delete_token(self, token: str) -> bool:
        """Delete a mapping by token."""

    @abc.abstractmethod
    def delete_value(self, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE) -> bool:
        """Delete a mapping by typed value."""

    @abc.abstractmethod
    def clear(self) -> None:
        """Delete all mappings."""

    @abc.abstractmethod
    def purge_expired(self) -> int:
        """Delete expired mappings and return their count."""


class _VaultState:
    """Shared typed mapping operations for in-memory and file-backed vaults."""

    default_ttl_seconds: Optional[int]

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _expires_at(self, ttl_seconds: Optional[int]) -> Optional[str]:
        ttl = self.default_ttl_seconds if ttl_seconds is None else ttl_seconds
        if ttl is None:
            return None
        return datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + ttl, timezone.utc).isoformat()

    def _is_expired(self, entry: Dict[str, str]) -> bool:
        expires_at = entry.get("expires_at")
        return bool(expires_at and _parse_timestamp(expires_at) <= datetime.now(timezone.utc))

    @staticmethod
    def _key(entity_type: str, value: str, namespace: str) -> Tuple[str, str, str]:
        _validate_entity_type(entity_type)
        _validate_namespace(namespace)
        if not isinstance(value, str):
            raise ValueError("value must be a string")
        return namespace, entity_type, value

    @staticmethod
    def _reverse_index(entries: Dict[str, Dict[str, str]]) -> Dict[Tuple[str, str, str], str]:
        index = {}
        for token, entry in entries.items():
            key = (entry["namespace"], entry["entity_type"], entry["value"])
            previous = index.setdefault(key, token)
            if previous != token:
                raise MappingConflict("Vault contains duplicate typed values")
        return index

    def _purge_entries(self, entries: Dict[str, Dict[str, str]]) -> int:
        expired = [token for token, entry in entries.items() if self._is_expired(entry)]
        for token in expired:
            del entries[token]
        return len(expired)


class MemoryVault(_VaultState, BaseVault):
    """In-memory typed token storage for a single RAG session."""

    def __init__(self, default_ttl_seconds: Optional[int] = None):
        self.default_ttl_seconds = default_ttl_seconds
        self._entries: Dict[str, Dict[str, str]] = {}

    def _purge(self) -> int:
        return self._purge_entries(self._entries)

    def get_value(self, token: str) -> Optional[str]:
        self._purge()
        entry = self._entries.get(token)
        return entry["value"] if entry else None

    def get_token(self, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE) -> Optional[str]:
        self._purge()
        return self._reverse_index(self._entries).get(self._key(entity_type, value, namespace))

    def save(self, token, entity_type, value, namespace=DEFAULT_NAMESPACE, ttl_seconds=None) -> None:
        if not isinstance(token, str) or not token:
            raise ValueError("token must be a non-empty string")
        self._purge()
        key = self._key(entity_type, value, namespace)
        existing = self._entries.get(token)
        if existing and self._key(existing["entity_type"], existing["value"], existing["namespace"]) != key:
            raise MappingConflict("Token is already bound to another value")
        previous_token = self._reverse_index(self._entries).get(key)
        if previous_token and previous_token != token:
            raise MappingConflict("Typed value is already bound to another token")
        now = self._now()
        if not existing:
            existing = {"entity_type": entity_type, "namespace": namespace, "value": value, "created_at": now}
            self._entries[token] = existing
        existing["last_used_at"] = now
        expires_at = self._expires_at(ttl_seconds)
        if expires_at is not None:
            existing["expires_at"] = expires_at

    def delete_token(self, token: str) -> bool:
        self._purge()
        return self._entries.pop(token, None) is not None

    def delete_value(self, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE) -> bool:
        self._purge()
        token = self._reverse_index(self._entries).get(self._key(entity_type, value, namespace))
        if token is None:
            return False
        del self._entries[token]
        return True

    def clear(self) -> None:
        self._entries.clear()

    def purge_expired(self) -> int:
        return self._purge()


class FileVault(_VaultState, BaseVault):
    """Versioned, lock-protected local storage for reversible RAG tokens."""

    def __init__(self, path: str, default_ttl_seconds: Optional[int] = None, encryption_key: Optional[Union[str, bytes]] = None):
        self.path = Path(path)
        self.default_ttl_seconds = default_ttl_seconds
        self._fernet = self._build_fernet(encryption_key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = FileLock(f"{self.path}.lock")
        with self._lock:
            self._read_entries()

    @staticmethod
    def _build_fernet(encryption_key: Optional[Union[str, bytes]]) -> Optional[Fernet]:
        if encryption_key is None:
            return None
        key = encryption_key.encode("utf-8") if isinstance(encryption_key, str) else encryption_key
        if not isinstance(key, bytes):
            raise ValueError("encryption_key must be a Fernet key as str or bytes")
        try:
            return Fernet(key)
        except (TypeError, ValueError) as exc:
            raise ValueError("encryption_key must be a valid Fernet key") from exc

    @staticmethod
    def _parse_json(raw_data: bytes, error: str) -> dict:
        try:
            data = json.loads(raw_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(error) from exc
        if not isinstance(data, dict):
            raise ValueError(error)
        return data

    def _read_entries(self) -> Dict[str, Dict[str, str]]:
        if not self.path.exists() or self.path.stat().st_size == 0:
            return {}
        outer = self._parse_json(self.path.read_bytes(), f"Invalid vault JSON: {self.path}")
        if self._fernet is not None:
            if outer.get("format") != VAULT_FORMAT or outer.get("version") != VAULT_VERSION or outer.get("encrypted") is not True:
                raise ValueError("Encrypted FileVault requires an encrypted v2 vault")
            ciphertext = outer.get("ciphertext")
            if not isinstance(ciphertext, str):
                raise ValueError("Encrypted FileVault ciphertext must be a string")
            try:
                payload = self._fernet.decrypt(ciphertext.encode("utf-8"))
            except InvalidToken as exc:
                raise ValueError("Unable to decrypt vault with the supplied encryption key") from exc
            data = self._parse_json(payload, "Invalid encrypted vault payload")
        else:
            if outer.get("encrypted") is True:
                raise ValueError("Vault is encrypted; provide an encryption key")
            data = outer
        if data.get("format") != VAULT_FORMAT or data.get("version") != VAULT_VERSION:
            raise ValueError("Unsupported vault format; migrate legacy vault before use")
        entries = data.get("entries")
        if not isinstance(entries, dict):
            raise ValueError("Vault field 'entries' must be an object")
        validated = {}
        for token, entry in entries.items():
            if not isinstance(token, str) or not token or not isinstance(entry, dict):
                raise ValueError("Vault entries must map non-empty tokens to objects")
            entity_type = entry.get("entity_type")
            namespace = entry.get("namespace")
            value = entry.get("value")
            self._key(entity_type, value, namespace)
            normalized = {"entity_type": entity_type, "namespace": namespace, "value": value}
            for timestamp in ("created_at", "last_used_at"):
                if not isinstance(entry.get(timestamp), str):
                    raise ValueError(f"Vault entry {timestamp} must be a string")
                _parse_timestamp(entry[timestamp])
                normalized[timestamp] = entry[timestamp]
            expires_at = entry.get("expires_at")
            if expires_at is not None:
                if not isinstance(expires_at, str):
                    raise ValueError("Vault entry expires_at must be a string or null")
                _parse_timestamp(expires_at)
                normalized["expires_at"] = expires_at
            validated[token] = normalized
        self._reverse_index(validated)
        return validated

    def _write_entries(self, entries: Dict[str, Dict[str, str]]) -> None:
        payload = {"format": VAULT_FORMAT, "version": VAULT_VERSION, "entries": entries}
        payload_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        if self._fernet is not None:
            envelope = {"format": VAULT_FORMAT, "version": VAULT_VERSION, "encrypted": True, "ciphertext": self._fernet.encrypt(payload_bytes).decode("utf-8")}
            payload_bytes = json.dumps(envelope, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"
        tmp_name = None
        try:
            with tempfile.NamedTemporaryFile("wb", delete=False, dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp") as temp_file:
                tmp_name = temp_file.name
                os.chmod(tmp_name, 0o600)
                temp_file.write(payload_bytes)
            os.replace(tmp_name, self.path)
        finally:
            if tmp_name and os.path.exists(tmp_name):
                os.unlink(tmp_name)

    def _read_and_purge(self) -> Tuple[Dict[str, Dict[str, str]], int]:
        entries = self._read_entries()
        return entries, self._purge_entries(entries)

    def get_value(self, token: str) -> Optional[str]:
        with self._lock:
            entries, purged = self._read_and_purge()
            if purged:
                self._write_entries(entries)
            entry = entries.get(token)
            return entry["value"] if entry else None

    def get_token(self, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE) -> Optional[str]:
        with self._lock:
            entries, purged = self._read_and_purge()
            if purged:
                self._write_entries(entries)
            return self._reverse_index(entries).get(self._key(entity_type, value, namespace))

    def save(self, token, entity_type, value, namespace=DEFAULT_NAMESPACE, ttl_seconds=None) -> None:
        if not isinstance(token, str) or not token:
            raise ValueError("token must be a non-empty string")
        with self._lock:
            entries, _ = self._read_and_purge()
            key = self._key(entity_type, value, namespace)
            existing = entries.get(token)
            if existing and self._key(existing["entity_type"], existing["value"], existing["namespace"]) != key:
                raise MappingConflict("Token is already bound to another value")
            previous_token = self._reverse_index(entries).get(key)
            if previous_token and previous_token != token:
                raise MappingConflict("Typed value is already bound to another token")
            now = self._now()
            if not existing:
                existing = {"entity_type": entity_type, "namespace": namespace, "value": value, "created_at": now}
                entries[token] = existing
            existing["last_used_at"] = now
            expires_at = self._expires_at(ttl_seconds)
            if expires_at is not None:
                existing["expires_at"] = expires_at
            self._write_entries(entries)

    def delete_token(self, token: str) -> bool:
        with self._lock:
            entries, purged = self._read_and_purge()
            deleted = entries.pop(token, None) is not None
            if deleted or purged:
                self._write_entries(entries)
            return deleted

    def delete_value(self, entity_type: str, value: str, namespace: str = DEFAULT_NAMESPACE) -> bool:
        with self._lock:
            entries, purged = self._read_and_purge()
            token = self._reverse_index(entries).get(self._key(entity_type, value, namespace))
            if token is None:
                if purged:
                    self._write_entries(entries)
                return False
            del entries[token]
            self._write_entries(entries)
            return True

    def clear(self) -> None:
        with self._lock:
            self._write_entries({})

    def purge_expired(self) -> int:
        with self._lock:
            entries, purged = self._read_and_purge()
            if purged:
                self._write_entries(entries)
            return purged

    def stats(self) -> Dict[str, object]:
        with self._lock:
            entries, purged = self._read_and_purge()
            if purged:
                self._write_entries(entries)
            by_type: Dict[str, int] = {}
            for entry in entries.values():
                entity_type = entry["entity_type"]
                by_type[entity_type] = by_type.get(entity_type, 0) + 1
            return {"path": str(self.path), "total": len(entries), "by_type": by_type, "has_timestamps": bool(entries), "has_expiration": any("expires_at" in entry for entry in entries.values())}


def migrate_legacy_file_vault(source_path: str, destination_path: str, encryption_key: Union[str, bytes]) -> int:
    """Convert a legacy plaintext FileVault into an encrypted v2 vault without touching the source."""
    source = Path(source_path)
    destination = Path(destination_path)
    if source.resolve(strict=False) == destination.resolve(strict=False):
        raise ValueError("source and destination vault paths must be different")
    if not source.exists():
        raise ValueError(f"Legacy vault does not exist: {source}")
    if destination.exists():
        raise ValueError(f"Migration destination already exists: {destination}")

    try:
        legacy = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid legacy vault JSON: {source}") from exc
    if not isinstance(legacy, dict) or legacy.get("encrypted") is True:
        raise ValueError("Migration source must be a plaintext legacy vault")

    legacy_entries = legacy.get("entries")
    token_to_value = legacy.get("token_to_value", {})
    if legacy_entries is not None and not isinstance(legacy_entries, dict):
        raise ValueError("Legacy vault entries must be an object")
    if not isinstance(token_to_value, dict):
        raise ValueError("Legacy vault token_to_value must be an object")

    records = {}
    for token, value in token_to_value.items():
        records[token] = {"value": value}
    for token, entry in (legacy_entries or {}).items():
        if not isinstance(entry, dict):
            raise ValueError("Legacy vault entries must map tokens to objects")
        records[token] = entry

    token_pattern = re.compile(r"^\[([A-Z][A-Z0-9_]*)_[a-f0-9]{8}(?:[a-f0-9]{24})?\]$")
    now = datetime.now(timezone.utc).isoformat()
    converted = {}
    for token, record in records.items():
        match = token_pattern.fullmatch(token) if isinstance(token, str) else None
        value = record.get("value") if isinstance(record, dict) else None
        if not match or not isinstance(value, str):
            raise ValueError("Legacy vault contains an invalid token or value")
        created_at = record.get("created_at", now)
        last_used_at = record.get("last_used_at", created_at)
        expires_at = record.get("expires_at")
        if not isinstance(created_at, str) or not isinstance(last_used_at, str) or (expires_at is not None and not isinstance(expires_at, str)):
            raise ValueError("Legacy vault contains invalid timestamps")
        _parse_timestamp(created_at)
        _parse_timestamp(last_used_at)
        if expires_at is not None:
            _parse_timestamp(expires_at)
        converted[token] = {"entity_type": match.group(1), "namespace": DEFAULT_NAMESPACE, "value": value, "created_at": created_at, "last_used_at": last_used_at}
        if expires_at is not None:
            converted[token]["expires_at"] = expires_at

    FileVault._reverse_index(converted)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_lock = FileLock(f"{destination}.lock")
    temporary_path = None
    temporary_lock_path = None
    try:
        with destination_lock:
            fd, temporary_path = tempfile.mkstemp(dir=destination.parent, prefix=f".{destination.name}.migration-", suffix=".tmp")
            os.close(fd)
            temporary_lock_path = f"{temporary_path}.lock"
            temporary_vault = FileVault(temporary_path, encryption_key=encryption_key)
            temporary_vault._write_entries(converted)
            os.replace(temporary_path, destination)
            temporary_path = None
        verified = FileVault(str(destination), encryption_key=encryption_key)
        for token, entry in converted.items():
            if verified.get_value(token) != entry["value"]:
                raise ValueError("Migrated vault verification failed")
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.unlink(temporary_path)
        if temporary_lock_path and os.path.exists(temporary_lock_path):
            os.unlink(temporary_lock_path)
    return len(converted)
