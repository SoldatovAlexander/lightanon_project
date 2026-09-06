from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class OrganizationProfile:
    """Known organization values and the role they have in a RAG document."""

    role: str
    full_name: str
    short_names: Tuple[str, ...] = ()
    aliases: Tuple[str, ...] = ()
    inn: Optional[str] = None
    kpp: Optional[str] = None
    ogrn: Optional[str] = None
    ogrnip: Optional[str] = None
    okpo: Optional[str] = None
    legal_address: Optional[str] = None
    bank_accounts: Tuple[str, ...] = ()
    correspondent_accounts: Tuple[str, ...] = ()
    bik: Optional[str] = None

    def __post_init__(self) -> None:
        if self.role not in {"company", "counterparty"}:
            raise ValueError("OrganizationProfile role must be 'company' or 'counterparty'")
        if not isinstance(self.full_name, str) or not self.full_name.strip():
            raise ValueError("OrganizationProfile full_name must be a non-empty string")
        for field_name in ("short_names", "aliases", "bank_accounts", "correspondent_accounts"):
            values = getattr(self, field_name)
            if isinstance(values, str):
                raise ValueError(f"OrganizationProfile {field_name} must contain non-empty strings")
            try:
                normalized_values = tuple(values)
            except TypeError as exc:
                raise ValueError(f"OrganizationProfile {field_name} must contain non-empty strings") from exc
            if any(not isinstance(value, str) or not value.strip() for value in normalized_values):
                raise ValueError(f"OrganizationProfile {field_name} must contain non-empty strings")
            object.__setattr__(self, field_name, normalized_values)
        for field_name in ("inn", "kpp", "ogrn", "ogrnip", "okpo", "legal_address", "bik"):
            value = getattr(self, field_name)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"OrganizationProfile {field_name} must be a non-empty string or None")

    def values(self) -> Tuple[str, ...]:
        """Return unique known values, longest first to keep matching span-safe."""
        values = (
            self.full_name,
            *self.short_names,
            *self.aliases,
            self.inn,
            self.kpp,
            self.ogrn,
            self.ogrnip,
            self.okpo,
            self.legal_address,
            *self.bank_accounts,
            *self.correspondent_accounts,
            self.bik,
        )
        return tuple(sorted({value for value in values if value}, key=len, reverse=True))
