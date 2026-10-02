# 设计决策

> 本文件只追加影响后续开发的重要取舍，不复制代码结构。来源/为什么：代码能说明“是什么”，但不能完整说明“为什么没有选另一条路”；适用条件：新架构选择、边界变化或替代方案被否决时；过期条件：正式 ADR 系统接管。

## 2026-07-31：目标是完成一条真实采购报价链

- 原因：当前企业底座已经接通，最大缺口是报价采集、标准化、比价和真实页面展示。
- 否决方案：按 ProcureRPA 目录逐项改名，或用模块数量和测试数量代表完成度。
- 约束：Day 10～16 按 `docs/procurement_completion_gap.md` 顺序实施，每次只领取一个 Day。

## 2026-07-31：浏览器执行只使用 Skyvern 原生链

- 原因：`task_v1_service`、原生 executor、ForgeAgent 和 ActionHandler 已能驱动真实浏览器。
- 否决方案：把 `enterprise/agent` 或 `enterprise/skills` 接成第二套 Planner/Executor 运行时。
- 约束：新报价任务使用 Skyvern TaskRequest 的提取目标与 schema；修改 Skyvern 核心前必须证明 enterprise 层无法完成。

## 2026-07-31：关键采购决定使用确定性规则

- 原因：金额、风险、审批、提交和供应商推荐需要可重复、可解释。
- 否决方案：让 LLM 直接决定报价是否有效、风险等级下限或推荐供应商。
- 约束：金额使用 Decimal；LLM 只做页面理解、字段候选映射和非决定性说明，输出必须再次校验。

## 2026-07-31：高风险任务采用单级审批和显式继续

- 原因：当前演示只需证明申请人与审批人分离，并继续同一条 Skyvern Task。
- 否决方案：Redis 阻塞等待、多级会签和新的流程编排平台。
- 约束：批准只写审批事实；发起人调用 continue 后才执行，拒绝后原 Task 必须取消。

## 2026-07-31：状态与决策分开持久化

- 原因：低推理 Agent 需要短小的当前状态，也需要关键取舍原因；聊天历史不能可靠跨会话。
- 否决方案：把全部状态塞进 `AGENTS.md`，或为每次会话创建新的长篇 handoff 文件。
- 约束：任务开始阅读 `PROGRESS.md` 和 `DECISIONS.md`；验证后覆盖 PROGRESS 的最新状态，DECISIONS 只追加重要决策。
- 2026-07-31 Day 10：报价事实单独存入 `supplier_quotes`，组织由认证用户服务端上下文派生，写入必须匹配同一组织的 TaskExtension 和 Artifact。
- 首版只接受 CNY 和 `unit` 基础单位；金额/数量使用 Decimal 与 Numeric，比较按含税到岸单价排序，交期、供应商 ID、报价 ID 固定破平局。
- 约束：Day 11 的 Skyvern 提取结果必须先通过同样的字段/租户校验再落库；不把 LLM 输出直接作为比价或推荐决定。

## 2026-07-31：报价采集结果必须绑定浏览器证据

- 原因：真实页面抽取需要保留可复核来源，不能只保存 LLM 返回的字段。
- 取舍：Day 11 只接受完成的原生 Skyvern Task、通过固定字段与置信度校验的单条报价，并绑定同 Task、同组织的 HTML 或截图 Artifact。
- 约束：缺字段、类型错误、低置信度或缺 Artifact 统一进入人工确认；跨 Task 比价保留每条报价的 `task_id` 和 `artifact_id`。

## 2026-08-01：采购工作台固定受控供应商入口

- 原因：Day 12 只需把已验证的真实报价链呈现给采购用户；任意 URL 会扩大 SSRF、权限和演示范围。
- 取舍：前端固定两个受控供应商页面并顺序调用已有 `quote-task`，组织、部门和品类继续由服务端事实控制。

## 2026-08-01：Compose preview 的 API 地址由共享 authFetch 统一解析

