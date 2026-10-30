# M2-07 幂等与故障矩阵验收

状态:已完成。依据 docs/plan/tasks.md M2-07、DESIGN.md v1.1;前置为已合流的 M2-04 enable(965af63)、M2-05 check(88e0fbf)、M2-06 remove(cc67e7d)。本任务只交付测试与本文档,不修改任何产品源码;发现的行为观察见 §5,未自行修复。

- 交付者:突突兔(ZCode 会话)。观测环境:macOS 26.6.2 arm64,CPython 3.14.3,git available。
- 交付物:`tests/unit/test_m207_faults.py`(7 项)、`tests/integration/test_m207_cli_cycle.py`(13 项)、本文档。
- 实际运行(仓库根,两轮复跑均绿):

```text
$ python3 -m unittest discover -s tests/unit
Ran 222 tests in 42.844s    # 基线 215 + M2-07 新增 7
OK
$ python3 -m unittest discover -s tests/integration
Ran 53 tests in 36.373s    # 基线 40 + M2-07 新增 13
OK
```

## 1. 隔离与证据口径

- 集成层整体拷贝真实安装树(`agm.py` + `agm_core/` + `agents.json` + `templates/`)到临时目录,临时 `HOME`(子进程 env 注入)、临时项目仓库(真实 `git init`)、Keeper 桩 checkout(git 仓库 + 真实子进程脚本);全程不触碰真实 `scripts/registry.json`、真实入口或记录库。单元层经文档化 Python-only 注入点(`install_dir`/`runner`/`registry_path`)隔离,文件行为全部真实。
- read-only/rollback 断言一律为真实文件证据:文件/符号链接记录(类型, 内容, mtime_ns)三元组前后比对;目录只记存在性(目录 mtime 会因被排除项写入联动,非输出字节证据)。排除项及理由:registry.json(每次 enable 按设计刷新证据时间戳)、backups/(新事务 manifest)、项目 `.git/`(git 自身触碰,非 AGM 输出)。没有以 mock 成功替代文件行为的断言。
- Keeper 桩语义:install 预览/批准/ensure-bridge 按上游合同返回 scope 校验 JSON;init 桩对已完整库零改写(建模上游幂等 init),未完成时建库;`mode` 文件注入 migration(rc=3)/partial(rc=2)故障。
- 退出码合同:D-M2-05(0 完成、1 缺口、2 失败/冲突、3 迁移、5 待授权)在所有场景按实际 rc 断言。

## 2. 幂等矩阵

| # | 场景 | 操作序列 | 结果 | 证据测试 |
|---|---|---|---|---|
| I-1 | 首装→幂等重装 | 批准 enable --memory → 再次 enable(无任何参数) | 二次 rc=0、changes=[],项目+HOME+安装树输出字节与 mtime 全等 | cli_cycle.test_second_enable_changes_no_byte_or_mtime |
| I-2 | 桥接被清空→check 只报告 | 删除 AGENTS.md 内 keeper 块(保留其余字节)→ check | rc=1、object_missing;check 前后全树字节/mtime 不变(只读证明) | cli_cycle.test_cleared_bridge_check_only_reports_then_enable_repairs |
| I-3 | 桥接被清空→enable 幂等补装 | I-2 之后 enable(无参数) | rc=0,块字节精确复原,块外字节原样;不需新批准(登记一致修复) | 同上 |
| I-4 | 库目录被外部删除 | enable --memory → 删 store → check → enable | check 报 store_missing 不重建;enable rc=0 重建库且不需新批准 | faults.test_store_deleted_check_reports_and_enable_reinits_without_new_approval |
| I-5 | 用户追加原生日志后幂等 | enable → 用户向 WorkBuddy 入口追加二进制原生日志 → enable | rc=0、changes=[]、字节与 mtime 不变 | faults.test_workbuddy_native_bytes_survive_enable_and_remove_cycle |
| I-6 | 二次 remove | enable --memory → remove(批准)→ remove(交互) | rc=0、changes=[],零变更完成;非交互无批准文件时仍保守返回 5 | cli_cycle.test_remove_twice_then_reenable_full_cycle |
| I-7 | 装→拆→装全周期 | enable → remove → check → enable | 拆后 check rc=1 报缺口;重装需新批准(预览 rc=5)→批准后 rc=0、四态 ready | 同 I-6 |
| I-8 | check --all 重复巡检 | 两项目 enable → check --all | rc=0;两项目+HOME+安装树(含 registry)快照全等,零写入 | cli_cycle.test_check_all_two_projects_zero_write |

