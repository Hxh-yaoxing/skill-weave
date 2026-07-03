"""Tests for skill_weave.circuit_breaker."""

from __future__ import annotations

import time
import pytest
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skill_weave.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Six core scenarios for the circuit breaker."""

    def test_default_state_closed(self):
        cb = CircuitBreaker()
        assert cb.is_available("skill_a") is True
        assert cb.get_state("skill_a").state == "CLOSED"

    def test_three_failures_trigger_open(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            assert cb.is_available("s") is True
            cb.record_failure("s")
        assert cb.is_available("s") is False
        assert cb.get_state("s").state == "OPEN"

    def test_cooldown_then_half_open(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.01)
        cb.record_failure("s")
        cb.record_failure("s")
        assert cb.get_state("s").state == "OPEN"
        time.sleep(0.02)
        assert cb.is_available("s") is True
        assert cb.get_state("s").state == "HALF_OPEN"

    def test_probe_success_closes(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.01)
        cb.record_failure("s")
        cb.record_failure("s")
        time.sleep(0.02)
        cb.is_available("s")  # triggers HALF_OPEN
        cb.record_success("s")
        assert cb.get_state("s").state == "CLOSED"
        assert cb.is_available("s") is True

    def test_probe_failure_reopens(self):
        cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.01)
        cb.record_failure("s")
        cb.record_failure("s")
        time.sleep(0.02)
        cb.is_available("s")  # HALF_OPEN
        cb.record_failure("s")  # probe fails
        assert cb.get_state("s").state == "OPEN"
        assert cb.is_available("s") is False

    def test_stats(self):
        cb = CircuitBreaker(failure_threshold=2)
        cb.record_success("a")
        cb.record_failure("b")
        cb.record_failure("b")
        stats = cb.stats()
        assert stats["total_skills"] == 2
        assert stats["by_state"]["CLOSED"] == 1
        assert stats["by_state"]["OPEN"] == 1
        assert stats["skills"]["a"]["success_count"] == 1
        assert stats["skills"]["b"]["failure_count"] == 2

    def test_fallback(self):
        cb = CircuitBreaker()
        cb.set_fallback("primary", "backup")
        assert cb.get_fallback("primary") == "backup"
        assert cb.get_fallback("unknown") == ""

    def test_reset(self):
        cb = CircuitBreaker(failure_threshold=1)
        cb.record_failure("s")
        assert cb.get_state("s").state == "OPEN"
        cb.reset("s")
        assert cb.get_state("s").state == "CLOSED"
        assert cb.get_state("s").failure_count == 0

    def test_reset_all(self):
        cb = CircuitBreaker()
        cb.record_failure("a")
        cb.record_failure("b")
        cb.reset()
        assert cb.stats()["total_skills"] == 0
