# 总控 Agent 派发手册

## 1. 总控职责

总控 agent 负责控制阶段、构造任务书、派发 subagent、汇总结果和执行门禁。总控不应自己替代章节初稿生成 agent 批量撰写正文，也不应替代人工确认偏差或承诺。

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

OpenClaw 快速验证阶段的历史材料复用不建设复杂片段库或真实向量索引。`intake-librarian` 或确定性预处理应对历史技术标和技术支撑材料进行人工粗筛、章节级/段落级片段登记，并输出 `inventory/rag-fragments.json`。片段进入章节初稿生成上下文之前必须完成去项目化和残留检测，删除或替换历史项目名称、历史客户单位、历史服务周期、历史采购编号、其他标包服务内容等风险信息。

历史片段只允许三种状态：

- `AVAILABLE`：可作为清洗后参考进入任务书。
- `NEEDS_CONFIRMATION`：必须经用户人工确认后才能进入任务书。
- `DISABLED`：不得进入章节初稿生成上下文。

总控不得把历史片段原始内容直接放入正文生成上下文，也不得把 `DISABLED` 或未确认的 `NEEDS_CONFIRMATION` 片段分配给 `chapter-realizer-*`。后续当历史材料规模扩大、复用频率提升后，再升级为独立可复用片段库。

当来源索引和项目白名单形成后，再派发 `requirement-analyst`。

`requirement-analyst` 完成后，总控必须暂停并请求人工确认当前标包、评分组组合与逻辑边界、评分映射、强制要求、要求—我司响应口径、格式规则和排除清单。G1 未通过，不得派发章节初稿生成。

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
如果招标文件中存在多组评分标准，必须逐组记录逻辑来源片段、适用范围原文、排除规则和覆盖关系；允许通用组、标包共用组、标包专项组和补遗覆盖组组合，不得强制只选一组。
每个评分项必须绑定已选中评分组的 scoring_group_id 和 source_segment_id。
每条原子要点必须明确适用标包、主响应章节、证据要求和确认状态，并生成 response_item_id。
供应商义务转写为“我司将……”，采购方义务转写为“我司理解并配合采购方……”，禁止性要求转写为“我司承诺不……”，评分期待形成具体方案响应。
每条响应口径必须登记 fixed_elements、allowed_expansion、forbidden_changes 和来源；未确认口径不得进入正文任务。
```

总控应执行：

```powershell
python scripts/bidflow.py check-requirements requirements/atomic-requirements.json `
  --markers requirements/marker-register.json `
  --rejections requirements/rejection-clauses.json `
  --report reviews/requirements-check.json

python scripts/bidflow.py check-scoring-applicability requirements/scoring-applicability.json `
  --package "<当前标包名称或编号>" `
  --scoring-map requirements/scoring-map.json `
  --report reviews/scoring-applicability-check.json

python scripts/bidflow.py check-scoring-map requirements/scoring-map.json `
  --applicability requirements/scoring-applicability.json `
  --report reviews/scoring-map-check.json

python scripts/bidflow.py check-response-register requirements/response-register.json `
  --requirements requirements/atomic-requirements.json `
  --report reviews/response-register-check.json
