# M4-07 交接（待主 Agent 独立验收）

基线 `27d6e26`。§12 布局及两项补充经主 Agent 批准后实现：库存持久保留；所有新首装/升级均先登记库存再换 C。产品仓库未 commit/push，未运行真实 HOME 的项目命令。工作中出现的 AGENTS.md / CLAUDE.md 修改由用户/协调侧产生，本任务未写入这两个文件，交付 diff 不包含它们。

最终全量：**408 单元 + 66 集成 = 474**，两个命令退出码均 0；基线的 387+62 未删除、未放宽，新增 21 条单元和 4 条真实快照集成。`git diff --check` 退出 0。

冻结 P=`27d6e264496184a85dc015039885ebdae174f89d`，T=`f5d3add71e7cf35039c0907728ec883151a9f6f6`（仅临时仓库提交，真实父提交为 P）。产品源码 SHA 与冻结产物逐项一致。

## 布局与实现

```text
H/.local/share/agent-group-memory/                         C，真实活动目录
H/.local/share/agent-group-memory-versions/                K，持久库存，不自动清理
  <SemVer>/<tree_sha256>/code/                            完整发行代码（只读文件）
  <SemVer>/<tree_sha256>/{release,complete}.json            精确清单及完成收据
  activations/<op>-{before,after}.json                     自包含提交证明，独立于历史 journal/备份
H/.agents-group-install-<op>/{journal.json,recover.py,tools/,code-source/}
H/.agents-group-upgrade.json                              升级/恢复门禁标记
R/backups/upgrade-<op>/{code-before/,registry-before.json}  本次操作恢复材料
R/var/registry.json                                       V，唯一活动版本权威，最后提交
```

C 和 Skill 投影路径不变，不把 C 改成链接、不整体 rename C。K 是回退能力的持久本体，不适用 backups 的 90 天提醒保留期，也不自动清理。新库存先暂存在 K 内、核验完整后原子 rename；不假设 HOME bootstrap 和 K 跨挂载点 rename 可用。

生产文件：

- `versions.py`：库存规划/严格校验、持久登记、原子槽切换、安装历史收据。使用前复核字节/类型/模式；成功收据内嵌原批准计划与提交证明，不依赖旧 checkout、历史安装/升级的 bootstrap journal 或 code-before 备份继续存在。项目 created 单元的创建证据仍按 registry 严格验证，不因代码回退放宽。只读权限不视为不可篡改保证。
- `upgrade.py`：显式升级/回退规划、精确转换表、代码 before 归档、逐文件原子替换/删除、读回、V 最后提交、独立批准恢复、固定工具包和恢复入口；M2/M3 复用 migrate 原内核。
- `user_install.py`：新首装先库存后 C；新 install plan 使用 schema_version=2（这是批准计划版本，非台账版本）；对旧 P 已完成/已回滚 plan v1 仅作严格只读诊断，不把缺库存字段的旧计划用于新写入。识别升级 journal/标记。
- `layout.py`：三项目命令和机器用户入口通过共享解析拒绝升级中标记，报告 machine_upgrade_pending；check 不修复。
- `agm.py`：在载入产品模块前禁止 bytecode 写入，避免普通 CLI 使用生成未归属 __pycache__ 而污染受管代码清单。命令和批准字段集未变。

持久库存也纳入机器判别证据；台账/C 被删但库存残留时停止，绝不伪装 fresh/v0。

没有修改 registry schema=1/2、migrate、transaction、user_entries、detect、paths、agents.json 或上游源码；没有改旧测试断言。

## 固定接口（供 M4-08 接线）

`upgrade.plan_upgrade(request)` 为纯读取，返回精确批准计划；`execute_upgrade(plan, approval, request=request)` 执行。非 noop 的 approval 必须逐字段等于计划并附 confirmed_at/reference；noop 可无批准，零锁/零 journal/零库存补建/零 mtime 更新。重复已完成 op 的同版新预览仍可 noop；不得直接把旧升级批准当新批准重放。

request 必须给 home、platform_config、已核验 source（沿 user_install._source 的 root/url/commit/version/files 合同）；可给 operation_id。`conversions` 来自所核验发行的精确支持转换表，且纳入批准，格式：

```json
{
  "before": {"schema_version": 2, "product_structure_version": 1,
             "product_code_version": "0.4.0", "source": {"url": "…", "commit": "…", "tree_sha256": "…"}},
  "after":  {"schema_version": 2, "product_structure_version": 1,
             "product_code_version": "0.4.1", "source": {"url": "…", "commit": "…", "tree_sha256": "…"}},
  "direction": "upgrade",
  "entries": "preserve"
}
```

目前明确支持 code-only/entries=preserve 转换；若 agents.json 或 user_entries.py 的发现/入口合同改变，拒绝，必须另有转换实现。版本大小仅作额外拒绝条件，绝不代替精确白名单；未来版即使错误列入普通升级表也拒绝反向覆盖。同版不同来源/清单不当作无漂移重装。

主动回退：`direction=rollback`、精确反向转换；推荐 request 给 `rollback_target={version,tree_sha256}`，直接从已安装库存读取，不需要旧 checkout（此路径 source 可省略）。无成功提交历史收据、库存不完整、当前状态不兼容则停止。回退只调整当前 V 的 product 版本/来源/操作信息，保留当前 projects/shared_objects/machine/migration/legacy_import 以及 installation_id，包括升级后新注册的项目与授权；不恢复整份过时账本。

