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
    # Passport RF: Series (4 digits) + Number (6 digits).
    # Requires a separator before the 6-digit number to avoid matching 10-digit INN.
    # Ex: 45 00 123456, 4500 123456
    PASSPORT_RU = r'\b\d{2}[\s\-]?\d{2}[\s\-]+\d{6}\b'

    # SNILS: 11 digits, often 123-456-789 00
    SNILS = r'\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b'

    # INN (Tax ID): 10 or 12 digits
    INN = r'\b\d{10}\b|\b\d{12}\b'

    # --- ONLINE IDENTIFIERS ---
    # Combined nickname/login + resource. Tokenize the full pair because the
    # combination can identify a person more reliably than either part alone.
    # Ex: никнейм ivan_dev на Habr, login petrov on forum.example.com
    ONLINE_ACCOUNT_RU = (
        r'\b(?:ник(?:нейм)?|логин|аккаунт|профиль|пользователь)\s+'
        r'@?[A-Za-z0-9][A-Za-z0-9_.-]{2,31}\s+'
        r'(?:на|в)\s+'
        r'(?:[A-Za-zА-Яа-яЁё0-9][A-Za-zА-Яа-яЁё0-9_.-]{1,63}'
        r'(?:\.[A-Za-zА-Яа-яЁё]{2,})?)\b'
    )
    ONLINE_ACCOUNT_EN = (
        r'\b(?:nickname|nick|login|account|profile|user(?:name)?)\s+'
        r'@?[A-Za-z0-9][A-Za-z0-9_.-]{2,31}\s+'
        r'(?:on|at)\s+'
        r'(?:[A-Za-z0-9][A-Za-z0-9_.-]{1,63}(?:\.[A-Za-z]{2,})?)\b'
    )
    RESOURCE_ACCOUNT = (
        r'\b(?:Telegram|GitHub|Gitlab|GitLab|Habr|VK|VKontakte|Discord|Slack|Forum|Форум|Хабр|ВК)\s*'
        r'[:=]\s*@?[A-Za-z0-9][A-Za-z0-9_.#-]{2,31}\b'
    )

    # Profile URLs and messenger/social links.
    # Ex: https://github.com/ivan_dev, vk.com/id123456, t.me/ivanov
    PROFILE_URL = (
        r'\b(?:https?://)?(?:'
        r't\.me|telegram\.me|vk\.com|vkontakte\.ru|github\.com|gitlab\.com|'
        r'habr\.com|career\.habr\.com|linkedin\.com/in|facebook\.com|'
        r'instagram\.com|x\.com|twitter\.com'
        r')/[A-Za-z0-9_.@#-]{3,64}\b'
    )

    # Social or messenger handle. Kept stricter than email local parts.
    # Ex: @ivan_dev
    SOCIAL_HANDLE = r'(?<![\w.%+-])@[A-Za-z0-9_][A-Za-z0-9_.-]{2,31}\b'

    # Generic username only when it is explicitly labelled.
    # Ex: username: ivan_dev, логин: petrov
    USERNAME = r'\b(?:username|user|login|nick|nickname|логин|ник(?:нейм)?|пользователь)\s*[:=]\s*@?[A-Za-z0-9][A-Za-z0-9_.-]{2,31}\b'

    # --- FINANCE ---
    # Credit Card: 13-19 digits, potentially grouped
    CREDIT_CARD = r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'

    # --- NAMES (HEURISTIC) ---
    # Warning: Regex for names is never 100% accurate.
    # Matches: Capitalized Cyrillic words (Name Surname)
    # Ex: Иван Иванов, Петров П.П.
    NAME_RU_BROAD = r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?\b'
