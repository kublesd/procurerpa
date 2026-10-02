# 项目进度

> 最后更新：2026-10-02 +08:00
>
> 本文件是当前目标、活动任务、最新证据、阻塞和下一步的唯一事实源。能力映射与版本二开发差距见 `docs/procurement_completion_gap.md`，历史阶段契约见 `docs/procurement_rpa_development_guide.md`，重大取舍见 `DECISIONS.md`。

## 当前目标

当前活动任务：无。`REVIEW-FIX-01` 已完成四项 review 修复及相关本地回归，直接证据见文末。以下为本轮已关闭范围；不自动领取其他任务。

- 完成定义：凭据输入同时校验顶层页面与目标 frame；企业浏览器上下文不采集本地 HAR/录像/控制台正文；Unicode JSON 转义不能绕过已知凭据掩码；非法表格抽取不被原生 filler 补成成功空结果。
- 范围：对应凭据输入、浏览器创建、掩码、Skill schema 及针对性测试和本文；保留开工前全部未提交修改。
- 范围外：历史文件/数据清理、新依赖、真实凭据/模型/供应商调用、生产迁移、commit/push/分支/部署及其他债务。
- 最小验证：四项失败回归及修复后正反例、相关报价/Skill/秘密回归、改动 Python Ruff、git diff --check 和本轮文件边界核对；外部边界仅用合成替身。
- 停止条件：四项修复与最小验证完成后停止，真实浏览器和外部服务未验证须明确保留。

阶段 5 `MODEL-COST-01` 工程验收已完成，历史直接证据见文末；真实 provider 成对计费基准未运行，不声明节省率。以下阶段 5 范围为已关闭任务记录。

- 完成定义：复用原生 scrape 的当前步骤结构信号选择已注册模型，脱敏路由审计可追溯到 Step；Dashboard 展示受权 PostgreSQL 用量/成本与 Redis 缓存状态，固定样本比较可重复且未知成本不伪造节省率。
- 范围：既有模型路由、原生 action 决策接点、成本统计/API/前端、相关测试和固定基准入口，以及必要状态/能力/简历文档；保留开始前所有未提交修改。
- 范围外：新增抓取/模型调用、保存原始 DOM、第二运行时、新依赖、真实模型/供应商/凭据、生产/外部写入、commit/push/分支/部署及无关修改。
- 最小验证：运行时特征/注册 key/缓存隔离与故障回源、安全审计和成本未知正反例、组织/部门/品类权限、固定样本重复比较、相关前后端回归、TypeScript/Ruff/git diff --check；必要数据库路径使用隔离合成数据。
- 开工选择：特征仅在已有 scrape 后、当前 extract-actions 调用前存活，缺失时保留静态路由；基准样本预先固定，离线工程证据与真实 provider 成本分开，无实调授权不声称 60% 或生产节省率。
- 停止条件：上述工程验收通过即停止；外部量化证据缺失明确保留，不自动调用真实 provider 或扩展生产范围。

阶段 4 历史完成范围：

- 完成定义：七个 Skill 映射到既有原生执行能力，六个历史模板通过同一安全编译/原生执行契约，代表模板的启动、步骤、Artifact、安全审计与恢复可验证；凭据只用组织内原生引用且失效失败关闭，前端目录可操作，保留报价主链与确定性采购决定。
- 范围：enterprise 的 Planner/Skill/Workflow 接线、必要的原生安全边界、模板目录前端、相关单元/PostgreSQL/前端检查和状态文档。新增实现前先复用原生 Workflow；不建立第二浏览器或执行引擎。
- 范围外：阶段 5、真实凭据访问、真实模型/供应商调用、生产/外部写入、commit/push/分支/部署、无关工作区修改。
- 最小验证：六模板及七 Skill 编译、安全负例、原生入口/步骤证据/审计、跨组织及凭据失效、恢复和过期版本、报价回归、临时 PostgreSQL、前端检查、Ruff 与 git diff --check。
- 本轮继续授权：用户在上一轮明确列出两项待确认后回复“继续”，按已提出的原生 CredentialVaultService/组织内 credential_id/发起人或管理员显式执行/启动恢复重验/吊销与版本变化失败关闭方案推进，并只从当前 HEAD 恢复 block.py；仍不访问真实凭据或外部服务。
- 停止条件：阶段 4 全范围工程门达到；如存在未获得的必要授权或不可消除阻塞，准确记录，不宣称完成。

以下为上一轮无凭据报价切片的历史范围（其未接入描述已由本轮全范围接线替代）：

- 完成定义：`quote-task/v1` 从模板 API 复用原生采购链，table_extract 状态、Artifact 和安全审计可追溯，恢复不重复执行；六个历史登录模板在凭据未接入时失败关闭。
- 范围：workflow/采购路由、Skill 编译边界、quote-state 步骤投影、相关单元/PostgreSQL 检查及状态/能力/重大决策文档；保留开始前全部修改与 block.py 删除。
- 范围外：登录和凭据解析、六个历史模板完整业务执行、第二浏览器运行时、新引擎/依赖/迁移、前端、阶段 5、真实模型/供应商调用、commit/push/部署。
- 最小验证：模板入口接线、凭据失败关闭、步骤/Artifact/人工处置/审计事务、跨组织/过期版本回归、临时 PostgreSQL、改动 Python Ruff、git diff --check。
- 停止条件：代表切片工程门达到即停止；凭据提供方/运行身份/轮换吊销仍待独立确认，不宣称 SKILL-01 全范围完成。

以下为阶段 4 首个切片授权与验收范围（用户授权“开始开发阶段4”，并确认“采用受限 Planner（推荐）”）：

- 完成定义：以真实 quote-task 为首个切片，受限计划驱动原生 Task 和确定性报价校验，数据库恢复不重复完成步骤，replan 仅含未完成步骤，过期版本拒绝、执行歧义转人工。
- 范围：enterprise/agent 的受限 Planner、procurement 路由与 quote_state、相关单元/PostgreSQL 测试、状态/重大决策/能力文档及简历中 Planner 表述。保留本轮开始前全部阶段 1～3 修改及 block.py 删除。
- 状态所有者：原生 Task 拥有浏览器事实；TaskExtension 拥有权限上下文及独占 claim；coordination state 拥有安全计划及版本；Quote/Review/Approval 拥有业务事实。先持久计划，再提交 running/审计，调用原生执行器，最后同事务持久报价或核验/状态/审计。
- 范围外：SKILL-01（先完成本切片）、阶段 5、第二浏览器运行时、新工作流引擎、自动重放歧义动作、凭据读取、外部模型/供应商调用、生产操作、commit/push/部署。
- 最小验证：计划枚举与顺序/完成步骤排除/非法输出、安全 prompt、恢复及 CAS/权限/人工核验回归，临时 PostgreSQL 检查、改动 Python Ruff、git diff --check。
- 停止条件：首个真实切片工程门达到，或明确范围/授权边界；不宣称其他模板和通用 Planner 已统一。

以下为阶段 3 授权与验收范围（用户授权“开始开发阶段3”，并对模型/数据政策及预算/拆单来源均回复“你来决定”）：

- 完成定义：在 quote-task 真实入口复用规则预筛与受限模型复核，低风险跳过模型，失败不降低确定性风险，完成安全审计与隔离回归。
- 范围：风险检测、必要的采购入口和原生模型接线、相关测试与状态文档；保留开始前所有阶段 1/2 和文档修改及 `block.py` 删除。
- 授权后决定：仅使用已注册 Google Gemini `GEMINI_2.5_FLASH`，缺失不回退其他提供方；仅发送服务端生成的风险类别和等级枚举，不发送客户端说明、金额、供应商身份或页面正文。应用正文零持久化，禁用调用缓存/普通回调；只保留校验等级、服务端说明和安全审计。对这些非敏感枚举不额外要求提供方零保留，不宣称其账户保留期已核实。预算与拆单缺乏权威来源，本阶段明确保留为未实现。
- 范围外：阶段 4/5、新浏览器运行时、凭据访问、真实模型/供应商调用、生产操作、commit/push/部署；不虚构预算/拆单事实或 `70%` 指标。
- 最小验证：规则跳过、上下文 allowlist、输出校验与失败下限、跨组织/敏感字段/超限负例、真实入口安全审计回归、改动文件 Ruff 与 git diff --check。
- 本次直接观察（Windows PowerShell）：smoke-task 与 quote-task 均仅调用 `detect_risk(payload.risk.to_context())`；现有 detector 支持可选 callable，但把客户端 `redacted_description` 直接拼入 prompt，仅有名称不能证明脱敏。现有风险输入未提供预算或关联申请权威事实。
- 停止条件：一条真实入口工程验收完成，或触及明确数据/授权边界。不自动进入阶段 4。

以下为阶段 2 授权与验收范围（已完成，证据见后文）：

- 完成定义：真实 quote-task 在原生 Skyvern 解析/有限重试之后，执行封闭规范化及 Pydantic/Decimal/Artifact 校验；非法结果或原生重试耗尽进入既有持久人工核验。
- 范围：采购抽取边界、必要的共享解析清理、相关报价/人工核验测试和本文；重大取舍追加 DECISIONS.md。保留全部开始前修改，包括阶段 1 未提交实现与 block.py 删除。
- 已确认政策：用户选择仅规范大小写和首尾空格；仅 unit/CNY，无币种别名、单位换算或汇率换算，未知值严格拒绝。
- 范围外：阶段 3～5、第二套 retry/浏览器状态机、新依赖、真实模型/供应商 smoke、凭据访问、生产操作、commit/push/部署。
- 最小验证：真实调用边界的结构错误/Markdown/封闭规范化/未知值/Decimal/Artifact、原生有限重试与耗尽、持久人工处置回归、改动文件 Ruff、git diff --check。
- 停止条件：本阶段工程完成门达到或明确授权/环境边界；不自动领取阶段 3。

以下为阶段 1 授权及验收范围（已完成，证据见后文）：

- 完成定义：生产采购入口持久化版本化审批路由与快照，审批决定提交后通过组织隔离 Redis 通知请求人工作台，数据库复核与故障轮询保持显式 continue。
- 实现范围：审批、采购接线、对应模型迁移、工作台与相关测试；更新本文。保留既有四份文档修改及 `block.py` 删除。
- 范围外：阶段 2～5、多级会签、新消息平台、真实采购/供应商/LLM 调用、生产数据库、凭据访问、commit/push/部署。
- 最小验证：金额边界、路由与权限负例、快照及旧记录、事务后通知/隔离/回退、并发 continue 回归、迁移、前端测试、Ruff、`git diff --check`；环境未能执行的检查如实记录。
- 停止条件：阶段 1 完成门达到或遇到明确授权/环境边界，绝不自动领取阶段 2。

以下为阶段 0 冻结契约（历史）：

