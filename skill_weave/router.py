"""Core routing engine — the heart of Skill Weave."""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class Skill:
    """A registered skill with metadata and usage history."""

    name: str
    metadata: str = ""
    success_count: int = 0
    total_count: int = 0
    last_used: float = 0.0
    avg_cost: float = 1.0  # normalized 0-1, lower is cheaper
    tags: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 0.5  # untested, assume neutral
        return self.success_count / self.total_count

    def record_use(self, success: bool, cost: float = 1.0) -> None:
        self.total_count += 1
        if success:
            self.success_count += 1
        self.last_used = time.time()
        # exponential moving average for cost
        alpha = 0.3
        self.avg_cost = alpha * cost + (1 - alpha) * self.avg_cost


@dataclass
class RouteResult:
    """A scored skill recommendation."""

    skill: Skill
    score: float
    breakdown: dict[str, float] = field(default_factory=dict)

    def __repr__(self) -> str:
        return f"RouteResult(skill={self.skill.name!r}, score={self.score:.3f})"


class SkillRouter:
    """Multi-dimensional skill router.

    Scores skills along 4 axes: semantic similarity, recency,
    historical success rate, and cost. Returns ranked results.
    """

    def __init__(
        self,
        alpha: float = 0.45,   # semantic weight
        beta: float = 0.20,    # recency weight
        gamma: float = 0.25,   # success rate weight
        delta: float = 0.10,   # cost weight
        decay_half_life: float = 3600.0,  # seconds (1 hour)
        embed_fn: Optional[Callable[[str], list[float]]] = None,
    ):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.delta = delta
        self.decay_half_life = decay_half_life
        self.embed_fn = embed_fn
        self._skills: dict[str, Skill] = {}
        self._embeddings: dict[str, list[float]] = {}

    def register_skill(
        self,
        name: str,
        metadata: str = "",
        tags: list[str] | None = None,
        avg_cost: float = 1.0,
    ) -> Skill:
        skill = Skill(name=name, metadata=metadata, tags=tags or [], avg_cost=avg_cost)
        self._skills[name] = skill
        # pre-compute embedding if provider available
        if self.embed_fn and metadata:
            self._embeddings[name] = self.embed_fn(metadata)
        return skill

    def unregister_skill(self, name: str) -> bool:
        removed = self._skills.pop(name, None)
        self._embeddings.pop(name, None)
        return removed is not None

    @property
    def skills(self) -> dict[str, Skill]:
        return dict(self._skills)

    def route(
        self,
        task: str,
        top_k: int = 5,
        max_cost: Optional[float] = None,
        tags_filter: list[str] | None = None,
    ) -> list[RouteResult]:
        """Route a task to the best-matching skills.

        Args:
            task: Natural language task description.
            top_k: Maximum number of results.
            max_cost: Exclude skills above this cost threshold.
            tags_filter: Only consider skills matching these tags.

        Returns:
            Ranked list of RouteResult.
        """
        if not self._skills:
            return []

        # compute task embedding if available
        task_emb = self.embed_fn(task) if self.embed_fn else None

        results: list[RouteResult] = []
        now = time.time()

        for name, skill in self._skills.items():
            # filter by cost
            if max_cost is not None and skill.avg_cost > max_cost:
                continue
            # filter by tags
            if tags_filter and not any(t in skill.tags for t in tags_filter):
                continue

            scores: dict[str, float] = {}

            # semantic similarity
            if task_emb and name in self._embeddings:
                scores["semantic"] = self._cosine(task_emb, self._embeddings[name])
            else:
                scores["semantic"] = self._keyword_overlap(task, skill.metadata)

            # recency (temporal decay)
            if skill.last_used > 0:
                elapsed = now - skill.last_used
                scores["recency"] = math.exp(-0.693 * elapsed / self.decay_half_life)
            else:
                scores["recency"] = 0.3  # never used, slight bump

            # success rate
            scores["success"] = skill.success_rate

            # cost (inverted — lower cost = higher score)
            scores["cost"] = max(0.0, 1.0 - skill.avg_cost)

            total = (
                self.alpha * scores["semantic"]
                + self.beta * scores["recency"]
                + self.gamma * scores["success"]
                + self.delta * scores["cost"]
            )

            results.append(RouteResult(skill=skill, score=total, breakdown=scores))

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def record_outcome(self, skill_name: str, success: bool, cost: float = 1.0) -> None:
        """Record the outcome of a skill invocation for learning."""
        skill = self._skills.get(skill_name)
        if skill:
            skill.record_use(success, cost)

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _keyword_overlap(query: str, metadata: str) -> float:
        """Character n-gram overlap with CJK-aware tokenization.

        Splits text into 2-grams for CJK and whitespace-delimited tokens
        for Latin text. Handles mixed Chinese-English without external tokenizers.
        """
        def tokenize(text: str) -> set[str]:
            tokens: set[str] = set()
            text = text.lower()
            for word in text.split():
                tokens.add(word)
            for i in range(len(text) - 1):
                bigram = text[i:i+2]
                if any(ord(c) > 127 for c in bigram):
                    tokens.add(bigram)
            return tokens

        q_tokens = tokenize(query)
        m_tokens = tokenize(metadata)
        if not q_tokens or not m_tokens:
            return 0.0
        overlap = q_tokens & m_tokens
        return len(overlap) / max(len(q_tokens), len(m_tokens))
