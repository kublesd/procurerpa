# ProcureRPA 能力与版本二开发差距

## 文档用途

本页负责采购能力边界、真实/模拟关系，以及 `resume_guide.md`“版本二：AI 强化版”与当前实现之间的开发差距；不负责声明当前任务、当前分支、最新验证或下一阶段。

- 当前目标、活动任务和最新证据：[`../PROGRESS.md`](../PROGRESS.md)
- 通用开发与验证流程：[`agent_development_workflow.md`](agent_development_workflow.md)
- S1～S9 历史阶段契约：[`procurement_rpa_development_guide.md`](procurement_rpa_development_guide.md)
- 架构和安全边界：[`agent_architecture.md`](agent_architecture.md)、[`agent_security_rules.md`](agent_security_rules.md)

P1～P6 与 S1～S9 均是已执行路线的历史名称，不能从本页直接领取。仓库 Git 历史重写后，旧 commit ID 只作为历史标签；是否可复现必须以当前 Git 对象和本次运行证据为准。

## 长期边界

1. **保留真实采购主链。** 已有 PostgreSQL、权限、审批、审计、Artifact 和 Skyvern 报价链只能复用或增强，不能改回 demo。
2. **模拟能力显式隔离。** fake page、内存 store、模拟 Executor、固定成本等只允许进入标记过的演示或兼容入口。
3. **真实决定保持确定性。** 金额、风险下限、审批、提交、删除和供应商推荐由服务端规则决定。
4. **证据等级不混用。** mock、用户报告、历史记录和本次真实运行分别标记；外部服务不可用时写 `unverified`。
5. **差距可见但不自动扩展范围。** 任何差距都需要在 `PROGRESS.md` 中形成有界活动任务后才能实施。

## 已验证真实采购主链

```text
受控供应商页
  → POST /enterprise/procurement/quote-task
  → task_v1_service.run_task()
  → 原生 Skyvern executor / Chromium
  → Task + Artifact + SupplierQuote
  → Decimal 确定性比价
  → 采购工作台 / 审批 / 审计 / PostgreSQL Dashboard
```

`demo_procurement_parity.py` 展示的是功能对等适配能力，不替代这条链，也不能作为真实链验收证据。

## 能力索引

| 能力 | 主要实现责任 | 真实/模拟边界 | 关键不变量 |
| --- | --- | --- | --- |
| 认证与租户范围 | `enterprise/auth/`、`enterprise/tenant/` | 生产 API 从同组织服务端事实重载范围 | 客户端字段不能扩大组织、部门或品类权限 |
| 风险与审批 | `enterprise/procurement/`、`enterprise/approval/` | 真实规则与 demo LLM 判断分离 | 申请人不能自批；决定可审计且幂等 |
| 报价与比价 | `enterprise/procurement/` | 真实 SupplierQuote 绑定 Task/Artifact | Decimal 计算；LLM 输出校验后才可入库 |
| Artifact 与审计 | `enterprise/audit/`、Skyvern Artifact | 真实文件存 MinIO/object URI；演示摘要需标记 | 同组织证据；日志不含预签名 URL 或敏感正文 |
| Planner/Coordinator | `enterprise/agent/` | 持久 Session 路径使用 PostgreSQL；无 Session 兼容路径仅供模拟 | 恢复只信数据库状态；写入失败不返回成功 |
| Skill 与模板 | `enterprise/skills/`、`enterprise/workflows/` | 生产编译结果交给原生 Skyvern；fake pipeline 仅供 demo/test | 不创建第二套浏览器运行时 |
| 人工核验 | `procurement_human_reviews` 与相关 API | 真实失败形成持久 Review；内存 helper 仅供演示 | 租户隔离、授权处置、审计和重启可读 |
| Action Cache | Skyvern Agent 调用点与 Redis | 生产缓存使用 Redis；内存 store 仅供 demo | 组织、DOM、目标、模型和 schema 隔离；敏感动作不缓存 |
| 模型路由 | Skyvern LLM Registry 与采购路由 | 生产只使用已注册 key；demo tier helper 不代表真实调用 | 无可用模型时失败关闭或进入 Review |
| 成本 Dashboard | PostgreSQL Step token/cost | 真实 API 不读取固定 demo facts | Decimal 聚合；未知成本不估算成真实值 |
| 工程验收 | pytest、Vitest、迁移检查和受控集成测试 | 历史成功不覆盖当前未验证实现 | 重启、并发、租户、失败关闭和日志证据分别记录；真实 smoke 不作为完成门 |

