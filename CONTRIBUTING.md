# Contributing to Skill Weave

Thanks for being here. Skill Weave is built by **FeiMing Studio** — a small team of humans and AI agents collaborating openly. We ship fast, communicate directly, and welcome contributions of all sizes.

## Code of Conduct

Be direct. Be kind. Skip the corporate theater.

If you open an issue, you'll get a response from a real person (or agent) who cares about the project. We don't use templates. We just talk.

## What to Work On

| You Are | Good First Issues |
|---------|-------------------|
| **New to the project** | Improve docs, add type hints, write tutorials |
| **Comfortable with Python** | Optimize BM25 scorer, add embedding backends, fix edge cases |
| **Multi-agent systems person** | Add new merge strategies, chain templates, benchmark queries |
| **Frontend/UX person** | Colab notebook improvements, visualization tools, dashboards |

Browse [open issues](https://github.com/Hxh-yaoxing/skill-weave/issues) or open one to propose something new.

## Development Setup

```bash
# Clone
git clone https://github.com/Hxh-yaoxing/skill-weave.git
cd skill-weave

# Editable install
pip install -e ".[dev]"

# Run tests
python tests/test_router.py    # 9 core routing tests
python tests/test_learner.py   # 11 learning + weaving tests
```

That's it. No Docker, no database, no API keys needed for core development.

## Project Structure

```
skill_weave/
├── __init__.py      # Package entry, lazy imports (zero-dependency core)
├── router.py        # SkillRouter — 4-dim weighted scoring
├── advanced.py      # SkillWeave — 3-stage pipeline + BM25 + TreeFilter
├── annotate.py      # Skill annotation engine (PyYAML required)
├── learner.py       # FeedbackLearner — UCB bandit + online learning
└── weaver.py        # WeavePlanner — multi-skill DAG orchestration

benchmark/
└── queries.json     # 23 real-world routing test cases

notebooks/
└── skill_weave_demo.ipynb  # Colab: try before you read

tests/
├── test_router.py   # Core router tests
└── test_learner.py  # Learner + weaver tests
```

## Commit Style

We use **conventional commits**:

```
feat: add Thompson sampling exploration mode
fix: handle empty skill set in tree filter
docs: clarify 4-dim weight semantics
test: add edge case for empty query
refactor: extract BM25 scorer to separate module
```

Squash-merge to `main`. Keep PRs focused — one thing per PR.

## Before Submitting

- [ ] Tests pass: `python tests/test_router.py && python tests/test_learner.py`
- [ ] New code has tests covering happy path + edge cases
- [ ] If adding a new module, update `skill_weave/__init__.py` lazy imports
- [ ] If changing public API, update the README API Reference section
- [ ] Run the benchmark to check for regressions (if you have a skill directory available)

## Design Philosophy

Three principles guide every decision:

1. **Zero-dependency core.** `SkillRouter` must work with only Python stdlib. Optional features (annotation, LLM re-rank) can have deps, but the core must not.

2. **Lazy everything.** No heavy imports at package init. Use `__getattr__` to defer imports until first use. This keeps `import skill_weave` instant.

3. **Production-truth.** We don't claim capabilities we haven't tested. Every number in the README comes from actual deployment data. If you add a feature, benchmark it against real workloads.

## Getting Help

- Open an [issue](https://github.com/Hxh-yaoxing/skill-weave/issues) — we read every one
- Tag `@Hxh-yaoxing` for architectural questions
- Check the [Colab demo](https://colab.research.google.com/github/Hxh-yaoxing/skill-weave/blob/main/notebooks/skill_weave_demo.ipynb) for interactive examples

---

*We iterate fast and ship on weekends. If something breaks, we fix it. If something's confusing, we clarify it. Just talk to us.*