- 完成定义：冻结生产审批创建调用图、失败复现、现状基线和阶段 1 的完整策略输入，使实现不再猜测业务政策。
- 批准路径：阶段 0 只修改 `PROGRESS.md`、`DECISIONS.md`、`docs/procurement_completion_gap.md` 和 `docs/resume_guide.md`；只读检查 `enterprise/approval/`、`enterprise/procurement/routes.py`、现有迁移、seed、Redis/实时通道与代表性审批测试。保留开始前已有的 `skyvern/forge/sdk/workflow/models/block.py` 删除。
- 范围外：业务代码、测试和迁移实现；多级会签、BPMN/规则平台、LLM 审批决定、新消息基础设施、真实数据库/浏览器/供应商调用、提交、推送和部署。
- 冻结策略：权威来源为版本化服务端常量，复用 `risk_keywords.py` 的 Decimal 阈值，不建配置平台；首版策略为 `approval-cny-v1`，生效时间 `2026-09-22T00:00:00Z`，只用于新建审批，旧记录不回填。仅支持 CNY；50,000 为 medium 审计阈值、100,000 为 high 审批阈值、1,000,000 为 critical 审批阈值。
- 路由输入：组织和角色来自服务端认证后数据库事实，部门与品类必须在同组织并经现有权限校验，金额使用请求边界校验后的 Decimal；客户端不得提交或覆盖策略版本、生效时间、命中阈值、路由结果和审批角色。
- 路由结果：high 由申请部门内具备目标品类授权的 approver 单级审批；critical 由同组织 `department_code=COMPLIANCE` 部门内具备目标品类授权的 approver 单级审批。合规部门缺失、重复、无合格 approver 或跨组织时失败关闭，不回退申请部门；不增加财务会签、风险通知或多级审批。
- 执行方式：批准/拒绝先提交 PostgreSQL，再向组织隔离的 Redis Pub/Sub channel 发布只含 approval ID、状态和安全主体 ID 的通知；请求人工作台通过受权 long-poll 消费事件并重新读取数据库事实。Redis 不是审批事实源，事件不得携带金额、备注或采购正文；丢事件/Redis 故障不得回滚已提交决定或触发采购动作，客户端回退数据库轮询。批准后仍由发起人显式 continue。
- RED 基线：`quote-task`/`smoke-task` 调用 `detect_risk` 后由 `_attach_procurement_context` 创建审批；该函数未调用 `route_approval`，而是将 high 和 critical 都写为申请部门。PowerShell 静态契约探针退出码 `1`。审批表也尚无 category、金额、阈值、策略版本或生效时间快照。
- 阶段 1 最小验证：边界金额与 high/critical 路由；缺失/重复合规部门失败关闭；客户端策略字段不可写；跨组织、跨部门、跨品类、自批、重复决定和并发 continue；Pub/Sub 仅在事务提交后发布、跨组织订阅拒绝、消费者重新读库、事件丢失/Redis 故障回退轮询且不自动执行；迁移升级/降级、旧记录兼容、相关后端/前端测试、Ruff 和 `git diff --check`。
- 停止条件：阶段 0 决策和证据写入并验证后停止；不自动进入阶段 1。

以下为已完成 STATE-01 记录：quote-task 状态/事务切片已达到本轮工程完成门；其他模板/Coordinator/Workflow 的统一仍保留，不宣称 STATE-01 全范围完成。

- 完成定义：同一 task_id 的固定报价模板实例、计划、当前步骤及版本可从数据库恢复，过期更新被拒绝，企业状态与业务写入及审计同事务成功或回滚。
- 范围：报价创建/恢复/报价入库/人工核验、对应审批决定、复用 coordination state 表、相关测试及状态文档；保留开始时所有既有修改和 block.py 删除。
- 状态所有者与顺序：原生 Task 拥有浏览器执行事实；TaskExtension 拥有租户/风险上下文；现有 coordination state 拥有企业步骤/版本；Approval/Review/Quote 拥有业务事实。先提交企业上下文，再原子提交 running 标记/企业步骤/审计，再调用原生执行器，最后原子提交报价或人工核验/步骤/审计。
- 并发与旧数据：保留 RUN-01 独占 claim；coordination state 使用 version CAS；旧记录不批量回填，在第一次合法报价状态变更时创建固定计划。只保存 task_id 输入引用，不复制 URL、页面正文或用户参数。
- 范围外：其他模板/Coordinator/demo 运行链统一、原生 executor 改写、页面自动重放、新工作流引擎、真实 smoke、提交/推送/部署。
- 最小验证：相关采购/审批单元回归；临时 PostgreSQL 重启、版本冲突、事务失败与租户隔离；Ruff、git diff --check。
- 停止条件：本报价切片工程验收通过即停止；其余模板/Coordinator 链明确保留为 STATE-01 后续范围。

以下为已完成 RUN-01 记录：

- 完成定义：两个报价入口共用数据库独占 claim；执行前可启动、完成后可补入库、执行中歧义态持久转人工，重启与并发不重复执行或报价。
- 范围：采购/审批路由、相关单元测试、临时 PostgreSQL 恢复检查、本文与重大取舍记录；必要时更新 RUN-01 契约状态。保留所有既有工作区修改，包括 block.py 删除。
- 范围外：通用队列、自动浏览器动作重放、其他债务、真实 smoke、提交/推送、部署及真实采购数据。
- 最小验证：两个入口回归、执行前/中/后中断与租户/审批隔离、临时 PostgreSQL 跨进程锁释放、Ruff 与 git diff --check。
- claim 决策：复用 TaskExtension 行锁直到执行/后处理结束，连接退出释放；不按时间强抢存活执行者。Task.running 在调用执行器前持久化，遗留 running/queued 不重放，只进入现有人工核验。恢复由显式重试触发。
- 停止条件：上述工程门通过即停止；环境阻碍的验证据实保留，不扩展到新消息基础设施或真实 smoke。

以下为上一轮债务契约整理记录：

- 完成定义：每项剩余债务都有唯一 ID、目标、范围外、开工前决策、可观察验收、代表性验证和停止条件；真实 smoke 明确不属于完成门。
- 范围：仅 `docs/procurement_completion_gap.md` 与 `PROGRESS.md`。范围外：业务代码、迁移、测试实现、债务排序、真实 smoke、部署、提交及其他工作区修改。
- 最小验证：债务契约完整性、本地 Markdown 链接、harness validator、批准路径检查和 `git diff --check`。

此前完成的任务是收口审批报价后处理和采购请求幂等性，当时修改范围仅限：

- `alembic/versions/2026_09_21_0011_procurement_runtime_reliability.py`
- `enterprise/auth/models.py`
- `enterprise/procurement/models.py`
- `enterprise/procurement/routes.py`
- `enterprise/approval/routes.py`
- `tests/unit/test_auth_models.py`
- `tests/unit/test_day_1_smoke_security.py`
- `tests/unit/test_day_10_quotes.py`
- `tests/unit/test_day_11_quotes.py`
- `tests/unit/test_procurement_review_regressions.py`
- `DECISIONS.md`
- `PROGRESS.md`

上一轮代码证据：114 项相关隔离检查、改动 Python 文件 Ruff、`alembic heads` 和 `git diff --check` 通过。真实数据库迁移未执行，真实 smoke 不属于完成条件。本轮 RUN-01 证据见文末。

## 当前仓库事实

- 2026-09-11 本轮开始时直接观察：`main` 指向 `9d078c0be9569e2c7401250c2127be6e5e1a5e35`；仓库历史已重写，旧标签 `c4b2e3f` 和旧开发分支不再可解析，不能作为当前 revision 证据。
- 迁移源码直接观察：企业迁移链当前 head 为 `ent_011`；当前运行数据库 revision 未在本轮验证，需执行 `alembic current` 才能声明。
- 现有真实采购主链继续保留：受控供应商页 → procurement API → 原生 Skyvern Task/Artifact → SupplierQuote → Decimal 比价 → 工作台/审批/审计/PostgreSQL Dashboard。
- 本轮开始前已有用户工作区修改：`skyvern/forge/sdk/workflow/models/block.py` 处于删除状态；不属于 harness 任务，必须保留且不得恢复、覆盖或纳入结论。

## 路线状态

| 路线 | 状态 | 证据边界 |
| --- | --- | --- |
| P1～P6 采购语义功能对等 | 历史记录为已完成 | 包含明确标记的 demo/simulated/not_connected 路径；不代表生产真实链 |
| S1～S8 逐项真实化 | 历史记录为已完成各自工程门 | 本轮未重新运行应用测试；不得把历史结果写成本次结果 |
| S9 安全硬化与 SIT | 历史记录为已完成工程门 | 真实 quotes/controls smoke 不再属于完成条件 |

项目当前按已有工程证据认定完成。真实 quotes 与 controls smoke 已从验收范围移除；历史运行结果继续按来源保留，但不得把未运行或失败记录写成通过。

## 最近可用历史证据

以下均来自 2026-08-06～2026-08-09 的历史记录，不是本轮重跑：

- 主机 unit：`517 passed, 300 warnings`；容器 unit：`518 passed, 302 warnings`。
- `tests/integration/test_e2e_flow.py`：`39 passed, 6 warnings`。
- 前端：`15 files / 93 tests`，生产 build 通过。
- Compose 标准 Skyvern/UI 镜像、PostgreSQL/Redis/MinIO 健康、`ent_010` 迁移与重启一致性曾通过。
- `controls` 历史当前源码 smoke 曾通过：批准后 Task completed，拒绝后 canceled，并包含 PDF/MinIO Artifact 与审计证据。
- `quotes` 在日志修复前曾通过；日志修复后的两次运行均因 Gemini `RateLimitError` 进入 `needs_human`，因此当前对应真实 smoke 只能标记为 `unverified`。
- S5 真实 smoke 曾由用户报告通过但未提供新的 Task/Artifact ID；该项保留为“用户报告”，不是独立直接观察。

## 环境限制与非验收项

- 本机 `.venv` 来自旧机器路径，系统 Python 依赖也可能不完整；应用验证优先使用已配置 Compose，或在明确任务中重建环境。
- 全量 Ruff 存在历史 agent/skills/workflows/demo/SIT 问题；没有当前应用改动时不顺带修复。
- Day 14 诊断产生的历史失败/待处理演示记录仍在数据库中；未经单独破坏性数据授权不得清理。

真实 smoke、外部 Gemini 可用性及数据库/浏览器联调均不是当前项目阻塞或默认下一步。

## 版本二开发差距

详细契约由 `docs/procurement_completion_gap.md` 负责，当前摘要为：

- `AI-RISK-01`：阶段 3 已接通 quote-task 的受限枚举风险复核与安全审计；预算/拆单、丰富上下文和真实调用避免率仍保留，`70%` 断言已移除。
- `LLM-RESILIENCE-01`：阶段 2 工程门已通过；仅 unit/CNY 的大小写/空白规范化，复用原生重试与持久人工核验。历史默认值与上游浮点数据不回填，真实模型/浏览器 smoke 未运行。
- `PLANNER-01`：quote-task 与六模板共享受限枚举计划；原生每步执行前核对剩余计划，完成后只规划未完成后缀，模型失败回退确定性链。幂等、CAS、显式恢复与歧义转人工接通；自由任务分解和通用浏览器断点续跑保留为未实现。
- `SKILL-01`：七 Skill 原生映射、六模板安全编译/入口、组织内凭据引用、逐步 Task/Artifact/事务审计与目录/实例/恢复/终止界面已接通。代表模板在合成受控 PostgreSQL 场景验收；真实 vault/browser/provider smoke 未运行。quote-task/v1 保留原采购链，人工结果仍标记 manual_completed。
- `MODEL-COST-01`：以运行时特征驱动三档模型并把真实 cache/token/cost 指标接入前端；`60%` 必须实测。
- `APPROVAL-01`：在四维权限下持久化确定性金额/品类/策略路由；继续使用显式 continue，除非新决策明确取代它。

这些差距都不是自动排期。实施前必须在本文件建立一个有范围、验收、验证、授权边界和停止条件的活动任务。

## 既有 harness 证据（历史）

- 来源：本次直接观察。
- 修订与环境：`main@9d078c0be9569e2c7401250c2127be6e5e1a5e35`；Windows PowerShell；仅文档修改。
- 中间检查：4 个职责文档的本地 Markdown 链接通过；harness validator 退出码 `0`，仅给出 `discovery_incomplete` 和 `reuse_existing_owners` 建议。
- 最终验证：5 个批准文档的本地 Markdown 链接检查通过；harness validator 退出码 `0`，仅保留两项非阻塞建议；过期领取语句搜索无命中；`git diff --check` 退出码 `0`，只有 LF→CRLF 工作区提示。
- 批准边界：`git status --short` 只显示 5 个批准文档被修改，以及任务开始前已有的 `skyvern/forge/sdk/workflow/models/block.py` 删除。
- 范围外状态：预先存在的 `skyvern/forge/sdk/workflow/models/block.py` 删除保持不变。

## 下一步

1. 阶段 5 工程验收已完成，活动任务关闭；最新直接证据见文末，不自动领取其他开发工作。
2. 生产迁移与部署、真实凭据/供应商/model smoke 均未授权，不自动领取或执行。
3. 自由任务分解、TOTP/浏览器配置、视觉与二进制证据、预算/拆单权威集成和真实量化收益保留；真实 smoke 不作为默认工程完成门，简历不保留未经实测的 `70%`/`60%`。

## 2026-09-26 阶段 2 / LLM-RESILIENCE-01 实现证据

