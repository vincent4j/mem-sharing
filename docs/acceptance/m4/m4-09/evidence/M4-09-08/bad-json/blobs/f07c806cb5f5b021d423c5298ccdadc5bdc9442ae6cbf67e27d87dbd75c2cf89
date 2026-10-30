# CK 集成重构：项目侧实施交接

实现依据：决策 §17—§26，以 §24 的四要点、§25 停用三层语义及 §26 取消开发版转换承诺为准。受托范围限项目合同、入口与项目命令；CK 尾步、机器版本与旧开发版诊断退役由并行任务交付。本文件不代替主 Agent 的全量验收。

## 实现合同

- 活动台账 `schema_version=3`。项目字段为 `main_checkout / memory_policy / checkouts`；政策仅 `follow_ck / disabled`。
- checkout 字段为 `git_common_dir / agents / objects / shared_object_ids / runtime_acceptance`；不再持久化 provider、记录库位置、授权证据及四态。
- `validate_registry_v1`、`validate_registry_v2`、`load_diagnostic_registry` 严格只读解析并返回原数据。`load_legacy_registry` 是只读诊断入口别名；旧字段与旧产品身份不被规范化或改写。活动 load/write 拒绝 v1/v2，提示保全后重装，不承担开发版迁移。
- 新项目缺省 `follow_ck`。`--no-memory` 显式写 `disabled` 并加优先级明确的项目停用规则，保留 CK 安装、别名及全部数据；缺省重进不翻转。解除须显式 `--memory` 与精确批准。
- `enable-memory` 不读取 CK 源码，不抽取 AST，不运行 CK install、probe、init 或 ensure，不创建 CK 记录库或项目 Skill 链接。
- AGENTS 短协议使用 `mem-sharing:project-experience`，仅位置、入口、职责三行。Claude 只追加缺失的 `@AGENTS.md`，已有原文保留。WB 原生目录实际存在后才写顶部 `mem-sharing:project-rules` 指针；不创建原生目录。
- 旧 CK 标记块转换独立列入 `legacy_bridge_transition`，包含原块精确字节十六进制、指纹、路径、所有权和动作；created 退役重建，reused 展示后确认替换，已登记块漂移或标记异常整次零写。旧产品品牌标记是漂移，保全并指引重装。
- remove 撤入口、保留数据与 CK、政策置 `disabled`，AGENTS 留优先级明确的停用保护。单独创建的 Claude 引用及 WB 指针只按生命周期证据撤销；用户正文与共享对象仍保全。
- remove 批准封皮通过 `next_action` JSON 展示。`changes` 仅绑定文件写集，`registry_sha256` 精确绑定原账；新随机事务出处不充当批准 after hash。模块层严格检查封皮字段、整数 schema、UTC 与确认引用，不能绕过 CLI 缺证据写入。
- check 只检查项目入口、所有权、身份及字节证据。不读取 CK 源码、记录库或私有记忆，不运行 CK；CK 未安装、记录库未建立、disabled 与 WB 尚未实际使用均不是健康缺口。
- 用户级生成规则区分默认规则启用与 CK 首次保存；disabled 不得自动恢复；Claude/WB 补入口限定各自实际使用；已有 Claude 正文只追加引用。菜单缩成六行短路由。

## 文件清单

生产文件：`scripts/agm.py`、`scripts/agents.json`、`scripts/agm_core/registry.py`、`enable.py`、`check.py`、`remove.py`、`user_entries.py`。

测试：unit 的 `test_m202_entries_project_registry.py`、`test_m204_enable.py`、`test_m205_check.py`、`test_m206_remove.py`、`test_m207_faults.py`、`test_m3_workbuddy.py`、`test_m405_user_entries.py`、`test_review_r2_r3.py`；integration 的 `test_m204_subprocess.py`、`test_m206_remove_integration.py`、`test_m207_cli_cycle.py`。

## 定向验证

全部使用临时 HOME、合成执行器安装事实及 Git 夹具；未改真实 HOME 或 CK 上游，未 commit/push。

| 测试套件 | 旧方法数 | 新方法数 | 单套结果 |
|---|---:|---:|---|
| m202 unit | 33 | 33 | 33 通过 |
| m204 unit | 39 | 26 | 26 通过 |
| m205 unit | 36 | 19 | 19 通过 |
| m206 unit | 8 | 8 | 8 通过 |
| m207 faults unit | 7 | 8 | 8 通过 |
| m3 WorkBuddy unit | 4 | 4 | 4 通过 |
| m405 user entries unit | 21 | 22 | 22 通过 |
| review R2/R3 unit | 8 | 8 | 8 通过 |
| m204 integration | 8 | 8 | 8 通过 |
| m206 integration | 11 | 12 | 12 通过 |
| m207 CLI integration | 13 | 12 | 12 通过 |

