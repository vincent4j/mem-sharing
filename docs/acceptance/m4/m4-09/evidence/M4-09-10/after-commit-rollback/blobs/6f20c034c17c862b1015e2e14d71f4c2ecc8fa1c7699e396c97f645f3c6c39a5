# M4-04 实施交接（不是验收判定）

基线 `fbddc93`。写集：新增 `scripts/agm_core/user_install.py`、`legacy_import.py`、两套 `test_m404*`；经主 Agent 消息授权，最小扩展 `user_entries.py` 的首装预览接口。未改 layout/detect/paths/agents.json/registry/transaction；不 commit/push，不操作真实安装。

## 机器路由与接口

`inspect_machine(request)` 为只读判别，返回 scene/channel/observations/错误与独立 content_candidate；不创建目录、锁、日志或缓存。

| 七类现场 | 返回与动作 |
|---|---|
| R 缺失/完全空，无外部产品信号 | empty / fresh |
| 非空、可枚举、没有产品痕迹 | v0 / legacy_copy；执行封皮必须 confirmed_v0 |
| 严格 schema1 + 显式旧来源提交/完整代码身份；或已安装 M4 的白名单来源 | valid_old / upgrade；本模块拒绝首装覆盖，由 M4-03/M4-07 承接 |
| 有效 V、代码清单与请求版本/来源相同 | same / upgrade；判别零写，不重做导入 |
| 更高 schema/结构/代码，或没有转换白名单 | future / stop |
| 坏台账、双账、缺创建证据、身份/代码不符 | bad_registry / stop；不调用项目级 rebuild |
| 锁、未完成/不可解释的 bootstrap | interrupted / stop；必须显式恢复 |

无 V 但存在 C、var、产品 Skill/用户 marker、未知恢复材料等另报 abnormal / stop，不猜 v0。检查已知路径及显式来源，不扫描用户全部磁盘。HOME 的系统祖先别名在规划前解析为 canonical 目标，批准绑定展示后的路径；C 的 home 以下父链和叶子单独拒绝 symlink。

`legacy_registries` 是已知旧账绝对路径清单；`legacy_source_commits` 逐路径绑定旧代码提交。安装源本身的 `scripts/registry.json`、锁和恢复材料也在检查范围内。旧产品账本与 R 中 v0 记忆同时存在时，返回 upgrade + content_candidate；不删除旧账、不同步其授权到 v0 内容、不用首装覆盖。`legacy_import.plan_import(R, op)` 独立提供内容子计划；旧产品转换由后续升级编排组合，M4-04 不执行升级。

`plan_install(request)` 只接受 fresh/legacy_copy，生成独立 schema=1 的 install-machine envelope；`execute_install(plan, approval, request=..., hook=...)` 要求完整计划加 confirmed_at/reference 的精确确认。v0 的顶层 legacy_identity=confirmed_v0、source_tree_sha256、op 与完整清单必须一同批准。身份警示写在 legacy_import.identity_warning 中，明确无法排除旧台账被删及不得并发运行旧同步器。

request 必须显式给 home、platform_config、source；没有 HOME 默认值。source 精确字段：root（已存在 canonical checkout/export）、url、commit（40/64 hex）、version（发行 SemVer）、files（相对路径→SHA256）。文件必须普通文件、不得路径逃逸或碰撞，Python 代码按 3.9 语法解析；有 Git 元数据时只读核对 HEAD 与清单内 dirty 状态。代码清单记录普通模式，不传播 setuid/setgid。导出目录的提交身份由明确来源请求承担，内容始终按清单核验，不声称额外供应链审计。生产首装限定 macOS，要求已有 Git；缺失给诊断，不装系统依赖。Python 解释器能否启动由外层入口负责。

## 首装、C 与用户入口

创建 R/memories（索引与 topics）、references、skills、mcp、backups、var；不接管 v0 mcp，已存在的 mcp 保留原件。C 固定为 layout.code=`H/.local/share/agent-group-memory`，复制批准的代码并落 `.agm-code-manifest.json`；提交前核对完整受管树，额外/缺失/变更节点停止。`H/.agents/skills` 不搬迁、不接管；R/skills 不作为产品代码位置。

Bootstrap `H/.agents-group-install-<op>/` 持久保存计划/批准/journal、before 材料、固定 tools/agm_core、code-source、用户入口事务恢复材料。写前记 intent、写后读回；工具包来自当前内核并以逐文件哈希绑定，不依赖正在落位的 C。计划 changes 显示内容写项、目录创建、用户入口子计划、V 最后提交与操作元数据/锁的限定范围。运行时生成的事务文件名/观察时间属于列出的操作元数据命名空间，不伪造提前确定的回执哈希。

首装直接调用 `user_entries.run_user_entries`；不复制模板或探测实现。为保持实际 V 最后提交，内部 `_StagedLayout` 仅把该次调用的工作台账/嵌套锁/恢复材料定位到 bootstrap，公共 root、C、所有用户目标仍为真实目标。它不是普通 runtime 的 fallback 或第二活动账；外层始终持 H 安装锁 → var 写锁 → transaction 子锁，普通写者被挡住，实际 V 在全部输出核验后才出现。首次用户入口 created 证据保留其真实 bootstrap 事务 manifest，最终 V 逐字段保留它们。

