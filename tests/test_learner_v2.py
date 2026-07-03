"""Tests for FeedbackLearner v2 — staleness detection + warm start."""

from __future__ import annotations

import sys
import os

# Ensure skill_weave is importable as a package
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest
from skill_weave.router import SkillRouter, Skill
from skill_weave.learner import FeedbackLearner


# ── Helpers ──────────────────────────────────────────────────────────────

def _make_router_with_skills(skill_configs: dict[str, dict]) -> SkillRouter:
    """Create a router with pre-registered skills.

    skill_configs: {name: {"tags": [...], "success_rate": float, "total_count": int, "avg_cost": float}}
    """
    router = SkillRouter()
    for name, cfg in skill_configs.items():
        skill = router.register_skill(name, metadata=cfg.get("metadata", name), tags=cfg.get("tags", []))
        # Simulate prior history
        tc = cfg.get("total_count", 0)
        if tc > 0:
            skill.total_count = tc
            sr = cfg.get("success_rate", 0.5)
            skill.success_count = int(sr * tc)
            skill.avg_cost = cfg.get("avg_cost", 0.5)
    return router


# ── Test 1: Staleness detection — consecutive failures mark stale ────────

def test_staleness_detection_consecutive_failures():
    """Record many failures for one skill → it should be marked stale → route score drops."""
    router = _make_router_with_skills({
        "good_skill": {"tags": ["deploy"], "total_count": 20, "success_rate": 0.9},
        "bad_skill": {"tags": ["deploy"], "total_count": 20, "success_rate": 0.9},
    })
    # Use small recheck interval so staleness triggers quickly
    learner = FeedbackLearner(
        router,
        staleness_window=50,
        staleness_threshold=0.3,
        staleness_penalty=0.1,
        staleness_recheck_interval=5,  # check every 5 records
        min_samples_for_learning=1,    # allow learning immediately
    )

    # Record 10 failures for bad_skill
    for _ in range(10):
        learner.record("bad_skill", "deploy", success=False, latency_ms=100)

    # After recheck, bad_skill should be stale
    assert learner.check_staleness("bad_skill"), "bad_skill should be stale after many failures"
    assert not learner.check_staleness("good_skill"), "good_skill should NOT be stale"

    # Route and verify bad_skill gets penalised
    results = learner.route("deploy", top_k=5, explore=False)
    result_map = {r.skill.name: r.score for r in results}
    assert "bad_skill" in result_map
    assert "good_skill" in result_map
    # bad_skill's score should be much lower (×0.1 penalty)
    assert result_map["bad_skill"] < result_map["good_skill"] * 0.5, (
        f"bad_skill score {result_map['bad_skill']} should be much less than good_skill {result_map['good_skill']}"
    )


# ── Test 2: Staleness recovery — success after stale lifts the mark ─────

def test_staleness_recovery():
    """After being stale, consecutive successes should lift the stale mark."""
    router = _make_router_with_skills({
        "recovering_skill": {"tags": ["test"], "total_count": 20, "success_rate": 0.9},
    })
    learner = FeedbackLearner(
        router,
        staleness_window=50,
        staleness_threshold=0.3,
        staleness_recheck_interval=5,
        min_samples_for_learning=1,
    )

    # Make it stale with failures
    for _ in range(10):
        learner.record("recovering_skill", "test", success=False, latency_ms=100)
    assert learner.check_staleness("recovering_skill"), "Should be stale"

    # Now record enough successes to recover (window is 50, need >30% success)
    # The window has 10 failures. Record 20 successes to push rate above 30%.
    for _ in range(20):
        learner.record("recovering_skill", "test", success=True, latency_ms=50)

    # Re-evaluate
    assert not learner.check_staleness("recovering_skill"), "Should have recovered from staleness"


# ── Test 3: Warm start — new skill inherits from similar neighbours ──────

def test_warm_start_from_similar_skills():
    """New skill with tags matching existing skills should inherit their data."""
    router = _make_router_with_skills({
        "deploy_k8s": {"tags": ["deploy", "kubernetes"], "total_count": 30, "success_rate": 0.8, "avg_cost": 0.3},
        "deploy_docker": {"tags": ["deploy", "docker"], "total_count": 20, "success_rate": 0.7, "avg_cost": 0.4},
        "monitoring": {"tags": ["monitor", "alert"], "total_count": 15, "success_rate": 0.9, "avg_cost": 0.2},
    })
    learner = FeedbackLearner(router)

    # Register a new skill with no history
    router.register_skill("deploy_helm", metadata="helm deploy", tags=["deploy", "kubernetes", "helm"])

    result = learner.warm_start("deploy_helm", tags=["deploy", "kubernetes", "helm"])

    assert result["warm_start"] is True
    assert len(result["source_skills"]) > 0
    # deploy_k8s has 2 tag overlaps (deploy, kubernetes), deploy_docker has 1 (deploy)
    assert "deploy_k8s" in result["source_skills"]
    # Inherited success rate should be closer to deploy_k8s (higher weight)
    assert result["inherited_success_rate"] > 0.7
    assert result["inherited_avg_cost"] < 0.5

    # The skill in the router should now have pre-heated data
    skill = router.skills["deploy_helm"]
    assert skill.total_count == 10, "Should have 10 synthetic samples"
    assert skill.success_count > 0, "Should have inherited successes"


