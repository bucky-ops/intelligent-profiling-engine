"""Minimal streaming module to push synthetic data to a Kafka-like sink (simulated)."""
import json
from typing import Dict, List, Optional

try:
    from generator.orchestrator import SyntheticDataOrchestrator
except Exception:
    SyntheticDataOrchestrator = object  # type: ignore


class SimulatedKafkaSink:
    def __init__(self):
        self.topics: Dict[str, List[str]] = {}

    def produce(self, topic: str, value: object) -> None:
        entry = value if isinstance(value, str) else json.dumps(value)
        self.topics.setdefault(topic, []).append(entry)

    def get_topic(self, topic: str) -> List[str]:
        return list(self.topics.get(topic, []))

    def clear(self, topic: Optional[str] = None) -> None:
        if topic:
            self.topics.pop(topic, None)
        else:
            self.topics.clear()


def simulate_streaming(domain: str, region: str, total: int, batch_size: int, sink: SimulatedKafkaSink, orchestrator=None) -> None:
    """Generate in batches and push to a simulated Kafka sink.

    If an orchestrator is provided, it will be used to generate batches; otherwise, a simplified generator is used.
    """
    if orchestrator is not None:
        batches = 0
        for _ in range(0, total, batch_size):
            batch = orchestrator.generate_batch(domain, region, min(batch_size, total - batches * batch_size))
            sink.produce(f"{domain}.{region}", batch)
            batches += 1
    else:
        # Fallback: simple placeholder data
        for _ in range(0, total, batch_size):
            batch = [{"domain": domain, "region": region, "generated": True} for _ in range(min(batch_size, total))]
            sink.produce(f"{domain}.{region}", batch)
