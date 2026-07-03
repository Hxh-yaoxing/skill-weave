---
name: skill-weave
slug: skill-weave
displayName: Skill Weave 技能牌组编织器
emoji: 🃏
description: "Skill Weave 技能路由与自进化平台 — 12链72牌，链识别100%准确率，验证协议门+并行度检测。v1.8.0，111测试，PyPI可用，零新依赖。"
version: 1.8.0
category: ai-agent
labels: [agent, routing, orchestration, skill-management, multi-agent, self-evolving]
dependencies: [skill-weave (PyPI)]
metadata:
  hermes:
    tags: [skill, weave, routing, orchestration, chain, 牌组, 编织, 元技能]
related_skills: [skill-routing, agent-cluster-orchestration, work-mode, subagent-driven-development]
where: "技能编排、链式调用、多技能组合路由、元技能操作手册 — 当需要把多个技能串成工作流或创建索引式入口时"
when: "skill weave, 牌组, 编织, 顺子, 飞机, 王炸, 箭矢, 打牌, 技能链, chain skills, orchestrate skills, 推演, 注册新链, 元技能, 操作手册, meta skill"
when_not: "单技能调用直接用 skill_view；子Agent派发用 delegate_task；集群协调用 agent-cluster-orchestration"
tree: workflow > skill-weave
tier: 1
updated: 2026-07-03
changelog: |
  v1.8.0: R12 质量层 — 验证协议门 + 资产传递规范 + 并行度检测 + 失败归因四分类 (2026-07-03 深蓝，借鉴万有DAG观察)。新增 verify_chain_output(CHAIN_OUTPUT_SCHEMAS) / detect_parallelism / feedback status 四态。3个新函数 0 新依赖。基准回归 22/23=95.65%，无回归。
  v1.5.0: 仪式交接协议落地 — task_graph.py(DAG真相源)+work_card_worker.py(执行引擎)+auto_archive.py(自动归档+清理)。45测试全过。任务图支持跨项目依赖。Worker cron驱动各profile轮流执行。归档自动打包→思源索引→清理临时文件。接口统一(owner字段)。完整设计见 references/ritual-handoff-protocol.md。
  v1.4.1: 卡片制+跨Profile共享入库。新增 card.py(27测试) + 共享目录 /opt/data/shared/cards/ + inject_card_context.py。LoopCard 替代全量上下文（认知负荷-98%）。子Agent spawn 自动注入最近3张卡片摘要。架构自进化草案 references/architecture-self-evolution-v05.md。
  v1.4.0: skill-weave v0.4.0 核心落地 — 6项P0编码完成，84个测试。新增 circuit_breaker.py（熔断器+Darwin棘轮/SkillOpt Rejected Buffer）+ telemetry.py（JSONL结构化日志+span追踪+自动轮转）+ embedding.py（LRU嵌入缓存+双模后端Ollama/Dify+自动故障转移）+ spine.py（循环状态脊柱，权重连续性444×提升）+ verifier.py（Maker-Checker验证层，虚假成功3/3识破）。改造 learner.py（滑动窗口失效检测+冷启动预热）+ router.py（嵌入缓存集成）。零新依赖，全向后兼容。基准无回归（17/23）。架构摘要见 references/v0.4-architecture.md。新增拆·织·验执行流 + Loop Engineering调研参考。
  v1.3.1: 基准测试文档补全 — 增加脚本完整路径、变更检测工作流（last_benchmark.txt/becnhmark_history.jsonl）、文件位置表格、cron 工作流步骤说明。
  v1.3.0: 修复链表格 staleness（R10 后未同步）。新增基准测试脚本 benchmark_chain_routing.py。新增 references/chain-routing-edge-cases.md（6 种误判模式文档化）。
  v1.2.0: 三子Agent并行审计工作流入库。链从5→9，牌从39→49。新增链验证规则（顺序/重叠/兼容性/伪链检测）。
  v1.1.0: 第五链「搜索→清洗（箭矢）」新增 — exa-web-search → crawl4ai → smart-web-fetch，39张牌
  v1.0.0: 初始版本 — 四条核心链定义、链识别+标签过滤路由、反馈学习闭环、36张牌注册
---

# Skill Weave — 技能牌组编织器

将技能牌编织成链。比喻：每张技能是一张牌，链是手牌组合（顺子/飞机/王炸）。

## 哲学

- **测试是为了修，不是为了攒**。每轮推演发现 P0 立即修，修完重测验证。
- **挑核心王牌，散牌自然搁置**。高频技能重点维护，低频技能不浪费精力。
- **子Agent不落地**。注册子Agent只出补丁，由父Agent审核链序（E2E结论优先于注册设计）后再落地。

## 十二条核心链（R12 审计后）

