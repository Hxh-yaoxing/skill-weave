"""Skill annotation engine — generates and manages 4-dimension metadata.

Dimensions: where (scene), when (triggers), when_not (exclusions), tree (hierarchy path).
"""

import json, re, sys, os, yaml
from pathlib import Path

DIMENSION_PROMPT = """You are a skill taxonomy expert. For the given skill, generate 4-dimension metadata.

## Skill Content
Name: {name}
Description: {description}

Body Summary:
{body_summary}

## Output Format
Output YAML with these 4 fields:

where: |
  <One sentence: what scenario/domain does this skill apply to?>
when: |
  <When should this skill be loaded? 2-4 trigger conditions>
when_not: |
  <When should this skill NOT be loaded? 2-4 exclusion conditions, reference alternative skill names>
tree: <Hierarchy path, e.g. "devops > ssh > nas-host-ops">

Only output YAML, no explanation."""


def annotate_skill(skill_path: str, llm_fn=None) -> dict:
    """Generate 4-dimension metadata for a skill file.

    Args:
        skill_path: Path to SKILL.md
        llm_fn: Optional function(text) -> str for LLM-based annotation

    Returns:
        Dict with where, when, when_not, tree keys
    """
    with open(skill_path) as f:
        content = f.read()

    if not content.startswith("---"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    fm = yaml.safe_load(parts[1]) or {}
    name = fm.get("name", "")
    desc = fm.get("description", "")
    body = parts[2]

    # Extract body summary (strip code blocks, take first 800 chars)
    lines = []
    in_code = False
    for line in body.split("\n"):
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        clean = line.strip().lstrip("#").strip()
        if clean:
            lines.append(clean)
    summary = " ".join(lines[:20])[:800]

    if llm_fn:
        prompt = DIMENSION_PROMPT.format(name=name, description=desc, body_summary=summary)
        try:
            raw = llm_fn(prompt)
            result = yaml.safe_load(raw) or {}
        except Exception:
            result = {}
    else:
        # Rule-based fallback
        result = _rule_based_annotation(name, desc)

    return {
        "where": result.get("where", "(unspecified)"),
        "when": result.get("when", "(unspecified)"),
        "when_not": result.get("when_not", "(unspecified)"),
        "tree": result.get("tree", "(unspecified)"),
    }


def _rule_based_annotation(name: str, desc: str) -> dict:
    """Fallback rule-based annotation when no LLM available."""
    combined = f"{name} {desc}".lower()

    # Tree detection
    tree = "general"
    if any(w in combined for w in ["ssh", "nas", "docker", "容器", "部署"]):
        tree = "devops > infrastructure"
    elif any(w in combined for w in ["github", "git", "pr", "仓库"]):
        tree = "devops > github"
    elif any(w in combined for w in ["feishu", "飞书", "lark"]):
        tree = "platform > feishu"
    elif any(w in combined for w in ["search", "搜索", "arxiv", "论文"]):
        tree = "research > search"
    elif any(w in combined for w in ["browser", "浏览器", "playwright", "selenium"]):
        tree = "automation > browser"
    elif any(w in combined for w in ["fine", "微调", "训练", "llm"]):
        tree = "mlops > training"
    elif any(w in combined for w in ["code", "代码", "debug", "调试"]):
        tree = "devops > code"
    elif any(w in combined for w in ["design", "设计", "ui", "界面"]):
        tree = "creative > design"
    elif any(w in combined for w in ["mcp", "工具", "协议"]):
        tree = "infrastructure > mcp"

    return {
        "where": f"Applied in {desc[:60]}",
        "when": f"When user requests: {desc[:80]}",
        "when_not": "When simpler alternatives exist or user explicitly excludes this domain",
        "tree": tree,
    }


def inject_annotations(skill_path: str, annotations: dict) -> bool:
    """Write 4-dimension annotations into SKILL.md frontmatter.

    Returns True on success.
    """
    with open(skill_path) as f:
        content = f.read()

    if not content.startswith("---"):
        return False

    parts = content.split("---", 2)
    if len(parts) < 3:
        return False

    fm = yaml.safe_load(parts[1]) or {}
    fm["where"] = annotations["where"]
    fm["when"] = annotations["when"]
    fm["when_not"] = annotations["when_not"]
    fm["tree"] = annotations["tree"]

    new_fm = yaml.dump(fm, allow_unicode=True, default_flow_style=False, sort_keys=False).strip()
    new_content = f"---\n{new_fm}\n---{parts[2]}"

    with open(skill_path, "w") as f:
        f.write(new_content)
    return True


def load_skill_metadata(skill_dir: str) -> list[dict]:
    """Scan a skill directory and return all skills with dimension metadata."""
    skills = []
    for root, dirs, files in os.walk(skill_dir):
        if "SKILL.md" in files:
            path = os.path.join(root, "SKILL.md")
            try:
                with open(path) as f:
                    content = f.read()
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        fm = yaml.safe_load(parts[1]) or {}
                        name = fm.get("name", "")
                        if name:
                            skills.append({
                                "name": name,
                                "description": fm.get("description", ""),
                                "where": fm.get("where", "(unspecified)"),
                                "when": fm.get("when", "(unspecified)"),
                                "when_not": fm.get("when_not", "(unspecified)"),
                                "tree": fm.get("tree", "(unspecified)"),
                                "tier": fm.get("tier", 2),
                                "path": path,
                            })
            except Exception:
                pass
    return skills
