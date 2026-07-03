"""Tests for the Loop Card System."""

from __future__ import annotations

import json
import os
import tempfile
import time

import pytest

# Ensure skill_weave is importable
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from skill_weave.card import (
    ArchitectureCard,
    CardChain,
    LoopCard,
    card_from_json,
)


# --- Fixtures ---------------------------------------------------------------

@pytest.fixture
def tmp_jsonl(tmp_path):
    return str(tmp_path / "test_cards.jsonl")


@pytest.fixture
def chain(tmp_jsonl):
    return CardChain(tmp_jsonl)


def _make_card(task: str = "test task", skill: str = "alpha", result: str = "PASS", **kw) -> LoopCard:
    return LoopCard(task=task, selected_skill=skill, result=result, **kw)


# --- LoopCard ---------------------------------------------------------------

class TestLoopCard:
    def test_create_defaults(self):
        c = _make_card()
        assert c.result == "PASS"
        assert c.loop_id  # auto-generated
        assert c.timestamp > 0
        assert c.new_facts == []
        assert c.warnings == []

    def test_roundtrip_json(self):
        c = _make_card(
            task="deploy service",
            skill="k8s-deploy",
            result="FAIL",
            warnings=["timeout"],
            weight_delta={"alpha": -0.02},
            next_hint="retry with backoff",
        )
        line = c.to_json()
        c2 = LoopCard.from_json(line)
        assert c2.loop_id == c.loop_id
        assert c2.task == "deploy service"
        assert c2.result == "FAIL"
        assert c2.warnings == ["timeout"]
        assert c2.weight_delta == {"alpha": -0.02}
        assert c2.next_hint == "retry with backoff"

    def test_compact(self):
        c = _make_card(task="fix the thing that broke", skill="debugger")
        compact = c.compact
        assert "PASS" in compact
        assert "debugger" in compact

    def test_summary(self):
        c = _make_card(warnings=["slow"], next_hint="use cache")
        s = c.summary
        assert c.loop_id in s
        assert "⚠1" in s
        assert "use cache" in s

    def test_from_dict_ignores_extra(self):
        d = _make_card().to_dict()
        d["_card_type"] = "LoopCard"
        d["extra_garbage"] = 42
        c = LoopCard.from_dict(d)
        assert c.result == "PASS"


# --- ArchitectureCard -------------------------------------------------------

class TestArchitectureCard:
    def test_create(self):
        ac = ArchitectureCard(
            task="migrate to v2 router",
            selected_skill="router-v2",
            result="PASS",
            gene_before={"scoring": "linear"},
            gene_after={"scoring": "attention"},
            migration_phase="canary",
        )
        assert ac.gene_before == {"scoring": "linear"}
        assert ac.migration_phase == "canary"
        assert ac.result == "PASS"

    def test_roundtrip_json(self):
        ac = ArchitectureCard(
            task="refactor pipeline",
            selected_skill="pipeline-v2",
            result="NEEDS_HUMAN",
            gene_before={"topology": "linear"},
            gene_after={"topology": "dag"},
            pilot_result={"latency_ms": 120, "accuracy": 0.95},
            migration_phase="shadow",
        )
        d = ac.to_dict()
        assert d["_card_type"] == "ArchitectureCard"
        ac2 = ArchitectureCard.from_dict(d)
        assert ac2.gene_after == {"topology": "dag"}
        assert ac2.pilot_result["latency_ms"] == 120

    def test_factory_deserialisation(self):
        ac = ArchitectureCard(
            task="x",
            selected_skill="y",
            result="PASS",
            gene_before={"a": 1},
            gene_after={"a": 2},
        )
        c = card_from_json(ac.to_json())
        assert isinstance(c, ArchitectureCard)
        assert c.gene_after == {"a": 2}

    def test_inherits_loop_card(self):
        ac = ArchitectureCard(task="t", selected_skill="s", result="PASS")
        assert isinstance(ac, LoopCard)
        assert ac.summary  # inherited property works


# --- CardChain --------------------------------------------------------------

