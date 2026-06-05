# Skill Weave

**Adaptive skill routing for multi-agent systems.**

[![PyPI](https://img.shields.io/badge/python-3.10+-blue)](https://pypi.org/project/skill-weave)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-9%20passed-brightgreen)](tests/)

Skill Weave dynamically matches incoming tasks to the most appropriate skill or tool using a **3-stage routing pipeline**. It doesn't hard-code mappings — it learns which skills weave together for optimal task completion.

> **Production-proven**: Currently routing **141 skills** in a live multi-agent system with **95.7%** benchmark accuracy and **81%** context overhead reduction.

---

## The Problem

Multi-agent systems accumulate skills over time — dozens, then hundreds. When a new task arrives, the system needs to decide: *which skill handles this best?*

Most approaches fail at scale:
- **Keyword matching** breaks when skills overlap or tasks span multiple domains
- **Static routing tables** rot as skills are added, removed, or retrained
- **Flat LLM calls** burn tokens linearly with skill count — 141 skills means 141 candidates to rank

Skill Weave solves all three.

---

## How It Works

### 3-Stage Routing Pipeline

```
┌──────────────┐
│  Task Input   │
└──────┬───────┘
       ▼
┌──────────────────┐
│  L1: Tree Filter  │  ← Zero-token. Narrows 141 → ~15 candidates
│  (hierarchy +     │     using tree paths + synonyms + keyword overlap
│   synonym match)  │
└──────┬───────────┘
       ▼
┌──────────────────┐
│  L2: BM25 Rank    │  ← Statistical. Character-level + 2-gram Chinese,
│  (sparse retrieval)│     word-level English. Fast, no GPU needed.
└──────┬───────────┘
       ▼
┌──────────────────┐
│  L3: LLM Re-rank  │  ← Semantic. Deep reasoning over top ~10 candidates.
│  (optional)       │     Boosts accuracy from 69.6% → 95.7%
└──────────────────┘
```

### Two Routers, One Package

| Router | Use Case | Accuracy | Dependencies |
|--------|----------|----------|--------------|
| **`SkillRouter`** | Lightweight, no-LLM routing with 4-dim scoring | ~70% | Zero |
| **`SkillWeave`** | Production 3-stage pipeline with LLM re-rank | ~96% | PyYAML |

---

## Quick Start

```python
from skill_weave import SkillRouter

router = SkillRouter()
router.register_skill("code-review", metadata="Review code for bugs, security, style")
router.register_skill("deploy", metadata="Deploy services to production infrastructure")
router.register_skill("monitor", metadata="Monitor system health and alert on anomalies")

result = router.route("Check if the new deployment broke anything")
# → [RouteResult(skill='monitor', score=0.89), RouteResult(skill='code-review', score=0.72)]
```

### With the Production Pipeline

```python
from skill_weave import SkillWeave

# Point to your skill directory (SKILL.md files with YAML frontmatter)
sw = SkillWeave("/path/to/skills")

# Route a task — 3-stage pipeline runs automatically
results = sw.route("帮我搜索最新的AI论文", top_k=3)
# Without LLM: ~70% accuracy, instant
# With LLM re-rank: ~96% accuracy, ~1s latency

# Check your skill inventory
print(sw.stats)
# → {'total_skills': 141, 'tier_distribution': {1: 63, 2: 56, 3: 22}}
```

---

## 4-Dimension Skill Annotation

Every skill carries metadata for intelligent routing:

```yaml
# In your SKILL.md frontmatter:
where: |
  Code review and quality assurance workflows
when: |
  - User requests code review or PR audit
  - Security vulnerability scanning needed
  - Pre-commit quality checks
when_not: |
  - Architecture design (use architecture-diagram)
  - Runtime debugging (use systematic-debugging)
tree: devops > github > code-review
tier: 1  # 1=core, 2=on-demand, 3=cold-storage
```

Skills without annotations get rule-based fallbacks. Use the built-in annotation tool:

```python
from skill_weave import annotate_skill, inject_annotations

dims = annotate_skill("path/to/SKILL.md")
inject_annotations("path/to/SKILL.md", dims)
```

---

## Benchmark

23 real-world queries from a live multi-agent deployment:

| Stage | Accuracy | Latency | Token Cost |
|-------|----------|---------|------------|
| L1+L2 (Tree + BM25) | **69.6%** | <50ms | 0 |
| L1+L2+L3 (+ LLM re-rank) | **95.7%** | ~1s | ~2K tokens |

```python
from skill_weave import SkillWeave
import json

sw = SkillWeave("/opt/data/skills")
with open("benchmark/queries.json") as f:
    result = sw.run_benchmark(json.load(f), verbose=True)
# → Accuracy: 69.6% (16/23) without LLM
```

---

## Features

- **3-stage pipeline** — coarse → statistical → semantic, each stage filtering the next
- **81% context reduction** — Tree filter cuts 141 skills to ~15 before any LLM call
- **Tier system** — T1 (core/always), T2 (on-demand), T3 (cold-storage/skip)
- **Synonym expansion** — Chinese-English cross-lingual matching built in
- **Dynamic registration** — add/remove skills at runtime, no restart needed
- **Historical learning** — `SkillRouter` tracks success rates over time
- **Zero-dependency core** — `SkillRouter` is pure Python, no installs needed

---

## Installation

```bash
pip install skill-weave
```

For the full pipeline with skill annotation:

```bash
pip install skill-weave[full]  # includes PyYAML
```

---

## Architecture

```
skill_weave/
├── __init__.py      # Package entry, lazy imports
├── router.py        # SkillRouter: 4-dim weighted scoring
├── advanced.py      # SkillWeave: 3-stage pipeline + BM25 + TreeFilter
└── annotate.py      # Skill annotation engine + metadata loader

benchmark/
└── queries.json     # 23 real-world routing queries

tests/
└── test_router.py   # 9 unit tests, all passing
```

---

## Real-World Scale

This isn't a toy. Skill Weave routes **141 skills** across **63 categories** in a live multi-agent system:

| Metric | Value |
|--------|-------|
| Total skills | 141 |
| Tier 1 (core) | 63 |
| Tier 2 (on-demand) | 56 |
| Tier 3 (cold-storage) | 22 |
| Annotated | 138/141 |
| BM25 accuracy | 69.6% |
| LLM re-rank accuracy | 95.7% |
| Context reduction | 81% |

---

## Status

Active development. Core pipeline stable, embedding integration in progress. Used daily in production.

## License

MIT

---

*Built by [FeiMing Studio](https://github.com/Hxh-yaoxing) — where humans and agents build together.*
