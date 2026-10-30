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
> [docs/plan/tasks-m4.md](docs/plan/tasks-m4.md) 推进。唯一设计依据:[DESIGN.md](DESIGN.md) v1.6;
> 实现合同:[docs/plan/architecture.md](docs/plan/architecture.md) v2;用户文档:[README.md](README.md)。

## 操作路由

- 用户请求装配/接入 → `python3 scripts/agm.py enable-memory [--project <Git根>] [--agent codex|claude|workbuddy ...] [--memory|--no-memory] [--approval-file <JSON>]`。
  - 未指定 --agent 时目标固定三家(codex、claude、workbuddy),不按残留目录缩减(现行 M2 裁定;
    DESIGN v1.6 已裁定改为仅"已验证安装"的执行器,残留 hint 不构成安装事实,M4-05 落地)。
  - 预览返回 5 时,把 stdout `next_action` 的精确计划用说人话转述给用户;用户确认后落盘为
    批准文件(补 `confirmed_at` UTC-`Z` 时间戳与 `reference` 确认出处),经 `--approval-file` 执行。
    非交互运行不得自行批准;现场与登记一致的幂等补装免新批准(由内核判定)。
- 用户请求检查/周期巡检 → `python3 scripts/agm.py check-memory [--project <Git根>|--all]`;
  只读,changes 恒为空,候选修复放 next_action,退出码 1 表示有缺口。check 不修复;缺口处置走 enable(一致修复)或人工核对。
- 用户请求撤销 → `python3 scripts/agm.py remove-memory [--project <Git根>] [--approval-file <JSON>]`;
  仅拆本工具创建的对象(链接与受管块),reused 内容、记录库与 context-keeper.json 永不触碰;
  精确计划预览需交互终端,非交互无批准只返回 5 门禁提示。
- 用户提及未接入执行器:建议接入,不自动安装;目录存在只是安装线索(hint),可能是残留,
  不构成安装事实,也不授权写入。
- 不存在第四个修复命令;没有 --force/--repair。进程崩溃后的显式恢复是库级
  `agm_core.transaction.recover_manifest`(操作员核对现场、确认并移除陈旧锁后执行),
  不是 CLI 子命令,不得擅自对生产 registry 使用。

## 输出与退出码

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
