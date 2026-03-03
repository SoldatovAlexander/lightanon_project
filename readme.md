LightAnonЛегковесная библиотека анонимизации данных для ML и соответствия 152-ФЗLightAnon — это быстрая Python-библиотека с минимальной конфигурацией, созданная для обезличивания датасетов в ML-пайплайнах. Она позволяет безопасно передавать данные подрядчикам или загружать в облака, соблюдая требования 152-ФЗ (Приказ Роскомнадзора № 996), при этом сохраняя статистическую полезность данных для обучения AI-моделей.🚀 Ключевые возможностиZero-Config: Чистый Python без тяжелых зависимостей. Не требует Docker, JVM или сложных NLP-моделей.Сохранение полезности (Utility): В отличие от простого удаления, использует статистический шум, обобщение и баккетинг, сохраняя распределения и корреляции в данных.Высокая производительность: Построена на векторизованных операциях numpy для обработки миллионов строк за секунды.Compliance Audit: Автоматически генерирует текстовый отчет, сопоставляющий примененные трансформации с методами, утвержденными Роскомнадзором.FinTech Ready: Специальный модуль для финансовых данных (мультипликативный шум, защита от атак на "китов"/выбросы).📦 УстановкаBash# Клонирование репозитория
git clone https://github.com/your-username/lightanon.git
cd lightanon

# Установка зависимостей
pip install -r requirements.txt
🛠 Использование1. Базовый примерPythonimport pandas as pd
import lightanon as la

# 1. Загрузка данных
df = pd.read_csv("data/clients.csv")

# 2. Определение схемы анонимизации
# Простой словарь: колонка -> правило
schema = {
    "full_name": la.rules.Mask(visible_chars=1),           # Результат: "И****"
    "email":     la.rules.Hash(salt="prod_v1_secret"),     # Результат: "a3f19..." (Можно делать JOIN!)
    "age":       la.rules.Generalize(step=5),              # Результат: "20-25"
    "salary":    la.rules.GaussianNoise(std=0.05)          # Результат: Значение +/- 5% шума
}

# 3. Запуск движка
engine = la.Engine(schema)
clean_df = engine.run(df)

# 4. Генерация отчета для офицера безопасности
print(engine.generate_report())
2. Финансовые данные (Advanced)Для банковских и финтех-датасетов стандартного шума недостаточно. Используйте модуль financial для скрытия VIP-клиентов ("китов") и сохранения трендов транзакций.Pythonschema = {
    # Маскирование карт по стандарту PCI DSS
    "card_number": la.financial.CreditCardMask(),
    
    # Мультипликативный шум сохраняет процентный тренд 
    # (например, 50 -> 52.5, 1млн -> 1.05млн)
    "transaction_amt": la.financial.MultiplicativeNoise(std_dev_percent=0.03),
    
    # Винзоризация (Top-Coding): Обрезаем все значения выше 99-го перцентиля.
    # Скрывает VIP-клиентов от атак повторной идентификации по уникальным суммам.
    "balance": la.financial.TopCoding(quantile=0.99)
}

engine = la.Engine(schema)
clean_df = engine.run(df)
⚖️ Юридическое соответствие (152-ФЗ)LightAnon реализует методы, явно утвержденные Приказом Роскомнадзора от 05.09.2013 № 996 "Об утверждении требований и методов по обезличиванию персональных данных":Правило LightAnonМетод по Приказу № 996ОписаниеHash, Mask, TokenizeМетод введения идентификаторовЗамена ПДн уникальными ID или масками. Позволяет джойнить таблицы при наличии ключа ("соли").Generalize, RoundingМетод изменения состава или семантикиСнижение детализации (например, точный возраст заменяется на возрастную группу).GaussianNoiseМетод изменения состава или семантикиСтатистическое возмущение (шум) с сохранением среднего и дисперсии.TopCodingМетод изменения состава или семантикиСкрытие выбросов для предотвращения атак по уникальным атрибутам.🏗 АрхитектураБиблиотека работает как линейный конвейер (Pipeline):Источник (Pandas DataFrame) -> Инспектор -> Движок Анонимизации -> РезультатЯдро: Построено на pandas apply (для строк) и numpy (векторизация для чисел).Расширяемость: Наследуйтесь от la.rules.BaseRule для создания собственных трансформеров.🗺 Планы развития (Roadmap)[x] Основной движок (MVP)[x] Отчетность по 152-ФЗ[x] Финансовый модуль (TopCoding, Multiplicative Noise)[ ] Поддержка Polars (для обработки датасетов 10GB+)[ ] CLI Интерфейс (lightanon input.csv output.csv)[ ] Поддержка неструктурированного текста (Regex для поиска ФИО в комментариях)🤝 Вклад в разработку (Contributing)Мы приветствуем Pull Requests. Для крупных изменений, пожалуйста, сначала откройте Issue для обсуждения того, что вы хотели бы изменить.📄 ЛицензияMIT

