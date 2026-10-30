# M4-08 文档与 M4-09 预备交接

开工基线 `fe1f832`，开工 `git status --short` 为空。只写 INSTALL.md、llms.txt、README.md、SKILL.md 与本目录文档；未改代码/测试，未执行安装、验收、commit 或 push，未操作真实中枢。并行期间出现的 scripts 与 tests 变更归代码侧。

## 五件交付

1. [INSTALL.md](../../../../INSTALL.md)：独立安装入口、来源、前置、四通道、精确批准、报告、项目命令与恢复。
2. [llms.txt](../../../../llms.txt)：仓库根与 docs 文档地图，按五组逐文档链接，验收快照明确为历史证据。
3. [README.md](../../../../README.md)：三处微调——维护行卸载措辞、撤销 FAQ 范围、检索 FAQ；安装请求原文保持不变。
4. [SKILL.md](../../../../SKILL.md)：v1.9、L0/L1/L2、精确查找、未安装路由及 `/agent-group` 四项菜单。
5. [cases.md](cases.md)：34 项案例及各子现场原始证据要求，全部未执行，判定留给主 Agent。

已纳入新裁定：后装 Agent 不自动发现、不自动提示，只由用户选菜单“添加新的 Agent”并输入名字，经 installed 核验与同版 `--agent` 计划接入。与旧 DESIGN/任务书/决策中的提示措辞冲突处，由主 Agent 在其写集内同步，本任务不改这些文件。

## 主 Agent 集成核对项

- 菜单名 `/agent-group` 与实际 Skill 注册/宿主发现名 `agent-group-memory` 的映射：文档定义会话入口，未声明已验证 slash alias；需新会话确认能找到菜单。
- 代码侧显式 source/commit/version 或 source-manifest、request-file、operation-id、重复 agent、approval-file、acquire/staging、recover/action 已静态对照当前 scripts/install.py；批准复制完整 approval_plan 加 confirmed_at/reference。并行代码仍可能变化，集成时复核。
- 后装不自动发现/提示的新政策：检查项目 check/enable 的提示及入口路径，不能仅靠文档改变行为；保留用户主动操作时必要的安装事实核验。
- 报告完整性：partial 下是否保留成功子项，channel、三版本 before/after、复制/排除和恢复路径是否可精确追溯；当前 TODO 不代表通过或许可省略合同字段。
- 固定恢复工具：升级 bootstrap/recover.py 已有交接接口；首装/迁账的独立恢复可达性仍需核对，不能假定混版 C 可执行。
- 34 案执行前补齐 HOME/探测隔离、实际 P/T 清单路径、故障注入与旧写者精确 argv。沿已有接口取原始证据，不新增判定脚本。用户未批准真实 v0 操作。
- llms.txt 的仓库相对链接在发布/安装产物中的可达性需与代码清单核对；当前静态检查只证明 checkout 内可达，不证明安装 C 携带全部 docs。

## 本轮检查与限制

`git diff --check` 无输出；五件文档本地相对链接存在性检查无缺失；README 与 INSTALL 的安装请求逐字相同。未运行单元/集成测试、M4-09 案例或新会话验证，静态检查不构成验收结论。项目记录库不在本次写集，交接事实留本页，由主 Agent 统一收录。