| 链名 | 牌型 | 步骤 | 并行 | 触发词 |
|------|------|------|:--:|--------|
| 研究→写作 | 顺子 | deep-research-pro → copy-editor | → | 研究/调研/深度分析/写报告/论文/评测/翻译 |
| 需求→代码 | 飞机 | plan → writing-plans → subagent-driven-development | → | 实现/开发/写代码/构建/功能/工具/系统 |
| 记忆→研究 | 对子 | memory-maintenance → deep-research-pro | ⚡ | 上次/之前/继续/跟进/记得/回忆 |
| 搜索→清洗 | 箭矢 | exa-web-search-free → crawl4ai-skill → smart-web-fetch | → | 搜索/查找/爬取/抓取/查资料/检索 |
| 法槌 | 顺子 | legal-contract-gen → legal-risk-analyzer → legal-document-review | → | 法律/合同/NDA/协议/隐私政策/代理词 |
| 创作发布 | 顺子 | fiction-writing → copy-editor → humanizer-zh | → | 创作/写作/小说/润色/去AI味/故事/文案 |
| 代码审查 | 对子 | codebase-inspection → requesting-code-review | ⚡ | 审查代码/代码审查/安全扫描/审计代码 |
| 技能治理 | 对子 | skill-routing → skill-vetter | ⚡ | 技能审查/技能安全/检查技能/审计技能 |
| Git工程 | 对子 | github-pr-workflow → github-code-review | ⚡ | PR/提交/code-review/commit/push/分支 |
| 微信全链路 🆕 | 顺子 | wewrite-wechat-publishing → wechat-article-writer → wechat-ai-detection | ⚡ | 公众号/微信文章/自媒体/推文/热点/选题/爆款 |
| 代码突破 🆕 | 顺子 | agent-failure-loop → self-evolving-agent → systematic-debugging | ⚡ | 自愈/自进化/持续改进/故障自动修复 |
| 思考→决策 🆕 | 顺子 | deepthink → thinking-munger → complex-task-methodology | ⚡ | 思考/决策/战略/选型/架构/权衡/判断 |

> ⚡=对子链(2独立步骤可并行) | →=顺子/飞机/箭矢(严格串行)。并行由 `detect_parallelism()` 自动检测。
> R12 变更 (2026-07-03)：新增验证门/资产规范/并行检测/失败归因。基准 22/23=95.65%。

> ⚠️ **搜索后端陷阱（2026-06-08）**：`web_search` 工具默认走 Firecrawl 后端（DDG 被 GFW 阻断 → 静默返回空）。触发箭矢链搜索步骤时，**必须**优先使用 MCP 工具（Bright Data `search_engine`/`discover`）或 Bocha `bocha_search.py`，不得直接调用 `web_search`。详见 multi-search-engine 降级链。

### 能力索引（非串行链）

| 索引名 | 技能 | 说明 |
|------|------|------|
| 飞书能力栈 | feishu-lark-mcp \| group-chat-protocol-v2 \| feishu-voice | 飞书三独立能力，按需组合，非串行管道 |

## 基准测试

运行链识别基准测试（23 个标准查询，测试 `identify_chain()` 准确率）。

**脚本位置**：`/opt/data/skills/workflow/skill-weave/scripts/benchmark_chain_routing.py`

```bash
cd /opt/data && PYTHONPATH="/opt/data/.local:$PYTHONPATH" python3 /opt/data/skills/workflow/skill-weave/scripts/benchmark_chain_routing.py
```

> ⚠️ **不要用 `pytest tests/`**：`/opt/data/skill-weave/` 下没有 `tests/` 目录，pytest 在该 venv 也无法安装（权限不足）。链识别准确率才是核心指标。详见 [`references/cron-setup.md`](references/cron-setup.md)。

### 变更检测与日志

> 📋 完整 cron 配置和文件格式说明见 [`references/cron-setup.md`](references/cron-setup.md)

文件位置（均在 `/opt/data/skill-weave/` 下，独立于 git repo）：

| 文件 | 用途 | 更新方式 |
|------|------|----------|
| `last_benchmark.txt` | 上一次运行的结果快照，用于 diff 判断是否有变化 | **手动写入**（脚本只输出到 stdout，不自动写此文件） |
| `benchmark_history.jsonl` | 全量历史日志，每行一条 JSON 记录 | 追加写入（含 `timestamp` 和 `regression_from_previous` 字段） |

**典型 cron 工作流**：
1. 运行脚本，收集 stdout
2. 与 `last_benchmark.txt` 比对准确率/失败列表
3. 若有变化 → 报告差异；若无变化 → SILENT
4. 追加新记录到 `benchmark_history.jsonl`
5. 用本次结果覆盖 `last_benchmark.txt`

> ⚠️ 脚本输出 JSON 格式（`accuracy/total/correct/skills_loaded/chain_count/failures`），`last_benchmark.txt` 需自行转换。两文件格式不一致：benchmark_history.jsonl 额外包含 `timestamp` 和 `regression_from_previous`。

已知边缘案例和误判模式见 `references/chain-routing-edge-cases.md`。

