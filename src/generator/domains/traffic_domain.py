import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any

from ..nlp import generate_synthetic_text


class TrafficDomainGenerator:
    domain = "traffic"

    @staticmethod
    def _hash_entity(entity_id: str) -> str:
        return hashlib.sha256(entity_id.encode()).hexdigest()[:16]

    def generate_record(self, region: str, country: str, seed: int = 0) -> Dict[str, Any]:
        entity_id = str(uuid.uuid4())
        profile_id = self._hash_entity(entity_id)
        timestamp = datetime.now(timezone.utc).isoformat()
        numeric_metrics = {
            "speed_index": max(1, int((seed % 100) + 20)),
            "congestion_level": (seed % 3) + 1,
            "sensor_cluster": "SC" + str(seed % 999)
        }
        behavioral_flags = {
            "high_activity": (seed % 6) == 0,
            "anomaly_detected": (seed % 13) == 0,
            "drift_signal": float((seed % 9) / 9.0)
        }
        text_payload = generate_synthetic_text("traffic", seed)
        return {
            "entity_id": entity_id,
            "domain": self.domain,
            "region": region,
            "synthetic_country": country,
            "event_type": "incident",
            "numeric_metrics": numeric_metrics,
            "behavioral_flags": behavioral_flags,
            "text_payload": text_payload,
            "timestamp": timestamp,
            "profile_id": profile_id,
            "human_review_flag": False,
            "confidence_score": 0.86,
            "review_notes_placeholder": ""
        }
