# memSharing 项目规则

memSharing 负责跨 Agent 的公共用户记忆共享、项目规则接入与执行器适配；项目经历由 Context Keeper 独立管理。本文件维护项目工作规则；产品需求与验收标准见 docs/prd/。进度、事实与经验记入项目经历记录库，不写入规则文件。

## 结构与检查

- Python 内核：仅使用标准库，无需构建；入口为 `python3 scripts/agm.py`。
- Paseo 插件：位于 `plugins/paseo/`，使用 TypeScript；检查命令见下方。
- 当前实证平台为 macOS；Windows、Linux 尚未验证。

## 测试

- Python 全量：`python3 -m unittest discover -s tests/unit && python3 -m unittest discover -s tests/integration`
- Python 单套件：`python3 -m unittest discover -s tests/unit -p 'test_cli.py'`
- Paseo 插件类型检查：`npm --prefix plugins/paseo run typecheck`
- Paseo 插件测试：`npm --prefix plugins/paseo test`

按改动范围运行相应检查；源码、合成测试与真实宿主验收分别报告，无真实运行证据的项目保持待验。

## 约定

- Git 提交、推送仅在用户明确指令下由主 Agent 执行；子 Agent 不得自行 commit/push。
- 不修改上游 Context Keeper 源码。

## 项目经历

本项目已有记录库 `docs/context-keeper/`，按已安装的 Context Keeper Skill 管理；不重复初始化，也不在本文件复制其保存、检索和记录格式规则。

<!-- mem-sharing:project-experience:start -->
位置：项目经历记录库由 Context Keeper 管理，默认位于 docs/context-keeper/。
入口：使用 /context-keeper，首次保存按 Context Keeper 流程确认位置并初始化。
职责：命令、记录格式、保存与查找流程由 Context Keeper 自行定义。
<!-- mem-sharing:project-experience:end -->

<!-- prd-distill:start -->
## PRD / 合同约束

开发、修 bug、改行为或遇到陌生业务词时，先检索项目知识库，不全文加载文档。

1. 用模块名、业务词、文件名、接口名、字段名、错误现象或合同 ID 检索 `docs/prd/README.md`，只读命中上下文。
2. 继续在相关 PRD / 合同中关键词检索，只读命中条目；命中不清、跨模块或触碰核心流程 / 数据 / 安全边界时才扩大读取。
3. 历史经验由 context-keeper 提供；按需消费已定位的有限证据，不依赖 context-keeper 也能运行。硬约束以 `docs/prd/contracts/` 为准。
4. 编码前有命中则列最多 5 条 `受影响合同：<ID>：原因；证据：类型`；无命中只说 `未命中生效合同`。
5. 实现后只验受影响合同；UI / UX / 视觉 / 交互 / 响应式需截图、DOM 或页面证据；无匹配证据不能宣称完成。
6. 最终只报告命中合同状态 `通过 / 部分通过 / 未验证 / 不适用`；提交前若改了 PRD / 合同，先做 PRD Distill 收尾。
<!-- prd-distill:end -->