## 拆·织·验 执行流（实现类任务的标准工作流）

当 v0.4 头脑风暴完成、设计已收敛时，用此流程替代「议」：

| 阶段 | 谁做 | 做什么 | 耗时 |
|------|------|--------|:--:|
| **拆** Decompose | 父Agent | 读源码 → 分析依赖 → 拆成 2-3 个并行任务 + 写接口契约 | ~5min |
| **织** Weave | 子Agent并行 | 每个任务独立编码 + TDD，互不阻塞。每任务含 context(完整源码+接口契约+约束) | ~3min |
| **验** Verify | 父Agent | 集成测试 → 基准回归 → 版本号 → 文档更新 → 笔记 | ~2min |

### 接口契约模板

每个子Agent任务必须包含：
- 任务目标（一句话）
- 现有代码的完整上下文（读入 context，不让子Agent自己读）
- 外源可借鉴的设计（Darwin/SkillOpt/SKILLWEAVER）
- 约束（零新依赖、向后兼容、不改哪些文件）
- 验证命令（具体的 pytest 命令）

### 适用条件

- 使用「拆·织·验」: 昨天已充分讨论，今天编码执行（设计收敛 → 实现）
- 使用「议」: 方向未定，需要多模型发散讨论（探索 → 收敛）
- 使用「新链推演」: 需要注册新技能链（验证 → 注册）

### 与 Loop Engineering 的对应

拆·织·验 是 Anthropic Loop Engineering 六部分架构的一个实例。详见 `references/loop-engineering-research-2026-06-27.md`。

---

## v0.4.0 模块架构

v0.4.0 新增了韧性层、状态层、验证层和卡片系统。完整架构见 `references/v0.4-architecture.md`。

### 卡片制注意力 (card.py)

**核心理念**：每轮循环结束时写一张 LoopCard（~200字节），下一轮只读卡片不读全量 MEMORY.md（~13KB）。认知负荷降低 ~98%。

| 类 | 用途 |
|---|------|
| `LoopCard` | 单轮循环摘要（task/skill/result/warnings/next_hint/weight_delta） |
| `ArchitectureCard` | 架构变更卡片（gene_before/gene_after/pilot_result） |
| `CardChain` | 卡片链管理。`last()`/`last_n()`/`context_for_delegate()` 注入子Agent |

```python
from skill_weave.card import LoopCard, CardChain

chain = CardChain('/opt/data/shared/cards/default/loop_cards.jsonl')
chain.append(LoopCard(task="搜索AI论文", selected_skill="deep-research-pro",
                      result="PASS", next_hint="下次优先查缓存"))

# 子Agent 注入 — 不读全量上下文，只读最近3张卡片
context += chain.context_for_delegate()
```

### 跨 Profile 共享

架构基因和卡片链放在 `/opt/data/shared/cards/`，所有 profile 可读写：

- `architecture_gene.json` — 当前架构基因（全 profile 对齐）
- `cross_profile_board.json` — 公共决策板
- `{profile}/loop_cards.jsonl` — 各 profile 卡片链
- `scripts/inject_card_context.py` — 读取卡片链生成子Agent context

子Agent spawn 时不瞎猜——卡片告诉它"做到哪了"，基因告诉它"用什么架构做"。

---

## 大规模链发现工作流（v1.7 新增）

技能库从 181→269 增长后，手动逐链推演不适用。

### 三路并行探索模式（2026-07-03 验证）

```python
delegate_task([
    {"goal": "扫描全部技能，发现新的可编织工作流链", ...},  # 链探索者
    {"goal": "筛选单点高质量技能，评估是否应加入现有链", ...}, # 质量探员
    {"goal": "审查现有架构，提出优化方案", ...},            # 编织优化师
])
# 三路并行，orchestrator级（可自行spawn子Agent探究细节）
# 结果汇总→父Agent终审→注册新链新牌
```

### 探索→编织→注册 闭环
1. 三路结果汇总
2. 父Agent裁决：确认新链 → 验证链序 → 设计触发词
3. 更新 `weave_chains.py`（CHAINS + CHAIN_TAGS + SYNONYMS）
4. 运行 `benchmark_chain_routing.py` 验证无回归
5. 更新链表格 + Stats

## 元技能编排模式（v1.7 新增）

链提供串行工作流，但 12 链 72 牌规模下，用户常面临"我该用哪个技能？"的导航问题。元技能是 **操作手册式的索引入口**——从导航直达子技能，不加载全量。

### 元技能 vs 链

| | 链 (Chain) | 元技能 (Meta-Skill) |
|---|---|---|
| 用途 | 串行工作流（A→B→C） | 索引导航（选A或B或C之一） |
| 触发 | 任务触发词 | 领域场景词 |
| 结构 | 步骤顺序 | 功能域分组 |
| 加载 | 识别链→加载全链技能 | 看导航→选对应子技能 |
| tier | 1（正常技能） | 0（仅路由，不执行） |