- 原因：Vite preview 没有开发服务器 proxy，工作台的相对 `/api/v1` 请求会落到 UI 静态服务并返回 500。
- 取舍：在共享 `authFetch` 中解析已配置的 `VITE_API_BASE_URL`，不让每个页面重复拼接 API 地址。

## 2026-08-01：Day 13 Dashboard 只保留 PostgreSQL 采购事实端点

- 原因：旧 Dashboard 使用进程内金融演示数据和未配置的缓存层，重启后会制造假统计，也无法按采购部门/品类隔离。
- 取舍：Dashboard 只保留 `overview`、`trend`、`categories` 和 `recent-tasks`，直接查询现有 TaskExtension、Task、SupplierQuote、ApprovalRequest 与采购品类表。
- 否决方案：继续保留旧金融端点、Redis org-only 缓存或前端失败 fallback；这些方案会把接口失败伪装成采购事实。
- 约束：查询先应用组织/部门/品类租户范围；审批只按已可见 Task ID 限制；无数据显示空态，接口失败显示真实错误；Permissions 与 LLM Monitor 暂不接入运行路径。

## 2026-08-01：采购演示数据只保留数据库 seed

- 原因：演示主链已经由真实 PostgreSQL、Skyvern Task、报价、审批、Artifact 和审计事实组成，旧金融内存/SQL seed 会制造第二套数据源。
- 取舍：`enterprise/procurement/seed.py` 是唯一演示数据来源；旧金融 seed、SIT runner 和无调用方的静态企业展示页面删除。
- 约束：seed 保持幂等，调用方负责 commit；不在 import 或 FastAPI 启动时自动写入业务数据。

## 2026-08-01：先完成 ProcureRPA 采购化功能对等，再统一真实链

- 原因：当前目标已从“只收口一条真实报价链”调整为“逐项把 ProcureRPA 企业能力适配成采购 RPA”；若先要求每项持久化并接入原生 Skyvern，会阻断 Planner、Skill、模板、容错、缓存和成本能力的直接适配。
- 取舍：第一阶段允许保留上游的内存 store、demo seed、模拟 Executor、独立 Planner/Skill 链、ID-only workflow instantiate、内存 Action Cache 和演示成本数据；完成标准是采购语义与最小演示对等。第二阶段再逐项完成 PostgreSQL/Redis、真实 Skyvern Task/Workflow/Action、安全硬化和 SIT。
- 保留：现有受控供应商 → Skyvern → Task/Artifact/SupplierQuote → Decimal 比价 → 审批/审计/Dashboard 真实主链不回退；已有更强采购实现无需降级成上游原型。
- 否决方案：继续用旧 Day 12～16 的“不得接 Planner/Skill/第二运行链”作为全局禁令；或为了对齐上游而删除当前真实采购实现。
- 约束：该决策对新的 P1～P6 路线优先，取代 2026-07-31 两项旧决策对新开发顺序和“只能使用原生链”的绝对适用；旧决策仍作为现有真实采购主链的历史设计依据。模拟/demo/未接入必须明确标记，真实密钥和真实敏感采购数据仍不得进入 LLM、日志或演示 store。

## 2026-08-01：P1 审批品类授权复用 TaskExtension

- 原因：现有 `approval_requests` 表只有部门和兼容 `business_line` 字段；P1 需要先证明品类授权，不能为第一阶段引入迁移和第二套审批事实源。
- 取舍：审批列表与 approve/reject 决定从同组织 TaskExtension 读取采购 `category_id`，再用服务端 `procurement_category_ids` 校验；`business_line` 只保留给旧调用方，管理员仍不能跨组织。
- 约束：审批表的 category/routing 持久化、多级路由、恢复和真实 Skyvern 暂停/继续进入第二阶段；现有真实报价与审批主链不回退。

## 2026-08-02：P4 模板按采购场景分类并保留模拟 Pipeline

