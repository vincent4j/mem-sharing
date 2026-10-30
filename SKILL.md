---
name: agent-group-memory
description: 多 Agent 记忆融合——跨执行器规则与项目记忆编排。enable-memory/remove-memory/check-memory 三命令已实现并在 macOS 完成安装/重装/卸载/失败恢复验收;Windows/Linux 未验证;WorkBuddy 桥接已由 context-keeper 上游接管,真机新会话验收待做。
---

# Agent Group Memory

> 当前状态(M3 收官,M4 进行中):三命令全部接线,281 项测试通过;WorkBuddy 桥接已回传
> context-keeper 上游接管(M3,证据见 [docs/acceptance/m3/](docs/acceptance/m3/))。macOS 四项
> 平台操作已验收(安装/重装含 M2-08 两项目真实装配与新会话读回、卸载、失败恢复,见
> [docs/acceptance/m2-platforms.md](docs/acceptance/m2-platforms.md));Windows/Linux not-run,
> 不得声称支持。WorkBuddy 桥接**待运行时验收**;M4(用户级层产品化)按
> [docs/plan/tasks-m4.md](docs/plan/tasks-m4.md) 推进。唯一设计依据:[DESIGN.md](DESIGN.md) v1.10;
> 实现合同:[docs/plan/architecture.md](docs/plan/architecture.md) v2;用户文档:[README.md](README.md)。

## 操作路由

`/agent-group` 是产品 Skill 的会话入口，不是第四个 CLI 子命令。用户只打开入口、未指定操作时，展示以下菜单；用户已说明操作则直接路由：

1. 给项目装配记忆 → `agm.py enable-memory --project <实际Git根>`。
2. 添加新的 Agent → 请用户输入执行器名字，映射为 `codex`、`claude` 或 `workbuddy`，核验安装事实后走安装器同版幂等通道：`python3 -B scripts/install.py --source-manifest <已核验源JSON绝对路径> --agent <名字>`；按精确计划批准执行。
3. 健康检查 → `agm.py check-memory --project <实际Git根>`（或明确请求的 `--all`）。
4. 撤销装配 → `agm.py remove-memory --project <实际Git根>`，只撤销指定项目装配，保留机器安装与用户级接入。

后装 Agent 接入不做自动化：不自动发现、不自动提示，由用户主动选择“添加新的 Agent”。名字输入不替代 installed 核验或精确计划批准；未知名字不猜测路径，未安装者不创建入口。安装事实核验只服务于用户主动请求。

- 产品未安装 → 先读 [INSTALL.md](INSTALL.md)，从已核验源运行 `python3 -B scripts/install.py` 安装入口，并按安装页补齐 `--source/--commit/--version` 或 `--source-manifest` 后预览；经匹配的批准文件执行机器安装。以下三命令不隐式安装或升级产品，check 始终只读。

- 用户请求装配/接入 → `python3 scripts/agm.py enable-memory [--project <Git根>] [--agent codex|claude|workbuddy ...] [--memory|--no-memory] [--approval-file <JSON>]`。
  - 未指定 --agent 时仅选择已验证 installed 的执行器；显式 --agent 也不能绕过安装事实。absent 不创建入口，unknown 只报告不写，残留 hint 不构成安装事实（M4 合同覆盖旧 M2 默认三家）。
  - 预览返回 5 时,把 stdout `next_action` 的精确计划用说人话转述给用户;用户确认后落盘为
    批准文件(补 `confirmed_at` UTC-`Z` 时间戳与 `reference` 确认出处),经 `--approval-file` 执行。
    非交互运行不得自行批准;现场与登记一致的幂等补装免新批准(由内核判定)。
- 用户请求检查/周期巡检 → `python3 scripts/agm.py check-memory [--project <Git根>|--all]`;
  只读,changes 恒为空,候选修复放 next_action,退出码 1 表示有缺口。check 不修复;缺口处置走 enable(一致修复)或人工核对。
- 用户请求撤销 → `python3 scripts/agm.py remove-memory [--project <Git根>] [--approval-file <JSON>]`;
  仅拆本工具创建的对象(链接与受管块),reused 内容、记录库与 context-keeper.json 永不触碰;
  精确计划预览需交互终端,非交互无批准只返回 5 门禁提示。
- 用户主动选择添加执行器后才进行接入核验；目录存在只是安装线索（hint），不构成安装事实，也不授权写入。
- 不存在第四个项目修复命令；没有 --force/--repair。机器安装中断使用独立安装器的 `--recover <journal绝对路径> --action continue|rollback --approval-file <批准文件绝对路径>`，详见 [INSTALL.md](INSTALL.md)。项目事务恢复仍是库级操作，不擅自清锁或对生产台账执行恢复。

## 检索与分层读取

检索 = 索引精确查找（find），不做语义搜索。按 [DESIGN v1.9 §4.7](DESIGN.md) 的读取约定：

- L0 恒读：`memories/MEMORY.md` 每主题一行，包含“主题名 + 一句话当前结论 + 链接”，索引不超过 200 行 / 25KB。
- 需要时读该主题 L1：`memories/<主题>.md` 开头几行概要，说明当前有效结论与待办。
- 仍不足才读 L2：主题全文与 `references/` 手册；不全量注入所有主题。

分层沿用索引和主题文件，不新增文件类型；概要由 Agent 整理时手写，不自动生成摘要；预算是固定惯例，不新增配置项。

## 输出与退出码

以下为项目三命令合同；机器安装报告见 [INSTALL.md](INSTALL.md)。

stdout 恒为单个 JSON envelope,字段固定:schema_version、command、status、projects、changes、
warnings、errors、approval_required、next_action;errors[] 每项含 code、path、message、recovery。
退出码(裁定 D-M2-05):0 完成、1 check 缺口、2 参数/schema/冲突/执行或恢复失败、
3 Keeper 迁移门禁、5 待授权;多结果优先级 2 > 3 > 5 > 1 > 0。

## 必须保留的边界

基座零依赖;记忆默认推荐 context-keeper。明确拒绝须记账且不重复追问。
第四态(记录库已授权可用)之前不得写记忆。迁移门禁返回 3 立即停读写。
created 对象外部漂移时 enable 拒绝写入,批准不能越过;恢复靠人工还原或 remove 后重装,
重装会有 §已知限制 所述连接符换行重排(README)。
WorkBuddy 桥接待运行时验收;新会话三执行器接力才证明共享有效。
registry/备份是本机记账文件,不随 git 分发;新 clone 须重新 enable。
本期不做 Skills/MCP 管理;仅支持主 checkout(裁定 D-M2-01:worktree 明确报告未支持)。
非交互不猜测批准;TTY 只影响能否提问,不扩大权限。

## 验收证据与限制引用

- 平台矩阵与四项操作证据:[docs/acceptance/m2-platforms.md](docs/acceptance/m2-platforms.md);
  幂等/故障矩阵:[docs/acceptance/m2-matrix.md](docs/acceptance/m2-matrix.md);
  两项目复制验收:[docs/acceptance/m2-08/](docs/acceptance/m2-08/)。
- 向用户转述装配结果时,如实区分:装配完成(rc=0、四态 ready)与运行时验收(pending)是两回事;
  不得把 CLI 退出码 0 说成"三执行器共享已生效"。
