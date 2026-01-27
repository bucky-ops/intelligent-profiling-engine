import pandas as pd
import json
import os
from datetime import datetime
from typing import Dict, List, Any


class Profile:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.static_attributes: Dict[str, Any] = {}
        self.behavioral_signals: List[Dict] = []
        self.temporal_patterns: Dict[str, Any] = {}
        self.text_insights: Dict[str, Any] = {}
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    def update_static(self, attributes: Dict[str, Any]):
        self.static_attributes.update(attributes)
        self.updated_at = datetime.now()

    def add_behavioral_signal(self, signal: Dict):
        # Ensure timestamp is present
        if "timestamp" not in signal:
            signal["timestamp"] = datetime.now().isoformat()
        self.behavioral_signals.append(signal)
        self.updated_at = datetime.now()

    def update_temporal(self, patterns: Dict[str, Any]):
        self.temporal_patterns.update(patterns)
        self.updated_at = datetime.now()

    def add_text_insight(self, insight: Dict):
        self.text_insights.update(insight)
        self.updated_at = datetime.now()

    def to_dict(self) -> Dict:
        return {
            "entity_id": self.entity_id,
            "static_attributes": self.static_attributes,
            "behavioral_signals": self.behavioral_signals,
            "temporal_patterns": self.temporal_patterns,
            "text_insights": self.text_insights,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict):
        profile = cls(data["entity_id"])
        profile.static_attributes = data.get("static_attributes", {})
        profile.behavioral_signals = data.get("behavioral_signals", [])
        profile.temporal_patterns = data.get("temporal_patterns", {})
        profile.text_insights = data.get("text_insights", {})
        if "created_at" in data:
            profile.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            profile.updated_at = datetime.fromisoformat(data["updated_at"])
        return profile


class EntityTracker:
    def __init__(self, storage_file="profiles.json"):
        self.storage_file = storage_file
        self.profiles: Dict[str, Profile] = {}
        self.load_profiles()

    def load_profiles(self):
        if os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, 'r') as f:
                    data = json.load(f)
                    for pid, pdata in data.items():
                        self.profiles[pid] = Profile.from_dict(pdata)
            except Exception as e:
                print(f"Error loading profiles: {e}")

    def save_profiles(self):
        data = {pid: p.to_dict() for pid, p in self.profiles.items()}
        try:
            with open(self.storage_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def get_or_create_profile(self, entity_id: str) -> Profile:
        if entity_id not in self.profiles:
            self.profiles[entity_id] = Profile(entity_id)
            self.save_profiles()
        return self.profiles[entity_id]

    def update_profile(self, entity_id: str, data: Dict):
        profile = self.get_or_create_profile(entity_id)
        if "static" in data:
            profile.update_static(data["static"])
        if "behavioral" in data:
            profile.add_behavioral_signal(data["behavioral"])
        if "temporal" in data:
            profile.update_temporal(data["temporal"])
        if "text" in data:
            profile.add_text_insight(data["text"])
        self.save_profiles()

    def detect_changes(self, entity_id: str) -> Dict:
        # Placeholder for change detection logic
        profile = self.profiles.get(entity_id)
        if not profile:
            return {}
        # Simple example: check if behavioral signals increased
        recent_signals = 0
        now = datetime.now()
        for s in profile.behavioral_signals:
            ts = s.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts)
            if (now - ts).days < 7:
                recent_signals += 1
                
        return {"anomalies": recent_signals > 10} 

    def get_profiles_df(self) -> pd.DataFrame:
        """Flatten profiles into a format suitable for ML."""
        data_list = []
        for p in self.profiles.values():
            # Base data
            row = {"entity_id": p.entity_id}
            
            # 1. Aggregate Behavioral Signals
            # Currently assuming signals might have 'amount' or 'frequency'
            amounts = [s.get("amount", 0) for s in p.behavioral_signals if "amount" in s]
            row["total_amount"] = sum(amounts)
            row["avg_amount"] = sum(amounts) / len(amounts) if amounts else 0
            row["signal_count"] = len(p.behavioral_signals)
            
            # 2. Flatten Static Attributes (only numeric for now or encode later)
            # For simplicity, we'll just take known numeric statics if they exist
            if "age" in p.static_attributes:
                row["age"] = p.static_attributes["age"]
            
            # 3. Text Insights (e.g. sentiment)
            # Assuming format: {'sentiment': {'polarity': 0.1, ...}}
            sentiment = p.text_insights.get("sentiment", {})
            row["sentiment_polarity"] = sentiment.get("polarity", 0)
            row["sentiment_subjectivity"] = sentiment.get("subjectivity", 0)

            data_list.append(row)
            
        return pd.DataFrame(data_list)