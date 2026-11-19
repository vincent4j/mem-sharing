---
name: mem-sharing
display_name: 多Agent编排记忆共享与融合 memSharing
display_name_en: memSharing
description: 给你的每一个 AI Agent 同一份记忆。Codex 记住的偏好，Claude Code 和 WorkBuddy 接着用；昨天做到一半的工作，今天任何 Agent 接着做。
description_zh: 给你的每一个 AI Agent 同一份记忆。Codex 记住的偏好，Claude Code 和 WorkBuddy 接着用；昨天做到一半的工作，今天任何 Agent 接着做。
description_en: Share one set of memories across AI agents and pick up unfinished work across sessions.
version: "@VERSION@"
author: vincent4j
examples_zh:
  - 找出 Codex、Claude Code 和 WorkBuddy 里重复的用户偏好，先给我看共享方案。
  - 整理当前项目的 Agent 规则，列出可以共享的约定，以及它们原来在哪些文件里。
  - 预览把这条共享偏好归还给原来的 Agent，告诉我会改动哪些文件。
examples_en:
  - Find duplicate preferences across Codex, Claude Code, and WorkBuddy and show a sharing proposal.
  - Review the project rules and show what can be shared and which files contain those rules.
  - Preview returning a shared preference to its original agents and show which files would change.
---

# memSharing · WorkBuddy

适用于 macOS。需要 Python 3.9+ 和 Git。Windows 仅有单独的限定预览验收，本市场包以 macOS 流程为准。加载技能时无需执行命令。

用户明确要求安装或使用功能后才准备离线源文件。在本技能目录执行 `python3 -B offline.py source`，从输出的路径读取产品 SKILL.md 和 INSTALL.md。下文优先于其中的在线获取说明。共享、归还、整理沿用产品流程及其确认条件，从该源码路径运行命令。

## 安装与确认

1. 运行 `python3 -B offline.py install` 生成计划。可用重复的 `--agent` 限定目标。根据实际检测结果展示将接入的 Agent，沿用 INSTALL.md 的确认流程。退出码 5 表示等待确认。
2. 获得用户确认后，按 INSTALL.md 将真实确认和完整计划写入批准文件，再执行 `python3 -B offline.py install --approval-file <批准文件绝对路径>`。普通安装完成后按产品流程展示共享预览。
3. 用户完成整理或明确暂不整理后，单独询问是否安装 Context Keeper。只有明确选择“安装”才运行 `python3 -B offline.py context-keeper`。可用 `--operation-id` 指定已完成主操作。沿用产品安装确认合同，根据返回的实际范围及用户真实确认生成独立批准文件，再执行 `python3 -B offline.py context-keeper --approval-file <批准文件绝对路径>`。
4. Context Keeper 使用打包时从官方 main 获取并固定的源码。若本机已存在其他版本或有本地修改的独立源码，报告冲突并保留现有文件。离线路由报错时直接说明，安装、预览和升级均不回退到在线获取。仅在输出确认入口已配置后报告完成，新会话验证另计。

本技能只在用户明确请求对应操作时运行。WorkBuddy 在当前会话分析所选文件，进入模型上下文的内容受 WorkBuddy 数据设置约束。先确定参与者与读取范围，排除凭据及无关文件。
