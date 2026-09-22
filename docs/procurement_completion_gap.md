# ProcureRPA 能力与债务索引

## 文档用途

本页负责采购能力边界、真实/模拟关系和仍需显式保留的技术债，不负责声明当前任务、当前分支、最新验证或下一阶段。

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
5. **债务可见但不自动扩展范围。** 任何债务都需要在 `PROGRESS.md` 中形成有界活动任务后才能实施。

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

## 债务领取规则

以下契约是能力限制索引，不是路线、优先级或自动排期。一次只能把一个债务 ID 复制到 `PROGRESS.md` 作为活动任务；开工前必须重新核对真实调用方、当前迁移 head 和代表性测试，不能仅按本文实现。

每项任务统一遵守以下完成门：

1. 在 `PROGRESS.md` 写明完成定义、批准路径、范围外、人工决策、最小验证和停止条件。
2. 先留下能复现缺口的失败测试，再做最小实现；至少覆盖成功、拒绝/失败、重试或重启、租户隔离中与任务相关的场景。
3. 涉及状态或 schema 时，验证旧记录兼容、迁移单 head、并发幂等和事务失败不返回成功。
4. 仅运行相关 pytest、改动文件 Ruff、必要的受控集成测试、迁移检查、本地 Markdown 链接检查和 `git diff --check`；实际结果写回 `PROGRESS.md`，计划命令不能记作通过。
5. 不要求真实供应商网站、真实凭据、外部 Gemini 或 `quotes`/`controls` smoke。若任务需要访问凭据、外部系统、部署、提交或破坏性数据，达到边界即停止并单独申请授权。
6. 保留采购主链和服务端确定性决策；失败进入已有持久人工核验或明确错误，不能降级成 demo/simulated 成功。

## 可领取债务契约

### `RUN-01` 原生执行中断恢复

- **实现边界：** 报价创建先 defer 并持久化上下文；直接报价、审批继续和 `POST /enterprise/procurement/tasks/{task_id}/recover-quote` 共用 TaskExtension 数据库行锁。created 可启动，completed 可幂等补报价，其余歧义态转持久人工核验；不自动重放浏览器步骤。最新验收证据只见 `PROGRESS.md`。
- **操作语义：** 锁随数据库连接/事务释放，无超时强抢；返回 409 时执行者仍持锁或已有人工处置记录，须按错误详情区分。首次中断核验返回 422 和 review_id。需原组织、部门、品类写权限；审批任务仍要求已批准和原发起人/管理员。保留每次执行占用一个额外连接、显式重试触发及现有 best-effort 审计边界。
- **目标与责任边界：** 为 `enterprise/approval/routes.py` 和 `enterprise/procurement/routes.py` 发起的原生 Skyvern 报价任务补齐“浏览器执行中进程退出”后的持久恢复；复用现有 Task、TaskExtension、SupplierQuote 和人工核验，不新建通用队列平台。
- **范围内：** 可恢复状态识别、单一恢复 claim/lease、完成后幂等报价入库、失败审计和人工核验。**范围外：** 所有 Skyvern 任务的调度重写、多级审批、真实 smoke 和外部站点容灾。
- **开工前决策：** 明确哪些 Task 状态允许重领、执行副作用是否可安全重放、lease 超时和人工接管规则；无法证明可重放的状态只能转人工核验。
- **可观察验收：** 受控执行器在执行前、执行中和完成后分别崩溃并重启时，任务只被一个恢复者领取；最多产生一条 SupplierQuote；完成态可补后处理；歧义态不盲目重跑；组织范围和审计链保持完整。
- **代表性验证与停止：** 扩展 `tests/unit/test_procurement_review_regressions.py`、`tests/unit/test_approval_routes.py`、`tests/unit/test_day_11_quotes.py`，并用临时 PostgreSQL 进程重启场景验证 claim。若必须引入新消息基础设施或无法界定浏览器副作用，记录证据后停止，另开架构决策。

### `STATE-01` 运行状态与事务收口

- **实施边界：** 已落地 quote-task 切片：固定模板/计划与输入引用保存于现有 coordination state，复用版本 CAS，报价/审批/人工核验与审计同事务；原生浏览器执行事实仍由 Task 负责。其他 Skill/template/Coordinator/Workflow 的统一事务保留，本项不得据此宣称全范围完成。直接验证证据见 `../PROGRESS.md`。