- 授权与来源：用户“开始开发阶段2”，确认仅规范 unit/CNY 大小写和首尾空格，随后“继续”。以下为本任务直接观察（含 09-22 初始复现、09-26 续接验证），不是历史 smoke。修订为 `main@4c86636` 工作区。
- 修改文件：`enterprise/procurement/routes.py`、`enterprise/llm/resilient_caller.py`（仅边界说明）、`skyvern/forge/sdk/api/llm/schema_validator.py`、`tests/unit/test_day_11_quotes.py`、`tests/integration/test_llm_resilience01.py`（新）、`tests/integration/test_run01_recovery.py`（仅允许备用本地测试端口）、`PROGRESS.md`、`DECISIONS.md`。保留全部已有阶段 1、文档修改及 `block.py` 删除；未改审批、前端、迁移或其他原生执行逻辑。
- 实现：报价对象及完整 Markdown/JSON 字符串进入同一 Pydantic 校验；仅规范 unit/CNY，未知单位/币种、额外字段、非法数值/结构仍拒绝并持久转人工。JSON 小数以标准库 `parse_float=Decimal` 解析，验证 `1.0049999999999999999` 按金额规则落为 `1.00`；清理与规范化不改写原候选对象。保留置信度、Artifact、组织/部门/品类校验与既有事务/独占 claim。
- 必要原生修改：新固定报价 schema 携带 `x-skyvern-preserve-missing=true`，原生 schema filler 将候选交回调用方验证，不再为报价缺失价格/运费/交期等补 0，也不在该 filler 分支记录候选验证正文。其他 schema 原有默认值行为保持。恢复识别新旧固定 schema；旧事实不回填。
- 原生能力盘点：`extract_information_for_navigation_goal` 使用任务 schema 和原生 LLM handler；`parse_api_response` 已处理 Markdown/JSON；router 使用配置的 `num_retries/retry_delay_seconds`；`ForgeAgent.handle_failed_step` 按组织或默认上限递增 retry_index，耗尽置 failed。企业层不新增重试包装器；失败仍经 `recover_quote_task` 进入 Review，显式人工处置后不重放浏览器。demo retry 有现存 demo/测试调用方，继续隔离，生产只复用纯 Markdown cleaner。
- RED 与过程发现：初始真实入库边界测试为 **2 failed, 1 passed**，证明大小写/空格及 Markdown 候选不能通过；修复后通过。单独精度探针观察到 Pydantic JSON Decimal 将 `0.1000000000000000001` 解析为 `0.1`，因此改用标准库 Decimal 解析并加入金额舍入回归。
- 验证环境：Windows PowerShell、Python 3.12.4，复用 `.venv/Lib/site-packages`，未安装依赖；禁用 dotenv 与 pytest 自动插件加载，显式加载 pytest-asyncio，并替换 executor factory 导入边界以避开既有 `block.py` 删除。测试均用合成数据，无真实模型/供应商调用；后续原生解析测试设置 `LITELLM_LOCAL_MODEL_COST_MAP=True` 使用本地模型元数据。
- 单元回归：`test_day_11_quotes.py`、`test_procurement_review_regressions.py`、`test_s1_human_reviews.py`、`test_day_10_quotes.py` 最终 **70 passed, 52 warnings**；`test_llm_resilience.py`、`test_approval_routes.py`、`test_day_1_smoke_security.py` **78 passed, 9 warnings**。合计 **148 passed**，先前 69 项运行是精度回归新增前的中间结果，不重复累计。
- PostgreSQL：Docker 29.6.2、一次性 `postgres:14.23-alpine3.23`、只绑定 `127.0.0.1:15439`、无宿主挂载/真实数据。`test_llm_resilience01.py` 与 `test_state01_transactions.py` 合计 **16 passed, 423 warnings**；最后 JSON Decimal 修改及精度断言强化后，入库两例定向复验 **2 passed, 7 deselected**，不重复计数。覆盖缺字段、未知币种、结构/Artifact 失败、持久 Review、重连、隔离、三种人工处置、幂等及事务回归。
- 重试证据边界：测试从当前 `ForgeAgent` 源码 AST 提取未改写的 `handle_failed_step` 方法，以受控 browser/summary/step 依赖执行两次有限重试并把 failed 写入临时 PostgreSQL，再执行真实企业恢复/人工处置；不是完整 ForgeAgent/provider/浏览器联调，也不是新的生产执行器。
- 环境过程：续接时旧测试进程不可查询，未将其认定成功；Docker 引擎未运行，默认安装路径启动失败，读取安装位置后从 `E:/Docker/app` 启动。55439 位于 Windows TCP 保留区，容器启动失败；测试 helper 增加固定备用 15439 后成功，不改变宿主端口保留或防火墙配置。
- 最终检查：6 份本轮 Python 文件 Ruff 通过，`git diff --check` 通过；工作区新增路径与上述范围一致。临时数据库 schema 数量最终为 0；本任务测试容器已停止并自动删除，保留既有应用容器。
- 未验证与保留：未运行真实 LLM/浏览器/供应商 smoke、完整原生运行时、全量应用/前端或生产迁移；通用原生 provider/Artifact 的响应处理未全面审计。旧任务已补的默认值和已转为浮点的上游数字不可逆，不宣称恢复精度或回填历史。无汇率/包装单位换算；其他阶段与 demo 路径保持原边界。
- 停止原因：本阶段约定工程完成门满足，无活动任务；不进入阶段 3，不 commit/push/部署。

## 2026-09-22 阶段 1 / APPROVAL-01 实现证据

- 授权与来源：用户明确“开始开发阶段1”；以下均为本次直接观察。修订 `main@4c86636` 工作区；保留开始前四份文档修改和 `skyvern/forge/sdk/workflow/models/block.py` 删除。本次只续写 `PROGRESS.md`，未改写另三份已有文档。
- 实现结果：生产 `_attach_procurement_context` 调用服务端路由解析；high 使用申请部门、critical 使用同组织唯一有效 `COMPLIANCE` 部门，均要求非申请人、有效、具备目标品类授权的 approver。缺失/重复/无人合格失败关闭，创建失败取消新建原生孤立 Task。策略为 `approval-cny-v1`，金额/币种/命中金额阈值/品类/策略版本/生效时间持久化；非金额风险的命中金额阈值可为 null。客户端策略字段拒绝写入。
- 权限与兼容：新策略审批只接受快照目标部门/品类 approver，管理员不能绕过该策略；旧审批无快照、不回填，继续读取 TaskExtension 品类和既有管理员授权。GET/long-poll 均校验组织与请求人/审批人可见范围，等待结束再次从数据库加载用户权限并读取审批。原有显式 continue 与独占 claim 保留。
- 通知与工作台：PostgreSQL 提交后发布组织及 approval 隔离 Redis channel；消息仅有 approval ID、状态、安全 actor ID。long-poll 不解析消息正文、不改变业务状态，超时/Redis 故障重新读库；工作台通知接口失败回退 GET 轮询，只有点击“继续已批准任务”才执行。旧 `pubsub.py` 标明 legacy simulated/not_connected，不接生产运行链。
- 修改文件（后端）：`enterprise/approval/models.py`、`policy.py`（新）、`routing.py`、`routes.py`、`notifications.py`（新）、`pubsub.py`；`enterprise/procurement/routes.py`；`alembic/versions/2026_09_22_0012_approval_policy.py`（新）；真实调用方契约变化同步到 `scripts/demo_procurement_parity.py`。
- 修改文件（前端）：`skyvern-frontend/src/routes/enterprise/procurement/ProcurementWorkbenchPage.tsx`、`src/components/enterprise/StatusBadge.tsx`、`src/i18n/locales.ts`、`src/__tests__/ProcurementWorkbenchPage.test.tsx`（后三项相对 skyvern-frontend）。
- 修改文件（后端测试）：`tests/unit/test_approval_policy.py`（新）、`test_day_1_smoke_security.py`、`test_risk_detector.py`；`tests/integration/test_approval01.py`（新）、`test_state01_transactions.py`、`test_e2e_flow.py`（各组内文件相对对应 tests 目录）。
- 实际环境：Windows PowerShell；Python 3.12.4，复用 `.venv/Lib/site-packages` 既有 pytest 8.4.2/SQLAlchemy 2.0.51/Pydantic 2.13.4；Docker 29.6.2；临时 `postgres:14.23-alpine3.23` 与 `redis:7.4.9-alpine3.21` 容器，只监听 localhost 55439/56379、无宿主挂载、合成数据。不读取 .env 或真实凭据，不新增依赖。
- 后端隔离验证：审批策略/模型/路由/PubSub、风险检测、Day 1/10/11、采购回归、P1 和 `test_e2e_flow.py` 合计 **185 passed, 11 warnings**。临时启动器禁用 dotenv 与插件自动加载，只替换原生 executor factory 导入边界；真实路由、模型、Decimal 与审计逻辑均加载，原生浏览器由受控替身代替。
- PostgreSQL/Redis 验证：`test_approval01.py` 首轮 **14 passed**，覆盖持久快照/重连、合规配置负例、决定提交顺序、跨组织订阅、数据库复核、重复/并发决定、真实 Redis 隔离与安全消息、新迁移升级/降级/旧记录保留；随后补充回滚不发布、并发 continue，并加强真实 Redis long-poll 消费检查，定向运行 **3 passed, 13 deselected**。该文件最终 16 个用例均已有本次通过证据（其中一个强化后重跑），不把两批重复项叠加为独立用例数。
- 事务回归：`test_day_1_smoke_security.py` 与 `test_state01_transactions.py` 合并运行 **19 passed, 179 warnings**，包含真实临时 PostgreSQL 的上下文/审批/审计回滚；既有测试 fixture 补齐新策略必需 approver/品类授权。临时并发 continue 检查证明一次执行、一条报价、竞争请求 409。
- 前端验证：工作台 Vitest **1 file / 5 tests passed**（正常报价、错误态、审批通知、GET 回退、拒绝与不自动继续）；`npm run build` 通过，保留 Browserslist 过期、既有 Tailwind 歧义类名和大 bundle 警告。
- 静态/迁移验证：`alembic heads` 输出唯一 `ent_012 (head)`；新迁移在临时 PostgreSQL fixture schema 实际升降级，非生产库；改动后端/迁移/测试 Ruff 通过。兼容 demo 脚本有既有 I001，通过 `git show HEAD:scripts/demo_procurement_parity.py | ruff check --stdin-filename ... -` 复现同一问题，未顺带排序其历史导入。`git diff --check` 通过，仅有 LF→CRLF 提示。
- 失败与修正：初次旧路由测试仍假定全局合规 ID、旧 Session 替身缺少资格查询接口，均按新契约更新后通过；快照测试改用 Decimal 数值比较（PostgreSQL 可返回指数表示）；前端增加审批状态中文标签。历史成功未代替本轮证据。
- 未验证与保留债务：未运行全量应用测试、真实浏览器/供应商/LLM smoke 或生产迁移/部署；既有 block.py 删除仍影响标准原生 executor 导入。采购 seed 的 COMPLIANCE/品类 approver 配置未写入，缺配置将明确拒绝 critical 请求；工作台保持原有页面会话任务列表，跨页面恢复任务列表不属于本阶段。旧 simulated Pub/Sub helper 只保留兼容；不承诺 Redis 消息可靠投递或自动续跑。
- 收尾：批准路径白名单检查通过；本轮两个 `--rm` 临时测试容器已停止并自动移除，临时隔离启动器已删除；原有工作区修改和 block.py 删除保留。
- 停止原因：阶段 1 工程完成门达到；无活动任务，不自动开始阶段 2，不 commit/push/部署。

## 2026-09-22 阶段 0 / APPROVAL-01 冻结证据