机器判别 `user_install.inspect_machine` 复用 conversions 的精确验证，支持的 P 返回 valid_old/upgrade；没有合法转换仍报 future/stop，不用旧的宽泛 supported_sources 列表授予执行权限。

M2/M3：request 给 legacy_registries、legacy_source_commits，可给 evidence_files。子迁移计划以 `migration_plan` 完整绑定外层批准，不混同 v0；旧账 raw bytes/来源/恢复材料/reference_map/tombstone/锁序沿 M4-03。旧写者已冻结、持有迁移锁后的 before_commit 钩子内完成库存和代码，再由原迁移内核提交 V；不会先暴露一个“已升级但无代码”的完成台账。外层和子 journal 同时保留，恢复计划嵌入子迁移恢复场景/批准。

同版后装执行器：`run_same_version_entries(request)` 先证明同版无漂移，再调用原 user_entries API，显示并批准其单独接入计划；不因为代码 noop 而静默扩装执行器，不刷 product 版本/操作时间。

## 恢复协议与调用

六阶段为 prepare/archive/inventory/code/verify/commit。先切换不依赖新模块的 layout 门禁，再切换其他可执行代码，降低混版期间入口继续执行的范围。旧清单独占而新清单不再引用的空目录仅在仍为空时移除，rollback 可按原目录重建；不删非空目录。提交 V 前重新核验全部 before 备份和固定工具。每阶段有 before_phase:<name> / after_phase:<name>；库存 rename、逐文件 replace、V commit 另有 before/after 钩子，具体原始矩阵见日志。每次变更先持久记 intent。原安装锁→原 scripts 锁→V 写锁→事务子锁的顺序保留。

- V=before，输出只为 before/after：同一 op 可以继续或从逐项核验后的 code-before 逆序回滚。
- V=after 且所有输出 after：只补库存历史、标记/journal/锁收尾，不重新 stage/替换/转换；rollback 请求明确拒绝，后续若要退版本需主动回退新批准。
- V=after 且混合，或代码/账本第三种字节、坏 before 备份、工具包漂移：停止，不猜成功，不覆盖用户改动。
- 锁接管只允许已退出 PID、精确 inode/device/owner bytes 和操作/计划一致，且已经出现在独立恢复批准中；不自动偷锁。现有协作锁无法消除非协作写者最后一刻的竞态，仍使用 R3 写前 expected 检查。

正常 API：`plan_recovery(journal_path, action='continue'|'rollback')` 后将整个计划加确认封皮交给 `recover_upgrade`。固定入口可从 bootstrap 直接运行，不从 C import：

```text
python3 -B <bootstrap>/recover.py preview <bootstrap>/journal.json continue
python3 -B <bootstrap>/recover.py apply <explicitly-approved-recovery-plan.json>
```

入口的内容、固定 agm_core 工具包哈希、所有版本及输出哈希均绑定原计划。真实测试在 C/user_install.py 已被替换、其余代码仍混合且 T 来源目录不可访问时，通过该入口继续完成升级并运行 T CLI。

## 证据与测试范围

三个新测试文件：`tests/unit/test_m407_upgrade.py`、`test_m407_legacy_upgrade.py`、`tests/integration/test_m407_real_upgrade.py`；原测试未删、未放宽。矩阵同时覆盖首装库存 rename 先于 C、六阶段前后故障、每个真实代码文件替换前后×继续/回滚、库存 rename 与 V 提交窗口、硬退出锁移交、同版全 HOME mtime、未来/坏账/dirty/异库存、第三态、V after 混合、备份损坏、机器门禁和同版新增执行器单独授权。

日志中 `PHASE commit after rollback completed` / `REAL_PHASE commit rollback completed finish_only` 的 rollback 是“原请求标签”：测试先断言 rollback 被拒绝，再提交 continue 恢复计划完成收尾，不表示允许提交后崩溃回滚。

`frozen/releases.json` 给出 P/T 的真实 Git commit 和逐文件哈希；P=27d6e26，T 是其真实子提交，含实际升级/库存代码，非修改版本字符串制造差异。P 由 P 自身内核安装完成，再运行安装后的 P check 命令；随后 T 工具包完成升级、回退及故障恢复。T 回退到 P 后仍能运行 P CLI，用户 bytes 和升级后新项目授权保留。

`frozen/P.tar` / `T.tar` 保存两份实际代码包；`T.bundle` 是以仓库内已有 P 为 prerequisite 的隔离 Git 增量包（未将 T commit 写回产品仓库）。可在另一个临时 clone 中导入 bundle 复验真实祖先关系，或按 releases.json 核验 tar 字节。冻结产物对应的实际运行日志见 integration.log；归档文件权限规范为 tar.umask=0022，额外的逐字节/模式清单和同一 T commit 对照见 artifacts.log。全部命令、退出码见 commands.txt；完整 source/test diff 与哈希见 working-tree.diff / sources.json。

## 边界与未验收范围

这是 macOS、Python 标准库和 Git 下的隔离夹具/真实代码快照证据，未操作真实 HOME，未启动/登录真实执行器，未验收新会话/模型调用。Python 3.9 做语法解析兼容核验，测试执行使用当前 Python，不冒充 Python 3.9 实机运行。非 macOS not-run。

不支持未知结构/schema 的逆迁移、任意历史版转换、全产品卸载或库存 GC；不自动下载源代码或系统依赖。M4-08 CLI/文档接线仍待后续任务。paseo-progress 因既有插件缺 zod 无法启动，未更改插件环境，进度通过消息持续报告。本交接不是独立验收判定。