```

检查结果为 `REJECT` 或 `REVIEW_REQUIRED` 时，G1 不得通过。

### Round 2：章节规划与任务生成

派发 `chapter-planner`，但它不是默认目录生成器，也不是章节初稿生成 agent。它是技术标编制流程中的核心调度节点，位于技术评分解析之后、章节任务书生成之前。

章节规划必须由三个因素共同决定：

- 招标文件技术投标格式。
- 技术评分项结构。
- 单项评分内容体量。

`chapter-planner` 必须先严格依据招标文件中的技术投标文件格式确定一级章节结构，不得擅自改动招标文件要求的章节名称、顺序和层级。随后按“一级守格式、二级守评分、三级逐项对应评分原文、四级结合项目实际”的规则，在对应一级章节下形成完整章节骨架。

具体拆解口径如下：

- 一级标题严格对应招标文件技术投标文件格式。
- 二级标题原则上按当前标包适用的详细评审分项要素顺序映射。
- 先读取最高得分档原文，将其拆成评分内容对象、质量标准、全局编写约束和证明材料要求。
- 三级标题按原始顺序逐项对应评分内容对象，原则上一个 `score_atom_id` 对应一个三级主响应标题，标题忠实保留评分原文中的响应对象。
- 全面、详细、较好、合理等质量程度词写入 `writing_quality_criteria`；结合项目建设内容等表述写入 `global_constraints`；横向比较等评审方式只登记，均不得单独生成标题。
- 三级以下标题围绕对应评分内容对象，结合技术规范书、服务范围、交付物、实施场景和项目实际继续细化。
- 每个父标题下同级子标题原则上 3-4 个，最多不超过 5 个。
- “项目建设思路”“服务方案”“实施方案”“详细的初步设计技术方案”等通用章节必须先定位对应评分分项，再继续下钻 2-3 级标题，不得直接套用历史通用目录；服务类完整技术方案应覆盖服务策略、内容流程、组织资源、实施保障和成果验收闭环，不得窄化为拟建系统设计说明。
- 组织、进度、质量、风险和交付物等交叉内容必须登记 `primary_section_id`、`supporting_section_ids` 和 `response_strategy`，允许概述与专项深化，不允许机械删除或整段复制。

当格式要求与评分项结构不一致时，系统应以投标文件格式为一级框架，以评分项作为章节内部展开依据。对于分值较高、内容范围较大的评分项，应在对应格式章节下拆分为多个可执行写作任务，避免单个 `chapter-realizer-*` 上下文过大、内容泛化或评分点遗漏。

`chapter-planner` 必须输出：

- `planning/chapter-plan.json`：章节规划表。
- `planning/scoring-section-map.json`：评分项到章节的映射。
- `planning/technical-requirement-section-map.json`：技术要求到章节的映射。
- `tasks/chapter-task-*.json`：由规划表派生的写作任务书。
- 每个标题层级的来源依据、评分分项映射、评分描述拆解关键词、项目实际细化依据和人工确认事项。
- 每个最高得分档的评分内容对象、质量标准、全局约束，以及评分内容对象到三级标题的一一映射。
- 交叉内容的主响应章节、关联章节和去重策略。
- 每个已确认 `response_item_id` 的主响应章节、关联章节和任务映射。

任务书之间必须：

- 输出文件互不重叠。
- 明确各自覆盖的评分项与强制要求。
- 明确各自覆盖的原子要点编号和废标/否决条款编号。
- 明确 `allowed_scoring_group_ids` 和 `response_item_ids`，未确认响应口径不得进入任务。
- 明确对应的招标格式章节编号、标题、层级和来源原文。
- 明确经过确认的 `planned_outline`，`chapter-realizer-*` 不得自行新增、删除、重排或重命名标题。
- 明确共享口径和前置依赖。
- 明确允许与禁止使用的来源。
- 明确允许使用的历史 RAG 片段编号，且只能使用 `AVAILABLE` 或已人工确认的 `NEEDS_CONFIRMATION` 片段。
- 明确 `grounding_pack_file`、`paragraph_plan_file`、`output_file`、`evidence_file`、`draft_review_file` 和 `expansion_task_file`。
- 明确待确认项不得自行补写。

章节规划确认后先执行：

```powershell
python scripts/bidflow.py check-plan planning/chapter-plan.json `
  --requirements requirements/atomic-requirements.json `
  --scoring-map requirements/scoring-map.json `
  --response-register requirements/response-register.json `
  --report reviews/plan-check.json