- 授权与范围：用户启动阶段 0，并授权依据版本二简历目标代为决定审批策略；只修改 `PROGRESS.md`、`DECISIONS.md`、`docs/procurement_completion_gap.md` 和 `docs/resume_guide.md`，没有业务实现授权。
- 来源与环境：本次直接观察 `main@4c86636`；Windows PowerShell。读取生产采购/审批调用方、审批模型与迁移、采购 seed、代表性审批测试、版本二简历和安全规则。
- 调用图与 RED：`quote-task`/`smoke-task` → `detect_risk` → `_attach_procurement_context`；生产创建链未调用 `route_approval`，high/critical 均硬编码申请部门。静态契约探针实际退出码 `1`，审批表缺少 category、金额、阈值、策略版本和生效时间快照。
- 决策结果：冻结 `approval-cny-v1`、CNY Decimal 阈值、high 本部门品类 approver、critical 同组织 `COMPLIANCE` 部门品类 approver、缺失配置失败关闭，以及 PostgreSQL 权威状态 + Redis Pub/Sub 实时通知 + 请求人显式 continue；不引入多级会签或让易失事件决定采购动作。
- 纠正记录：曾误把目标简历当成当前能力声明并删除 `Redis Pub/Sub`；用户澄清简历是开发目标后已恢复原文，并把真实生产发布、消费、鉴权、数据库复核和故障回退纳入阶段 1 完成门。
- 实际验证：PowerShell 策略字段与重大决策检查通过；版本二简历保留 `Redis Pub/Sub` 目标；四份批准文档本地 Markdown 链接通过；`git diff --check` 退出码 `0`，仅有 LF→CRLF 工作区提示。
- 未验证：阶段 0 未修改或运行应用代码、迁移、pytest、Ruff、数据库、浏览器、前端或外部服务；阶段 1 的 RED/GREEN 和集成验证尚未开始。
- 保留债务与边界：生产路由、持久快照、事务后 publish、受权 long-poll 消费者和前端回退仍未实现；当前采购 seed 尚无 `COMPLIANCE` 部门和对应 approver。开始前已有的 `block.py` 删除保持不变。
- 停止原因：阶段 0 完成门已达到；按阶段契约停止，等待用户单独授权阶段 1。

## 2026-09-22 版本二差距契约替换证据

- 授权与范围：用户要求把版本二实现差距写入 harness 作为开发指导，并先移除当前旧债务清单；仅修改 `docs/procurement_completion_gap.md` 与 `PROGRESS.md`，未授权业务实现。
- 来源与环境：本次直接观察 `main@4c86636`；Windows PowerShell。依据真实调用方确认风险 LLM、容错 helper、Planner/Coordinator、Skill Pipeline、模型路由/成本和审批路由的接入边界。
- 结构结果：旧可领取契约从当前差距文档移除，替换为 `AI-RISK-01`、`LLM-RESILIENCE-01`、`PLANNER-01`、`SKILL-01`、`MODEL-COST-01`、`APPROVAL-01` 六项；每项均包含当前差距、目标与范围、范围外、开工前决定、可观察验收、代表性验证与停止。
- 设计边界：每项允许“真实主链接通”或“收缩简历表述”两种出口；不以新增 demo 关闭差距，不为匹配简历恢复已否决的 Redis 阻塞审批或第二套浏览器运行时，`70%`、`60%` 必须来自可复现测量。
- 实际验证：PowerShell 契约结构检查通过（6 项 × 6 个必需字段）；旧契约 ID 在当前差距文档无命中；两份改动文档的本地 Markdown 链接通过；`git diff --check` 退出码 `0`，仅有 LF→CRLF 工作区提示。
- 未验证：harness validator 未运行；系统 Python 是不可执行的 Windows App Alias（退出码 `9009`），`.venv` 指向旧用户目录（退出码 `103`），`py`/WSL 无可用 Python，Docker daemon 不可用。文档任务未运行应用、数据库、浏览器、前端或外部模型测试。
- 批准边界与停止：最终工作区只新增两份批准文档修改，并保留开始前已有的 `skyvern/forge/sdk/workflow/models/block.py` 删除。文档完成门已达到，停止，不自动领取六项中的任何实现任务。

## 2026-09-22 版本二分阶段开发指导证据

- 授权与范围：用户要求在现有文档内补充分阶段开发指导；继续只修改 `docs/procurement_completion_gap.md` 与 `PROGRESS.md`，未授权业务实现。
- 阶段设计：阶段 0 冻结证据与人工决定；阶段 1 完成 `APPROVAL-01`；阶段 2 完成 `LLM-RESILIENCE-01`；阶段 3 完成 `AI-RISK-01`；阶段 4 依次完成 `PLANNER-01`、`SKILL-01`；阶段 5 完成 `MODEL-COST-01` 和量化证据。
- 控制边界：每阶段定义入口门和完成门，执行统一使用 RED→GREEN→REFACTOR→VERIFY→HANDOFF；一次只允许一个活动差距，阶段完成后停止，外部/高风险边界变化时单独申请授权。
- 实际验证：PowerShell 检查确认阶段 0～5、六项 ID 映射、入口/完成门、执行循环和中止规则完整；两份文档本地 Markdown 链接通过；`git diff --check` 退出码 `0`，仅有 LF→CRLF 工作区提示。
- 未验证：harness validator 因系统 Python 仍为不可执行 Windows App Alias 未启动（退出码 `9009`）；未运行应用、数据库、浏览器、前端或外部模型测试。
- 停止原因：分阶段指导写入完成后停止，不自动启动阶段 0 或 `APPROVAL-01`。

## 2026-09-21 代码审查记录

- 用户授权：审查项目代码；完成定义为定位采购主链的可操作问题并给出验证证据。范围外：业务修复、提交、部署、真实采购和外部模型调用；不创建新的活动实现任务。
- 本次直接观察：采购写入校验复用读取可见范围，允许 A 部门 operator 在 B 部门仅有 viewer 或全组织只读权限时通过写入校验；高风险 quote-task 审批分支提前返回，continue 只启动原生 Task，未接报价入库；比价未校验物料一致性。
- 实际验证环境：Windows PowerShell、系统 Python 3.12.12。标准库隔离执行实际权限校验函数（数据库替身）复现两类越权；直接运行 comparison.py 复现 SSD 与纸张被一起排序并推荐纸张。审批缺少报价入库通过源码调用链及全仓调用搜索确认，未运行真实审批闭环。
- 验证限制：针对报价与审批的 pytest 命令因系统 Python 缺少 pytest 未能启动；Docker daemon 不可用，未运行容器、数据库、浏览器、前端或真实 quotes/controls smoke。历史测试结果未作为本次通过证据。
- 修改仅限本记录；业务问题保留待单独修复。既有 block.py 删除保持不变且排除审查；持久化等债务继续保留。
- 停止原因：本轮审查已形成有源码位置和验证边界的发现，不自动转入修复。最终 git diff --check 结果以本轮命令为准。

## 2026-09-21 三项审查修复证据

- 授权：用户在审查后明确要求“进行修复”，并要求继续；仅本地实现和验证，无提交/推送/部署或外部采购操作。
- 来源与修订：本次直接观察；`3c31bd708b68a03a140977c9b3036e8374e6148e` 工作区；Windows PowerShell、系统 Python 3.12.12，复用 `.venv/Lib/site-packages` 中 pytest 8.4.2 等已有依赖，未安装新依赖。
- 实现：将既有人工复核操作权限守卫推广到报价/任务写入；目标部门 operator + 品类授权或同组织管理员才能写入。审批继续从持久化 Task schema 和 TaskExtension 恢复报价上下文，原生执行完成后复用报价校验和入库，执行/提取失败转现有人工作业；重复 continue 仍返回 409，幂等请求从数据库读取已入库报价，并检查原 Task 可见范围。比价按物料名称（去首尾空白）、数量、单位、币种一致性校验，不一致返回 422，不生成推荐。
- 复现与验证：新增回归修复前 `4 failed`，准确复现两类只读越权、混合物料推荐、审批只执行不入库。修复后运行 `test_procurement_review_regressions.py`、`test_day_10_quotes.py`、`test_day_11_quotes.py`、`test_approval_routes.py`、`test_s1_human_reviews.py`、`test_day_1_smoke_security.py`、`test_day_4_procurement_isolation.py`、`test_p1_procurement_alignment.py`，结果 `54 passed, 15 warnings`（已有弃用警告）。
- 隔离方式：临时 Python 启动器加入已有 site-packages；禁用 pytest 插件自动加载，显式加载 pytest_asyncio；禁用 dotenv 文件读取；仅替换原生 executor factory 的导入边界，各测试显式注入执行器/数据库替身。实际采购/审批路由、Task service、SQLAlchemy 模型、Pydantic 校验和 Decimal 比价代码均加载；临时启动器验证后删除。此结果是隔离测试，不是实际浏览器执行或真实数据库持久化证明。
- 失败与限制：未隔离的三组 pytest 收集因既有 `skyvern/forge/sdk/workflow/models/block.py` 删除而失败；该删除未恢复。初次隔离还替换 Task service 导致一个原生创建测试不适用，随后撤去该替换并通过全部 54 项。未运行全量测试、前端、真实 PostgreSQL/浏览器、迁移或外部模型 smoke。
- 最终检查：`.venv/Scripts/ruff.exe check --no-cache` 对三个实现文件和新测试通过；`git diff --check` 通过，仅 LF→CRLF 提示；范围仅上述五个文件及原有 block.py 删除。
- 保留债务：审批后处理仍使用进程内 BackgroundTasks，崩溃恢复需要持久任务执行机制；报价模型尚无权威 SKU，当前使用严格物料名匹配，别名不会自动合并；原有内存幂等缓存等债务保留。
- 停止原因：授权的三项修复及可用环境内回归已完成，不扩展历史阶段或擅自恢复用户删除。

## 2026-09-21 运行可靠性修复证据

- 授权：用户要求处理第一项运行可靠性债务；仅本地实现和验证，无提交、部署、外部调用或真实数据库写入。
- 实现：报价审批 continue 请求内顺序执行原生任务、校验和报价入库/人工复核，不再把报价后处理交给响应后的 BackgroundTasks；已完成 Task 重试会从 Task、TaskExtension 和 SupplierQuote 恢复。`supplier_quotes.task_id` 唯一约束防止并发重复报价。smoke/quote 幂等键仅保存带用途前缀的 SHA-256 摘要，并通过 `(organization_id, request_key_hash)` 唯一约束在重启和多进程间复用。
- 迁移：新增 `ent_011`，为 `task_extensions` 增加可空 `request_key_hash`，并增加请求键和单 Task 报价唯一约束；`python -m alembic heads` 输出 `ent_011 (head)`。
- 验证：Windows PowerShell、系统 Python 3.12.12，复用 `.venv/Lib/site-packages`；隔离执行 9 个相关测试文件，结果 `114 passed, 23 warnings`；改动 Python 文件 Ruff、`alembic heads`、本地 Markdown 链接和 `git diff --check` 通过。
- 限制：既有 `block.py` 删除导致标准 pytest 收集失败，隔离启动器仅替换原生 executor factory 导入边界并在验证后删除。未执行真实 PostgreSQL `upgrade head`、浏览器、前端或外部模型调用；真实 smoke 不属于完成门。
- 保留债务：Skyvern 原生执行器在浏览器执行中途崩溃的自动续跑、新队列服务及其他已列债务均未实现。
- 停止原因：本项完成定义已达到；不扩展到原生执行器或下一项债务。

## 2026-09-22 债务契约文档证据

- 授权：用户要求把剩余债务写入文档指导开发；使用现有 harness，不创建新 roadmap 或活动实现任务。
- 来源与范围：本次直接观察 `enterprise/approval/routes.py`、`enterprise/procurement/`、`enterprise/agent/`、`enterprise/skills/`、`enterprise/workflows/`、`enterprise/llm/action_cache.py` 及对应单元测试入口；改动批准路径仅为 `docs/procurement_completion_gap.md`、`PROGRESS.md`。
- 结构：形成 7 项可领取债务契约和 2 项有条件候选项；每项写明责任边界、范围外、人工决策、可观察验收、代表性验证及停止条件。真实 smoke、外部模型配额和真实站点可用性明确排除。
- 验证：Windows PowerShell；7 份可领取契约的 5 个必备字段检查通过；2 份改动文档的本地 Markdown 链接通过；harness validator 退出码 `0`，保留 `discovery_incomplete`、`reuse_existing_owners` 建议和历史完成声明需人工复核的警告；全工作区 `git diff --check` 退出码 `0`，仅有 LF→CRLF 提示。按 harness-only 边界未运行应用测试、数据库、浏览器、前端或外部模型调用。
- 保留边界：债务未排序、未领取、未实现；既有业务代码和 `skyvern/forge/sdk/workflow/models/block.py` 删除保持不变。
- 停止原因：文档任务达到完成门后停止，等待用户选择单项债务。

## 2026-09-22 RUN-01 开发与直接验证证据

