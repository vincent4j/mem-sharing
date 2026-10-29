# agent-group-memory

多 Agent 跨执行器共享记忆的**互通编排层**:让 Codex、Claude Code、WorkBuddy 在同一个项目里共用一份记忆,换工具不失忆。

**不自建项目记忆**——项目记忆直接复用 [context-keeper](https://github.com/vincent4j/context-keeper):本仓库负责自动安装、入口配置与未验收执行器(WorkBuddy)的桥接。三套系统的分工边界见 [DESIGN.md](DESIGN.md) §2。

- 用户级共享(`~/.agents-group`)已独立建成,不在本仓库范围。
- 历史回溯(装 context-keeper 之前的会话回填)属 context-keeper 的可选功能,不在本仓库范围。
