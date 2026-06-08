# 总控 Agent 派发手册

## 1. 总控职责

总控 agent 负责控制阶段、构造任务书、派发 subagent、汇总结果和执行门禁。总控不应自己替代章节编写 agent 批量撰写正文，也不应替代人工确认偏差或承诺。

总控交接状态应优先使用 `state/workflow-state.json` 和 artifact refs。除非任务书明确授权，不得把完整聊天历史、整份招标文件、完整历史技术标或未清洗历史片段交给 subagent。

每次派发前必须明确：

- 当前项目和当前标包。
- 当前所处阶段及已通过门禁。
- subagent 的唯一任务和写入范围。
- 允许读取的材料与明确禁用的材料。
- 必须交付的结构化产物。
- 必须停止并上报的条件。

## 2. 推荐派发轮次

### Round 0：最小化路由判断

总控启动前先读取 `config/minimalism-router.json`，判断当前任务的最低充分执行等级。能由脚本、schema、模板或清单完成的任务，不默认派发 subagent。

总控可运行：

```powershell
python scripts/bidflow.py review-minimalism
```

当该命令提示某个 L0/L1 阶段缺少确定性检查或默认派发 agent 时，应先修正流程配置，再进入真实编制。

### Round 1：资料与要求准备

资料入库默认按 L0 执行，优先使用文件清单、来源登记、版本规则和项目白名单完成隔离。只有当资料无法按文件类型、元数据或人工清单判断项目/标包归属，或存在版本冲突需要语义判断时，才升级派发 `intake-librarian`。

涉及资料分类、历史材料复用、片段登记或项目知识沉淀时，总控先读取 `technical-bid-authoring` skill 下的 `references/knowledge-management.md`。OpenClaw 快速验证阶段只验证“人工粗筛 + 章节/段落片段登记 + 去项目化清洗 + 三态准入”的受控复用链路，不建设系统级知识库、复杂片段库或真实向量召回系统。

资料入库完成后，总控必须先形成 `inventory/source-readiness.json`，并确认招标文件、技术规范书、技术评分细则、技术投标文件格式等核心依据能够稳定解析正文、关键表格、条款和章节结构。系统不得仅根据 `.doc`、`.docx`、`.pdf` 等扩展名阻断流程；应先尝试解析或转换，再按文件用途和解析可信度处置。核心依据文件不可稳定解析时，G0 不得通过，并提示用户重新上传可解析文件或进入人工摘录模式；历史技术标、既往方案和技术支撑材料解析质量较低时，只降低引用优先级或排除出 RAG 检索范围。

```powershell
python scripts/bidflow.py check-sources inventory/source-readiness.json --report reviews/source-readiness-check.json
```

OpenClaw 快速验证阶段的历史材料复用不建设复杂片段库或真实向量索引。`intake-librarian` 或确定性预处理应对历史技术标和技术支撑材料进行人工粗筛、章节级/段落级片段登记，并输出 `inventory/rag-fragments.json`。片段进入 writer 之前必须完成去项目化和残留检测，删除或替换历史项目名称、历史客户单位、历史服务周期、历史采购编号、其他标包服务内容等风险信息。

历史片段只允许三种状态：

- `AVAILABLE`：可作为清洗后参考进入任务书。
- `NEEDS_CONFIRMATION`：必须经用户人工确认后才能进入任务书。
- `DISABLED`：不得进入 writer 上下文。

总控不得把历史片段原始内容直接放入正文生成上下文，也不得把 `DISABLED` 或未确认的 `NEEDS_CONFIRMATION` 片段分配给 writer。后续当历史材料规模扩大、复用频率提升后，再升级为独立可复用片段库。

当来源索引和项目白名单形成后，再派发 `requirement-analyst`。

`requirement-analyst` 完成后，总控必须暂停并请求人工确认当前标包、评分映射、强制要求、格式规则和排除清单。G1 未通过，不得派发章节编写。

`requirement-analyst` 不得只输出概括性清单，必须将材料中的要求逐条拆解并记录。一个记录只能表达一个可以独立判断“已响应/未响应”的条件。复合句中包含多个动作、条件、成果或证明材料要求时，应拆成多条记录，并通过 `parent_clause_id` 保留与原条款的关系。

派发提示至少包含：

