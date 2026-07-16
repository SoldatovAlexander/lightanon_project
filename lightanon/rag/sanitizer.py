import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple
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
        for start, end, entity_type, real_value in self._find_entities(text):
            token = self._get_or_create_token(entity_type, real_value)
            replacements.append((start, end, token))

        if not replacements:
            return text

        return self._apply_replacements(text, replacements)

    def _find_entities(self, text: str) -> List[Tuple[int, int, str, str]]:
        replacements = []
        occupied_spans = []

        for entity_type, pattern in self.rules:
            for match in re.finditer(pattern, text):
                start, end = match.span()
                if start == end or self._overlaps_existing_span(start, end, occupied_spans):
                    continue
                real_value = match.group()
                replacements.append((start, end, entity_type, real_value))
                occupied_spans.append((start, end))

        return replacements

    def _apply_replacements(self, text: str, replacements: List[Tuple[int, int, str]]) -> str:
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

    def scan(self, text: str) -> Dict[str, object]:
        """
        Detect entities without modifying text or writing to the vault.
        """
        entities = self._entity_counts(text)
        return {
            "entities": entities,
            "total": sum(entities.values()),
            "residual_risk": self._risk_level(entities),
        }

    def sanitize_with_report(self, text: str) -> Tuple[str, Dict[str, object]]:
        """
        Sanitize text and report entities detected before and after sanitization.
        """
        before = self.scan(text)
        clean = self.sanitize(text)
        residual_entities = self._entity_counts(clean)
        report = {
            "entities": before["entities"],
            "total": before["total"],
            "residual_entities": residual_entities,
            "residual_total": sum(residual_entities.values()),
            "residual_risk": self._risk_level(residual_entities),
        }
        return clean, report

    def _entity_counts(self, text: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for _, _, entity_type, _ in self._find_entities(text):
            counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts

    def _risk_level(self, entities: Dict[str, int]) -> str:
        total = sum(entities.values())
        if total == 0:
            return "low"
        if total <= 2:
            return "medium"
        return "high"

    def sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize string values in RAG metadata.
        Non-string scalar values are preserved.
        """
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")
        return self._sanitize_metadata_value(metadata)

    def deanonymize_metadata(
        self,
        metadata: Dict[str, Any],
        policy: str = "restore",
        allowed_entity_types: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        """
        Recursively deanonymize string values in RAG metadata.
        Non-string scalar values are preserved.
        """
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")
        return self._deanonymize_metadata_value(metadata, policy, allowed_entity_types)

    def sanitize_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Sanitize RAG document text and metadata with the same vault.
        """
        clean_text = self.sanitize(text)
        clean_metadata = self.sanitize_metadata(metadata or {})
        return clean_text, clean_metadata

    def deanonymize_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        policy: str = "restore",
        allowed_entity_types: Optional[Iterable[str]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Deanonymize RAG document text and metadata with the same policy.
        """
        restored_text = self.deanonymize(text, policy=policy, allowed_entity_types=allowed_entity_types)
        restored_metadata = self.deanonymize_metadata(
            metadata or {},
            policy=policy,
            allowed_entity_types=allowed_entity_types,
        )
        return restored_text, restored_metadata

    def _sanitize_metadata_value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.sanitize(value)
        if isinstance(value, dict):
            return {key: self._sanitize_metadata_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_metadata_value(item) for item in value]
        if isinstance(value, tuple):
            return tuple(self._sanitize_metadata_value(item) for item in value)
        if isinstance(value, set):
            return {self._sanitize_metadata_value(item) for item in value}
        return value

    def _deanonymize_metadata_value(
        self,
        value: Any,
        policy: str,
        allowed_entity_types: Optional[Iterable[str]],
    ) -> Any:
        if isinstance(value, str):
            return self.deanonymize(value, policy=policy, allowed_entity_types=allowed_entity_types)
        if isinstance(value, dict):
            return {
                key: self._deanonymize_metadata_value(item, policy, allowed_entity_types)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._deanonymize_metadata_value(item, policy, allowed_entity_types) for item in value]
        if isinstance(value, tuple):
            return tuple(self._deanonymize_metadata_value(item, policy, allowed_entity_types) for item in value)
        if isinstance(value, set):
            return {self._deanonymize_metadata_value(item, policy, allowed_entity_types) for item in value}
        return value

    def deanonymize(
        self,
        text: str,
        policy: str = "restore",
        allowed_entity_types: Optional[Iterable[str]] = None,
    ) -> str:
        """
        Restores real data from tokens.
        Input: "Hello [PERSON_a1]"
        Output: "Hello Ivan"
        """
        allowed_types = None
        if allowed_entity_types is not None:
            allowed_types = {self._normalize_entity_type(entity_type) for entity_type in allowed_entity_types}
        if policy not in {"restore", "no_personal_data", "mask", "restore_allowed_only"}:
            raise ValueError(f"Unknown deanonymization policy: {policy}")

        restored_text = text
        # Regex to find our tokens: [TYPE_hexcode]
        token_pattern = r'\[[A-Z][A-Z0-9_]*_[a-f0-9]{8}\]'

        matches = list(set(re.findall(token_pattern, text)))

        for token in matches:
            entity_type = self._entity_type_from_token(token)
            if policy == "no_personal_data":
                continue
            if policy == "mask":
                restored_text = restored_text.replace(token, f"[{entity_type}]")
                continue
            if policy == "restore_allowed_only" and (allowed_types is None or entity_type not in allowed_types):
                continue

            real_value = self.vault.get_value(token)
            if real_value:
                restored_text = restored_text.replace(token, real_value)

        return restored_text

    def _entity_type_from_token(self, token: str) -> str:
        return token[1:-1].rsplit("_", 1)[0]
