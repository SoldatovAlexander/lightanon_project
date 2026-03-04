from typing import Dict, Any, Iterable, Generator, List
from .rules import BaseRule


class StreamEngine:
    """
    High-performance engine for processing single records (dicts).
    Ideal for Kafka consumers, API endpoints, or event loops.
    No Pandas overhead.
    """

    def __init__(self, schema: Dict[str, BaseRule]):
        """
        :param schema: Dictionary mapping field names to Rules.
        """
        self.schema = schema

    def process_one(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single dictionary.
        Returns a NEW dictionary (shallow copy) with anonymized fields.
        """
        # Shallow copy is much faster than deepcopy and safe for immutable primitives
        clean_record = record.copy()

        for field, rule in self.schema.items():
            if field in clean_record:
                # Direct scalar call -> Microsecond latency
                clean_record[field] = rule.apply_single(clean_record[field])

        return clean_record

    def process_iter(self, iterator: Iterable[Dict[str, Any]]) -> Generator[Dict[str, Any], None, None]:
        """
        Generator for processing a stream of records.
        """
        for record in iterator:
            yield self.process_one(record)

    def process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a list of dicts.
        """
        return [self.process_one(record) for record in batch]