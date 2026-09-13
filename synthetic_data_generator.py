"""
Global Synthetic Big Data Generator
====================================

This module generates large-scale, anonymized synthetic data for finance, NGO, telecom, and traffic systems.
Designed for profiling algorithms using unsupervised learning, NLP, and Human-in-the-Loop (HITL) validation.

Features:
- Multi-domain data modeling
- Global regional simulation
- NLP-optimized synthetic text
- Profiling-ready schema
- Spark/Hadoop compatible
- Streaming/micro-batch support
- Privacy-by-design anonymization

Privacy Guarantee: This dataset is fully synthetic and GDPR-style anonymized by design.
No real personal data is used or generated.
"""

import uuid
import random
import hashlib
from datetime import datetime, timedelta
import json
from typing import Dict, List, Iterator

# For Spark compatibility, assume PySpark is available
try:
    from pyspark.sql import SparkSession, DataFrame
    from pyspark.sql.types import (
        StructType, StructField, StringType, DoubleType, BooleanType,
    )
    SPARK_AVAILABLE = True
except ImportError:
    SPARK_AVAILABLE = False
    print("PySpark not available. Running in local mode.")

# Faker for synthetic text (install via pip)
try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False
    print("Faker not available. Using basic text generation.")

class SyntheticDataGenerator:
    def __init__(self, spark_session=None):
        self.regions = {
            "NA": {"name": "North America", "countries": ["US", "CA", "MX"], "behavior_multiplier": 1.2},
            "EU": {"name": "Europe", "countries": ["DE", "FR", "UK"], "behavior_multiplier": 0.9},
            "SSA": {"name": "Sub-Saharan Africa", "countries": ["NG", "ZA", "KE"], "behavior_multiplier": 0.7},
            "ME": {"name": "Middle East", "countries": ["SA", "AE", "IL"], "behavior_multiplier": 1.1},
            "SA": {"name": "South Asia", "countries": ["IN", "PK", "BD"], "behavior_multiplier": 0.8},
            "EA": {"name": "East Asia", "countries": ["CN", "JP", "KR"], "behavior_multiplier": 1.3},
            "LA": {"name": "Latin America", "countries": ["BR", "AR", "MX"], "behavior_multiplier": 1.0}
        }
        self.domains = ["finance", "ngo", "telecom", "traffic"]
        self.spark = spark_session or (SparkSession.builder.appName("SyntheticDataGen").getOrCreate() if SPARK_AVAILABLE else None)
        self.faker = Faker() if FAKER_AVAILABLE else None

    def generate_entity_id(self) -> str:
        return str(uuid.uuid4())

    def generate_profile_id(self, entity_id: str) -> str:
        return hashlib.sha256(entity_id.encode()).hexdigest()[:16]

    def get_region_data(self, region_code: str) -> Dict:
        return self.regions.get(region_code, self.regions["NA"])

    def generate_nlp_text(self, domain: str, event_type: str) -> str:
        templates = {
            "finance": {
                "transaction": "Transaction processed for amount {amount} via {channel}. Note: {note}",
                "risk_event": "Irregular activity detected during {time} settlement window",
                "compliance": "Compliance check passed for account {id} with score {score}"
            },
            "ngo": {
                "aid_event": "Aid distribution completed for program {program}. Feedback: {feedback}",
                "beneficiary": "Beneficiary registered with vulnerability index {index}",
                "report": "Field report indicates {issue} affecting {count} individuals"
            },
            "telecom": {
                "usage": "Session duration {duration} minutes in cluster {cluster}",
                "alert": "Service alert: {issue} reported by subscriber {id}",
                "support": "Support ticket: Intermittent {problem} in high-density area"
            },
            "traffic": {
                "incident": "Traffic incident: {description} near junction {junction}",
                "sensor": "Sensor data shows congestion level {level} at speed {speed}",
                "vehicle": "Vehicle tracked with speed index {index} in cluster {cluster}"
            }
        }
        template = random.choice(list(templates.get(domain, {}).values()))
        if self.faker:
            return self.faker.text(max_nb_chars=200)  # Use faker for varied text
        else:
            return template.format(
                amount=random.uniform(10, 10000),
                channel=random.choice(["online", "ATM", "mobile"]),
                note="standard processing",
                time=random.choice(["morning", "evening", "night"]),
                id="SYN" + str(random.randint(1000, 9999)),
                score=random.uniform(0.1, 1.0),
                program=random.choice(["food", "medical", "education"]),
                feedback="positive community response",
                issue="logistical delay",
                count=random.randint(50, 500),
                index=random.uniform(0.1, 1.0),
                duration=random.randint(1, 120),
                cluster="CL" + str(random.randint(100, 999)),
                problem=random.choice(["signal loss", "data drop"]),
                description="recurring congestion",
                junction="JCT-" + str(random.randint(1, 50)),
                level=random.choice(["low", "medium", "high"]),
                speed=random.randint(20, 100)
            )

    def generate_record(self, domain: str, region: str, entity_id: str = None) -> Dict:
        if not entity_id:
            entity_id = self.generate_entity_id()
        profile_id = self.generate_profile_id(entity_id)
        region_data = self.get_region_data(region)
        country = random.choice(region_data["countries"])
        event_type = random.choice(["transaction", "aid_event", "usage", "incident"])  # Domain-specific
        multiplier = region_data["behavior_multiplier"]

        # Domain-specific metrics
        if domain == "finance":
            numeric_metrics = {
                "transaction_amount": random.uniform(10, 10000) * multiplier,
                "risk_score": random.uniform(0.1, 1.0),
                "anomaly_flag": random.choice([True, False]),
                "payment_channel": random.choice(["online", "ATM", "mobile"])
            }
        elif domain == "ngo":
            numeric_metrics = {
                "resource_allocation_score": random.uniform(0.1, 1.0) * multiplier,
                "vulnerability_index": random.uniform(0.1, 1.0),
                "program_type": random.choice(["food", "medical", "shelter"])
            }
        elif domain == "telecom":
            numeric_metrics = {
                "session_duration": random.randint(1, 120) * multiplier,
                "cell_cluster_id": "CL" + str(random.randint(100, 999)),
                "quality_score": random.uniform(0.1, 1.0)
            }
        elif domain == "traffic":
            numeric_metrics = {
                "speed_index": random.randint(20, 100) * multiplier,
                "congestion_level": random.choice([1, 2, 3]),
                "sensor_cluster": "SC" + str(random.randint(100, 999))
            }
        else:
            numeric_metrics = {}

        # Behavioral flags for profiling
        behavioral_flags = {
            "high_activity": random.choice([True, False]),
            "anomaly_detected": random.choice([True, False]),
            "drift_signal": random.uniform(0.0, 1.0)
        }

        # HITL hooks
        human_review_flag = random.random() < 0.1  # 10% flagged for review
        confidence_score = random.uniform(0.5, 1.0)
        review_notes_placeholder = "" if not human_review_flag else "Pending analyst review"

        timestamp = datetime.now() - timedelta(days=random.randint(0, 365))

        return {
            "entity_id": entity_id,
            "domain": domain,
            "region": region,
            "synthetic_country": country,
            "event_type": event_type,
            "numeric_metrics": json.dumps(numeric_metrics),
            "behavioral_flags": json.dumps(behavioral_flags),
            "text_payload": self.generate_nlp_text(domain, event_type),
            "timestamp": timestamp.isoformat(),
            "profile_id": profile_id,
            "human_review_flag": human_review_flag,
            "confidence_score": confidence_score,
            "review_notes_placeholder": review_notes_placeholder
        }

    def generate_batch(self, domain: str, region: str, size: int) -> List[Dict]:
        """Generate a batch of records for local processing."""
        return [self.generate_record(domain, region) for _ in range(size)]

    def generate_streaming_batch(self, domain: str, region: str, size: int) -> Iterator[Dict]:
        """Generator for streaming/micro-batch simulation."""
        for _ in range(size):
            yield self.generate_record(domain, region)

    def to_spark_df(self, records: List[Dict]) -> DataFrame:
        if not SPARK_AVAILABLE:
            raise ImportError("PySpark required for DataFrame conversion")
        schema = StructType([
            StructField("entity_id", StringType(), True),
            StructField("domain", StringType(), True),
            StructField("region", StringType(), True),
            StructField("synthetic_country", StringType(), True),
            StructField("event_type", StringType(), True),
            StructField("numeric_metrics", StringType(), True),
            StructField("behavioral_flags", StringType(), True),
            StructField("text_payload", StringType(), True),
            StructField("timestamp", StringType(), True),
            StructField("profile_id", StringType(), True),
            StructField("human_review_flag", BooleanType(), True),
            StructField("confidence_score", DoubleType(), True),
            StructField("review_notes_placeholder", StringType(), True)
        ])
        return self.spark.createDataFrame(records, schema)

    def save_to_parquet(self, df: DataFrame, path: str):
        df.write.mode("overwrite").parquet(path)
        print(f"Saved to Parquet: {path}")

    def save_to_jsonl(self, records: List[Dict], path: str):
        with open(path, 'w') as f:
            for record in records:
                f.write(json.dumps(record) + '\n')
        print(f"Saved to JSONL: {path}")

# Example usage
if __name__ == "__main__":
    gen = SyntheticDataGenerator()
    # Generate sample for finance in NA
    records = gen.generate_batch("finance", "NA", 100)
    print("Sample record:")
    print(json.dumps(records[0], indent=2))
    # Save locally
    gen.save_to_jsonl(records, "data/synthetic_finance_na.jsonl")
    # For Spark: gen.to_spark_df(records).show()
    print("Generator ready for big data scaling.")

# Scaling Instructions:
# - For millions: Use Spark with gen.to_spark_df() and repartition.
# - For billions: Distribute across cluster, adjust size parameter.
# - New regions: Add to self.regions dict.
# - New domains: Extend generate_record logic.
# - HITL: Inject feedback by updating records post-generation.
# - Streaming: Use generate_streaming_batch with Kafka producer integration.