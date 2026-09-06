import re
import secrets
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from .vault import BaseVault, MemoryVault
from .patterns import Patterns
from .organizations import OrganizationProfile


@dataclass(frozen=True)
class SanitizedDocument:
    """Sanitized RAG document and the bounded restoration scope it created."""

    text: str
    metadata: Dict[str, Any]
    token_scope: Dict[str, int]


class TextSanitizer:
    TOKEN_PATTERN = re.compile(r"\[[A-Z][A-Z0-9_]*_[a-f0-9]{8}(?:[a-f0-9]{24})?\]")
    AVAILABLE_RULES: Dict[str, str] = {
        "COUNTERPARTY_REQUISITES": Patterns.COUNTERPARTY_REQUISITES,
        "BUSINESS_REQUISITES": Patterns.BUSINESS_REQUISITES,
        "ORGANIZATION_NAME": Patterns.ORGANIZATION_NAME,
        "COMPANY_INN": Patterns.COMPANY_INN,
        "KPP": Patterns.KPP,
        "OGRN": Patterns.OGRN,
        "OKPO": Patterns.OKPO,
        "LEGAL_ADDRESS": Patterns.LEGAL_ADDRESS,
        "BANK_ACCOUNT": Patterns.BANK_ACCOUNT,
        "CORRESPONDENT_ACCOUNT": Patterns.CORRESPONDENT_ACCOUNT,
        "BIK": Patterns.BIK,
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
    COMPANY_RULE_NAMES: Tuple[str, ...] = (
        "BUSINESS_REQUISITES",
        "ORGANIZATION_NAME",
        "COMPANY_INN",
        "KPP",
        "OGRN",
        "OKPO",
        "LEGAL_ADDRESS",
        "BANK_ACCOUNT",
        "CORRESPONDENT_ACCOUNT",
        "BIK",
    )
    COUNTERPARTY_RULE_NAMES: Tuple[str, ...] = (
        "COUNTERPARTY_REQUISITES",
    )
    BUSINESS_MODES: Tuple[str, ...] = ("none", "company", "company_and_counterparties")
    UNKNOWN_ORGANIZATION_POLICIES: Tuple[str, ...] = ("report", "mask", "reject")

    def __init__(
        self,
        vault: Optional[BaseVault] = None,
        enabled_rules: Optional[Iterable[str]] = None,
        rules: Optional[List[Tuple[str, str]]] = None,
        profile: str = "basic",
        business_mode: str = "none",
        organization_profiles: Optional[Iterable[OrganizationProfile]] = None,
        unknown_organization_policy: str = "report",
    ):
        """
        Initialize the RAG Sanitizer.
        :param vault: Storage backend. Defaults to MemoryVault.
        :param enabled_rules: Built-in rule names to enable. Defaults to DEFAULT_RULE_NAMES.
        :param rules: Explicit rule list as (entity_type, regex pattern) tuples.
        :param profile: Built-in rule profile. One of: basic, ru_152, ru_152_strict.
        :param business_mode: Organization-requisites mode: none, company, company_and_counterparties.
        :param organization_profiles: Known organizations and their document roles.
        :param unknown_organization_policy: report, mask, or reject for organizations not in profiles.
        """
        self.vault = vault if vault else MemoryVault()
        self.organization_profiles = self._validate_organization_profiles(organization_profiles)
        self.unknown_organization_policy = self._validate_unknown_organization_policy(unknown_organization_policy)
        self.business_mode = business_mode.lower()

        # Priority matters: Specific patterns first (Email), generic last (Names)
        if rules is not None:
            self.rules = [(self._normalize_entity_type(name), pattern) for name, pattern in rules]
        else:
            selected_rules = enabled_rules if enabled_rules is not None else self._rules_for_profile(profile)
            self.rules = self._rules_with_organization_profiles(selected_rules, business_mode)

    def _validate_organization_profiles(
        self, organization_profiles: Optional[Iterable[OrganizationProfile]]
    ) -> Tuple[OrganizationProfile, ...]:
        if organization_profiles is None:
            return ()
        profiles = tuple(organization_profiles)
        if any(not isinstance(profile, OrganizationProfile) for profile in profiles):
            raise ValueError("organization_profiles must contain OrganizationProfile instances")
        return profiles

    def _validate_unknown_organization_policy(self, policy: str) -> str:
        if policy not in self.UNKNOWN_ORGANIZATION_POLICIES:
            raise ValueError(f"Unknown organization policy: {policy}")
        return policy

    def _rules_with_organization_profiles(
        self, selected_rules: Iterable[str], business_mode: str
    ) -> List[Tuple[str, str]]:
        mode = business_mode.lower()
        if mode not in self.BUSINESS_MODES:
            raise ValueError(f"Unknown business mode: {business_mode}")
        if not self.organization_profiles or mode == "none":
            return self._build_rules(self._apply_business_mode(selected_rules, mode))

        base_rules = tuple(selected_rules)
        profile_rules = self._organization_profile_rules(mode)
        if self.unknown_organization_policy == "mask":
            base_rules = self._apply_business_mode(base_rules, mode)
        return profile_rules + self._build_rules(base_rules)

    def _organization_profile_rules(self, business_mode: str) -> List[Tuple[str, str]]:
        allowed_roles = {"company"} if business_mode == "company" else {"company", "counterparty"}
        rules = []
        for profile in self.organization_profiles:
            if profile.role not in allowed_roles:
                continue
            entity_type = f"ORGANIZATION_{profile.role.upper()}"
            for value in profile.values():
                rules.append((entity_type, self._literal_organization_pattern(value)))
        return rules

    @staticmethod
    def _literal_organization_pattern(value: str) -> str:
        return rf"(?<![A-Za-zА-Яа-яЁё0-9]){re.escape(value)}(?![A-Za-zА-Яа-яЁё0-9])"

    def _rules_for_profile(self, profile: str) -> Tuple[str, ...]:
        profile_name = profile.lower()
        if profile_name not in self.PROFILES:
            raise ValueError(f"Unknown RAG profile: {profile}")
        return self.PROFILES[profile_name]

    def _apply_business_mode(self, rule_names: Iterable[str], business_mode: str) -> Tuple[str, ...]:
        mode = business_mode.lower()
        if mode not in self.BUSINESS_MODES:
            raise ValueError(f"Unknown business mode: {business_mode}")

        business_rules: Tuple[str, ...] = ()
        if mode == "company":
            business_rules = self.COMPANY_RULE_NAMES
        elif mode == "company_and_counterparties":
            business_rules = self.COUNTERPARTY_RULE_NAMES + self.COMPANY_RULE_NAMES

        return self._dedupe_rules(business_rules + tuple(rule_names))

    def _dedupe_rules(self, rule_names: Iterable[str]) -> Tuple[str, ...]:
        result = []
        seen = set()
        for rule_name in rule_names:
            normalized = self._normalize_entity_type(rule_name)
            if normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return tuple(result)

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
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", entity_type):
            raise ValueError("Rule name must start with a letter and contain only alphanumeric characters or underscores")
        return entity_type

    def _make_token(self, entity_type: str) -> str:
        uid = secrets.token_hex(16)
        return f"[{entity_type}_{uid}]"

    def _get_or_create_token(self, entity_type: str, real_value: str) -> str:
        existing_token = self.vault.get_token(entity_type, real_value)
        if existing_token:
            return existing_token

        token = self._make_token(entity_type)
        while self.vault.get_value(token) is not None:
            token = self._make_token(entity_type)
        self.vault.save(token, entity_type, real_value)
        return token

    def sanitize(self, text: str) -> str:
        """
        Replaces PII with reversible tokens.
        Input: "Call Ivan at +7999..."
        Output: "Call [PERSON_a1] at [PHONE_b2]..."
        """
        clean, _ = self.sanitize_with_scope(text)
        return clean

    def sanitize_with_scope(self, text: str) -> Tuple[str, Dict[str, int]]:
        """Sanitize text and return a bounded restoration scope for its tokens."""
        replacements = []
        entities = self._find_entities(text)
        self._reject_unknown_organizations(text, entities)
        for start, end, entity_type, real_value in entities:
            token = self._get_or_create_token(entity_type, real_value)
            replacements.append((start, end, token))

        if not replacements:
            return text, {}

        scope: Dict[str, int] = {}
        for _, _, token in replacements:
            scope[token] = scope.get(token, 0) + 1
        return self._apply_replacements(text, replacements), scope

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
        found_entities = self._find_entities(text)
        self._reject_unknown_organizations(text, found_entities)
        report = self._detection_report(self._counts_from_entities(found_entities))
        unknown_count = self._unknown_organization_count(text, found_entities)
        if unknown_count:
            report["unknown_organizations"] = unknown_count
        return report

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
            "active_rules": before["active_rules"],
            "coverage": before["coverage"],
            "residual_entities": residual_entities,
            "residual_total": sum(residual_entities.values()),
            "residual_coverage": "heuristic",
        }
        return clean, report

    def _entity_counts(self, text: str) -> Dict[str, int]:
        return self._counts_from_entities(self._find_entities(text))

    @staticmethod
    def _counts_from_entities(entities: Iterable[Tuple[int, int, str, str]]) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for _, _, entity_type, _ in entities:
            counts[entity_type] = counts.get(entity_type, 0) + 1
        return counts

    def _unknown_organization_count(self, text: str, entities: List[Tuple[int, int, str, str]]) -> int:
        if not self.organization_profiles or self.business_mode == "none":
            return 0
        protected_spans = [(start, end) for start, end, _, _ in entities if entity_type.startswith("ORGANIZATION_")]
        return sum(
            1
            for _, pattern in self._build_rules(self.COMPANY_RULE_NAMES + self.COUNTERPARTY_RULE_NAMES)
            for match in re.finditer(pattern, text)
            if not self._overlaps_existing_span(*match.span(), protected_spans)
        )

    def _reject_unknown_organizations(self, text: str, entities: List[Tuple[int, int, str, str]]) -> None:
        if self.organization_profiles and self.unknown_organization_policy == "reject" and self._unknown_organization_count(text, entities):
            raise ValueError("Unknown organization detected; add a profile or choose report/mask policy")

    def _detection_report(self, entities: Dict[str, int]) -> Dict[str, object]:
        return {
            "entities": entities,
            "total": sum(entities.values()),
            "active_rules": [entity_type for entity_type, _ in self.rules],
            "coverage": "heuristic",
        }

    def sanitize_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recursively sanitize string values in RAG metadata.
        Non-string scalar values are preserved.
        """
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")
        return self._sanitize_metadata_value(metadata)

    def sanitize_metadata_with_scope(self, metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, int]]:
        """Sanitize metadata and return scope only for replacements made in it."""
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")
        scope: Dict[str, int] = {}
        return self._sanitize_metadata_value_with_scope(metadata, scope), scope

    def deanonymize_metadata(
        self,
        metadata: Dict[str, Any],
        policy: str = "mask",
        allowed_entity_types: Optional[Iterable[str]] = None,
        token_scope: Optional[Mapping[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Recursively deanonymize string values in RAG metadata.
        Non-string scalar values are preserved.
        """
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be a dictionary")
        allowed_types = self._allowed_types(allowed_entity_types)
        scope_counts = self._scope_counts(policy, token_scope)
        return self._deanonymize_metadata_value(metadata, policy, allowed_types, scope_counts)

    def sanitize_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Sanitize RAG document text and metadata with the same vault.
        """
        result = self.sanitize_document_with_scope(text, metadata)
        return result.text, result.metadata

    def sanitize_document_with_scope(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SanitizedDocument:
        """Sanitize text and metadata with one bounded restoration scope."""
        clean_text, text_scope = self.sanitize_with_scope(text)
        clean_metadata, metadata_scope = self.sanitize_metadata_with_scope(metadata or {})
        scope = dict(text_scope)
        for token, count in metadata_scope.items():
            scope[token] = scope.get(token, 0) + count
        return SanitizedDocument(clean_text, clean_metadata, scope)

    def deanonymize_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        policy: str = "mask",
        allowed_entity_types: Optional[Iterable[str]] = None,
        token_scope: Optional[Mapping[str, int]] = None,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Deanonymize RAG document text and metadata with the same policy.
        """
        allowed_types = self._allowed_types(allowed_entity_types)
        scope_counts = self._scope_counts(policy, token_scope)
        restored_text = self._deanonymize_text(text, policy, allowed_types, scope_counts)
        restored_metadata = self._deanonymize_metadata_value(metadata or {}, policy, allowed_types, scope_counts)
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

    def _sanitize_metadata_value_with_scope(self, value: Any, scope: Dict[str, int]) -> Any:
        if isinstance(value, str):
            clean, value_scope = self.sanitize_with_scope(value)
            for token, count in value_scope.items():
                scope[token] = scope.get(token, 0) + count
            return clean
        if isinstance(value, dict):
            return {key: self._sanitize_metadata_value_with_scope(item, scope) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_metadata_value_with_scope(item, scope) for item in value]
        if isinstance(value, tuple):
            return tuple(self._sanitize_metadata_value_with_scope(item, scope) for item in value)
        if isinstance(value, set):
            return {self._sanitize_metadata_value_with_scope(item, scope) for item in value}
        return value

    def _deanonymize_metadata_value(
        self,
        value: Any,
        policy: str,
        allowed_types: Optional[set],
        scope_counts: Optional[Dict[str, int]],
    ) -> Any:
        if isinstance(value, str):
            return self._deanonymize_text(value, policy, allowed_types, scope_counts)
        if isinstance(value, dict):
            return {
                key: self._deanonymize_metadata_value(item, policy, allowed_types, scope_counts)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._deanonymize_metadata_value(item, policy, allowed_types, scope_counts) for item in value]
        if isinstance(value, tuple):
            return tuple(self._deanonymize_metadata_value(item, policy, allowed_types, scope_counts) for item in value)
        if isinstance(value, set):
            return {self._deanonymize_metadata_value(item, policy, allowed_types, scope_counts) for item in value}
        return value

    def deanonymize(
        self,
        text: str,
        policy: str = "mask",
        allowed_entity_types: Optional[Iterable[str]] = None,
        token_scope: Optional[Mapping[str, int]] = None,
    ) -> str:
        """
        Masks tokens by default or restores values within an explicit token scope.
        Input: "Hello [PERSON_a1]"
        Output: "Hello [PERSON]" by default
        """
        allowed_types = self._allowed_types(allowed_entity_types)
        scope_counts = self._scope_counts(policy, token_scope)
        return self._deanonymize_text(text, policy, allowed_types, scope_counts)

    def _allowed_types(self, allowed_entity_types: Optional[Iterable[str]]) -> Optional[set]:
        if allowed_entity_types is None:
            return None
        return {self._normalize_entity_type(entity_type) for entity_type in allowed_entity_types}

    def _scope_counts(
        self,
        policy: str,
        token_scope: Optional[Mapping[str, int]],
    ) -> Optional[Dict[str, int]]:
        if policy not in {"restore", "no_personal_data", "mask", "restore_allowed_only"}:
            raise ValueError(f"Unknown deanonymization policy: {policy}")
        if policy not in {"restore", "restore_allowed_only"}:
            return None
        if token_scope is None:
            raise ValueError("token_scope is required for restoration policies")
        if not isinstance(token_scope, Mapping):
            raise ValueError("token_scope must be a mapping of tokens to positive occurrence counts")

        scope_counts: Dict[str, int] = {}
        for token, count in token_scope.items():
            if not isinstance(token, str) or not self.TOKEN_PATTERN.fullmatch(token):
                raise ValueError("token_scope contains an invalid token")
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise ValueError("token_scope counts must be positive integers")
            scope_counts[token] = count
        return scope_counts

    def _deanonymize_text(
        self,
        text: str,
        policy: str,
        allowed_types: Optional[set],
        scope_counts: Optional[Dict[str, int]],
    ) -> str:
        def replace_token(match: re.Match) -> str:
            token = match.group()
            entity_type = self._entity_type_from_token(token)
            if policy == "no_personal_data":
                return token
            if policy == "mask":
                return f"[{entity_type}]"
            if policy == "restore_allowed_only" and (allowed_types is None or entity_type not in allowed_types):
                return token
            if scope_counts is None or scope_counts.get(token, 0) <= 0:
                return token

            real_value = self.vault.get_value(token)
            if real_value:
                scope_counts[token] -= 1
                return real_value
            return token

        return self.TOKEN_PATTERN.sub(replace_token, text)

    def _entity_type_from_token(self, token: str) -> str:
        return token[1:-1].rsplit("_", 1)[0]