## 3. 双安装顺序矩阵

| # | 场景 | 操作序列 | 结果 | 证据测试 |
|---|---|---|---|---|
| O-1 | 先 Group 后 Keeper | enable --no-memory → 置项目 Skill 链接 → enable --memory | 第二步完成;四态 ready;基座块 created、keeper 桥接补装;先置链接登记 reused 不改写 | cli_cycle.test_group_first_then_keeper |
| O-2 | 先 Keeper 后 Group | 用户已用上游装好(AGENTS.md/CLAUDE.md 含桥接块+用户前后缀字节、四链接)→ enable --memory | 用户前缀 `\r\n` 与尾部字节原样;桥接块登记 reused;既有 AGENTS.md 整体按 reused 文件保护,不追加基座块(见 §5-3) | cli_cycle.test_keeper_first_adoption_preserves_user_bytes |
| O-3 | 两项目共享用户级入口 | 项目 A enable → 项目 B enable → remove A → remove B | 共享对象 consumers 正确增减;两轮 remove 全程入口字节不变;最后消费者移除后对象与 created 证据仍保留(O2) | faults.test_shared_user_entry_two_project_lifecycle |

## 4. 故障与边界矩阵

| # | 场景 | 操作 | 结果 | 证据测试 |
|---|---|---|---|---|
| F-1 | 拒绝记忆持久化 | enable --no-memory → check → enable(无参数) | check rc=1 报 memory_not_enabled;重复 enable 不翻转选择,不建库 | cli_cycle.test_no_memory_persisted_check_gap_and_no_silent_flip |
| F-2 | no→yes 需显式批准 | enable --no-memory → enable --memory | 预览 rc=5,登记仍为 no;仅新批准后置 yes 并建库 | faults.test_no_to_yes_requires_explicit_approval_no_silent_flip |
| F-3 | 库位置自定义 | 批准 store_path=自定义 → enable → 幂等重装 | 库建在自定义位置;context-keeper.json 指向它;registry 登记一致;重装不移动位置 | cli_cycle.test_custom_store_location_via_approval |
| F-4 | 批准位置与现场配置冲突 | 预写 context-keeper.json 指向别处 → 批准另一位置 | rc=2 approval_mismatch;不建库、不改现场配置、不写 AGENTS.md | cli_cycle.test_approved_store_conflicting_with_local_config_rejected |
| F-5 | 复制目录冲突 | `.codex/skills/context-keeper` 为真实目录(好链接在 `.agents` 保源发现)→ enable --memory | rc=2 path_conflict;目录内容原样;无 registry、无 AGENTS.md | cli_cycle.test_skill_copy_directory_conflict_rejected_untouched |
| F-6 | registry 损坏 × check | 写入损坏字节 → check | rc=1 + registry 校验失败警告;损坏字节原样(零写入) | cli_cycle.test_corrupt_registry_… 与 faults.test_registry_corrupt_… |
| F-7 | registry 损坏 × remove | 损坏后带结构合法批准文件 remove | rc=2 registry_invalid;不删任何输出 | 同上两测试 |
| F-8 | registry 损坏 × enable 重建 | 损坏 → enable 预览 → 批准重建 | 预览 rc=5;批准后 rc=0,warning "Corrupt registry backed up";损坏字节存留备份;所有权降级不恢复 created | cli_cycle.test_corrupt_registry_conservative_across_cli_commands |
| F-9 | registry 整体丢失 | 删除 registry → enable/check/remove | enable rc=5;check rc=1(仅内存观察);remove rc=0 声明不推断删除权,零删除零重建 | faults.test_registry_missing_all_three_commands_conservative |
| F-10 | AGENTS.md 落点被目录占用 | mkdir AGENTS.md → enable | rc=2 path_conflict;目录内容原样;无 registry/备份/CLAUDE.md | faults.test_agents_md_replaced_by_directory_rejected_before_any_write |
| F-11 | Provider init 部分失败 | 已有 no-memory 装配 → mode=partial → enable --memory | rc=2 keeper_failed;旧 registry/AGENTS.md 字节不变(回滚);部分库资产保留现场;故障排除后同流程重试成功 | cli_cycle.test_partial_init_failure_keeps_prior_state_and_store_assets |
| F-12 | remove 保留边界 | enable --memory → remove(批准) | 记录库/context-keeper.json 原样;CLAUDE.md 的 @AGENTS.md 引用保留(import 受 schema v1 保护);created 块摘除、reused 链接(.agents)保留 | cli_cycle.test_remove_twice_then_reenable_full_cycle |
| F-13 | 全周期卫生 | enable → check → remove 全链 | 无 __pycache__ 残留(冷启动零写入)、.agm.lock 正常释放 | cli_cycle.test_no_pycache_or_lock_residue |
| F-14 | 单项目漂移定位 | 两项目健康 → 损坏项目 2 基座块 → check --all | rc=1;缺口仅出现在项目 2,项目 1 无缺口 | cli_cycle.test_check_all_two_projects_zero_write |

