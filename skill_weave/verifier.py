"""Verification layer for skill-weave — Maker-Checker separation.

Independent Verifier uses a different model to check routing execution results.
Contract-based: explicit PASS/FAIL conditions, no ambiguous space.

Design reference: bridge/verifier-design-2026-06-27.md
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    requests = None


def _load_novita_key() -> str:
    """Load NOVITA_API_KEY from env or .env file."""
    key = os.environ.get("NOVITA_API_KEY")
    if key:
        return key
    env_path = os.path.expanduser("/opt/data/.env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("NOVITA_API_KEY="):
                return line.split("=", 1)[1].strip()
    return ""


@dataclass
class Check:
    """A single verifiable condition.

    Args:
        description: Human-readable description of the check.
        command: Shell command. Exit code 0 = PASS, non-zero = FAIL.
        assertion: LLM judgment (e.g. "output contains 5+ bullet points").
        evidence: Evidence source ('auto' = infer from command/assertion).
    """
    description: str
    command: str | None = None
    assertion: str | None = None
    evidence: str = "auto"


@dataclass
class VerificationContract:
    """Verifiable success conditions for a skill execution.

    All checks must pass for the contract to be satisfied.
    """
    skill_name: str
    checks: list[Check]
    max_cost: float = 0.01
    model: str = "qwen/qwen3.7-max"
    timeout_seconds: int = 30
    on_fail: str = "flag_needs_human"


@dataclass
class VerificationResult:
    """Result of a verification pass."""
    passed: bool
    contract_id: str
    checks_passed: int
    checks_total: int
    failures: list[str]
    evidence: str
    verifier_model: str
    latency_ms: float


class RouteVerifier:
    """Independent verifier that checks routing execution results.

    Uses a different model (default qwen/qwen3.7-max via Novita) to avoid
    "grading your own homework". Command checks go through subprocess,
    assertion checks go through LLM.

    Usage:
        verifier = RouteVerifier()
        result = verifier.quick_verify(
            "deep-research-pro",
            "search AI papers",
            "Found 10 papers: 1. ...",
            ["output contains at least 5 items", "no placeholder text"],
        )
        print(result.passed)  # True/False
    """

    def __init__(self, model: str = "qwen/qwen3.7-max", api_key: str = ""):
        self.model = model
        self.api_key = api_key or _load_novita_key()
        self._api_url = "https://api.novita.ai/v3/openai/chat/completions"
        self._api_available = bool(self.api_key and len(self.api_key) > 10)

    def verify(
        self,
        contract: VerificationContract,
        context: dict,
    ) -> VerificationResult:
        """Execute full verification against a contract.

        Args:
            contract: The verification contract with checks.
            context: Dict with keys: skill_name, task, result_summary, output_snippet.

        Returns:
            VerificationResult with pass/fail and evidence.
        """
        start = time.time()
        passed_count = 0
        failures = []
        evidence_parts = []
        contract_id = f"{contract.skill_name}-{int(start)}"

        for check in contract.checks:
            try:
                if check.command is not None:
                    ok, ev = self._run_command_check(check.command)
                elif check.assertion is not None:
                    ok, ev = self._run_llm_check(check.assertion, context.get("output_snippet", ""))
                else:
                    # No command or assertion — treat as informational, auto-pass
                    ok, ev = True, "no check specified (informational)"

                if ok:
                    passed_count += 1
                else:
                    failures.append(check.description)
                evidence_parts.append(f"[{check.description}] {ev}")
            except Exception as e:
                failures.append(f"{check.description} (error: {e})")
                evidence_parts.append(f"[{check.description}] ERROR: {e}")

        latency_ms = (time.time() - start) * 1000
        return VerificationResult(
            passed=(passed_count == len(contract.checks)),
            contract_id=contract_id,
            checks_passed=passed_count,
            checks_total=len(contract.checks),
            failures=failures,
            evidence="\n".join(evidence_parts),
            verifier_model=self.model,
            latency_ms=round(latency_ms, 1),
        )

    def quick_verify(
        self,
        skill_name: str,
        task: str,
        output: str,
        checks: list[str],
    ) -> VerificationResult:
        """Quick verification without a pre-defined contract.

        Args:
            skill_name: Name of the skill that produced the output.
            task: Original task description.
            output: The output to verify.
            checks: List of assertion strings (each becomes a Check with LLM assertion).

        Returns:
            VerificationResult.
        """
        contract = VerificationContract(
            skill_name=skill_name,
            checks=[
                Check(description=c, assertion=c) for c in checks
            ],
        )
        context = {
            "skill_name": skill_name,
            "task": task,
            "output_snippet": output,
        }
        return self.verify(contract, context)

    def _run_command_check(self, command: str) -> tuple[bool, str]:
        """Run a shell command. Exit 0 = PASS."""
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return True, f"exit 0 | stdout: {result.stdout.strip()[:200]}"
            else:
                return False, f"exit {result.returncode} | stderr: {result.stderr.strip()[:200]}"
        except subprocess.TimeoutExpired:
            return False, "command timed out (10s)"
        except Exception as e:
            return False, f"command error: {e}"

    def _run_llm_check(self, assertion: str, output: str) -> tuple[bool, str]:
        """Call Novita API to judge an assertion against output."""
        if not self._api_available:
            return self._fallback_llm_check(assertion, output), "heuristic (no API key)"

        try:
            resp = requests.post(
                self._api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                f"判定以下断言是否为真。只回答 PASS 或 FAIL。\n"
                                f"断言：{assertion}"
                            ),
                        },
                        {
                            "role": "user",
                            "content": output[:3000],
                        },
                    ],
                    "max_tokens": 10,
                    "temperature": 0,
                },
                timeout=15,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"].upper()
            passed = "PASS" in content
            return passed, f"LLM says: {content.strip()}"
        except requests.RequestException as e:
            # API unavailable — fallback to heuristic
            return self._fallback_llm_check(assertion, output), f"API error ({e}), used heuristic"
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            return self._fallback_llm_check(assertion, output), f"Parse error ({e}), used heuristic"

    def _fallback_llm_check(self, assertion: str, output: str) -> bool:
        """Heuristic fallback when LLM API is unavailable.

        Simple keyword/length based checks. Conservative: defaults to False
        (fail) when uncertain, to avoid false positives.
        """
        output_lower = output.lower()
        assertion_lower = assertion.lower()

        # "contains" / "有" checks — verify keyword presence
        for keyword in ["包含", "包含至少", "contains", "has at least", "有"]:
            if keyword in assertion_lower:
                # Extract number if present
                import re
                nums = re.findall(r'\d+', assertion)
                if nums:
                    n = int(nums[0])
                    # Count bullet points, lines, or items
                    lines = [l.strip() for l in output.split('\n') if l.strip()]
                    items = [l for l in lines if l.startswith(('-', '*', '•', '1', '2', '3', '4', '5', '6', '7', '8', '9'))]
                    return len(items) >= n or len(lines) >= n

        # "no placeholder" / "无占位符" checks
        for keyword in ["placeholder", "TODO", "TBD", "占位符", "无占位符"]:
            if keyword in assertion_lower:
                has_placeholder = any(
                    p in output_lower for p in ["todo", "tbd", "placeholder", "占位符"]
                )
                return not has_placeholder

        # "至少" / "at least" generic — check minimum content length
        if "至少" in assertion_lower or "at least" in assertion_lower:
            return len(output.strip()) > 50

        # Default: conservative fail
        return False
