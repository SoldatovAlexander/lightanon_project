# LightAnon

High-performance data anonymization for ML pipelines and compliance workflows.

![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Engine](https://img.shields.io/badge/engine-Pandas%20%7C%20Polars-orange)
![License](https://img.shields.io/badge/license-MIT-green)
![Compliance](https://img.shields.io/badge/compliance-152--FZ-red)

## Project Description / Описание проекта

**EN:** LightAnon is a lightweight Python library for anonymizing structured and text data in ML, analytics, and compliance workflows. It provides batch processing for `pandas` and `polars`, streaming/event anonymization, domain-specific financial rules, and a reversible RAG text-sanitization block that replaces sensitive values with tokens before sending text to LLM systems.

**RU:** LightAnon — легковесная Python-библиотека для обезличивания структурированных и текстовых данных в ML-, аналитических и compliance-пайплайнах. Проект поддерживает пакетную обработку через `pandas` и `polars`, потоковую анонимизацию событий, отдельные финансовые правила и обратимый RAG-блок, который заменяет чувствительные данные токенами перед отправкой текста в LLM-системы.

## Features
- Pandas and Polars support.
- YAML-driven CLI.
- Core rules: `Hash`, `Mask`, `GaussianNoise`, `Generalize`.
- Financial rules: `MultiplicativeNoise`, `TopCoding`, `CreditCardMask`.
- Separate RAG block for reversible text sanitization before LLM calls.
- Compliance report generation from applied transformations.

## Installation
```bash
git clone https://github.com/SoldatovAlexander/lightanon_project.git
cd lightanon_project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Quick Start (Python API)
```python
import pandas as pd
import lightanon as la

df = pd.DataFrame(
    {
        "full_name": ["Alice Smith", "Bob Stone"],
        "email": ["alice@example.com", "bob@example.com"],
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

## CLI Usage
```bash
lightanon input.csv output.parquet -c schema.yaml --engine pandas
lightanon input.parquet output.csv -c schema.yaml --engine polars
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json
lightanon rag sanitize prompt.txt sanitized.txt --vault vault.json --rules EMAIL,PHONE,INN
lightanon rag restore llm_response.txt restored.txt --vault vault.json
lightanon rag inspect-vault vault.json
```

Supported I/O formats: `.csv`, `.parquet`.

## Tests
```bash
pytest -q
```

## Documentation
- Main English docs index: `docs/en/README.md`
- API reference: `docs/en/api.md`
- CLI guide: `docs/en/cli.md`
- Streaming guide: `docs/en/streaming.md`
- RAG guide: `docs/en/rag.md`
- Troubleshooting: `docs/en/troubleshooting.md`
- Russian docs index: `docs/ru/README.md`
