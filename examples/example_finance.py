import sys
sys.path.append('src')

from profile_system.profile import EntityTracker
from profile_system.unsupervised import Clustering, AnomalyDetection
from profile_system.nlp import NLPProcessor
from profile_system.hitl import HITLFeedback
import pandas as pd

# Dummy finance data
data = pd.DataFrame({
    'entity_id': ['user1', 'user2', 'user3'],
    'amount': [100, 500, 1000],
    'frequency': [1, 5, 10]
})

# Initialize components
tracker = EntityTracker()
nlp = NLPProcessor()
hitl = HITLFeedback()

# Create profiles
for _, row in data.iterrows():
    tracker.update_profile(row['entity_id'], {
        'static': {'name': row['entity_id']},
        'behavioral': {'amount': row['amount'], 'frequency': row['frequency']}
    })

# Add text insight
texts = ["User made a large purchase", "Frequent small transactions"]
embeddings = nlp.get_embeddings(texts)
tracker.update_profile('user1', {'text': {'embeddings': embeddings[0], 'sentiment': nlp.sentiment_analysis(texts[0])}})

# Clustering
clustering = Clustering(n_clusters=2)
labels = clustering.fit(data[['amount', 'frequency']])
print("Cluster labels:", labels)

# Anomaly detection
anomaly = AnomalyDetection()
scores = anomaly.fit(data[['amount', 'frequency']])
print("Anomaly scores:", scores)

# HITL: Add validation
hitl.add_validation({'entity_id': 'user1', 'validated': True, 'notes': 'Legitimate user'})

print("Profiles created successfully.")