- **目标与责任边界：** 让模板编译、Coordinator 计划、Workflow 进度、审批等待、页面恢复和审计引用同一组既有持久任务标识与版本事实；优先扩展 Task/TaskExtension，不创建第二套编排运行时。
- **范围内：** 持久化模板/计划标识、当前步骤、状态版本和脱敏输入引用；用一个明确事务边界提交业务状态与审计。**范围外：** 改写原生 Skyvern executor、保存页面敏感正文、统一全部历史 demo API。
- **开工前决策：** 画出现有状态所有者和提交顺序，确定唯一权威状态、乐观并发策略及旧记录的可空/回填行为；若一个切片无法覆盖，先限于 quote-task 链。
- **可观察验收：** 进程重启从数据库恢复同一模板实例和步骤；过期版本写入被拒绝；事务任一写入失败时不返回成功且不留下互相矛盾的审计；响应和日志不出现敏感参数。
- **代表性验证与停止：** 扩展 `tests/unit/test_agent.py`、`tests/unit/test_workflows.py`、`tests/unit/test_s5_skill_pipeline.py` 及采购回归测试。若需要新工作流引擎或跨服务分布式事务，停止并缩小为可独立验收的状态切片。

### `SEC-01` 生产凭据引用与即时注入

- **目标与责任边界：** 模板只保存凭据引用，执行时由服务端按组织和用途即时解析；凭据值不得进入模板参数、数据库业务记录、Prompt、Artifact、日志或 API 响应。
- **范围内：** 复用已批准的生产凭据存储、引用 schema、组织/用途授权、短生命周期注入和全链路脱敏。**范围外：** 自建密钥管理系统、把明文加密后塞进模板表、在测试中使用真实凭据。
- **开工前决策：** 由用户确认既有凭据提供方、轮换/吊销语义和运行身份；仓库没有已批准提供方时停止，不先写推测性的适配层，也不能宣称真实接通。
- **可观察验收：** 合法引用可在执行边界解析；跨组织、已吊销、缺失引用失败关闭；数据库、日志、Prompt、错误和 Artifact 扫描均无凭据值；测试仅使用合成 secret。
- **代表性验证与停止：** 扩展 `tests/unit/test_workflows.py`、`tests/unit/test_s5_skill_pipeline.py` 和安全日志测试。需要访问真实凭据或外部 secret manager 时立即停止并申请单独授权。

### `SEC-02` Prompt 与页面上下文治理

- **目标与责任边界：** 对送入模型的真实页面内容建立字段/节点 allowlist、体积上限、脱敏、访问控制和保留期；确定性采购字段继续由服务端结构化输入提供。
- **范围内：** 当前真实模型调用点的数据流清单、最小上下文构造器、敏感模式拒绝/脱敏、只含元数据的审计。**范围外：** 抓取更多页面、长期保存原始 DOM、用 LLM 判断权限或金额。
- **开工前决策：** 用户确认允许发送的数据类别、提供方与保留期；未确认类别默认不发送。先覆盖真实 quote-task 调用点，不泛化全部 Agent。
- **可观察验收：** 只有 allowlist 内容可离开进程；跨租户引用、凭据/银行账户/Token 和超限上下文在调用模型前被拒绝或脱敏；审计能回答谁、何时、向哪个模型发送了哪类数据但不保存正文。
- **代表性验证与停止：** 扩展 `tests/unit/test_day_1_smoke_security.py`、`tests/unit/test_risk_detector.py` 和相关模型调用测试。无法证明第三方保留策略满足约束时保持 `not_connected`，不得降级放行。

### `APR-01` 审批策略与路由快照持久化

- **目标与责任边界：** 将采购 category、命中的金额阈值、路由结果和策略版本作为创建审批时的服务端快照持久化，使后续授权和审计不依赖进程常量或重新计算。
- **范围内：** 既有单级审批的确定性策略、schema/迁移、历史记录兼容和策略版本。**范围外：** 多级会签、动态规则语言、管理后台和 LLM 路由。
- **开工前决策：** 用户确认阈值配置的权威来源、币种/生效时间和旧审批解释规则；没有明确来源时保持现有常量，不能先造配置平台。
- **可观察验收：** 边界金额产生预期风险与路由快照；category 与授权校验使用同一持久事实；策略后来变化不改写历史审批；客户端不能提交或覆盖路由字段。
- **代表性验证与停止：** 扩展 `tests/unit/test_risk_detector.py`、`tests/unit/test_p1_procurement_alignment.py`、`tests/unit/test_approval_model.py` 和 `tests/unit/test_approval_routes.py`，验证迁移升级和回滚边界。达到单级快照验收即停止，不顺带实现多级审批。

