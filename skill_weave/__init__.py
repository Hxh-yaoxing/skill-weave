"""Skill Weave — Adaptive skill routing for multi-agent systems.

Core router: 4-dimension weighted scoring (semantic × recency × success × cost).
Advanced router: 3-stage pipeline (Tree Filter → BM25 → LLM Re-rank).
Active learning: online weight adjustment via bandit + gradient feedback.
Skill weaving: multi-skill DAG orchestration (chains, parallel, conditional).

Production-proven with 141 real-world skills, 95.7% benchmark accuracy.
"""

from .router import Skill, RouteResult, SkillRouter

# Lazy imports for optional heavy dependencies
__all__ = [
    "SkillRouter",
    "SkillWeave",
    "Skill",
    "RouteResult",
    "TreeFilter",
    "BM25Scorer",
    "FeedbackLearner",
    "WeavePlanner",
    "WeaveNode",
    "WeaveEdge",
    "WeaveChain",
    "MergeStrategy",
    "NodeType",
    "annotate_skill",
    "inject_annotations",
    "load_skill_metadata",
    "EmbeddingCache",
    "OllamaEmbedBackend",
    "DifyEmbedBackend",
    "DualEmbedBackend",
    "create_embed_fn",
    "SpineIO",
    "RouteVerifier",
    "VerificationContract",
    "Check",
    "VerificationResult",
    "LoopCard",
    "ArchitectureCard",
    "CardChain",
]

__version__ = "0.4.0"


def __getattr__(name: str):
    if name == "SkillWeave":
        from .advanced import SkillWeave as _SkillWeave
        return _SkillWeave
    if name == "TreeFilter":
        from .advanced import TreeFilter as _TreeFilter
        return _TreeFilter
    if name == "BM25Scorer":
        from .advanced import BM25Scorer as _BM25Scorer
        return _BM25Scorer
    if name in ("annotate_skill", "inject_annotations", "load_skill_metadata"):
        from . import annotate as _annotate
        return getattr(_annotate, name)
    if name == "FeedbackLearner":
        from .learner import FeedbackLearner as _FeedbackLearner
        return _FeedbackLearner
    if name == "SpineIO":
        from .spine import SpineIO as _SpineIO
        return _SpineIO
    if name in ("WeavePlanner", "WeaveNode", "WeaveEdge", "WeaveChain",
                "MergeStrategy", "NodeType"):
        from . import weaver as _weaver
        return getattr(_weaver, name)
    if name in ("RouteVerifier", "VerificationContract", "Check", "VerificationResult"):
        from . import verifier as _verifier
        return getattr(_verifier, name)
    if name in ("LoopCard", "ArchitectureCard", "CardChain"):
        from . import card as _card
        return getattr(_card, name)
    raise AttributeError(f"module 'skill_weave' has no attribute {name!r}")
