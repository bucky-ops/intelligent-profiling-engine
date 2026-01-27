from typing import Dict, List


class HITLFeedback:
    def __init__(self):
        self.validations: List[Dict] = []  # e.g., {"entity_id": "123", "validated": True, "notes": "..."}
        self.overrides: List[Dict] = []    # e.g., {"rule": "anomaly_threshold", "override_value": 0.5}

    def add_validation(self, validation: Dict):
        self.validations.append(validation)

    def add_override(self, override: Dict):
        self.overrides.append(override)

    def get_feedback_for_entity(self, entity_id: str) -> List[Dict]:
        return [v for v in self.validations if v.get("entity_id") == entity_id]

    def apply_overrides(self, config: Dict) -> Dict:
        for override in self.overrides:
            config[override["rule"]] = override["override_value"]
        return config