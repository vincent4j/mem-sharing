# M1-06 前两环运行证据

运行 ID：`20261029T111910Z`；执行者：呱唧；cwd：`/Users/vincent4j/Tools/Source/agent-group-memory`。仅执行 Codex → Claude Code；WorkBuddy 与返回 Codex 未执行。没有重跑执行器会话，没有手工修补记录库，没有 commit/push。

实际观察：两个全新会话均运行并退出 0；Codex 写入了唯一事实和未开始待办，Claude 自行从项目库读到它们，并把状态改成进行中。**不能据此宣布 M1-06 通过**：Claude 未调用 Keeper 门禁与保护流程，向 Codex 的旧会话日志追加，而非创建自己的关联日志；Codex 也采用了临时改写模块缓存路径的非标准调用。以下只报告现场，不把 CLI 的退出 0 或保存自述当验收通过。

## 前置与方法

- 任务依据：`docs/plan/tasks.md` M1-06、`docs/plan/m1-acceptance.md` B、DESIGN §2/4/5/6/8。
- 已读公共规则与 Context Keeper Skill。现有入口、Skill 链接和库沿用 M1-03/04；位置授权来自 `scripts/registry.json` 中 memory_authorization=yes、location_approved=true，引用 Paseo 消息 `4c4c4df3-3f6c-4ed5-ba98-fbb213cbbac1` 和 `7b6244d9-426f-4681-9d22-b94566ae21f1`。本轮没有安装、init、补桥或用户配置修改。
- CLI 实测版本：Codex `0.162.0`；Claude Code `2.1.295`。使用本机 `codex exec --help`、`claude --help` 核对启动参数；未指定模型、账户或 fallback。
- P0 HEAD：`3fc2696ce0fd4ce085ffd706dbeabdf0bbfea4b9`；P0 Git 工作区干净，见 [run.json](run.json)。会话中出现其他任务对 `docs/plan/architecture.md` 的修改；本任务未修改或恢复它。
- 唯一事实：`AGM-M1-20261029T111910Z-1c6de08c`；本次接力测试的纸鹤颜色是青绿色。待办：验证三执行器记忆接力。
- 首轮包含事实与未开始待办；第二轮使用验收清单的普通续接语句，不给标记、事实、路径、入口或前轮摘要。两条完整消息见 [codex-prompt.txt](codex-prompt.txt)、[claude-prompt.txt](claude-prompt.txt)。补充限制仅约束本次进度、规则/入口/用户级文件和提交推送。
- 控制员仅通过 Python 子进程记录 argv、stdout/stderr、rc、UTC，复制库快照并计算 SHA-256/mtime，使用系统 `diff -ruN` 留差异。没有编写判定脚本。证据先置系统临时目录，两会话结束后才复制到本目录，避免后一个会话从验收证据中读取答案。
- Codex 用 `--json -s danger-full-access -c approval_policy="never"`，与控制会话权限环境一致；Claude 用 `--output-format stream-json --verbose --permission-mode acceptEdits` 和命令文件列出的 allowedTools。没有使用 resume/continue、fork、追加系统答案或禁用规则加载。Claude 有真实权限拒绝，未扩大权限后重跑；不能把本次受限运行解释为所有 Claude 环境都如此。

## 会话与真实写入

| 环 | UTC 窗口 | session-id | 读写与输出 |
|---|---|---|---|
| P1 Codex | 11:19:10.971597–11:20:17.122967 | `01a18762-a4f3-7413-bd7a-8a6811222ea0` | 自行找到项目 Skill；新增测试 worklog、更新 memory-keeper；事实、待办未开始落库 |
| P2 Claude Code | 11:20:20.820226–11:21:09.748640 | `892391b4-d896-437e-886e-ab742abf4c8c` | 直接读取 memory-keeper 与测试 worklog；保留标记/颜色，把待办改进行中，追加旧 worklog；未新增独立日志 |

原始命令：[Codex](codex-command.txt)、[Claude](claude-command.txt)。完整 stdout：[Codex JSONL](codex.stdout.jsonl)、[Claude JSONL](claude.stdout.jsonl)；完整 stderr：[Codex](codex.stderr)、[Claude](claude.stderr)；启动/结束回执为各自 `*-process.json`、`*-result.json`，两者 exit_code 均为 0。

实际库路径为 `docs/context-keeper/`，变动如下：

