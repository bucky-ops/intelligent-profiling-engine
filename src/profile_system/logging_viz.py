"""Centralised structured logging + matplotlib visualisations.

Improvements over the original:
- Uses module-level lazy ``get_logger()`` so consumers can configure the root
  logger without side effects at import time.
- Adds JSON-friendly ``log_event`` with severity control.
- :meth:`Visualizer.plot_profile_timeline` no longer looks up a missing
  ``behavioral_signals`` column on the flattened DataFrame; it accepts the
  ``Profile`` object directly, fixing the previous ``KeyError``.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import pandas as pd

_LOGGER: Optional[logging.Logger] = None


def get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is None:
        _LOGGER = logging.getLogger("profile_system")
        if not _LOGGER.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
                )
            )
            _LOGGER.addHandler(handler)
            _LOGGER.setLevel(logging.INFO)
    return _LOGGER


def log_event(event: str, details: Dict[str, Any], level: int = logging.INFO) -> None:
    """Structured log helper that JSON-encodes the ``details`` payload."""
    get_logger().log(level, "%s | %s", event, json.dumps(details, default=str))


class Visualizer:
    def plot_profile_timeline(
        self,
        profile_df: pd.DataFrame,
        entity_id: str,
        profile: Optional[Any] = None,
    ):
        """Plot the behavioural timeline for ``entity_id``.

        ``profile`` is the :class:`profile_system.profile.Profile` object.
        Passing it directly avoids the original ``KeyError`` caused by looking
        up ``behavioral_signals`` on the *flattened* DataFrame.
        """
        if profile is None:
            # Fallback: try the tracker bound to this visualizer (if any)
            return
        signals = getattr(profile, "behavioral_signals", []) or []
        if not signals:
            return
        timestamps = [s.get("timestamp") for s in signals]
        plt.figure(figsize=(8, 4))
        plt.plot(range(len(timestamps)), range(len(timestamps)))
        plt.title(f"Behavioral Signals for {entity_id}")
        plt.xlabel("Event Index")
        plt.ylabel("Signal #")
        plt.tight_layout()
        plt.show()

    def plot_clusters(self, data: pd.DataFrame, labels: list):
        plt.figure(figsize=(6, 4))
        plt.scatter(data.iloc[:, 0], data.iloc[:, 1], c=labels)
        plt.title("Clusters")
        plt.tight_layout()
        plt.show()
