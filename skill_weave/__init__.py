"""Skill Weave — Adaptive skill routing for multi-agent systems.

Core router: 4-dimension weighted scoring (semantic × recency × success × cost).
Advanced router: 3-stage pipeline (Tree Filter → BM25 → LLM Re-rank).

Production-proven with 138 real-world skills, 95.7% benchmark accuracy.
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
    "annotate_skill",
    "inject_annotations",
    "load_skill_metadata",
]

__version__ = "0.2.0"


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
    raise AttributeError(f"module 'skill_weave' has no attribute {name!r}")
