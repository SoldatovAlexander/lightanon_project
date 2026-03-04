# Streaming Guide

`StreamEngine` is designed for low-latency processing of dictionary records.

## When to Use
- Kafka consumers,
- API events,
- queue workers,
- ETL stages operating on JSON-like payloads.

## Basic Example

```python
import lightanon as la

schema = {
    "user_id": la.rules.Hash(salt="kafka_secret"),
    "ip": la.rules.Mask(visible_chars=3),
    "amount": la.financial.TopCodingFixed(cap_value=10000.0),
}

engine = la.StreamEngine(schema)

event = {"ts": 1, "user_id": "alice", "ip": "192.168.1.1", "amount": 35000.0}
print(engine.process_one(event))
```

## API
- `process_one(record: Dict[str, Any]) -> Dict[str, Any>`
- `process_iter(iterator: Iterable[Dict[str, Any]]) -> Generator[...]`
- `process_batch(batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]`

## Performance Note
For best latency, each rule used in streaming should implement `apply_single`.
Otherwise, fallback logic may be noticeably slower.