## 历史两阶段路线

| 阶段 | 历史目标 | 当前用途 |
| --- | --- | --- |
| P1～P6 | 取得采购语义功能对等，允许明确标记的内存、fake 和 demo 路径 | 解释演示兼容代码来源，不再领取 |
| S1～S8 | 逐项接入 PostgreSQL、原生 Skyvern、Redis、真实模型配置和 Step 成本 | 复核实现与验收边界，不再领取 |
| S9 | 安全硬化、SIT 和生产 fallback 清理 | 复核安全边界与工程证据；真实外部 smoke 已移出完成门 |

阶段顺序、原始完成门和禁止项保留在历史实施契约中。某项需要返工时，应根据当前源码重新定义独立任务，不能假定旧阶段描述仍与调用方一致。

## 差距领取规则

以下契约只服务于“版本二”能力真实性，不是自动路线或优先级。一次只能把一个差距 ID 复制到 `PROGRESS.md` 作为活动任务；开工前重新核对真实调用方、当前迁移 head 和代表性测试。

每项差距有两个合法出口：实现进入真实采购主链并留下本次证据，或收缩 `docs/resume_guide.md` 的对应表述。新增 demo、测试专用 helper 或静态样例不能关闭差距；`70%`、`60%` 等数字只能来自可复现基线和测量结果。

每项任务统一遵守：先留下失败测试或可复现证据；涉及状态/schema 时验证旧记录、并发和事务失败；只运行相关测试、改动文件检查和必要的受控集成验证；失败不得降级成 `demo`/`simulated` 成功；完成后停止，不自动领取下一项。

## 分阶段开发指导

阶段只定义依赖顺序，不代表已经授权、开始或完成。每次仍只允许一个差距 ID 成为 `PROGRESS.md` 的活动任务；当前阶段达到完成门后必须停止，由用户明确选择是否进入下一阶段。若前序阶段选择“收缩简历表述”而非实现，后序阶段按收缩后的真实能力继续，不补造兼容层。

| 阶段 | 顺序与目标 | 入口门 | 完成门 |
| --- | --- | --- | --- |
| 0. 证据与决定冻结 | 为下一项建立真实调用图、失败复现、基线和人工决定 | 用户明确选择一个差距 ID；`git status --short` 已记录；真实调用方和代表性测试已定位 | `PROGRESS.md` 写明完成定义、批准路径、范围外、最小验证、停止条件；所有必需人工决定已有答案，否则停止 |
| 1. 确定性审批边界 | `APPROVAL-01`：先稳定金额、品类、角色和策略快照 | 阈值权威来源、币种、生效时间、critical 路由规则已确认 | 路由快照可恢复且不可由客户端覆盖；Pub/Sub 有受权消费者与故障回退；越权、自批、重复决定、并发 continue 失败关闭或幂等 |
| 2. 现有报价 LLM 边界 | `LLM-RESILIENCE-01`：先强化已存在的报价抽取链，不新增模型职责 | 支持单位、币种、汇率来源和封闭纠正规则已确认；原生 Skyvern retry/parse 能力已盘点 | 真实 quote-task 覆盖解析、有限重试、规范化、Artifact 校验和持久人工核验；没有重复 retry 状态机 |
| 3. 新增风险 LLM | `AI-RISK-01`：在确定性审批和模型边界稳定后接入 Stage 2 | 模型提供方、允许数据类别、保留期、预算/拆单事实来源已确认 | 只在规则命中时发送 allowlist 上下文；失败不降低确定性风险；调用避免率有可复现基线，或删除 `70%` 表述 |
| 4. 原生编排与模板 | 先 `PLANNER-01`，验收后再 `SKILL-01` | 状态所有者、提交顺序、首个真实入口及代表模板已确定；凭据提供方和运行身份在进入 `SKILL-01` 前确认 | Planner 只驱动原生 Skyvern 且可恢复/replan；代表模板具备真实步骤、Artifact、审计和凭据引用，其余模板通过同一安全编译契约 |
| 5. 路由与量化 | `MODEL-COST-01`：最后接运行时特征、Dashboard 和成本基准 | 前序真实链能稳定产生 Step、token/cache/cost 事实；运行时特征生命周期和固定样本已定义 | UI 只展示真实指标；路由与缓存基线可重复；达不到 `60%` 就修改简历数字，不调整样本凑结果 |

