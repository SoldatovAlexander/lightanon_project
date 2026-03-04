import abc
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