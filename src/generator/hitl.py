from typing import Dict, List


class HITLStore:
    def __init__(self):
        self.validations: List[Dict] = []
        self.overrides: List[Dict] = []

    def add_validation(self, validation: Dict):
        self.validations.append(validation)

    def add_override(self, override: Dict):
        self.overrides.append(override)

    def get_for_entity(self, entity_id: str) -> List[Dict]:
        return [v for v in self.validations if v.get("entity_id") == entity_id]
