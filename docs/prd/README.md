# PRD 模块索引

memSharing：多 Agent 记忆共享与融合，给你的每一个 AI Agent 同一份记忆。

本目录从本次完整会话提炼当前有效需求，后续按模块维护。用户最新明确决定优先于旧设计；本轮尤其取消融合后的二次确认，将 Context Keeper 推荐移到公共用户记忆流程结束之后。PRD 描述目标行为，不以文档存在代替实现或运行验收。

## 模块列表

| 模块 | 说明 | 主 PRD | 合同 / 不变量 | 相关 plans |
|---|---|---|---|---|
| 安装与原生入口 | 六家探测、选装、补装、幂等、安装对话、Context Keeper 尾步 | [installation.md](installation.md) | 本文验收标准；暂无独立生效合同 | — |
| 公共用户记忆与融合 | 保存归属、索引、两块编号、选择即执行、精确去重 | [sharing.md](sharing.md) | 本文验收标准；暂无独立生效合同 | — |
| 项目规则接入 | AGENTS、自动接入、各家桥接、Context Keeper 边界 | [project-rules.md](project-rules.md) | 本文验收标准；暂无独立生效合同 | — |
| 卸载与恢复 | 全机卸载、正文归还、来源次数、事务恢复 | [uninstall-recovery.md](uninstall-recovery.md) | 本文验收标准；暂无独立生效合同 | — |

## 阅读与验收边界

- 工作方法：Agent 理解、用户决定、小工具准确修改。工具不承担语义判断，不用摘要替换用户正文。
- 六家是 Codex、Claude Code、WorkBuddy、DeepSeek Harness、ZCode、OpenCode。文件适配、原生发现、模型实际读取分别验收；不承诺各客户端采用同一种斜杠语法。
- 当前实证以 macOS 为主；Windows、Linux 保持待验。
- 源码、合成测试、真实安装、客户端发现和模型读取分层报告。受影响测试通过不等于全量或真机通过。
- 保留必要的安装、卸载、归还、恢复和宿主适配能力；有明确无消费者证据的一次性事故工具可删除，不能按模块名字推断废弃。
- 产品数据不随源码文档任务修改。发布、部署与提交分别依用户授权。

## 资料关系

[融合详细规格](../memory-sharing-fusion-prd.md)提供具体分组与示例，与本目录保持一致；历史验收与复盘是证据，不覆盖最新需求。
[安装与本机验收](../acceptance/skill-first-real-reinstall.md)、[六家原生分发验收](../acceptance/six-native-skill-distribution.md)、[项目恢复验收](../acceptance/skill-first-project-runtime.md)记录各自当时的验证范围。本轮新增交互不得直接借用旧证据宣称通过。

项目已启用 PRD Distill；[合同索引](contracts/README.md)只登记有明确测试绑定与证据的合同。