### `APR-02` 多级审批与完整暂停/继续

- **依赖与开工前决策：** 仅在 `APR-01` 已提供稳定策略快照，且用户给出明确的级次、会签/或签、超时和撤回规则后领取。
- **目标与责任边界：** 在现有 Approval 与 Task 上表达顺序级次，使原生任务只在最终批准后继续一次；复用现有权限、通知、审计和人工核验。
- **范围内：** 顺序审批、每级授权、拒绝/超时终态、幂等决定和最终继续。**范围外：** 任意 BPMN、并行会签、委托代办和可视化流程设计器，除非另有明确需求。
- **可观察验收：** 非当前级不能决定；申请人不能自批；任一级拒绝即终止；重复决定不产生第二次状态迁移；重启后级次可恢复；最终批准并发请求最多启动一次任务。
- **代表性验证与停止：** 扩展 `tests/unit/test_approval_model.py`、`tests/unit/test_approval_routes.py`、`tests/unit/test_approval_pubsub.py` 和 `tests/unit/test_procurement_review_regressions.py`，覆盖跨组织、越级、重复、超时和并发。规则存在歧义时停止，不用代码猜业务政策。

### `MAT-01` 权威物料标识与别名解析

- **目标与责任边界：** 为 SupplierQuote 和比价引入服务端权威 material/SKU 标识；显示名称只用于展示，别名解析不能由 LLM 直接决定推荐。
- **范围内：** 权威来源适配、确定性别名映射、不可解析时人工核验、schema/迁移和同物料比价。**范围外：** 新建完整物料主数据系统、模糊自动合并和跨物料替代推荐。
- **开工前决策：** 用户确认物料主数据所有者、唯一键、别名冲突和历史 quote 回填规则；没有权威来源时继续严格名称匹配，不伪造 SKU。
- **可观察验收：** 不同显示别名可解析为同一标识并比价；不同标识即使名称相似也拒绝混比；未知/冲突别名进入人工核验；数据库约束和租户范围阻止错误关联。
- **代表性验证与停止：** 扩展 `tests/unit/test_procurement_review_regressions.py`、`tests/unit/test_day_10_quotes.py`、`tests/unit/test_day_11_quotes.py`。达到确定性解析与比价验收即停止，不扩展替代品推荐。

## 有条件候选项

以下两项当前安全边界已经成立，不应仅为“清零债务”启动：

### `CACHE-01` 敏感动作缓存 schema

默认继续不缓存个性化输入、上传、选项、登录和提交动作。只有真实调用指标证明重复模型决策形成明确成本/延迟，并且用户批准可缓存数据分类时才领取。届时 schema 必须排除原始值、凭据、上传内容和提交副作用，以组织、页面、目标、模型和 schema 版本隔离；跨组织、过期、敏感字段及 Redis 故障均失败关闭。代表性测试为 `tests/unit/test_action_cache.py`。无法证明“不含 secret 且可安全重放”时，停止并保留 no-cache。

### `DEMO-01` 演示/兼容残留收口

无 handler Executor、内存 Action Cache、demo 模型路由和固定成本 helper 已明确隔离时，不是生产完成阻塞。只有生产调用图出现引用，或用户单独批准维护清理时才领取：先用全仓调用搜索分类“生产调用、测试 fixture、演示入口、无调用”，生产引用改回现有真实实现，无调用代码可删除，其余继续显式标记 `demo`/`simulated`/`not_connected`。不得为了复用这些代码而把它们接入生产。

## 明确排除项

- 真实 `quotes`/`controls` smoke、外部 Gemini 配额和真实供应商站点可用性不属于开发债务、项目阻塞或上述契约的默认验收。
- 全量 Ruff 历史问题、旧数据库中的演示记录和本机失效 `.venv` 只在单独维护任务中处理。
- 任何债务完成后只更新其实际证据和剩余限制，不自动领取下一项。
