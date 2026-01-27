"""Terminal-style UI shim that wires to the orchestrator and a simple in-memory profiler."""
import json
from typing import Dict, List
from generator.config import ConfigLoader

try:
    from generator.orchestrator import SyntheticDataOrchestrator
except Exception:
    class SyntheticDataOrchestrator:  # minimal stub
        def __init__(self, _config_path):
            self.config = ConfigLoader(_config_path).config
        def generate_batch(self, domain, region, size):
            return []
        def to_parquet(self, records, path):
            return path


class InMemoryProfiler:
    def __init__(self):
        self.profiles: Dict[str, Dict] = {}
    def update(self, record: Dict):
        entity = record.get('entity_id')
        if not entity:
            return
        self.profiles.setdefault(entity, {}).setdefault('records', []).append(record)
    def summarize(self) -> str:
        lines = [f"Entities: {len(self.profiles)}"]
        for k, v in list(self.profiles.items())[:5]:
            lines.append(f"{k}: {len(v.get('records', []))} records")
        return "\n".join(lines)

def run_terminal_ui(config_path: str = "config/global_synthetic_config.yaml"):
    orch = SyntheticDataOrchestrator(config_path)
    profiler = InMemoryProfiler()
    print("Profile System Terminal UI (simulated). Type 'help' for commands.")
    print("Commands: generate <domain> <region> <size>, stream <domain> <region> <size>, show, help, exit")
    while True:
        try:
            cmd = input("> ").strip()
        except KeyboardInterrupt:
            print("\nExiting UI.")
            break
        if not cmd:
            continue
        parts = cmd.split()
        if parts[0] == 'exit':
            break
        if parts[0] == 'help':
            print("Commands: generate, stream, show, exit")
            continue
        if parts[0] == 'generate' and len(parts) == 4:
            domain, region, size_s = parts[1], parts[2], int(parts[3])
            records = orch.generate_batch(domain, region, size_s)
            for r in records:
                profiler.update(r)
            print(f"Generated {len(records)} records for {domain} {region}.")
        elif parts[0] == 'stream' and len(parts) == 4:
            domain, region, size_s = parts[1], parts[2], int(parts[3])
            # Simple streaming: generate one batch and feed into profiler
            batch = orch.generate_batch(domain, region, size_s)
            for r in batch:
                profiler.update(r)
            print(f"Streamed {len(batch)} records for {domain} {region}.")
        elif parts[0] == 'show':
            print(profiler.summarize())
            else:
                print("Unknown command. Type 'help'.")


if __name__ == "__main__":
    # Quick start: optional config path argument could be added via argparse
    run_terminal_ui()
