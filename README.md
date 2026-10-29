# agent-group-memory

多 Agent 跨执行器共享记忆:让 Codex、Claude Code、WorkBuddy 在同一个项目里共用一份项目级记忆,换工具不失忆。

**设计方案见 [DESIGN.md](DESIGN.md)**:单一公共源 + 原生入口指针 + 蒸馏管道(自蒸馏 → 批量收割 → 定期压缩),全部提交进 Git。

用户级互通已由 `~/.agents-group` 解决,本仓库只负责项目级与蒸馏能力。