```text
将招标要求、评分办法、技术规范、格式说明、表格、脚注和附件中的要点逐条拆解。
每个可独立判断是否响应的条件单独形成一条原子要点，不得把多个条件合并记录。
完整保留原文，并记录来源文件、版本、页码、章节路径、表格或附件位置。
原样记录 *、⭐、加粗、下划线、醒目色以及“废标、否决、无效投标、投标无效、不予受理”等标记。
* 和 ⭐ 的具体含义必须从招标文件说明中确认；无法确认时标记待人工确认，不得自行解释。
废标/否决项必须拆出触发条件、后果原文、适用范围，并按 BLOCKER 登记。
评分项必须继续拆成逐条得分条件、扣分条件、证明材料要求和响应位置。
如果招标文件中存在多组评分标准，必须逐组记录适用标包范围原文，并在 scoring-applicability.json 中只选中当前标包适用的一组。
每条原子要点必须明确适用标包、主响应章节、证据要求和确认状态。
```

总控应执行：

```powershell
python scripts/bidflow.py check-requirements requirements/atomic-requirements.json `
  --markers requirements/marker-register.json `
  --rejections requirements/rejection-clauses.json `
  --report reviews/requirements-check.json

python scripts/bidflow.py check-scoring-applicability requirements/scoring-applicability.json `
  --package "<当前标包名称或编号>" `
  --report reviews/scoring-applicability-check.json
