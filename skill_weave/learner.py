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
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from .router import SkillRouter, Skill
from .verifier import RouteVerifier, VerificationResult


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
        # Staleness detection params
        staleness_enabled: bool = True,
        staleness_window: int = 50,
        staleness_threshold: float = 0.3,
        staleness_penalty: float = 0.1,
        staleness_recheck_interval: int = 20,
        staleness_recheck_seconds: float = 300.0,
        # Warm start params
        warm_start_enabled: bool = True,
        warm_start_min_samples: int = 10,
        # Verifier (optional)
        verifier: RouteVerifier | None = None,
    ):
        self.router = router
        self.exploration_bonus = exploration_bonus
        self.weight_learning_rate = weight_learning_rate
        self.min_samples_for_learning = min_samples_for_learning
        self.verifier = verifier

        # History
        self._records: list[RouteRecord] = []

        # Per-dimension success tracking (for weight adjustment)
        self._dim_success_counts: dict[str, float] = defaultdict(float)
        self._dim_total_counts: dict[str, float] = defaultdict(float)

        # Total interactions (for UCB)
        self.total_routes = 0

        # Snapshot of original weights for reset capability
        self._original_weights = (router.alpha, router.beta, router.gamma, router.delta)

        # Staleness detection state
        self._staleness_enabled = staleness_enabled
        self._staleness_window_size = staleness_window
        self._staleness_threshold = staleness_threshold
        self._staleness_penalty = staleness_penalty
        self._staleness_recheck_interval = staleness_recheck_interval
        self._staleness_recheck_seconds = staleness_recheck_seconds
        self._staleness_window: deque[tuple[str, bool]] = deque(maxlen=staleness_window)
        self._stale_skills: set[str] = set()
        self._last_staleness_check: float = time.time()
        self._routes_since_staleness_check: int = 0

        # Warm start state
        self._warm_start_enabled = warm_start_enabled
        self._warm_start_min_samples = warm_start_min_samples
        self._warm_start_data: dict[str, dict] = {}  # skill_name -> inherited data

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
            # Still apply staleness penalty even when not exploring
            if self._staleness_enabled:
                for r in results:
                    if r.skill.name in self._stale_skills:
                        r.score *= self._staleness_penalty
                results.sort(key=lambda r: r.score, reverse=True)
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

            # Apply staleness penalty
            if self._staleness_enabled and skill.name in self._stale_skills:
                r.score *= self._staleness_penalty

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

        # Staleness detection: push to sliding window and maybe re-evaluate
        if self._staleness_enabled:
            self._staleness_window.append((skill_name, success))
            self._routes_since_staleness_check += 1
            if (
                self._routes_since_staleness_check >= self._staleness_recheck_interval
                or (time.time() - self._last_staleness_check) >= self._staleness_recheck_seconds
            ):
                self._evaluate_staleness()

        # Learn from dimension contributions if provided
        if dimension_contributions and self.total_routes >= self.min_samples_for_learning:
            self._adjust_weights(dimension_contributions, success)

        # Warm start: discard inherited data once enough real samples
        if self._warm_start_enabled and skill_name in self._warm_start_data:
            skill = self.router.skills.get(skill_name)
            if skill and skill.total_count >= self._warm_start_min_samples:
                del self._warm_start_data[skill_name]

    def record_verified(
        self,
        skill_name: str,
        task: str,
        output: str,
        checks: list[str],
        latency_ms: float = 0,
        dimension_contributions: dict[str, float] | None = None,
    ) -> VerificationResult:
        """Record a routing outcome after verification.

        Uses the verifier to independently check the output, then records
        the verifier's conclusion instead of trusting the caller's self-report.

        If no verifier is configured, falls back to trusting the caller
        (backward compatible).

        Args:
            skill_name: The skill that was executed.
            task: Original task description.
            output: The output produced by the skill.
            checks: List of assertion strings for the verifier to check.
            latency_ms: Execution time.
            dimension_contributions: Optional per-dimension contribution scores.

        Returns:
            VerificationResult with pass/fail verdict and evidence.
        """
        if self.verifier:
            result = self.verifier.quick_verify(skill_name, task, output, checks)
            self.record(
                skill_name, task,
                success=result.passed,
                latency_ms=latency_ms,
                dimension_contributions=dimension_contributions,
            )
            return result
        else:
            # No verifier configured — trust the caller (backward compatible)
            self.record(
                skill_name, task,
                success=True,
                latency_ms=latency_ms,
                dimension_contributions=dimension_contributions,
            )
            return VerificationResult(
                passed=True,
                contract_id="no-verifier",
                checks_passed=len(checks),
                checks_total=len(checks),
                failures=[],
                evidence="no verifier configured — trusted caller self-report",
                verifier_model="none",
                latency_ms=0,
            )

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

        result = {
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
        if self._staleness_enabled:
            result["stale_skills"] = sorted(self._stale_skills)
            result["staleness_window_size"] = len(self._staleness_window)
        if self._warm_start_enabled:
            result["warm_start_skills"] = sorted(self._warm_start_data.keys())
        return result

    def reset(self) -> None:
        """Reset all learned weights to original values."""
        self.router.alpha, self.router.beta, self.router.gamma, self.router.delta = (
            self._original_weights
        )
        self._records.clear()
        self._dim_success_counts.clear()
        self._dim_total_counts.clear()
        self.total_routes = 0
        self._staleness_window.clear()
        self._stale_skills.clear()
        self._last_staleness_check = time.time()
        self._routes_since_staleness_check = 0
        self._warm_start_data.clear()

    # ── Staleness detection ─────────────────────────────────────────────

    def _evaluate_staleness(self) -> None:
        """Re-evaluate all skills in the sliding window for staleness."""
        self._last_staleness_check = time.time()
        self._routes_since_staleness_check = 0

        if not self._staleness_window:
            return

        # Count success/total per skill in window
        skill_counts: dict[str, dict[str, int]] = defaultdict(lambda: {"success": 0, "total": 0})
        for skill_name, success in self._staleness_window:
            skill_counts[skill_name]["total"] += 1
            if success:
                skill_counts[skill_name]["success"] += 1

        for skill_name, counts in skill_counts.items():
            rate = counts["success"] / counts["total"]
            if rate < self._staleness_threshold and skill_name not in self._stale_skills:
                self._stale_skills.add(skill_name)
            elif rate >= self._staleness_threshold and skill_name in self._stale_skills:
                self._stale_skills.discard(skill_name)

    def check_staleness(self, skill_name: str) -> bool:
        """Check if a skill is currently marked as stale."""
        return skill_name in self._stale_skills

    def get_stale_skills(self) -> set[str]:
        """Return the set of currently stale skills."""
        return set(self._stale_skills)

    def reset_staleness(self, skill_name: str) -> None:
        """Manually unmark a skill as stale."""
        self._stale_skills.discard(skill_name)

    # ── Warm start (cold-start preheating) ──────────────────────────────

    def warm_start(
        self,
        new_skill_name: str,
        tags: list[str],
        top_k: int = 3,
    ) -> dict:
        """Pre-heat a new skill by inheriting data from similar skills.

        Finds skills with the most tag overlap, computes a weighted average
        of their success_rate and avg_cost, and stores it for routing.

        Args:
            new_skill_name: Name of the newly registered skill.
            tags: Tags of the new skill (used for similarity).
            top_k: Number of nearest neighbours to average.

        Returns:
            Dict with inherited data: source_skills, inherited_success_rate,
            inherited_avg_cost, warm_start=True.
        """
        all_skills = self.router.skills
        if not all_skills or not tags:
            return {"source_skills": [], "inherited_success_rate": 0.5, "inherited_avg_cost": 1.0, "warm_start": True}

        # Score existing skills by tag overlap
        scored: list[tuple[int, str, Skill]] = []
        tag_set = set(tags)
        for name, skill in all_skills.items():
            if name == new_skill_name:
                continue
            if skill.total_count == 0:
                continue  # skip untested skills
            overlap = len(tag_set & set(skill.tags))
            if overlap > 0:
                scored.append((overlap, name, skill))

        if not scored:
            # No tag overlap found — fall back to global average
            tested = [s for s in all_skills.values() if s.total_count > 0 and s.name != new_skill_name]
            if not tested:
                result = {"source_skills": [], "inherited_success_rate": 0.5, "inherited_avg_cost": 1.0, "warm_start": True}
            else:
                avg_sr = sum(s.success_rate for s in tested) / len(tested)
                avg_cost = sum(s.avg_cost for s in tested) / len(tested)
                result = {
                    "source_skills": [s.name for s in tested[:top_k]],
                    "inherited_success_rate": round(avg_sr, 4),
                    "inherited_avg_cost": round(avg_cost, 4),
                    "warm_start": True,
                }
            self._warm_start_data[new_skill_name] = result
            return result

        # Pick top_k by overlap count (most tags in common)
        scored.sort(key=lambda x: x[0], reverse=True)
        neighbours = scored[:top_k]

        # Weighted average by overlap count
        total_weight = sum(overlap for overlap, _, _ in neighbours)
        inherited_sr = sum(overlap * s.success_rate for overlap, _, s in neighbours) / total_weight
        inherited_cost = sum(overlap * s.avg_cost for overlap, _, s in neighbours) / total_weight

        result = {
            "source_skills": [name for _, name, _ in neighbours],
            "inherited_success_rate": round(inherited_sr, 4),
            "inherited_avg_cost": round(inherited_cost, 4),
            "warm_start": True,
        }
        self._warm_start_data[new_skill_name] = result

        # Apply warm start data to the skill in the router
        skill = self.router.skills.get(new_skill_name)
        if skill and skill.total_count == 0:
            skill.success_count = int(inherited_sr * 10)
            skill.total_count = 10
            skill.avg_cost = inherited_cost

        return result
