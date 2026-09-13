"""NLP processor with lazy model loading and embedding caching.

Improvements over the original:
- spaCy and SentenceTransformer models are loaded **on first use**, not at
  construction. This cuts CLI/web-app startup time from several seconds to
  near-zero when NLP features are not used.
- Embeddings are cached by ``hash(text)`` so repeated encoding of the same
  text is free.
- When a model is unavailable we raise a clear ``RuntimeError`` instead of
  silently returning zero vectors that look like real output.
"""
from __future__ import annotations

import threading
from typing import Dict, List, Tuple


class NLPProcessor:
    def __init__(
        self,
        spacy_model: str = "en_core_web_sm",
        embedder_model: str = "all-MiniLM-L6-v2",
    ):
        self._spacy_model_name = spacy_model
        self._embedder_model_name = embedder_model
        self._nlp = None
        self._embedder = None
        self._lock = threading.Lock()
        self._embedding_cache: Dict[int, List[float]] = {}

    # ---------------------------------------------------------- spacy -------
    @property
    def nlp(self):
        if self._nlp is None:
            with self._lock:
                if self._nlp is None:
                    try:
                        import spacy
                    except ImportError as e:
                        raise RuntimeError(
                            "spaCy is not installed. Run `pip install spacy` "
                            "and `python -m spacy download en_core_web_sm`."
                        ) from e
                    try:
                        self._nlp = spacy.load(self._spacy_model_name)
                    except OSError as e:
                        raise RuntimeError(
                            f"spaCy model '{self._spacy_model_name}' not found. "
                            f"Run `python -m spacy download {self._spacy_model_name}`."
                        ) from e
        return self._nlp

    # ----------------------------------------------------- embedder ---------
    @property
    def embedder(self):
        if self._embedder is None:
            with self._lock:
                if self._embedder is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except ImportError as e:
                        raise RuntimeError(
                            "sentence-transformers is not installed. "
                            "Run `pip install sentence-transformers`."
                        ) from e
                    self._embedder = SentenceTransformer(self._embedder_model_name)
        return self._embedder

    # ---------------------------------------------------------- API ----------
    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        results: List[List[float]] = []
        missing: List[Tuple[int, str]] = []
        for i, t in enumerate(texts):
            key = hash(t)
            cached = self._embedding_cache.get(key)
            if cached is not None:
                results.append(cached)
            else:
                results.append([])  # placeholder
                missing.append((i, t))
        if missing:
            new_vecs = self.embedder.encode([t for _, t in missing]).tolist()
            for (i, t), vec in zip(missing, new_vecs):
                self._embedding_cache[hash(t)] = vec
                results[i] = vec
        return results

    def extract_entities(self, text: str) -> List[Tuple[str, str]]:
        doc = self.nlp(text)
        return [(ent.text, ent.label_) for ent in doc.ents]

    def sentiment_analysis(self, text: str) -> Dict[str, float]:
        from textblob import TextBlob  # lazy import
        blob = TextBlob(text)
        return {
            "polarity": blob.sentiment.polarity,
            "subjectivity": blob.sentiment.subjectivity,
        }

    def topic_modeling(self, texts: List[str], n_topics: int = 5) -> Dict[str, str]:
        if not texts:
            return {}
        from sklearn.decomposition import NMF
        from sklearn.feature_extraction.text import TfidfVectorizer

        vectorizer = TfidfVectorizer(stop_words="english", max_features=1000)
        try:
            tfidf = vectorizer.fit_transform(texts)
            nmf = NMF(n_components=min(n_topics, len(texts)), random_state=42)
            nmf.fit(tfidf)
            feature_names = vectorizer.get_feature_names_out()
            topics: Dict[str, str] = {}
            for topic_idx, topic in enumerate(nmf.components_):
                top_words = [feature_names[i] for i in topic.argsort()[:-6:-1]]
                topics[f"Topic {topic_idx + 1}"] = ", ".join(top_words)
            return topics
        except ValueError:
            return {"Topic 1": "Insufficient data"}
