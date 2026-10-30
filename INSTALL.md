# 安装多 Agent 记忆融合

把下面这段复制给正在使用的任意 AI Agent，与 README 的安装请求一致：

```text
请从 https://github.com/vincent4j/agent-group-memory 安装「多 Agent 记忆融合」，
安装完成后告诉我装在了哪里、怎么给项目装配记忆。
```

本文是独立机器安装操作页，无须先装本产品、v0 工具、Context Keeper 或项目配置，也不要求当前目录是 Git 项目。合同依据为 [M4 决策 §4、§8.2、§12](docs/plan/decisions-m4.md)；M4 验收状态见 [案例清单](docs/acceptance/m4/m4-09/cases.md)，本文不代表实际安装或新会话验收已通过。

## 运行时与来源

受支持系统为 macOS，需已有 Python ≥3.9 和 Git。先检查 `python3 --version` 与 `git --version`。缺 Python 时由 Agent 或用户报告解释器无法启动，并说明手动安装 Python 3.9 或更高版本、重新打开终端再核对版本的步骤；缺 Git 时说明手动安装 Git、重新打开终端再核对版本的步骤，或提供已核验本地源的路径。安装器不自动安装系统运行时，缺必要依赖时不得报告完成；“零前置”不等于零系统依赖。Windows/Linux 不声明生产支持。

来源限上述官方仓库或用户明确提供的已核验本地 checkout。获取前固定完整 commit，核验产品代码版本与逐文件清单，记录来源 URL、commit 和清单哈希；执行中不浮动跟随 HEAD，不对 dirty checkout 做 reset/pull。获取须在安装请求与批准涵盖的暂存范围内，并由 bootstrap manifest 追踪；普通 help/check/规划不 clone、不创建缓存。网络获取遵守当前环境的委派边界，不用远程脚本管道执行。外层获取和安装器只读预览分别报告。

## 预览、批准与执行

在已核验源中运行（从其他目录调用时使用脚本绝对路径）：

```bash
python3 -B scripts/install.py --source /absolute/path/clean-checkout --commit <完整SHA> --version <SemVer>
python3 -B scripts/install.py --source-manifest /absolute/path/source.json --agent codex --agent claude
```

示例中的 `<完整SHA>` 与 `<SemVer>` 必须替换为核验值，不直接粘贴尖括号占位符。`--source-manifest` 的 JSON 含 `root/url/commit/version/files`，与 `--source/--commit/--version` 二选一。无批准只输出 `approval_plan`。安装器先排异常，再按四通道处理：全新安装、明确确认的 v0 存量复制、有效产品升级（含同版幂等）、异常停止。没有台账不自动视为 v0；非空无痕迹目录仍需真实 v0 身份确认。坏台账、未来版、来源漂移、未知身份或中断现场均停止普通安装。

计划明确来源、目标、执行器与精确写集后，由用户确认，再把确认承载于绝对路径批准文件：

```bash
python3 -B scripts/install.py --approval-file /absolute/path/install-approval.json
```

若预览显式选择执行器，执行时保持同一选择。`--agent` 可重复，不能绕过 installed 判定。默认只接入已验证 installed 者；absent 不预建目录，unknown 只报告不写。批准后安装器落位活动代码 `C = ~/.local/share/agent-group-memory`，建立公共中枢 `R = ~/.agents-group`、统一台账 `V = R/var/registry.json`，装配 installed 执行器用户入口与本产品 Skill，读回并报告。持久版本库存为 `~/.local/share/agent-group-memory-versions`，布局与回退遵守决策 §12，不自行改成 current 符号链接。

机器批准 envelope 使用独立 schema=1，绑定 command、op、R/C/V、来源与提交/清单、通道、三版本、请求/有效执行器、现场观察总指纹、精确 changes、快照/备份/暂存路径、旧账/证据映射、v0 身份确认（无则 null）、confirmed_at/reference。批准文件承载既有确认，不自证授权，不复用项目批准键。写前锁内重核，计划外变化即停。

批准文件等于输出的完整 `approval_plan` 加 `confirmed_at` 与 `reference`，不得裁剪或重造计划。`--operation-id` 可显式绑定操作；执行可从批准中读取已保存请求，再重核现场。`--request-file <绝对JSON路径>` 承载 `conversions/legacy_registries/legacy_source_commits/evidence_files/legacy_identity`；这些是内核计划输入，不是绕过来源核验或现场授权的开关。安装中断或崩溃后的恢复走独立入口 `--recover`（见下文"故障恢复"）；本 CLI 不提供日常版本降级，主动版本回退由升级内核按版本库存另立新计划执行。

独立源码获取模式为 `--acquire --staging <绝对且不存在的目录> --commit <完整SHA> --version <SemVer>`，先预览，获批后同参数加 `--approval-file` 才 clone。该模式不与普通安装/恢复参数混用；获取状态 `acquired` 只表示源码取得，`installation_complete` 仍为 false。执行网络获取仍须遵守环境委派边界。

v0 仅按批准清单快照并入 memories/references/skills，保留原文及相对链接上下文；旧索引另有快照与 legacy 阅读包。异字节冲突先停，外链不解引用复制，旧脚本/状态/mcp 不迁移、不运行。不得操作旧管理器或接管其他 Skills。