```

检查结果为 `REJECT` 或 `REVIEW_REQUIRED` 时，G1 不得通过。

### Round 2：章节规划与任务生成

派发 `chapter-planner`，但它不是默认目录生成器，也不是正文编写 agent。它是技术标编制流程中的核心调度节点，位于技术评分解析之后、章节任务书生成之前。

章节规划必须由三个因素共同决定：

- 招标文件技术投标格式。
- 技术评分项结构。
- 单项评分内容体量。

`chapter-planner` 必须先严格依据招标文件中的技术投标文件格式确定一级章节结构，不得擅自改动招标文件要求的章节名称、顺序和层级。随后结合技术评分项、技术规范书和服务范围要求，在对应一级章节下进行二级或三级拆分。

当格式要求与评分项结构不一致时，系统应以投标文件格式为一级框架，以评分项作为章节内部展开依据。对于分值较高、内容范围较大的评分项，应在对应格式章节下拆分为多个可执行写作任务，避免单个 writer 上下文过大、内容泛化或评分点遗漏。

`chapter-planner` 必须输出：

- `planning/chapter-plan.json`：章节规划表。
- `planning/scoring-section-map.json`：评分项到章节的映射。
- `planning/technical-requirement-section-map.json`：技术要求到章节的映射。
- `tasks/chapter-task-*.json`：由规划表派生的写作任务书。
- 章节拆分依据和人工确认事项。

任务书之间必须：

- 输出文件互不重叠。
- 明确各自覆盖的评分项与强制要求。
- 明确各自覆盖的原子要点编号和废标/否决条款编号。
- 明确对应的招标格式章节编号、标题、层级和来源原文。
- 明确共享口径和前置依赖。
- 明确允许与禁止使用的来源。
- 明确允许使用的历史 RAG 片段编号，且只能使用 `AVAILABLE` 或已人工确认的 `NEEDS_CONFIRMATION` 片段。
- 明确待确认项不得自行补写。

G2 通过前，总控必须暂停并人工确认章节规划表，确认一级章节结构符合招标文件技术投标格式，评分项和技术规范要求均已映射到格式章节内，写作任务粒度可执行。

### Round 3：章节并行编制

每个章节任务书派发一个 `chapter-writer-*` subagent。并行数量由任务书数量决定，而不是由评分项数量决定。

派发提示至少包含：

```text
你负责且仅负责 <任务书路径>。
只读取任务书允许的来源，只写入任务书指定的章节和证据文件。
历史 RAG 片段只能读取 cleaned_content，且只能作为表达、方法和结构参考，不能替代当前项目要求和技术规范。
所有事实与结论保留来源；证据缺失时标记待人工确认。
不得编造人员、资质、业绩、时限、服务、功能或接口承诺。
不得使用 DISABLED 历史片段，不得使用未确认的 NEEDS_CONFIRMATION 片段。
发现其他项目或其他标包内容时立即停止并上报。
你不是唯一在仓库工作的 agent，不得覆盖或回退他人改动。
```

### Round 4：章节受控扩写

每个已验收章节派发一个 `chapter-expander-*` subagent。扩写角色只负责在原有结构和事实边界内将内容加厚，不承担需求补写、事实创造、承诺增强或章节重构职责。

派发提示至少包含：

```text
你负责且仅负责扩写任务书 <任务书路径>。
严格保持原文全部标题、标题层级、分段顺序和段落数量，不得删除、合并、拆分或重排段落。
完整保留原文官样文风、我司视角、核心事实、参数、约束、承诺边界及证据引用。
将全文有效字符数扩写至原文约 3 倍，允许范围为 2.7–3.5 倍；每个正文段落不得低于原段落的 2.5 倍。
扩写只能展开原文已有的实施动作、执行步骤、协作关系、控制节点和成果形成过程。
不得新增未经来源支持的事实、功能、人员、业绩、时限、服务或承诺。
各段落开头直接进入具体内容，禁止使用概括、总结或结论性引导语。
各段落结尾停留在具体动作、控制要求、交付内容或衔接事项，禁止使用总结性收束语。
保持上下文衔接流畅、逻辑严谨，禁止同义反复、空泛口号或形容词堆砌凑字数。
无法在不新增事实的前提下达到扩写比例时，立即停止并上报。
你不是唯一在仓库工作的 agent，不得覆盖或回退他人改动。
```

总控必须对每个扩写稿执行：

```powershell
python scripts/bidflow.py check-expansion <原章节.md> <扩写章节.md> --report <审查报告.json>
```

自动检查通过后，仍须人工抽查核心细节、我司视角、官样文风、上下文衔接及新增事实风险。

### Round 5：合稿

全部章节扩写并验收后，派发一个 `integration-editor`。其职责是去重、统一术语与承诺口径、修复衔接并生成追溯表，不得创造新事实。

### Round 6：确定性门禁优先审查

合稿完成后，总控先执行确定性门禁：

```powershell
python scripts/bidflow.py check-requirements requirements/atomic-requirements.json --report reviews/requirements-check.json
python scripts/bidflow.py check-expansion <原章节.md> <扩写章节.md> --report <扩写审查.json>
python scripts/bidflow.py validate <项目目录> --stage export
```

只有当确定性门禁发现问题且需要语义定位、误报判断或跨章节整改建议时，才升级派发：

- `compliance-reviewer`
- `residue-reviewer`
- `format-reviewer`

三者写入不同审查文件。总控汇总确定性检查和升级审查结果并计算门禁：

- 存在任何 `BLOCKER`：`REJECT`，立即阻断。
- 无 `BLOCKER`，但存在 `CRITICAL` 或 `MAJOR`：`REVIEW_REQUIRED`。
- 仅有 `MINOR` 或 `INFO`：`PASS_WITH_WARNINGS`。
- 无未解决问题：`PASS`。

### Round 7：整改与复审

整改应优先回派给原章节编写 agent；跨章节问题回派给 `integration-editor`。整改后只复审受影响范围，但项目、标包、承诺和技术偏差发生变化时必须重新执行全量审查。

### Round 8：Word 导出

仅当以下条件同时满足时派发 `exporter`：

- 高风险问题为零。
- 中风险问题已有人工作出决定。
- 技术偏差表与正文一致并经人工确认。
- 项目和标包身份已确认。
- 导出配置保持 `draft_only=true`。

任一条件不满足时，不得生成任何 Word，只保留内部 Markdown/JSON 审阅产物。

## 3. 动态拆分原则

不采用“一个评分项一个 subagent”的固定模式，也不采用“历史模板默认章节”的固定模式。总控应让 `chapter-planner` 按以下原则规划：

- 一级章节由招标文件技术投标格式锁定。
- 评分项只能作为格式章节内部展开和任务拆分依据。
- 同一技术方案、实施方法或质量机制下的评分项可在同一格式章节内合并。
- 需要共同证据或共享术语的评分项尽量在同一格式章节或相邻任务中处理。
- 章节之间不得同时修改同一正文文件。
- 单个任务上下文过大时，按可独立验收的二级或三级子章节再拆分。
- 每个评分项可映射多个章节，但必须指定一个主响应章节。

## 4. 总控汇总记录

总控每轮至少记录：

- 已派发任务和 subagent。
- 输入版本与输出文件。
- 已通过门禁与未通过原因。
- 人工确认事项。
- 阻断问题和责任人。
- 下一轮允许启动的任务。