### 每阶段执行循环

1. **RED：** 在选定契约的真实调用边界留下一个失败测试或最小复现，证明差距仍存在；禁止用 demo 路径代替。
2. **GREEN：** 复用现有责任模块、原生 Skyvern、数据库约束和已安装依赖，做满足当前完成门的最小修改。
3. **REFACTOR：** 删除被真实链取代的重复 helper 或入口；保留仍有调用方的 demo 时继续标记 `demo`/`simulated`/`not_connected`。
4. **VERIFY：** 运行契约指定的代表性测试、改动文件 Ruff、需要的迁移/临时 PostgreSQL/前端检查和 `git diff --check`；计划命令、历史结果和外部失败不得记作本次通过。
5. **HANDOFF：** 把修订、环境、命令结果、未验证项、剩余限制和停止原因写回 `PROGRESS.md`；只有影响后续阶段的重大取舍才追加 `DECISIONS.md`。

### 阶段中止与回退

- 发现需要真实凭据、外部写入、部署、破坏性数据操作、新消息基础设施或第二套浏览器运行时时立即停止，记录最小证据并申请单独授权。
- 模型、Redis、MinIO、浏览器或数据库不可用时保留失败事实；不得返回模拟成功。可安全重试的操作必须有幂等依据，浏览器副作用不明时转人工核验。
- 阶段完成后不得自动进入下一项。若实现成本超过简历价值，直接采用该契约允许的“收缩简历表述”出口。

## 版本二开发契约

### `AI-RISK-01` 双阶段风险识别进入真实入口

- **能力边界：** `quote-task` 已接入受限 Stage 2：仅发送服务端风险类别/等级，原生模型未配置或失败进入保守风险回退；smoke-task 保持规则层。预算、拆单缺乏权威事实，页面/供应商正文不获准发送，均未纳入本切片。模型实调与调用避免率尚未验证，简历移除 `70%` 断言，其他上下文能力继续作为目标而非本切片成果；本轮证据仅由 PROGRESS.md 记录。
- **目标与范围：** 复用现有 `detect_risk`，只在规则命中且获准上下文存在时调用已批准模型；服务端规则决定风险下限，LLM 只能补充说明或提高等级。补齐预算超额和拆单必须先有权威预算/关联申请事实，不能靠文本猜测。
- **范围外：** 让 LLM 决定金额、权限、审批或供应商推荐；保存原始页面正文；为凑规则数量增加无业务依据规则。
- **开工前决定：** 用户确认模型提供方、允许发送的数据类别、保留期及预算/拆单事实来源；未确认时保持规则层并收缩简历表述。
- **可观察验收：** 低风险不调用模型；命中场景只发送 allowlist 且已脱敏上下文；模型失败保留确定性下限并产生安全审计；跨组织、secret、银行账户、Token 和超限上下文在调用前被拒绝或脱敏；基线报告给出真实调用避免率，达不到 `70%` 就修改简历数字。
- **代表性验证与停止：** 扩展 `tests/unit/test_risk_detector.py`、`tests/unit/test_day_1_smoke_security.py` 和 quote-task 路由测试；达到一条真实入口闭环即停止，不泛化全部 Agent。

### `LLM-RESILIENCE-01` 报价抽取容错进入真实主链

- **当前差距：** JSON Schema、Pydantic、Markdown 清理和指数退避 helper 存在，但该 helper 明确为 demo；真实报价链直接消费原生 Skyvern 提取结果，只做严格 `unit`/`CNY` 校验，没有单位币种纠错。
- **目标与范围：** 先复用原生 Skyvern 的结构化输出和重试能力；仅补真实链缺失的解析清理、有限重试与确定性单位/币种规范化。耗尽重试后复用持久人工核验及跳过、人工补录、终止三种处置，不创建第二套状态机。
- **范围外：** 用 LLM 自由换算金额、猜汇率或自动接受未知单位；把原始模型响应写入日志、审计或业务表；保留两套等价 retry wrapper。
- **开工前决定：** 明确支持单位、币种、汇率权威来源及可自动纠正的封闭映射；没有权威来源时继续严格拒绝。
- **可观察验收：** 结构错误、Markdown 包裹、可纠正规范值、不可识别单位/币种、重试耗尽和人工处置均在真实 quote-task 调用图中可观察；落库前仍通过同一 Pydantic/Decimal/Artifact 校验。
- **代表性验证与停止：** 扩展 `tests/unit/test_day_11_quotes.py`、`tests/unit/test_procurement_review_regressions.py` 及真实调用边界测试；原生能力已覆盖的部分删除或停用 demo helper，而不是再包一层。