# ── Test 4: Warm start data discarded after enough real samples ──────────

def test_warm_start_data_discarded_after_real_samples():
    """Warm start data should be discarded once the skill has enough real samples."""
    router = _make_router_with_skills({
        "existing": {"tags": ["code"], "total_count": 20, "success_rate": 0.8},
    })
    learner = FeedbackLearner(router, warm_start_min_samples=5)

    router.register_skill("new_skill", metadata="code review", tags=["code"])
    learner.warm_start("new_skill", tags=["code"])
    # Need at least one record so stats() doesn't short-circuit with "no data"
    learner.record("existing", "code", success=True, latency_ms=100)
    assert "new_skill" in learner.stats().get("warm_start_skills", [])

    # Record 5 real uses — should trigger discard
    for _ in range(5):
        learner.record("new_skill", "code review", success=True, latency_ms=100)

    assert "new_skill" not in learner.stats().get("warm_start_skills", [])


# ── Test 5: Backward compatibility — existing behaviour unchanged ────────

def test_backward_compatibility():
    """FeedbackLearner without new features should behave identically to v1."""
    router = SkillRouter()
    s1 = router.register_skill("s1", metadata="deploy server", tags=["deploy"])
    s1.total_count = 10
    s1.success_count = 8
    s1.avg_cost = 0.5

    # Create with staleness + warm_start disabled
    learner = FeedbackLearner(router, staleness_enabled=False, warm_start_enabled=False)

    # route() should work as before
    results = learner.route("deploy server", top_k=5)
    assert len(results) > 0
    assert results[0].skill.name == "s1"

    # record() should work as before
    learner.record("s1", "deploy server", success=True, latency_ms=200)
    assert learner.total_routes == 1

    # stats() should NOT include stale_skills or warm_start_skills
    st = learner.stats()
    assert "stale_skills" not in st
    assert "warm_start_skills" not in st

    # reset() should work as before
    learner.reset()
    assert learner.total_routes == 0


def test_backward_compatibility_default_args():
    """Default args (features enabled) should not break existing call patterns."""
    router = SkillRouter()
    router.register_skill("a", metadata="alpha task", tags=["alpha"])
    router.register_skill("b", metadata="beta task", tags=["beta"])

    learner = FeedbackLearner(router)  # all defaults

    # Standard usage pattern
    results = learner.route("alpha task")
    assert len(results) > 0

    learner.record("a", "alpha task", success=True, latency_ms=100)
    learner.record("b", "beta task", success=False, latency_ms=200)

    st = learner.stats()
    assert st["total_routes"] == 2
    assert "stale_skills" in st  # enabled by default
    assert "staleness_window_size" in st


# ── Test 6: Warm start with no tag overlap falls back to global ──────────

def test_warm_start_no_tag_overlap():
    """When no tags overlap, warm_start should fall back to global average."""
    router = _make_router_with_skills({
        "deploy": {"tags": ["deploy"], "total_count": 20, "success_rate": 0.8, "avg_cost": 0.3},
    })
    learner = FeedbackLearner(router)
    router.register_skill("unrelated", metadata="something else", tags=["finance"])

    result = learner.warm_start("unrelated", tags=["finance"])
    assert result["warm_start"] is True
    assert "deploy" in result["source_skills"]  # falls back to all tested
    assert abs(result["inherited_success_rate"] - 0.8) < 0.01


# ── Test 7: reset_staleness manual override ──────────────────────────────

def test_reset_staleness_manual():
    """reset_staleness() should manually clear the stale flag."""
    router = _make_router_with_skills({
        "s": {"tags": ["x"], "total_count": 20, "success_rate": 0.9},
    })
    learner = FeedbackLearner(router, staleness_recheck_interval=3, min_samples_for_learning=1)

    for _ in range(10):
        learner.record("s", "x", success=False, latency_ms=100)

    assert learner.check_staleness("s")
    learner.reset_staleness("s")
    assert not learner.check_staleness("s")


# ── Test 8: get_stale_skills returns a copy ──────────────────────────────

def test_get_stale_skills_returns_copy():
    """get_stale_skills() should return a copy, not the internal set."""
    router = _make_router_with_skills({
        "s": {"tags": ["x"], "total_count": 20, "success_rate": 0.9},
    })
    learner = FeedbackLearner(router, staleness_recheck_interval=3, min_samples_for_learning=1)

    for _ in range(10):
        learner.record("s", "x", success=False, latency_ms=100)

    stale = learner.get_stale_skills()
    assert "s" in stale
    stale.discard("s")
    assert learner.check_staleness("s"), "Internal state should not be affected"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