- 原因：P4 需要让上游六个声明式模板具备采购语义，同时证明参数映射可以进入现有 Skill Pipeline。
- 取舍：模板按直接物料、MRO、服务采购各两个分类；包级导入自动注册七个 Skill；`build_skill_pipeline` 只做参数校验、字面量/占位符解析和 `SkillStep` 转换。
- 约束：Pipeline 和 instantiate 响应明确标记 `simulated`；当前只使用 fake page/内存步骤，不创建真实 Skyvern Task、不持久化实例，敏感参数仍只在响应中遮罩。

## 2026-08-02：P5 成本区与真实采购 Dashboard 分离

- 原因：P5 需要展示模型档位、缓存命中和成本节省，但当前 Dashboard 已由 PostgreSQL 真实采购事实驱动，不能用 demo model-call 数据覆盖任务、报价和审批统计。
- 取舍：复用现有 `dashboard/routes.py` 入口新增 `/cost`，成本计算读取独立固定采购 demo facts；模型路由与缓存继续使用纯函数/内存 singleton。
- 约束：成本单价、token、cache hit、节省值和模型路由均返回 `demo_estimate`/`simulated`/`not_connected` 标签；真实模型调用、价格事实、Redis、Skyvern action 接点和持久化进入第二阶段。

## 2026-08-02：P6 使用单入口演示收口，不统一第一阶段运行时

- 原因：P6 的验收目标是一次观察 P1～P5 的采购语义结果和边界，不是提前建设跨模块生产编排器。
- 取舍：新增 `scripts/demo_procurement_parity.py`，直接复用现有风险/路由、Agent、Skill Pipeline、LLM 容错、模型路由、Action Cache 和 demo 成本 helper；输出只保留采购结果、状态、合成 ID 和来源标签。
- 约束：fake page、内存 store、模拟模型和审计摘要统一标记 `demo`/`simulated`/`not_connected`；现有真实 `quote-task` → Skyvern → SupplierQuote → 比价/审批/审计/Dashboard 主链不由该脚本替换或冒充已联通。第二阶段再逐项接真实 handler、状态/审计持久化、Redis、模型调用和统一登录态。

## 2026-08-06：S6 在真实 Agent 调用点使用 Redis Action Cache

- 原因：Skyvern 既有数据库 action-plan 只按 URL+goal 复用，缺少组织、DOM、model、schema 和 24 小时 TTL；Vertex cache 只缓存 Prompt，均不能满足 S6 action decision 约束。
- 取舍：保留既有机制不改表，在 `ForgeAgent` extract-action LLM 调用点显式注入最小 Redis store；key 使用组织前缀和 SHA-256 variant，Redis 不可用时回源 LLM。
- 约束：只缓存原生解析器校验后的非个性化动作安全字段；输入、上传、选项、文件 URL、DOM、Prompt 和响应正文不得持久化。模型路由与真实 model key 解析仍属于 S7。

## 2026-08-06：S7 只路由到已注册的原生 LLM key

- 原因：Skyvern 的前端 model-name 映射不覆盖所有已启用 Registry key；仅写 model name 会让部分真实配置静默回落到默认 handler。
- 取舍：采购三档配置保存 Registry key，Task `model` 保存服务端解析出的 key/tier/reason；Task 只接受 Registry 已注册 key，继续复用原生 override handler，不实例化 provider SDK。
- 约束：heavy 只向 standard/light 降级；无可用 key 时创建 deferred Task 和 S1 review。审计只保存安全路由字段、Step ID、耗时和错误类型；真实 token/cost 聚合仍属于 S8。

## 2026-08-06：S9 生产入口失败关闭，第一阶段 fallback 不回流

- 原因：S9 的真实 API 不能在 Redis、MinIO、浏览器或持久化链不可用时返回 `simulated`/`demo` 成功；租户边界也必须由数据库事实再次约束，不能只依赖客户端 JWT 快照或关联表 ID。
- 取舍：缓存管理 API 只注入 Redis 持久 store，未配置/异常统一返回 503；Task/TaskExtension/Artifact/Quote/Audit 查询加入同组织关联条件；认证请求每次从同组织服务端表重载部门、业务线、品类和特殊权限；审批 continue 在审批行锁内 claim 原生 Task，失败则显式置为 failed。
- 约束：P6 的内存 Action Cache、demo cost、独立模型路由和无 handler Executor 仍保留给演示/兼容测试，但生产路由不可达且不得移除 `simulated` 边界标签。旧金融 Dashboard integration helper 不恢复为生产兼容 API，测试需迁移到当前采购事实 contract。