本分工 8 套 unit 从 156 条调整为 128 条，3 套 integration 均为合计 32 条。减少来自 provider 安装/预览/ensure/init、四态和 store 授权探针退役，及同义健康断言合并；对应新增政策、短协议、显式旧块转换、未安装 CK 不成缺口、原始正文及直接模块批准证据测试。批准范围、锁、身份、对象所有权、事务回滚、恢复失败和字节保护回归仍覆盖。此处方法数不是全仓最终计数。

合并验证：8 套 unit 128 条全部通过（48.122 秒），3 套 integration 32 条全部通过（34.454 秒）。输出分别保留于本机临时文件 `/tmp/project-ck-unit-final`、`/tmp/project-ck-integration-final`。

额外协调检查：`test_m408_organize.py` 18 条通过；`test_m402_layout_registry.py` 初次 20 条有 2 条失败，原因是合成 remove 批准未填真实 UTC 确认证据；经主 Agent 授权，仅在 helper 补 UTC/ref 两行后复测 20 条全部通过（5.321 秒）。主 Agent 完成全仓单元和集成稳定树复跑后统一报告最终数字。

初次 m204 定向发现旧 created 块转换复用了原对象 ID，引发所有权身份保护；已改为新对象 ID 并复测 26 条通过。早期断言还包含旧 schema/四态预期，按批准的新语义改写，没有把交叠失败当作通过。

## 已知边界

CK 不识别新 `mem-sharing:project-experience` 标记，也不直接读取 memSharing 的 disabled 政策。停用保护由 Agent 遵守项目规则；这不是 CK 脚本级强制拒写接口。手动 CK 操作按用户明确请求与 CK 自身门禁处理。

历史项目级 CK Skill 别名被保留，CK 后续 ensure 可能据其重建完整 CK 块。本轮不改 CK 上游、不加额外硬门禁，不承诺项目始终只有三行协议，留用户后续裁定。

这些测试证明合成环境的代码行为，不证明真实执行器新会话已读取规则、运行期遵守 disabled 或三家经历接力已完成；这些仍是 M4-10 的独立验收层。

## B04 独立复审后的修正

主 Agent 独立复审发现：CLI 缺省 `agents=None` 会解析为三家，再按机器 installed 事实创建 Claude 引用，违反 §16 的项目实际使用前提。此前全部测试通过不能关闭这一语义缺陷；原 128/32 定向结果及主 Agent 的修前全量结果保留为修前证据。

经主 Agent 批准，本次最小修正保持安装检测、批准执行器名单、项目政策和 schema 不变：只有本次显式 `--agent` 名单包含 Claude 时，才创建/补引用或转换 Claude 内旧 CK 块。缺省既不创建不存在的 CLAUDE.md，也不补写已有正文。WB 保留 §16 明确的实际使用证据，即真实原生目录出现，并限定本次有效目标包含 WB。AGENTS 与 disabled 仍是全项目政策。

check 对没有登记 Claude 引用单元的按需状态不报入口缺口；已登记对象的缺失、漂移和引用检查仍保留。CLI 三家生命周期夹具改为显式选择三家，避免用夹具默认值掩盖实际使用条件。

新增 unit 4 条、integration 1 条（CLI 方法含“无文件”和“已有正文缺引用”两个缺省负例，以及显式 Claude 接入正例），另覆盖 Claude 旧块的作用域。项目侧方法计数更新为 unit 132 条、integration 33 条；先前数字保留为当时记录。

修后相关 7 套合并运行：`test_m204_enable` 29 条、`test_m205_check` 20 条、`test_m3_workbuddy` 4 条、`test_m406_lifecycle` 20 条、`test_m204_subprocess` 8 条、`test_m207_cli_cycle` 13 条、`test_m406_cli_lifecycle` 3 条，共 97 条全部通过，耗时 93.730 秒。原始输出 `/tmp/project-ck-b04-targeted`。`git diff --check` 通过。完成后再次冻结源码与测试，等待主 Agent 修后稳定树全量验收；不把修前全量当作修后通过。
