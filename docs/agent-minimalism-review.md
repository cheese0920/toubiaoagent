# Agent Minimalism 复盘与调整

## 1. 复盘结论

现有技术标 agent 已具备分工、门禁和 subagent 编排，但仍有三类可以压缩的复杂度：

- 固定检查过多依赖“审查 agent”，容易把规则判断变成自由文本判断。
- 要求拆解、扩写、导出等阶段没有显式区分确定性校验与语义生成。
- 总控派发容易默认“多 agent 并行”，而不是先判断是否真的需要 subagent。

本轮调整采用“最小充分执行者”原则：脚本和 schema 能处理的走 L0；固定格式语义转换走 L1；需要证据和章节规划走 L2；只有章节初稿生成这类开放生成任务默认使用 L3 subagent；总控只保留 L4 编排职责。

## 2. 分级策略

| 等级 | 执行方式 | 标书 agent 中的典型任务 |
| --- | --- | --- |
| L0 | 确定性脚本、schema、清单 | JSON 校验、扩写比例检查、门禁判断、导出阻断、人工粗筛片段登记 |
| L1 | 单次有界语义转换 | 逐条要求拆解、历史片段去项目化清洗、章节扩写 |
| L2 | 带证据约束的语义规划 | 格式约束下的章节规划、章节依据包与段落计划、评分项映射、合稿衔接 |
| L3 | 有写入边界的 subagent | 章节初稿生成、复杂整改 |
| L4 | 总控编排 | 阶段推进、任务派发、门禁汇总 |

## 3. 已调整点

- 新增 `config/minimalism-router.json`，为每个阶段定义默认复杂度和升级条件。
- 将 `review` 阶段默认降为 L0，先运行 `check-requirements`、`check-scoring-map`、`check-plan`、`check-grounding-pack`、`check-paragraph-plan`、`check-chapter-draft`、`check-expansion`、`check-rejection` 和分阶段 `validate`。
- 将 `expansion` 阶段标记为 L1，扩写后必须用确定性命令检查结构、比例、禁用词、空话、无来源承诺和废标风险；最多自动整改两轮。
- 将 `requirements` 阶段标记为 L1，要求输出原子要点台账和最高得分档原子化结果，并用确定性命令检查 `*`、`⭐`、废标/否决项、评分内容对象、质量标准和全局约束。
- 评分组组合和要求—响应口径不新增独立 agent：`requirement-analyst` 用固定 schema 完成逻辑边界记录和“招标原文 → 我司响应”转换，`check-scoring-applicability`、`check-scoring-map`、`check-response-register`、`check-responses` 用 L0 脚本拦截跨标包污染、责任主体错误和范围漂移；只有原文冲突时转人工裁决。
- 保留 `chapter-planner` 为 L2 语义规划节点，但把评分内容对象与三级标题的一一映射、质量标准不得充当标题、交叉内容主响应/关联响应策略交给 `check-plan` 确定性校验。
- 新增 `content-grounder` 作为 L2 有界语义节点。它只把任务书、评分原文、项目事实和知识卡组织为固定 schema，不生成正文，也不自主分支。
- 保留 `chapter-realizer-*` 作为默认 L3，因为章节初稿生成仍是开放生成任务，需要证据、文风、评分点和章节边界共同约束；`chapter-writer-*` 仅作为兼容性别名。

## 4. 新的总控判断

总控每次派发前先问四个问题：

- 这个任务能否由 schema、脚本或清单完成？
- 是否已有明确输入、输出和验收规则？
- 是否需要语义生成，还是只需要校验？
- 失败时是否需要 autonomous recovery，还是只需阻断并返回人工确认？
- L2+ 阶段是否声明 `context_policy`，并通过 `state/workflow-state.json` 传递紧凑状态？

只有答案指向开放生成、跨章节判断或复杂整改时，才派发 subagent。

## 5. 保留 subagent 的位置

- `chapter-realizer-*`：保留。章节初稿需要结合评分项、原子要求、证据、文风和履约边界，是合理的 L3。
- `content-grounder`：保留为固定 schema 的 L2 节点。任务间可并行，但每个任务只读取授权来源和所需知识卡。
- `chapter-writer-*`：保留为兼容性别名，不作为独立流程阶段。
- `chapter-expander-*`：保留但降级为有界 L1/L3 混合任务。它不能创造新事实，必须接受 `check-expansion`。
- `integration-editor`：保留为 L2。只做去重、衔接和口径统一，不新增事实。
- `compliance-reviewer`、`rejection-reviewer`、`residue-reviewer`、`format-reviewer`：不再默认先派发，改为确定性门禁失败后的升级路径。