### 元技能模板

```yaml
name: <domain>-manual
tier: 0                      # 元技能最高层，只路由不执行
description: "操作手册入口——索引导航到 N 个子技能"
when: "<中文触发词集合>"
when_not: "单一子技能已覆盖的场景——直接加载对应子技能"
related_skills: [子技能1, 子技能2, ...]
```

主体结构：
1. **快速导航表** — 功能域分组 + 子技能一句话定位 + skill_view() 跳转
2. **场景速查** — "遇到X问题→加载Y技能"
3. **架构全景图** — 层次/阶段可视化  
4. **决策树** — "我该用哪个？"
5. **加载路径** — 每个子技能的具体调用方法

### 已创建元技能（13 个，2026-07-03 批量生成）

| 元技能 | 覆盖域 | 子技能数 | 链 |
|--------|--------|:--:|------|
| memory-manual | 记忆系统 | 16 | 记忆→研究 |
| knowledge-lifecycle | 知识生命周期 | 11 | 跨链（采集→归档） |
| research-writing-workbench | 研究写作 | 14 | 研究→写作 |
| requirements-to-code-manual | 需求→代码 | 12 | 需求→代码 |
| search-pipeline-manual | 搜索管线 | 10 | 搜索→清洗 |
| legal-manual | 法槌 | 11 | 法槌 |
| creative-manual | 创作工坊 | 9 | 创作发布 |
| code-review-manual | 代码审查 | 9 | 代码审查 |
| skill-governance-manual | 技能治理 | 10 | 技能治理 |
| git-engineering-manual | Git工程 | 9 | Git工程 |
| wechat-publishing-manual | 微信全链路 | 8 | 微信全链路 |
| code-breakthrough-manual | 代码突破 | 8 | 代码突破 |
| thinking-decision-manual | 思考→决策 | 8 | 思考→决策 |

> 13 元技能覆盖全部 12 链 + 知识生命周期。总 196KB。4 批子Agent并行生成，每批 ~70 秒。Hermes 自动发现注册。

### 并行生成模式

元技能可用子Agent并行批量生成：

```
派 3 个 orchestrator 子Agent，各领 1 条链
→ 各自加载相关子技能 SKILL.md
→ 按模板生成元技能 SKILL.md
→ 写入磁盘 → Hermes 自动发现
```

3 条元技能约 60-70 秒并行完成。12 链可 4 批覆盖。

## 新链推演工作流（三子Agent并行审计）

每轮推演使用 3 个子 Agent 并行，最后父 Agent 审核修正落地：

### 子Agent分工

| 子Agent | 职责 | 输入 | 输出 |
|----------|------|------|------|
| **校检** (leaf) | 逐牌读 SKILL.md，检查四维标注、元数据、陷阱文档 | 技能路径列表 | 🟢/🟡/🔴 状态 + 修复清单 |
| **实测** (leaf) | 端到端模拟链执行，检查每步产出能否喂入下一步 | 链定义 + 技能路径 | 链可行性 + 顺序问题 + 重叠分析 |
| **注册** (leaf) | 读 weave_chains.py + advanced.py，出补丁 **不落地** | 链定义 | 精确补丁（CHAINS/SKILLS/SYNONYMS） |

### 父Agent审核清单

从 E2E 实测子Agent的报告中提取关键发现，逐项核对后再落地：

1. **链序是否正确**：实测子Agent可能发现注册子Agent设计的顺序不对。典型案例：
   - 创作链：注册子Agent 设计 `copy-editor → fiction-writing`，实测发现应该 **先写后编** → 修正为 `fiction-writing → copy-editor → humanizer-zh`
   - Git链：注册子Agent 设计 `PR → commit`，实测发现 commit message 在开 PR 之前生成 → 修正为 `smart-commit-gen → github-pr-workflow → github-code-review`
   - **规则**：E2E 结论 > 注册设计。父Agent 必须读实测报告，不能直接信任注册补丁。

2. **技能兼容性**：链中每个技能对前置步骤的输出是否兼容：
   - copy-editor 7轮框架有 5/7 轮对法律文书无意义 → 应从法槌链移除
   - copy-editor 第四轮「证据」对创作文本应跳过 → 链描述标注

3. **功能重叠**：相邻步骤是否做同样的事：
   - legal-risk-analyzer 和 legal-document-review 都有法条核实 → 确认分工不同（一个出报告、一个改文档）则保留
   - smart-commit-gen 和 github-pr-workflow 都有 Conventional Commits → 链描述标注冗余

4. **伪链检测**：三个技能是否真的形成串行数据流，还是只是并列能力拼在一起：
   - 飞书链是**能力栈**非串行管道 → 注册但标注 ⚠️，链描述写明

### 落地步骤

