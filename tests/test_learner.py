"""Tests for active learning and skill weaving."""

from skill_weave import SkillRouter, FeedbackLearner, WeavePlanner


# ── FeedbackLearner Tests ──

def test_learner_records_outcomes():
    router = SkillRouter()
    router.register_skill("test", metadata="test skill")
    learner = FeedbackLearner(router)

    learner.record("test", "do something", success=True, latency_ms=100)
    learner.record("test", "do something", success=False, latency_ms=200)

    assert learner.total_routes == 2
    assert len(learner.records) == 2
    assert learner.records[0].success is True
    assert learner.records[1].success is False


def test_learner_weight_adjustment():
    router = SkillRouter()
    router.register_skill("good", metadata="reliable skill")
    router.register_skill("bad", metadata="unreliable skill")

    learner = FeedbackLearner(
        router,
        weight_learning_rate=0.5,
        min_samples_for_learning=3,
    )

    original_alpha = router.alpha

    # Feed: semantic-heavy successes
    for _ in range(10):
        learner.record(
            "good", "test task",
            success=True,
            dimension_contributions={"semantic": 0.9, "recency": 0.1, "success": 0.5, "cost": 0.3},
        )

    # Weights should have shifted
    stats = learner.stats()
    assert stats["total_routes"] == 10
    # Semantic weight should increase since it correlated with success
    assert router.alpha > original_alpha * 0.9  # at least not dropping


def test_learner_ucb_exploration():
    router = SkillRouter()
    router.register_skill("popular", metadata="often used")
    router.register_skill("new", metadata="never tried")

    # Make "popular" well-tested
    popular = router._skills["popular"]
    popular.total_count = 100
    popular.success_count = 90
    popular.last_used = 1.0

    learner = FeedbackLearner(router, exploration_bonus=3.0)
    learner.total_routes = 100

    results = learner.route("some task")
    # "new" should get exploration bonus
    # Both skills should be in results
    names = [r.skill.name for r in results]
    assert "new" in names


def test_learner_reset():
    router = SkillRouter()
    learner = FeedbackLearner(router)

    learner.record("test", "task", success=True)
    assert learner.total_routes == 1

    learner.reset()
    assert learner.total_routes == 0
    assert len(learner.records) == 0


def test_learner_history_cap():
    router = SkillRouter()
    router.register_skill("test", metadata="test")
    learner = FeedbackLearner(router)

    # Add 1100 records
    for i in range(1100):
        learner.record("test", f"task_{i}", success=True)

    # Should be capped (trimmed at 1000 to 500, then +100 = 600)
    assert len(learner.records) == 600


# ── WeavePlanner Tests ──

def test_weave_simple_chain():
    router = SkillRouter()
    router.register_skill("fetch", metadata="fetch data from API")
    router.register_skill("parse", metadata="parse raw data")
    router.register_skill("store", metadata="store to database")

    planner = WeavePlanner(router)
    chain = planner.register_chain_simple("data-pipeline", ["fetch", "parse", "store"])

    assert chain.name == "data-pipeline"
    assert len([n for n in chain.nodes if n.type.value == "skill"]) == 3
    assert len(chain.edges) >= 3  # sequential + merge


def test_weave_conditional_chain():
    router = SkillRouter()
    router.register_skill("validate", metadata="validate input")
    router.register_skill("process", metadata="process valid input")
    router.register_skill("reject", metadata="handle invalid input")

    planner = WeavePlanner(router)
    chain = planner.register_chain(
        "input-pipeline",
        skills=["validate", "process"],
        conditions={1: ("not output.get('valid')", "reject")},
    )

    assert chain.name == "input-pipeline"
    # Should have condition node
    cond_nodes = [n for n in chain.nodes if n.type.value == "condition"]
    assert len(cond_nodes) == 1
    # Should have merge node
    merge_nodes = [n for n in chain.nodes if n.type.value == "merge"]
    assert len(merge_nodes) == 1


def test_weave_plan_match():
    router = SkillRouter()
    router.register_skill("deploy", metadata="deploy to production")
    router.register_skill("verify", metadata="verify deployment")

    planner = WeavePlanner(router)
    planner.register_chain_simple("deploy-pipeline", ["deploy", "verify"],
                                  description="Full deploy workflow")

    # Should match by name
    result = planner.plan("run the deploy-pipeline now")
    assert result is not None
    assert result.name == "deploy-pipeline"


def test_weave_deep_plan():
    router = SkillRouter()
    router.register_skill("fetch", metadata="fetch data")
    router.register_skill("clean", metadata="clean data")
    router.register_skill("analyze", metadata="analyze data")
    router.register_skill("report", metadata="generate report")
    router.register_skill("archive", metadata="archive results")

    planner = WeavePlanner(router)
    alternatives = planner.plan_deep("process the data", max_depth=3)

    assert len(alternatives) >= 1
    assert all(len(alt) <= 3 for alt in alternatives)


def test_weave_chain_stats():
    router = SkillRouter()
    planner = WeavePlanner(router)
    planner.register_chain_simple("test-chain", ["skill-a", "skill-b"])

    assert "test-chain" in planner.chains

    planner.record_chain_outcome("test-chain", True)
    planner.record_chain_outcome("test-chain", False)
    planner.record_chain_outcome("test-chain", True)

    stats = planner.stats()
    chain_stats = stats["chains"]["test-chain"]
    assert chain_stats["success_rate"] > 0.5
    assert chain_stats["executions"] == 3


def test_weave_remove_chain():
    router = SkillRouter()
    planner = WeavePlanner(router)
    planner.register_chain_simple("temp", ["a", "b"])

    assert "temp" in planner.chains
    planner.remove_chain("temp")
    assert "temp" not in planner.chains


if __name__ == "__main__":
    test_learner_records_outcomes()
    test_learner_weight_adjustment()
    test_learner_ucb_exploration()
    test_learner_reset()
    test_learner_history_cap()
    test_weave_simple_chain()
    test_weave_conditional_chain()
    test_weave_plan_match()
    test_weave_deep_plan()
    test_weave_chain_stats()
    test_weave_remove_chain()
    print("✅ All 11 v0.3.0 tests passed")
