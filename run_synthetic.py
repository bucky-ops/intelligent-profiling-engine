#!/usr/bin/env python3
"""Minimal entrypoint to generate synthetic data via config-driven orchestrator.
Usage:
  python run_synthetic.py --config config/global_synthetic_config.yaml --domain finance --region NA --size 1000 --output data/output.jsonl
"""
import argparse
import os
from generator.orchestrator import SyntheticDataOrchestrator


def main():
    parser = argparse.ArgumentParser(description="Global Synthetic Data Generator (MVP)")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    parser.add_argument("--domain", required=True, choices=["finance", "ngo", "telecom", "traffic"])
    parser.add_argument("--region", required=True, help="Region code (e.g., NA, EU, SSA)")
    parser.add_argument("--size", type=int, default=1000, help="Number of records to generate")
    parser.add_argument("--output", default="data/output.jsonl", help="Output path (Parquet/JSONL)")
    args = parser.parse_args()

    # Initialize orchestrator with config path
    orch = SyntheticDataOrchestrator(args.config)
    records = orch.generate_batch(args.domain, args.region, args.size)
    # Simple JSONL write via orchestrator API
    dirname = os.path.dirname(args.output)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    orch.to_parquet(records, args.output)  # will fallback to JSONL if parquet not implemented in orchestrator

if __name__ == "__main__":
    main()
