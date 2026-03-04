# Getting Started

## Installation

```bash
git clone https://github.com/SoldatovAlexander/lightanon_project.git
cd lightanon_project
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

## Verify Setup

```bash
python -m pytest -q
```

## First Batch Example (`pandas`)

```python
import pandas as pd
import lightanon as la

df = pd.DataFrame(
    {
        "full_name": ["Alice Smith", "Bob Stone"],
        "email": ["alice@example.com", "bob@example.com"],
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

## Schema Concept

A schema maps input columns/fields to rule instances:

```python
schema = {
    "column_a": RuleA(...),
    "column_b": RuleB(...),
}
```

## Next Steps
- CLI flow: [CLI Guide](./cli.md)
- Rule details: [API Reference](./api.md)
- Streaming events: [Streaming Guide](./streaming.md)
- Text for LLM pipelines: [RAG Guide](./rag.md)
