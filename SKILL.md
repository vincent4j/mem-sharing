---
name: agent-group-memory
description: 跨执行器规则与项目记忆编排(CLI 外壳已实现,装配命令体接线中,尚不可安装)。
---

# Agent Group Memory

> M2-03 交付 CLI 外壳:严格参数解析、agents.json 路径表加载、--approval-file 结构校验、
> 稳定 JSON 输出与退出码。enable/remove/check 的执行内核尚未接线;**任何执行器都未完成
> 运行时验收**,不得把本文件当作已可用的安装能力。

唯一设计依据:[DESIGN.md](DESIGN.md) v1.1;实现合同:[docs/plan/architecture.md](docs/plan/architecture.md) v2。
任务:[docs/plan/tasks.md](docs/plan/tasks.md)。

## 操作路由

- 用户请求装配/接入 → `python3 scripts/agm.py enable-memory [--project <Git根>] [--agent codex|claude|workbuddy ...] [--memory|--no-memory] [--approval-file <JSON>]`。
  - 未指定 --agent 时目标固定三家(codex、claude、workbuddy),不按残留目录缩减。
  - 非交互(非 TTY)运行必须提供 --approval-file 绑定用户已确认的执行计划(裁定 D-M2-04),
    否则返回 5 待确认,不自行批准;交互确认流程随 enable 内核交付。
- 用户请求检查/周期巡检 → `python3 scripts/agm.py check-memory [--project <Git根>|--all]`;
  只读,changes 恒为空,候选修复放 next_action,退出码 1 表示有缺口。
- 用户请求撤销 → `python3 scripts/agm.py remove-memory [--project <Git根>] [--approval-file <JSON>]`;
  仅本工具所有权对象,记录库永不删除。
- 用户提及未接入执行器:建议接入,不自动安装;目录存在只是安装线索(hint),可能是残留,
  不构成安装事实,也不授权写入。
- 不存在第四个修复命令;没有 --force/--repair;内核接线前命令体返回 kernel_unavailable。

## 输出与退出码

stdout 恒为单个 JSON envelope,字段固定:schema_version、command、status、projects、changes、
warnings、errors、approval_required、next_action;errors[] 每项含 code、path、message、recovery。
退出码(裁定 D-M2-05):0 完成、1 check 缺口、2 参数/schema/冲突/执行或恢复失败、
3 Keeper 迁移门禁、5 待授权;多结果优先级 2 > 3 > 5 > 1 > 0。

## 必须保留的边界

基座零依赖;记忆默认推荐 context-keeper。明确拒绝须记账且不重复追问。
第四态(记录库已授权可用)之前不得写记忆。迁移门禁返回 3 立即停读写。
WorkBuddy 桥接待运行时验收;新会话三执行器接力才证明共享有效。
本期不做 Skills/MCP 管理;仅支持主 checkout(裁定 D-M2-01:worktree 明确报告未支持)。
非交互不猜测批准;TTY 只影响能否提问,不扩大权限。

## 待补内容

enable/remove/check 命令体接线(M2-04/05/06)后补充实际装配输出解释、授权交互、缺口处置
与验收操作;不得预填成功记录。
