import logging
import matplotlib.pyplot as plt
import pandas as pd
from typing import Dict

# Set up logging
logging.basicConfig(filename='profile_system.log', level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def log_event(event: str, details: Dict):
    logging.info(f"{event}: {details}")

class Visualizer:
    def plot_profile_timeline(self, profile_df: pd.DataFrame, entity_id: str):
        profile = profile_df[profile_df['entity_id'] == entity_id]
        if profile.empty:
            return
        # Dummy plot: number of behavioral signals over time
        signals = profile.iloc[0]['behavioral_signals']
        if signals:
            timestamps = [s.get('timestamp') for s in signals]
            plt.plot(timestamps, range(len(timestamps)))
            plt.title(f"Behavioral Signals for {entity_id}")
            plt.show()

    def plot_clusters(self, data: pd.DataFrame, labels: list):
        plt.scatter(data.iloc[:, 0], data.iloc[:, 1], c=labels)
        plt.title("Clusters")
        plt.show()