- 授权与来源：用户要求“进行run01债务的开发”；本次直接观察 `3c31bd7` 工作区，未提交、推送或部署。开始时已有 12 份 tracked 修改、block.py 删除和 2 份未跟踪文件；无关修改保留。
- 本轮修改文件：`enterprise/procurement/routes.py`、`enterprise/approval/routes.py`、`tests/unit/test_procurement_review_regressions.py`、`tests/unit/test_day_11_quotes.py`、新增 `tests/integration/test_run01_recovery.py`、`PROGRESS.md`、`DECISIONS.md`、`docs/procurement_completion_gap.md`。
- 实现：创建报价先 defer；持久上下文后，直接报价与审批 continue 共用数据库行锁。执行前提交 running 标记；created 可启动，completed 幂等补报价，中断/歧义状态建立持久人工核验。幂等请求可补低风险报价后处理；新增 `POST /api/v1/enterprise/procurement/tasks/{task_id}/recover-quote`，允许按现有 task_id 显式恢复。审批与组织/部门/品类写权限继续校验。
- 实际环境：Windows PowerShell、Python 3.12.12、现有 `.venv/Lib/site-packages`（pytest 8.4.2）；Docker Desktop、已安装 `postgres:14.23-alpine3.23` 镜像，临时容器 `procurerpa-run01-test` 仅监听 `127.0.0.1:55439`，无宿主挂载。无安装新依赖，无生产数据库/凭据访问。
- 最终检查：10 个测试文件合计 **134 passed, 130 warnings**（128 项单元检查 + 6 项 PostgreSQL 进程崩溃场景，74.60 秒）；5 份改动 Python 文件 Ruff 通过；`git diff --check` 通过，仅 LF→CRLF 提示。
- 数据库验证：使用实际模型及依赖表创建每例独立临时 schema，真实 PostgreSQL 约束/行锁/报价/人工核验/审计写入；受控执行器子进程分别在执行前、执行中、原生完成后以 `os._exit(71)` 退出。进程存活持锁时另一恢复者返回 409；数据库识别断连后重领；普通与已审批两个场景均验证最多一条报价、歧义态不执行且审计可查。已审批场景最终直接调用真实 continue 路由。
- 隔离边界：沿用临时 Python 启动器复用现有依赖，禁用 dotenv 读取和 pytest 插件自动加载，仅替换原生 executor factory 导入边界；真实采购/审批路由、SQLAlchemy/Pydantic/Decimal 及审计写入代码加载。原生浏览器执行使用受控替身；既有 block.py 删除未恢复。临时启动器在验证后删除。
- 过程发现：首次隔离单元检查因旧测试替身缺少新 claim 所需数据库字段/联表识别失败，已按实际查询补齐。首次数据库检查因测试未替换 ForgeApp 代理失败；修正后发现 Windows 进程退出与 PostgreSQL 感知 TCP 断连存在短暂间隔，测试改为最多 10 秒等待数据库实际释放锁，无强制解锁或自动重跑。
- 未验证：全量应用、前端、真实浏览器/供应商/模型 smoke、生产迁移升级均未运行。本轮不新增迁移，临时 schema 创建不冒充 `alembic upgrade head` 验证。
- 清理：每例临时 schema 已删除，临时启动器已删除；`docker stop procurerpa-run01-test` 成功，容器由 `--rm` 清理。未清理任何既有业务数据或工作区修改。
- 保留债务：显式重试恢复，无后台扫描或浏览器步骤自动续跑；每次持锁占用一个额外数据库连接；现有 best-effort 审计与业务事务统一仍属 STATE-01。其他债务不变。
- 停止原因：RUN-01 契约工程门已达到，停止扩展；真实 smoke 不属于完成门。


## 2026-09-22 STATE-01 quote-task 切片与直接验证证据

- 授权与来源：用户要求“进行 STATE-01 的开发”并要求继续；本次直接观察 `3c31bd7` 工作区。按契约先限定 quote-task，未提交、推送、切换分支、部署或访问真实采购/凭据。
- 本轮修改文件（含与前轮已有改动重叠的文件，保留原改动）：
  - `enterprise/procurement/quote_state.py`（新增）
  - `enterprise/procurement/routes.py`
  - `enterprise/approval/routes.py`
  - `enterprise/audit/logger.py`
  - `enterprise/agent/coordinator.py`
  - `tests/integration/test_state01_transactions.py`（新增）
  - `tests/integration/test_run01_recovery.py`
  - `tests/unit/test_procurement_review_regressions.py`
  - `tests/unit/test_day_11_quotes.py`
  - `tests/unit/test_approval_routes.py`
  - `tests/unit/test_s1_human_reviews.py`
  - `tests/unit/test_day_1_smoke_security.py`
  - `PROGRESS.md`
  - `DECISIONS.md`
  - `docs/procurement_completion_gap.md`
- 实现：复用 `procurement_coordination_states` 的 JSON/版本列，保存固定 `quote-task/v1`、`quote:<task_id>`、当前步骤与 task_id 输入引用，无新表/迁移/依赖。状态 CAS 拒绝过期更新（同一步骤的幂等写入也核对实际数据库版本）。新增 `GET /api/v1/enterprise/procurement/tasks/{task_id}/quote-state`，恢复入口支持 `expected_version`；响应只返回安全标识、步骤和版本。
- 事务：上下文/审批创建、执行前 Task.running、报价入库、人工核验、审批决定及人工处置各自与状态/审计同事务提交。审计失败不返回业务成功。恢复保留 RUN-01 独占 claim、completed 补后处理及歧义态转人工。人工核验提前 autoflush 的唯一约束失败纳入原有回滚/读取并发成功记录逻辑。
- 隔离：Coordinator 拒绝加载报价拥有的快照；非报价人工核验不进入报价状态机。旧无快照记录在首次合法变更时建立，未变更的历史任务保持 `state=null`。此处固定报价模板不是其余 Skill/template 的完整统一。
- 实际环境：Windows PowerShell、Python 3.12.12、复用 `.venv/Lib/site-packages` 的现有 pytest/SQLAlchemy/asyncpg；Docker 29.6.2，`postgres:14.23-alpine3.23` 临时容器 `procurerpa-state01-test`，只监听 `127.0.0.1:55439`、无宿主挂载、合成数据、每例独立临时 schema。
- 单元检查：11 个相关文件合计 **146 passed, 213 warnings**（1.95 秒）；覆盖采购/审批/人工核验/安全、Agent/Workflow/Skill、Coordinator 持久化及审计。最后将并发核验替身细化为另一条成功记录后，该专项再验 **1 passed**。
- PostgreSQL 检查：`test_state01_transactions.py` + `test_run01_recovery.py` 合计 **13 passed, 300 warnings**（164.05 秒），覆盖业务/状态/审计失败回滚、执行器调用前失败关闭、审批拒绝原子性、人工核验处置、数据库重载、过期 CAS、跨组织读取及执行前/中/后子进程崩溃。最后版本幂等分支和核验事务调整后，重跑状态/原子性两例 **2 passed, 49 warnings**（20.41 秒）。重复复验不重复计入 13 个场景。
- 验证隔离：临时 Python 启动器禁用 dotenv 文件读取和 pytest 插件自动加载，仅替换原生 executor factory 导入边界；为依赖模型路由的既有 Workflow/Skill 测试注册无凭据的合成 `STATE01_TEST` 配置，执行器/数据库替身由各单元测试注入。数据库场景加载真实路由、SQLAlchemy/Pydantic/审计代码，浏览器执行用受控替身；没有外部模型调用。
- 过程失败：首次单元检查有 6 项旧替身不支持新事务查询/审计接口，调整测试边界后通过；另 5 项 Workflow/Skill 检查因禁用 dotenv 后模型未配置而失败，使用合成注册配置后通过。首次数据库审批负例的测试用户角色错误，修正为同组织独立 approver 并写入合成用户后通过。后续 Docker 引擎停止导致一轮连接拒绝（6 failed、7 errors），未作为业务通过；恢复本地 Docker、重建临时容器后获得上述 13 项通过结果。
- 最终检查：12 份改动 Python 文件 Ruff 通过；`git diff --check` 通过（仅 LF→CRLF 提示）。本次未修改已有 auth/model/comparison/迁移文件，既有 `block.py` 删除保持不变。
- 未验证与保留：未运行全量应用、前端、真实浏览器/供应商/模型 smoke、生产迁移升级；临时 schema 测试不代表 `alembic upgrade head`。其他 Skill/template/Coordinator/Workflow 的统一事务、自动页面重放、其他债务与未接入路径仍保留。旧 best-effort audit writer 模式仍供范围外调用方使用。
- 清理与边界检查：各测试临时 schema 已清理；已停止并自动删除本轮临时 PostgreSQL 容器，临时启动器与测试输出文件已删除。3 份改动文档的本地链接检查通过，最终工作区路径与本轮范围/既有修改一致。
- 停止原因：本次契约允许的 quote-task 切片完成门已满足，不扩展到其他运行链或下一项债务。

## 2026-09-26 阶段 3 / AI-RISK-01 受限切片证据

- 来源与授权：本次直接观察，用户启动阶段 3 并授权代定模型、数据、保留期和预算/拆单来源。修订 `main@4c86636` 工作区；以下不是历史 smoke 或用户报告。
- 本轮修改文件：`enterprise/approval/risk_detector.py`、`enterprise/approval/risk_review.py`（新）、`enterprise/procurement/routes.py`、`skyvern/forge/sdk/api/llm/api_handler_factory.py`、`tests/unit/test_ai_risk01.py`（新）、`tests/integration/test_ai_risk01.py`（新）、`tests/unit/test_day_11_quotes.py`（仅增加风险模型替身）、`PROGRESS.md`、`DECISIONS.md`、`docs/procurement_completion_gap.md`、`docs/resume_guide.md`（仅移除 70% 断言）。开始前的阶段 1/2、其他文档和 block.py 删除均保留。
- 实现：quote-task 在现有权限与幂等检查后注入原生 Gemini 复核；低风险跳过，仅发送服务端类别和等级。结果严格限制为单个 risk_level 枚举，不能降低确定性下限；未配置/非法/超时沿现有保守回退。自由说明、供应商标识、金额、页面和历史不进入模型；风险/审批/审计仍通过原事务提交，审批后保持显式 continue。
- 原生必要修改：通用解析器的修复失败日志可能含响应正文，故增加 opt-in strict_response；不附带 Artifact 或历史、不继承浏览器上下文、不走通用修复解析、不写正文 Artifact，禁用 LiteLLM 普通回调及缓存。未启用该选项时原生解析路径保持，已加兼容性回归；没有新增 SDK/依赖/迁移。
- 验证环境：Windows PowerShell、Python 3.12.4、现有 .venv/Lib/site-packages；禁用 dotenv 与 pytest 自动插件加载，显式 pytest_asyncio，仅替换原生 executor factory 导入边界以绕过既有 block.py 删除。单元检查使用受控 provider/数据库替身；集成检查使用 Docker 29.6.2、postgres:14.23-alpine3.23 临时容器 `procurerpa-risk01-test`，仅绑定 127.0.0.1:15439、无宿主挂载，每例独立合成 schema。
- 最终组合命令：隔离启动器执行 `pytest -p pytest_asyncio.plugin tests/unit/test_ai_risk01.py tests/unit/test_risk_detector.py tests/unit/test_day_11_quotes.py tests/unit/test_day_1_smoke_security.py tests/unit/test_procurement_review_regressions.py tests/integration/test_ai_risk01.py -q --tb=short`，结果 **119 passed, 187 warnings**。随后新增默认原生解析兼容性用例并修正 provider 替身为原生 ModelResponse，专项文件复验 **19 passed, 6 warnings**；合计覆盖 **120 个独立用例**，不是把重复运行相加。
- 直接证据：跨组织/权限/超长说明在调用前拒绝；敏感合成标记不进入 prompt；低风险零调用；模型错误与降级不降低规则下限；严格原生调用无 Artifact/历史/普通回调/缓存，默认解析保留。4 个 PostgreSQL 场景覆盖升级/降级尝试/非法/超时，断开连接后能读取一致的风险、审批和安全审计，critical 去合规部门，幂等重试不再调用模型，Task 保持 created 且未执行浏览器。
- 过程问题：首轮 4 个测试因替换共享 skyvern_context.current 同时影响日志处理器而失败，改为仅替换原生模块的 context 引用；新增默认解析测试首次因 SimpleNamespace 不具备 model_dump_json 失败，改用真实 ModelResponse 后通过。两者都是测试替身问题，没有改写生产行为掩盖失败。
- 静态与边界：7 份改动 Python 文件 Ruff 通过；4 份文档本地链接检查通过；git diff --check 通过，仅 LF→CRLF 提示。路径核对只新增本轮范围内修改；没有 commit/push/部署。临时数据库已停止并由 --rm 清除，临时启动器清理，不清理任何既有业务数据。
- 未验证与保留债务：未运行真实模型/浏览器/供应商 smoke、全量应用测试或生产部署；未读取凭据、核实模型账户与提供方保留期。既有 block.py 删除仍限制标准原生执行器导入。预算超额/拆单仍缺权威事实，页面/供应商自由上下文未接入，真实调用避免率未测量；应用正文零持久化不等于提供方零保留，也不代表任意外部代理的日志政策。客户端风险事实权威化不在本切片内，现有请求边界与服务端阈值/审批规则保持。
- 停止原因：获准的一条真实入口受限切片达到工程完成门；不宣称预算/拆单、丰富上下文或 AI-RISK-01 全范围完成，不自动进入阶段 4。
- 最后复核：发现原生 Gemini 默认 thinking budget 为 1024，风险调用 completion 上限调整为 2048，保持 provider 12 秒/企业 15 秒超时；provider 替身改用真实注册模型标识（仍无外部调用）。修改后专项再次 **19 passed, 6 warnings**，7 份 Python 文件 Ruff 再次通过。

