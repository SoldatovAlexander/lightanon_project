# LightAnon

High-performance data anonymization for ML pipelines and compliance workflows.

## Features
- Pandas and Polars support.
- YAML-driven CLI.
- Core rules: `Hash`, `Mask`, `GaussianNoise`, `Generalize`.
- Financial rules: `MultiplicativeNoise`, `TopCoding`, `CreditCardMask`.
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
```

Supported I/O formats: `.csv`, `.parquet`.

## Tests
```bash
pytest -q
```
