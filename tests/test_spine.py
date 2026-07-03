"""Tests for SpineIO — state spine persistence."""

from __future__ import annotations

import json
import os
import sys
import time
import tempfile
from pathlib import Path

import pytest

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from skill_weave.spine import SpineIO, _empty_state, _VERSION


@pytest.fixture
def spine_path(tmp_path):
    """Provide a temporary spine file path."""
    return str(tmp_path / "state_spine.json")


@pytest.fixture
def spine(spine_path):
    return SpineIO(path=spine_path)


# ── Basic read/write ──────────────────────────────────────────────────

class TestBasicIO:
    def test_read_returns_default_when_missing(self, spine):
        state = spine.read()
        assert state["version"] == _VERSION
        assert state["completed"] == []
        assert state["needs_human"] == []

    def test_write_persists_data(self, spine):
        spine.write({"session_id": "test-001"})
        state = spine.read()
        assert state["session_id"] == "test-001"
        # Version should still be present
        assert state["version"] == _VERSION

    def test_write_merges_not_replaces(self, spine):
        spine.write({"session_id": "s1"})
        spine.write({"metrics": {"total_routes": 5}})
        state = spine.read()
        assert state["session_id"] == "s1"
        assert state["metrics"]["total_routes"] == 5


# ── Heartbeat ─────────────────────────────────────────────────────────

class TestHeartbeat:
    def test_heartbeat_updates_timestamp(self, spine):
        spine.write({"session_id": "h1"})
        before = spine.read()["last_heartbeat"]
        time.sleep(0.05)
        spine.heartbeat()
        after = spine.read()["last_heartbeat"]
        assert after >= before

    def test_heartbeat_preserves_state(self, spine):
        spine.write({"session_id": "h2"})
        spine.heartbeat()
        state = spine.read()
        assert state["session_id"] == "h2"


# ── Completed ─────────────────────────────────────────────────────────

class TestCompleted:
    def test_mark_completed_appends(self, spine):
        spine.mark_completed("task_a", tests="9/9")
        spine.mark_completed("task_b")
        state = spine.read()
        assert len(state["completed"]) == 2
        assert state["completed"][0]["task"] == "task_a"
        assert state["completed"][0]["tests"] == "9/9"
        assert state["completed"][1]["task"] == "task_b"

    def test_completed_has_timestamp(self, spine):
        spine.mark_completed("task_c")
        state = spine.read()
        assert "at" in state["completed"][0]


# ── Needs human ───────────────────────────────────────────────────────

class TestNeedsHuman:
    def test_flag_needs_human(self, spine):
        spine.flag_needs_human("API key expired")
        spine.flag_needs_human("Rate limited")
        state = spine.read()
        assert len(state["needs_human"]) == 2
        assert "API key" in state["needs_human"][0]["issue"]


# ── Learner snapshot / restore ────────────────────────────────────────

class TestLearnerSnapshot:
    """Test learner snapshot/restore using a mock FeedbackLearner."""

    def _make_mock_learner(self, alpha=0.45, beta=0.20, gamma=0.25, delta=0.10):
        """Create a minimal mock that satisfies SpineIO's needs."""
        class MockRouter:
            pass
        class MockLearner:
            def __init__(self, a, b, g, d):
                self.router = MockRouter()
                self.router.alpha = a
                self.router.beta = b
                self.router.gamma = g
                self.router.delta = d
                self.total_routes = 42
            def stats(self):
                return {
                    "total_routes": self.total_routes,
                    "recent_success_rate": 0.85,
                    "weights": {
                        "alpha": self.router.alpha,
                        "beta": self.router.beta,
                        "gamma": self.router.gamma,
                        "delta": self.router.delta,
                    },
                }
        return MockLearner(alpha, beta, gamma, delta)

    def test_snapshot_and_restore(self, spine):
        learner = self._make_mock_learner(0.50, 0.15, 0.25, 0.10)
        spine.snapshot_learner(learner)

        state = spine.read()
        snap = state["learner_snapshot"]
        assert snap["weights"]["alpha"] == 0.50
        assert snap["total_routes"] == 42

        # Now restore into a fresh learner with default weights
        fresh = self._make_mock_learner(0.45, 0.20, 0.25, 0.10)
        assert fresh.router.alpha == 0.45

        ok = spine.restore_learner(fresh)
        assert ok is True
        assert fresh.router.alpha == 0.50
        assert fresh.router.beta == 0.15
        assert fresh.total_routes == 42

    def test_restore_returns_false_when_no_snapshot(self, spine):
        fresh = self._make_mock_learner()
        ok = spine.restore_learner(fresh)
        assert ok is False

    def test_restore_preserves_defaults_for_missing_weights(self, spine):
        """If snapshot only has partial weights, missing ones keep defaults."""
        spine.write({"learner_snapshot": {"weights": {"alpha": 0.99, "gamma": 0.01}}})
        fresh = self._make_mock_learner()
        spine.restore_learner(fresh)
        assert fresh.router.alpha == 0.99
        assert fresh.router.gamma == 0.01
        assert fresh.router.beta == 0.20  # default preserved


# ── Atomic write ──────────────────────────────────────────────────────

class TestAtomicWrite:
    def test_no_tmp_file_left_behind(self, spine, spine_path):
        spine.write({"session_id": "atomic"})
        tmp_path = Path(spine_path).with_suffix(".tmp")
        assert not tmp_path.exists()

    def test_data_is_valid_json(self, spine, spine_path):
        spine.write({"test": True})
        with open(spine_path) as f:
            data = json.load(f)
        assert data["test"] is True

    def test_corrupted_file_returns_default(self, spine, spine_path):
        """If the JSON file is corrupted, read() should return defaults."""
        Path(spine_path).write_text("not json {{{")
        state = spine.read()
        assert state["version"] == _VERSION
        assert state["completed"] == []
