# memSharing 项目规则

memSharing 负责跨 Agent 的公共用户记忆共享、项目规则接入与执行器适配；产品在其他项目中保持与 Context Keeper 的职责分离。本仓已按用户要求改用 docs/ 根文档维护项目状态、历史和经验，不再自动建立记录库。本文件只维护项目工作规则；产品需求与验收标准见 docs/README.md，进度和事实见 docs/project-state.md，不写入规则文件。

## 结构与检查

- Python 内核：仅使用标准库，无需构建；入口为 `python3 scripts/agm.py`。
- Paseo 插件：位于 `plugins/paseo/`，使用 TypeScript；检查命令见下方。
- macOS 有现有生产实证；此DELL上ZCode/WorkBuddy首次Windows预览闭环已限定通过，一般Windows及Linux仍待验。

## 测试

- Python 全量：`python3 -m unittest discover -s tests/unit && python3 -m unittest discover -s tests/integration`
- Python 单套件：`python3 -m unittest discover -s tests/unit -p 'test_cli.py'`
- Paseo 插件类型检查：`npm --prefix plugins/paseo run typecheck`
- Paseo 插件测试：`npm --prefix plugins/paseo test`

按改动范围运行相应检查；源码、合成测试与真实宿主验收分别报告，无真实运行证据的项目保持待验。

## 约定

- Git 提交、推送仅在用户明确指令下由主 Agent 执行；子 Agent 不得自行 commit/push。
- 不修改上游 Context Keeper 源码。

## 项目文档与经历

用户明确将有用文档归并到docs根并删除旧三目录。当前状态见`docs/project-state.md`，历史结论见`docs/project-history.md`，经验边界见`docs/project-lessons.md`。

<!-- mem-sharing:project-experience:start -->
本仓已明确退出原Context Keeper自动记录目录；不自动init、ensure-bridge、建库或重建已删除目录。后续直接维护上述docs根文档。其他项目的产品默认CK行为不变，不改全局Skill或上游CK。
<!-- mem-sharing:project-experience:end -->

## PRD 与验收约束

1. 开发前关键词检索`docs/README.md`，只读命中的docs根PRD/验收；不全文加载历史。
2. 当前无独立生效合同文件，依模块PRD及明确已验范围实施；用户最新决定优先，不将Windows有限预览等同一般平台支持。
3. 源码、合成、宿主/客户端与发布分别报告；UI/新会话结论要有实际证据。
4. 本仓已退出原PRD Distill固定目录布局。可使用技能做语义整理，但不运行init/install-bridge重建目录；not_initialized是预期，不冒称结构通过。
5. 提交前核需求/实现/证据/文档一致性、有效链接和授权范围；不为文档整理重启真实验收或产品写入。
