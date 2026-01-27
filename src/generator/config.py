import yaml
from typing import Any, Dict


class ConfigLoader:
    def __init__(self, path: str):
        self.path = path
        self.config: Dict[str, Any] = {}
        self.load()

    def load(self) -> Dict[str, Any]:
        with open(self.path, 'r') as f:
            self.config = yaml.safe_load(f)
        return self.config

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)
