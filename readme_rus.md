# LightAnon

Библиотека для обезличивания данных в ML-пайплайнах с поддержкой отчетности.

## Возможности
- Поддержка `pandas` и `polars`.
- CLI с YAML-конфигом.
- Базовые правила: `Hash`, `Mask`, `GaussianNoise`, `Generalize`.
- Финансовые правила: `MultiplicativeNoise`, `TopCoding`, `CreditCardMask`.
- Генерация отчета о примененных методах обезличивания.

## Установка
```bash
git clone https://github.com/SoldatovAlexander/lightanon_project.git
cd lightanon_project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Быстрый старт (Python API)
```python
import pandas as pd
import lightanon as la

df = pd.DataFrame(
    {
        "full_name": ["Иван Иванов", "Анна Петрова"],
        "email": ["ivan@example.com", "anna@example.com"],
        "age": [23, 41],
    }
)

schema = {
    "full_name": la.rules.Mask(visible_chars=1),
    "email": la.rules.Hash(salt="project_salt"),
    "age": la.rules.Generalize(step=5),
}

engine = la.Engine(schema)
clean_df = engine.run(df)
print(clean_df)
print(engine.generate_report())
```

## CLI
```bash
lightanon input.csv output.parquet -c schema.yaml --engine pandas
lightanon input.parquet output.csv -c schema.yaml --engine polars
```

Поддерживаемые форматы входа/выхода: `.csv`, `.parquet`.

## Тесты
```bash
pytest -q
```
