# 项目专属硬崩溃恢复与旧安装兼容运行时验收

状态：合成 fixture 与用例通过；一处已授权最小源码修复（`transaction.py` 恢复白名单）落地后全绿。日期：2026-11-03。分支 `verify/skill-first-runtime`，基于 HEAD `4e8c2d53`。改动：新增 `tests/unit/project_share_crash_fixture.py`、`tests/unit/test_project_share_runtime.py`、本文档；经主授权修改 `scripts/agm_core/transaction.py` 一行（`_recovery_entries` 白名单加入 `share-project-memory`，与 `run()` 对齐）。未提交。

## 范围与隔离

- 全部为纯合成：临时 HOME 与临时 Git 主 checkout（`git init` + 初始提交），不读取、不复制真实私人正文/manifest/外置备份，不安装卸载真实 HOME，不启动任何原生 CLI/App/模型，无网页操作。
- 旧登记按 `scripts/agm_core/registry.py` 真实布局构造（`schema_version:3`、`projects.<main_checkout>` 记录含 `main_checkout/memory_policy/checkouts`，registry.py:163/180/500），未虚造旧 manifest 布局。
- 崩溃为真子进程 `os._exit(9)` 硬退出：不经异常回滚、不执行 finally、不释放锁。崩溃规格 JSON 指定 event/path_suffix/occurrence；规格未触发时 fixture 以退出码 3 自报。
- 写入顺序合同注意：`.workbuddy` 路径排序在 `CLAUDE.md` 之前，实际写入链为 AGENTS 公共 → WB 入口 → CLAUDE 入口 → WB 删源 → CLAUDE 删源。

## 历史失败记录与纠正（保留）

首段初版（15:36:47–15:43:30 UTC）：9 用例中旧安装 5 项 OK、崩溃 4 项 FAIL。首版报告称"四项仅因实现缺陷、所有前置全绿"不准确，主 15:44 复跑纠正：实际为 3 项失败于恢复预览 `invalid phased recovery scope`（实现缺陷），1 项（`test_crash_after_first_entry_write` 首版）因测试自身断言错误在 `crash_scene_bytes` 先失败、未到恢复步骤。同批还发现首版两处断言与实际合同不符（plan 层阻断状态为 `failed`+`code=recovery_required`；重复 `@AGENTS.md` 行执行期 fail closed 非完成），均已按实际合同修正。教训：tail 截断的失败清单不得当作全量证据。

## 实现缺陷与已授权修复（2026-11-03 主裁定）

`transaction.py` 两处 phased 白名单不对称：`run()` 允许 `share-project-memory`，`_recovery_entries()` 原仅允许 `('organize-user-rules','share-user-memory')`。后果：项目 phased 事务硬崩溃后 `recover-memory-share` 在只读核验即抛 `invalid phased recovery scope`，无法按 SKILL.md 项目行与 `final_list` 承诺回滚；备份与清单完好，仅白名单拦截。主授权最小修复：`_recovery_entries` 白名单加入 `'share-project-memory'`（一行），已落地；其余源码零改动。

## 最终命令与证据（2026-11-03 15:45–15:48 UTC 实际执行）

| 命令 | 用例 | 结果 |
| --- | --- | --- |
| `python3 -B -m unittest tests.unit.test_project_share_runtime` | 12（硬崩溃恢复 7 + 旧安装兼容 5） | OK |
| `python3 -B -m unittest tests.unit.test_fusion_phases tests.unit.test_fusion_recovery tests.integration.test_m202_transactions` | 32（事务白名单改动回归，主指定） | OK |
| `python3 -B -m unittest tests.unit.test_project_share` | 20（既有项目套件，确认零影响） | OK |

### 硬崩溃恢复用例（7 项，每项独立子进程 `os._exit(9)` 后同一合同链）

覆盖关键阶段：公共写入前、公共落盘后、首个入口（WB 桥块）落盘后、第二入口（CLAUDE `@AGENTS.md`）落盘后、首处删源（WB）写入前、首处删源落盘后、最后删源（CLAUDE）落盘后。删源后两例断言已删原文确实从文件移除，恢复后逐字节回到共享前原文——证明删源内容可恢复，而非只覆盖删源前阶段。

