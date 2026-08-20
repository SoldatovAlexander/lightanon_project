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
    PHONE_RU = r'(?<!\d)(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}(?!\d)'

    # --- DOCUMENTS (RUSSIA) ---
    # Passport RF: Series (4 digits) + Number (6 digits).
    # Requires a separator before the 6-digit number to avoid matching 10-digit INN.
    # Ex: 45 00 123456, 4500 123456
    PASSPORT_RU = (
        r'(?i:\bпаспорт\s*(?:серия\s*)?\d{2}[\s\-]?\d{2}\s*(?:№|номер|n)?\s*\d{6}\b)'
        r'|\b\d{2}[\s\-]?\d{2}[\s\-]+\d{6}\b'
    )

    # SNILS: 11 digits, often 123-456-789 00
    SNILS = r'\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}[\s\-]?\d{2}\b'

    # INN (Tax ID): 10 or 12 digits
    INN = r'\b(?:\d{10}|\d{12})\b'

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

    # --- TECHNICAL IDENTIFIERS ---
    # Ex: 192.168.1.10
    IP_ADDRESS = r'\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b'

    # Explicitly labelled cookie/session IDs to avoid matching arbitrary hashes.
    # Ex: cookie_id: abc123, session=xyZ-789
    COOKIE_ID = r'\b(?:cookie(?:_id)?|session(?:_id)?)\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}\b'

    # Explicitly labelled device/client IDs.
    # Ex: device_id: a1b2c3d4, client id = 123e4567-e89b-12d3-a456-426614174000
    DEVICE_ID = r'\b(?:device(?:_id)?|client(?:_id)?|device id|client id)\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9_.:-]{7,127}\b'

    # Explicitly labelled user IDs.
    # Ex: user_id: 123456, id пользователя = abc-123
    USER_ID = r'\b(?:user(?:_id)?|user id|id пользователя|идентификатор пользователя)\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9_.:-]{3,127}\b'

    # --- BUSINESS / ORGANIZATION IDENTIFIERS ---
    # Composite organization requisites block. Kept first in business modes to
    # avoid tokenizing each field separately when a compact requisites string is present.
    # Ex: реквизиты ООО "Ромашка": ИНН 7707083893, КПП 770701001
    BUSINESS_REQUISITES = (
        r'(?i:\b(?:реквизиты|данные компании|карточка компании|организация|компания|юр\.?\s*лицо)\s*'
        r'[:\-]?\s*'
        r'(?:[^\n;]{0,160}?)'
        r'(?:ИНН\s*\d{10}|КПП\s*\d{9}|ОГРН\s*\d{13}|БИК\s*\d{9}|'
        r'(?:р/с|расчетный счет|расчётный счет)\s*\d{20})'
        r'(?:[^\n;]{0,80}?(?:ИНН\s*\d{10}|КПП\s*\d{9}|ОГРН\s*\d{13}|БИК\s*\d{9}|'
        r'(?:р/с|расчетный счет|расчётный счет)\s*\d{20}|ОКПО\s*\d{8,10}))*'
        r')'
    )

    # Counterparty-specific composite block.
    # Ex: контрагент: ООО "Вектор", ИНН 7708123456, КПП 770801001
    COUNTERPARTY_REQUISITES = (
        r'(?i:\b(?:контрагент|поставщик|подрядчик|покупатель|заказчик|исполнитель|клиент)\s*'
        r'[:\-]\s*'
        r'(?:[^\n;]{0,160}?)'
        r'(?:ИНН\s*\d{10}|КПП\s*\d{9}|ОГРН\s*\d{13}|БИК\s*\d{9}|'
        r'(?:р/с|расчетный счет|расчётный счет)\s*\d{20})'
        r'(?:[^\n;]{0,80}?(?:ИНН\s*\d{10}|КПП\s*\d{9}|ОГРН\s*\d{13}|БИК\s*\d{9}|'
        r'(?:р/с|расчетный счет|расчётный счет)\s*\d{20}|ОКПО\s*\d{8,10}))*'
        r')'
    )

    # Full and short organization names.
    # Ex: ООО "Ромашка", АО «Вектор», Общество с ограниченной ответственностью "Ромашка"
    ORGANIZATION_NAME = (
        r'(?i:\b(?:'
        r'ООО|АО|ПАО|НАО|ЗАО|ОАО|АНО|НКО|ФГБУ|ГБУ|МБУ|ИП|'
        r'Общество с ограниченной ответственностью|Акционерное общество|'
        r'Публичное акционерное общество|Индивидуальный предприниматель'
        r')\s+'
        r'(?:[«"][^»"\n]{2,120}[»"]|[A-ZА-ЯЁ][A-Za-zА-Яа-яЁё0-9_.\- ]{2,120}))'
    )

    # Organization tax IDs and registration IDs.
    COMPANY_INN = r'(?i:\bИНН\s*[:№#-]?\s*\d{10}\b)'
    KPP = r'(?i:\bКПП\s*[:№#-]?\s*\d{9}\b)'
    OGRN = r'(?i:\bОГРН\s*[:№#-]?\s*\d{13}\b)'
    OKPO = r'(?i:\bОКПО\s*[:№#-]?\s*\d{8,10}\b)'

    # Legal address. Stops at newline or semicolon to avoid swallowing full documents.
    LEGAL_ADDRESS = r'(?i:\b(?:юридический адрес|юр\.?\s*адрес|адрес регистрации)\s*[:\-]\s*[^;\n]{10,220})'

    # Bank details.
    BANK_ACCOUNT = r'(?i:\b(?:р/с|расчетный счет|расчётный счет)\s*[:№#-]?\s*\d{20}\b)'
    CORRESPONDENT_ACCOUNT = r'(?i:\b(?:к/с|корр\.?\s*счет|корреспондентский счет|корреспондентский счёт)\s*[:№#-]?\s*\d{20}\b)'
    BIK = r'(?i:\bБИК\s*[:№#-]?\s*\d{9}\b)'

    # --- FINANCE ---
    # Credit Card: 13-19 digits, potentially grouped
    CREDIT_CARD = r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'

    # --- NAMES (HEURISTIC) ---
    # Warning: Regex for names is never 100% accurate.
    # Matches: Capitalized Cyrillic words (Name Surname)
    # Ex: Иван Иванов, Петров П.П.
    NAME_RU_BROAD = (
        r'\b(?:[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?:\s+[А-ЯЁ][а-яё]+)?'
        r'|[А-ЯЁ][а-яё]+\s+[А-ЯЁ]\.\s*[А-ЯЁ]\.)(?!\w)'
    )