## 5. 行为观察(非缺陷裁定,交主 Agent 判断)

以下为测试过程中确认的产品行为,与直觉预期有差异但均可从 M2-04/05/06 实现或 schema v1 约束推出;本人未修改源码,仅登记:

1. **幂等 enable 仍重写 registry.json 并新建备份 manifest**:每次 enable(含零输出变更的幂等运行)都会刷新登记中的证据时间戳,registry 字节变化并产生新备份目录。任务验收"无字节/mtime 变化"的口径因此限定于受管输出(入口/块/链接/用户入口);registry 属记账文件按设计刷新。若期望"真正零写"的幂等,需要内核跳过时间戳刷新——属设计取舍,不是实现错误。
2. **`--memory` 的幂等重装不需要批准文件**:登记一致时 `--memory` 重装走"一致修复"免批准路径(rc=0)。这使"用新批准文件改库位置"的场景实际上不可达(根本没有批准核对机会);位置锁定由 F-4 的"与现场配置冲突即拒"兜住。安全性等价,但与"enable 是写命令须批准"的直觉有差异。
3. **既有 AGENTS.md 不会被追加基座块**:AGENTS.md 预先存在时(先 Keeper 后 Group),enable 把整文件登记为 reused 文件对象,不写入 `agent-group-memory:rules` 基座块;基座块仅在 AGENTS.md 缺失时创建。符合"已有规则不自动改写"的 M1 边界,但意味着该顺序下 D1"唯一规则源"标记不存在,后续 check 对该文件的基线核对走整文件指纹。
4. **created 块 remove 后留残余字节**:enable 在新文件上创建的两个受管块(基座+桥接)remove 时按块精确摘除,块间连接符(`\n`)留在文件里,产生仅含残余字节的 AGENTS.md 而非删除整文件。字节精确性优先;是否应清理由主 Agent 裁定。

## 6. 未验收范围

- 未覆盖真实上游 context-keeper 安装器(用桩按 M2-04 合同建模);真实上游行为由 M2-08 两项目复制验收。
- Windows/Linux 平台、worktree、AGENTS.override 实际劫持效果、执行器新会话接力:分别属 M2-09/M1-06/M2-08 范围。
- registry 并发写(同一 registry 写操作串行由任务书约定,本轮未注入并发竞态)。

## 6. 主 Agent 裁定(2026-10-29)

| 观察 | 裁定 |
|---|---|
| 1. 幂等 enable 仍刷新 registry 证据时间戳并新建备份 | **接受,属设计取舍**:registry 是本机记账文件,刷新执行证据合理;"零字节变化"约束仅适用于受管输出;不追求记账绝对零写 |
| 2. `--memory` 幂等重装免批准文件;改库位置由"context-keeper.json 冲突即 rc=2"兜底 | **接受**:安全性等价(位置锁定仍强制),差异仅在于批准粒度;记入 known-behavior |
| 3. 先 Keeper 后 Group 顺序下,既有 AGENTS.md 按 reused 整文件保护,不追加基座标记块 | **接受**:D1 标记不存在时 check 走整文件指纹核对,语义正确 |
| 4. remove 摘除全部受管块后留下仅含 `\n` 的空 AGENTS.md 而非删文件 | **接受现状**:字节精确性优先;空文件清理列为 M2-9 前可选打磨,不阻塞 |

以上为行为认定,不构成设计变更;DESIGN/architecture 无需改动。
