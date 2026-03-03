import pandas as pd
import lightanon as la

# 1. Создаем грязные данные (Mock Data)
data = {
    "user_id": [101, 102, 103, 104, 105],
    "full_name": ["Иван Иванов", "Петр Петров", "Анна Сидорова", "Джон Доу", "Мария Кюри"],
    "email": ["ivanov@mail.ru", "petrov@yandex.ru", "anna@gmail.com", "john@corp.com", "maria@science.org"],
    "salary": [100000, 150000, 120000, 300000, 85000],
    "age": [23, 45, 31, 28, 56],
    "department": ["IT", "IT", "HR", "Management", "Science"]
}

df = pd.DataFrame(data)

print("--- ORIGINAL DATA ---")
print(df.head())
print("\n")

# 2. Определяем схему анонимизации
# Это тот самый "Zero-config start" - просто словарь
schema = {
    "full_name": la.rules.Mask(visible_chars=1),         # И****
    "email":     la.rules.Hash(salt="secret_project_x"), # a3f1...
    "salary":    la.rules.GaussianNoise(std=0.05),       # Шум 5%
    "age":       la.rules.Generalize(step=5)             # 20-25
    # Department не трогаем, это не PII в данном контексте
}

# 3. Запускаем движок
engine = la.Engine(schema)
clean_df = engine.run(df)

# 4. Проверяем результат
print("--- CLEAN DATA (Ready for ML) ---")
print(clean_df.head())
print("\n")

# 5. Генерируем отчет для юристов/безопасников
print(engine.generate_report())