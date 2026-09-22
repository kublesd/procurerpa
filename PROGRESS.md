# 项目进度

> 最后更新：2026-09-22 +08:00
>
> 本文件是当前目标、活动任务、最新证据、阻塞和下一步的唯一事实源。能力映射与保留债务见 `docs/procurement_completion_gap.md`，历史阶段契约见 `docs/procurement_rpa_development_guide.md`，重大取舍见 `DECISIONS.md`。

## 当前目标

当前活动任务：SEC-01/02（用户 2026-09-22 明确授权开发），已完成前置调查，等待契约要求的提供方与数据政策决定；尚未开始业务实现，不宣称接通或验收通过。

- 完成定义：凭据仅按组织/用途在执行边界解析引用，模型仅接收获准且受限的页面上下文，敏感值不进入业务记录、Prompt、Artifact、日志和响应，并有隔离负例验证。
- 范围：凭据引用及执行接点、quote-task 模型上下文治理、相关安全测试与状态文档；具体提供方接线须在用户确认后确定。保留开工前全部工作区修改及 block.py 删除。
- 范围外：自建密钥系统、全部 Agent 泛化、真实凭据访问、外部写入、真实 smoke、提交/推送/部署。
- 最小验证：合成凭据的合法/跨组织/吊销/缺失场景，模型输入 allowlist/敏感字段/体积边界、元数据审计与正文不留存回归，相关 Ruff 与 git diff --check；当前只读调查不替代这些验收。
- 前置决定：SEC-01 尚无用户确认的凭据提供方、运行身份及轮换/吊销语义；SEC-02 尚无用户确认的模型提供方、数据类别与保留期。已请求这些信息，不读取实际配置秘密，不以现有适配代码推定已批准。
- 停止条件：缺少上述决策时停在调查边界；确认后完成两项契约验收即停止，不扩展其他债务。

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

## 保留债务

详细契约由 `docs/procurement_completion_gap.md` 负责，当前仍影响后续工作的摘要为：

- `RUN-01` 已完成显式恢复切片：保留浏览器步骤不可盲目重放、恢复需请求触发、持锁占用一个额外数据库连接的边界；自动浏览器续跑不属于本契约完成定义。
- `STATE-01`：quote-task 固定计划/步骤/版本及报价、审批、人工核验与审计事务切片已完成；其他 Skill/template、Coordinator/Workflow 和完整页面恢复的状态统一仍保留。
- `SEC-01`、`SEC-02`：生产凭据引用与即时注入；Prompt/page context 最小化、访问控制和保留策略。
- `APR-01`、`APR-02`：审批策略/category/routing 快照持久化；多级审批和完整暂停/继续。
- `MAT-01`：权威物料/SKU 标识与确定性别名解析。
- `CACHE-01`、`DEMO-01`：仅在有性能或真实生产调用证据时领取；当前 no-cache 与显式 demo 隔离继续成立。

这些债务都不是自动排期。实施前必须在本文件建立一个有范围、验收、验证、授权边界和停止条件的活动任务。

## 本轮 harness 证据

- 来源：本次直接观察。
- 修订与环境：`main@9d078c0be9569e2c7401250c2127be6e5e1a5e35`；Windows PowerShell；仅文档修改。
- 中间检查：4 个职责文档的本地 Markdown 链接通过；harness validator 退出码 `0`，仅给出 `discovery_incomplete` 和 `reuse_existing_owners` 建议。
- 最终验证：5 个批准文档的本地 Markdown 链接检查通过；harness validator 退出码 `0`，仅保留两项非阻塞建议；过期领取语句搜索无命中；`git diff --check` 退出码 `0`，只有 LF→CRLF 工作区提示。
- 批准边界：`git status --short` 只显示 5 个批准文档被修改，以及任务开始前已有的 `skyvern/forge/sdk/workflow/models/block.py` 删除。
- 范围外状态：预先存在的 `skyvern/forge/sdk/workflow/models/block.py` 删除保持不变。

## 下一步

1. SEC-01/02 等待用户明确凭据提供方/运行身份/轮换吊销，以及模型提供方/允许数据类别/保留期；收到决定后继续既有接点实现与验证。
2. STATE-01 其他模板/Coordinator/Workflow 的统一仍保留；不自动扩展其他债务。`CACHE-01`、`DEMO-01` 还需满足各自启动证据。
3. 真实 smoke 不作为默认下一步或完成门。

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
