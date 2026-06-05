"""Skill composition engine — the "weave" in Skill Weave.

Enables multi-skill orchestration: sequential chains, parallel branches,
conditional routing, and DAG-based execution plans.

Core concept: a Weave is a directed acyclic graph (DAG) of skill invocations.
Nodes = skills, edges = data/control flow dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from .router import Skill, SkillRouter


class NodeType(Enum):
    SKILL = "skill"
    MERGE = "merge"  # collects outputs from parallel branches
    CONDITION = "condition"  # if-then-else branching


class MergeStrategy(Enum):
    CONCAT = "concat"  # concatenate outputs
    FIRST = "first"  # take first non-empty output
    VOTE = "vote"  # majority/consensus
    JSON_MERGE = "json_merge"  # deep-merge JSON outputs


@dataclass
class WeaveNode:
    """A node in the skill DAG."""

    id: str
    type: NodeType = NodeType.SKILL
    skill_name: str | None = None  # for SKILL nodes
    condition: str | None = None  # for CONDITION nodes: Python expression
    merge_strategy: MergeStrategy = MergeStrategy.CONCAT  # for MERGE nodes
    metadata: dict = field(default_factory=dict)

    # Execution state
    executed: bool = False
    output: Any = None
    error: str | None = None


@dataclass
class WeaveEdge:
    """Directed edge: from_node → to_node."""

    from_node: str
    to_node: str
    label: str = ""  # optional label (e.g., "on_success", "on_failure")


@dataclass
class WeaveChain:
    """A named multi-skill workflow."""

    name: str
    description: str = ""
    nodes: list[WeaveNode] = field(default_factory=list)
    edges: list[WeaveEdge] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    success_count: int = 0
    total_count: int = 0

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.total_count, 1)


class WeavePlanner:
    """Plans and manages multi-skill execution DAGs.

    Two modes:
    1. **Manual** — register explicit chains (A→B→C)
    2. **Auto** — use the router to suggest a chain based on task description

    Usage:
        router = SkillRouter()
        router.register_skill("fetch", ...)
        router.register_skill("analyze", ...)

        planner = WeavePlanner(router)
        planner.register_chain("research", ["fetch", "analyze"])

        plan = planner.plan("research AI safety")
        # → WeaveChain with ordered nodes
    """

    def __init__(self, router: SkillRouter):
        self.router = router
        self._chains: dict[str, WeaveChain] = {}

    # ── Chain Registration ──

    def register_chain(
        self,
        name: str,
        skills: list[str],
        description: str = "",
        tags: list[str] | None = None,
        parallel: list[tuple[str, str]] | None = None,
        conditions: dict[int, tuple[str, str]] | None = None,
    ) -> WeaveChain:
        """Register a named skill chain.

        Args:
            name: Chain identifier
            skills: Ordered skill names for sequential execution
            description: Human-readable description
            tags: Categorization tags
            parallel: Pairs of (skill_a, skill_b) that run in parallel branches
            conditions: {position: (condition_expr, alt_skill)} for branching
                e.g., {1: ("output.contains('error')", "fallback_handler")}

        Returns:
            The registered WeaveChain

        Example:
            planner.register_chain(
                "data-pipeline",
                skills=["fetch_data", "validate", "store"],
                conditions={1: ("not output['valid']", "flag_invalid")},
            )
            # → fetch_data → if valid: store / else: flag_invalid
        """
        chain = WeaveChain(name=name, description=description, tags=tags or [])
        nodes: list[WeaveNode] = []
        edges: list[WeaveEdge] = []

        # Identify parallel groups
        parallel_set: set[str] = set()
        if parallel:
            for a, b in parallel:
                parallel_set.add(a)
                parallel_set.add(b)

        # Build nodes
        for i, skill_name in enumerate(skills):
            node_id = f"{name}_{i}_{skill_name}"

            if conditions and i in conditions:
                # Conditional node
                cond_expr, alt_skill = conditions[i]
                cond_node = WeaveNode(
                    id=f"{node_id}_cond",
                    type=NodeType.CONDITION,
                    condition=cond_expr,
                )
                nodes.append(cond_node)

                # Primary path
                primary = WeaveNode(
                    id=node_id,
                    type=NodeType.SKILL,
                    skill_name=skill_name,
                )
                nodes.append(primary)
                edges.append(WeaveEdge(cond_node.id, primary.id, "on_match"))

                # Alternative path
                alt_id = f"{name}_{i}_{alt_skill}"
                alternative = WeaveNode(
                    id=alt_id,
                    type=NodeType.SKILL,
                    skill_name=alt_skill,
                )
                nodes.append(alternative)
                edges.append(WeaveEdge(cond_node.id, alt_id, "on_miss"))

                # Merge both paths
                merge_id = f"{name}_{i}_merge"
                merge = WeaveNode(
                    id=merge_id,
                    type=NodeType.MERGE,
                    merge_strategy=MergeStrategy.FIRST,
                )
                nodes.append(merge)
                edges.append(WeaveEdge(primary.id, merge_id))
                edges.append(WeaveEdge(alt_id, merge_id))
            else:
                node = WeaveNode(
                    id=node_id,
                    type=NodeType.SKILL,
                    skill_name=skill_name,
                )
                nodes.append(node)

        # Add sequential edges between consecutive nodes (skip condition/merge internals)
        skill_nodes = [n for n in nodes if n.type == NodeType.SKILL]
        for i in range(len(skill_nodes) - 1):
            edges.append(WeaveEdge(skill_nodes[i].id, skill_nodes[i + 1].id))

        chain.nodes = nodes
        chain.edges = edges
        self._chains[name] = chain
        return chain

    def register_chain_simple(
        self,
        name: str,
        skills: list[str],
        description: str = "",
        merge_strategy: MergeStrategy = MergeStrategy.CONCAT,
    ) -> WeaveChain:
        """Quick registration of a simple sequential chain A→B→C.

        This is the most common use case. For parallel or conditional chains,
        use register_chain() with the full API.
        """
        chain = WeaveChain(name=name, description=description)
        nodes = []
        edges = []

        for i, skill_name in enumerate(skills):
            node_id = f"{name}_{i}"
            node = WeaveNode(id=node_id, skill_name=skill_name)
            nodes.append(node)
            if i > 0:
                edges.append(WeaveEdge(nodes[i - 1].id, node.id))

        # Add final merge node
        if len(skills) > 1:
            merge = WeaveNode(
                id=f"{name}_merge",
                type=NodeType.MERGE,
                merge_strategy=merge_strategy,
            )
            nodes.append(merge)
            edges.append(WeaveEdge(nodes[-2].id, merge.id))

        chain.nodes = nodes
        chain.edges = edges
        self._chains[name] = chain
        return chain

    # ── Planning ──

    def plan(self, task: str, max_depth: int = 3) -> WeaveChain | None:
        """Suggest a skill chain for a complex task.

        First checks registered chains by keyword match, then falls back
        to auto-planning using the router.

        Args:
            task: Natural language task description
            max_depth: Maximum chain length

        Returns:
            A WeaveChain if one can be planned, None otherwise
        """
        # Try registered chains first
        task_lower = task.lower().replace("-", " ")
        for name, chain in self._chains.items():
            name_lower = name.lower().replace("-", " ")
            if name_lower in task_lower:
                return chain

        # Auto-plan: use router to find candidate skills
        candidates = self.router.route(task, top_k=max_depth + 2)

        if not candidates:
            return None

        # Take top candidates and build a chain
        top_skills = [r.skill.name for r in candidates[:max_depth]]
        chain_name = f"auto_{hash(task) % 10000}"

        return self.register_chain_simple(
            name=chain_name,
            skills=top_skills,
            description=f"Auto-generated chain for: {task[:80]}",
        )

    def plan_deep(
        self, task: str, max_depth: int = 3
    ) -> list[list[str]]:
        """Plan multiple alternative chains for the same task.

        Returns up to 3 alternative skill sequences.
        """
        candidates = self.router.route(task, top_k=max_depth * 3)
        if not candidates:
            return []

        skill_names = [r.skill.name for r in candidates]
        alternatives = []

        # Chain 1: top-k direct
        alternatives.append(skill_names[:max_depth])

        # Chain 2: interleaved (every other)
        if len(skill_names) >= max_depth * 2:
            alt2 = []
            for i in range(max_depth):
                alt2.append(skill_names[i * 2])
            alternatives.append(alt2)

        return alternatives

    # ── Chain Management ──

    @property
    def chains(self) -> dict[str, WeaveChain]:
        return dict(self._chains)

    def get_chain(self, name: str) -> WeaveChain | None:
        return self._chains.get(name)

    def remove_chain(self, name: str) -> bool:
        return self._chains.pop(name, None) is not None

    def record_chain_outcome(self, name: str, success: bool) -> None:
        """Record execution outcome for a chain."""
        chain = self._chains.get(name)
        if chain:
            chain.total_count += 1
            if success:
                chain.success_count += 1

    def stats(self) -> dict:
        """Statistics about registered chains."""
        return {
            "total_chains": len(self._chains),
            "chains": {
                name: {
                    "description": c.description,
                    "nodes": len(c.nodes),
                    "success_rate": round(c.success_rate, 3),
                    "executions": c.total_count,
                }
                for name, c in self._chains.items()
            },
        }
