"""Orchestrator to generate synthetic data according to a config."""
import uuid
from typing import Dict, List
from datetime import datetime

from .domains import FinanceDomainGenerator, NGODomainGenerator, TelecomDomainGenerator, TrafficDomainGenerator
from .nlp import generate_synthetic_text, generate_embeddings_for_texts
from .config import ConfigLoader
import random


class SyntheticDataOrchestrator:
    def __init__(self, config_path: str):
        self.config = ConfigLoader(config_path).config
        self.regions = self.config.get("regions", {})
        self.domain_generators = {
            "finance": FinanceDomainGenerator(),
            "ngo": NGODomainGenerator(),
            "telecom": TelecomDomainGenerator(),
            "traffic": TrafficDomainGenerator(),
        }

        # seeds for reproducibility
        self.global_seed = self.config.get("seed", 42)
        random.seed(self.global_seed)

    def generate_record(self, domain: str, region_code: str) -> Dict:
        region_info = self.regions.get(region_code, None)
        country = region_info.get("countries")[0] if region_info else "ZZ"  # fallback
        seed = random.randint(0, 1_000_000)
        generator = self.domain_generators[domain]
        return generator.generate_record(region_code, country, seed)

    def generate_batch(self, domain: str, region_code: str, size: int) -> List[Dict]:
        return [self.generate_record(domain, region_code) for _ in range(size)]

    def to_parquet(self, records: List[Dict], path: str):
        # Lightweight: save as JSONL if parquet not available
        import json
        with open(path, 'w') as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        print(f"Saved {len(records)} records to {path} (JSONL fallback)")