### `PLANNER-01` Planner 只作为原生 Skyvern 编排层

- **能力边界：** quote-task 与六模板入口复用受限枚举 Planner；原生 Workflow 每步执行前核对持久计划顺序，完成后只规划未完成后缀，模型失败采用 deterministic_fallback。准备完成但未执行的实例可显式启动，运行歧义转 needs_human，过期版本拒绝。自由任务分解、独立 Coordinator 和四种失败策略仍属 demo，不宣称通用浏览器断点续跑或规划收益。
- **目标与范围：** Planner 只产出并更新脱敏计划；浏览器事实和动作始终由原生 Skyvern Task/Workflow/Action 拥有。复用现有 coordination state、TaskExtension、Review 和审计标识，replan 只包含未完成步骤。
- **范围外：** 第二套浏览器运行时、改写原生 executor、自动重放副作用不明的浏览器动作、保存页面正文或凭据。
- **开工前决定：** 先画明 quote-task 与模板入口的状态所有者和提交顺序，选择一个真实入口作为首个切片；若接入需要新工作流引擎，停止并收缩简历表述。
- **可观察验收：** LLM 计划能驱动同一原生任务链；完成步骤在重启后不重复；replan 不包含已完成步骤；过期版本被拒绝；执行歧义进入人工核验；响应、日志和快照无敏感参数。
- **代表性验证与停止：** 扩展 `tests/unit/test_agent.py`、`tests/unit/test_s2_coordination_persistence.py` 和选定入口的 PostgreSQL 恢复测试；完成一个端到端真实切片即停止，其他入口仍明确标记未统一。

### `SKILL-01` Skill/模板具备真实执行与审计语义

- **能力边界：** 七个 Skill 已映射为原生 Login/Navigation/Extraction/FileDownload Block，六个历史模板通过同一编译与安全契约，代表模板经真实路由、原生步骤入口、数据库证据/审计和显式恢复验收。组织内 CredentialVaultService 引用在启动、每步与输入边界重验身份/用途/版本；缺失、吊销或变更失败关闭。目录、实例读取、恢复与终止前端已接入。quote-task/v1 保留原采购链与人工 manual_completed 语义。数据模式为 controlled_demo，浏览器/provider/vault 外部边界的集成验证使用合成替身；独立 Pipeline 仍为 simulated，不代表新增原生入口。仅支持无 TOTP、无浏览器配置的密码引用；图像、录屏、二进制及路径 Artifact 不保留，已知秘密掩码后的文本证据才可持久化。真实供应商、外部模型/密钥库 smoke、六模板实际网页完成率和任意敏感正文脱敏尚未验证。
- **目标与范围：** 复用现有 Skill 定义和原生 Skyvern，不执行第二套 Playwright Pipeline；每个模板的声明步骤可映射到可观察的原生执行/结果，Skill 粒度审计只保存安全元数据。凭据只保存引用并在执行边界按组织/用途解析。
- **范围外：** 自建密钥系统、明文/可逆凭据进入模板或 Prompt、为每个 Skill 新建运行时、把报价/合同正文写入普通审计。
- **开工前决定：** 用户确认凭据提供方、运行身份、轮换/吊销语义；先选择一个代表模板，证明映射方案后再决定是否批量推广。
- **可观察验收：** 代表模板可由真实入口启动并完成或明确失败；步骤状态和 Artifact 可追溯；跨组织、吊销、缺失凭据失败关闭；数据库、Prompt、日志、Artifact 和响应扫描无 secret；其余五个模板至少通过同一编译和安全契约，不能仅靠 fake page 宣称完成。
- **代表性验证与停止：** 扩展 `tests/unit/test_s5_skill_pipeline.py`、`tests/unit/test_workflows.py`、安全日志测试及一个受控原生执行集成测试；代表切片验收后停止，不顺带建设通用 Workflow 平台。

### `MODEL-COST-01` 运行时模型路由与量化成本证据

