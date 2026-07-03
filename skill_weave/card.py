"""Loop Card System — lightweight context for multi-turn skill routing.

Each loop cycle writes a LoopCard (~200 bytes) summarising the round.
The next cycle reads only the card chain, not full MEMORY.md.
ArchitectureCard extends LoopCard for gene-mutation tracking.
CardChain manages JSONL append-only storage with query helpers.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

DEFAULT_CARD_DIR = "/opt/data/shared/cards/default"
DEFAULT_JSONL = os.path.join(DEFAULT_CARD_DIR, "loop_cards.jsonl")


@dataclass
class LoopCard:
    """One cycle's summary — the atomic unit of loop memory."""

    task: str
    selected_skill: str
    result: str  # "PASS" | "FAIL" | "NEEDS_HUMAN" | "SKIPPED"
    next_hint: str = ""
    weight_delta: dict | None = None
    new_facts: list[str] = field(default_factory=list)
    open_decisions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    previous_card_id: str | None = None
    loop_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)

    # ---- serialisation --------------------------------------------------

    def to_dict(self) -> dict:
        d = asdict(self)
        d["_card_type"] = type(self).__name__
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, separators=(",", ":"))

    @classmethod
    def from_dict(cls, d: dict) -> LoopCard:
        d = dict(d)  # shallow copy
        d.pop("_card_type", None)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, line: str) -> LoopCard:
        return cls.from_dict(json.loads(line))

    # ---- convenience ----------------------------------------------------

    @property
    def summary(self) -> str:
        """~120-char human-readable summary."""
        warn = f" ⚠{len(self.warnings)}" if self.warnings else ""
        hint = f" →{self.next_hint[:40]}" if self.next_hint else ""
        return f"[{self.loop_id}] {self.selected_skill} → {self.result}{warn}{hint}"

    @property
    def compact(self) -> str:
        """Minimal one-liner for delegate context."""
        return f"{self.result}|{self.selected_skill}|{self.task[:60]}"


@dataclass
class ArchitectureCard(LoopCard):
    """Extended card for architecture gene mutations."""

    gene_before: dict = field(default_factory=dict)
    gene_after: dict = field(default_factory=dict)
    pilot_result: dict | None = None
    migration_phase: str | None = None  # "shadow" | "canary" | "full" | None

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["_card_type"] = "ArchitectureCard"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ArchitectureCard:
        d = dict(d)
        d.pop("_card_type", None)
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# --- Card type registry for deserialisation -------------------------------

_CARD_TYPES: dict[str, type[LoopCard]] = {
    "LoopCard": LoopCard,
    "ArchitectureCard": ArchitectureCard,
}


def card_from_json(line: str) -> LoopCard:
    """Factory: deserialise the correct card subclass from a JSONL line."""
    d = json.loads(line)
    cls_name = d.get("_card_type", "LoopCard")
    cls = _CARD_TYPES.get(cls_name, LoopCard)
    return cls.from_dict(d)


# --- CardChain ------------------------------------------------------------

class CardChain:
    """Append-only JSONL card store with query helpers."""

    def __init__(self, jsonl_path: str = DEFAULT_JSONL):
        self.path = Path(jsonl_path)
        self._cache: list[LoopCard] | None = None

    # ---- storage --------------------------------------------------------

    def _ensure_dir(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, card: LoopCard) -> None:
        """Append a card to the JSONL chain."""
        self._ensure_dir()
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(card.to_json() + "\n")
        # invalidate cache
        self._cache = None

    def _load(self) -> list[LoopCard]:
        if self._cache is not None:
            return self._cache
        cards: list[LoopCard] = []
        if self.path.exists():
            with open(self.path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            cards.append(card_from_json(line))
                        except (json.JSONDecodeError, TypeError, KeyError):
                            continue  # skip corrupt lines
        self._cache = cards
        return cards

    # ---- queries --------------------------------------------------------

    def last(self) -> LoopCard | None:
        cards = self._load()
        return cards[-1] if cards else None

    def last_n(self, n: int = 3) -> list[LoopCard]:
        cards = self._load()
        return cards[-n:]

    def decision_trail(self, keyword: str) -> list[str]:
        """Return loop_ids of cards whose task/warnings/open_decisions contain keyword."""
        kw = keyword.lower()
        ids: list[str] = []
        for card in self._load():
            haystack = " ".join(
                [card.task]
                + card.warnings
                + card.open_decisions
            ).lower()
            if kw in haystack:
                ids.append(card.loop_id)
        return ids

    def count(self) -> int:
        return len(self._load())

    # ---- delegate context -----------------------------------------------

    def context_for_delegate(self) -> str:
        """Generate a ~300-byte context snippet from the last 3 cards.

        Inject into delegate_task context:
            context += card_chain.context_for_delegate()
        """
        cards = self.last_n(3)
        if not cards:
            return "[cards] no history"
        lines = ["[cards] last 3 loops:"]
        for c in cards:
            warnings = f" w={','.join(c.warnings)}" if c.warnings else ""
            hint = f" → {c.next_hint}" if c.next_hint else ""
            lines.append(
                f"  {c.loop_id} {c.selected_skill} {c.result} "
                f"task={c.task[:50]}{warnings}{hint}"
            )
        return "\n".join(lines)

    # ---- snapshot helpers -----------------------------------------------

    def weight_snapshot(self, n: int = 5) -> dict[str, float]:
        """Aggregate weight_delta from the last n cards."""
        agg: dict[str, float] = {}
        for card in self.last_n(n):
            if card.weight_delta:
                for k, v in card.weight_delta.items():
                    agg[k] = agg.get(k, 0.0) + v
        return agg
