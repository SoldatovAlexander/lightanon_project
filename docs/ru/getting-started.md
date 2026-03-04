# Быстрый старт

## Установка

```bash
git clone https://github.com/SoldatovAlexander/lightanon_project.git
cd lightanon_project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Проверка окружения

```bash
python -m pytest -q
```

## Первый пример (`pandas`)

```python
import pandas as pd
import lightanon as la

df = pd.DataFrame(
    {
        "full_name": ["Иван Иванов", "Анна Петрова"],
        "email": ["ivan@example.com", "anna@example.com"],
        "age": [23, 41],
        "salary": [100000, 120000],
    }
)

schema = {
    "full_name": la.rules.Mask(visible_chars=1),
    "email": la.rules.Hash(salt="prod_salt"),
    "age": la.rules.Generalize(step=5),
    "salary": la.rules.GaussianNoise(std=0.1),
}

engine = la.Engine(schema)
clean_df = engine.run(df)
print(clean_df)
print(engine.generate_report())
```

## Что такое Schema

Schema - словарь соответствия колонок и правил:

```python
schema = {
    "column_a": RuleA(...),
    "column_b": RuleB(...),
}
```

## Дальше
- CLI: [Руководство по CLI](./cli.md)
- правила и классы: [Справочник API](./api.md)
- потоковые события: [Streaming](./streaming.md)
- текст для LLM: [RAG](./rag.md)
