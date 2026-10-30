# M4-06 交接（待主 Agent 独立验收）

基线：2789ea7。开工时工作区干净；未 commit/push，未运行真实 HOME 的项目命令。生产写集为 entries/enable/remove/check/registry，以及主 Agent 单独授权的最小 agm.py 封皮接线；未改 layout、detect、paths、agents.json、user_install、legacy_import 或上游源码。

全量单元 **387/387**、集成 **62/62**（合计 449）通过，两个命令退出码均 0。相对基线新增 27 条单元、3 条集成；原测试未删除。`git diff --check` 退出码 0。

## 行为与证据

- AGENTS 新建“项目名 + 空规则节”，不再创建/登记受管 base。旧整文件/base marker 记录仅为历史证据：正文可改、marker 可删，不重建、不按旧哈希判漂移；AGENTS 路径永不由 remove 删除。真正 Keeper bridge、停用 guard 仍校验精确字节。
- 新 CLAUDE 引用独立记账：schema=2 项目对象可有 `lifecycle`（version=1、unit_hex、prefix_hex、suffix_hex、file_created、operation_id、container_units），绑定真实事务 before/manifest。严格 schema=1 校验器未放宽。引用/bridge 全部为本工具 created 且去除后无剩余字节时，允许删除新建薄文件；后来加入的用户字节原样保留。旧 reused、缺独立来源的旧 created 薄文件不追认删除权。
- WorkBuddy 的 `.workbuddy/memory` 不存在时不 mkdir、不调用其 provider、不投影其项目 Keeper Skill；报告 native_pending/blocked，执行结果使用 CLI 已有 gaps 状态（退出码 1）。已安装且原生目录存在时沿用上游模板。remove 保留原生目录。
- 默认执行器范围由 detect 的 installed 事实筛选；显式 absent/unknown 停止。CLI 保留“省略 --agent”的 None 语义。已有授权撤销依登记所有权执行，不因执行器后来 absent/unknown 而残留 created 指令。
- 项目 remove 保留 machine 全账、产品代码与用户产品 Skill；复用机器 WorkBuddy 约定时只核对该物理单元，不复制所有权或伪造项目消费者；现有共享 O2 零消费者保留政策未改。
- R1：yes→no 先预览精确撤销计划（含链接 remove），获批后撤 created bridge/项目 Skill 触发链接；记录库和 provider 源码保留。reused/unknown/未登记历史 bridge 保留字节，并在相关入口添加显式禁止自动写记忆的受管 guard。计划列出 reused_conflicts；remove 在 no 状态保留停用 guard，避免旧 reused 指令重激活。恢复 yes 必须批准移除本工具 guard；用户自有 guard 不自动解除。
- R4：check 只读核验 SKILL.md、scripts/install.py、scripts/context_keeper_probe.py 的存在、文件类型/链接、Git 根及可用的获批源码指纹；缺文件报 missing/source_missing，类型异常/字节漂移报 blocked/source_invalid。不导入或调用 provider/probe。

`tests/unit/test_m406_lifecycle.py` 新增 20 条、`test_m406_cli.py` 7 条，`tests/integration/test_m406_cli_lifecycle.py` 3 条。全量及复现原始输出见 unit.log、integration.log；命令/退出码见 commands.txt。工作 diff 见 working-tree.diff，覆盖新测试正文。sources.json 记录被测文件哈希。

R1/R4 的原始反转输出由测试直接打印：`SOURCE source_status=missing`、`DECLINE authorization=no/created_bridges_removed=true/denial_guard=true/store_preserved=true`；真实复制 CLI 子进程另打印 `CLI DECLINE` 与 `CLI SOURCE`。这是隔离夹具证据，不宣称执行器真实新会话已遵守停用指令。

## CLI 字段集矩阵与测试映射

公共必填字段 B：schema_version、command、main_checkout、checkout、git_common_dir、agents、memory_authorization、store_path、provider_source、provider_fingerprints、changes、confirmed_at、reference。

| 命令 | 必填 | 可接受扩展 | 拒绝 |
|---|---|---|---|
| enable-memory | B | installation、native_pending、memory_transition、rebuild、rebuild_confirmation | 所有未知字段；扩展内部未知/缺失字段；不同旧账哈希的 rebuild_confirmation |
| remove-memory | B（memory_authorization=null） | 无 | 全部 enable 扩展、所有未知字段 |
| check-memory | 无批准入口 | 无 | 任何批准封皮（解析器与 validate_approval 均拒绝） |