1. 先修技能（校检子Agent发现的问题）→ patch SKILL.md
2. 再修链序（根据实测子Agent结论）→ patch CHAINS
3. 最后注册（应用修正后的注册补丁）→ 更新 weave_chains.py + SYNONYMS
4. Stats更新 → memory() + MEMORY.md stats行 + Hindsight快照

### 常见问题速查

| 问题 | 现象 | 修复 |
|------|------|------|
| frontmatter 标签在 `---` 外 | YAML解析器读不到 tags/related_skills | 移到 `---` 内 |
| 缺 version/tier | 新入库技能未填 | 补 `version: 1.0.0`, `tier: 1` |
| related_skills 指向无关技能 | 从其他技能复制 frontmatter 时遗留 | 改为实际关联的技能 |
| 注册子Agent抢先落地 | 补丁中包含 copy-editor 等已被实测否定的牌 | **规则：注册子Agent不落地，只出补丁** |

## 链验证规则

E2E 实测必须检查以下维度：

1. **顺序**：步骤 N 的产出能否作为步骤 N+1 的输入？实际工作流中哪步先发生？
2. **重叠**：相邻步骤是否有 30%+ 功能重叠？重叠是否互补（诊断 vs 治疗）还是冗余？
3. **兼容性**：中间步骤是否会改变前一步产出的关键信息（如 copy-editor 改法律术语 → risk-analyzer 误判）？
4. **真实性**：是真正的数据管道，还是三个独立能力硬拼成串？
5. **when_not 冲突**：链路中某个技能的 when_not 是否明确排除了前/后步骤的适用场景？

## 使用方式

```bash
# 路由任务到链
python3 /opt/data/scripts/weave_chains.py route "研究新能源汽车政策"

# 查看牌组
python3 /opt/data/scripts/weave_chains.py list
python3 /opt/data/scripts/weave_chains.py chains

# 反馈学习
python3 /opt/data/scripts/weave_chains.py feedback deep-research-pro success 3.0
```

## 仪式交接协议 (task_graph + worker + archive)

任务图是真相之源。Worker 是执行引擎。归档是自动清理。

### 核心组件

| 文件 | 测试 | 用途 |
|------|:--:|------|
| `/opt/data/shared/cards/task_graph.yaml` | — | DAG 定义——任务/依赖/owner/验证条件 |
| `/opt/data/scripts/task_graph.py` | 13 | 加载 YAML，解析依赖，返回可执行节点 |
| `/opt/data/scripts/work_card_worker.py` | 20 | Worker 执行引擎——sync→execute→verify |
| `/opt/data/scripts/auto_archive.py` | 12 | 自动归档——打包→清单→清理临时文件 |

### task_graph.yaml 格式

```yaml
projects:
  project-name:
    status: in_progress
    scene: A
    priority: P0
    subtasks:
      - id: task-1
        title: 任务标题
        owner: router
        deps: []
        checks: ["验证条件1", "验证条件2"]
```

### 执行流程

```
task_graph.yaml（蓝图）
  → worker cron 轮询（每个 profile 每分钟）
  → 找自己的 executable 节点 → running → verifying → done
  → auto_archive 自动触发（打包 + 清理）
```

### 依赖语义

- `[]` — 无依赖，立即可执行
- `task-id` — 同项目内依赖
- `project-id.task-id` — 跨项目依赖

### 接口契约（关键教训）

**给子Agent写 dataclass field names，不是自然语言描述。** 三个模块由不同子Agent并行编码，接口断裂的三个来源：
1. 字段名不一致（`assigned_to` vs `owner`）
2. 重复定义（两个文件各写一份 WorkCard）
3. 必需字段过多（archive 不关心的字段导致测试炸）

**统一规范**：唯一定义在 `work_card_worker.py`；其他模块 `from work_card_worker import WorkCard`；接口契约用 dataclass 定义。

### 跨 Profile 部署

```bash
python3 scripts/work_card_worker.py --profile router --once
python3 scripts/work_card_worker.py --profile challenger --once
python3 scripts/work_card_worker.py --profile default --once
```

设计文档：`references/ritual-handoff-protocol.md`。

## 路由原理

三步闭环：

1. **链识别 v2** → 加权触发词匹配(1-3分)+链优先级+bigram模糊回退（规则层，零 token）
2. **标签过滤** → 缩小候选集到链相关技能
3. **Thompson 采样** → 质量/新鲜度/成本/语义 四维评分

反馈学习：记录每次调用的成功/失败和成本，Thompson 采样根据历史表现调整路由权重。

**冷启动教训**：新注册技能初始评分相同，必须灌入初始反馈数据（基于推演验证的已知表现），路由才能分出高低。

## 当前牌组

72 张已验证技能牌：

