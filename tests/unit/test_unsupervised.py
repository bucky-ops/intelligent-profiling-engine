"""Unit tests for the unsupervised ML helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from profile_system.unsupervised import AnomalyDetection, Clustering


def test_clustering_fit_returns_one_label_per_row():
    df = pd.DataFrame(
        {"amount": [10, 20, 30, 200, 15], "freq": [1, 2, 3, 50, 1]}
    )
    labels = Clustering(n_clusters=2).fit(df)
    assert len(labels) == len(df)


def test_clustering_deterministic_with_random_state():
    df = pd.DataFrame({"x": np.random.RandomState(0).rand(20), "y": np.random.RandomState(1).rand(20)})
    labels_a = Clustering(n_clusters=3).fit(df)
    labels_b = Clustering(n_clusters=3).fit(df)
    np.testing.assert_array_equal(labels_a, labels_b)


def test_anomaly_detection_fit_returns_scores():
    df = pd.DataFrame(
        {"amount": [10, 20, 30, 5000, 15], "freq": [1, 2, 3, 200, 1]}
    )
    scores = AnomalyDetection(contamination=0.1).fit(df)
    assert len(scores) == len(df)


def test_anomaly_detection_predict_returns_minus_one_or_one():
    df = pd.DataFrame(
        {"amount": [10, 20, 30, 5000, 15], "freq": [1, 2, 3, 200, 1]}
    )
    detector = AnomalyDetection(contamination=0.1)
    detector.fit(df)
    preds = detector.predict(df)
    assert set(np.unique(preds)).issubset({-1, 1})