## 2026-08-09：HTTP response 日志不保存预签名 URL

- 原因：文件上传接口需要向调用方返回短期预签名 URL，但通用 response logger 不得把该 URL写入普通日志。
- 取舍：在共享精确字段脱敏集合中加入 `presigned_url`，仅把日志值替换为 `****`，不改变 API response 或 MinIO 对象引用。
- 约束：日志回归测试必须证明 `X-Amz-*` 查询值不落日志；业务库仍只保存 `minio://` object URI。

## 2026-09-21：真实 smoke 不再作为项目完成门

- 原因：用户明确要求去掉真实 smoke 验收。
- 取舍：项目状态以已有工程验证为完成依据，不再要求当前源码下的真实 quotes/controls smoke、数据库或浏览器联调后才能认定完成。
- 约束：该取舍不把未运行或失败的历史 smoke 重新标记为通过；历史证据继续按来源保留，未来只有在用户明确安排时才运行真实 smoke。

## 2026-09-21：审批报价后处理同步收口并复用现有数据库事实

- 原因：响应后的进程内 BackgroundTasks 在进程中断时会丢失报价入库；进程内幂等字典也不能跨重启或多进程复用。
- 取舍：不引入新队列。报价审批 continue 在返回前完成原生执行和入库/人工复核；完成 Task 可按现有 Task、TaskExtension 和 SupplierQuote 重试恢复。请求幂等键以用途前缀加 SHA-256 摘要存入 TaskExtension，数据库唯一约束负责并发兜底。
- 约束：每个 Task 只允许一条 SupplierQuote；该方案不承诺 Skyvern 原生浏览器执行中途崩溃后的自动续跑，后者仍需独立任务。

## 2026-09-22：RUN-01 使用数据库独占 claim 和显式恢复，不重放歧义浏览器动作

- 原因：原生执行器可能已经提交页面动作，单凭 Task.running 或超时无法证明重放安全；仅在审批行加锁也无法覆盖直接报价入口和报价后处理。
- 取舍：报价创建统一 defer execution，先持久化 TaskExtension/审批，再通过同一个恢复函数取得该 TaskExtension 的 PostgreSQL `FOR UPDATE SKIP LOCKED`。持锁贯穿执行与后处理，另一个数据库事务在调用原生执行器前提交 Task.running。无需新增表、迁移或消息服务。
- 恢复规则：created 可启动；completed 仅校验并幂等补报价；其他状态及执行异常进入持久人工核验；存在人工处置记录时不自动重跑。高风险仍检查已批准事实和发起人/管理员身份。
- 触发：quote-task 幂等重试、审批 continue 或 `POST /enterprise/procurement/tasks/{task_id}/recover-quote`；不增加后台扫描器。API 实际前缀沿用 `/api/v1`。
- 锁与接管：不使用基于耗时的 lease，不强抢存活连接；连接/事务结束后数据库释放锁，在断连被数据库确认前返回 409。执行期间占用一个额外数据库连接，连接池压力有实际证据时才考虑带 fencing 的 lease。
- 保留：自动续跑中断浏览器步骤仍不承诺；审计继续复用现有 writer，其 best-effort 与业务事务原子性属于 STATE-01。进程崩溃测试使用合成 Task/Artifact 和受控执行器，不代表真实浏览器 smoke。


## 2026-09-22：STATE-01 先收口 quote-task 的状态和事务