## 2026-09-26 阶段 4 / PLANNER-01 受限报价计划证据

- 来源：本次直接观察；用户启动阶段 4 并明确选择受限 Planner。修订 `main@4c86636` 工作区；未提交、未推送、未部署，阶段 1～3 既有修改及 block.py 删除保持。
- 本轮修改文件：`enterprise/agent/quote_planner.py`（新增）、`enterprise/procurement/routes.py`、`enterprise/procurement/quote_state.py`、`tests/unit/test_quote_planner.py`（新增）、`tests/unit/test_procurement_review_regressions.py`、`tests/integration/test_planner01.py`（新增）、`tests/integration/test_run01_recovery.py`、`tests/integration/test_state01_transactions.py`、`PROGRESS.md`、`DECISIONS.md`、`docs/procurement_completion_gap.md`、`docs/resume_guide.md`（仅 Planner 相关表述）。
- 实现：受限计划只允许 execute_native → persist_quote；模型只能返回当前未完成后缀，额外字段/动作/重复完成步骤/非法顺序均回退 deterministic_fallback。只发送固定步骤枚举，不发送任务 ID、URL、说明、金额或页面。复用已注册 Gemini 和原生 strict_response，模型缺失/异常不阻断既有确定性链。
- 持久与恢复：计划/安全审计先同事务提交，再沿既有独占 claim 和原生 running 标记执行同一 Task；原生 completed 恢复只保留 persist_quote，有效持久计划不再次调用模型。报价与完成状态/审计同事务；计划已提交后报价失败，保留计划安全重试。过期计划写入及幂等写入均验证数据库版本。歧义态先转人工，不交给模型重试；人工补录不虚构原生步骤完成。
- 环境：Windows PowerShell、Python 3.12.4、现有 .venv/Lib/site-packages；禁用 dotenv 与 pytest 自动插件加载，显式 pytest_asyncio，仅替换原生 executor factory 导入边界以绕过既有 block.py 删除。Docker 29.6.2，postgres:14.23-alpine3.23 临时容器 procurerpa-planner01-test，只监听 127.0.0.1:15439、无宿主挂载、无生产数据，每例独立合成 schema；模型与浏览器执行均用受控替身。
- 组合验证：隔离启动器运行 `pytest -p pytest_asyncio.plugin tests/unit/test_quote_planner.py tests/unit/test_procurement_review_regressions.py tests/unit/test_day_11_quotes.py tests/unit/test_agent.py tests/unit/test_s2_coordination_persistence.py tests/integration/test_planner01.py tests/integration/test_state01_transactions.py tests/integration/test_run01_recovery.py -q --tb=short --disable-warnings`，**117 passed, 640 warnings**（339.57 秒）。人工完成边界修正及新用例加入后，最终重跑 `test_planner01.py` 与 `test_state01_transactions.py`，**12 passed, 312 warnings**（248.28 秒）；合计 118 个独立场景，不累加重复运行。
- 覆盖：初始/复用/剩余计划、原生 strict handler 参数、非法计划回退、敏感异常不输出；PostgreSQL 断连重载、模型只规划未完成步骤、原生完成后不重跑、重复恢复幂等、过期 CAS/幂等 CAS、计划审计原子性、报价/完成状态/审计回滚、人工完成事实；原有跨组织/权限/审批/执行前中后进程崩溃回归。
- 过程失败：首轮 7 个旧路由替身缺少新增计划存储接口，扩展隔离边界后通过；首次组合为 114 passed / 1 failed，失败来自旧断言要求报价失败后无任何状态，与先持久计划的新边界不符。改为预存计划后注入三类写入故障，验证计划保留、报价及完成事件回滚；复验全部通过。未通过修改生产行为掩盖测试错误。
- 静态与清理：8 份改动 Python 文件 Ruff 通过，4 份文档本地链接检查通过，git diff --check 通过。路径核对仅涉及上述文件及既有修改。各临时 schema 由 fixture 清理；本轮临时数据库已停止并由 --rm 删除，隔离启动器已删除；未清理其他容器或数据。
- 未验证与保留：未运行外部模型/浏览器/供应商 smoke、全量应用/前端或生产迁移；未访问凭据。既有 block.py 删除仍限制标准原生执行器导入。固定顺序没有自由业务分支，本切片不证明通用规划或规划收益；旧 PlannerAgent/Coordinator/四种失败策略仍是独立 demo，SKILL-01、模板与凭据接入保留。
- 停止原因：用户确认的受限方案及首个真实入口工程完成门已满足；按 PLANNER-01 契约停止，不宣称整个阶段 4 完成。


## 2026-09-30 阶段 4 / SKILL-01 无凭据报价切片证据

- 来源与授权：本次直接观察 `main@4c86636298bb8bb1db2cc3e2f81ff3e09bb915ec` 工作区；用户要求继续阶段 4，并确认采用无凭据报价切片。开始前全部阶段 1～4 修改与 block.py 删除保留，没有 commit/push/分支切换/部署。
- 本轮修改文件（与既有修改重叠时保留原内容）：
  - `enterprise/workflows/routes.py`
  - `enterprise/skills/executor.py`
  - `enterprise/procurement/quote_state.py`
  - `enterprise/procurement/routes.py`（只增加人工/原生提取来源）
  - `tests/unit/test_workflows.py`
  - `tests/unit/test_s5_skill_pipeline.py`
  - `tests/unit/test_s1_human_reviews.py`（只补齐列查询替身）
  - `tests/unit/test_skill01.py`（新增）
  - `tests/integration/test_state01_transactions.py`（安全响应/审计契约断言）
  - `tests/integration/test_skill01.py`（新增）
  - `PROGRESS.md`
  - `DECISIONS.md`
  - `docs/procurement_completion_gap.md`
- 入口与行为：新增 `POST /api/v1/enterprise/workflows/instantiate/quote-task/v1`，请求沿用 QuoteTaskRequest 的 organization_id/department_id/category_id/url/risk 和 Idempotency-Key，直接调用现有 quote-task。原生 Task/Artifact、规则/审批、显式 continue、独占 claim、受限 Planner/CAS、Decimal 与人工核验沿用；没有第二套 Task/浏览器/Pipeline。用原采购 GET tasks/{task_id}/quote-state 查询安全 Skill 投影。
- 步骤证据：仅 table_extract 映射到原生报价抽取，快照与审计只保存 step_id/skill_name/task_id/status/artifact_id。准备、审批等待、执行中、人工核验与终态可重载；同报价/核验/状态事务提交，Skill 审计故障不返回业务成功。原生候选通过完整报价和同组织 Artifact 校验后才由服务端内部标记 completed；人工核验或直接 /quotes 录入都为 manual_completed。旧快照无 Skill 字段时标记 not_connected，不批量回填、不虚构历史提取成功。
- 安全边界：六个历史模板列表/详情标记 not_connected，实例化在 Task 创建前返回 409 workflow_credentials_not_connected；编译器统一拒绝 login/session_keep_alive。六个模板均通过相同关闭契约；独立 simulated Pipeline 与 Skill 定义保留。新增原生模板是 API 切片，未放入旧前端模板目录，也不冒充六个历史业务模板之一已完成。
- 实际环境：Windows PowerShell、Python 3.12.4、复用 .venv/Lib/site-packages；禁用 dotenv 与 pytest 插件自动加载，显式 pytest_asyncio，仅替换原生 executor factory 导入边界以避开既有 block.py 删除。Docker 29.6.2，已有 postgres:14.23-alpine3.23；本任务临时容器 procurerpa-skill01-test 仅监听 127.0.0.1:15439，无宿主挂载、无生产数据/凭据，每例独立合成 schema。Task 创建/浏览器/provider/通知外部边界使用受控替身，真实 FastAPI/采购路由/SQLAlchemy/数据库约束与审计代码加载。
- 最终组合验证：隔离启动器运行 `pytest -p pytest_asyncio.plugin tests/unit/test_quote_planner.py tests/unit/test_workflows.py tests/unit/test_s5_skill_pipeline.py tests/unit/test_skill01.py tests/unit/test_day_11_quotes.py tests/unit/test_procurement_review_regressions.py tests/unit/test_day_1_smoke_security.py tests/unit/test_s1_human_reviews.py tests/unit/test_day_10_quotes.py tests/integration/test_skill01.py tests/integration/test_state01_transactions.py tests/integration/test_planner01.py -q --tb=short --disable-warnings`，**163 passed, 574 warnings**（229.74 秒）：145 个单元场景、18 个 PostgreSQL 场景。
- 崩溃恢复：本轮此前组合包含 test_run01_recovery.py 的全部 6 个执行前/中/后普通与已审批进程崩溃场景，均通过；该组合整体是 22 passed / 1 fixture setup error（377.13 秒），不能写成整体通过。缺失审批 fixture 在下面过程记录中修正，最终组合覆盖它。两组共覆盖 169 个独立场景，不累加重复复验。
- 覆盖：同一原生报价链和幂等键、审批 202 等待且不执行浏览器、跨组织/部门/URL/非开发环境拒绝、六模板与登录/会话编译失败关闭、断开连接后重载 Skill/Artifact、重复入口只执行一次、Skill 审计失败回滚与安全重试、两种原生状态下人工补录及直接人工报价来源、既有 stale CAS/事务/权限/崩溃恢复。
- 过程失败与修复：初始隔离基线为 48 passed / 5 failed，原因是未配置合成模型；后续 handler 用受控 routing 替身，未读取实际模型凭据。新增 HTTP 测试首次用 Python model_dump 携带 Decimal，改为真实 JSON 序列化。首次 PostgreSQL 组合 14 passed / 2 failed：旧快照断言缺新增 Skill 字段，以及默认缺失供应商/资质/比价事实触发保守高风险但基础 fixture 无审批权限表；更新响应断言、为低风险场景提供合成完整事实，并另用真实审批 fixture 验证高风险等待，没有降低生产风险规则。Ruff 曾移除改名 fixture 导入，改为显式模块 fixture 引用。扩大人工回归时 143 passed / 2 failed 来自旧 scalar 替身把 Artifact 列查询返回整条 Review；补齐列查询后专项 6 passed。所有相关场景最终组合通过。
- 静态与清理：10 份改动 Python 文件 Ruff 通过；3 份文档本地链接检查通过；git diff --check 通过，仅既有 LF→CRLF 提示。沙箱阻止 Docker 启动日志和本地管道，使用经自动审核允许的宿主进程权限启动本地 Docker，并用空 Docker 配置避免读取配置凭据。精确核对本任务容器 ID 后确认临时 schema 剩余 0，停止容器并由 --rm 删除；临时启动器与空 Docker 配置目录已清理，未清理其他容器、业务数据或工作区修改。
- 未验证：外部模型/供应商/浏览器 smoke、全量应用和前端、生产迁移/部署未运行；无新迁移，临时 schema 不代表 alembic upgrade。既有 block.py 删除仍限制标准原生执行器导入，没有恢复它。
- 保留债务与停止原因：本次明确授权的无凭据代表切片达到工程门后停止。凭据提供方、运行身份、轮换/吊销、其余 Skill 的独立步骤证据、六个历史模板完整原生执行及前端目录尚未接入；不宣称 SKILL-01 全范围或整个阶段 4 完成，不自动进入阶段 5。


