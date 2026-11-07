# Paseo 载荷同步审核准备

更新：用户现已批准 0.1.11 与主 Agent 本地 S/R 提交。以下无版本或提交授权的描述为前一阶段审核事实；当前正在专用 worktree 准备源码态，尚未固定 S/R，不重跑既有整批测试。

## 已核实输入与差异

本轮固定审核 HEAD 为 `2f2ace967fa80eb85c2b1b6317a4f959cb193f7d`。现有载荷仍声明 source `3c14b053` / `0.1.10`，不能作为本轮源码的发行身份。当前未取得新版本或提交授权，未运行正式 generate、未替换仓库载荷、未安装。

复用 `scripts/agm_core/plugin_release.py` 的受管文件选择规则，从固定 HEAD 的 Git blob 导出原始文件审核副本，逐文件核验 SHA-256、mode 和文件集合。当前为 49 文件：8 份文档与 41 份 scripts 文件。相对现有载荷：

- 内容或模式发生差异：`INSTALL.md`、`SKILL.md`、`scripts/agm_core/ck_install.py`、`scripts/agm_core/memory_share.py`、`scripts/agm_core/uninstall_memory.py`、`scripts/agm_core/user_rules_organize.py`。
- 缺失模块：`scripts/agm_core/ck_common_trigger.py`。
- 无待移除的受管文件。

文档集合以生成器的 `SHIPPED_DOCS` 为准：`SKILL.md`、`README.md`、`INSTALL.md`、`llms.txt`、`DESIGN.md`、`docs/architecture.md`、`docs/operations.md`、`docs/uninstall-design.md`。

## 审核材料与边界

本轮临时材料位于 `/private/var/folders/r6/qgw1rpbj2q51tgk942d0vz4w0000gn/T/memsharing-paseo-review-tr7gwq9x/`：

- `fixed-head-checkout/`：本地隔离 clone，HEAD 固定且导出前后干净；本地来源不构成官方来源证明。
- `raw-managed-files/`：49 个受管原始文件，只供核对；没有赋予新版本，也没有发行 manifest 或 identity。此目录不是插件安装来源或 S/R 产物。
- `inventory.json`：完整实算 SHA-256 / mode 清单、六个变更和一个新增文件。
- `source-gate.command.json`、`source-gate.stdout`、`source-gate.stderr`、`source-gate.exit`：隔离 checkout 的原始 source gate 证据。退出 2，按预期拒绝旧 manifest / payload / identity；不能描述为 source 检查通过。
- `OVERVIEW.diff`：本轮中英文文案改动。

临时目录可能被系统清理；这里记录结论与复算依据，不将它视作持久正式发行证据。正式候选路径：无。没有借用 0.1.10 为新内容生成替换包，没有手填摘要，没有跳过或降低 source / release 门禁。

## 正式同步所需的最小后续操作

由主 Agent 取得相应授权后，按 `tools/plugin-release/README.md` 执行：

1. 在专用源码 checkout 纳入完成的源码和本轮 OVERVIEW 文案；保留当前工作区已有 CK 修改的归属。不能把旧 main HEAD 直接改称 S。
2. 删除旧 `release/core-release.json` 与完整 `plugins/paseo/payload/` 树；将 `plugins/paseo/server/shared/release-identity.ts` 恢复为开发空字符串哨兵。当前三类路径共 51 个跟踪文件（50 个旧生成文件待删除，1 个 identity 恢复）；禁止在旧 payload 上混合覆盖。
3. 运行既有 `node plugins/shared/sync-to-plugins.mjs`，审核 common / notices；由主 Agent 获授权后提交源码为新 S。要求 HEAD 为完整 S、全树干净、旧生成物物理上不存在，运行 `check.py source` 并通过。
4. 使用用户明确批准的新产品版本，从干净 S 向外部尚不存在的目录运行正式 generate，再向另一目录重复生成比较。当前原始审核导出不能替代此步骤。
5. 在同一 S checkout 只回填正式生成的根 manifest、完整 payload 与 identity；核对 49 个当前受管文件（届时以 S 的规则实算）、模式和闭包。只提交允许生成物形成 R；不在 R 运行 sync。
6. 在 clean、完整固定 R 上运行 `check.py release`，通过后才进入获授权的宿主安装与真实 UI 验收。UI 由章教授负责。主 Agent 最新转述其原生 UI 证据为：当前插件 revision `2f2ace967fa8`、`running`、Command Center 九入口通过；这不证明新载荷已经同步，也不证明融合写入、新会话或缺依赖机器已通过。本执行任务未操作 UI，界面证据由主 Agent 汇集。

无新 S 提交与获批版本，正式生成保持阻断；无 R 提交与 release gate，不能声称得到可安装正式候选。本轮源码和合成测试结果另见统一测试证据，不提升为真实宿主通过。

## 统一检查与只读 UI 补证

本轮一次统一检查：`npm --prefix plugins/paseo run typecheck` 退出 0；`npm --prefix plugins/paseo test` 67/67 通过；`test_plugin_release`、`test_release_source_gate`、`test_release_closure` 合计 26/26 通过；`test_plugin_release_cli.py` 集成 2/2 通过。全部退出 0，零失败、零跳过。审查根 `tests-results.json` 记录实际捕获的退出码、完整 argv、耗时、计数及 stdout / stderr / .exit 路径；`evidence.sha256` 提供对应文件摘要。未重跑同批。主 Agent 回报独立审查无阻断发现。

主 Agent 最后转述章教授的原生 AX 证据（无截图）：`ms-status` 的 Python ready（3.9.6，`/usr/bin/python3`）、Git ready（2.54.0）、插件载荷 ready / 发行身份就绪；持久 source-manifest 位于 `0.1.10` 目录；onboarding 列出 codex / claude / workbuddy / dsh / zcode / opencode 六家，未点击生成精确预览或执行写入。宿主 revision 较 payload source 新，不自动构成状态 bug；ready 证明现包完整性，不能证明它与最新源码一致。融合执行、拒绝、错误恢复、CK 安装及新会话读取未在这组只读 UI 证据中验收。
