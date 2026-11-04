# 项目规则接入 PRD

## 自动接入

首次进入未登记的 Git 主工作目录时，默认启用项目规则：创建缺失的 AGENTS.md 骨架并追加项目经历短协议，完整保留已有内容。非 Git 目录、linked worktree、历史 disabled 项目跳过；重新接入 disabled 须用户明确计划，不能默认重建。

项目已接入后，当前 Agent 首次实际使用时，只补自身缺失专属入口，不替其他 Agent 预建。Claude 缺失 CLAUDE.md 时建立必要 `@AGENTS.md` 引用；已有全文保留，只追加缺失引用，重复执行零写。WorkBuddy 按原生入口合同处理。公共 AGENTS 的默认创建不取决于是否安装 Codex，常驻规则无需重复解释这项常识。

## Context Keeper 边界

项目经历由 Context Keeper 独立管理。默认接入不安装 Context Keeper、不初始化记录库、不调用其安装器。首次 `/context-keeper` 按上游流程选择保存位置和初始化。

memSharing 不提供项目经历启停开关，不撤销或否决上游行为。历史 disabled 只表示本产品项目规则登记停用，不代表 Context Keeper 停用或既有入口已移除。不修改上游源码或既有经历。

## 项目内容融合

只分析本次当前项目及有效来源，按独立真实文件去重计算参与集合；AGENTS.md 的真实来源不能漏计，别名不能重复增加分母。原文、作用域、字节范围和稳定编号遵守用户记忆融合要求。

公共项目目标和每个读取入口必须先核验，再删除来源；只修改选定范围，保留其他项目/执行器入口和 Context Keeper 协议。

## 验收标准

覆盖空项目/已有 AGENTS/已有 CLAUDE 正文/重复引用、首次当前 Agent 接入、disabled/non-Git/linked worktree 跳过、旧安装兼容、入口先于删源、逐阶段硬崩溃恢复。合成 Git 项目通过不代替真实客户端新会话加载验证。
