# M4-03 实施交接（不含验收判定）

基线：`cfe0ac1bb0f4aa6fe1ec934cdc2f03b5e3fab203`。执行者仅修改 `registry.py`、新增 `migrate.py`、`test_m403*` 与本证据目录；未修改 M4-05 的 paths/agents/detect/user_entries 写集，不 commit/push，不运行真实 HOME 下的项目命令。

## 调用合同

这是供机器安装器显式调用的库，不增加项目子命令，也不通过 enable/check 自动迁移。

- `plan_migration(runtime, source_registries, source_commits=..., product=..., allowed_user_paths=..., evidence_files=..., operation_id=...)`：只读，严格验证旧 schema=1、代码清单、事务恢复材料与现场，返回绑定来源/目标/版本/完整写范围的计划。
- `execute_migration(plan, approval, hook=None)`：批准必须等于完整计划加 `confirmed_at`（UTC Z）和真实确认引用 `reference`。宿主先展示并获得确认；JSON 文件不能自证用户授权。
- `inspect_migration(runtime, explicit_sources, allowed_user_paths=...)`：只读场景报告。没有显式来源时不扫描代码 checkout，也不把 v0 状态当产品台账。正常 check-memory 仍不会调用迁移；它从 registry 的中断诊断得到缺口而不重写。
- `plan_recovery(journal_path, action='continue'|'rollback')` / `recover_migration(recovery_plan, recovery_approval)`：独立、精确批准的恢复。绑定 journal 指纹、before/after 现场、退出进程的锁 inode/owner 指纹。未知所有者、仍活跃 PID、第三种字节均停止。
- `resolve_reference(model, original_path)` / `archived_recovery_descriptor(model, original_manifest)`：不依赖旧备份目录，定位并校验档案；返回原 manifest 及 before 文件映射，明确标出需要活动台账协调的旧 registry 输出。不能把原 manifest 原封不动交给旧 recover 去覆盖 tombstone。

所有参数必须显式提供。写路径使用既有 transaction 的 canonical-path 约束：调用者在预览前将环境 HOME（包括 `/var` 这种别名）解析到同一实体目录，展示 canonical 目标并绑定批准，不在执行时悄悄改计划。只读项目命令的 HOME 祖先别名处理不变。

目标 `product` 是后续安装器提供并负责核验的代码身份/三版本元数据；本模块不安装/升级代码、不探测执行器、不提升 runtime 四态。如果产品代码尚未准备完毕，调用者必须传 `installation_status=installing`，不能仅凭迁账声称机器安装完成。本模块记录 `last_operation_id` 为迁移 op。

## 保真与归档

旧账的原始字节、M2/M3 来源标记 `m2-schema1`、代码清单/提交/树指纹、当前和历史 before 账本递归引用的 manifest/before 文件、显式文件证据和 runtime 文件证据进入 `R/backups/m2-migration-<op>/`。

每个原始绝对路径映射到 `files/<parent-path-hash>/<basename>`：同目录的 manifest/before 文件保留 sibling 布局，文件字节不改，档案模式收紧为 0600，原模式保存在计划中。代码是可校验的恢复材料，原代码树可按 source identity/reference_map 重建；档案不是另一个可写安装。

新账仅替换 `backup_manifest` 为核验后的档案路径；旧值同时保存在原始旧账和 `source-identity.json` 的 original_backup_manifests 中。projects、授权、实际库位置、ownership、指纹、消费者、Evidence 原文、四态与 runtime 状态不归零、不升格。runtime 的原 evidence_path 字符串不改：schema=2 用已核验 reference_map 中的档案路径作为校验视图，返回/持久化的数据仍保留原值，schema=1 验证器不放宽。machine 不伪造项目消费者。

自由文本 Evidence 保留原文，不猜测拆分长字符串；精确文件路径可直接归档，组合引用的文件依赖由调用者通过 `evidence_files` 明确枚举并随计划批准。外部 URL/纯人类确认引用不触发网络读取。未知事务格式或未结束的旧事务拒绝迁移，先处理其旧现场；不放宽 v1 验证器。

## 切换与恢复

锁顺序固定为 HOME 安装锁 → 旧来源锁（规范路径排序）→ var 写锁 → transaction 子锁。预览不拿锁；已有锁在执行前被发现即停止。写阶段复用既有原子文件/锁内核，加迁移 journal 记录目录、复制、unlink/mkdir、redirect、最终提交的 intent；文件及相关目录项均同步，写后读回。