## 2026-09-30：阶段 4 全范围继续，必要确认待答复（上一轮历史记录）

- 最新授权：用户要求“继续开发直到完成阶段4”。本任务仍活动；两个旧切片的停止条件不再限制本次范围，不宣称阶段 4 已完成。
- 本轮新增/修改：enterprise/agent/quote_planner.py、enterprise/skills/native.py、tests/unit/test_quote_planner.py、tests/unit/test_native_skills.py；skyvern-frontend/src/routes/enterprise/workflows/WorkflowTemplatesPage.tsx、src/__tests__/WorkflowTemplatesPage.test.tsx、src/router.tsx、src/components/enterprise/EnterpriseSideNav.tsx；本文和 docs/procurement_completion_gap.md。
- 实现：Planner 可校验任意服务端固定原生步骤序列的未完成后缀，拒绝不连续完成记录并复用已存有效计划。五个公共 Skill 编译为单一原生 Workflow 的 Navigation/Extraction/FileDownload Block，默认禁缓存、不继续失败、不接受未知参数/凭据字段或自定义重放策略；当前尚未接入运行入口。login/session_keep_alive 仍失败关闭。
- 前端：模板目录已接真实目录/详情 API、采购权限上下文和侧栏；not_connected 模板禁用启动并不展示旧 username/password 输入。未来 real 实例的启动/状态读取界面已实现，网络重试复用 Idempotency-Key，输入更改重置尝试；相应实例 API 尚待本任务接线，不能宣称已可执行六模板。
- 本次直接验证（Windows PowerShell，Python 3.12.4 + 现有 .venv 包，不加载 .env，不调用真实模型/凭据）：Planner 11 passed；随后原生编译/安全负例 7 passed。Node + Vitest 3.2.4：目录 2、既有采购工作台 5，共 7 passed；tsc --noEmit、四 Python 文件 Ruff 均通过。git diff --check 已通过，本次最终还将检查文档改动。PostgreSQL 和真实浏览器未在本次新增代码上运行，旧切片历史结果不算本次验证。
- 测试环境处置：默认 Vitest 缓存写入被沙箱禁止；自动权限审查请求超时，未运行该提权命令。随后在沙箱内使用本轮临时 ESM 配置、runner loader 和单 worker threads 成功完成测试，临时配置已删除；未修改仓库现有测试配置。
- 实际阻塞证据：无 .env、无替代 module 的真实 import skyvern.forge.sdk.workflow.models.workflow 报 ModuleNotFoundError: skyvern.forge.sdk.workflow.models.block。本轮开始前 block.py 已删除，其余既有工作区修改均保留。
- 必要待确认：已通过异步问题请求用户确认原生 CredentialVaultService/组织 credential_id/发起人或管理员显式运行/启动恢复重验/吊销或版本变化失败关闭，以及只从当前 HEAD 恢复既有删除 block.py 的授权；目前未收到答复。前者由 SKILL-01 开工前决策契约要求，后者由 AGENTS.md 保留既有工作区修改规则要求。
- 保留工作：原生凭据边界与用途/版本校验、login/session 映射、六模板完整运行入口、步骤/Artifact/安全审计、原生恢复及数据库集成；这些仍属于当前阶段 4 任务，不转交为阶段 5，不以编译或前端单元测试替代原生工程验收。
- 下一步：得到上述必要确认后，在同一活动任务内完成原生 Workflow 接线、安全审计与受控集成检查，再更新阶段 4 完成状态。不得假定等待时间等于批准。


## 2026-09-30：阶段 4 全范围接线与最终验收（本轮直接观察）

- 来源与授权：用户“继续开发直到完成阶段4”，在上轮两项确认后回复“继续”；按已提出的凭据策略继续，并只恢复当前 HEAD 的 block.py。基于 main@4c86636298bb8bb1db2cc3e2f81ff3e09bb915ec 的未提交工作区；此前阶段 1～4 及无关修改均保留。未 commit/push、切换分支、部署、读取真实凭据或调用外部模型/供应商。
- 完成定义与边界：七 Skill 映射原生能力，六模板通过同一原生转换与安全契约，代表模板有真实路由/原生步骤入口/数据库证据审计/恢复验收，目录可操作，报价主链不退化；仅 controlled_demo 合成数据，不以真实门户完成率、通用自由规划或外部 smoke 作为本轮完成门。
- 修改文件（本轮）：enterprise/agent/quote_planner.py；enterprise/skills/native.py；enterprise/workflows/{models,routes,runtime,templates}.py；alembic/env.py、alembic/versions/2026_09_30_0013_workflow_instances.py；skyvern/forge/sdk/api/llm/api_handler_factory.py、skyvern/forge/sdk/artifact/manager.py、skyvern/forge/sdk/forge_log.py、skyvern/forge/sdk/workflow/context_manager.py、skyvern/forge/sdk/workflow/models/block.py、skyvern/forge/sdk/workflow/service.py、skyvern/utils/prompt_engine.py、skyvern/webeye/actions/handler.py；skyvern-frontend/src/components/enterprise/EnterpriseSideNav.tsx、src/router.tsx、src/routes/enterprise/workflows/WorkflowTemplatesPage.tsx、src/__tests__/WorkflowTemplatesPage.test.tsx；tests/unit/test_{native_skills,stage4_secrets,quote_planner,workflows,s5_skill_pipeline}.py、tests/integration/test_stage4_workflows.py；PROGRESS.md、DECISIONS.md、docs/procurement_completion_gap.md、docs/resume_guide.md。保留并回归此前 quote-task/v1、quote-state、Skill 审计和采购工作台改动，未重写无关审批/风险实现。
- 原生接线：六模板用 credential_id 取代 username/password，移除客户端输出文件路径；七 Skill 转现有 Login/Navigation/Extraction/FileDownload，原生 create → prepare → AsyncExecutorFactory，执行固定准备版本。session_keep_alive 是有界会话检查/重新登录。实例表仅保存授权和安全投影，不增加执行引擎；同组织 Task/Block/Artifact 才能证明步骤完成，表格须再经结构校验，下载须有原生下载结果。
- 持久化与恢复：计划、派发前 running、步骤、终态各与安全审计同事务。组织/幂等摘要唯一，版本与行锁隔离并发；已完成步骤不重复，只有原生 created 且无 Block 的 ready 可启动，preparing/running 歧义转人工。恢复/终止均 expected_version；终止同时取消原生 run 和未完成 Task，准备/派发异常不覆盖已提交终态。
- 凭据与数据：沿原生 CredentialVaultService，只支持同组织、精确受控 tested_url、无 TOTP/浏览器配置的密码引用。发起人/管理员显式执行，启动、恢复、每步与密码输入重验当前身份、用途、删除与 modified_at。秘密只在原生文本填充边界解析，填充异常返回安全固定失败；其他动作拒绝解析。模型禁历史与图像；Prompt、输出、创建/更新 Artifact、原生控制台/上下文日志掩码已知凭据，包含 JSON/HTML 转义；不保留截图/录屏/PDF/二进制/路径 Artifact。不能据此宣称任意敏感采购正文脱敏。
- 前端：目录和详情、部门/品类上下文、启动与安全步骤证据、刷新、恢复和终止已接真实 API；启动丢响应保留幂等键，参数改变才重置，恢复/终止携最新版本。页面标记原生工作流与受控演示数据，不接受旧用户名/密码输入。
- 实际环境：Windows PowerShell、Python 3.12.4，复用 .venv/Lib/site-packages 的既有依赖；禁 dotenv 和插件自动加载，显式 pytest_asyncio；恢复 block.py 后加载真实原生模块，不再替换 executor 导入。Docker Desktop 的临时 postgres:14.23-alpine3.23，仅监听 127.0.0.1:55439，无宿主挂载，每例合成 schema。浏览器、vault、模型/provider 和后台外部边界用合成替身；真实 FastAPI/转换器/prepare/WorkflowService 单步入口/SQLAlchemy/约束与审计运行。Node、Vitest 3.2.4、现有 TypeScript/happy-dom/react 依赖，临时 ESM runner 配置解决默认缓存写入限制，无安装依赖。
- 本次直接验证（中间与最终区分）：此前 82 passed / 993 warnings / 215.93 秒的后端组合；增加持久计划破坏场景后 PostgreSQL 16 passed / 1009 warnings / 247.81 秒；再修终止竞态后专项 2 passed / 15 deselected / 43.03 秒；新增真实文本填充/日志/Artifact 更新安全检查 2 passed / 15.65 秒。最终六文件组合为 **85 passed / 1083 warnings / 232.60 秒**，包含 17 个 PostgreSQL 工作流场景和 68 个单元场景，覆盖最后的计划顺序、终止竞态、日志/Artifact 更新及原生文本填充改动。
- 扩大报价回归：本轮 14 文件组合为 172 passed / 1 failed / 1559 warnings / 524.60 秒，唯一失败是新秘密测试构造 CredentialParameter 缺 created_at/modified_at；补齐后该项单独 1 passed，并已包含于上面的 82 passed 组合。真实报价、Planner、Skill、STATE 事务与人工核验相关通过项可作为本轮证据；不把失败组合写成 173 passed，不累加复验。
- 前端与静态：目录 3、既有采购工作台 5，共 8 passed；tsc --noEmit 通过。20 份 enterprise/迁移/测试文件与 8 份必要原生文件 Ruff 分别通过。迁移图单 head 为 ent_013、父 ent_012；隔离 PostgreSQL 已执行 ent_013 upgrade/downgrade，新表模型/API 在真实数据库运行，不代表生产全图 upgrade。4 份文档本地链接通过，28 份改动 Python 文件最终 Ruff 通过；正常 git diff --check 通过，仅既有 LF→CRLF 提示。
- 过程问题与修复：临时数据库安全 fixture 只准 55439/15439，初始端口 55434 被拒，精确停止本轮错误端口容器后重建。Native Login/Folder 外键、CredentialParameter 时间戳和转换器参数顺序的测试构造已修正；前端 act 函数曾误放 useEffect，经 TypeScript 检查移至组件作用域。正常 git diff --check 已通过；错误使用 core.autocrlf=false 的检查把 Windows CRLF 视为尾空白，未据此格式化任何无关文件。实际迁移名为 ent_013；首次用 ent013 查找失败，按源码名 ent_013 复核通过。新增日志测试曾误取未初始化 AppHolder，改为复用已注入的原生运行上下文；不是生产凭据读取。
- 未验证与保留债务：真实外部模型/密钥库/供应商/Chromium smoke、六模板真实页面成功率、全量应用测试、生产迁移/部署均未运行；没有真实成本或规划收益数字。自由任务分解、独立 demo Coordinator/四种失败策略、TOTP/浏览器配置和永久保活、图片/二进制安全留存、任意敏感采购正文脱敏保留。新的 ent_013 尚未应用到生产环境。
- 资源清理：临时 PostgreSQL 非系统 schema 剩余 0；再次 inspect 核对 procurerpa-stage4-20260930 的精确容器 ID 和镜像后停止，由 --rm 删除。只删除本轮 .stage4_check.py、skyvern-frontend/.stage4-vitest.config.mjs 与空 .stage4-docker，不触及其他容器或文件。Docker Desktop 留在正常运行状态。
- 停止原因：阶段 4 已达到冻结的全范围工程门，最终组合、前端、静态、迁移、链接与资源清理完成；活动任务关闭。阶段 5、生产迁移/部署和真实外部 smoke 仍需另行明确授权，不自动扩展。


## 2026-10-01 阶段 5 / MODEL-COST-01 工程验收证据

