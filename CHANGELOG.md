# Changelog

All notable changes to Skill Weave will be documented in this file.

---

## [0.3.0] — 2026-06-05

### Added
- **`FeedbackLearner`** (`learner.py`): Online learning engine using UCB bandit for exploration/exploitation balance and gradient-informed weight adjustment for 4-dimension scoring.
- **`WeavePlanner`** (`weaver.py`): Multi-skill DAG orchestration with sequential chains, conditional branching, and parallel merge strategies.
- 11 new tests covering active learning and skill weaving (20 total).
- Colab demo notebook with four interactive scenarios.

### Changed
- All heavy imports moved to lazy `__getattr__` — core `SkillRouter` remains zero-dependency.
- TreeFilter now includes synonym expansion for Chinese-English cross-lingual matching.
- TreeFilter fallback: when no candidates match, routes BM25 over all non-T3 skills instead of returning empty.

### Fixed
- `WeavePlanner.plan()` chain name matching now normalizes hyphens in both query and chain names.

---

## [0.2.0] — 2026-06-05

### Added
- **`SkillWeave`** (`advanced.py`): 3-stage pipeline — Tree Filter → BM25 → LLM Re-rank.
- **`TreeFilter`**: Zero-token hierarchy + keyword coarse filtering.
- **`BM25Scorer`**: Character-level 2-gram (Chinese) + word-level (English) statistical retrieval.
- **`annotate`** module: 4-dimension skill metadata generation and injection.
- 23-query benchmark suite with real-world routing test cases.
- Tier system: T1 (core), T2 (on-demand), T3 (cold-storage).

---

## [0.1.0] — 2026-06-05

### Added
- **`SkillRouter`**: Core routing engine with 4-dimension weighted scoring (semantic × recency × success × cost).
- `Skill` and `RouteResult` data classes.
- Dynamic skill registration, unregistration, and outcome recording.
- Cosine similarity + keyword fallback for embedding-optional deployments.
- Cost filtering and tag filtering.
- 9 unit tests covering registration, routing, outcomes, filtering, recency, and top-k.
- `pyproject.toml` with MIT license.
- Initial README with architecture diagram and quick start.
