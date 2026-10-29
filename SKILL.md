---
name: agent-group-memory
description: 跨执行器规则与项目记忆编排（规划骨架，尚不可执行）。
---

# Agent Group Memory

> 规划占位；CLI 尚未实现，不得把本文件当作已可用的安装能力。

唯一设计依据：[DESIGN.md](DESIGN.md) v1.1。
实现任务：[docs/plan/tasks.md](docs/plan/tasks.md)。

## 待实现的操作路由

- 用户请求装配／接入：enable-memory；写入由用户发起或确认。
- 用户请求检查／周期巡检：check-memory；零写入，只提示修复。
- 用户请求撤销：remove-memory；仅本工具所有权对象，记录库永不删除。
- 用户提及未接入执行器：建议接入，不自动安装。

## 必须保留的边界

基座零依赖；记忆默认推荐 context-keeper。明确拒绝须记账且不重复追问。
第四态（记录库已授权可用）之前不得写记忆。迁移门禁返回 3 立即停读写。
WorkBuddy 桥接待运行时验收；新会话三执行器接力才证明共享有效。
本期不做 Skills/MCP 管理；安装 context-keeper 是记忆装配的特定依赖操作。

## 待补内容

实现完成后补充实际命令、输出解释、授权交互、缺口处置与验收操作；不得预填成功记录。
