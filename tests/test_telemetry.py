"""Tests for skill_weave.telemetry."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telemetry import Telemetry, RouteSpan


@pytest.fixture
def tmp_telemetry(tmp_path):
    """Create a Telemetry instance with a temp log path."""
    log_file = str(tmp_path / "test_telemetry.jsonl")
    return Telemetry(log_path=log_file, max_size_mb=1)


class TestTelemetry:

    def test_span_lifecycle(self, tmp_telemetry):
        span = tmp_telemetry.start_span("hello world")
        assert span.route_id
        assert span.query == "hello world"
        assert span.start_time > 0

        record = tmp_telemetry.end_span(span, selected="greet", success=True, latency_ms=12.3)
        assert record["selected"] == "greet"
        assert record["success"] is True
        assert record["latency_ms"] == pytest.approx(12.3, rel=0.01)

    def test_context_manager_span(self, tmp_telemetry):
        with tmp_telemetry.span("test query") as s:
            s.selected = "test_skill"
            s.success = True

        logs = tmp_telemetry.read_logs()
        assert len(logs) == 1
        assert logs[0]["selected"] == "test_skill"
        assert logs[0]["success"] is True

    def test_log_write_and_read(self, tmp_telemetry):
        for i in range(5):
            span = tmp_telemetry.start_span(f"q{i}")
            tmp_telemetry.end_span(span, selected=f"s{i}", success=i % 2 == 0, latency_ms=float(i))

        logs = tmp_telemetry.read_logs(limit=3)
        assert len(logs) == 3
        # Should return last 3
        assert logs[0]["selected"] == "s2"
        assert logs[2]["selected"] == "s4"

    def test_read_logs_empty(self, tmp_telemetry):
        assert tmp_telemetry.read_logs() == []

    def test_rotation(self, tmp_path):
        log_file = str(tmp_path / "rot.jsonl")
        # Very small max size to trigger rotation
        t = Telemetry(log_path=log_file, max_size_mb=0.0001)

        # Write enough to exceed ~100 bytes
        for i in range(20):
            span = t.start_span(f"query number {i} with some padding text")
            t.end_span(span, selected="skill", success=True, latency_ms=1.0)

        # Check that a rotated file exists
        files = list(tmp_path.glob("rot.*.jsonl"))
        assert len(files) >= 1, "Expected rotated log files"

    def test_stats(self, tmp_telemetry):
        for i in range(10):
            span = tmp_telemetry.start_span(f"q{i}")
            tmp_telemetry.end_span(
                span, selected="s", success=i < 7, latency_ms=float(i * 10)
            )

        stats = tmp_telemetry.stats()
        assert stats["total_routes"] == 10
        assert stats["success"] == 7
        assert stats["failure"] == 3
        assert stats["avg_latency_ms"] > 0
        assert stats["log_size_bytes"] > 0

    def test_stats_empty(self, tmp_telemetry):
        stats = tmp_telemetry.stats()
        assert stats["total_routes"] == 0
        assert stats["avg_latency_ms"] == 0.0

    def test_log_event(self, tmp_telemetry):
        tmp_telemetry.log_event("circuit_open", skill="foo", reason="threshold")
        logs = tmp_telemetry.read_logs()
        assert len(logs) == 1
        assert logs[0]["event"] == "circuit_open"
        assert logs[0]["skill"] == "foo"

    def test_span_auto_latency(self, tmp_telemetry):
        """When latency_ms not provided, it's computed from monotonic time."""
        span = tmp_telemetry.start_span("slow query")
        # Simulate some work
        import time; time.sleep(0.01)
        record = tmp_telemetry.end_span(span, selected="s", success=True)
        assert record["latency_ms"] >= 5  # at least 5ms after 10ms sleep