| 花色 | 数量 | 王牌 |
|------|:----:|------|
| ♠️ 研究 | 5 | deep-research-pro |
| ♥️ 写作 | 5 | copy-editor, humanizer-zh |
| ♦️ 代码 | 6 | plan, subagent-driven-development |
| ♣️ 记忆 | 4 | memory-maintenance |
| 🃏 治理 | 7 | skill-routing, requesting-code-review |
| 🎴 运维 | 4 | ssh-tunneling, service-audit |
| 🀄 MLOps | 4 | axolotl v2.0, unsloth v2.0 |
| 🎯 内容 | 3 | content-digest-pipeline |
| 🌐 搜索管线 | 3 | exa-web-search-free, crawl4ai-skill, smart-web-fetch |
| ⚖️ 法律 🆕 | 3 | legal-contract-gen, legal-risk-analyzer, legal-document-review |
| ✍️ 创作 🆕 | 1 | fiction-writing |
| 💬 飞书 🆕 | 3 | feishu-lark-mcp, group-chat-protocol-v2, feishu-voice |
| 🔀 Git 🆕 | 2 | github-pr-workflow, smart-commit-gen |

## 添加新链

1. 校检子Agent → 验证所有技能 SKILL.md 完整性
2. 实测子Agent → 端到端检查链序/重叠/兼容性
3. 注册子Agent → 出补丁（不落地）
4. 父Agent 审核 → 修正链序和元数据
5. 落地 → 更新 `weave_chains.py`（CHAINS, SKILLS, CHAIN_TAGS） + `advanced.py`（SYNONYMS）
6. Stats → 更新 MEMORY.md stats 行 + Hindsight 快照

## 链识别 v2（2026-06-29 升级）

`identify_chain()` 从精确子串匹配升级为三层机制，准确率 73.91% → **100% (23/23)**：

### 三层评分机制

1. **加权触发词** — 核心触发词 3 分（如"智能提交"），通用词 1 分（如"信息"），消除歧义词劫持路由
2. **链优先级** — 平分时按优先级打破平局（技能治理 > 法槌 > 代码审查 > 搜索 > Git工程 > 研究 > 创作 > 需求 > 记忆），替代 dict insertion order 随机性
3. **Bigram 模糊兜底** — 无精确匹配时用中文 bigram 重叠评分，阈值 ≥2 命中

### 触发词扩展

每条链从 3-11 → 8-15 词，新增中文口语变体：
- 搜索链：`搜一下` `爬` `检索` `找资料`
- 研究链：`评测` `翻译` `数据科学` `深度学习` `写文章`
- 技能治理：`审查技能` `审查外部技能`
- Git链：`智能提交` `提交信息` `commit信息`

### 代码位置

`/opt/data/scripts/weave_chains.py` — `identify_chain()`、`_tokenize_bigrams()`、`TRIGGER_WEIGHTS`、`CHAIN_PRIORITY`

### 三误判根因及修复

| 误判模式 | 根因 | 修复 |
|----------|------|------|
| 「信息」「提交」劫持路由 | 歧义词平等计分 | 权重分级 + 优先级 |
| 「审查技能」字序不匹配 | 子串匹配对中文词序敏感 | 扩展触发词 + 优先级 |
| 「分析数据」全部 NONE | 触发词覆盖不足 | Bigram 模糊兜底 |

## 架构审计发现 (2026-07-03)

> 详细分析见 `references/architecture-audit-2026-07-03.md`。

| 问题 | 严重度 | 现状 | 修复方向 |
|------|:------:|------|----------|
| v0.4 韧性模块未接入主路由流 | P0 | weave_chains.py 只导入 SkillRouter，circuit_breaker/telemetry/verifier 完全未使用 | 在 init_router() 创建 CircuitBreaker，在 route_task() 中过滤熔断技能 |
| 技能注册覆盖率 19% | P1 | 254 个技能只注册 49 个（devops 46个/ workflow 44个几乎全遗漏） | 批量从 SKILL.md frontmatter 提取注册，设计 MLOps/内容/记忆加固链 |
| Validation Gate 未实现 | P1 | 修改链定义无回归检测门（SkillOpt 的方法论已识别未落地） | 黄金测试集 + validate_chains() 集成到 CLI |
| Benchmark cron 持续失败 | P2 | benchmark_history.jsonl 最近 5 条全是 test_suite_missing | cron 改为直接运行 benchmark_chain_routing.py 不走 pytest |
| CJK 盲区未修复 | P2 | _tokenize_bigrams 对中文长串覆盖率不足（jieba 已安装未启用） | 在 identify_chain() 的 bigram 回退中启用 jieba.lcut() |

### P0: v0.4 "幽灵架构"

v0.4 编码了 6 个新模块（circuit_breaker/telemetry/embedding/spine/verifier/card，共 2928 行，111 测试），但 **weave_chains.py 只导入了 `SkillRouter`，未使用任何 v0.4 模块**。韧性层和验证层完全未接入主路由流。

```
验证命令：
grep -r "circuit_breaker\|telemetry\|verifier\|embedding\|spine\|card" /opt/data/scripts/weave_chains.py
# 预期输出：空（即未接入）
```