- 来源与授权：本次直接观察。用户“开始开发阶段5”；原生 block.py 在检查期间从已有修改变为删除，导致导入失败，用户随后明确“授权从 HEAD 恢复”。只恢复该文件并保留必要的企业模板禁强制秘密/输出掩码边界；不声称恢复了已丢失修改的完整字节内容。已有阶段 1～4 其他工作区修改保留。基于 main@4c86636298bb8bb1db2cc3e2f81ff3e09bb915ec 未提交工作区。
- 修改文件（18 份）：enterprise/llm/model_router.py；enterprise/dashboard/routes.py、enterprise/dashboard/stats.py；enterprise/procurement/routes.py（仅给新 quote-task 标记运行时路由）；skyvern/forge/agent.py、skyvern/forge/sdk/models.py、skyvern/forge/sdk/workflow/models/block.py；scripts/benchmark_model_cost.py（新）；tests/unit/test_s7_model_routing.py、tests/unit/test_dashboard.py、tests/integration/test_stage5_model_cost.py（新）；skyvern-frontend/src/routes/enterprise/dashboard/DashboardPage.tsx、skyvern-frontend/src/__tests__/DashboardPage.test.tsx、skyvern-frontend/src/i18n/locales.ts；PROGRESS.md、DECISIONS.md、docs/procurement_completion_gap.md、docs/resume_guide.md。
- 实现与数据：已有 scrape 后、提示词/Vertex 缓存前选择已注册 key，无额外抓取/模型调用。原生树已观察节点、iframe 深度、表单/Shadow DOM 为结构信号；AJAX/WebSocket 明确 not_observed。当前 Task 副本使用 Step 路由，不覆盖初始模型；路由摘要与 Step 审计先提交。无注册 key/授权上下文/审计提交时沿原生失败边界停止，采购 speculative 预调用禁用。恢复和下一步骤重新取当前结构，不缓存原树或个性化值。
- 缓存与展示：Redis 组织/DOM/goal/实际 model/schema key 与 24h TTL 保留；采购无表单页面仅 WAIT/SCROLL 可复用，任何采购 Workflow（包括已有 TaskExtension 的认证步骤）、缺失结构、输入/上传/提交等不缓存。API 用量查询按组织/部门/品类隔离，Step 最新安全路由决定档位；旧 Step 保留 Task 档位兼容。原生报告成本独立标记 native_step_reported，缺失/零/非有限/负值为 unknown。Dashboard 展示 Token、提供方缓存 Token、报告成本和组织动作缓存状态；Redis 故障与 org_admin 权限受限分别 unavailable/restricted，不掩盖 PostgreSQL 事实。
- 固定基准：`scripts/benchmark_model_cost.py` 无参数仅输出 model-cost-v1 固定六场景（simple-100、moderate-101、complex-501、iframe-2、form-20、shadow）。两次直接 CLI 输出完全一致，档位 light/standard/heavy/heavy/heavy/heavy，cost_status=unknown，savings_percent=null。可接受严格成对数值记录，覆盖/顺序/成功结果/有限非负 Decimal 校验；数值仅标 reported_measurements，缺记录或失败不计算节省率。测试中的 20% 只验证计算器算术，不是实测项目收益；没有真实 provider 记录，简历删除 60% 断言。
- 实际环境：Windows PowerShell；Python 3.12.4，复用 .venv/Lib/site-packages，禁 dotenv/Pydantic dotenv 读取与 pytest 自动插件，显式 pytest_asyncio.plugin；没有替换原生 executor/block 模块。Node 25.7.0、Vitest 3.2.4、现有 happy-dom/react/TypeScript；临时 ESM runner 配置仅用于运行检查。Docker 29.6.2，已缓存 postgres:14.23-alpine3.23，容器 procurerpa-stage5-20261001，仅绑定 127.0.0.1:55439，无宿主 bind mount，每例合成 schema；浏览器/provider/vault 使用合成替身，未安装依赖或访问凭据。
- 直接 PostgreSQL 验证：真实 SQLAlchemy/原生 build_and_record_step_prompt/scrape 接点/事务审计/成本查询运行。单 Task 两个 Step 分别路由 light/heavy，持久审计无页面文本；连接重启后按 Step 归类，组织/部门/品类负例均返回空事实。独立首次 1 passed / 29 warnings / 28.21 秒，已包含最终组合，不累计重复次数。
- 后端验证：中间七文件组合 115 passed / 107 warnings / 15.82 秒。九文件兼容组合（含阶段 4 的 17 个 PostgreSQL 场景）136 passed / 1163 warnings / 311.83 秒；期间最后增加 Workflow 缓存禁用分支与保守零成本处理，此后八文件最终复验 **120 passed / 128 warnings / 39.03 秒**（119 单元与 1 PostgreSQL），覆盖最后的路由/缓存/成本修改。八文件为 test_s7_model_routing、test_action_cache、test_dashboard、test_day_11_quotes、test_quote_planner、test_native_skills、test_stage4_secrets 和 test_stage5_model_cost；不把重叠组合相加或将中间结果冒充最终修订。
- 前端与静态：Dashboard 4、工作台 5、模板目录 3，共 **12 passed**；tsc --noEmit 通过。11 份相关 Python（含恢复的 block.py）Ruff 通过；4 份文档本地链接通过；全工作区与本轮批准文件 git diff --check 通过，只有已有 LF→CRLF 提示。git status 与开始时逐项核对，新增路径仅阶段 5 实现/测试及随后删除的临时检查文件；未格式化或恢复其他工作区文件。
- 过程问题与修复：WindowsApps Python alias 不可运行，改用已安装 Python312 可执行文件；最初错误 pytest 插件名已改为 pytest_asyncio.plugin。block.py 删除经用户授权恢复。S7 旧测试依赖 dotenv 注册模型，改为显式合成注册 key；Settings 方法 patch 改在类上执行。前端重复翻译键复用旧键，未知成本断言改为包含文本匹配；默认 runner 的 __dirname 问题用临时 ESM 配置解决。Docker 从实际 E:/Docker/app 安装位置启动，daemon pipe 访问通过本地测试自动审批提升权限，未读取 Docker 凭据配置；首轮失败不记为通过。
- 资源清理：测试 schema 剩余 0；核对容器精确 ID 1d8d92caa64fb170e56fd5184785388838e6be38301a62c08997f71facd8c8ba、镜像、localhost 端口与匿名卷后停止，--rm 自动删除容器和该匿名测试卷；后续精确容器/卷查询为空。只删除本轮 .stage5_check.py、skyvern-frontend/.stage5-vitest.config.mjs、.stage5-docker/config.json 与空目录，不触及其他容器、卷或文件。
- 未验证与保留债务：真实 provider/供应商/Chromium/vault smoke、真实 Redis 服务联调、生产迁移/部署和全量应用测试未运行；Redis 测试使用 fakeredis，成本/Token 为合成持久 Step 值。真实计费/任务质量/路由缓存组合收益需要独立授权的固定场景成对运行，当前不声明生产节省率。节点树不等于全量 DOM，不推断 AJAX 生命周期；strict 风险/Planner 调用仍不进入浏览器 Step 用量，Dashboard 不是全组织全部模型账单。原生 Step 正成本只代表已有报告值，未独立核验提供方发票或混合调用完整性。TOTP/永久保活/视觉与二进制安全证据、预算/拆单权威集成、自由 Planner 和 demo Coordinator 原债务继续保留。
- 停止原因：当前授权的阶段 5 工程完成门满足，活动任务关闭；真实量化证据按契约收缩简历表述，不自动实调 provider、进入其他任务或 commit/push/部署。


## 2026-10-02：REVIEW-FIX-01 四项审查修复（本轮直接观察）

- 来源与授权：用户在只读 review 后要求“进行修复”；基于 HEAD `4c86636298bb8bb1db2cc3e2f81ff3e09bb915ec` 的已有未提交工作区。没有 commit/push/分支/部署、凭据访问或真实外部服务调用。
- 修改文件（8 份）：`enterprise/workflows/runtime.py`、`enterprise/skills/executor.py`、`skyvern/webeye/actions/handler.py`、`skyvern/webeye/browser_factory.py`、`skyvern/forge/sdk/workflow/context_manager.py`、`tests/unit/test_stage4_secrets.py`、新增 `tests/unit/test_review_fixes.py`、`PROGRESS.md`。其余开工快照中的文件哈希未变；没有格式化已有无关修改。
- 修复：凭据输入同时检查顶层与目标 frame 的精确受控 URL，frame 缺失/不匹配失败关闭；企业 Chromium 创建参数关闭 HAR/录像且不注册本地控制台正文监听，CDP 强制新建无录像上下文，非企业行为不变。凭据掩码覆盖 JSON 的 ASCII/Unicode 两种转义。表格 schema 复用 `x-skyvern-preserve-missing`，缺失/非法 rows 与缺列交企业验证拒绝，合法空表仍接受。
- 最小回归：新增 17 例覆盖受控填充允许、跨域/空白 iframe 与顶层越界拒绝、headless/headful/CDP 企业与非企业创建、Unicode/emoji/引号组合在 Prompt/Artifact 掩码、原生 filler 后非法表格拒绝和合法空表/有数据表保留。实际调用生产函数，浏览器、数据库与凭据均为合成替身；不以替身结果声称真实浏览器已运行。
- 实际环境和命令：Windows PowerShell、Python 3.12.4，复用 `.venv/Lib/site-packages`；测试进程隔离环境、禁 dotenv 与 pytest 插件自动加载、显式 `pytest_asyncio.plugin`、禁字节码与 pytest 缓存，LiteLLM 使用本地成本映射。Python stdin 引导 `pytest.main`，参数为五个下述文件及 `-q -p pytest_asyncio.plugin -p no:cacheprovider --tb=short --disable-warnings`。
- 本次直接结果：专项先行 **17 passed / 21 warnings / 17.63 秒**；最终五文件组合 **67 passed / 94 warnings / 10.15 秒**，文件为 `test_review_fixes`、`test_stage4_secrets`、`test_native_skills`、`test_s5_skill_pipeline`、`test_day_11_quotes`。前者包含于后者，不相加。7 份本轮 Python 文件 `ruff check --no-cache` 通过；`git diff --check` 通过，仅已有 LF→CRLF 提示。
- 过程与恢复：第一次 pytest 收集因 `skyvern/forge/sdk/workflow/models/block.py` 从开工的修改态变为删除态而失败。按 AGENTS.md 单独询问恢复授权后，用户回复“继续”；实际写入前该文件已经重新出现，脚本存在性断言中止，未覆盖文件。随后核对其 HEAD diff，已有企业禁强制秘密模板和输出掩码保护完整；正常导入真实 block 模块完成上述回归。最初 apply_patch 因工作区 reparse point 被拒，改为精确 Python 文本替换并保留原换行，没有放宽权限或清理其他文件。
- 未验证与保留债务：未运行真实 Chromium/CDP 浏览器、数据库集成、provider/vault/供应商联调、全量应用测试或生产部署；既有历史 HAR/录像/其他敏感文件不读取、不自动删除。远端浏览器基础设施独立录制、任意敏感采购正文脱敏及历史阶段债务仍不在本次保证内。
- 停止原因：四项局部修复、相关回归、静态检查和本轮文件边界核对完成，活动任务关闭；无新增依赖或数据库迁移。


## 2026-10-02：本地仓库提交授权与检查

- 用户明确选择“一起提交全部 78 个文件”，范围包含当前审批、风险、Planner、原生 Workflow、模型路由、四项 review 修复及相关迁移、前端、测试和文档；仅本地 commit，不包含 push、部署或生产迁移。
- 完成定义：这 78 个文件形成同一可追溯本地提交，提交后核对 HEAD、文件数和工作区；不修改其他业务实现。
- 本次直接检查：暂存区起始为空，候选清单 78 个文件；64 个 Python 文件 AST 语法检查通过，git diff --check 通过。Windows PowerShell / Python 3.12.4。
- 验证来源：相关 67 项测试与 Ruff 通过属于同一会话上一修复轮的直接证据，本提交轮未重新运行测试；不把阶段 1～5 的历史记录声明为本轮全量回归。
- 保留边界：真实浏览器、数据库/外部服务联调及历史敏感文件清理仍未执行；提交结果和提交 ID 以 Git 历史及本次最终汇报为准。
