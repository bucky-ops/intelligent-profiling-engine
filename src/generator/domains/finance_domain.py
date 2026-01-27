import uuid
import hashlib
from datetime import datetime
from typing import Dict, Any

from ..nlp import generate_synthetic_text


class FinanceDomainGenerator:
    domain = "finance"

    @staticmethod
    def _hash_entity(entity_id: str) -> str:
        return hashlib.sha256(entity_id.encode()).hexdigest()[:16]

    def generate_record(self, region: str, country: str, seed: int = 0) -> Dict[str, Any]:
        entity_id = str(uuid.uuid4())
        profile_id = self._hash_entity(entity_id)
        timestamp = datetime.utcnow().isoformat()
        numeric_metrics = {
            "transaction_amount": round((seed + 1) * 123.45, 2),
            "risk_score": min(1.0, max(0.0, (seed % 100) / 100.0)),
            "anomaly_flag": bool(seed % 7 == 0),
            "payment_channel": "online"
        }
        behavioral_flags = {
            "high_activity": (seed % 5) == 0,
            "anomaly_detected": (seed % 11 == 0),
            "drift_signal": float((seed % 10) / 10.0)
        }
        text_payload = generate_synthetic_text("finance", seed)
        return {
            "entity_id": entity_id,
            "domain": self.domain,
            "region": region,
            "synthetic_country": country,
            "event_type": "transaction",
            "numeric_metrics": numeric_metrics,
            "behavioral_flags": behavioral_flags,
            "text_payload": text_payload,
            "timestamp": timestamp,
            "profile_id": profile_id,
            "human_review_flag": False,
            "confidence_score": 0.9,
            "review_notes_placeholder": ""
        }