### P1: 注册鸿沟（待解决）

磁盘有 254 个技能，牌组只注册了 72 个。缺失的高价值独立技能：fic-pipeline、a2a-agent-mail、computer-use、self-improving、deepblue-rss-gating 等。缺失的链：MLOps 链、内容管线链、记忆加固链。

## R12 质量层（2026-07-03 新增，借鉴万有DAG）

万有DAG的三个关键启发在 R12 落地为3个新函数，零新依赖。

### 验证协议门 `verify_chain_output()`

每步执行后强制5项检查（从万有的 Step 4 协议借鉴）：

| 检查项 | 说明 |
|--------|------|
| upload_confirmed | 产出是否存在/可访问 |
| content_complete | 必需字段是否齐全（对照 CHAIN_OUTPUT_SCHEMAS） |
| format_valid | 格式是否匹配预期（markdown/json/docx） |
| context_passed | 前序产出是否被正确消费 |
| consumable | 下游步骤能否直接使用 |

返回 `{status: PASS|WARN|FAIL, checks: {...}, issues: [...]}`。

```python
result = verify_chain_output('research-to-writing', 'deep-research-pro',
    {'has_output': True, 'fields': ['title','sources','findings','citations'],
     'format': 'markdown', 'context_consumed': True, 'consumable': True})
# → {status: 'PASS', passed: 5, total: 5}
```

### 资产传递规范 `CHAIN_OUTPUT_SCHEMAS`

定义每链每步的标准输出格式，确保步骤间数据可消费。5条主链已定义：

```python
CHAIN_OUTPUT_SCHEMAS = {
    "research-to-writing": {
        "deep-research-pro": {
            "format": "markdown",
            "required": ["title", "sources", "findings", "citations"],
            "pass_to_next": "findings + sources → copy-editor 的事实基础",
        },
        ...
    },
    "search-to-fetch": {...},
    "legal-document-chain": {...},
    ...
}
```

### 并行度检测 `detect_parallelism()`

分析链步骤间的数据依赖，自动识别可并行组：

```
代码审查: [codebase-inspection, requesting-code-review] → ⚡1组可并行
记忆→研究: [memory-maintenance, deep-research-pro] → ⚡1组
研究→写作: [deep-research-pro][copy-editor] → 2组串行
```

对子链（2独立步骤）自动标记可并行 → 父Agent可派2个子Agent同时执行。

### 失败归因四分类 `feedback()`

从二元成功/失败升级为四态（借鉴万有 SUCCESS/PARTIAL/FAILED/ERROR）：

```bash
python3 weave_chains.py feedback deep-research-pro SUCCESS 3.0  # ✅
python3 weave_chains.py feedback deep-research-pro PARTIAL 2.0  # ⚠️
python3 weave_chains.py feedback deep-research-pro FAILED  1.0  # ❌
python3 weave_chains.py feedback deep-research-pro ERROR   0.5  # 💥
## 技能采购管道（SkillHub）

SkillHub (skillhub.cn) 可作为补充技能采购渠道。已部署：

```bash
# CLI 已安装
skillhub search <关键词>
skillhub install <slug> --dir /opt/data/skills

