import re
import uuid
from typing import Dict, Iterable, List, Optional, Tuple
from .vault import BaseVault, MemoryVault
from .patterns import Patterns


class TextSanitizer:
    AVAILABLE_RULES: Dict[str, str] = {
        "ONLINE_ACCOUNT": "|".join(
            [
                Patterns.ONLINE_ACCOUNT_RU,
                Patterns.ONLINE_ACCOUNT_EN,
                Patterns.RESOURCE_ACCOUNT,
            ]
        ),
        "PROFILE_URL": Patterns.PROFILE_URL,
        "SOCIAL_HANDLE": Patterns.SOCIAL_HANDLE,
        "USERNAME": Patterns.USERNAME,
        "IP_ADDRESS": Patterns.IP_ADDRESS,
        "COOKIE_ID": Patterns.COOKIE_ID,
        "DEVICE_ID": Patterns.DEVICE_ID,
        "USER_ID": Patterns.USER_ID,
        "EMAIL": Patterns.EMAIL,
        "PHONE": Patterns.PHONE_RU,
        "PASSPORT": Patterns.PASSPORT_RU,
        "SNILS": Patterns.SNILS,
        "INN": Patterns.INN,
        "CARD": Patterns.CREDIT_CARD,
        "PERSON": Patterns.NAME_RU_BROAD,
    }
    DEFAULT_RULE_NAMES: Tuple[str, ...] = (
        "EMAIL",
        "PHONE",
        "PASSPORT",
        "SNILS",
        "CARD",
        "PERSON",
    )
    PROFILES: Dict[str, Tuple[str, ...]] = {
        "basic": DEFAULT_RULE_NAMES,
        "ru_152": (
            "EMAIL",
            "PHONE",
            "PASSPORT",
            "SNILS",
            "INN",
            "CARD",
            "PERSON",
            "ONLINE_ACCOUNT",
            "PROFILE_URL",
            "SOCIAL_HANDLE",
            "USERNAME",
        ),
        "ru_152_strict": (
            "EMAIL",
            "PHONE",
            "PASSPORT",
            "SNILS",
            "INN",
            "CARD",
            "PERSON",
            "ONLINE_ACCOUNT",
            "PROFILE_URL",
            "SOCIAL_HANDLE",
            "USERNAME",
            "IP_ADDRESS",
            "COOKIE_ID",
            "DEVICE_ID",
            "USER_ID",
        ),
    }

    def __init__(
        self,
        vault: Optional[BaseVault] = None,
        enabled_rules: Optional[Iterable[str]] = None,
        rules: Optional[List[Tuple[str, str]]] = None,
        profile: str = "basic",
    ):
        """
        Initialize the RAG Sanitizer.
        :param vault: Storage backend. Defaults to MemoryVault.
        :param enabled_rules: Built-in rule names to enable. Defaults to DEFAULT_RULE_NAMES.
        :param rules: Explicit rule list as (entity_type, regex pattern) tuples.
        :param profile: Built-in rule profile. One of: basic, ru_152, ru_152_strict.
        """
        self.vault = vault if vault else MemoryVault()

        # Priority matters: Specific patterns first (Email), generic last (Names)
        if rules is not None:
            self.rules = [(self._normalize_entity_type(name), pattern) for name, pattern in rules]
        else:
            selected_rules = enabled_rules if enabled_rules is not None else self._rules_for_profile(profile)
            self.rules = self._build_rules(selected_rules)

    def _rules_for_profile(self, profile: str) -> Tuple[str, ...]:
        profile_name = profile.lower()
        if profile_name not in self.PROFILES:
            raise ValueError(f"Unknown RAG profile: {profile}")
        return self.PROFILES[profile_name]

    def _build_rules(self, enabled_rules: Iterable[str]) -> List[Tuple[str, str]]:
        rules = []
        for name in enabled_rules:
            entity_type = self._normalize_entity_type(name)
            if entity_type not in self.AVAILABLE_RULES:
                raise ValueError(f"Unknown built-in RAG rule: {name}")
            rules.append((entity_type, self.AVAILABLE_RULES[entity_type]))
        return rules

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
        replacements = []
        occupied_spans = []

        for entity_type, pattern in self.rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                if start == end or self._overlaps_existing_span(start, end, occupied_spans):
                    continue
                real_value = match.group()
                token = self._get_or_create_token(entity_type, real_value)
                replacements.append((start, end, token))
                occupied_spans.append((start, end))

        if not replacements:
            return text

        sanitized_parts = []
        current_pos = 0
        for start, end, token in sorted(replacements):
            sanitized_parts.append(text[current_pos:start])
            sanitized_parts.append(token)
            current_pos = end
        sanitized_parts.append(text[current_pos:])

        return "".join(sanitized_parts)

    def _overlaps_existing_span(self, start: int, end: int, spans: List[Tuple[int, int]]) -> bool:
        return any(start < existing_end and existing_start < end for existing_start, existing_end in spans)

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
