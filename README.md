# Skill Weave

**Adaptive skill routing for multi-agent systems.**

Skill Weave dynamically matches incoming tasks to the most appropriate skill or agent capability using a weighted multi-dimensional classifier. Instead of hard-coding task-to-skill mappings, it learns which skills weave together for optimal task completion.

## The Problem

Multi-agent systems accumulate skills over time — dozens, then hundreds. When a new task arrives, the system needs to decide: *which skill handles this best?* Most approaches use simple keyword matching or static routing tables. They break when skills overlap, when tasks span multiple domains, or when the skill inventory grows beyond what any human can manually curate.

## How It Works

Skill Weave uses a **4-dimensional scoring model** to rank candidate skills:

```
score = α·semantic + β·recency + γ·success_rate + δ·cost
```

| Dimension | What it measures | Default weight |
|-----------|-----------------|----------------|
| **Semantic** | Embedding similarity between task description and skill metadata | 0.45 |
| **Recency** | How recently the skill was used successfully (temporal decay) | 0.20 |
| **Success Rate** | Historical completion rate for similar tasks | 0.25 |
| **Cost** | Token/time cost of invoking this skill (lower = better) | 0.10 |

The router doesn't just pick one skill — it returns a **ranked weave** of complementary skills when a task spans multiple domains.

## Quick Start

```python
from skill_weave import SkillRouter

router = SkillRouter()
router.register_skill("code-review", metadata="Review code for bugs, security, style")
router.register_skill("deploy", metadata="Deploy services to production infrastructure")
router.register_skill("monitor", metadata="Monitor system health and alert on anomalies")

result = router.route("Check if the new deployment broke anything")
# → [{'skill': 'monitor', 'score': 0.89}, {'skill': 'code-review', 'score': 0.72}]
```

## Architecture

```
┌──────────────┐
│ Task Input   │
└──────┬───────┘
       ▼
┌──────────────┐    ┌─────────────────┐
│  Embedding   │───▶│ Skill Registry  │
│  Encoder     │    │ (metadata +     │
└──────────────┘    │  history)       │
       │            └────────┬────────┘
       ▼                     ▼
┌──────────────────────────────────────┐
│         Scoring Engine               │
│  semantic × recency × success × cost │
└──────────────────┬───────────────────┘
                   ▼
            ┌─────────────┐
            │ Ranked Weave │
            └─────────────┘
```

## Features

- **Dynamic registration** — add/remove skills at runtime
- **Historical learning** — success rates update after each task completion
- **Cost-aware routing** — respects token budgets and latency constraints
- **Multi-skill weave** — returns ranked combinations for cross-domain tasks
- **Zero dependencies** — pure Python core, optional embedding providers

## Status

Early development. Core routing engine functional, embedding integration in progress.

## License

MIT

---

*Built by [FeiMing Studio](https://github.com/Hxh-yaoxing) — where humans and agents build together.*