旧 registry 被非空真实目录替换，内含 0400 redirect.json。实际 `aff8864` 旧代码被导出到夹具，未改源码，用它验证目录触发 `path_conflict` 而不是坏 JSON 空账重建。多份已知旧账必须同字节，全部封堵，不能按 mtime 选一个。

V 最后提交；V 和所有 tombstone 已是 after 时，继续恢复仅从已核验档案完成收尾，不依赖旧代码/旧备份仍存在，也不重写 V。在 journal 收尾完成前，schema=2 的写者与 check 通过 registry 门禁识别 interrupted。journal 已完成但硬退出遗留迁移锁时，只允许显式完成锁移交，不重新导入、不改写 V、不开放已完成迁移的降级。无迁移 owner 的旧锁或不能证明进程退出的锁不自动删除，保留现场供人工核对。

六类台账现场已按函数逻辑区分：仅旧账；仅有效 V；无可信 journal 的双普通账冲突；可信未完成 journal 的已知 before/after 双账；指纹/身份/来源变化冲突；V + 匹配 tombstone。普通入口均不代替恢复；已知 before/after 继续或回滚，第三种状态停止。完成后不再普通重迁，缺失或被改 tombstone 也不会降回首装。

## 证据与边界

原始测试输出、argv/退出码、进程竞争与硬退出记录在 `raw/`。进程观察记录由测试驱动显式写在测试 HOME 外，不是被测迁移命令的隐式写入；记录实际结果，不生成独立验收判定脚本。

M4-03 涉及 B1 的旧产品/双账/中断门禁、B4 的 m2-schema1 状态转换与恢复、B5 的台账/锁/恢复证据移交；不关闭代码升级/首装/v0 内容复制/生命周期/执行器运行时各项。

共享工作区与 `cfe0ac1 + M4-03` 临时检出的测试结果分别记录，不能用后者冒充包含并行 M4-05 改动的端到端验收。没有真实机器迁移、真实产品安装、执行器新会话或其他平台验证；主 Agent 独立判定。

## 测试交接索引

- 最终隔离检出：279 单测、57 集成，退出码均为 0；见 `raw/final-isolated-unit.log`、`raw/final-isolated-integration.log`。检出基线、复制文件和最终 SHA256 见 `raw/isolated-checkout-provenance.json`、`raw/final-source-provenance.json`，最终文件与共享工作区本任务四个源码/测试文件逐个比对相同。
- 最终定向套件：27 单测、4 进程集成，退出码均为 0；见 `raw/final-scoped-*.log`。全量集成保留既有 PTY 测试的 ResourceWarning 原始输出，未过滤。
- 较早共享工作区全量：277 单测，退出码 1（2 failures、3 errors）；57 集成，退出码 0。单测失败是并行 `paths.py` 对旧夹具缺失 `user_skill_roots` 的 3 个 KeyError，以及 2 个路径占位符断言收到 `agents_table_invalid`；未修改其写集。该次尚未添加本任务最后两条单测，不能与最终隔离计数混同。见 `raw/shared-unit.log`、`raw/shared-integration.log`。
- `raw/commands.json` 记录命令、cwd、退出码；`raw/m403-code.patch` 仅含 registry/migrate 与本任务两套测试的 diff，不包含并行改动或本证据目录；`raw/process-observations.jsonl` 记录多轮真实子进程 argv/返回值和恢复现场，不是验收判定。

## 最新用户裁定同步

主 Agent 已通知 C 改为 `~/.local/share/agent-group-memory`，独立代码版本并支持回退；R 仍为 `~/.agents-group`，`~/.agents/skills` 原地不动。layout/DESIGN/决策单修订由主 Agent 负责，本任务未改写集外文件，也没有安装或搬迁 C。本任务通过 `RuntimeLayout` 属性定位并绑定完整 `describe()`，测试未写死旧 C 路径；布局修订后，旧布局下生成的批准计划必须重新预览，不能复用旧计划指纹。

上述最终隔离全量基于 cfe0ac1 的 layout；主 Agent 合并新 C 后仍需进行整合验证。产品代码版本回退属于后续安装/升级合同，不等于重新开放已经关闭的台账迁移降级入口。Python≥3.9 与 Git 为已有运行时前置，缺失只诊断并给安装步骤；本任务没有系统依赖自动安装。R2/R3 修复按主 Agent 排期在 M4-03 后执行，未混入本次补丁。
