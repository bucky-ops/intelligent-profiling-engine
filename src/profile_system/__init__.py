"""Intelligent Profiling Engine - core package.

Public API:

    from profile_system import (
        EntityTracker,
        Profile,
        Clustering,
        AnomalyDetection,
        NLPProcessor,
        HITLFeedback,
    )
"""
from .profile import EntityTracker, Profile
from .unsupervised import AnomalyDetection, Clustering
from .nlp import NLPProcessor
from .hitl import HITLFeedback

__all__ = [
    "EntityTracker",
    "Profile",
    "Clustering",
    "AnomalyDetection",
    "NLPProcessor",
    "HITLFeedback",
]

__version__ = "0.2.0"
