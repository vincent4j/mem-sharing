# memSharing 项目规则

memSharing负责跨Agent公共用户记忆共享、项目规则接入与执行器适配；产品在其他项目中保持与Context Keeper的职责分离。本仓docs只维护现行产品、平台、架构和操作说明，不保存历史记录或阶段流水。本文件只维护项目工作规则；需求入口为docs/README.md。

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

## 文档维护

有用内容按产品、平台和集成分类维护，入口为`docs/README.md`；发行依赖的架构/操作/卸载技术文档保持固定路径。不新增历史日志、证据流水、过期计划或过程归档。

<!-- mem-sharing:project-experience:start -->
本仓已退出自动项目记录库，不运行init、ensure-bridge或重建旧目录。技能仅用于必要整理，不在本仓保存过程历史。其他项目默认CK行为不变，不改全局Skill或上游CK。
<!-- mem-sharing:project-experience:end -->

## PRD 与验收约束

1. 开发前关键词检索`docs/README.md`，只读命中的分类文档；不全文加载历史。
2. 当前无独立生效合同文件，依模块PRD及明确已验范围实施；用户最新决定优先，不将Windows有限预览等同一般平台支持。
3. 源码、合成、宿主/客户端与发布分别报告；UI/新会话结论要有实际证据。
4. 本仓不采用PRD Distill的固定目录布局。可使用技能做语义整理，但不运行init/install-bridge重建目录；not_initialized是预期，不冒称结构通过。
5. 提交前核需求/实现/证据/文档一致性、有效链接和授权范围；不为文档整理重启真实验收或产品写入。
