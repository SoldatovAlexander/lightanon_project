"""
Pre-defined regex patterns for PII detection.
Optimized for Russian (152-FZ) and International standards.
"""


class Patterns:
    # --- COMMUNICATIONS ---
    # Email: standard pattern
    EMAIL = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    # Phone (RU): Matches +7, 8, with brackets or dashes.
    # Ex: +7 (999) 123-45-67, 89991234567
    PHONE_RU = r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'

    # --- DOCUMENTS (RUSSIA) ---
    # Passport RF: Series (4 digits) + Number (6 digits)
    # Ex: 45 00 123456, 4500 123456
    PASSPORT_RU = r'\b\d{2}[\s\-]?\d{2}[\s\-]?\d{6}\b'

    # SNILS: 11 digits, often 123-456-789 00
    SNILS = r'\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b'

    # INN (Tax ID): 10 or 12 digits
    INN = r'\b\d{10}\b|\b\d{12}\b'

    # --- FINANCE ---
    # Credit Card: 13-19 digits, potentially grouped
    CREDIT_CARD = r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'

    # --- NAMES (HEURISTIC) ---
    # Warning: Regex for names is never 100% accurate.
    # Matches: Capitalized Cyrillic words (Name Surname)
    # Ex: Иван Иванов, Петров П.П.
    NAME_RU_BROAD = r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?\b'