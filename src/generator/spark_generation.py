"""Spark-backed Parquet writer for synthetic data."""
import json
from typing import List, Dict, Any, Optional

try:
    from pyspark.sql import SparkSession
    SPARK_AVAILABLE = True
except Exception:
    SPARK_AVAILABLE = False
    SparkSession = None  # type: ignore


def to_parquet_from_records(records: List[Dict[str, Any]], path: str, partitions: Optional[List[str]] = None) -> str:
    """Write records to Parquet using Spark when available, else fall back to JSONL."""
    if SPARK_AVAILABLE:
        spark = SparkSession.builder.appName("SyntheticDataParquetGen").getOrCreate()
        df = spark.createDataFrame(records)
        if partitions:
            df.write.mode("overwrite").partitionBy(*partitions).parquet(path)
        else:
            df.write.mode("overwrite").parquet(path)
        return path
    else:
        # Fallback: JSONL local file
        jsonl_path = path if path.endswith(".jsonl") else path + ".jsonl"
        with open(jsonl_path, 'w', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return jsonl_path
