import re
import uuid
from typing import List, Tuple, Optional
from .vault import BaseVault, MemoryVault
from .patterns import Patterns


class TextSanitizer:
    def __init__(self, vault: Optional[BaseVault] = None):
        """
        Initialize the RAG Sanitizer.
        :param vault: Storage backend. Defaults to MemoryVault.
        """
        self.vault = vault if vault else MemoryVault()

        # Priority matters: Specific patterns first (Email), generic last (Names)
        self.rules: List[Tuple[str, str]] = [
            ("EMAIL", Patterns.EMAIL),
            ("PHONE", Patterns.PHONE_RU),
            ("PASSPORT", Patterns.PASSPORT_RU),
            ("SNILS", Patterns.SNILS),
            ("CARD", Patterns.CREDIT_CARD),
            ("PERSON", Patterns.NAME_RU_BROAD),
        ]

    def add_rule(self, name: str, pattern: str):
        """Add a custom regex rule."""
        self.rules.insert(0, (self._normalize_entity_type(name), pattern))

    def _normalize_entity_type(self, name: str) -> str:
        entity_type = re.sub(r"[^A-Z0-9_]", "_", name.upper()).strip("_")
        if not entity_type:
            raise ValueError("Rule name must contain at least one alphanumeric character")
        return entity_type

    def _make_token(self, entity_type: str) -> str:
        uid = str(uuid.uuid4())[:8]
        return f"[{entity_type}_{uid}]"

    def _get_or_create_token(self, entity_type: str, real_value: str) -> str:
        existing_token = self.vault.get_token(real_value)
        if existing_token:
            return existing_token

        token = self._make_token(entity_type)
        self.vault.save(token, real_value)
        return token

    def sanitize(self, text: str) -> str:
        """
        Replaces PII with reversible tokens.
        Input: "Call Ivan at +7999..."
        Output: "Call [PERSON_a1] at [PHONE_b2]..."
        """
        sanitized_text = text

        for entity_type, pattern in self.rules:
            # Find all matches
            matches = list(re.finditer(pattern, text))

            for match in matches:
                real_value = match.group()
                token = self._get_or_create_token(entity_type, real_value)

                # Replace in text
                # Note: This is a simple string replacement.
                # For huge docs, consider single-pass replacement, but for RAG chunks this is fine.
                sanitized_text = sanitized_text.replace(real_value, token)

        return sanitized_text

    def deanonymize(self, text: str) -> str:
        """
        Restores real data from tokens.
        Input: "Hello [PERSON_a1]"
        Output: "Hello Ivan"
        """
        restored_text = text
        # Regex to find our tokens: [TYPE_hexcode]
        token_pattern = r'\[[A-Z][A-Z0-9_]*_[a-f0-9]{8}\]'

        matches = list(set(re.findall(token_pattern, text)))

        for token in matches:
            real_value = self.vault.get_value(token)
            if real_value:
                restored_text = restored_text.replace(token, real_value)

        return restored_text
