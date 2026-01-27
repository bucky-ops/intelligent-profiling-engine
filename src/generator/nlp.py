"""NLP helpers for synthetic text generation and embeddings placeholders."""
from typing import List


def generate_synthetic_text(domain: str, seed: int = 0) -> str:
    # Simple, domain-specific templates with non-identifiable content
    templates = {
        "finance": [
            "Irregular activity detected during late settlement window",
            "Transaction notes indicate standard processing with variance in timing",
            "Compliance check passed for synthetic account"
        ],
        "ngo": [
            "Community feedback indicates delayed distribution due to weather",
            "Program deliverables completed with beneficiary satisfaction rating high",
            "Field report shows resource allocation within planned budget"
        ],
        "telecom": [
            "Intermittent signal loss reported in high-density cluster",
            "Usage spike observed during event period",
            "Service ticket opened for intermittent connectivity"
        ],
        "traffic": [
            "Recurring congestion observed near arterial junction",
            "Sensor indicates rising speed variation across lanes",
            "Road network functioning within resilience thresholds"
        ],
    }
    items = templates.get(domain, ["Synthetic domain text payload"])
    idx = seed % len(items)
    return items[idx]

def generate_embeddings_for_texts(texts: List[str]):
    # Placeholder: return same-length list of dummy vectors
    return [[0.0] * 128 for _ in texts]