```

检查通过后进入章节依据构造；此时仍未允许生成正文。

### Round 3：章节依据包与段落计划

每个章节任务派发一个有固定 schema 的 `content-grounder`。该节点只形成 `grounding/*.json` 和 `paragraph-plans/*.json`，不写正文。章节依据包必须绑定允许评分组、评分原文、`score_atom`、技术要求、当前项目事实、已确认 `canonical_response`、`fixed_elements`、`allowed_expansion`、`forbidden_changes`、来源引用、知识卡和废标/否决条款；段落计划必须为每个三级或四级主响应标题明确写作对象、项目实际、执行动作、控制节点、交付成果、响应口径和来源。

```powershell
python scripts/bidflow.py check-grounding-pack <章节依据包.json> `
  --response-register requirements/response-register.json `
  --scoring-applicability requirements/scoring-applicability.json `
  --report <依据包检查报告.json>
python scripts/bidflow.py check-paragraph-plan <段落计划.json> `
  --grounding <章节依据包.json> `
  --report <段落计划检查报告.json>
```

G2 通过前，总控必须确认章节规划、每个章节任务的依据包和段落计划均为 `PASS`，且 `open_questions` 已关闭。缺少项目事实、来源或废标条款绑定时，不得启动 `chapter-realizer-*`。

### Round 4：章节初稿真实落位

每个章节任务书派发一个 `chapter-realizer-*` subagent；`chapter-writer-*` 仅作为兼容性别名。并行数量由任务书数量决定，而不是由评分项数量决定。

派发提示至少包含：

```text
你负责且仅负责 <任务书路径>。
只读取任务书、章节依据包、段落写作计划和任务书允许的来源，只写入任务书指定的章节和证据文件。
严格使用任务书中的 planned_outline，不得自行新增、删除、重排或重命名标题。
逐段落实项目实际、评分内容对象、执行动作、控制节点、交付成果和来源引用。
对每个 response_item_id 先原样写入 canonical_response，再按 allowed_expansion 增加细节；不得改变 fixed_elements 中的责任主体、条件、范围、数字、单位和承诺强度。
不要追求最终篇幅，不要执行三倍扩写，不要进行页级模板轮转、同义反复或空泛堆砌。
扩写深化由后续 chapter-expander-* 负责，你不得承担该环节职责。
禁止使用首先、其次、再次、此外、另外、最后、综上、综上所述、总之、由此可见、可以看出等模板化连接词。
历史 RAG 片段只能读取 cleaned_content，且只能作为表达、方法和结构参考，不能替代当前项目要求和技术规范。
所有事实与结论保留来源；证据缺失时标记待人工确认。
不得编造人员、资质、业绩、时限、服务、功能或接口承诺。
不得使用 DISABLED 历史片段，不得使用未确认的 NEEDS_CONFIRMATION 片段。
发现其他项目或其他标包内容时立即停止并上报。
你不是唯一在仓库工作的 agent，不得覆盖或回退他人改动。
```

总控必须对每个章节初稿执行：

```powershell
python scripts/bidflow.py check-chapter-draft <任务书.json> <章节初稿.md> `
  --evidence <章节证据.json> `
  --grounding <章节依据包.json> `
  --paragraph-plan <段落计划.json> `
  --report <初稿检查报告.json>

python scripts/bidflow.py check-responses requirements/response-register.json <章节初稿.md> `
  --task <任务书.json> `
  --evidence <章节证据.json> `
  --report <响应口径检查报告.json>

python scripts/bidflow.py check-rejection <废标否决条款.json> <章节初稿.md> `
  --task <任务书.json> `
  --evidence <章节证据.json> `
  --report <废标否决检查报告.json>
```

初稿检查未通过时，不得进入 `chapter-expander-*`。

### Round 5：章节受控扩写

每个已通过 `check-chapter-draft` 的章节初稿派发一个 `chapter-expander-*` subagent。扩写角色只负责在原有结构和事实边界内将内容加厚，不承担需求补写、事实创造、承诺增强或章节重构职责，也不得回退为初稿生成器。

派发提示至少包含：

```text
你负责且仅负责扩写任务书 <任务书路径>。
严格保持原文全部标题、标题层级、分段顺序和段落数量，不得删除、合并、拆分或重排段落。
完整保留原文官样文风、我司视角、核心事实、参数、约束、response_item_id、canonical_response、fixed_elements 及证据引用。
将全文有效字符数扩写至原文约 3 倍，允许范围为 2.7–3.5 倍；每个正文段落不得低于原段落的 2.5 倍。
扩写只能展开原文已有的实施动作、执行步骤、协作关系、控制节点和成果形成过程。
不得新增未经来源支持的事实、功能、人员、业绩、时限、服务或承诺。
不得把阶段性现场联络扩大为全周期驻场，不得把采购方义务转为我司义务。
禁止使用首先、其次、再次、此外、另外、最后、综上、综上所述、总之、由此可见、可以看出等模板化连接词。
各段落开头直接进入具体内容，禁止使用概括、总结或结论性引导语。
各段落结尾停留在具体动作、控制要求、交付内容或衔接事项，禁止使用总结性收束语。
保持上下文衔接流畅、逻辑严谨，禁止同义反复、空泛口号或形容词堆砌凑字数。
无法在不新增事实的前提下达到扩写比例时，立即停止并上报。
你不是唯一在仓库工作的 agent，不得覆盖或回退他人改动。
```

总控必须对每个扩写稿执行：

```powershell
python scripts/bidflow.py check-expansion <原章节.md> <扩写章节.md> `
  --evidence <章节证据.json> `
  --paragraph-plan <段落计划.json> `
  --report <扩写审查报告.json>

python scripts/bidflow.py check-responses requirements/response-register.json <扩写章节.md> `
  --task <任务书.json> `
  --evidence <章节证据.json> `
  --report <扩写响应口径检查报告.json>

python scripts/bidflow.py check-rejection <废标否决条款.json> <扩写章节.md> `
  --task <任务书.json> `
  --evidence <章节证据.json> `
  --report <废标否决检查报告.json>
```

自动检查失败时只允许针对命中问题整改，最多两轮；仍不通过则转人工处理，禁止无边界地反复扩写。自动检查通过后，仍须人工抽查核心细节、我司视角、官样文风、上下文衔接及新增事实风险。

### Round 6：合稿

全部章节扩写并验收后，派发一个 `integration-editor`。其职责是去重、统一术语与承诺口径、修复衔接并生成追溯表，不得创造新事实。

### Round 7：确定性门禁优先审查

合稿完成后，总控先执行确定性门禁：

```powershell
python scripts/bidflow.py check-requirements requirements/atomic-requirements.json --report reviews/requirements-check.json
python scripts/bidflow.py check-response-register requirements/response-register.json --requirements requirements/atomic-requirements.json --report reviews/response-register-check.json
python scripts/bidflow.py check-responses requirements/response-register.json merged/technical-bid-draft.md --report reviews/response-consistency.json
python scripts/bidflow.py check-rejection requirements/rejection-clauses.json merged/technical-bid-draft.md --report reviews/rejection.json
python scripts/bidflow.py validate <项目目录> --stage export
```

只有当确定性门禁发现问题且需要语义定位、误报判断或跨章节整改建议时，才升级派发：

- `compliance-reviewer`
- `rejection-reviewer`
- `residue-reviewer`
- `format-reviewer`

四者写入不同审查文件。总控汇总确定性检查和升级审查结果并计算门禁：

- 存在任何 `BLOCKER`：`REJECT`，立即阻断。
- 无 `BLOCKER`，但存在 `CRITICAL` 或 `MAJOR`：`REVIEW_REQUIRED`。
- 仅有 `MINOR` 或 `INFO`：`PASS_WITH_WARNINGS`。
- 无未解决问题：`PASS`。

### Round 8：整改与复审

整改应优先回派给原章节初稿生成 agent 或扩写 agent；跨章节问题回派给 `integration-editor`。整改后只复审受影响范围，但项目、标包、承诺和技术偏差发生变化时必须重新执行全量审查。

### Round 9：Word 导出

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