- 原因：原生 Task、审批/报价/人工核验和 best-effort 审计原先分开提交；Coordinator 已有持久状态表和版本列，不需要新增状态表或工作流引擎。
- 范围：按 STATE-01 契约先限定 quote-task；使用固定 `quote-task/v1` 模板标识和 `quote:<task_id>` 计划标识，实例就是原 Task ID。`procurement_coordination_states.current_plan` 保存当前企业步骤和 task_id 输入引用；不复制参数、URL 或页面正文。
- 唯一事实：Task 保留浏览器执行事实；TaskExtension 保留租户/风险；Approval/Review/Quote 保留业务事实；coordination state 仅记录企业处理步骤。Coordinator 拒绝加载由 quote-task 拥有的快照，不产生另一套执行器。
- 提交顺序：上下文/待审批/审计同事务；执行前 Task.running/企业 running/审计同事务；原生执行后报价或人工核验/企业步骤/审计同事务。审批决定及拒绝取消 Task、人工处置也同事务提交。原生浏览器副作用不纳入数据库事务，保留 RUN-01 的显式恢复与歧义态转人工。
- 并发：保留 TaskExtension 独占 claim，企业快照用 task_id + organization_id + version CAS；恢复 API 可携带 expected_version，过期返回 409。只读 quote-state API 复用采购读取权限，并只返回标识、步骤和版本。
- 历史兼容：不批量回填。无快照旧任务首次合法状态变更时建立版本 1；未发生变更的旧任务返回 state=null。复用现有 JSON/版本列，不新增迁移。
- 保留：其他 Skill/template/Coordinator/Workflow 链的统一事务与页面自动恢复仍未完成；旧 best-effort 审计模式仅保留给未纳入本切片的调用方。

## 2026-09-22：APPROVAL-01 使用版本化 CNY 常量和同组织合规路由

- 原因：版本二简历要求组织、部门、品类、角色和金额共同形成确定性审批路由；当前生产创建链未调用 `route_approval`，且审批记录缺少策略快照。用户授权依据简历目标代为冻结阶段 0 策略。
- 取舍：复用现有 Decimal/CNY 阈值作为 `approval-cny-v1`，生效时间固定为 `2026-09-22T00:00:00Z`，只作用于新建审批。high 路由到申请部门的品类 approver；critical 按同组织唯一 `department_code=COMPLIANCE` 路由到具备品类授权的 approver，缺失、重复或无人具备授权时失败关闭。
- 实时协调：为实现版本二简历的 Redis Pub/Sub 目标，审批决定事务提交后向组织隔离 channel 发布安全通知，请求人工作台通过受权 long-poll 消费后重新读取 PostgreSQL；事件只降低通知延迟，不是审批事实或执行授权。Redis 故障/丢事件回退数据库轮询，批准后仍需请求人显式 continue。
- 否决方案：不建阈值配置平台，不使用跨组织或全局硬编码合规部门 ID，不让 critical 回退申请部门，不增加多级会签；不让 Pub/Sub 消息携带金额、备注或正文，不因消息到达自动执行采购，也不让发布失败回滚已提交审批。
- 约束：组织、部门、品类和角色以数据库事实为准；金额使用边界校验后的 Decimal。客户端不能覆盖策略版本、生效时间、阈值、路由或审批角色；LLM 不能改变风险下限、审批或供应商推荐。订阅必须复用审批可见范围，收到事件后必须重查数据库。

## 2026-09-26：LLM-RESILIENCE-01 保留原生重试与报价缺失事实