| 文件 | P0 | P1 后 | P2 后 |
|---|---|---|---|
| memory-keeper.md | 775 字节 | 1583 字节；事实/当前待办/主题/时间线 | 1633 字节；待办及主题状态进行中 |
| worklogs/2026-10-29-三执行器记忆接力测试.md | 无 | 973 字节；Codex session marker、标题、时间、事实、待办、边界 | 1894 字节；原文保留，末尾增加 Claude 续接段，session marker 仍只有 Codex |
| worklogs/2026-10-29-仓库创建与设计演进.md | 7397 字节 | 字节哈希及 mtime 不变 | 字节哈希及 mtime 不变 |
| evolution/index.md | 78 字节 | 字节哈希及 mtime 不变 | 字节哈希及 mtime 不变 |

逐文件完整哈希、长度与原库 mtime：[before.json](before.json)、[after-codex.json](after-codex.json)、[after-claude.json](after-claude.json)。完整文本快照：`before/`、`after-codex/`、`after-claude/`。库文件集合分别为 3、4、4；空目录未列入文件 manifest，未声称监控所有目录元数据。

完整差异：[P0→P1](codex-store.diff)、[P1→P2](claude-store.diff)、[P0→P2](total-store.diff)。diff 路径和文件头时间指向采集时的临时快照；原库时间以 JSON 的 mtime_ns 为准。

## 流程偏差与限制

1. Codex 启动出现 scys-mcp OAuth 授权错误与忽略配置键警告，见 stderr 和 stdout 前几行；本任务没有使用该 MCP，也未修配置或授权。该错误没有阻止此次模型与本地文件流程完成。
2. Codex 发现 Keeper 的历史基线缓存默认写入用户目录，为遵守用户级文件限制，动态导入上游模块并在内存中替换 `_baseline_path`，指向系统临时目录。源码未改，但这不是标准 CLI 路径，不作为默认流程已通过的证据。详见 Codex stdout 第 30–31 行。
3. Codex 首次调用 record-path 后写库，coverage 返回 1：旧 legacy 日志缺 session-id，另有两条 missing_summary 提示，因此该批次未继续 save-report。随后它在另一个临时目录重新建 record-guard 基线，再运行 save-report，输出通过（第 36–37 行）。重新建基线不保留第一次写入前的同一保护缓存，不能只凭最后输出证明整个写入期间的历史保护；控制员的 P0/P1 快照独立显示原 legacy 日志字节未变。本轮只发生此一次检查再调用，未重跑执行器会话。
4. Claude 先直接读库，未先运行 resume 的迁移门禁；两条查找用户技能目录的 Bash 命令遭权限拒绝。它随后使用 Edit 修改项目库，没有调用 record-path、record-guard、save-report 或 coverage。相关读取见 Claude stdout 第 27、30 行，权限拒绝汇总见第 190 行。其“目录不允许”的解释属于会话自述，实际拒绝项见原始 permission_denials，不能扩大成 CLI 整体不可用。
5. Claude 使用 Edit 向 Codex 日志末尾追加 7 行，并更新 memory-keeper 两处状态（第 170、172、174 行）。P1 原日志正文是完整前缀，未观察到覆盖或删除原段；但跨会话复用日志、缺自身 session-id 与保护流程，违反 Keeper 的跨会话新日志要求。它在日志及最终回答中说“尚未实际执行接力验证”，这是执行器自述；控制员已经实际运行两个新会话，不能采用该说法否定本轮运行证据。
6. [protected-before.json](protected-before.json) 与 [protected-after.json](protected-after.json) 所列六个入口文件（项目 AGENTS.md/CLAUDE.md/WorkBuddy MEMORY.md，以及三家用户入口）的 SHA-256 与 mtime 完全相同。该核对仅覆盖所列文件，不等于递归证明全部用户目录零变化；CLI 自身的会话/运行元数据也不在该入口指纹证据范围。

## 当前交付边界

事实在两会话之间恢复，状态目前为进行中；标准保存和会话边界要求存在上述偏差。本轮保留为不完整流程的真实现场，不修库、不清除失败证据、不以两次 exit 0 宣布通过。下一步 WorkBuddy 操作见 [用户操作单](workbuddy-user-script.md)。继续当前 run 只能增加诊断证据；若要验收完整通过，须处理偏差后以新 run_id 从 P0 重跑，不能把后续成功覆盖本轮。

P3 WorkBuddy、P4 返回 Codex 均 not-run；N1/N2 与 M1-07 不在本次范围。仅新增本证据目录，记录库写入全部由上述执行器会话完成；控制员没有向库补写报告或经验。
