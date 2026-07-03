"""Circuit breaker for skill routing — protects against cascading failures.

State machine per skill: CLOSED → OPEN → HALF_OPEN → CLOSED.
Zero external dependencies, pure stdlib.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict

__all__ = ["CircuitState", "CircuitBreaker"]


@dataclass
class CircuitState:
    """Tracks the circuit-breaker state for a single skill."""

    skill_name: str
    state: str = "CLOSED"  # "CLOSED" | "OPEN" | "HALF_OPEN"
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    last_probe_time: float = 0.0
    fallback_skill: str = ""
    history: list[dict] = field(default_factory=list)


class CircuitBreaker:
    """Per-skill circuit breaker with configurable threshold and cooldown.

    Usage::

        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=60)
        if cb.is_available("my_skill"):
            result = call_skill(...)
            if result.ok:
                cb.record_success("my_skill")
            else:
                cb.record_failure("my_skill")
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_seconds: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._states: Dict[str, CircuitState] = {}

    # ── internal helpers ──────────────────────────────────────────

    def _get_or_create(self, skill_name: str) -> CircuitState:
        if skill_name not in self._states:
            self._states[skill_name] = CircuitState(skill_name=skill_name)
        return self._states[skill_name]

    def _maybe_half_open(self, cs: CircuitState) -> None:
        """Transition OPEN → HALF_OPEN if cooldown has elapsed."""
        if cs.state == "OPEN":
            elapsed = time.monotonic() - cs.last_failure_time
            if elapsed >= self.cooldown_seconds:
                cs.state = "HALF_OPEN"
                cs.last_probe_time = time.monotonic()

    # ── public API ────────────────────────────────────────────────

    def record_success(self, skill_name: str) -> None:
        """Record a successful call — resets failure count and closes the circuit."""
        cs = self._get_or_create(skill_name)
        cs.success_count += 1
        cs.failure_count = 0
        cs.state = "CLOSED"
        cs.history.append({
            "time": time.monotonic(),
            "event": "success",
            "state": "CLOSED",
        })

    def record_failure(self, skill_name: str) -> None:
        """Record a failure — increments counter; opens circuit at threshold."""
        cs = self._get_or_create(skill_name)
        cs.failure_count += 1
        cs.last_failure_time = time.monotonic()
        cs.history.append({
            "time": cs.last_failure_time,
            "event": "failure",
            "count": cs.failure_count,
        })

        if cs.state == "HALF_OPEN":
            # Probe failed → back to OPEN with fresh cooldown
            cs.state = "OPEN"
            cs.history[-1]["state"] = "OPEN"
        elif cs.failure_count >= self.failure_threshold:
            cs.state = "OPEN"
            cs.history[-1]["state"] = "OPEN"

    def is_available(self, skill_name: str) -> bool:
        """Return True if the skill may be called (CLOSED or HALF_OPEN with probe slot)."""
        cs = self._get_or_create(skill_name)
        self._maybe_half_open(cs)
        return cs.state != "OPEN"

    def get_state(self, skill_name: str) -> CircuitState:
        """Return the full circuit state for a skill (creates default if unknown)."""
        cs = self._get_or_create(skill_name)
        self._maybe_half_open(cs)
        return cs

    def set_fallback(self, skill_name: str, fallback_skill: str) -> None:
        """Register a fallback skill to use when *skill_name* is OPEN."""
        cs = self._get_or_create(skill_name)
        cs.fallback_skill = fallback_skill

    def get_fallback(self, skill_name: str) -> str:
        """Return the fallback skill name, or empty string if none registered."""
        cs = self._get_or_create(skill_name)
        return cs.fallback_skill

    def stats(self) -> dict:
        """Aggregate statistics across all tracked skills."""
        summary = {"total_skills": 0, "by_state": {"CLOSED": 0, "OPEN": 0, "HALF_OPEN": 0}, "skills": {}}
        for name, cs in self._states.items():
            self._maybe_half_open(cs)
            summary["total_skills"] += 1
            summary["by_state"][cs.state] = summary["by_state"].get(cs.state, 0) + 1
            summary["skills"][name] = {
                "state": cs.state,
                "failure_count": cs.failure_count,
                "success_count": cs.success_count,
                "fallback": cs.fallback_skill,
                "history_len": len(cs.history),
            }
        return summary

    def reset(self, skill_name: str | None = None) -> None:
        """Reset circuit state for one skill or all."""
        if skill_name is None:
            self._states.clear()
        else:
            self._states.pop(skill_name, None)
