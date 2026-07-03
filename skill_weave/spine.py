"""State Spine — cross-loop memory for skill-weave.

Provides SpineIO: a JSON-backed persistence layer that gives cron jobs
and delegate_tasks memory continuity between runs.

Zero new dependencies (json, os, time, pathlib, datetime only).
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .learner import FeedbackLearner

_DEFAULT_PATH = "~/.skill_weave/state_spine.json"
_VERSION = "0.4.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _empty_state() -> dict:
    return {
        "version": _VERSION,
        "last_heartbeat": _now_iso(),
        "session_id": "",
        "active_goals": [],
        "completed": [],
        "blocked": [],
        "needs_human": [],
        "decisions": [],
        "metrics": {
            "routing_accuracy": 0.0,
            "total_routes": 0,
            "active_skills": 0,
            "stale_skills": 0,
        },
        "learner_snapshot": {},
    }


class SpineIO:
    """Read/write state spine for cross-loop memory continuity.

    Usage::

        spine = SpineIO()
        state = spine.read()          # loop start
        # ... do work ...
        spine.heartbeat()             # loop end
        spine.mark_completed("task")  # mark done
    """

    def __init__(self, path: str = _DEFAULT_PATH):
        self._path = Path(path).expanduser().resolve()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # ── Core I/O ──────────────────────────────────────────────────────

    def read(self) -> dict:
        """Return current spine state, or empty default if file missing."""
        if not self._path.exists():
            return _empty_state()
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Ensure all top-level keys exist (forward compat)
            defaults = _empty_state()
            for key, default_val in defaults.items():
                data.setdefault(key, default_val)
            return data
        except (json.JSONDecodeError, OSError):
            return _empty_state()

    def write(self, updates: dict) -> None:
        """Merge *updates* into current state and atomically persist."""
        current = self.read()
        self._deep_merge(current, updates)
        current["last_heartbeat"] = _now_iso()
        self._atomic_write(current)

    # ── Convenience methods ───────────────────────────────────────────

    def heartbeat(self) -> None:
        """Update last_heartbeat timestamp."""
        state = self.read()
        state["last_heartbeat"] = _now_iso()
        self._atomic_write(state)

    def mark_completed(self, task: str, **meta: Any) -> None:
        """Append a completed-task entry."""
        state = self.read()
        entry: dict[str, Any] = {"task": task, "at": _now_iso()}
        entry.update(meta)
        state.setdefault("completed", []).append(entry)
        self._atomic_write(state)

    def flag_needs_human(self, issue: str) -> None:
        """Flag an issue that requires human intervention."""
        state = self.read()
        entry = {"issue": issue, "at": _now_iso()}
        state.setdefault("needs_human", []).append(entry)
        self._atomic_write(state)

    # ── Learner snapshot / restore ────────────────────────────────────

    def snapshot_learner(self, learner: FeedbackLearner) -> None:
        """Persist FeedbackLearner weights and metrics to the spine."""
        stats = learner.stats()
        snapshot: dict[str, Any] = {}
        if "weights" in stats:
            snapshot["weights"] = stats["weights"]
        snapshot["total_routes"] = stats.get("total_routes", 0)
        snapshot["recent_success_rate"] = stats.get("recent_success_rate", 0.0)

        state = self.read()
        state["learner_snapshot"] = snapshot
        # Also update top-level metrics
        state.setdefault("metrics", {})["total_routes"] = snapshot["total_routes"]
        self._atomic_write(state)

    def restore_learner(self, learner: FeedbackLearner) -> bool:
        """Restore weights from spine into *learner*. Returns True if restored."""
        state = self.read()
        snap = state.get("learner_snapshot", {})
        weights = snap.get("weights")
        if not weights:
            return False

        learner.router.alpha = weights.get("alpha", learner.router.alpha)
        learner.router.beta = weights.get("beta", learner.router.beta)
        learner.router.gamma = weights.get("gamma", learner.router.gamma)
        learner.router.delta = weights.get("delta", learner.router.delta)
        # Restore total_routes so UCB math continues
        learner.total_routes = snap.get("total_routes", 0)
        return True

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _deep_merge(base: dict, overlay: dict) -> dict:
        """Recursively merge *overlay* into *base* (mutates base)."""
        for key, val in overlay.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                SpineIO._deep_merge(base[key], val)
            else:
                base[key] = val
        return base

    def _atomic_write(self, data: dict) -> None:
        """Write JSON atomically: write to .tmp then os.replace."""
        tmp = self._path.with_suffix(".tmp")
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(str(tmp), str(self._path))
        except OSError:
            # Best-effort cleanup
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
