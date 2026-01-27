import spacy
from textblob import TextBlob
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import NMF

class NLPProcessor:
    def __init__(self):
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            print("⚠ Spacy model not found. Run `python -m spacy download en_core_web_sm`.")
            self.nlp = None
            
        try:
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except Exception as e:
            print(f"⚠ Could not load SentenceTransformer: {e}")
            self.embedder = None

    def get_embeddings(self, texts: list) -> list:
        if self.embedder:
            return self.embedder.encode(texts).tolist()
        return [[0.0] * 384 for _ in texts] 

    def extract_entities(self, text: str) -> list:
        if not self.nlp:
            return []
        doc = self.nlp(text)
        return [(ent.text, ent.label_) for ent in doc.ents]

    def sentiment_analysis(self, text: str) -> dict:
        blob = TextBlob(text)
        return {"polarity": blob.sentiment.polarity, "subjectivity": blob.sentiment.subjectivity}

    def topic_modeling(self, texts: list, n_topics=5) -> dict:
        if not texts:
            return {}
        
        # Use NMF for topic modeling
        vectorizer = TfidfVectorizer(stop_words='english', max_features=1000)
        try:
            tfidf = vectorizer.fit_transform(texts)
            nmf = NMF(n_components=min(n_topics, len(texts)), random_state=42)
            nmf.fit(tfidf)
            
            feature_names = vectorizer.get_feature_names_out()
            topics = {}
            for topic_idx, topic in enumerate(nmf.components_):
                top_words = [feature_names[i] for i in topic.argsort()[:-6:-1]]
                topics[f"Topic {topic_idx+1}"] = ", ".join(top_words)
            return topics
        except ValueError:
            # Fallback if too few documents
            return {"Topic 1": "Insufficient data"}