- 政策来源：用户明确选择仅规范大小写和首尾空格，最终仍只接受 unit/CNY；无币种别名、包装单位或汇率换算。
- 取舍：继续使用原生 Skyvern JSON/Markdown 解析、provider 配置与 ForgeAgent 有限 step retry；企业层不重放执行器、不增加 retry wrapper，非法结果或原生失败沿既有 Review/quote-state 转人工。demo retry 保留原有 demo 调用方，生产仅复用其无副作用 Markdown 清理函数。
- 原生边界：通用 schema filler 会把缺失价格、运费、交期等数值补成 0，企业入库层无法辨别该 0 是否为源页面事实。新报价 schema 增加 `x-skyvern-preserve-missing=true`，原生 filler 原样交回候选结果，由企业 Pydantic/Decimal/Artifact 校验决定是否入库；无标记的其他抽取保持原行为。此处为必要的最小原生修改，不建立第二套抽取器。
- 解析与安全：企业层只接受对象或完整 JSON/Markdown JSON，不修补残缺 JSON、不猜字段；字符串中的数字直接使用 `json.loads(parse_float=Decimal)`，避免 Pydantic JSON 入口的浮点中转。额外字段拒绝，异常链不附原始候选正文；不新增响应正文日志、审计或业务字段。
- 兼容与限制：恢复入口识别新旧两种固定报价 schema，不回填或改写历史 Task；旧任务已由原生补过的默认值、或已解析为浮点的数字无法反向恢复原始信息。本阶段不宣称修复历史数据，也不改写整个原生 provider/Artifact 存储体系。真实敏感采购数据仍不得进入 LLM。

## 2026-09-26：AI-RISK-01 只发送规则枚举并保留原生模型边界

- 授权：用户启动阶段 3，对模型/数据/保留期及预算/拆单来源均授权“你来决定”。选择仓库已有 Google Gemini `GEMINI_2.5_FLASH`，仅使用已注册配置，不读取凭据确认可用性、不回退其他提供方。本轮仅以受控替身验证，不调用外部模型。
- 最小数据：quote-task 在组织/部门/品类校验与幂等查重后复用 detect_risk；无命中跳过，命中仅发送服务端规则类别与确定性等级。客户端 redacted_description 只供本地规则识别，标签不视为脱敏证明，不发送金额、供应商标识、页面、历史消息或说明正文。原始预算/关联申请事实不存在，不用文本推断预算超额或拆单。
- 输出与保留：只接受单字段 risk_level 枚举；忽略自由文本的方案不足以避免底层日志泄漏，故原生 direct handler 新增 strict_response 选项，在通用修复解析/Artifact/响应日志之前严格解析，禁止附带 Artifact/历史，隔离继承的浏览器上下文，禁用 LiteLLM 普通回调和读写缓存；禁用 no-log 或启用 verbose 时拒绝调用。应用正文保留期为零；对发出的非敏感枚举不额外约束提供方保留期，不承诺提供方零保留或已核实账户政策。
- 决策与预算：模型只能保持/提高风险，不决定审批或采购；未配置/非法/异常沿现有保守回退（至少 high，critical 不降级），风险/审批/审计复用原事务持久化。单次最多 2048 completion tokens（容纳原生默认 1024 thinking budget），provider timeout 12 秒，企业边界 15 秒，不增加重试。只保存服务端固定说明、规则依据、stage 和 fallback，不保存模型自由说明。
- 范围与限制：smoke-task 与隔离 demo 保留原行为；没有新增 SDK、配置平台、迁移或第二运行时。strict 路径不写原生正文 Artifact 或 token/cost 记录；真实用量聚合留给 MODEL-COST-01。预算/拆单权威集成、丰富上下文、提供方实调与量化测量保留；删除简历 70% 断言，不把测试分布当成生产节省率。

## 2026-09-26：PLANNER-01 首个切片使用 quote-task 受限枚举计划

