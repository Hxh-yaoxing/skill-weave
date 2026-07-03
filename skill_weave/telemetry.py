"""Structured telemetry for skill routing — JSONL logs with OpenTelemetry-style spans.

Zero external dependencies, pure stdlib.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Generator, List

__all__ = ["RouteSpan", "Telemetry"]


@dataclass
class RouteSpan:
    """Represents one route decision lifecycle."""

    route_id: str = ""
    query: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    candidates: List[str] = field(default_factory=list)
    selected: str = ""
    success: bool = False
    latency_ms: float = 0.0
    circuit_triggered: bool = False
    fallback_used: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Telemetry:
    """JSONL telemetry logger with rotation.

    Usage::

        telemetry = Telemetry("~/.skill_weave/telemetry.jsonl")
        span = telemetry.start_span("translate this text")
        # ... do routing ...
        telemetry.end_span(span, selected="xindaya-translator", success=True, latency_ms=42.5)
    """

    def __init__(
        self,
        log_path: str = "~/.skill_weave/telemetry.jsonl",
        max_size_mb: float = 10.0,
    ) -> None:
        self.log_path = Path(log_path).expanduser().resolve()
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self._ensure_dir()

    # ── internal helpers ──────────────────────────────────────────

    def _ensure_dir(self) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def _rotate_if_needed(self) -> None:
        if self.log_path.exists() and self.log_path.stat().st_size >= self.max_size_bytes:
            rotated = self.log_path.with_suffix(f".{int(time.time())}.jsonl")
            self.log_path.rename(rotated)

    def _append(self, record: dict) -> None:
        self._rotate_if_needed()
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── public API ────────────────────────────────────────────────

    def start_span(self, query: str) -> RouteSpan:
        """Begin a new route span."""
        return RouteSpan(
            route_id=uuid.uuid4().hex[:12],
            query=query,
            start_time=time.monotonic(),
        )

    def end_span(
        self,
        span: RouteSpan,
        selected: str,
        success: bool,
        latency_ms: float = 0.0,
        candidates: List[str] | None = None,
        circuit_triggered: bool = False,
        fallback_used: str = "",
    ) -> dict:
        """Finalize and write a span to the log."""
        span.end_time = time.monotonic()
        span.selected = selected
        span.success = success
        span.latency_ms = latency_ms if latency_ms > 0 else (span.end_time - span.start_time) * 1000
        span.candidates = candidates or []
        span.circuit_triggered = circuit_triggered
        span.fallback_used = fallback_used

        record = span.to_dict()
        record["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self._append(record)
        return record

    def log_event(self, event_type: str, **kwargs: object) -> dict:
        """Write an arbitrary event to the telemetry log."""
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "event": event_type,
            **kwargs,
        }
        self._append(record)
        return record

    def read_logs(self, limit: int = 100) -> List[dict]:
        """Read the most recent *limit* log entries."""
        if not self.log_path.exists():
            return []
        lines: List[str] = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    lines.append(line)
        result: List[dict] = []
        for raw in lines[-limit:]:
            try:
                result.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return result

    def stats(self) -> dict:
        """Aggregate statistics from the telemetry log."""
        if not self.log_path.exists():
            return {"total_routes": 0, "success": 0, "failure": 0, "avg_latency_ms": 0.0, "log_size_bytes": 0}

        total = success = 0
        total_latency = 0.0
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "route_id" in rec:
                    total += 1
                    if rec.get("success"):
                        success += 1
                    total_latency += rec.get("latency_ms", 0.0)

        return {
            "total_routes": total,
            "success": success,
            "failure": total - success,
            "avg_latency_ms": round(total_latency / total, 2) if total else 0.0,
            "log_size_bytes": self.log_path.stat().st_size,
        }

    @contextmanager
    def span(self, query: str, **kwargs: object) -> Generator[RouteSpan, None, None]:
        """Context manager that auto-logs on exit.

        Usage::

            with telemetry.span("my query") as s:
                s.selected = "some_skill"
                s.success = True
        """
        s = self.start_span(query)
        try:
            yield s
        finally:
            self.end_span(
                s,
                selected=s.selected,
                success=s.success,
                latency_ms=s.latency_ms,
                candidates=s.candidates,
                circuit_triggered=s.circuit_triggered,
                fallback_used=s.fallback_used,
            )