LightAnonLightweight Data Anonymization Library for ML & Compliance (152-FZ)LightAnon is a high-performance, zero-config Python library designed to anonymize datasets for Machine Learning pipelines. It allows developers to safely share data with contractors or cloud services while complying with Roskomnadzor Order No. 996 (152-FZ), without destroying the statistical utility required for training AI models.🚀 Key FeaturesZero-Config Start: Pure Python architecture with minimal dependencies (numpy, pandas). No heavy NLP models, JVM, or Docker containers required.Utility Preservation: Unlike simple masking, LightAnon uses statistical noise, generalization, and bucketing to preserve data distribution and correlations.High Performance: Built on vectorized operations to process millions of rows in seconds.Compliance Audit: Automatically generates a text report mapping applied transformations to legal methods (Introduction of Identifiers, Change of Composition, etc.).FinTech Ready: Includes specialized modules for financial data (Multiplicative Noise, Outlier/Whale protection).📦 InstallationBash# Clone the repository
git clone https://github.com/your-username/lightanon.git
cd lightanon

# Install dependencies
pip install -r requirements.txt
🛠 Quick Start1. Basic AnonymizationPythonimport pandas as pd
import lightanon as la

# Load your dataset
df = pd.read_csv("data/clients.csv")

# Define the anonymization schema
# Simple dictionary mapping columns to rules
schema = {
    "full_name": la.rules.Mask(visible_chars=1),           # Result: "I****"
    "email":     la.rules.Hash(salt="prod_v1_secret"),     # Result: "a3f19..." (Joinable!)
    "age":       la.rules.Generalize(step=5),              # Result: "20-25"
    "salary":    la.rules.GaussianNoise(std=0.05)          # Result: Value +/- 5% noise
}

# Run the engine
engine = la.Engine(schema)
clean_df = engine.run(df)

# Generate Compliance Report for your Security Officer
print(engine.generate_report())
2. Financial Data (Advanced)For banking and fintech datasets, standard noise is not enough. Use the financial module to handle "whales" (VIP clients) and preserve transaction trends.Pythonschema = {
    # PCI DSS style masking for cards
    "card_number": la.financial.CreditCardMask(),
    
    # Multiplicative noise preserves the percentage trend 
    # (e.g., 50 -> 52.5, 1M -> 1.05M)
    "transaction_amt": la.financial.MultiplicativeNoise(std_dev_percent=0.03),
    
    # Winsorization: Cap all values above 99th percentile 
    # Hides VIP clients from re-identification attacks
    "balance": la.financial.TopCoding(quantile=0.99)
}

engine = la.Engine(schema)
clean_df = engine.run(df)
⚖️ Legal Compliance (152-FZ)LightAnon implements methods explicitly approved by Roskomnadzor Order No. 996 (05.09.2013) "On approval of requirements and methods for depersonalization of personal data":LightAnon RuleLegal Method (Order No. 996)DescriptionHash, Mask, TokenizeMethod of Introduction of Identifiers (Метод введения идентификаторов)Replaces PII with unique IDs or masks. Allows joining tables if the key is known.Generalize, RoundingMethod of Change of Composition (Метод изменения состава)Reduces granularity (e.g., exact age to age group).GaussianNoise, MultiplicativeNoiseMethod of Change of Composition (Метод изменения состава)Statistical perturbation preserving means and variances.TopCodingMethod of Change of Composition (Метод изменения состава)Hiding outliers to prevent unique attribute attacks.🏗 ArchitectureThe library operates as a linear pipeline:Source (Pandas DataFrame) -> Inspector -> Anonymizer Engine -> SinkCore: Built on pandas apply (for strings) and numpy vectorization (for numbers).Extensibility: Inherit from la.rules.BaseRule to create custom transformers.🗺 Roadmap[x] Core Engine (MVP)[x] 152-FZ Compliance Reporting[x] Financial Module (TopCoding, Multiplicative Noise)[ ] Polars Support (for handling 10GB+ datasets)[ ] CLI Interface (lightanon input.csv output.csv)[ ] Unstructured Text Support (Regex-based PII removal)🤝 ContributingPull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.📄 LicenseMIT