installation 必须覆盖请求集、每项恰为 status/fingerprint，并与 effective agents 对齐；native_pending 仅允许已选 WorkBuddy。memory_transition 恰为 before/after/scope/affected_agents/reused_conflicts，after 与授权一致。空 effective agents 仅允许有 installation 事实与 yes→no 撤权计划的情况。rebuild 与独立 confirmation 必须同时提供，registry_sha256 精确相等；confirmation 的时间/定位证据复用公共严格校验。内核仍在锁内复验完整计划与现场，CLI 扩展不成为免授权路径。

| 新测试（test_m406_cli.py） | 覆盖 |
|---|---|
| test_enable_accepts_installed_facts_and_native_pending | installation/native_pending 正例 |
| test_default_effective_subset_and_empty_revocation | 默认 installed 子集；空执行集撤权的限定条件 |
| test_enable_transition_with_reused_conflict | memory_transition 及保留冲突；授权不一致拒绝 |
| test_rebuild_requires_independent_exact_hash_binding_and_valid_evidence | rebuild 双重哈希、独立确认、日期/引用校验 |
| test_remove_rejects_each_enable_extension_check_rejects_approval | 命令间字段隔离 |
| test_unknown_or_malformed_extension_rejected | 未知字段及畸形扩展拒绝 |
| test_default_request_preserves_none_for_installed_filter | CLI 默认与显式 --agent 不混淆 |

原有 test_cli.py 的 105 条未改；新 CLI 子进程用例另验证筛选、撤权和只读源码缺口实际接线。

## 被修改的既有测试文件（精确清单）及依据

| 文件 | 改动点 → 冻结条款 | 新回归 |
|---|---|---|
| tests/unit/runtime_fixture.py | 增加合成可核验执行器信号、CLI 扫描仅限临时 HOME → §7.1/§7.2；不借宿主安装状态满足测试 | test_installed_filter_and_explicit_unknown_stop_without_foreign_entries；CLI default_agent_scope |
| tests/unit/test_m204_enable.py | 请求注入合成安装事实；完整 WorkBuddy 装配前由夹具提供原生目录 → §7.2/§8.2；原有断言未放宽 | installed_filter；WorkBuddy_installed_without_native_directory |
| tests/unit/test_m205_check.py | 健康源码夹具补最低文件和 Git 根 → R4；历史 AGENTS base 从 ok 改为 unverified → §8.1 | R4_missing_source_scripts/R4_wrong_source_type；old_base_marker |
| tests/unit/test_m206_remove.py | 原 AGENTS 整文件重叠拒绝改为保留自由基座、只摘 owned bridge，仍逐项核对输出字节和保留记录 → §8.1 | AGENTS_rules_are_free；old_base_marker/old_base_block |
| tests/unit/test_m207_faults.py | 注入安装事实及 WorkBuddy 原生目录前置；直接 no→yes 用例同样准备原生目录 → §7.2/§8.2；故障/回滚断言未放宽 | no_installed_executor；WorkBuddy_installed_without_native_directory |
| tests/unit/test_m3_workbuddy.py | 缺上游模板用例先满足原生目录前置，使其继续真正检验模板失败 → §8.2 | WorkBuddy_installed_without_native_directory；原缺模板测试仍要求 failed/零 provider 调用 |
| tests/integration/test_m204_subprocess.py | 新装 AGENTS 不再断言 #base created，改验证文件存在且独立 bridge created → §8.1 | AGENTS_rules_are_free；managed_bridge_edit |
| tests/integration/test_m207_cli_cycle.py | 合成安装信号与受限 CLI 启动器 → §7.2；正例由夹具提供原生目录 → §8.2；AGENTS 标题/base 断言改自由规则，check --all 分别验证正文可改与桥接漂移 → §8.1；新纯 CLAUDE 删除 → §8.1 | test_m406_lifecycle 的对应政策测试及三个 CLI 集成用例 |

未改变测试的故障条件、授权门禁、事务恢复/回滚、store 资产保护、reused/O2 保护断言。原 PTY 测试仍有既存 ResourceWarning（stderr 未 close），保留原状，不在本任务顺手改动。

## 未验收范围

不提供完整机器卸载、升级执行、子目录规则重构、worktree 扩展；不更新 README/SKILL 文档（M4-08）。未使用真实执行器登录/模型/新会话；installed 仅代表静态安装事实，停止自动记忆是受控指令合同，真实运行时行为仍待 M4-09 独立证据。本交接不替代主 Agent 判定。