# 采购→审查→入库 流程
find-skill-skillhub（搜索推荐） → skill-vetter（安全审查） → 注册入牌组
```

skill-weave 已发布至 SkillHub（#94647, `@user_03812eb9`），详情见 `references/skillhub-publishing.md`。

## 已知限制

- 语义匹配基于关键字重叠，非 embedding 相似度
- 新注册技能需手动灌反馈或等待自然积累
- 只做路由推荐，不自动执行链
- CJK Tokenization Bug（TreeFilter `_expand_query`）：bigram 展开已修复（n=2），jieba 已安装暂未启用
- 飞书协作链是能力栈非串行管道 —— 链描述已标注 ⚠️
- 基准测试：`scripts/benchmark_chain_routing.py` — 当前 22/23 = 95.65%（R12 无回归）

## 外源研究摘要 (2026-06-27)

skill-weave v0.4 规划中研究了三个外部项目/论文，提取可借鉴设计思路。

### Darwin-skill (alchaincyf, 4.3k⭐)
- **定位**: Skill 优化器（非路由器），自动评估和优化 SKILL.md
- **核心机制**: 棘轮（Ratchet，分数只升不降）+ 9维评估体系（总分100，实测占23分）+ 5阶段优化循环
- **独立评分**: 每个优化循环启动2个独立子Agent评分，下一轮换评委避免锚定效应
- **可借鉴**: 棘轮→skill-weave的熔断回滚；9维评估→skill质量维度特征；独立评分→路由验证层
- **局限**: 非路由框架，单skill优化视角，评估成本高（需spawn多子Agent）

### 微软 SkillOpt (arxiv 2605.23904)
- **定位**: 文本空间优化器——把skill文档当"可训练权重"，用训练循环迭代优化
- **核心机制**: Rollout→Minibatch Reflection→Bounded Text Update→Validation Gate→Epoch-Wise Meta Update
- **关键设计**: 文本学习率（编辑预算）控制改动幅度；双模型分离（target/optimizer）；零推理开销部署
- **可借鉴**: Validation Gate→路由更新前held-out验证；Rejected Buffer→失败路由硬约束；文本学习率→路由权重调整步长上限
- **局限**: 不做多skill路由，训练成本高（0.6-3.6M tokens/pt），依赖明确验证器

### 阿里 SKILLWEAVER (arxiv 2606.18051)
- **定位**: 组合技能路由——拆解复杂任务→检索子技能→组合成DAG
- **核心机制**: Decompose(LLM)→Retrieve(Bi-encoder+FAISS)→Compose(DAG)。创新：SAD反馈回路（用检索结果校正拆解）
- **数据**: 2209个MCP技能池；拆解精度51%→67.7%（+SAD）；Token消耗降低99%
- **与我们关系**: 互补——他们做任务拆解+技能组合，我们做多技能路由+在线学习。我们是生产级实现。
- **可借鉴**: SAD反馈→我们的FeedbackLearner可以加retrieval-informed re-ranking

详见 `references/skill-weave-brainstorm-clusters-2026-06-27.md`。Anthropic Loop Engineering 调研见 `references/loop-engineering-research-2026-06-27.md`。

### v0.4 规划结论

六大集群编织完成。P0六项（零新依赖）：熔断器+OpenTelemetry日志+~~失效检测~~✅+嵌入缓存+双模后端(Ollama+Dify@192.168.1.10:8090)+~~冷启动预热~~✅。学习层复用5个已有技能(error-learning-loop/memory-gating/skill-vetter/skill-routing/skill-weave)。

> ✅ 已实现：失效检测（滑动窗口降权）+ 冷启动预热（tag相似度继承）。详见 [`references/learner-v2-staleness-warmstart.md`](references/learner-v2-staleness-warmstart.md)。

[SkillOpt](https://arxiv.org/abs/2605.23904)（上交+微软, 2026.5）提出了将技能文档视为可训练状态的范式——独立优化器模型通过 Rollout→Reflection→Bounded Edit→Validation Gate→Meta Update 五步法自动打磨单个技能。详见 [`references/skillopt-comparison-2026-06-25.md`](references/skillopt-comparison-2026-06-25.md)。

对 Skill Weave 的三个启发：

| SkillOpt 机制 | Skill Weave 映射 | 收益 |
|---------------|-----------------|------|
| **Validation Gate** | 新链/新路由过黄金测试集 | 防"优化A链路崩B链路" |
| **Minibatch Reflection** | 失败归因：路由问题 vs 牌不行 | 不再只看二元信号 |
| **Bounded Text Updates** | 改技能描述时限制语义漂移 | L1树召回不降 |

融合方向 **OptiWeave**：Skill Weave 负责宏观编排（不变），SkillOpt 负责离线打磨单牌——解决"Weave 不知如何把烂牌变好牌"的核心缺口。

## Phase 4 集成：技能路由引擎 (2026-06-23)

Skill Weave 的链语义和触发词体系被选为 Hermes 技能路由的底层引擎，替代原计划的 JSON 倒排索引方案。核心理由：Weave 编码的不只是关键词——是工作流依赖关系（链内先后序、重叠/兼容性检测、伪链识别）。

### 扩展组件

| 组件 | 位置 | 用途 |
|------|------|------|
| `skill_router.py` | `scripts/skill_router.py` | Weave 中文关键词匹配 + DeepSeek 精排 |
| 技能注册表 | `skill_router/registry.json` | 181 技能全文索引（SKILL.md → when/desc/tree 字段） |
| 中文关键词映射 | skill_router.py 内 `CN_KEYWORD_MAP` | 24 个中文域 → 技能名（如 记忆→memory-maintenance） |

### 路由流程

```
用户消息 → Weave 关键词匹配 (零 token) → Top-10 候选
         → 置信度 < 0.7 → DeepSeek 精排 → Top-3
         → 置信度 ≥ 0.7 → 直接 Top-3
```

### 测试结果 (6/6 全命中)

记忆查询 → memory-maintenance ✅ | VM 查询 → nas-ssh-login ✅ | 代码审查 → github-code-review ✅ | 搜索 → search-routing ✅ | 写作 → copy-editor ✅ | 飞书 → feishu-lark-mcp ✅

### 设计决策：手动中文关键词优于自动 bigram

Weave 的 `identify_chain()` 基于英文触发词（SKILL.md 的 `when` 字段），但用户查询是中文。自动 bigram 提取导致"帮我""一下""系统"等通用词污染匹配。**手动 24 域 × 精选映射**在准确率上远超自动方法。映射表位于 `scripts/skill_router.py` 的 `CN_KEYWORD_MAP` 字典中，随新技能增删同步维护。
