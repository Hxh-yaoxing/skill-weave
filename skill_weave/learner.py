"""Active learning engine — closes the feedback loop.

Records routing decisions → execution outcomes → dynamically adjusts weights
and per-skill scores. Converts passive routing into a self-improving system.

Theoretical foundation: multi-armed bandit (Upper Confidence Bound) for skill
selection + gradient-informed weight adjustment for 4-dimension scoring.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from .router import SkillRouter, Skill


@dataclass
class RouteRecord:
    """A single routing decision + outcome."""

    skill_name: str
    task: str
    score: float
    success: bool
    latency_ms: float
    timestamp: float = field(default_factory=time.time)


class FeedbackLearner:
    """Online learning wrapper that tunes routing over time.

    Two learning mechanisms:
    1. **UCB bandit** — balances exploration vs exploitation per skill
    2. **Weight gradient** — adjusts α,β,γ,δ toward dimensions that predict success

    Usage:
        router = SkillRouter()
        learner = FeedbackLearner(router)

        results = learner.route("deploy to production")
        # ... execute the selected skill ...
        learner.record("deploy", success=True, latency_ms=450)

        # Weights auto-adjust. Next route uses updated scores.
    """

    def __init__(
        self,
        router: SkillRouter,
        exploration_bonus: float = 2.0,  # UCB exploration factor
        weight_learning_rate: float = 0.05,
        min_samples_for_learning: int = 5,
    ):
        self.router = router
        self.exploration_bonus = exploration_bonus
        self.weight_learning_rate = weight_learning_rate
        self.min_samples_for_learning = min_samples_for_learning

        # History
        self._records: list[RouteRecord] = []

        # Per-dimension success tracking (for weight adjustment)
        self._dim_success_counts: dict[str, float] = defaultdict(float)
        self._dim_total_counts: dict[str, float] = defaultdict(float)

        # Total interactions (for UCB)
        self.total_routes = 0

        # Snapshot of original weights for reset capability
        self._original_weights = (router.alpha, router.beta, router.gamma, router.delta)

    @property
    def records(self) -> list[RouteRecord]:
        return list(self._records)

    def route(
        self,
        task: str,
        top_k: int = 5,
        explore: bool = True,
        **kwargs,
    ) -> list:
        """Route with optional UCB exploration boost.

        When explore=True, skills with few attempts get a bonus score
        proportional to sqrt(log(N) / n_i) — classic UCB bandit.
        """
        results = self.router.route(task, top_k=top_k, **kwargs)

        if not explore or self.total_routes < self.min_samples_for_learning:
            return results

        # Apply UCB bonus to encourage exploration
        for r in results:
            skill = r.skill
            if skill.total_count > 0:
                exploration_bonus = self.exploration_bonus * math.sqrt(
                    math.log(self.total_routes + 1) / skill.total_count
                )
                # Blend UCB bonus with original score
                r.score = r.score * 0.7 + min(exploration_bonus, 0.3) * 0.3

        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def record(
        self,
        skill_name: str,
        task: str,
        success: bool,
        latency_ms: float = 0,
        dimension_contributions: dict[str, float] | None = None,
    ) -> None:
        """Record a routing outcome and trigger learning.

        Args:
            skill_name: The skill that was executed
            task: Original task description
            success: Whether the execution succeeded
            latency_ms: Execution time
            dimension_contributions: Optional per-dimension contribution scores
                e.g., {"semantic": 0.8, "recency": 0.3, ...}
                Used to adjust weights toward dimensions that predict success.
        """
        # Record in the underlying router
        self.router.record_outcome(skill_name, success)

        # Store detailed record
        record = RouteRecord(
            skill_name=skill_name,
            task=task,
            score=0.0,  # filled below if available
            success=success,
            latency_ms=latency_ms,
        )
        self._records.append(record)
        self.total_routes += 1

        # Cap history at 1000 records to prevent memory leak
        if len(self._records) >= 1000:
            self._records = self._records[-500:]

        # Learn from dimension contributions if provided
        if dimension_contributions and self.total_routes >= self.min_samples_for_learning:
            self._adjust_weights(dimension_contributions, success)

    def _adjust_weights(
        self, contributions: dict[str, float], success: bool
    ) -> None:
        """Gradient-informed weight adjustment.

        Dimensions that contribute highly to successful routes get weight increase.
        Dimensions that contribute highly to failed routes get weight decrease.
        """
        # Map dimension names to weight attributes
        dim_to_attr = {
            "semantic": "alpha",
            "recency": "beta",
            "success": "gamma",
            "cost": "delta",
        }

        for dim, contribution in contributions.items():
            if dim not in dim_to_attr:
                continue
            self._dim_total_counts[dim] += 1
            if success:
                self._dim_success_counts[dim] += contribution

        # Only adjust when we have enough data
        if self._dim_total_counts["semantic"] < self.min_samples_for_learning:
            return

        # Calculate reliability of each dimension
        reliabilities = {}
        for dim in dim_to_attr:
            total = self._dim_total_counts[dim]
            if total > 0:
                reliabilities[dim] = self._dim_success_counts[dim] / total
            else:
                reliabilities[dim] = 0.5  # neutral

        # Normalize to sum to 1.0
        total_rel = sum(reliabilities.values()) or 1.0
        for dim in reliabilities:
            reliabilities[dim] /= total_rel

        # Smooth toward reliability scores
        lr = self.weight_learning_rate
        for dim, attr in dim_to_attr.items():
            current = getattr(self.router, attr)
            target = reliabilities[dim]
            new_weight = current * (1 - lr) + target * lr
            setattr(self.router, dim_to_attr[dim], new_weight)

    def stats(self) -> dict:
        """Current learning state."""
        if not self._records:
            return {"status": "no data", "total_routes": 0}

        recent = self._records[-50:] if len(self._records) >= 50 else self._records
        recent_success = sum(1 for r in recent if r.success) / len(recent)

        return {
            "total_routes": self.total_routes,
            "recent_success_rate": round(recent_success, 3),
            "weights": {
                "alpha": round(self.router.alpha, 4),
                "beta": round(self.router.beta, 4),
                "gamma": round(self.router.gamma, 4),
                "delta": round(self.router.delta, 4),
            },
            "per_dimension_success": {
                dim: round(
                    self._dim_success_counts[dim] / max(self._dim_total_counts[dim], 1), 3
                )
                for dim in ["semantic", "recency", "success", "cost"]
            },
            "record_count": len(self._records),
        }

    def reset(self) -> None:
        """Reset all learned weights to original values."""
        self.router.alpha, self.router.beta, self.router.gamma, self.router.delta = (
            self._original_weights
        )
        self._records.clear()
        self._dim_success_counts.clear()
        self._dim_total_counts.clear()
        self.total_routes = 0