## 如何读结果报告

以下是必报语义，不约定尚未冻结的 JSON 嵌套或字段别名。

| 报告内容 | 含义与完成边界 |
|---|---|
| 状态与通道 | 区分预览、完成、partial、异常及恢复待办；下载或 clone 完成而接入失败必须报 partial，不能说安装完成。 |
| R / C / V | 公共中枢、唯一活动代码、唯一活动台账的实际绝对路径；开发 checkout 仅为本次来源。 |
| 三版本 | product_code_version、product_structure_version、schema_version 分开报告，升级列 before/after；DESIGN 版本不能代替代码版本。 |
| 来源 | URL、本次固定 commit、代码清单哈希，用于核验实际安装字节。 |
| op 与恢复位置 | 本次操作标识、manifest/journal、固定恢复工具包、快照/备份/暂存路径；恢复前仍需核验。 |
| 执行器 | 分列已接入、absent、unknown、未选及接入失败者；无 installed 时只能报中枢已建、接入待办。 |
| 复制与排除项 | 每项实际 copy/reuse/legacy_index/excluded/conflict 及原因；外链目标不能算已复制或审查。 |
| 项目下一步 | 使用用户指定的实际项目绝对根路径给出装配命令，不把安装目录当项目。 |
| runtime pending | 脚本、Skill、入口、台账读回只能证明静态安装；新会话读取公共记忆及项目接力需独立验收。 |

代码侧报告字段对应：`status`、`layout`、`versions`、`source`、`operation_id`、`recovery`、`agents.connected/absent/unknown/unselected`、`copies`、`exclusions`、`project_commands`、`project_root_required`、`runtime_acceptance`、`connection_pending`、`result`、`entries`。预览另含 `approval_required/approval_plan`。退出码：待批准为 5，completed/acquired/rolled_back 为 0，partial/failed 为 2；必须同时读状态，不能仅凭退出码 0 推断安装完成。

<!-- TODO(与代码侧核对): 集成时复核 partial 报告是否保留已成功接入子项、channel 与 before/after 三版本如何在最终报告呈现，以及备份/暂存/排除项能否由 recovery/result 精确追溯；这是 §4 报告完整性核对，不新增字段合同。 -->

装完后要接入后来新装的 Agent：进入 `/agent-group` →“添加新的 Agent”→ 输入执行器名字，由安装事实核验及同版 `--agent` 计划完成接入；不自动发现或提示。

## 给项目装配记忆

将 `/absolute/path/to/project` 替换为用户明确指定的实际 Git 主 checkout 根，再预览：

```bash
python3 -B "$HOME/.local/share/agent-group-memory/scripts/agm.py" enable-memory --project /absolute/path/to/project
```

按项目计划确认是否启用记忆及记录库位置，再使用该项目的批准文件执行：

```bash
python3 -B "$HOME/.local/share/agent-group-memory/scripts/agm.py" enable-memory --project /absolute/path/to/project --approval-file /absolute/path/project-approval.json
python3 -B "$HOME/.local/share/agent-group-memory/scripts/agm.py" check-memory --project /absolute/path/to/project
```

机器安装不自动授权任意项目记录库。项目三命令不隐式安装/升级，check 始终只读。`remove-memory --project ...` 仅撤销指定项目的本工具装配，保留机器安装、用户级接入、记录库和规则正文；本期无完整产品卸载命令。

## 故障恢复

普通安装发现未完成操作时停止并报告恢复位置，不自动删锁、不重新首装或重复导入。核对原 op、批准、固定工具包、快照/备份及现场 before/after；第三种字节或材料缺损即停。恢复是独立模式，必须有针对恢复计划的批准文件：

```bash
python3 -B /absolute/path/verified-source/scripts/install.py --recover /absolute/path/journal.json --action continue
python3 -B /absolute/path/verified-source/scripts/install.py --recover /absolute/path/journal.json --action continue --approval-file /absolute/path/recovery-approval.json
```

不能与普通安装混用；本示例中的源须仍完整可用，活动 C 混版时应采用报告指向的固定恢复工具包。无批准的恢复命令只输出 `approval_plan`；批准等于该计划加真实 `confirmed_at/reference`。需要回滚时将 `--action` 明确选为 `rollback`，重新预览并批准。继续/回滚须按冻结恢复合同选择：V 已提交且输出全为 after 时只收尾，不能借故障恢复撤回已提交版本；主动回退另走 §12 的新计划。保留失败现场，不猜成功。

`--recover` 接受安装、升级或迁账 journal，不能混用普通安装/获取参数。活动 C 不完整时，固定升级工具包提供 `python3 -B <bootstrap>/recover.py preview <journal> continue` 与 `python3 -B <bootstrap>/recover.py apply <批准计划JSON>`；使用报告所指的已核验工具包，不能把两种入口参数混用。

<!-- TODO(与代码侧核对): 集成时核对首装/迁账故障下固定恢复工具入口的可达性；升级工具包接口以 M4-07 交接为据，不将其泛化到所有恢复来源。 -->
