import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler


class Clustering:
    def __init__(self, n_clusters: int = 5):
        self.n_clusters = n_clusters
        self.model = KMeans(n_clusters=n_clusters, random_state=42)
        self.scaler = StandardScaler()

    def fit(self, data: pd.DataFrame):
        scaled_data = self.scaler.fit_transform(data.select_dtypes(include=[np.number]))
        self.model.fit(scaled_data)
        return self.model.labels_

    def predict(self, data: pd.DataFrame):
        scaled_data = self.scaler.transform(data.select_dtypes(include=[np.number]))
        return self.model.predict(scaled_data)


class AnomalyDetection:
    def __init__(self, contamination: float = 0.1):
        self.contamination = contamination
        self.model = IsolationForest(contamination=contamination, random_state=42)

    def fit(self, data: pd.DataFrame):
        numeric_data = data.select_dtypes(include=[np.number])
        self.model.fit(numeric_data)
        return self.model.decision_function(numeric_data)

    def predict(self, data: pd.DataFrame):
        numeric_data = data.select_dtypes(include=[np.number])
        return self.model.predict(numeric_data)  # -1 for anomaly, 1 for normal