- 授权：用户启动阶段 4，并明确选择“采用受限 Planner（推荐）”；模型只返回允许的未完成步骤枚举，服务端校验顺序，失败回退既有确定性链，不接自由文本计划或自动重放。
- 取舍：首个切片使用 execute_native → persist_quote；仅发送固定步骤/完成枚举，复用已注册 GEMINI_2.5_FLASH 和 strict_response，12 秒 provider / 15 秒企业超时，无新增重试。模型计划只能通过完整顺序校验后参与调度，不能修改 Task 目标、URL、金额、权限或审批。没有可选业务顺序，因此本切片不宣称通用任务分解或规划收益。
- 状态：计划和安全审计先同事务提交；Task.running/企业状态/审计在浏览器调用前提交；最终业务入库和完成状态/审计保持同事务。继续使用同一 TaskExtension 独占 claim 和 coordination state CAS，无新表/引擎。原生 completed 的恢复只规划 persist_quote，running/queued 等歧义态不调用模型、不重跑而转人工。已保存有效计划在恢复时复用，已完成 Task 的剩余计划最多更新一次。
- 兼容：旧任务在首次合法恢复时懒建受限计划；计划提交后入库失败，计划保留可重试，报价/完成状态/完成审计一起回滚。人工补录只结束企业计划，只有同组织原生 Task 确实 completed 才记录 execute_native 完成。响应仍仅返回既有安全标识与版本；模型输出原文不持久化，source 明确区分 llm 与 deterministic_fallback。
- 保留：旧 PlannerAgent/Coordinator/demo 继续隔离；其他模板、Skill 粒度执行与凭据解析、真实模型/浏览器 smoke 不在本切片，不修改现有 block.py 删除，不创建第二套浏览器运行时。


## 2026-09-30：SKILL-01 首个切片复用无凭据 quote-task/v1

- 授权：用户要求继续阶段 4，并明确采用无凭据报价切片；登录、凭据提供方、运行身份与轮换/吊销留待独立确认。
- 取舍：使用既有 quote-task/v1 作为代表，增加 POST /api/v1/enterprise/workflows/instantiate/quote-task/v1；请求复用 QuoteTaskRequest 与 Idempotency-Key，直接调用原采购路由。模板入口保留开发环境、受控 URL、四维权限、风险/审批、显式 continue、独占 claim、Planner/CAS 和 Decimal/Artifact 校验；不创建另一套 Task 或 Pipeline 执行器，也不把六个历史模板改名冒充已真实化。
- 证据：coordination state 保存 table_extract 的安全投影与 Skill 审计，同报价/人工核验/状态事务提交。这里只映射原生报价抽取步骤，不执行独立 Playwright Skill。只有确定性校验后的原生 extracted_information 入库调用能标记 completed；人工核验及直接人工报价都标记 manual_completed，不因 Task.completed 推断人工结果来自原生提取。旧快照无 Skill 字段时显示 not_connected，首次合法状态变更才补投影。
- 失败关闭：六个历史模板仍可查询，但列表/详情标记 not_connected，实例化在创建 Task 前返回 workflow_credentials_not_connected。原生编译器拒绝 login/session_keep_alive，避免丢弃凭据后仍宣称登录完成；独立 demo Skill 定义与 simulated Pipeline 保留。
- 保留：代表模板为 API 切片，前端模板目录未接入；其余 Skill、历史模板的业务步骤、凭据引用和完整原生 Workflow 仍未统一。没有新增依赖、迁移、模型职责或真实外部调用，不改变既有 block.py 删除。


## 2026-09-30：阶段 4 复用原生 Workflow 与组织内凭据引用