class TestCardChain:
    def test_empty_chain(self, chain):
        assert chain.last() is None
        assert chain.last_n(5) == []
        assert chain.count() == 0

    def test_append_and_last(self, chain):
        c1 = _make_card(task="step 1", result="PASS")
        chain.append(c1)
        assert chain.last().loop_id == c1.loop_id
        assert chain.count() == 1

    def test_append_multiple_and_last_n(self, chain):
        ids = []
        for i in range(5):
            c = _make_card(task=f"step {i}", result="PASS")
            chain.append(c)
            ids.append(c.loop_id)
        assert chain.count() == 5
        last3 = chain.last_n(3)
        assert len(last3) == 3
        assert [c.loop_id for c in last3] == ids[-3:]

    def test_last_n_more_than_available(self, chain):
        chain.append(_make_card(task="only one"))
        assert len(chain.last_n(10)) == 1

    def test_decision_trail(self, chain):
        chain.append(_make_card(task="deploy production", result="PASS"))
        chain.append(_make_card(task="test staging", result="FAIL"))
        chain.append(_make_card(
            task="fix prod issue",
            result="NEEDS_HUMAN",
            open_decisions=["should we rollback?"],
        ))
        trail = chain.decision_trail("prod")
        assert len(trail) == 2  # "deploy production" + "fix prod issue"

    def test_decision_trail_by_warning(self, chain):
        chain.append(_make_card(warnings=["timeout on prod endpoint"]))
        assert len(chain.decision_trail("timeout")) == 1

    def test_decision_trail_no_match(self, chain):
        chain.append(_make_card(task="unrelated"))
        assert chain.decision_trail("nonexistent") == []

    def test_jsonl_persistence(self, tmp_jsonl):
        """Cards survive across chain instances."""
        c1 = CardChain(tmp_jsonl)
        c1.append(_make_card(task="persist me"))
        c2 = CardChain(tmp_jsonl)
        assert c2.last().task == "persist me"

    def test_mixed_card_types(self, chain):
        """LoopCard and ArchitectureCard coexist in the same chain."""
        chain.append(_make_card(task="normal loop"))
        chain.append(ArchitectureCard(
            task="arch change",
            selected_skill="arch",
            result="PASS",
            gene_before={"x": 1},
            gene_after={"x": 2},
        ))
        assert chain.count() == 2
        cards = chain.last_n(2)
        assert isinstance(cards[0], LoopCard)
        assert isinstance(cards[1], ArchitectureCard)

    def test_corrupt_lines_skipped(self, tmp_jsonl):
        with open(tmp_jsonl, "w") as f:
            f.write("not json\n")
            f.write(_make_card(task="good").to_json() + "\n")
            f.write("{bad json\n")
        chain = CardChain(tmp_jsonl)
        assert chain.count() == 1
        assert chain.last().task == "good"

    def test_cache_invalidation(self, chain):
        chain.append(_make_card(task="first"))
        assert chain.count() == 1
        chain.append(_make_card(task="second"))
        assert chain.count() == 2  # cache refreshed


# --- context_for_delegate ---------------------------------------------------

class TestContextForDelegate:
    def test_empty_chain(self, chain):
        ctx = chain.context_for_delegate()
        assert "no history" in ctx

    def test_format_with_cards(self, chain):
        chain.append(_make_card(task="deploy v1", skill="k8s", result="PASS", next_hint="try blue-green"))
        chain.append(_make_card(
            task="verify health",
            skill="monitor",
            result="FAIL",
            warnings=["cpu spike"],
        ))
        chain.append(_make_card(task="rollback", skill="k8s", result="PASS"))
        ctx = chain.context_for_delegate()
        assert "[cards] last 3 loops:" in ctx
        assert "cpu spike" in ctx
        assert "try blue-green" in ctx
        # ~300 bytes: should be compact
        assert len(ctx.encode()) < 600

    def test_only_last_3(self, chain):
        for i in range(10):
            chain.append(_make_card(task=f"step {i}"))
        ctx = chain.context_for_delegate()
        # only 3 lines after header
        lines = ctx.strip().split("\n")
        assert len(lines) == 4  # header + 3 cards

    def test_injects_into_delegate_context(self, chain):
        chain.append(_make_card(task="do stuff", skill="alpha", result="PASS"))
        base_context = "You are a subagent.\n"
        full = base_context + chain.context_for_delegate()
        assert "do stuff" in full
        assert "You are a subagent" in full


# --- weight_snapshot --------------------------------------------------------

class TestWeightSnapshot:
    def test_empty(self, chain):
        assert chain.weight_snapshot() == {}

    def test_aggregation(self, chain):
        chain.append(_make_card(weight_delta={"alpha": 0.1, "beta": -0.05}))
        chain.append(_make_card(weight_delta={"alpha": 0.2, "gamma": 0.3}))
        snap = chain.weight_snapshot(n=5)
        assert abs(snap["alpha"] - 0.3) < 1e-9
        assert abs(snap["beta"] - (-0.05)) < 1e-9
        assert abs(snap["gamma"] - 0.3) < 1e-9

    def test_none_weight_delta(self, chain):
        chain.append(_make_card(weight_delta=None))
        assert chain.weight_snapshot() == {}