- **当前事实（2026-10-01）：** 阶段 5 已接原生 scrape 的结构特征选择点、Step 路由审计和 Dashboard 成本/缓存 API。元素数指原生树已观察节点，不是完整 DOM 总量；无可靠 AJAX/WebSocket 信号，动态内容明确 `not_observed`。固定六样本数值比较入口为 `scripts/benchmark_model_cost.py`，没有 provider 实调与成对计费记录时成本/节省率保持 unknown，简历删除 `60%` 断言。验收证据以 PROGRESS.md 为准。
- **目标与范围：** 优先复用原生 scrape/step 已有信号，在不增加一次昂贵模型调用的前提下取得元素量、iframe/动态内容等运行时特征并选择已注册模型 key；保留当前缓存隔离和敏感动作 no-cache。前端只展示 PostgreSQL Step 与 Redis 真实指标。
- **范围外：** 为路由额外抓取或长期保存原始 DOM；把 demo price/call 数据混入真实 Dashboard；缓存输入、上传、登录、提交或个性化值；为了得到 `60%` 调整样本。
- **开工前决定：** 明确可用运行时特征的生命周期和成本基线；若模型选择前拿不到可信特征，保留静态 page-kind 路由并收缩“页面复杂度评分”表述。
- **可观察验收：** 路由审计记录脱敏特征摘要、模型 key、tier、原因和 Step；Redis 故障回源模型且不返回伪缓存命中；Dashboard UI 展示真实 token、cache、cost 状态；固定样本基线可重复比较路由/缓存前后成本，达不到 `60%` 就修改简历数字。
- **代表性验证与停止：** 扩展 `tests/unit/test_s7_model_routing.py`、`tests/unit/test_action_cache.py`、`tests/unit/test_dashboard.py` 和对应前端测试；没有真实 provider cost 时显示 unknown，不估算成事实。

### `APPROVAL-01` 四维权限下的确定性审批路由闭环

- **当前差距：** 组织、部门、品类、角色隔离和申请人不能自批已落地；但生产审批创建没有复用 `route_approval`，金额/品类/策略版本未作为路由快照持久化，Redis Pub/Sub 只有独立模块和测试调用。
- **目标与范围：** 组织、部门、品类、角色和金额共同形成服务端确定性路由输入；创建审批时持久化策略版本、命中阈值、category 和路由结果。审批决定提交后通过组织隔离的 Redis Pub/Sub 安全事件通知受权请求人，消费者重新读取 PostgreSQL。LLM 只提供风险说明，不能改变授权或推荐。
- **范围外：** 无业务规则支持的多级会签、BPMN/规则平台、LLM 审批决定。现有“审批后由发起人显式 continue”是已批准架构；不得只为匹配技术栈文字重新引入 Redis 阻塞等待。
- **开工前决定：** 用户已授权按版本二简历目标冻结：复用版本化 CNY/Decimal 服务端阈值；high 路由本部门品类 approver；critical 路由同组织 `COMPLIANCE` 部门品类 approver；Redis Pub/Sub 只做事务后实时通知，PostgreSQL 仍为事实源，批准后保留请求人显式 continue。
- **可观察验收：** 边界金额和品类产生预期且可恢复的路由快照；客户端不能覆盖策略字段；跨组织、跨部门、跨品类、自批、重复决定和并发 continue 均失败关闭或幂等；决定只在提交后发布安全事件，跨组织不能订阅，消费者必须重读数据库，Redis 故障/事件丢失回退轮询且不自动执行；供应商推荐仍由 Decimal 规则决定。
- **代表性验证与停止：** 扩展 `tests/unit/test_risk_detector.py`、`tests/unit/test_approval_model.py`、`tests/unit/test_approval_routes.py`、`tests/unit/test_approval_pubsub.py`、审批前端测试和采购回归测试；单级确定性闭环完成即停止，多级审批另需明确业务授权。

## 明确排除项

- 真实 `quotes`/`controls` smoke、外部模型配额和真实供应商站点可用性不是上述契约的默认验收；若某项量化指标必须依赖外部运行，应单独授权并如实标记环境。
- 全量 Ruff 历史问题、旧数据库演示记录、本机失效 `.venv`、权威 SKU/别名等未包含在版本二主张中的事项，不再作为本页当前开发差距。
- 任何契约完成后只更新本次观察证据和剩余限制，不自动领取下一项。
