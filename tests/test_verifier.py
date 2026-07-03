"""Tests for verifier.py — VerificationContract, Check, RouteVerifier."""

import pytest
import sys
import os

# Ensure skill_weave package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from skill_weave.verifier import (
    Check,
    VerificationContract,
    VerificationResult,
    RouteVerifier,
)
from skill_weave.learner import FeedbackLearner
from skill_weave.router import SkillRouter


# ── Contract creation ──────────────────────────────────────────────────

def test_check_creation():
    c = Check(description="has output", assertion="output is non-empty")
    assert c.description == "has output"
    assert c.command is None
    assert c.assertion == "output is non-empty"
    assert c.evidence == "auto"


def test_check_with_command():
    c = Check(description="exit zero", command="true")
    assert c.command == "true"


def test_contract_creation():
    contract = VerificationContract(
        skill_name="test-skill",
        checks=[
            Check(description="check1", assertion="assertion1"),
            Check(description="check2", command="echo ok"),
        ],
        model="test-model",
    )
    assert contract.skill_name == "test-skill"
    assert len(contract.checks) == 2
    assert contract.model == "test-model"
    assert contract.on_fail == "flag_needs_human"


# ── Command checks ─────────────────────────────────────────────────────

def test_command_check_pass():
    """echo hello → exit 0 → PASS."""
    verifier = RouteVerifier(api_key="dummy")
    ok, ev = verifier._run_command_check("echo hello")
    assert ok is True
    assert "exit 0" in ev
    assert "hello" in ev


def test_command_check_fail():
    """false → exit 1 → FAIL."""
    verifier = RouteVerifier(api_key="dummy")
    ok, ev = verifier._run_command_check("false")
    assert ok is False
    assert "exit 1" in ev


def test_command_check_nonexistent():
    """Non-existent command → FAIL."""
    verifier = RouteVerifier(api_key="dummy")
    ok, ev = verifier._run_command_check("nonexistent_command_xyz")
    assert ok is False


# ── LLM checks (fallback heuristic when no API) ────────────────────────

def test_llm_check_fallback_contains_items():
    """Heuristic fallback detects 'contains at least N items'."""
    verifier = RouteVerifier(api_key="dummy")
    # Output with 6 bullet items
    output = "- item1\n- item2\n- item3\n- item4\n- item5\n- item6"
    ok, ev = verifier._run_llm_check("output contains at least 5 items", output)
    assert ok is True


def test_llm_check_fallback_contains_items_fail():
    """Heuristic fallback detects insufficient items."""
    verifier = RouteVerifier(api_key="dummy")
    output = "- item1\n- item2"
    ok, ev = verifier._run_llm_check("output contains at least 5 items", output)
    assert ok is False


def test_llm_check_fallback_no_placeholder():
    """Heuristic detects no placeholder text."""
    verifier = RouteVerifier(api_key="dummy")
    output = "This is a real result with actual content."
    ok, ev = verifier._run_llm_check("output has no placeholder text", output)
    assert ok is True


def test_llm_check_fallback_has_placeholder():
    """Heuristic detects TODO/placeholder text."""
    verifier = RouteVerifier(api_key="dummy")
    output = "Result: TODO - need to fill this in"
    ok, ev = verifier._run_llm_check("output has no placeholder text", output)
    assert ok is False


# ── Quick verify ────────────────────────────────────────────────────────

def test_quick_verify_all_pass():
    """All checks pass → overall pass."""
    verifier = RouteVerifier(api_key="dummy")
    output = "- item1\n- item2\n- item3\n- item4\n- item5\n- item6"
    result = verifier.quick_verify(
        "test-skill",
        "list items",
        output,
        ["output contains at least 5 items"],
    )
    assert result.passed is True
    assert result.checks_passed == 1
    assert result.checks_total == 1
    assert len(result.failures) == 0


def test_quick_verify_some_fail():
    """Some checks fail → overall fail."""
    verifier = RouteVerifier(api_key="dummy")
    output = "- item1"
    result = verifier.quick_verify(
        "test-skill",
        "list items",
        output,
        ["output contains at least 5 items"],
    )
    assert result.passed is False
    assert result.checks_passed == 0
    assert result.checks_total == 1
    assert len(result.failures) == 1


def test_quick_verify_mixed():
    """Mix of passing and failing checks."""
    verifier = RouteVerifier(api_key="dummy")
    output = "- item1\n- item2\n- item3"
    result = verifier.quick_verify(
        "test-skill",
        "list items",
        output,
        [
            "output contains at least 2 items",      # pass
            "output contains at least 10 items",      # fail
        ],
    )
    assert result.passed is False
    assert result.checks_passed == 1
    assert result.checks_total == 2


# ── Context insufficiency → fallback ────────────────────────────────────

def test_empty_output_fallback():
    """Empty output with heuristic → conservative fail."""
    verifier = RouteVerifier(api_key="dummy")
    ok, ev = verifier._run_llm_check("output is meaningful", "")
    # Fallback should return False for empty output with generic assertion
    assert ok is False


# ── Backward compatibility (no verifier on FeedbackLearner) ─────────────

def test_backward_compat_no_verifier():
    """FeedbackLearner without verifier — record() still works."""
    router = SkillRouter()
    router.register_skill("test", tags=["test"])
    learner = FeedbackLearner(router)  # no verifier
    # record() should work unchanged
    learner.record("test", "task", success=True)
    assert learner.total_routes == 1
    assert learner.records[0].success is True


def test_record_verified_no_verifier():
    """record_verified without verifier — trusts caller, returns passed=True."""
    router = SkillRouter()
    router.register_skill("test", tags=["test"])
    learner = FeedbackLearner(router)  # no verifier
    result = learner.record_verified(
        "test", "task", "some output", ["check1"]
    )
    assert result.passed is True
    assert result.verifier_model == "none"
    assert learner.total_routes == 1
    assert learner.records[0].success is True


def test_record_verified_with_verifier():
    """record_verified with verifier — uses verifier's judgment."""
    router = SkillRouter()
    router.register_skill("test", tags=["test"])
    verifier = RouteVerifier(api_key="dummy")  # will use fallback
    learner = FeedbackLearner(router, verifier=verifier)

    # Output with enough items → verifier should pass
    output = "- item1\n- item2\n- item3\n- item4\n- item5"
    result = learner.record_verified(
        "test", "list items", output,
        ["output contains at least 5 items"],
    )
    assert result.passed is True
    assert learner.records[0].success is True


def test_record_verified_with_verifier_fail():
    """record_verified with verifier — detects failure."""
    router = SkillRouter()
    router.register_skill("test", tags=["test"])
    verifier = RouteVerifier(api_key="dummy")
    learner = FeedbackLearner(router, verifier=verifier)

    # Output too short → verifier should fail
    output = "- item1"
    result = learner.record_verified(
        "test", "list items", output,
        ["output contains at least 5 items"],
    )
    assert result.passed is False
    assert learner.records[0].success is False


# ── VerificationResult fields ───────────────────────────────────────────

def test_verification_result_fields():
    """Check all fields are populated."""
    verifier = RouteVerifier(api_key="dummy")
    output = "- item1\n- item2\n- item3\n- item4\n- item5"
    result = verifier.quick_verify(
        "test-skill", "task", output,
        ["output contains at least 3 items"],
    )
    assert isinstance(result, VerificationResult)
    assert result.passed is True
    assert result.contract_id  # non-empty
    assert result.checks_passed == 1
    assert result.checks_total == 1
    assert result.failures == []
    assert result.evidence  # non-empty
    assert result.verifier_model  # non-empty
    assert result.latency_ms >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