经主 Agent 授权的 verified_product_source 扩展：只在内部 ContextVar 安装器上下文中有效，普通装配请求直接拒绝；预览仅允许以该源代替 C/SKILL.md 的存在性检查，Skill 目标仍是 C。子计划绑定 SKILL SHA256，执行要求 C 存在且与批准指纹相同；首装外层还绑定并复验整个代码清单。三条指定接口回归及普通请求拒绝在 test_installer_only_preview_extension_binds_source_and_execution_C 中覆盖。

默认只装配 detect 的 installed 集合，absent/unknown 的指纹/状态在 agent_facts 中报告，不创建其用户目录；显式指定未安装执行器由原 API 在预览阶段拒绝。初始 V 的 product 分开记 schema=2、structure=1、发行代码版本及来源；machine 有自身 agents/objects，不伪造项目或消费者。

## v0 快照与原文阅读包

只枚举/复制 memories、references、skills；旧脚本/散落状态/mcp 留原地。完整源清单记录相对路径、类型、普通权限、文件长度与 SHA256、链接文本及其哈希、目录和总指纹。先在 bootstrap/source 完成并核验、封存，再按持久化的同一 intent 移到 R/backups/v0-<op>/source。Darwin 移动只读目录所需的临时解封/再次封存在同一恢复协议内，不跳过核验。

R/memories/legacy-v0-<op>/ 镜像批准的三目录原文；旧 MEMORY.md 原始字节同时保存在快照和阅读包，不改正文。根 MEMORY 改为短索引并链接阅读包；其他原位主题/参考/Skills 核验复用，不产生产品删除权。文件目标不存在才复制；同类型同字节可复用；不同字节、不同类型、同名包/快照均停止，不加后缀绕过。

外部/绝对/悬空 symlink 仅记录文本并留原位，不遍历外部目标或在阅读包激活；内部链接按批准包内路径保留。循环、特殊文件、大小写/Unicode 碰撞停止。Markdown 内联/引用定义中的可解析本地目标会作来源/镜像检查：原已失效只报告，镜像新增有效链接断裂则规划失败；外部 URI 不访问、不复制，绝对本地依赖如实报告原现场依赖。

import-manifest.json 按 prepared → snapshot_complete → applying → outputs_verified → committed 更新；终态只能在 V 读回后落下。包含计划/批准身份、源总指纹、快照、目标、排除项、逐项 before/after、处置及完成观察、V 指纹；V.legacy_import 保存同一 op/source/manifest。提交前复核 source 的 before/after 差异，只扣除本次精确新增目标和索引替换，其他新增/变更/缺失停止。快照本身、阅读包及 C 的额外内容也会停止提交。

## 显式恢复与边界

`plan_recovery(journal_path, action='continue'|'rollback')` 为只读恢复预览；`recover_install(recovery_plan, exact_approval, request=...)` 验证 journal/计划/批准、before/after、快照、工具及第三种字节后执行。沿用 M4-03 的带 PID/op/plan hash 锁所有者协议；仅明确确认退出的所有者、精确 inode/内容批准可清理，未知/活跃所有者停止。op 内的嵌套入口锁还须有已证明退出的外层 owner 才可按精确 inode 批准清理。

用户入口中途退出时，先用原 Transaction manifest 恢复其部分事务，再以同一安装计划继续；已经完成的用户入口则验证 staged ledger/after，不重放 created 计划。恢复适配器先验证原事务仅含批准叶子与其精确父目录，才允许通用恢复处理新建父目录。rollback 保留源快照/工具/证据，只恢复本次输出与入口、只清理本次创建且仍空的目录，拒绝第三种内容。

V 已是 after、所有输出均是 after 时只补收尾，不依赖原 checkout，不重写 V、不二次复制。普通重跑已关闭 op 被拒绝；相同版本判别不再扫描复制 v0。恢复工具包使用方法：`python3 -B`，将 `<bootstrap>/tools` 加入 sys.path 后 import agm_core.user_install，使用同样两个恢复 API；后续独立 CLI 由 M4-08 承接。含应用签名测试后端的合成恢复调用仍须显式提供相同 detect_runner；JSON 不承载任意可执行回调。

这是协作锁和读回协议，不宣称全树原子切换、消灭所有非协作写者竞态、抵御同用户恶意篡改或实现系统级禁用旧管理器。未知写者/损坏恢复材料保留现场停，不猜测修复。

## 测试与证据

新增 17 单测、2 进程集成方法；软中断为五个阶段×继续/回滚，硬退出为六个阶段（含用户入口只写第一文件时）×继续/回滚，另有删除原 checkout 后用固定工具包收尾、回滚 intent 内外部改写台账/索引仍保留外部内容。保留原文原位、旧产品/内容共存、预览源漂移、提交前漂移、部分目标异字节、外部链接不激活、七类路由、空 HOME 零写及三条 verified source 接口回归均有对应断言。

最终全量日志、命令/退出码、源码 SHA256 和限定 diff 在 raw。`process-observations.jsonl` 保留多轮研发原始记录，最终完整进程运行标识为 `fbddc93-m404-delivery`，不把较早版本记录混成最终证据。日志中的既有 PTY ResourceWarning 未过滤。没有验收判定脚本，由主 Agent 独立判定。

未实现/未验证：升级执行（M4-07）、独立安装 CLI（M4-08）、真实机器首装/迁移、新执行器会话加载、导入 Skills 的运行或安全审查、MCP 配置、Windows/Linux 生产写入。C 独立版本切换/回退布局仍由 M4-07 承接；本次首装落位当前 C，未改 layout。