每例断言：退出码恰为 9 且零输出；恰一份 manifest 状态 `applying` 持久于 `<项目>/.mem-sharing/backups/`；两层陈旧锁（`var/.agm.lock` 及其 `transaction` 子锁）存在；新共享被未闭合事务阻断（`code=recovery_required`）；`write_lock` 原语对陈旧锁 `lock_conflict` 拒绝抢占；恢复在陈旧锁现场拒绝完成且零写；崩溃现场字节按文件实际阶段核验（original / 原文前缀完整+入口恰一个 / 删源终态且原文确已移除）；操作员处置两层陈旧锁后恢复只读核验 `approval_required`（再次零写）→ 批准回滚 `rolled_back` → 三文件逐字节回原文 → 锁释放 → `plan_share` 可重新预览。

### 旧安装兼容用例（5 项）

- 真实 v3 登记 `follow_ck` 放行；已有 `@AGENTS.md` 行与 WorkBuddy 受管桥块原样保全不重复，共享仍完成迁移删源。
- 登记 `disabled`：`project_disabled` 拒绝且零写。
- 损坏 JSON 与缺 `memory_policy` 键登记：`disabled_unknown` fail closed。
- WorkBuddy 桥块漂移（双标记）：预览即 `entry_conflict` fail closed。
- CLAUDE 双 `@AGENTS.md` 行：预览放行、执行在删源守卫 fail closed 回滚（"入口未就绪"），不产生无入口删源。

## 六家真实 Skill/原生新会话运行计划（v2，隔离优先；仅计划，全部 pending）

主审核否决 v1"第一步写真实 HOME 正文快照"（与隔离优先边界冲突）。v2 改为：先建立并验证隔离环境，真实 HOME 快照仅在隔离方案被证不可行且用户单独授权后才可能进入，当前不进行任何真实私文读取或原生启动。以下仅基于仓库合同（根 SKILL.md、docs/memory-sharing-fusion-prd.md、INSTALL.md、runtime-next），逐家（Codex、Claude Code、WorkBuddy、DSH、ZCode、OpenCode）独立执行与取证：

1. 隔离方案建立（待授权动作 A：创建独立 macOS 测试用户或 VM）：在隔离环境内布置纯合成规则文件（合成 HOME、合成 Git 项目，输入只来自合成 fixture，位置在隔离环境的临时目录，不复制任何真实私文）。仅改 HOME 不构成原生隔离（runtime-next 合同）。
2. CLI 与 App 分别验证可用性（待授权动作 B：在隔离环境内启动该家 CLI/App）：启动前核查该进程实际 HOME、配置根、数据根均落在隔离环境内，且无外部私文访问路径；未完成核查不启动模型/会话。
3. 阶段一 Skill 对话链（隔离环境内）：合成原文预览 → 两块稳定编号 → `查看 N` 零写核验 → 用户选择 → 完整确认清单（解码 after_hex、删源范围、恢复位置）→ 人类实际批准（真实 `confirmed_at`/`reference`）→ 执行。
4. 阶段二 新会话加载链：隔离环境内新开该家原生会话，以合成查询取证公共记忆/项目规则被实际读取（读取证据而非仅入口存在）。
5. 还原与证据：`return-*-memory` 全量归还 + 入口剥离，逐字节比对合成基线；记录读取证据、manifest 与退出码。

写入范围（批准前零写检查）：批准前一切操作只读（预览/查看/核验零写）；批准后写入仅限隔离环境内该家合成原生文件、合成 `~/.mem-sharing/memories/` 或合成项目目录。撤销路径：各家 return 命令 + `recover-memory-share --manifest`；隔离环境可整体销毁重建。停止条件：任何 drift/`lock_conflict`/未知来源/入口冲突/进程 HOME 或数据根越出隔离环境即停，只读取证，不抢锁、不删备份、不越过人类批准。网页/App 图形操作属章教授职权，本计划不含。

## 未完成项

- 真实隔离环境建立、六家真实运行：未开始，全部 pending（计划见上节，待授权动作 A/B）。
- 插件外围、Windows/Linux：不在范围。本阶段不 commit/push。`docs/context-keeper/` 由主维护，本切片未触碰。