- 授权：用户要求继续直至整个阶段 4 完成，在上轮列出凭据策略与恢复 block.py 两项确认后回复“继续”；本轮按提出的策略推进，并只从当前 HEAD 恢复该文件。此前报价切片的范围与停止记录保留为历史，不再限制本轮任务。
- 执行与事实：七 Skill 编译为现有 Login/Navigation/Extraction/FileDownload Block，六模板共享原生 Workflow 创建、prepare 和 AsyncExecutorFactory。准备的 run 固定其 workflow_id/版本，避免后续模板更新改变凭据与步骤。Task/Block/Artifact 仍拥有浏览器事实，quote-task/v1 仍调用既有采购 API，不改变 Decimal、风险、审批或人工报价决定。
- 持久化：原生登录前尚无 Task，既有 coordination 表的 Task 外键不能承载授权与准备态；因此 ent_013 只增加 procurement_workflow_instances 保存组织/部门/品类/请求人、幂等摘要、原生引用和安全状态。该表不是另一执行引擎。计划/状态/审计同事务，running 在原生派发前提交；每步核对剩余计划，完成必须有同组织原生 Task、Block、Artifact，表格另经结构校验。
- 凭据：沿原生 CredentialVaultService 按组织解析 credential_id，仅允许无 TOTP、无浏览器配置的 password 引用及精确受控 tested_url。启动、恢复、每步与密码输入重查执行人授权、用途、删除和 modified_at；吊销或轮换失败关闭。只允许发起人或组织管理员显式执行；管理员作为当前运行身份。凭据不得作为普通模板参数、模型输入、数据库输出或异常文本保存。
- 安全证据：已知秘密在 Prompt/输出/原生日志/创建和更新的文本 Artifact 掩码（含 JSON/HTML 转义）；认证 Workflow 禁模型历史、图片输入、强制秘密模板、录屏、截图、PDF、二进制和路径 Artifact。秘密只在受控 URL 的原生文本输入边界解析，其他动作拒绝解析。该选择牺牲视觉和二进制留存能力，不能宣称图片自动脱敏或任意敏感采购正文已获准。
- 恢复与取消：只有原生 created 且尚无 Block 的 ready 实例可派发；preparing/running 歧义转人工，不自动重放。恢复/终止要求 expected_version，终止同事务取消原生 run 和未完成 Task，后续准备或派发异常不能覆盖已提交终态。session_keep_alive 是有界原生会话检查/重新登录，不是后台永久保活服务。
- 验收边界：代表模板运行真实路由、转换器、prepare、原生步骤入口和 PostgreSQL；vault/browser/provider 仅用合成替身。其余五模板通过相同转换与安全契约，未宣称真实供应商全部完成或外部凭据可用。ent_013 仅在隔离测试库验证，生产迁移、真实 smoke、全量应用测试和阶段 5 均未执行。


## 2026-10-01：MODEL-COST-01 以当前 scrape 与 Step 审计归属模型

- 授权：用户明确启动阶段 5；检查期间 block.py 从已有修改变成删除后，用户单独授权从当前 HEAD 恢复。只恢复该文件，并保留企业模板禁强制秘密与输出掩码边界；不访问真实凭据、模型、供应商或生产环境。
- 特征生命周期：在已有 scrape 后、当前提示词/Vertex 缓存建立前读取原生结构树，保存节点/iframe 深度/表单/Shadow DOM 的计数和布尔摘要；不增加抓取或模型调用，不保存原始树/属性/文本。AJAX/WebSocket 无可信信号，记为 not_observed；缺失结构时保留已有注册静态 key，首次无 key 的任务使用既有静态动态门户档位。
- 模型归属：当前 Step 保存瞬时路由，当前调用使用 Task 副本而不覆盖 Task 的初始模型；同组织授权上下文与 Step 路由审计先提交，再构建提示词。无可用注册 key 或路由审计失败沿原生失败/重试边界停止，不静默回到默认 handler。Step 成本按持久路由归类；旧 Step 沿原 Task 档位。禁采购 speculative 预调用，避免并行步骤混用模型/缓存与用量归属。
- 缓存与权限：保留原 Redis key 与 24h TTL。采购仅缓存无表单页面的 WAIT/SCROLL；认证实例、缺失结构、输入/上传/提交等不缓存。Dashboard 用量按组织/部门/品类隔离，组织级 Redis 统计仅 org_admin 可读；Redis 故障只标记 unavailable，不覆盖 PostgreSQL 用量或伪造命中率。提供方缓存 Token 与动作缓存查询命中分开显示。
- 成本边界：展示原生 Step 报告成本（native_step_reported），不是供应商发票或新价格估算。缺失、零成本、非有限/负值均 unknown；不注入 demo 成本或补造价格。固定六个结构场景和顺序为 model-cost-v1；成对数值记录必须覆盖全部场景并具有相同成功结果，缺记录/失败不计节省率。外部输入仅标 reported_measurements，不宣称独立核实计费。真实 provider 基准需另行授权，不保留 60% 断言。
