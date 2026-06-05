"""Tests for the core routing engine."""

import time
from skill_weave import SkillRouter


def test_register_and_list():
    router = SkillRouter()
    router.register_skill("deploy", metadata="deploy to production")
    router.register_skill("review", metadata="code review")
    assert len(router.skills) == 2
    assert "deploy" in router.skills


def test_route_basic():
    router = SkillRouter()
    router.register_skill("deploy", metadata="deploy services to production server")
    router.register_skill("review", metadata="review code for quality and bugs")
    router.register_skill("monitor", metadata="monitor system health metrics")

    results = router.route("deploy the new service")
    assert len(results) > 0
    assert results[0].skill.name == "deploy"


def test_route_empty():
    router = SkillRouter()
    results = router.route("anything")
    assert results == []


def test_record_outcome():
    router = SkillRouter()
    router.register_skill("test-skill", metadata="testing")

    # no history → 0.5 success rate
    assert router.skills["test-skill"].success_rate == 0.5

    router.record_outcome("test-skill", success=True)
    assert router.skills["test-skill"].success_rate == 1.0

    router.record_outcome("test-skill", success=False)
    assert router.skills["test-skill"].success_rate == 0.5


def test_cost_filter():
    router = SkillRouter()
    router.register_skill("cheap", metadata="low cost task", avg_cost=0.1)
    router.register_skill("expensive", metadata="high cost task", avg_cost=0.9)

    results = router.route("any task", max_cost=0.5)
    names = [r.skill.name for r in results]
    assert "cheap" in names
    assert "expensive" not in names


def test_tag_filter():
    router = SkillRouter()
    router.register_skill("python-review", metadata="review python code", tags=["python", "code"])
    router.register_skill("infra-deploy", metadata="deploy infrastructure", tags=["devops", "infra"])

    results = router.route("check code", tags_filter=["python"])
    assert len(results) == 1
    assert results[0].skill.name == "python-review"


def test_recency_boost():
    router = SkillRouter(beta=0.5)  # high recency weight
    s1 = router.register_skill("old", metadata="old skill used long ago")
    s2 = router.register_skill("recent", metadata="recent skill just used")

    s1.last_used = time.time() - 7200  # 2 hours ago
    s2.last_used = time.time() - 60     # 1 minute ago

    # both match equally by keywords
    results = router.route("skill used")
    # recent should rank higher due to recency
    assert results[0].skill.name == "recent"


def test_unregister():
    router = SkillRouter()
    router.register_skill("temp", metadata="temporary")
    assert "temp" in router.skills
    router.unregister_skill("temp")
    assert "temp" not in router.skills


def test_top_k():
    router = SkillRouter()
    for i in range(20):
        router.register_skill(f"skill-{i}", metadata=f"skill number {i}")

    results = router.route("skill", top_k=3)
    assert len(results) == 3


if __name__ == "__main__":
    test_register_and_list()
    test_route_basic()
    test_route_empty()
    test_record_outcome()
    test_cost_filter()
    test_tag_filter()
    test_recency_boost()
    test_unregister()
    test_top_k()
    print("✅ All 9 tests passed")
