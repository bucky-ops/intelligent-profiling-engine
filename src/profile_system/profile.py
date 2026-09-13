"""Profile + EntityTracker with batched (write-behind) persistence.

The original implementation rewrote the entire ``profiles.json`` file on every
single ``update_profile`` call - an O(N) disk write per signal that becomes
catastrophic at scale. We now:
- buffer updates in memory,
- flush to disk on a debounce (default 2 seconds) or when the buffer hits
  ``flush_threshold`` updates,
- register an ``atexit`` handler so nothing is lost on process exit.
"""
from __future__ import annotations

import atexit
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Profile:
    def __init__(self, entity_id: str):
        self.entity_id = entity_id
        self.static_attributes: Dict[str, Any] = {}
        self.behavioral_signals: List[Dict[str, Any]] = []
        self.temporal_patterns: Dict[str, Any] = {}
        self.text_insights: Dict[str, Any] = {}
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)

    def update_static(self, attributes: Dict[str, Any]):
        self.static_attributes.update(attributes)
        self.updated_at = datetime.now(timezone.utc)

    def add_behavioral_signal(self, signal: Dict[str, Any]):
        if "timestamp" not in signal:
            signal["timestamp"] = _now_iso()
        self.behavioral_signals.append(signal)
        self.updated_at = datetime.now(timezone.utc)

    def update_temporal(self, patterns: Dict[str, Any]):
        self.temporal_patterns.update(patterns)
        self.updated_at = datetime.now(timezone.utc)

    def add_text_insight(self, insight: Dict[str, Any]):
        self.text_insights.update(insight)
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
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
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        profile = cls(data["entity_id"])
        profile.static_attributes = data.get("static_attributes", {})
        profile.behavioral_signals = data.get("behavioral_signals", [])
        profile.temporal_patterns = data.get("temporal_patterns", {})
        profile.text_insights = data.get("text_insights", {})
        if "created_at" in data:
            profile.created_at = _parse_dt(data["created_at"])
        if "updated_at" in data:
            profile.updated_at = _parse_dt(data["updated_at"])
        return profile


def _parse_dt(value: str) -> datetime:
    """Parse an ISO timestamp, tolerating both naive and aware variants."""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


class EntityTracker:
    """In-memory profile store with debounced disk persistence.

    Parameters
    ----------
    storage_file:
        Path to the JSON file used for persistence.
    debounce_seconds:
        Maximum delay before pending updates are flushed.
    flush_threshold:
        If the number of pending updates reaches this number, flush early.
    auto_flush:
        When ``True`` (default) register an ``atexit`` handler so pending
        writes are not lost on interpreter exit.
    """

    def __init__(
        self,
        storage_file: str = "profiles.json",
        debounce_seconds: float = 2.0,
        flush_threshold: int = 50,
        auto_flush: bool = True,
    ):
        self.storage_file = storage_file
        self.profiles: Dict[str, Profile] = {}
        self._debounce_seconds = debounce_seconds
        self._flush_threshold = flush_threshold
        self._dirty = 0
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.RLock()
        self.load_profiles()
        if auto_flush:
            atexit.register(self.save_profiles)

    # ----------------------------------------------------- persistence -----
    def load_profiles(self):
        if not os.path.exists(self.storage_file):
            return
        try:
            with open(self.storage_file, "r") as f:
                data = json.load(f)
                for pid, pdata in data.items():
                    self.profiles[pid] = Profile.from_dict(pdata)
        except Exception as e:
            # Use the structured logger if it has been initialised.
            try:
                from profile_system.logging_viz import get_logger
                get_logger().error("Error loading profiles: %s", e)
            except Exception:
                print(f"Error loading profiles: {e}")

    def save_profiles(self):
        """Flush all profiles to disk immediately and cancel any pending timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
            data = {pid: p.to_dict() for pid, p in self.profiles.items()}
            self._dirty = 0
        try:
            tmp = self.storage_file + ".tmp"
            with open(tmp, "w") as f:
                json.dump(data, f, indent=4, default=str)
            os.replace(tmp, self.storage_file)
        except Exception as e:
            try:
                from profile_system.logging_viz import get_logger
                get_logger().error("Error saving profiles: %s", e)
            except Exception:
                print(f"Error saving profiles: {e}")

    def _schedule_flush(self):
        """Debounce writes: flush after ``_debounce_seconds`` of inactivity."""
        if self._timer is not None:
            self._timer.cancel()
        self._timer = threading.Timer(self._debounce_seconds, self.save_profiles)
        self._timer.daemon = True
        self._timer.start()

    def _mark_dirty(self):
        self._dirty += 1
        if self._dirty >= self._flush_threshold:
            self.save_profiles()
        else:
            self._schedule_flush()

    # ---------------------------------------------------- mutations --------
    def get_or_create_profile(self, entity_id: str) -> Profile:
        with self._lock:
            if entity_id not in self.profiles:
                self.profiles[entity_id] = Profile(entity_id)
                self._mark_dirty()
            return self.profiles[entity_id]

    def update_profile(self, entity_id: str, data: Dict[str, Any]):
        profile = self.get_or_create_profile(entity_id)
        if "static" in data:
            profile.update_static(data["static"])
        if "behavioral" in data:
            profile.add_behavioral_signal(data["behavioral"])
        if "temporal" in data:
            profile.update_temporal(data["temporal"])
        if "text" in data:
            profile.add_text_insight(data["text"])
        self._mark_dirty()

    # ------------------------------------------------- analytics -----------
    def detect_changes(self, entity_id: str) -> Dict[str, Any]:
        """Detect recent activity changes for ``entity_id``.

        Returns a dict with ``recent_signals`` count and an ``anomalies``
        flag based on a configurable threshold (default 10 signals/week).
        """
        profile = self.profiles.get(entity_id)
        if not profile:
            return {}
        recent_signals = 0
        now = datetime.now(timezone.utc)
        for s in profile.behavioral_signals:
            ts = s.get("timestamp")
            if isinstance(ts, str):
                ts = _parse_dt(ts)
            if ts is None:
                continue
            try:
                if (now - ts).days < 7:
                    recent_signals += 1
            except TypeError:
                # Mixing tz-aware and naive datetimes - skip.
                continue
        return {"recent_signals": recent_signals, "anomalies": recent_signals > 10}

    def get_profiles_df(self) -> "pd.DataFrame":  # type: ignore[name-defined]
        """Flatten profiles into a DataFrame suitable for ML.

        ``pandas`` is imported lazily so that the core module remains
        importable in environments without pandas installed.
        """
        import pandas as pd  # noqa: F811

        data_list = []
        for p in self.profiles.values():
            row: Dict[str, Any] = {"entity_id": p.entity_id}
            amounts = [s.get("amount", 0) for s in p.behavioral_signals if "amount" in s]
            row["total_amount"] = sum(amounts)
            row["avg_amount"] = sum(amounts) / len(amounts) if amounts else 0
            row["signal_count"] = len(p.behavioral_signals)
            if "age" in p.static_attributes:
                row["age"] = p.static_attributes["age"]
            sentiment = p.text_insights.get("sentiment", {})
            row["sentiment_polarity"] = sentiment.get("polarity", 0)
            row["sentiment_subjectivity"] = sentiment.get("subjectivity", 0)
            data_list.append(row)
        return pd.DataFrame(data_list)
